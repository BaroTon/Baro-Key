#!/usr/bin/env python3
"""Build BaroKey app icons from desktop/barokey-source.png.

The source artwork has a thin white rim baked into its edge and fills the
whole canvas. This crops the rim away, redraws a clean anti-aliased rounded
square, and writes:

* desktop/barokey.png        512 px, no padding (used inside the app)
* desktop/barokey-notext.png 512 px without the wordmark (small logos in the app)
* desktop/icons/barokey-N.png  padded with a soft shadow (launcher/dock icons);
  sizes up to NO_TEXT_MAX use the wordmark-free artwork because the text is
  unreadable that small
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

# Geometry of the source artwork once cropped and resized to 512 px.
TEXT_BAND = (352, 472)    # rows covering the "BaroKey" wordmark (text: 375-456)
MARK_CENTER = (263, 204)  # centre of the blue B + key mark (bbox 140,65-387,343)
MARK_ZOOM = 1.22          # enlarge the mark once the wordmark is gone
NO_TEXT_MAX = 64          # icons up to this size are drawn without the wordmark


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


def text_free(art: Image.Image) -> Image.Image:
    """Remove the wordmark and enlarge the mark, re-centred in the square."""
    art = art.convert("RGBA")
    size = art.width  # 512
    top, bottom = TEXT_BAND
    px = art.load()
    for x in range(size):
        a, b = px[x, top - 2], px[x, bottom]
        for y in range(top - 1, bottom):
            t = (y - (top - 2)) / (bottom - (top - 2))
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)
    zoomed = int(size * MARK_ZOOM)
    big = art.resize((zoomed, zoomed), Image.LANCZOS)
    left = min(max(int(MARK_CENTER[0] * MARK_ZOOM) - size // 2, 0), zoomed - size)
    upper = min(max(int(MARK_CENTER[1] * MARK_ZOOM) - size // 2, 0), zoomed - size)
    out = big.crop((left, upper, left + size, upper + size))
    out.putalpha(rounded_mask(size))
    return out


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
    notext = text_free(clean_square(source, 512))
    notext.save(os.path.join(DESKTOP, "barokey-notext.png"))
    os.makedirs(os.path.join(DESKTOP, "icons"), exist_ok=True)
    for size in SIZES:
        art = notext if size <= NO_TEXT_MAX else master
        padded(art, size).save(os.path.join(DESKTOP, "icons", f"barokey-{size}.png"))
    print("icons written")


if __name__ == "__main__":
    main()
