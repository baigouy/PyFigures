"""Panel editor ("Edit Image"), the mouse-driven parts not covered by
test_panel_editor.py: polygon / polyline drawn click by click and finished
with a double-click, selecting a drawn ROI and dragging it, Ctrl-click
multi-selection, Ctrl+D duplicate, "Move to ori (0,0)", the significance
bracket tool, double-click editing of a floating text and of a scale bar,
the zoom limits, and that the drawing pane really paints what was drawn.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPointF, QEvent
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QInputDialog, QPushButton

from test_panel_editor import ui, fig, edit, draw, tool, annot_types, _mouse  # noqa: E402,F401


def _click(v, x, y, kind="click", mods=Qt.KeyboardModifier.NoModifier):
    """Click (or double-click) the drawing pane at image pixel (x, y)."""
    pos = QPointF(x * v.scale, y * v.scale)
    if kind == "dbl":
        ev = QMouseEvent(QEvent.Type.MouseButtonDblClick, pos, v.mapToGlobal(pos),
                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, mods)
        v.mouseDoubleClickEvent(ev)
        return
    for t, held in ((QEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton),
                    (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
        ev = QMouseEvent(t, pos, v.mapToGlobal(pos), Qt.MouseButton.LeftButton, held, mods)
        (v.mousePressEvent if t == QEvent.Type.MouseButtonPress else v.mouseReleaseEvent)(ev)


def _of(img, cls):
    return [a for a in (img.annotations or []) if type(a).__name__ == cls]


@pytest.mark.parametrize("tip,cls", [("Polygon", "Polygon2D"), ("polyline", "PolyLine2D")])
def test_polygon_and_polyline_click_by_click(fig, ui, tip, cls):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, tip)
        for x, y in ((30, 30), (160, 40), (150, 150), (40, 120)):
            _click(v, x, y)
        _click(v, 40, 120, "dbl")                          # double-click finishes the shape
        assert v.currently_drawn_shape is None
    img = edit(fig, ui, "gray", do)
    shapes = _of(img, cls)
    assert len(shapes) == 1
    r = shapes[0].boundingRect()
    assert r.width() > 100 and r.height() > 80


def test_tiny_polygon_is_dropped(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Polygon")
        for x, y in ((30, 30), (33, 31), (31, 34)):
            _click(v, x, y)
        _click(v, 31, 34, "dbl")
    img = edit(fig, ui, "gray", do)
    assert "Polygon2D" not in annot_types(img)


def test_select_and_drag_a_roi(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 120, 100)
        v.selected_shape = []
        _click(v, 60, 60)                                  # click inside: selects it
        assert len(v.selected_shape) == 1
        draw(ed, 60, 60, 110, 90)                          # drag it by (+50, +30)
    img = edit(fig, ui, "gray", do)
    r = _of(img, "Rectangle2D")[0].getRect()
    assert abs(r.x() - 70) < 3 and abs(r.y() - 50) < 3 and abs(r.width() - 100) < 2


def test_ctrl_click_multi_selection_moves_together(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Rectangle")
        draw(ed, 10, 10, 60, 60)
        v.selected_shape = []
        tool(ed, "Circle")
        draw(ed, 150, 100, 220, 170)
        v.selected_shape = []
        _click(v, 30, 30)
        _click(v, 185, 135, mods=Qt.KeyboardModifier.ControlModifier)
        assert len(v.selected_shape) == 2
        draw(ed, 30, 30, 50, 40)                           # +20, +10 for both
    img = edit(fig, ui, "gray", do)
    rect = _of(img, "Rectangle2D")[0].getRect()
    circ = _of(img, "Circle2D")[0].boundingRect()
    assert abs(rect.x() - 30) < 3 and abs(rect.y() - 20) < 3
    assert abs(circ.x() - 170) < 4 and abs(circ.y() - 110) < 4


def test_click_on_empty_area_clears_selection(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 80, 80)
        assert v.selected_shape
        v.shape_to_draw = None                             # no tool armed: a click only selects
        _click(v, 250, 180)
        assert v.selected_shape == []
    edit(fig, ui, "gray", do)


def test_duplicate_shortcut(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Rectangle")
        draw(ed, 40, 40, 140, 120)
        original = v.selected_shape[0]
        ed.duplicate.trigger()                             # Ctrl+D
        assert len(v.selected_shape) == 1 and v.selected_shape[0] is not original
    img = edit(fig, ui, "gray", do)
    rects = _of(img, "Rectangle2D")
    assert len(rects) == 2
    assert rects[0].getRect() == rects[1].getRect()


# The "Misc" box (Erode / Dilate / Move to ori (0,0)) is not shown in the
# editor (`if False`), so its three drawing-pane functions are tested directly.

def test_misc_move_to_origin(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Rectangle")
        draw(ed, 40, 40, 140, 120)
        v.move_to_origin()
        r = v.selected_shape[0].boundingRect()
        assert (r.x(), r.y()) == (0, 0)
        assert (r.width(), r.height()) == (100, 80)       # moved, not resized
    img = edit(fig, ui, "gray", do)
    r = _of(img, "Rectangle2D")[0].boundingRect()
    assert (r.x(), r.y()) == (0, 0)


def test_misc_erode_dilate_lines_and_skip_other_shapes(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Rectangle")
        draw(ed, 40, 40, 140, 120)
        rect = v.selected_shape[0]
        before = rect.getRect()
        v.erode()                                          # a rectangle cannot erode: no crash, unchanged
        v.dilate()
        assert rect.getRect() == before
        tool(ed, "Line")
        draw(ed, 20, 150, 200, 150)
        line = v.selected_shape[0]
        assert type(line).__name__ == "Line2D"
        w0 = line.length()
        cx0 = line.center().x()
        v.dilate()
        w1 = line.length()
        v.erode()
        v.erode()
        w2 = line.length()
        assert (w1, w2) == pytest.approx((w0 + 2, w0 - 2))      # 1 px at each end
        assert line.center().x() == pytest.approx(cx0)          # around its centre
        v.selected_shape = []
        v.erode()                                          # nothing selected: a no-op
        v.dilate()
    edit(fig, ui, "gray", do)


def test_significance_bracket(fig, ui, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("**", True)))

    def do(ed):
        v = ed.qt_viewer
        tool(ed, next(b.toolTip() for b in ed.findChildren(QPushButton) if b.text() == "Signif. bracket"))
        assert v._bracket_mode
        draw(ed, 50, 60, 200, 64)
        assert not v._bracket_mode                         # one-shot tool
    img = edit(fig, ui, "gray", do)
    poly = _of(img, "PolyLine2D")
    assert len(poly) == 1 and len(poly[0]) == 4            # down-tick, bar, down-tick
    labels = [t for t in _of(img, "TAText2D") if t.getPlainText() == "**"]
    assert labels and 50 < labels[0].boundingRect().center().x() < 200


def test_significance_bracket_without_label(fig, ui, monkeypatch):
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))

    def do(ed):
        tool(ed, next(b.toolTip() for b in ed.findChildren(QPushButton) if b.text() == "Signif. bracket"))
        draw(ed, 50, 60, 200, 64)
    img = edit(fig, ui, "gray", do)
    assert len(_of(img, "PolyLine2D")) == 1 and not any(t.getPlainText() == "**" for t in _of(img, "TAText2D"))


@pytest.mark.parametrize("accept", [True, False])
def test_double_click_floating_text_edits_it(fig, ui, accept, monkeypatch):
    from batoolset.GUI.customdialog import CustomDialog

    def edit_text(editor):
        editor.textEdit.setPlainText("Edited")
    ui["inner_cfg"]["Edit text"] = edit_text
    if not accept:                                         # the user types, then presses Cancel
        real = CustomDialog.exec

        def refuse(self, *a, **k):
            if self.windowTitle() == "Edit text":
                edit_text(self.main_widget)
                ui["inner"].append("Edit text")
                return 0
            return real(self, *a, **k)
        monkeypatch.setattr(CustomDialog, "exec", refuse)
        monkeypatch.setattr(CustomDialog, "exec_", refuse, raising=False)

    def do(ed):
        v = ed.qt_viewer
        ed.add_text_button.click()
        txt = next(s for s in v.shapes if type(s).__name__ == "TAText2D" and s.getPlainText() == "Your text here")
        v.selected_shape = [txt]
        r = txt.boundingRect()
        _click(v, r.center().x(), r.center().y(), "dbl")
    img = edit(fig, ui, "gray", do)
    assert "Edit text" in ui["inner"]
    texts = [t.getPlainText() for t in _of(img, "TAText2D")]
    assert ("Edited" in texts) == accept


def test_double_click_scale_bar_opens_its_editor(fig, ui):
    def set_bar(editor):
        editor.bar_width_spin.setValue(37) if hasattr(editor, "bar_width_spin") else None

    def do(ed):
        v = ed.qt_viewer
        tool(ed, "Scale Bar")
        bar = next(s for s in v.shapes if type(s).__name__ == "ScaleBar")
        v.selected_shape = [bar]
        r = bar.boundingRect()
        _click(v, r.center().x(), r.center().y(), "dbl")
    img = edit(fig, ui, "gray", do)
    assert "Edit ScaleBar" in ui["inner"]
    assert _of(img, "ScaleBar")


def test_zoom_is_clamped(fig, ui):
    def do(ed):
        v = ed.qt_viewer
        v.set_scale(1000)
        assert v.scale == v.max_scaling_factor
        v.set_scale(0.0001)
        assert v.scale == v.min_scaling_factor
        v.reset_scale()
        assert v.scale == 1
        v.zoom_in()
        assert v.scale > 1
        v.zoom_out()
        assert abs(v.scale - 1) < 1e-9
    edit(fig, ui, "gray", do)


def test_drawing_pane_paints_the_roi(fig, ui):
    seen = {}

    def do(ed):
        v = ed.qt_viewer
        v.contour_color = 0xFF0000
        v.resize(v.minimumSize())
        before = v.grab().toImage()
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 150, 120)
        v.selected_shape = []
        after = v.grab().toImage()                         # runs paintEvent

        def px(img, x, y):
            c = img.pixelColor(int(x * v.scale), int(y * v.scale))
            return c.red(), c.green(), c.blue()
        seen["before"] = px(before, 20, 70)
        seen["after"] = px(after, 20, 70)                  # on the left edge of the ROI
    edit(fig, ui, "gray", do)
    assert seen["after"] != seen["before"]
    r, g_, b = seen["after"]
    assert r > 150 and g_ < 120 and b < 120, seen
