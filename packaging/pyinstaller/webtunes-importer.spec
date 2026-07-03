# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec shared by every platform (onedir everywhere: fast startup,
no onefile AV heuristics, and a real .app bundle signing can target later).

CI sets FFMPEG_BINARY to a static ffmpeg to bundle (Windows/macOS); Linux
packages depend on the distro's ffmpeg instead.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent
SRC = ROOT / "src"

sys.path.insert(0, str(SRC))
from webtunes_importer import __version__  # noqa: E402

binaries = []
ffmpeg = os.environ.get("FFMPEG_BINARY")
if ffmpeg:
    binaries.append((ffmpeg, "bin"))

datas = [(str(SRC / "webtunes_importer" / "resources"), "webtunes_importer/resources")]

a = Analysis(
    [str(SRC / "webtunes_importer" / "__main__.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=collect_submodules("yt_dlp"),
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="webtunes-importer",
    console=False,
    icon=str(ROOT / "packaging" / "windows" / "icon.ico") if sys.platform == "win32" else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="webtunes-importer",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="WebTunes Importer.app",
        icon=str(ROOT / "packaging" / "macos" / "icon.icns"),
        bundle_identifier="dev.matteob.webtunes-importer",
        version=__version__,
        info_plist={
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.music",
            "NSHumanReadableCopyright": "© Matteo Bombelli",
        },
    )
