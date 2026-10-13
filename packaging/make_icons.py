"""Draws the three app icons — PyFigures (figure editor), PyFigures Album
(photo album designer) and PyFigures Poster (poster designer) — and writes
each as a Windows .ico and a macOS .icns into images/icons/ (used by
pyfigures.spec and packaging/make_macos_launcher_apps.sh) and a 1024 px PNG
into pyfigures/icons/ (the window icons, see pyfigures.icons).

    python packaging/make_icons.py [out_dir]

The icons are committed; rerun this only to change them.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 1024                      # drawn at this size, downscaled for the small icons
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
ICONS = {
    # name: (gradient top, gradient bottom, draw function name)
    'pyfigures': ((66, 133, 244), (26, 74, 170), 'draw_figure'),
    'pyfigures_album': ((247, 151, 60), (200, 78, 30), 'draw_album'),
    'pyfigures_poster': ((38, 190, 170), (12, 118, 108), 'draw_poster'),
}


def _gradient(size, top, bottom):
    w, h = size
    grad = Image.new('RGBA', (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,))
    return grad.resize((w, h))


def _tile(top, bottom):
    """Rounded square background with a soft drop shadow."""
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    m = 70
    shadow = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((m, m + 18, S - m, S - m + 18), radius=210, fill=(0, 0, 0, 90))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    mask = Image.new('L', (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((m, m, S - m, S - m), radius=210, fill=255)
    tile = _gradient((S, S), top, bottom)
    img.paste(tile, (0, 0), mask)
    return img


def _photo(w, h, sky=(120, 190, 250), hill=(70, 170, 90), sun=(255, 214, 80)):
    """A tiny landscape 'photo': sky, sun, two hills."""
    ph = _gradient((w, h), tuple(min(255, c + 50) for c in sky), sky)
    d = ImageDraw.Draw(ph)
    r = h * 0.13
    d.ellipse((w * 0.68 - r, h * 0.28 - r, w * 0.68 + r, h * 0.28 + r), fill=sun + (255,))
    d.polygon([(0, h), (0, h * 0.62), (w * 0.3, h * 0.42), (w * 0.62, h * 0.72), (w * 0.62, h)],
              fill=tuple(max(0, c - 25) for c in hill) + (255,))
    d.polygon([(w * 0.25, h), (w * 0.6, h * 0.55), (w, h * 0.68), (w, h)], fill=hill + (255,))
    return ph


def _shadowed(img, layer, radius=14, offset=(0, 12), alpha=110):
    """Composite *layer* (full-size RGBA) over *img* with a blurred shadow."""
    sh = Image.new('RGBA', layer.size, (0, 0, 0, 0))
    sh.putalpha(layer.getchannel('A').point(lambda a: a * alpha // 255))
    sh = sh.filter(ImageFilter.GaussianBlur(radius))
    img.alpha_composite(sh, offset)
    img.alpha_composite(layer)


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                      # Pillow < 10.1
        return ImageFont.load_default()


def draw_figure(img):
    """A white sheet holding a tightly packed, lettered multi-panel figure."""
    layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = 210, 200, 814, 824
    d.rounded_rectangle((x0, y0, x1, y1), radius=36, fill=(255, 255, 255, 255))
    pad, gap = 44, 22
    ix0, iy0, ix1, iy1 = x0 + pad, y0 + pad, x1 - pad, y1 - pad
    mid_x = ix0 + (ix1 - ix0) * 0.58
    mid_y = iy0 + (iy1 - iy0) * 0.56
    right_mid = iy0 + (mid_y - iy0) / 2
    panels = [
        ((ix0, iy0, mid_x - gap / 2, mid_y - gap / 2), (232, 60, 130), (60, 20, 70)),
        ((mid_x + gap / 2, iy0, ix1, right_mid - gap / 2), (80, 210, 110), (10, 50, 20)),
        ((mid_x + gap / 2, right_mid + gap / 2, ix1, mid_y - gap / 2), (90, 200, 250), (10, 40, 80)),
        ((ix0, mid_y + gap / 2, ix1, iy1), (255, 196, 60), (90, 40, 10)),
    ]
    for (a, b, c, e), bright, dark in panels:
        box = (int(a), int(b), int(c), int(e))
        w, h = box[2] - box[0], box[3] - box[1]
        p = _gradient((w, h), dark, tuple(int(dark[i] * 0.4 + bright[i] * 0.6) for i in range(3)))
        pd = ImageDraw.Draw(p)
        # a few bright "cells" so each panel reads as a micrograph
        for k in range(5):
            cx = w * (0.18 + 0.17 * k)
            cy = h * (0.35 + 0.3 * ((k * 37) % 3) / 2)
            r = min(w, h) * 0.11
            pd.ellipse((cx - r, cy - r, cx + r, cy + r), fill=bright + (255,))
        layer.paste(p, box[:2])
    f = _font(58)
    for (a, b, _c, _e), letter in zip((p[0] for p in panels), 'abcd'):
        d.text((a + 14, b + 6), letter, fill=(255, 255, 255, 255), font=f)
    _shadowed(img, layer)


def draw_album(img):
    """An open photo book: a cover edge, two pages and one photo across the spread."""
    layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx = S // 2
    top, bottom = 300, 740
    d.rounded_rectangle((150, top + 30, S - 150, bottom + 34), radius=34, fill=(110, 40, 20, 255))  # cover
    d.polygon([(178, top), (cx, top + 34), (cx, bottom + 10), (178, bottom - 6)], fill=(255, 255, 255, 255))
    d.polygon([(cx, top + 34), (S - 178, top), (S - 178, bottom - 6), (cx, bottom + 10)], fill=(250, 248, 244, 255))
    ph = _photo(520, 290)
    mask = Image.new('L', ph.size, 0)
    ImageDraw.Draw(mask).rectangle((0, 0, ph.size[0], ph.size[1]), fill=255)
    layer.paste(ph, (cx - 260, top + 100), mask)
    d.line((cx, top + 34, cx, bottom + 10), fill=(0, 0, 0, 70), width=8)       # the fold
    d.line((cx + 4, top + 34, cx + 4, bottom + 10), fill=(255, 255, 255, 120), width=3)
    _shadowed(img, layer)


def _polaroid(w, h, angle, sky, hill):
    border, chin = int(w * 0.07), int(w * 0.2)
    card = Image.new('RGBA', (w + 2 * border, h + border + chin), (255, 255, 255, 255))
    card.paste(_photo(w, h, sky=sky, hill=hill), (border, border))
    return card.rotate(angle, resample=Image.BICUBIC, expand=True)


def draw_poster(img):
    """A portrait poster sheet with a title and freely rotated photos on it."""
    layer = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = 270, 170, 754, 854
    d.rounded_rectangle((x0, y0, x1, y1), radius=26, fill=(255, 255, 255, 255))
    d.rounded_rectangle((x0 + 60, y0 + 60, x1 - 60, y0 + 108), radius=20, fill=(40, 60, 80, 255))    # title
    d.rounded_rectangle((x0 + 110, y0 + 132, x1 - 110, y0 + 156), radius=12, fill=(150, 165, 180, 255))
    _shadowed(img, layer)
    for (px, py, w, h, angle, sky, hill) in (
            (300, 380, 250, 190, 11, (130, 180, 250), (80, 170, 90)),
            (480, 420, 250, 190, -9, (250, 170, 120), (200, 120, 60)),
            (360, 580, 270, 200, 4, (120, 200, 230), (60, 150, 140))):
        p = _polaroid(w, h, angle, sky, hill)
        card = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        card.alpha_composite(p, (px, py))
        _shadowed(img, card, radius=10, offset=(0, 8), alpha=120)


def make(out_dir, png_dir=None):
    """.ico/.icns into *out_dir*, the PNG (the window icon) into *png_dir*
    (default: *out_dir*)."""
    png_dir = png_dir or out_dir
    for d in (out_dir, png_dir):
        os.makedirs(d, exist_ok=True)
    for name, (top, bottom, fn) in ICONS.items():
        img = _tile(top, bottom)
        globals()[fn](img)
        img.save(os.path.join(png_dir, f'{name}.png'))
        img.save(os.path.join(out_dir, f'{name}.ico'), sizes=ICO_SIZES)
        img.save(os.path.join(out_dir, f'{name}.icns'))
        print('made', name)


if __name__ == '__main__':
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if len(sys.argv) > 1:
        make(sys.argv[1])
    else:      # the build's .ico/.icns, and the window icons shipped in the package
        make(os.path.join(root, 'images', 'icons'), os.path.join(root, 'pyfigures', 'icons'))
