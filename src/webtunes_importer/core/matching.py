"""Resolve a track's metadata to the best-matching YouTube video."""

import difflib
import re

import yt_dlp

from webtunes_importer.constants import DEFAULT_STRICTNESS, DURATION_TOLERANCE, SEARCH_RESULTS
from webtunes_importer.core.models import TrackMeta


def make_ydl(**opts):
    """A yt-dlp instance carrying our shared defaults (quiet output). Per-call
    options override these defaults."""
    return yt_dlp.YoutubeDL({"quiet": True, "noprogress": True, **opts})


BRACKETS = re.compile(r"\(.*?\)|\[.*?\]")
NOISE_WORDS = re.compile(r"\b(official|video|audio|lyrics?|music|hd|4k|remaster(ed)?|topic|vevo)\b")


def normalize(s):
    s = BRACKETS.sub(" ", s.lower())
    s = NOISE_WORDS.sub(" ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


# matched on the raw title - normalize() strips "(Live)"/"(Remix)" brackets
LIVE_PATTERNS = re.compile(r"\b(live|concert|unplugged|tour)\b")
JUNK_PATTERNS = re.compile(
    r"\b(remix|sped[\s-]?up|slowed|nightcore|reverb|8d|cover|karaoke|mashup)\b")


def version_allowed(title, preference):
    """True if a candidate title is acceptable for the requested version.

    studio - reject live takes and weird versions (remix/sped-up/nightcore/...).
    live   - require a live indicator.
    none   - everything allowed.
    Word-boundary matching can mis-flag legitimate titles ("Live and Let Die",
    "Cover Me"); accepted, since every drop is reported.
    """
    t = (title or "").lower()
    if preference == "studio":
        return not (LIVE_PATTERNS.search(t) or JUNK_PATTERNS.search(t))
    if preference == "live":
        return bool(LIVE_PATTERNS.search(t))
    return True


def _ratio(a, b):
    """Order-invariant similarity: compare the sorted word sets so that
    "artist title" and "title ... artist" score the same."""
    a = " ".join(sorted(a.split()))
    b = " ".join(sorted(b.split()))
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_score(track: TrackMeta, entry):
    want = normalize(f"{track.artist} {track.title}")
    title = normalize(entry.get("title") or "")
    # Official "Artist - Topic"/VEVO uploads often carry only the song name in the
    # title and the artist in the channel, so also try title+channel and take the
    # better fit; a junk channel just makes that variant score lower, never higher.
    channel = normalize(entry.get("uploader") or entry.get("channel") or "")
    score = max(_ratio(want, title), _ratio(want, f"{title} {channel}".strip()))
    duration = entry.get("duration")
    if track.duration and duration and abs(duration - track.duration) > DURATION_TOLERANCE:
        score -= 0.2
    return score


def find_match(track: TrackMeta, search_ydl, preference="none", threshold=DEFAULT_STRICTNESS):
    """Return (url, score, reason). Score every candidate and take the highest; on a
    confident match (score >= threshold) reason is None, otherwise url is None and
    reason explains the skip. Below the threshold the track is skipped, never
    downloaded."""
    query = f"{track.artist} {track.title}"
    if preference == "live":
        query += " live"
    info = search_ydl.extract_info(f"ytsearch{SEARCH_RESULTS}:{query}", download=False)
    entries = [e for e in (info.get("entries") or [])
               if version_allowed(e.get("title"), preference)]
    if not entries:
        return None, 0.0, f"no {preference} version in top {SEARCH_RESULTS} results"
    best, best_score = max(((e, match_score(track, e)) for e in entries), key=lambda p: p[1])
    if best_score >= threshold:
        return best["url"], best_score, None
    return None, best_score, f"below strictness {threshold:.2f}, best {best_score:.2f}"


def best_audio_kbps(url, probe_ydl):
    """Best available audio bitrate (kbps) for url, or 0 if undeterminable."""
    info = probe_ydl.extract_info(url, download=False)
    rates = [f.get("abr") or f.get("tbr") or 0
             for f in (info.get("formats") or [])
             if f.get("acodec") not in (None, "none")]
    return max(rates, default=0)
