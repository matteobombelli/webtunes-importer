"""Import orchestration: resolve a link (or one search row) to YouTube audio,
download it to a temp dir, upload it to WebTunes, clean up.

Ported from the exporter's worker jobs; the destination changed from a local
folder to WebTunesClient.upload_track, and 409 duplicates are reported apart
from misses.
"""

import re
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from webtunes_importer.config import Settings, missed_file_path
from webtunes_importer.constants import MIN_SOURCE_KBPS
from webtunes_importer.core.apple_music import apple_music_tracks
from webtunes_importer.core.download import download_audio, sanitize
from webtunes_importer.core.matching import best_audio_kbps, find_match, make_ydl
from webtunes_importer.core.models import TrackMeta
from webtunes_importer.core.queue_model import ImportItem, ItemStatus
from webtunes_importer.core.ratelimit import run_with_retry
from webtunes_importer.core.runtime_deps import find_ffmpeg
from webtunes_importer.core.spotify import spotify_track_noauth, spotify_tracks_noauth
from webtunes_importer.core.webtunes import (
    AuthRevokedError,
    DuplicateTrackError,
    WebTunesClient,
)


def classify_url(url: str) -> str | None:
    """"spotify" | "apple" | "youtube" | None."""
    if "open.spotify.com" in url and re.search(r"(playlist|track)/([A-Za-z0-9]+)", url):
        return "spotify"
    if "music.apple.com" in url and re.search(r"/(playlist|album|song)/", url):
        return "apple"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    return None


@dataclass
class Emit:
    """Callback bundle the GUI worker wires to Qt signals. Defaults are no-ops
    so core code is runnable (and testable) without a GUI."""

    log: Callable[[str], None] = lambda msg: None
    progress: Callable[[int, int], None] = lambda done, total: None
    counts: Callable[[int, int], None] = lambda imported, missed: None


@dataclass
class JobResult:
    total: int = 0
    imported: int = 0
    duplicates: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)  # "label (reason)"
    cancelled: bool = False
    missed_file: Path | None = None

    @property
    def summary(self) -> str:
        parts = [f"{self.imported} imported", f"{len(self.missed)} missed"]
        if self.duplicates:
            parts.append(f"{len(self.duplicates)} already in WebTunes")
        prefix = "Cancelled" if self.cancelled else "Done"
        return f"{prefix}: " + ", ".join(parts) + f" (of {self.total})."


def write_missed_file(source_url: str, missed: list[str]) -> Path:
    """Overwrite last-missed.txt with this run's misses. Always written - an
    empty run truthfully records that nothing was missed."""
    path = missed_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Missed tracks - {datetime.now():%Y-%m-%d %H:%M}",
        f"# Source: {source_url}",
        "",
    ]
    lines += missed if missed else ["(none - every track was imported)"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _download_and_upload(
    video_url: str,
    name: str,
    settings: Settings,
    client: WebTunesClient,
    *,
    meta: TrackMeta | None = None,
    on_percent: Callable[[int], None] | None = None,
    on_uploading: Callable[[], None] | None = None,
) -> None:
    """One video: download into a fresh temp dir, upload, delete the dir.

    meta present (Spotify/Apple path): its title/artist/album/art win, square
    art as-is. meta absent (YouTube path): metadata comes from the video and
    the 16:9 thumbnail is square-cropped server-side."""
    tmp = tempfile.mkdtemp(prefix="webtunes-import-")
    try:
        path, video_meta, thumb_url = download_audio(
            video_url,
            str(Path(tmp) / sanitize(name)),
            quality=settings.quality,
            ffmpeg_path=find_ffmpeg(),
            on_progress=on_percent,
        )
        if on_uploading:
            on_uploading()
        if meta is not None:
            client.upload_track(
                path,
                source_url=video_url,
                title=meta.title,
                artist=meta.artist,
                album=meta.album,
                art_url=meta.art_url or None,
            )
        else:
            client.upload_track(
                path,
                source_url=video_url,
                title=video_meta["title"],
                artist=video_meta["artist"],
                album=video_meta["album"],
                art_url=thumb_url,
                art_crop_square=True,
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_link_job(
    url: str,
    settings: Settings,
    client: WebTunesClient,
    emit: Emit,
    cancel: threading.Event,
) -> JobResult:
    """Import everything behind a pasted link. Raises AuthRevokedError if the
    connection dies mid-run (the worker turns that into a disconnect); any
    other per-track failure is recorded as a miss and the job continues."""
    kind = classify_url(url)
    if kind == "spotify":
        result = _run_matched_job(url, "spotify", settings, client, emit, cancel)
    elif kind == "apple":
        result = _run_matched_job(url, "apple", settings, client, emit, cancel)
    elif kind == "youtube":
        result = _run_youtube_job(url, settings, client, emit, cancel)
    else:
        raise ValueError("Enter a Spotify, Apple Music, or YouTube URL.")

    result.missed_file = write_missed_file(url, result.missed)
    emit.log(result.summary)
    return result


def _fetch_tracks(url: str, kind: str, emit: Emit) -> list[TrackMeta]:
    if kind == "spotify":
        track_match = re.search(r"track/([A-Za-z0-9]+)", url)
        item_id = (track_match or re.search(r"playlist/([A-Za-z0-9]+)", url)).group(1)
        emit.log(f"Fetching Spotify {'track' if track_match else 'playlist'} metadata...")
        if track_match:
            return [spotify_track_noauth(item_id)]
        return spotify_tracks_noauth(item_id, emit.log)
    emit.log("Fetching Apple Music metadata...")
    return apple_music_tracks(url)


def _run_matched_job(url, kind, settings, client, emit, cancel) -> JobResult:
    """Spotify/Apple path: resolve each metadata track to YouTube, then import."""
    tracks = _fetch_tracks(url, kind, emit)
    result = JobResult(total=len(tracks))
    emit.log(f"Found {result.total} tracks. Searching YouTube...")
    emit.progress(0, result.total)

    search_ydl = make_ydl(extract_flat=True)
    probe_ydl = make_ydl()

    for i, track in enumerate(tracks, 1):
        if cancel.is_set():
            result.cancelled = True
            break
        label = track.label

        def miss(msg, label=label, i=i):
            result.missed.append(f"{label} ({msg})")
            emit.log(f"[{i}/{result.total}] Missed: {label} ({msg})")

        try:
            match_url, score, reason = run_with_retry(
                emit.log, lambda track=track: find_match(
                    track, search_ydl, settings.version_pref, settings.strictness))
            if not match_url:
                miss(reason)
            else:
                kbps = run_with_retry(
                    emit.log, lambda url=match_url: best_audio_kbps(url, probe_ydl))
                if 0 < kbps < MIN_SOURCE_KBPS:
                    miss(f"source {kbps:.0f} kbps < {MIN_SOURCE_KBPS} kbps floor")
                else:
                    emit.log(f"[{i}/{result.total}] Importing (match {score:.2f}): {label}")
                    run_with_retry(
                        emit.log,
                        lambda url=match_url, track=track: _download_and_upload(
                            url, track.title, settings, client, meta=track))
                    result.imported += 1
        except DuplicateTrackError:
            result.duplicates.append(label)
            emit.log(f"[{i}/{result.total}] Already in WebTunes: {label}")
        except AuthRevokedError:
            raise
        except Exception as e:
            miss(str(e))
        emit.progress(i, result.total)
        emit.counts(result.imported, len(result.missed))
    return result


def _run_youtube_job(url, settings, client, emit, cancel) -> JobResult:
    emit.log("Fetching YouTube link...")
    # 'in_playlist' (not True) so a watch?v=...&list=... URL still recurses into
    # the playlist; plain extract_flat=True stops at a flat reference -> 1 entry.
    with make_ydl(extract_flat="in_playlist") as ydl:
        info = run_with_retry(emit.log, lambda: ydl.extract_info(url, download=False))
    entries = [e for e in (info.get("entries") if "entries" in info else [info]) if e]
    result = JobResult(total=len(entries))
    emit.log(f"Found {result.total} videos. Importing...")
    emit.progress(0, result.total)

    probe_ydl = make_ydl()

    for i, entry in enumerate(entries, 1):
        if cancel.is_set():
            result.cancelled = True
            break
        title = entry.get("title") or entry.get("id", "unknown")
        try:
            video_url = entry.get("url") or entry.get("webpage_url")
            kbps = run_with_retry(
                emit.log, lambda url=video_url: best_audio_kbps(url, probe_ydl))
            if 0 < kbps < MIN_SOURCE_KBPS:
                result.missed.append(
                    f"{title} (source {kbps:.0f} kbps < {MIN_SOURCE_KBPS} kbps floor)")
                emit.log(f"[{i}/{result.total}] Missed: {title} (low-bitrate source)")
            else:
                emit.log(f"[{i}/{result.total}] Importing: {title}")
                # metadata + thumbnail come from the video inside _download_and_upload
                run_with_retry(
                    emit.log,
                    lambda url=video_url, title=title: _download_and_upload(
                        url, title, settings, client))
                result.imported += 1
        except DuplicateTrackError:
            result.duplicates.append(title)
            emit.log(f"[{i}/{result.total}] Already in WebTunes: {title}")
        except AuthRevokedError:
            raise
        except Exception as e:
            result.missed.append(f"{title} ({e})")
            emit.log(f"[{i}/{result.total}] Missed: {title} ({e})")
        emit.progress(i, result.total)
        emit.counts(result.imported, len(result.missed))
    return result


def import_single_video(
    item: ImportItem,
    settings: Settings,
    client: WebTunesClient,
    update: Callable[[str, ItemStatus, int], None],
    log: Callable[[str], None],
) -> None:
    """Search-tab path: import one video, reporting per-row status transitions.
    AuthRevokedError propagates (worker handles the disconnect)."""
    try:
        probe_ydl = make_ydl()
        kbps = run_with_retry(log, lambda: best_audio_kbps(item.url, probe_ydl))
        if 0 < kbps < MIN_SOURCE_KBPS:
            raise RuntimeError(f"source {kbps:.0f} kbps < {MIN_SOURCE_KBPS} kbps floor")
        update(item.item_id, ItemStatus.DOWNLOADING, 0)
        run_with_retry(log, lambda: _download_and_upload(
            item.url, item.title, settings, client,
            on_percent=lambda pct: update(item.item_id, ItemStatus.DOWNLOADING, pct),
            on_uploading=lambda: update(item.item_id, ItemStatus.UPLOADING, 100),
        ))
        item.status = ItemStatus.DONE
        update(item.item_id, ItemStatus.DONE, 100)
    except DuplicateTrackError:
        item.status = ItemStatus.DUPLICATE
        update(item.item_id, ItemStatus.DUPLICATE, 100)
    except AuthRevokedError:
        item.status = ItemStatus.FAILED
        item.error = "connection revoked"
        update(item.item_id, ItemStatus.FAILED, 0)
        raise
    except Exception as e:
        item.status = ItemStatus.FAILED
        item.error = str(e)
        log(f"Import failed: {item.title} ({e})")
        update(item.item_id, ItemStatus.FAILED, 0)
