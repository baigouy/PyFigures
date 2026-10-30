"""Fitting label rows (top-level text rows) to the row they label.

One implementation for the canvas repack and for arrange_text_rows (run on
open and undo): they used to differ (per panel vs per range, stacked label
rows fitted by neither), so undo/redo and reopening gave other label widths.
"""
from batoolset.drawings.shapes.group import areIndicesOverlapping


def _is_label(shape):
    return bool(getattr(shape, 'isText', False))


def labelled_row(shapes, i):
    """The image row (or single panel) that label row shapes[i] labels.

    isText 'below' means the labelled content comes after it, anything else
    before it; label rows stacked on top of each other label the same row,
    so they are looked past. The other side is used when the direction finds
    nothing (the user moved rows)."""
    step = 1 if getattr(shapes[i], 'isText', None) == 'below' else -1
    for direction in (step, -step):
        j = i + direction
        while 0 <= j < len(shapes) and _is_label(shapes[j]):
            j += direction
        if 0 <= j < len(shapes):
            return shapes[j]
    return None


def _ranges(labels):
    """Each label's [first, last] panel; sequential when unset or overlapping."""
    ranges = [getattr(lbl.annotations[0], 'range', None) if getattr(lbl, 'annotations', None) else None
              for lbl in labels]
    if any(r is None for r in ranges) or areIndicesOverlapping(ranges):
        ranges = [[k, k] for k in range(len(labels))]
        for lbl, rng in zip(labels, ranges):
            if getattr(lbl, 'annotations', None):
                lbl.annotations[0].range = rng
    return ranges


def _span(panels, first, last):
    n = len(panels)
    # a label left over after its panel left the row sits on the last panel
    first = max(0, min(first, n - 1))
    last = max(0, min(last, n - 1))
    if first > last:
        first, last = last, first
    rects = [panels[k].getRect(all=True) for k in range(first, last + 1)]
    left = min(r.x() for r in rects)
    right = max(r.x() + r.width() for r in rects)
    return left, right - left


def fit_label_row(row, target):
    """Give each label of *row* the width and x of the panels it labels."""
    labels = list(row.content) if hasattr(row, 'content') else [row]
    if not labels or target is None:
        return
    if hasattr(target, 'content'):
        panels = [e for e in target.content if not _is_label(e)]  # side labels are not panels
    else:
        panels = [target]
    if not panels:
        return
    for lbl, (first, last) in zip(labels, _ranges(labels)):
        x, width = _span(panels, first, last)
        lbl.setWidth(width)
        lbl.set_to_scale(1)
        lbl.setTopLeft(x, lbl.y())
    if hasattr(row, 'content'):
        row.update_bounds()


def fit_label_rows(shapes):
    for i, shape in enumerate(shapes):
        if _is_label(shape):
            fit_label_row(shape, labelled_row(shapes, i))
