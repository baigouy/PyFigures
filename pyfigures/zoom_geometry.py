"""Where a corner inset sits on its panel, and the leader lines joining an
ROI box to it, in the panel's image pixels (the coordinates ROIs and lines
are stored in). Shared by add_zoom_callout, connect_roi_to_inset (MCP and the
chat) and the image editor's "Connect ROI ↔ inset" button, so the lines end
exactly on the inset's corners: models guessing the inset position from its
placement drew lines that stopped short of it (user finding 2026-11-04).

An inset is drawn flush in its corner, *fraction* of the panel's shown width
wide, with the aspect ratio of its own (cropped) source; a cropped panel
shows only its crop window, so the inset sits in that window.
"""
from __future__ import annotations


def placement_words(placement) -> set[str]:
    """{'top', 'right'} for 'top right', 'Top-Right', "Position('top-right')"…"""
    import re
    text = str(placement or '').lower()
    words = set(re.findall(r'top|bottom|left|right|center|centre', text))
    if 'centre' in words:
        words.discard('centre')
        words.add('center')
    return words


def inset_rect(parent_size, parent_crops, inset_size, inset_crops, fraction, placement):
    """(x, y, w, h) of the inset in the parent's image pixels.

    *parent_size* / *inset_size*: (width, height) of the source images;
    *_crops*: (left, right, top, bottom); *fraction*: inset width / shown width.
    """
    pw, ph = parent_size
    pl, pr, pt, pb = parent_crops or (0, 0, 0, 0)
    shown_w, shown_h = pw - pl - pr, ph - pt - pb
    iw_src = inset_size[0] - (inset_crops or (0, 0, 0, 0))[0] - (inset_crops or (0, 0, 0, 0))[1]
    ih_src = inset_size[1] - (inset_crops or (0, 0, 0, 0))[2] - (inset_crops or (0, 0, 0, 0))[3]
    w = float(fraction) * shown_w
    h = w * ih_src / iw_src if iw_src > 0 else w
    words = placement_words(placement)
    if 'left' in words:
        x = pl
    elif 'right' in words:
        x = pl + shown_w - w
    else:
        x = pl + (shown_w - w) / 2.0
    if 'top' in words:
        y = pt
    elif 'bottom' in words:
        y = pt + shown_h - h
    else:
        y = pt + (shown_h - h) / 2.0
    return (x, y, w, h)


def leader_lines(box, inset, connectors=2):
    """[((x1, y1), (x2, y2)), ...]: from the box corners facing the inset to
    the inset corners facing the box (the usual funnel; they never cross).
    *box* / *inset*: (x, y, w, h)."""
    bx1, by1, bx2, by2 = box[0], box[1], box[0] + box[2], box[1] + box[3]
    ix1, iy1, ix2, iy2 = inset[0], inset[1], inset[0] + inset[2], inset[1] + inset[3]
    box_c = {"tl": (bx1, by1), "tr": (bx2, by1), "bl": (bx1, by2), "br": (bx2, by2)}
    ins_c = {"tl": (ix1, iy1), "tr": (ix2, iy1), "bl": (ix1, iy2), "br": (ix2, iy2)}
    bcx, bcy = (bx1 + bx2) / 2, (by1 + by2) / 2
    icx, icy = (ix1 + ix2) / 2, (iy1 + iy2) / 2
    if abs(icx - bcx) >= abs(icy - bcy):
        (bp, ip) = (("tr", "br"), ("tl", "bl")) if icx > bcx else (("tl", "bl"), ("tr", "br"))
    else:
        (bp, ip) = (("bl", "br"), ("tl", "tr")) if icy > bcy else (("tl", "tr"), ("bl", "br"))
    return [(box_c[b], ins_c[i]) for b, i in list(zip(bp, ip))[:max(0, int(connectors))]]
