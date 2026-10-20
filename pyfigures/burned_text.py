"""Text burned into the pixels of a colour image near its top or bottom edge
(an info line such as Fiji's sample-image notice, a microscope's caption).

Found as neutral bright pixels (white / light grey text, R = G = B) packed in
a band at the edge of an image whose content elsewhere has almost none of
them — a fluorescence image, a coloured photograph of tissue. Grey-scale
images and images with white backgrounds are not judged (text cannot be told
apart from data there). The answer is a crop that removes the band; it is a
suggestion only: whether the text is part of the data is the user's call.
"""
from __future__ import annotations

import os

import numpy as np

_BAND = 0.2          # fraction of the height searched at each edge
_GAP = 6             # rows without text allowed between two text lines
_MIN_PIXELS = 40     # text pixels needed to call it text


def _text_mask(rgb):
    a = rgb.astype(np.int16)
    mn = a.min(axis=2)
    mx = a.max(axis=2)
    # anti-aliased light-grey text (Fiji's notice is ~140-220, R = G = B)
    return (mn >= 140) & (mx - mn <= 12)


def _band_rows(counts, rows):
    """First and last row of the text cluster touching the edge side of
    *rows* (ordered from the edge inward), or None."""
    first = last = None
    gap = 0
    for y in rows:
        if counts[y] >= 2:
            if first is None:
                first = y
            last = y
            gap = 0
        elif first is not None:
            gap += 1
            if gap > _GAP:
                break
    return None if first is None else (first, last)


def find_burned_in_text(path: str, crop: dict | None = None) -> dict | None:
    """{'side': 'bottom'|'top', 'rows': [y0, y1], 'crop': {side: n}} for text
    burned in near an edge that *crop* does not already remove, else None."""
    if not isinstance(path, str) or not os.path.isfile(path) \
            or not path.lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
        return None
    try:
        from PIL import Image
        with Image.open(path) as im:
            if im.mode not in ("RGB", "RGBA", "P"):
                return None
            rgb = np.asarray(im.convert("RGB"))
    except Exception:
        return None
    h, w = rgb.shape[:2]
    if h < 64 or w < 64:
        return None
    crop = crop or {}
    if np.ptp(rgb.astype(np.int16), axis=2).max() < 30:
        return None                          # grey-scale saved as RGB
    mask = _text_mask(rgb)
    band = max(8, int(h * _BAND))
    middle = mask[band:h - band]
    if middle.size and middle.mean() > 0.003:
        return None                          # bright neutral content: a white background
    counts = mask.sum(axis=1)
    found = []
    for side, rows in (("bottom", range(h - 1, h - 1 - band, -1)), ("top", range(band))):
        span = _band_rows(counts, rows)
        if span is None:
            continue
        y0, y1 = sorted(span)
        if mask[y0:y1 + 1].sum() < _MIN_PIXELS or y1 - y0 < 4:
            continue
        need = (h - y0 + 2) if side == "bottom" else (y1 + 3)
        need = min(need, band)
        if crop.get(side, 0) >= need:
            continue                         # already cropped away
        found.append({"side": side, "rows": [int(y0), int(y1)], "crop": {side: int(need)}})
    if not found:
        return None
    return max(found, key=lambda f: f["rows"][1] - f["rows"][0])


def burned_text_warning(path: str, crop: dict | None = None) -> str | None:
    """One-line warning for find_burned_in_text, or None."""
    f = find_burned_in_text(path, crop)
    if f is None:
        return None
    side = f["side"]
    n = f["crop"][side]
    total = dict(crop or {})
    total[side] = max(total.get(side, 0), n)
    return (f"{os.path.basename(path)} has text burned into its pixels at the {side} (rows "
            f"{f['rows'][0]}-{f['rows'][1]}, e.g. an information line): crop: "
            f"{{{', '.join(f'{k}: {v}' for k, v in total.items())}}} removes it — unless that "
            f"text is part of the data")
