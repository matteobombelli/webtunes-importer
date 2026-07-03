"""Locate (or fetch) the external binaries the app depends on.

ffmpeg is required for the MP3/Opus quality modes; it is bundled into the
Windows/macOS builds and a package dependency on Linux. deno runs yt-dlp's JS
challenge solver - optional but strongly recommended for full YouTube format
access - and can be downloaded on demand into the user data dir.
"""

import hashlib
import io
import os
import platform
import shutil
import stat
import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import requests
from platformdirs import user_data_dir

from webtunes_importer.constants import APP_AUTHOR, APP_NAME

DENO_RELEASE_API = "https://api.github.com/repos/denoland/deno/releases/latest"

_DENO_TARGETS = {
    ("Windows", "AMD64"): "x86_64-pc-windows-msvc",
    ("Windows", "ARM64"): "x86_64-pc-windows-msvc",  # runs under emulation
    ("Darwin", "arm64"): "aarch64-apple-darwin",
    ("Darwin", "x86_64"): "x86_64-apple-darwin",
    ("Linux", "x86_64"): "x86_64-unknown-linux-gnu",
    ("Linux", "aarch64"): "aarch64-unknown-linux-gnu",
}


def data_dir() -> Path:
    return Path(user_data_dir(APP_NAME, APP_AUTHOR))


def _bin_dir() -> Path:
    return data_dir() / "bin"


def _bundled_dir() -> Path | None:
    """Directory PyInstaller unpacked our bundled binaries into, if frozen."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "bin"
    return None


def _exe(name: str) -> str:
    return f"{name}.exe" if platform.system() == "Windows" else name


def find_ffmpeg() -> str | None:
    bundled = _bundled_dir()
    if bundled and (bundled / _exe("ffmpeg")).exists():
        return str(bundled / _exe("ffmpeg"))
    return shutil.which("ffmpeg")


def find_deno() -> str | None:
    local = _bin_dir() / _exe("deno")
    if local.exists():
        return str(local)
    return shutil.which("deno")


def inject_deno_path() -> None:
    """Prepend our private bin dir to PATH so yt-dlp's solver finds deno there."""
    bin_dir = _bin_dir()
    if (bin_dir / _exe("deno")).exists():
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


def fetch_deno(on_progress: Callable[[int], None] | None = None) -> Path:
    """Download the latest official deno static binary into the user data dir.

    The release asset's published .sha256sum is verified before install.
    Returns the installed binary path.
    """
    target = _DENO_TARGETS.get((platform.system(), platform.machine()))
    if not target:
        raise RuntimeError(f"no deno build for {platform.system()}/{platform.machine()}")
    asset_name = f"deno-{target}.zip"

    release = requests.get(DENO_RELEASE_API, timeout=30).json()
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    if asset_name not in assets:
        raise RuntimeError(f"deno release asset {asset_name} not found")

    resp = requests.get(assets[asset_name], stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get("Content-Length") or 0)
    buf = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=1 << 16):
        buf.write(chunk)
        if on_progress and total:
            on_progress(int(buf.tell() * 100 / total))

    sum_name = f"{asset_name}.sha256sum"
    if sum_name in assets:
        expected = requests.get(assets[sum_name], timeout=30).text.split()[0].strip()
        actual = hashlib.sha256(buf.getvalue()).hexdigest()
        if actual != expected:
            raise RuntimeError("deno download failed checksum verification")

    bin_dir = _bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(buf) as zf:
        zf.extract(_exe("deno"), bin_dir)
    deno_path = bin_dir / _exe("deno")
    deno_path.chmod(deno_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    inject_deno_path()
    return deno_path


def startup_report() -> list[str]:
    """Human-readable warnings about missing runtime dependencies."""
    warnings = []
    if not find_ffmpeg():
        warnings.append(
            "ffmpeg was not found - MP3 and Opus quality modes will fail. "
            "Install ffmpeg and restart."
        )
    if not find_deno():
        warnings.append(
            "deno was not found - some YouTube downloads may fail without it."
        )
    return warnings
