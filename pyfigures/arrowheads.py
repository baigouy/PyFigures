"""Arrowhead-only marks, as in papers: a larger head and no line. Stored as an
ordinary arrow (Line2D, arrow=True) whose line is much shorter than its head,
so the head always swallows it — nothing new in the .pyf format, every export
draws it. One rule shared by the image editor, the MCP tools and the readers
that tell an arrowhead from an arrow.
"""
from __future__ import annotations

import math

# head (half width, length) in multiples of the stroke: larger than an arrow's
ARROWHEAD_ONLY = (6.0, 16.0)
ARROWHEAD_SIZES = {"small": (4.5, 12.0), "normal": (6.0, 16.0), "large": (8.0, 22.0)}
# line length (image px) of a stored arrowhead: only its direction matters
HEAD_ONLY_LENGTH = 0.5


def make_head_only(line, sizes=ARROWHEAD_ONLY):
    """Turn a drawn arrow (Line2D) into an arrowhead: same tip and direction,
    a line too short to show, a larger head."""
    p1, p2 = line.p1(), line.p2()
    dx, dy = p2.x() - p1.x(), p2.y() - p1.y()
    n = math.hypot(dx, dy)
    if n > 0:
        from qtpy.QtCore import QPointF
        line.setP1(QPointF(p2.x() - dx / n * HEAD_ONLY_LENGTH, p2.y() - dy / n * HEAD_ONLY_LENGTH))
    line.arrow = True
    line.arrow_at_both_ends = False
    line.arrowhead_width_scaler = max(float(line.arrowhead_width_scaler or 0), sizes[0])
    line.arrowhead_height_scaler = max(float(line.arrowhead_height_scaler or 0), sizes[1])
    return line


def is_head_only(x1, y1, x2, y2, arrow) -> bool:
    """An arrow whose line is (about) HEAD_ONLY_LENGTH long: an arrowhead."""
    return bool(arrow) and math.hypot(float(x2) - float(x1), float(y2) - float(y1)) <= 2 * HEAD_ONLY_LENGTH
