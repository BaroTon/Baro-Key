#!/usr/bin/env python3
"""Build BaroKey app icons from desktop/barokey-source.png.

The source artwork has a thin white rim baked into its edge and fills the
whole canvas. This crops the rim away, redraws a clean anti-aliased rounded
square, and writes:

* desktop/barokey.png        512 px, no padding (used inside the app)
* desktop/icons/barokey-N.png  padded with a soft shadow (launcher/dock icons)
"""

import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DESKTOP = os.path.join(ROOT, "desktop")
SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

CROP = (8, 8, 503, 503)  # inside the rim, square
RADIUS = 0.215           # corner radius as a fraction of the side
SCALE = 0.86             # artwork size inside the padded icon canvas
MASTER = 1024


def rounded_mask(size: int) -> Image.Image:
    ss = 4
    mask = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size * ss - 1, size * ss - 1), radius=int(size * ss * RADIUS), fill=255
    )
    return mask.resize((size, size), Image.LANCZOS)


def clean_square(source: Image.Image, size: int) -> Image.Image:
    art = source.crop(CROP).resize((size, size), Image.LANCZOS).convert("RGBA")
    art.putalpha(rounded_mask(size))
    return art


def padded(art_master: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    side = int(MASTER * SCALE)
    art = art_master.resize((side, side), Image.LANCZOS)
    offset = (MASTER - side) // 2
    shadow = Image.new("RGBA", (MASTER, MASTER), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 90), (offset, offset + int(MASTER * 0.012)), art.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(MASTER * 0.014))
    canvas = Image.alpha_composite(canvas, shadow)
    canvas.alpha_composite(art, (offset, offset))
    return canvas.resize((size, size), Image.LANCZOS)


def main() -> None:
    source = Image.open(os.path.join(DESKTOP, "barokey-source.png")).convert("RGBA")
    clean_square(source, 512).save(os.path.join(DESKTOP, "barokey.png"))
    master = clean_square(source, MASTER)
    os.makedirs(os.path.join(DESKTOP, "icons"), exist_ok=True)
    for size in SIZES:
        padded(master, size).save(os.path.join(DESKTOP, "icons", f"barokey-{size}.png"))
    print("icons written")


if __name__ == "__main__":
    main()
