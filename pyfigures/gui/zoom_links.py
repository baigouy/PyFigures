"""Zoom callouts in the image editor: a box (Rectangle2D), a magnified inset
(an Image2D cropping the parent to the box) and leader lines (Line2D) joining
them are separate annotations. Moving the inset left the leaders behind;
moving the box left the leaders and the inset's crop behind. These find what
belongs to a moved piece (from the geometry just before the move) and move it
along.
"""
from __future__ import annotations

from qtpy.QtCore import QPointF, QRectF

_TOL = 1.5


def _shown_rect(img):
    """The rectangle an inset covers on its parent (its stored rect is the
    crop size; it is drawn scaled)."""
    r = img.getRect()
    s = getattr(img, 'scale', 1) or 1
    big = QRectF(r.x(), r.y(), r.width() / s, r.height() / s)
    try:
        if img.contains(QPointF(big.right() - 0.5, big.bottom() - 0.5)):
            return big
    except Exception:
        pass
    return QRectF(r)


def _near_rect(p, rect, tol=_TOL):
    """*p* lies on (or within *tol* of) the border of *rect*."""
    outer = rect.adjusted(-tol, -tol, tol, tol)
    inner = rect.adjusted(tol, tol, -tol, -tol)
    return outer.contains(p) and not (inner.isValid() and inner.contains(p))


def _is_zoom_inset(shape):
    from batoolset.drawings.shapes.image2d import Image2D
    return isinstance(shape, Image2D) and not shape.isText and (
        getattr(shape, 'crop_left', 0) or getattr(shape, 'crop_top', 0)
        or getattr(shape, 'crop_right', 0) or getattr(shape, 'crop_bottom', 0))


def _box_of(shapes, inset):
    """The Rectangle2D whose corner is the inset's crop origin."""
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.image2d import Image2D
    for s in shapes:
        if type(s) is Rectangle2D and not isinstance(s, Image2D):
            if abs(s.x() - inset.crop_left) <= 1 and abs(s.y() - inset.crop_top) <= 1:
                return s
    return None


def _leaders(shapes, box, inset_rect, moving):
    from batoolset.drawings.shapes.line2d import Line2D
    out = []
    box_rect = QRectF(box.x(), box.y(), box.width(), box.height())
    for s in shapes:
        if not isinstance(s, Line2D) or any(s is m for m in moving):
            continue
        p1, p2 = s.p1(), s.p2()
        if _near_rect(p1, box_rect) and _near_rect(p2, inset_rect):
            out.append((s, 'box', 'inset'))
        elif _near_rect(p2, box_rect) and _near_rect(p1, inset_rect):
            out.append((s, 'inset', 'box'))
    return out


def zoom_links(shapes, moved, moving=()):
    """What must follow *moved*: a list of (line, end) — the end (1 or 2) of a
    leader line to move — plus ('crop', inset) when the box moves. Empty
    when *moved* is not part of a zoom callout."""
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.image2d import Image2D
    links = []
    if _is_zoom_inset(moved):
        box = _box_of(shapes, moved)
        if box is None:
            return []
        for line, end1, end2 in _leaders(shapes, box, _shown_rect(moved), moving):
            links.append((line, 1 if end1 == 'inset' else 2))
    elif type(moved) is Rectangle2D and not isinstance(moved, Image2D):
        for inset in shapes:
            if _is_zoom_inset(inset) and _box_of([moved], inset) is moved:
                for line, end1, end2 in _leaders(shapes, moved, _shown_rect(inset), moving):
                    links.append((line, 1 if end1 == 'box' else 2))
                if not any(inset is m for m in moving):
                    links.append(('crop', (inset, moved)))
    return links


def _crop_to_box(inset, box):
    """Set the inset's crop margins so it shows exactly what *box* covers (as
    roi_to_inset makes it). False when the image size is unknown."""
    try:
        w, h = inset.get_raw_size()
    except Exception:
        return False
    if not w or not h:
        return False
    x0 = min(max(0, int(round(box.x()))), int(w) - 1)
    y0 = min(max(0, int(round(box.y()))), int(h) - 1)
    x1 = min(max(x0 + 1, int(round(box.x() + box.width()))), int(w))
    y1 = min(max(y0 + 1, int(round(box.y() + box.height()))), int(h))
    inset.crop(x0, int(w) - x1, y0, int(h) - y1)
    return True


def follow_zoom_links(links, delta):
    """Move the linked leader ends by *delta*; with a moved box, the inset
    shows what the box now covers. (Its crop used to be shifted by *delta*: a
    crop already wrong — margins entered as coordinates, the inset 0 px wide —
    stayed wrong, 2026-11-06.)"""
    for target, what in links:
        if target == 'crop':
            inset, box = what
            if _crop_to_box(inset, box):
                continue
            dx, dy = int(round(delta.x())), int(round(delta.y()))
            w = inset.crop_left + inset.crop_right
            h = inset.crop_top + inset.crop_bottom
            left = min(max(0, inset.crop_left + dx), w)
            top = min(max(0, inset.crop_top + dy), h)
            inset.crop(left, w - left, top, h - top)
            continue
        line = target
        if what == 1:
            line.setP1(line.p1() + delta)
        else:
            line.setP2(line.p2() + delta)
