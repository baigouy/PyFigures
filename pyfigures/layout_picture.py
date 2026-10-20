"""Picture layouts: draw the figure with panel names, one line per row.

    a a b
    a a c
    d e f

* every line is a row of cells, names separated by spaces; all lines have
  the same number of cells, so the result is an aligned grid;
* repeating a name makes that panel span several cells; the cells of one
  name must form a rectangle (an L shape is an error with its line/column);
* the picture is turned into nested rows and columns by guillotine cuts: a
  line (horizontal first, else vertical) that crosses no panel cuts the
  picture into bands, and each band is cut again. The example gives
  ``(a,(b/c))/(d,e,f)``. A picture that no line can cut (a pinwheel:
  ``a a b / d e b / d c c``) cannot be made of rows and columns: refused,
  with that explanation;
* each panel's cells give its shape: a panel spanning 2 x 2 cells is cropped
  (centred) to twice the cell's width and height ratio, so the packed rows
  and columns line up. The cell ratio is the most common ratio of the
  single-cell panels (or of all panels).

Same tree format as pyfigures/layout_formula.py, with the span of every
panel in cells (``cells: (columns, rows)``) so the recipe build can crop.
"""
from __future__ import annotations

import re

from pyfigures.layout_formula import FormulaError

_NAME = re.compile(r"^[^\s(),|/\[\]]+$")


def is_picture(text) -> bool:
    """A picture layout: none of the formula's symbols, and several non-empty
    lines or one line of several names (``a b c`` is one row — models wrote
    it and a formula cannot mean anything else by it). Anything else is a
    one-line formula (pyfigures/layout_formula)."""
    if re.search(r"[(),|/\[\]]", str(text)):
        return False
    lines = [ln for ln in str(text).splitlines() if ln.strip()]
    return len(lines) >= 2 or len(lines) == 1 and len(lines[0].split()) >= 2


def _cells(text):
    rows = [ln.split() for ln in str(text).splitlines() if ln.strip()]
    if not rows:
        raise FormulaError("the layout picture is empty")
    n = len(rows[0])
    for i, r in enumerate(rows):
        if len(r) != n:
            raise FormulaError(f"layout picture: line {i + 1} has {len(r)} cells, line 1 has {n}; "
                               "every line needs the same number of cells (repeat a name to "
                               "make a panel span several cells)" + _row_hint(rows))
        for name in r:
            if not _NAME.match(name):
                raise FormulaError(f"layout picture: {name!r} (line {i + 1}) is not a panel name")
    return rows


def _row_hint(rows, max_cells=24):
    """The picture with every line stretched to a common number of cells
    ("a b / c d e" -> "a a a b b b / c c d d e e"), offered when it is a valid
    picture (Qwen3 30B repeated unequal rows 16 times). Never applied silently:
    the stretched spans may not be what was meant."""
    import math
    n = math.lcm(*(len(r) for r in rows))
    if n > max_cells:
        return ""
    lines = [" ".join(name for name in r for _ in range(n // len(r))) for r in rows]
    try:
        parse("\n".join(lines))        # rectangles and no pinwheel
    except FormulaError:
        return ""
    return ("; with equal widths per line that would be:\n  " + "\n  ".join(lines)
            + "\n(check the spans are what you meant)")


def _areas(rows):
    """{name: (r0, c0, r1, c1)} (inclusive), checking each is a rectangle."""
    spots = {}
    for i, r in enumerate(rows):
        for j, name in enumerate(r):
            spots.setdefault(name, []).append((i, j))
    areas = {}
    for name, cells in spots.items():
        r0 = min(i for i, _ in cells)
        r1 = max(i for i, _ in cells)
        c0 = min(j for _, j in cells)
        c1 = max(j for _, j in cells)
        if len(cells) != (r1 - r0 + 1) * (c1 - c0 + 1):
            holes = [(i + 1, j + 1) for i in range(r0, r1 + 1) for j in range(c0, c1 + 1)
                     if rows[i][j] != name]
            raise FormulaError(f"layout picture: {name!r} is not a rectangle (lines {r0 + 1}-{r1 + 1}, "
                               f"columns {c0 + 1}-{c1 + 1}, but line/column {holes[0]} holds "
                               f"{rows[holes[0][0] - 1][holes[0][1] - 1]!r})")
        areas[name] = (r0, c0, r1, c1)
    return areas


def _split(names, areas, axis):
    """Cut the region of *names* into bands along *axis* (0 = horizontal
    cuts between lines, 1 = vertical cuts between columns), or None."""
    lo = min(areas[n][axis] for n in names)
    hi = max(areas[n][axis + 2] for n in names)
    cuts = [k for k in range(lo + 1, hi + 1)
            if not any(areas[n][axis] < k <= areas[n][axis + 2] for n in names)]
    if not cuts:
        return None
    bands, start = [], lo
    for k in cuts + [hi + 1]:
        band = [n for n in names if start <= areas[n][axis] < k]
        bands.append(sorted(band, key=lambda n: (areas[n][0], areas[n][1])))
        start = k
    return bands


def _tree(names, areas):
    if len(names) == 1:
        n = names[0]
        r0, c0, r1, c1 = areas[n]
        return {"type": "panel", "id": n, "cells": (c1 - c0 + 1, r1 - r0 + 1)}
    for axis, kind in ((0, "col"), (1, "row")):
        bands = _split(names, areas, axis)
        if bands:
            return {"type": kind, "children": [_tree(b, areas) for b in bands]}
    shown = ", ".join(sorted(names))
    raise FormulaError(f"layout picture: the panels {shown} interlock (like a pinwheel): no "
                       "straight line separates them, so they cannot be made of rows and "
                       "columns. Change the picture so a line can cut between them, or place "
                       "these panels on the free canvas (layout_canvas)")


def parse(text) -> dict:
    """The layout tree of a picture (same format as layout_formula.parse,
    plus each panel's span in cells)."""
    rows = _cells(text)
    areas = _areas(rows)
    order = sorted(areas, key=lambda n: (areas[n][0], areas[n][1]))      # reading order
    return _tree(order, areas)


def to_formula(tree) -> str:
    """The equivalent one-line formula (for messages and the CLI)."""
    from pyfigures.layout_formula import to_text
    return to_text(tree)
