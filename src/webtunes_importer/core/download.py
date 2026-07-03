"""Download a YouTube video's audio into a caller-owned directory.

Unlike the exporter this was ported from, nothing is tagged locally: the file
is uploaded to WebTunes immediately afterwards and metadata/cover art travel
as upload form fields, applied server-side.
"""

import re
from collections.abc import Callable
from pathlib import Path

import yt_dlp


def sanitize(name):
    return re.sub(r'[\\/:*?"<>|%]', "_", name).strip() or "track"


def _progress_hook(on_progress: Callable[[int], None]):
    def hook(d):
        if d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if total:
            on_progress(int(d.get("downloaded_bytes", 0) * 100 / total))

    return hook


def download_audio(url, out_path_no_ext, quality="192", *, ffmpeg_path=None, on_progress=None):
    """Download audio to out_path_no_ext.<ext>.

    Returns (path, meta, thumb_url) where meta is {title, artist, album} pulled
    from the video itself (the caller decides whether to prefer its own richer
    metadata) and thumb_url is the video thumbnail.

    quality is one of:
      "128"/"192" - transcode to MP3 at that kbps (lossy)
      "opus"      - keep YouTube's native Opus stream, repackaged to .opus (lossless)
      "m4a"       - keep YouTube's native AAC stream, copied to .m4a (lossless)
    """
    opts = {
        "outtmpl": f"{out_path_no_ext}.%(ext)s",
        "quiet": True,
        "noprogress": True,
        # let yt-dlp fetch its JS challenge solver (runs on deno), needed for
        # full YouTube format access
        "remote_components": ["ejs:github"],
    }
    if ffmpeg_path:
        opts["ffmpeg_location"] = ffmpeg_path
    if on_progress:
        opts["progress_hooks"] = [_progress_hook(on_progress)]

    if quality == "opus":
        opts["format"] = "bestaudio[acodec=opus]/bestaudio"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "opus"}]
        out = f"{out_path_no_ext}.opus"
    elif quality == "m4a":
        # AAC-only so the copy below is truly lossless (no Opus->AAC re-encode)
        opts["format"] = "bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]"
        out = None  # set from prepare_filename after extraction
    else:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": quality}]
        out = f"{out_path_no_ext}.mp3"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if out is None:
                out = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        if quality == "m4a":
            raise RuntimeError(
                "no lossless .m4a (AAC) stream available - try 'Best (Opus, lossless)' instead"
            ) from e
        raise

    if not Path(out).exists():
        raise RuntimeError(f"download produced no file at {out}")

    meta = {
        "title": info.get("track") or info.get("title") or "",
        "artist": info.get("artist") or info.get("uploader") or "",
        "album": info.get("album") or "",
    }
    return out, meta, info.get("thumbnail")
