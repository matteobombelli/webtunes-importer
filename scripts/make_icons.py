"""Regenerate the raster app icons from the canonical shapes in app.svg.

Outputs (committed to the repo so CI needs no image tooling):
  packaging/linux/icons/webtunes-importer.png  (512px, .desktop icon)
  packaging/windows/icon.ico                   (multi-size)
  packaging/macos/icon.png                     (1024px; CI turns it into .icns)

Run: uv run python scripts/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ACCENT = "#4f46e5"
WHITE = "#ffffff"


def draw_icon(size: int, pad_ratio: float = 0.0) -> Image.Image:
    """Mirror app.svg: indigo rounded square + white beamed eighth notes.
    Drawn at 4x and downscaled for clean anti-aliasing."""
    s = size * 4
    pad = int(s * pad_ratio)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def c(v):  # scale a 512-viewBox coordinate into the padded canvas
        return pad + v * (s - 2 * pad) / 512

    d.rounded_rectangle([c(0), c(0), c(512), c(512)], radius=c(112), fill=ACCENT)
    d.ellipse([c(130), c(314), c(222), c(406)], fill=WHITE)
    d.ellipse([c(294), c(282), c(386), c(374)], fill=WHITE)
    d.rectangle([c(202), c(168), c(222), c(364)], fill=WHITE)
    d.rectangle([c(366), c(136), c(386), c(332)], fill=WHITE)
    d.polygon([(c(202), c(168)), (c(386), c(136)), (c(386), c(188)), (c(202), c(220))],
              fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


def main():
    linux_png = ROOT / "packaging/linux/icons/webtunes-importer.png"
    linux_png.parent.mkdir(parents=True, exist_ok=True)
    draw_icon(512).save(linux_png)

    win_ico = ROOT / "packaging/windows/icon.ico"
    win_ico.parent.mkdir(parents=True, exist_ok=True)
    draw_icon(256).save(win_ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                        (128, 128), (256, 256)])

    # macOS icons breathe: Apple's grid leaves ~10% margin around the shape
    mac_png = ROOT / "packaging/macos/icon.png"
    mac_png.parent.mkdir(parents=True, exist_ok=True)
    mac = draw_icon(1024, pad_ratio=0.09)
    mac.save(mac_png)
    mac.save(ROOT / "packaging/macos/icon.icns")

    print("icons written")


if __name__ == "__main__":
    main()
