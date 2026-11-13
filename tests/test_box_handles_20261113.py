"""Resize handles on rectangles, squares, ellipses and circles in the panel editor
(user, 2026-11-13: "I have no bounds for circle shapes (unlike for lines)"): a
selected box shape gets 8 handles; dragging one resizes it, the opposite side stays,
circles and squares stay round / square, and Ctrl+Z puts the old size back."""
from __future__ import annotations

import pytest
from qtpy.QtCore import QPointF, QRectF
from qtpy.QtWidgets import QApplication

from test_panel_editor import ui, fig, edit, draw, tool, _mouse  # noqa: F401  (fixtures)
from pyfigures.gui import editor_interaction as EI


def _drag(ed, a, b, steps=4):
    draw(ed, a[0], a[1], b[0], b[1], steps=steps)
    for _ in range(2):
        QApplication.processEvents()


def _box(shape):
    r = EI.box_rect(shape)
    return r.x(), r.y(), r.width(), r.height()


# -- pure helpers --------------------------------------------------------------
def test_the_eight_handles_and_what_they_grab():
    r = QRectF(10, 20, 100, 50)
    points = EI.box_handle_points(r)
    assert list(points) == list(EI.BOX_HANDLES)
    assert points['bottom right'] == QPointF(110, 70) and points['top'] == QPointF(60, 20)

    class Box(QRectF):
        pass
    box = Box(r)
    assert EI.box_handle_at(box, QPointF(108, 69), 2.0) == 'bottom right'
    assert EI.box_handle_at(box, QPointF(11, 45), 2.0) == 'left'
    assert EI.box_handle_at(box, QPointF(60, 45), 2.0) is None          # the inside still moves it


def test_a_tiny_shape_keeps_its_middle_free_and_visible():
    """A tiny ROI vanished under its eight opaque squares (user, 2026-11-13): small
    shapes get 4 smaller corner handles and a smaller grab zone."""
    class Box(QRectF):
        pass
    tiny = Box(QRectF(100, 100, 12, 12))
    rects = EI.box_handle_rects(tiny, 1.0)
    assert len(rects) == 4 and all(r.width() <= 4 for r in rects)
    assert EI.box_handle_at(tiny, QPointF(106, 106), 1.0) is None      # the middle moves it
    assert EI.box_handle_at(tiny, QPointF(112, 112), 1.0) == 'bottom right'
    # zoomed in, the same shape is big on screen: all 8 handles again
    assert len(EI.box_handle_rects(tiny, 8.0)) == 8


def test_resized_box_keeps_the_opposite_side():
    r = QRectF(10, 20, 100, 50)
    assert EI.resized_box(r, 'bottom right', QPointF(150, 100)) == QRectF(10, 20, 140, 80)
    assert EI.resized_box(r, 'left', QPointF(30, 0)) == QRectF(30, 20, 80, 50)
    assert EI.resized_box(r, 'top', QPointF(0, 60)) == QRectF(10, 60, 100, 10)
    # never flipped inside out
    out = EI.resized_box(r, 'right', QPointF(-50, 0))
    assert out.width() >= 2 and out.left() == 10


def test_a_circle_stays_round():
    r = QRectF(0, 0, 40, 40)
    out = EI.resized_box(r, 'bottom right', QPointF(80, 50), keep_square=True)
    assert out == QRectF(0, 0, 80, 80)
    out = EI.resized_box(r, 'top left', QPointF(-20, 10), keep_square=True)
    assert out.width() == out.height() and out.right() == 40 and out.bottom() == 40
    out = EI.resized_box(r, 'right', QPointF(60, 5), keep_square=True)
    assert out.width() == out.height() == 60 and out.center().y() == 20


def test_undo_state_keeps_an_ellipse_size():
    from batoolset.drawings.shapes.ellipse2d import Ellipse2D
    e = Ellipse2D(10, 10, 40, 30)
    state = EI.shape_state(e)
    EI.set_box_rect(e, QRectF(10, 10, 90, 90))
    EI.restore_state(e, state)
    assert _box(e) == (10, 10, 40, 30)


# -- in the editor ---------------------------------------------------------------
@pytest.mark.parametrize('kind', ['Rectangle', 'Ellipse'])
def test_drag_a_corner_resizes_then_undo(fig, ui, kind):
    out = {}

    def do(ed):
        tool(ed, kind)
        _drag(ed, (20, 20), (80, 60))
        shape = ed.qt_viewer.shapes[-1]
        assert type(shape).__name__ in ('Rectangle2D', 'Rect2D', 'Ellipse2D')
        assert ed.qt_viewer.selected_shape == [shape] and ed.qt_viewer._single_selected_box() is shape
        before = _box(shape)
        _drag(ed, (80, 60), (130, 120))                      # the bottom-right handle
        x, y, w, h = _box(shape)
        assert (x, y) == pytest.approx(before[:2], abs=1)
        assert (w, h) == pytest.approx((110, 100), abs=2)
        assert ed.undo()
        out['after_undo'] = _box(shape)
        out['before'] = before
    edit(fig, ui, "gray", do, accept=False)
    assert out['after_undo'] == pytest.approx(out['before'], abs=0.5)


def test_a_drawn_circle_stays_a_circle(fig, ui):
    out = {}

    def do(ed):
        tool(ed, "Circle")
        _drag(ed, (20, 20), (60, 60))
        shape = ed.qt_viewer.shapes[-1]
        _, _, w0, _ = _box(shape)
        x, y = _box(shape)[:2]
        _drag(ed, (x + w0, y + w0), (x + w0 + 40, y + w0 + 10))
        out['box'] = _box(shape)
        out['w0'] = w0
    edit(fig, ui, "gray", do, accept=False)
    _, _, w, h = out['box']
    assert w == pytest.approx(h, abs=0.5) and w > out['w0'] + 30
