"""Arrowheads: the tip is the pointed-at pixel whatever the zoom / panel scale.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import math
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _red_mask(qimg):
    from batoolset.img import Img  # noqa: F401  (ensures the Qt binding is set)
    w, h = qimg.width(), qimg.height()
    ptr = qimg.constBits()
    ptr.setsize(qimg.sizeInBytes())
    arr = np.frombuffer(ptr, np.uint8).reshape(h, qimg.bytesPerLine() // 4, 4)[:, :w]
    b, g, r = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    # any red tint: the very point of an antialiased head has partial coverage
    return (r - g > 40) & (r - b > 40)


def _furthest_along(mask, ux, uy):
    ys, xs = np.nonzero(mask)
    assert len(xs), "nothing drawn"
    proj = xs * ux + ys * uy
    i = int(np.argmax(proj))
    return xs[i] + 0.5, ys[i] + 0.5


@pytest.mark.parametrize("scale", [0.25, 1.0, 4.0])
@pytest.mark.parametrize("both", [False, True])
@pytest.mark.parametrize("stroke", [0.65, 3.0])
def test_tip_is_the_end_point_at_any_scale(qapp, scale, both, stroke):
    from qtpy.QtGui import QImage, QPainter, QColor
    from batoolset.drawings.shapes.line2d import Line2D
    size = int(200 * scale) + 40
    x1, y1, x2, y2 = 20.0, 150.0, 150.0, 40.0          # diagonal, up-right
    ux, uy = (x2 - x1), (y2 - y1)
    n = math.hypot(ux, uy)
    ux, uy = ux / n, uy / n
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(scale, scale)
    Line2D(x1, y1, x2, y2, color=0xFF0000, stroke=stroke, arrow=True,
           arrow_at_both_ends=both).draw(p)
    p.end()
    mask = _red_mask(img)
    tx, ty = _furthest_along(mask, ux, uy)
    # the tip is within ~1 device pixel of the target, never beyond it
    assert math.hypot(tx - x2 * scale, ty - y2 * scale) <= 1.6
    if both:
        sx, sy = _furthest_along(mask, -ux, -uy)
        assert math.hypot(sx - x1 * scale, sy - y1 * scale) <= 1.6


def test_shaft_stops_inside_head():
    from qtpy.QtCore import QPointF
    from batoolset.drawings.shapes.line2d import arrow_shaft, arrowhead_polygon
    shaft = arrow_shaft(QPointF(0, 0), QPointF(100, 0), 10, True, False)
    assert shaft.p1().x() == 0 and shaft.p2().x() == pytest.approx(92)
    path, base = arrowhead_polygon(QPointF(0, 0), QPointF(100, 0), 10, 4)
    assert base.x() == pytest.approx(90)
    r = path.boundingRect()
    assert r.right() == pytest.approx(100) and r.left() == pytest.approx(90)
    # heads longer than the line: no shaft at all, still a head at the tip
    assert arrow_shaft(QPointF(0, 0), QPointF(5, 0), 10, True, True) is None
    assert arrowhead_polygon(QPointF(3, 3), QPointF(3, 3), 10, 4) is None


def test_tip_follows_the_image_when_the_panel_is_resized(qapp, tmp_path):
    """Real path: an arrow annotation on an Image2D, drawn at two panel widths.
    The tip must land on the same *image* pixel both times."""
    from PIL import Image
    from qtpy.QtGui import QImage, QPainter, QColor
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.line2d import Line2D
    src = str(tmp_path / "black.png")
    Image.fromarray(np.zeros((100, 200), np.uint8)).save(src)
    target = (150.0, 30.0)                        # image pixels
    for width in (80, 400, 1200):
        panel = Image2D(src)
        panel.annotations.append(Line2D(20, 90, target[0], target[1], color=0xFF0000,
                                        stroke=1.0, arrow=True))
        panel.setToWidth(width)
        rect = panel.getRect(scale=True)            # the rectangle actually drawn
        img = QImage(int(rect.right()) + 20, int(rect.bottom()) + 20,
                     QImage.Format.Format_ARGB32)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        panel.draw(p)
        p.end()
        k = rect.width() / 200.0
        ex, ey = rect.x() + target[0] * k, rect.y() + target[1] * k
        ux, uy = target[0] - 20, target[1] - 90
        n = math.hypot(ux, uy)
        tx, ty = _furthest_along(_red_mask(img), ux / n, uy / n)
        assert math.hypot(tx - ex, ty - ey) <= 1.6, (width, (tx, ty), (ex, ey))
