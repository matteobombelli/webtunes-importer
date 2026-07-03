# WebTunes Importer

Desktop importer for [WebTunes](https://matteob.dev/projects/webtunes): paste a
Spotify, Apple Music, or YouTube link (playlist or song) — or search YouTube
directly — and the tracks land straight in your WebTunes library. No files to
manage: audio is downloaded, uploaded to WebTunes, and cleaned up.

![CI](https://github.com/matteobombelli/webtunes-importer/actions/workflows/ci.yml/badge.svg)

## Install

Grab the latest build from
[Releases](https://github.com/matteobombelli/webtunes-importer/releases):

| Platform | File | Notes |
|---|---|---|
| Windows | `WebTunes-Importer-Setup-x64.exe` | or the portable `.zip` |
| macOS (Apple Silicon) | `WebTunes-Importer-macOS-arm64.dmg` | unsigned — see below |
| macOS (Intel) | `WebTunes-Importer-macOS-x64.dmg` | unsigned — see below |
| Debian / Ubuntu | `webtunes-importer_…_amd64.deb` | `sudo apt install ./webtunes-importer_…_amd64.deb` |
| Fedora / RHEL | `webtunes-importer-….x86_64.rpm` | `sudo dnf install ./webtunes-importer-….x86_64.rpm` |
| Arch / EndeavourOS | `PKGBUILD` | download, then `makepkg -si` in the same folder |

**macOS first launch:** the app isn't notarized yet, so macOS will block the
double-click. Right-click the app → **Open** → **Open**, or run
`xattr -cr "/Applications/WebTunes Importer.app"` once.

**ffmpeg** is bundled on Windows/macOS. On Linux it comes from your package
manager (the .deb depends on it; on Fedora install `ffmpeg-free` or RPM Fusion
ffmpeg). **deno** (used by yt-dlp for full YouTube format access) is optional:
the Setup tab offers a one-click download if it's missing.

## Use

1. **Setup** — in WebTunes open *Settings → YouTube importer*, generate a
   pairing code, and enter it in the app. Pick your quality / version /
   match-strictness preferences (saved automatically).
2. **Links** — paste a Spotify, Apple Music, or YouTube URL and hit Import.
   Progress and a running imported/missed count are shown; missed tracks are
   listed afterwards and written to `last-missed.txt` (path shown in the app,
   overwritten on the next import).
3. **Search** — search the YouTube catalog and import individual tracks with
   per-row progress.

Spotify and Apple Music tracks are metadata-only sources: each track is matched
against YouTube search results (order-invariant title similarity + duration
check) and skipped — never guessed — when no candidate clears your strictness
threshold. Downloads run sequentially on purpose to stay under YouTube's
anonymous rate limits.

## Development

Requires Python ≥ 3.10, [uv](https://docs.astral.sh/uv/), and ffmpeg on PATH.

```sh
uv sync                    # create the venv and install everything
uv run webtunes-importer   # run the app
uv run pytest              # tests
uv run ruff check .        # lint
```

To test pairing against a local WebTunes dev server, expand *WebTunes server*
on the Setup tab and point it at `http://localhost:3000/projects/webtunes`.

### Layout

- `src/webtunes_importer/core/` — Qt-free logic (metadata fetch, YouTube
  matching, download, WebTunes API client, queue, jobs); everything under
  `tests/` targets this layer.
- `src/webtunes_importer/gui/` — PySide6 UI (theme mirrors WebTunes' design
  tokens; one sequential import worker feeds the tabs via signals).
- `packaging/` + `.github/workflows/release.yml` — PyInstaller onedir builds,
  Inno Setup installer, dmg, nfpm .deb/.rpm, Arch PKGBUILD. Tag `v*` to
  release. macOS signing/notarization switches on automatically when the
  `MACOS_CERT_P12` (+ password/notary) repo secrets are set.

Fonts: Space Grotesk & Geist, bundled under the SIL Open Font License
(see `src/webtunes_importer/resources/fonts/`).
