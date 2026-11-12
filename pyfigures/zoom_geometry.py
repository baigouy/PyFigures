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


# -- measured on a real paint (rotated / cropped panels) --------------------
def measured_inset_corners(panel, inset):
    """The inset's four drawn corners (tl, tr, br, bl as seen in the figure) in
    the panel's image pixels, measured on a real paint of *panel*: valid for
    rotated and cropped panels, whose transforms differ for placed objects
    (the inset, drawn upright) and free ones (ROIs, lines, rotated with the
    image). None if it cannot be measured."""
    from qtpy.QtCore import QPointF, QRectF
    from qtpy.QtGui import QImage, QPainter, QTransform
    from batoolset.drawings.shapes.line2d import Line2D

    seen = {}

    class _Probe(Line2D):
        # a free annotation: records the painter transform ROIs and lines get
        def draw(self, painter, draw=True, parent=None):
            seen['free'] = QTransform(painter.worldTransform())

    original = inset.draw

    def inset_draw(*args, **kwargs):
        painter = kwargs.get('painter', args[0] if args else None)
        seen['inset'] = (QTransform(painter.worldTransform()), QRectF(inset.getRect(all=True)))
        return original(*args, **kwargs)

    annotations = panel.annotations
    probe = _Probe(0, 0, 1, 1)
    panel.annotations = list(annotations) + [probe]
    inset.draw = inset_draw
    try:
        image = QImage(8, 8, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        try:
            panel.draw(painter)
        finally:
            painter.end()
    except Exception:
        return None
    finally:
        panel.annotations = annotations
        try:
            del inset.draw
        except AttributeError:
            pass
    if 'free' not in seen or 'inset' not in seen:
        return None
    s = panel.scale or 1.0
    tl = panel.topLeft()
    # a line point p is drawn at p / scale + topLeft, then through the painter
    to_device = QTransform(1.0 / s, 0, 0, 1.0 / s, tl.x(), tl.y()) * seen['free']
    back, ok = to_device.inverted()
    if not ok:
        return None
    inset_transform, r = seen['inset']
    corners = [r.topLeft(), r.topRight(), r.bottomRight(), r.bottomLeft()]
    return [back.map(inset_transform.map(QPointF(c))) for c in corners]


def scene_to_image_point(panel, scene_point):
    """The panel's image pixel (raw source pixels, where ROIs and arrows are
    stored) under a point of the figure, measured on a real paint: valid for a
    rotated and/or cropped panel ("add an arrowhead where I clicked" on a rotated
    panel could not be placed, 2026-11-12). None if it cannot be measured or the
    point falls outside the image."""
    from qtpy.QtCore import QPointF
    from qtpy.QtGui import QImage, QPainter, QTransform
    from batoolset.drawings.shapes.line2d import Line2D
    seen = {}

    class _Probe(Line2D):
        def draw(self, painter, draw=True, parent=None):
            seen['free'] = QTransform(painter.worldTransform())

    annotations = panel.annotations
    panel.annotations = list(annotations or []) + [_Probe(0, 0, 1, 1)]
    try:
        image = QImage(8, 8, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        try:
            panel.draw(painter)
        finally:
            painter.end()
    except Exception:
        return None
    finally:
        panel.annotations = annotations
    if 'free' not in seen:
        return None
    s = panel.scale or 1.0
    tl = panel.topLeft()
    to_device = QTransform(1.0 / s, 0, 0, 1.0 / s, tl.x(), tl.y()) * seen['free']
    back, ok = to_device.inverted()
    if not ok:
        return None
    p = back.map(QPointF(scene_point[0], scene_point[1]))
    width, height = panel.get_raw_size()
    if not (0 <= p.x() <= width and 0 <= p.y() <= height):
        return None
    return p.x(), p.y()


def _hull(points):
    """Convex hull (counter-clockwise), collinear points kept out."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-9:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-9:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def leader_lines_to_corners(box, corners, connectors=2):
    """Leader lines from the ROI *box* (x, y, w, h) to an inset given by its
    four *corners* (image pixels, any rotation): the two outer tangents of
    the pair (the hull edges joining a box corner to an inset corner), so
    they never cross either shape. An upright inset uses leader_lines."""
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    upright = all(min(abs(x - min(xs)), abs(x - max(xs))) < 0.5 for x in xs) and         all(min(abs(y - min(ys)), abs(y - max(ys))) < 0.5 for y in ys)
    if upright:
        return leader_lines(box, (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), connectors)
    bx1, by1, bx2, by2 = box[0], box[1], box[0] + box[2], box[1] + box[3]
    box_pts = [(bx1, by1), (bx2, by1), (bx2, by2), (bx1, by2)]
    ins_pts = [(round(x, 6), round(y, 6)) for x, y in corners]
    hull = _hull(box_pts + ins_pts)
    in_box = set(box_pts)
    edges = []
    for a, b in zip(hull, hull[1:] + hull[:1]):
        if (a in in_box) != (b in in_box):
            edges.append((a, b) if a in in_box else (b, a))
    if len(edges) != 2:            # overlapping shapes: nearest corners instead
        import math
        pairs = sorted(((math.dist(p, q), p, q) for p in box_pts for q in ins_pts))
        edges = [(p, q) for _d, p, q in pairs[:2]]
    edges.sort(key=lambda e: (e[0][0] - e[1][0]) ** 2 + (e[0][1] - e[1][1]) ** 2)
    return edges[:max(0, int(connectors))]
