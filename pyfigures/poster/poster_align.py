"""Smart alignment guides for the poster canvas (Figma/PowerPoint-style "semi-automatic"
snapping): while a shape is being dragged, its edges/center are compared against the
edges/center of every other shape and of the page; if one is within `threshold_mm`, a
guide line is shown, and the drag is nudged towards it.

The pull is *eased*, not a hard grab: right at the edge of `threshold_mm` the nudge is
almost nothing (you can glide straight past it), and it only ramps up to a full, exact
snap once the shape is nearly on the line already — see the `pull_fraction` easing
below. This is the fix for repeated feedback that on/off snapping (either always-on, or
only fully engaging past a hard radius) felt "magnetic"/too strong, especially for small
text boxes, while an assist with no pull at all defeated the point of having guides —
this on-by-default gradient split the difference. Still a soft nudge, not a layout
algorithm: the user is always free to drop a shape anywhere (hold Alt to disable it for
one drag), unlike the scientific-figure packing in batoolset.figure.alignment, which
this module never imports or uses.
"""
from qtpy.QtCore import QRectF, QLineF, QPointF


def _candidates_x(rect: QRectF):
    return {
        'left': rect.left(),
        'right': rect.right(),
        'centerX': rect.center().x(),
    }


def _candidates_y(rect: QRectF):
    return {
        'top': rect.top(),
        'bottom': rect.bottom(),
        'centerY': rect.center().y(),
    }


def _eased_pull(dx, dist, threshold_mm):
    """Scale a raw to-the-line correction *dx* down by how far *dist* (its
    magnitude, 0..threshold_mm) is from the line: ~0 pull near the edge of
    the catch radius, ramping up to a full/exact snap only once already
    almost on the line. Quadratic ease so the ramp-up itself feels gradual
    rather than a sudden switch-on partway through the radius."""
    if dist <= 0.0:
        return dx
    fraction = (1.0 - dist / threshold_mm) ** 2
    return dx * fraction


def compute_snaps(moving_rect: QRectF, other_rects, page_rect: QRectF, threshold_mm=1.2):
    """Return (dx, dy, guides) where dx/dy (mm) should be added to the moving rect's
    position to ease it towards alignment, and `guides` is a list of QLineF (mm
    coordinates) to draw wherever a candidate line is within threshold_mm — even if the
    eased pull at that distance is currently tiny, so the guide still shows as an early
    heads-up before the tug becomes noticeable.

    other_rects: iterable of QRectF (other shapes' bounding rects), page_rect is always
    considered too (edges + center of the page).
    """
    references = list(other_rects) + [page_rect]

    best_dx, best_dx_dist = 0.0, threshold_mm
    best_dy, best_dy_dist = 0.0, threshold_mm
    guide_x_at = None
    guide_y_at = None

    mv_x = _candidates_x(moving_rect)
    mv_y = _candidates_y(moving_rect)

    for ref in references:
        ref_x = _candidates_x(ref)
        ref_y = _candidates_y(ref)
        for mv_val in mv_x.values():
            for ref_val in ref_x.values():
                dist = ref_val - mv_val
                if abs(dist) < best_dx_dist:
                    best_dx_dist = abs(dist)
                    best_dx = dist
                    guide_x_at = ref_val
        for mv_val in mv_y.values():
            for ref_val in ref_y.values():
                dist = ref_val - mv_val
                if abs(dist) < best_dy_dist:
                    best_dy_dist = abs(dist)
                    best_dy = dist
                    guide_y_at = ref_val

    guides = []
    eased_dx = _eased_pull(best_dx, best_dx_dist, threshold_mm) if guide_x_at is not None else 0.0
    eased_dy = _eased_pull(best_dy, best_dy_dist, threshold_mm) if guide_y_at is not None else 0.0

    snapped_rect = moving_rect.translated(eased_dx, eased_dy)
    if guide_x_at is not None:
        top = min(snapped_rect.top(), page_rect.top())
        bottom = max(snapped_rect.bottom(), page_rect.bottom())
        guides.append(QLineF(QPointF(guide_x_at, top), QPointF(guide_x_at, bottom)))
    if guide_y_at is not None:
        left = min(snapped_rect.left(), page_rect.left())
        right = max(snapped_rect.right(), page_rect.right())
        guides.append(QLineF(QPointF(left, guide_y_at), QPointF(right, guide_y_at)))

    return eased_dx, eased_dy, guides


ALIGN_MODES = ('left', 'right', 'top', 'bottom', 'center_h', 'center_v')


def align_shapes(shapes, mode):
    """Align *shapes* (each needs .bounding_rect_mm()/.move_by_mm(dx, dy), i.e.
    any PosterImage/PosterText) to each other along *mode* — same idea as
    PowerPoint/Illustrator's align panel, using the selection's own overall
    bounding box as the target rather than any one "anchor" shape:

    - left/right/top/bottom: every shape's matching edge moves onto the
      selection's own extreme edge (e.g. "left" moves everyone's left edge
      onto the leftmost shape's left edge).
    - center_h/center_v: every shape's center moves onto the horizontal/
      vertical center of the selection's overall bounding box (the midpoint
      between the extreme edges, not the average of the individual centers
      — so it doesn't get pulled off-center by however shapes happen to
      cluster).

    No-op for fewer than 2 shapes (nothing to align to).
    """
    if len(shapes) < 2:
        return
    rects = [s.bounding_rect_mm() for s in shapes]
    lefts = [r.left() for r in rects]
    rights = [r.right() for r in rects]
    tops = [r.top() for r in rects]
    bottoms = [r.bottom() for r in rects]

    if mode == 'left':
        target = min(lefts)
        for shape, r in zip(shapes, rects):
            shape.move_by_mm(target - r.left(), 0.0)
    elif mode == 'right':
        target = max(rights)
        for shape, r in zip(shapes, rects):
            shape.move_by_mm(target - r.right(), 0.0)
    elif mode == 'top':
        target = min(tops)
        for shape, r in zip(shapes, rects):
            shape.move_by_mm(0.0, target - r.top())
    elif mode == 'bottom':
        target = max(bottoms)
        for shape, r in zip(shapes, rects):
            shape.move_by_mm(0.0, target - r.bottom())
    elif mode == 'center_h':
        target = (min(lefts) + max(rights)) / 2.0
        for shape, r in zip(shapes, rects):
            shape.move_by_mm(target - r.center().x(), 0.0)
    elif mode == 'center_v':
        target = (min(tops) + max(bottoms)) / 2.0
        for shape, r in zip(shapes, rects):
            shape.move_by_mm(0.0, target - r.center().y())
    else:
        raise ValueError(f'unknown align mode {mode!r}; use one of {ALIGN_MODES}')


DISTRIBUTE_AXES = ('x', 'y')


def distribute_shapes(shapes, axis):
    """Evenly space *shapes* (each needs .center_mm()/.move_by_mm()) along
    *axis* ('x' or 'y') between the two extreme members, which themselves
    stay put — same "distribute horizontally/vertically" as PowerPoint/
    Illustrator, spacing centers rather than edges so it behaves sensibly
    even when shapes are different sizes. No-op for fewer than 3 shapes —
    with only 2, there is nothing in between to redistribute.
    """
    if len(shapes) < 3:
        return
    if axis not in DISTRIBUTE_AXES:
        raise ValueError(f'unknown axis {axis!r}; use one of {DISTRIBUTE_AXES}')

    def _coord(shape):
        center = shape.center_mm()
        return center.x() if axis == 'x' else center.y()

    ordered = sorted(shapes, key=_coord)
    first_c, last_c = _coord(ordered[0]), _coord(ordered[-1])
    step = (last_c - first_c) / (len(ordered) - 1)
    for i, shape in enumerate(ordered):
        delta = (first_c + i * step) - _coord(shape)
        if axis == 'x':
            shape.move_by_mm(delta, 0.0)
        else:
            shape.move_by_mm(0.0, delta)
