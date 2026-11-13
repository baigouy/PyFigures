"""Mouse editing helpers for the image editor (annotation_editor.py), kept
apart from the widget so they can be tested without a dialog:

- undo snapshots of the annotations (list membership + each shape's geometry),
- line endpoint handles (drag an end; the middle still moves the whole line),
- the crop rectangle of the Rotate + Crop tab, dragged by a side, a corner or
  the inside (the four crop values are measured in the rotated image's
  bounding box, like get_shape_after_rotation_and_crop).
"""
from __future__ import annotations

from qtpy.QtCore import QLineF, QPointF, QRectF
from qtpy.QtGui import QPolygonF, QTransform

HANDLE_PX = 7          # handle half-size / grab distance, in screen pixels
UNDO_DEPTH = 50
_CROPS = ('crop_left', 'crop_right', 'crop_top', 'crop_bottom')


# ── undo ────────────────────────────────────────────────────────────────────
def shape_state(shape):
    """What is needed to put *shape* back where it is now."""
    crops = tuple(getattr(shape, c, 0) for c in _CROPS) if hasattr(shape, 'crop_left') else None
    if isinstance(shape, QLineF):
        return ('line', QLineF(shape), crops)
    if isinstance(shape, QPolygonF):
        return ('poly', QPolygonF(shape), crops)
    if isinstance(shape, QRectF):
        return ('rect', QRectF(shape), crops)
    if callable(getattr(shape, 'rect', None)) and callable(getattr(shape, 'setRect', None)):
        return ('ellipse', QRectF(shape.rect()), crops)        # its size too, not only its position
    try:
        return ('topleft', QPointF(shape.topLeft()), crops)
    except Exception:
        return ('none', None, crops)


def restore_state(shape, state):
    kind, geom, crops = state
    if crops is not None and hasattr(shape, 'crop') and crops != tuple(getattr(shape, c, 0) for c in _CROPS):
        try:
            shape.crop(*crops)
        except Exception:
            for name, value in zip(_CROPS, crops):
                setattr(shape, name, value)
    if kind == 'line':
        shape.setP1(geom.p1())
        shape.setP2(geom.p2())
    elif kind == 'poly':
        shape.clear()
        for p in geom:
            shape.append(QPointF(p))
    elif kind == 'rect':
        shape.setRect(geom.x(), geom.y(), geom.width(), geom.height())
    elif kind == 'ellipse':
        shape.setRect(QRectF(geom))
    elif kind == 'topleft':
        shape.setTopLeft(geom)


def snapshot(shapes):
    return (list(shapes), [(s, shape_state(s)) for s in shapes])


def same_snapshot(a, b):
    if a is None or b is None or len(a[0]) != len(b[0]):
        return False
    if any(x is not y for x, y in zip(a[0], b[0])):
        return False
    return all(_state_eq(sa, sb) for (_s, sa), (_t, sb) in zip(a[1], b[1]))


def _state_eq(a, b):
    if a[0] != b[0] or a[2] != b[2]:
        return False
    if a[0] == 'poly':
        return list(a[1]) == list(b[1])
    return a[1] == b[1]


def apply_snapshot(shapes, snap):
    """Put *shapes* (a list, changed in place) back to *snap*."""
    members, states = snap
    shapes[:] = members
    for shape, state in states:
        restore_state(shape, state)


# ── line endpoints ──────────────────────────────────────────────────────────
def line_handle_at(line, point, scale):
    """1 or 2 when *point* (image coordinates) grabs an end of *line*, else
    None. The grab distance is HANDLE_PX screen pixels at zoom *scale*."""
    if not isinstance(line, QLineF):
        return None
    tol = HANDLE_PX / max(scale, 1e-6)
    d1 = QLineF(line.p1(), point).length()
    d2 = QLineF(line.p2(), point).length()
    if min(d1, d2) > tol:
        return None
    return 1 if d1 <= d2 else 2


def handle_rects(line, scale):
    """The squares drawn on the two ends of a selected line (image coords)."""
    h = HANDLE_PX / max(scale, 1e-6)
    return [QRectF(p.x() - h, p.y() - h, 2 * h, 2 * h) for p in (line.p1(), line.p2())]


# ── rectangle / ellipse resize handles ──────────────────────────────────────
# A selected line had end handles; rectangles, squares, ellipses and circles had
# none, so their size could not be changed after drawing (user, 2026-11-13).
BOX_HANDLES = ('top left', 'top', 'top right', 'right', 'bottom right', 'bottom', 'bottom left', 'left')


def box_rect(shape):
    """The box of a rectangle-like (QRectF) or ellipse-like (rect()) shape."""
    if isinstance(shape, QRectF):
        return QRectF(shape)
    return QRectF(shape.rect())


def set_box_rect(shape, rect):
    if isinstance(shape, QRectF):
        shape.setRect(rect.x(), rect.y(), rect.width(), rect.height())
    else:
        shape.setRect(QRectF(rect))


def box_handle_points(rect):
    """{handle name: point} for the 8 handles of *rect*."""
    c = rect.center()
    return {'top left': rect.topLeft(), 'top': QPointF(c.x(), rect.top()), 'top right': rect.topRight(),
            'right': QPointF(rect.right(), c.y()), 'bottom right': rect.bottomRight(),
            'bottom': QPointF(c.x(), rect.bottom()), 'bottom left': rect.bottomLeft(),
            'left': QPointF(rect.left(), c.y())}


def box_handle_rects(shape, scale):
    h = HANDLE_PX * 0.8 / max(scale, 1e-6)
    return [QRectF(p.x() - h, p.y() - h, 2 * h, 2 * h) for p in box_handle_points(box_rect(shape)).values()]


def box_handle_at(shape, point, scale):
    """The handle of *shape* under *point* (image coordinates), or None."""
    tol = HANDLE_PX / max(scale, 1e-6)
    best, dist = None, tol
    for name, p in box_handle_points(box_rect(shape)).items():
        d = QLineF(p, point).length()
        if d <= dist:
            best, dist = name, d
    return best


def resized_box(rect, handle, point, keep_square=False, minimum=2.0):
    """*rect* with *handle* dragged to *point*; the opposite side stays put. With
    *keep_square* (circles, squares) width and height stay equal."""
    left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
    if 'left' in handle:
        left = min(point.x(), right - minimum)
    if 'right' in handle:
        right = max(point.x(), left + minimum)
    if handle.startswith('top'):
        top = min(point.y(), bottom - minimum)
    if handle.startswith('bottom'):
        bottom = max(point.y(), top + minimum)
    out = QRectF(left, top, right - left, bottom - top)
    if keep_square:
        horizontal = handle in ('left', 'right')
        vertical = handle in ('top', 'bottom')
        side = out.width() if horizontal else out.height() if vertical else max(out.width(), out.height())
        x = out.left() if 'right' in handle or vertical else out.right() - side
        y = out.top() if handle.startswith('bottom') or horizontal else out.bottom() - side
        if horizontal:
            y = rect.center().y() - side / 2          # an edge handle grows around the middle
        if vertical:
            x = rect.center().x() - side / 2
        out = QRectF(x, y, side, side)
    return out


# ── crop rectangle ──────────────────────────────────────────────────────────
def _transforms(width, height, angle):
    center = QRectF(0, 0, width, height).center()
    fwd = QTransform()
    bwd = QTransform()
    if angle:
        fwd.translate(center.x(), center.y())
        fwd.rotate(angle)
        fwd.translate(-center.x(), -center.y())
        bwd.translate(center.x(), center.y())
        bwd.rotate(-angle)
        bwd.translate(-center.x(), -center.y())
    return fwd, bwd


def rotated_bounds(width, height, angle):
    """The image's bounding box once rotated (where crops are measured)."""
    fwd, _bwd = _transforms(width, height, angle)
    return QRectF(fwd.mapToPolygon(QRectF(0, 0, width, height).toRect()).boundingRect())


def crop_hit(point, width, height, angle, crops, scale):
    """Which part of the crop rectangle *point* (image coords) grabs: a tuple
    of sides ('left', 'top', ...: one side, or two at a corner), ('move',)
    inside it, or None outside. *crops* = (left, right, top, bottom)."""
    fwd, _bwd = _transforms(width, height, angle)
    q = fwd.map(QPointF(point))
    rb = rotated_bounds(width, height, angle)
    left, right, top, bottom = crops
    cr = QRectF(rb.left() + left, rb.top() + top,
                rb.width() - left - right, rb.height() - top - bottom)
    tol = HANDLE_PX / max(scale, 1e-6)
    if not cr.adjusted(-tol, -tol, tol, tol).contains(q):
        return None
    sides = []
    if abs(q.x() - cr.left()) <= tol:
        sides.append('left')
    elif abs(q.x() - cr.right()) <= tol:
        sides.append('right')
    if abs(q.y() - cr.top()) <= tol:
        sides.append('top')
    elif abs(q.y() - cr.bottom()) <= tol:
        sides.append('bottom')
    if sides:
        return tuple(sides)
    return ('move',) if cr.contains(q) else None


def drag_crops(grab, start_crops, start_point, point, width, height, angle):
    """New (left, right, top, bottom) after dragging *grab* (from crop_hit)
    from *start_point* to *point* (image coords). Sides stop before they
    cross; a moved rectangle keeps its size and stays inside the image."""
    fwd, _bwd = _transforms(width, height, angle)
    d = fwd.map(QPointF(point)) - fwd.map(QPointF(start_point))
    dx, dy = d.x(), d.y()
    rb = rotated_bounds(width, height, angle)
    W, H = int(rb.width()), int(rb.height())
    left, right, top, bottom = start_crops
    if grab == ('move',):
        dx = min(max(dx, -left), right)
        dy = min(max(dy, -top), bottom)
        return (int(round(left + dx)), int(round(right - dx)),
                int(round(top + dy)), int(round(bottom - dy)))
    if 'left' in grab:
        left = min(max(0, left + dx), W - right - 1)
    if 'right' in grab:
        right = min(max(0, right - dx), W - left - 1)
    if 'top' in grab:
        top = min(max(0, top + dy), H - bottom - 1)
    if 'bottom' in grab:
        bottom = min(max(0, bottom - dy), H - top - 1)
    return (int(round(left)), int(round(right)), int(round(top)), int(round(bottom)))


def crop_handle_points(width, height, angle, crops):
    """Corners and side middles of the crop rectangle, in image coordinates
    (squares are drawn there in the Rotate + Crop tab: grab them)."""
    _fwd, bwd = _transforms(width, height, angle)
    rb = rotated_bounds(width, height, angle)
    left, right, top, bottom = crops
    x1, y1 = rb.left() + left, rb.top() + top
    x2, y2 = rb.left() + rb.width() - right, rb.top() + rb.height() - bottom
    xm, ym = (x1 + x2) / 2, (y1 + y2) / 2
    pts = [(x1, y1), (xm, y1), (x2, y1), (x2, ym), (x2, y2), (xm, y2), (x1, y2), (x1, ym)]
    return [bwd.map(QPointF(x, y)) for x, y in pts]
