"""End-to-end image editor (marker ``gui_e2e``): a real double-click on a
panel opens "Annotate the image" (really executed), the edit is made with
the editor's own widgets / mouse drags on its drawing pane, nested dialogs
(LUTs, scale bar, colour) are answered by clicking their buttons, then Ok.
The result is read back from the saved file; undo / redo / reopen must keep
it; Cancel must change nothing.

(test_panel_editor.py covers every control in depth with a stubbed exec;
this file proves the same edits survive the real dialog path.)
"""
from __future__ import annotations

import pytest
from qtpy.QtCore import QEvent, QPointF, Qt
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QPushButton

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e


@pytest.fixture(scope="module")
def base_pyf(qapp, e2e_files, tmp_path_factory):
    """The base figure + a 300 × 200 'big.png' in its own row: shapes are
    drawn on it (the editor ignores shapes under 40 screen pixels, and the
    panel letter sits in the top-left corner of every panel)."""
    from PIL import Image
    from pyfigures import mcp_server as M
    d = tmp_path_factory.mktemp("editor")
    big = str(d / "big.png")
    Image.fromarray(H._blobs(30, h=200, w=300)).save(big)
    pyf = H.base_figure(d, e2e_files)
    M.add_image(pyf, [], big)
    return pyf


def _pane_mouse(v, kind, pos, double=False):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease, "double": QEvent.Type.MouseButtonDblClick}[kind]
    btn = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.NoButton if kind == "release" else Qt.MouseButton.LeftButton
    ev = QMouseEvent(t, pos, v.mapToGlobal(pos), btn, held, Qt.KeyboardModifier.NoModifier)
    {"press": v.mousePressEvent, "move": v.mouseMoveEvent, "release": v.mouseReleaseEvent,
     "double": v.mouseDoubleClickEvent}[kind](ev)


def _draw(ed, x0, y0, x1, y1, steps=5):
    """Mouse drag on the editor's drawing pane, in image pixels."""
    v = ed.qt_viewer
    _pane_mouse(v, "press", QPointF(x0 * v.scale, y0 * v.scale))
    for i in range(1, steps + 1):
        _pane_mouse(v, "move", QPointF((x0 + (x1 - x0) * i / steps) * v.scale, (y0 + (y1 - y0) * i / steps) * v.scale))
    _pane_mouse(v, "release", QPointF(x1 * v.scale, y1 * v.scale))


def _clicks(ed, points):
    """Polygon / polyline: one click per vertex, double-click closes."""
    v = ed.qt_viewer
    for x, y in points:
        p = QPointF(x * v.scale, y * v.scale)
        _pane_mouse(v, "press", p)
        _pane_mouse(v, "release", p)
    x, y = points[-1]
    p = QPointF(x * v.scale, y * v.scale)
    _pane_mouse(v, "double", p)
    _pane_mouse(v, "release", p)


def _tool(ed, tooltip):
    next(b for b in ed.findChildren(QPushButton) if b.toolTip() == tooltip).click()


def _extent(ed):
    """Image size in pixels: drags span most of it (the editor ignores a
    shape smaller than 40 screen pixels as an accidental click)."""
    w, h = ed.qt_viewer.background.get_raw_size()
    return float(w), float(h)


def _shape_tool(tip, polygon=False):
    def edit(ed):
        _tool(ed, tip)
        w, h = _extent(ed)
        if polygon:          # (away from the top-left corner: the panel letter is there)
            _clicks(ed, [(0.3 * w, 0.3 * h), (0.9 * w, 0.35 * h), (0.85 * w, 0.9 * h), (0.35 * w, 0.85 * h)])
        else:
            _draw(ed, 0.3 * w, 0.3 * h, 0.95 * w, 0.95 * h)
    return edit


def _crop(ed):
    ed.crop_left_spinbox.setValue(4)
    ed.crop_right_spinbox.setValue(6)
    ed.crop_top_spinbox.setValue(2)
    ed.crop_bottom_spinbox.setValue(3)


def _rotate(ed):
    ed.rotate_image_spinbox.setValue(30)


def _set_luts(ed):
    next(b for b in ed.findChildren(QPushButton) if b.text() == "Set LUTs").click()


def _projection(proj):
    def edit(ed):
        ed.projection_combo_box.setCurrentIndex(ed.projection_combo_box.findData(proj))
    return edit


def _text(ed):
    ed.add_text_button.click()


def _scale_bar(ed):
    _tool(ed, "Scale Bar")


def _roi_added(cls):
    def check(b, a):
        assert a["rois"].count(cls) == b["rois"].count(cls) + 1, (b["rois"], a["rois"])
        return True
    return check


# (id, panel, edit, nested dialogs, check(panel before, panel after))
EDITS = [
    ("crop", "cells", _crop, [], lambda b, a: a["crop"] == (4.0, 6.0, 2.0, 3.0)),
    ("rotate", "cells", _rotate, [], lambda b, a: a["theta"] == 30.0),
    ("LUTs", "rgb", _set_luts, [("Edit Look Up Tables (LUTs)", H.accept)], lambda b, a: a["luts"] and not b["luts"]),
    ("projection min", "zstack", _projection("min"), [], lambda b, a: a["projection"] == "min"),
    ("projection avg", "zstack", _projection("avg"), [], lambda b, a: a["projection"] == "avg"),
    ("text", "cells", _text, [], lambda b, a: len(a["texts"]) == len(b["texts"]) + 1),
    ("scale bar", "cells", _scale_bar, [("Add Scale Bar", H.accept)],
     lambda b, a: len(a["scale_bars"]) == len(b["scale_bars"]) + 1),
    ("rectangle", "big", _shape_tool("Rectangle"), [], _roi_added("Rectangle2D")),
    ("square", "big", _shape_tool("square"), [], _roi_added("Square2D")),
    ("circle", "big", _shape_tool("Circle"), [], _roi_added("Circle2D")),
    ("ellipse", "big", _shape_tool("Ellipse"), [], _roi_added("Ellipse2D")),
    ("line", "big", _shape_tool("Line"), [], _roi_added("Line2D")),
    ("arrow", "big", _shape_tool("Arrow"), [], _roi_added("Line2D")),
    ("double arrow", "big", _shape_tool("Dual Headed Arrow"), [], _roi_added("Line2D")),
    ("freehand", "big", _shape_tool("hand drawing"), [], _roi_added("Freehand2D")),
    ("polygon", "big", _shape_tool("Polygon", polygon=True), [], _roi_added("Polygon2D")),
    ("polyline", "big", _shape_tool("polyline", polygon=True), [], _roi_added("PolyLine2D")),
    ("floating text", "big", _shape_tool("Floating txt"), [],
     lambda b, a: len(a["texts"]) + len(a["rois"]) > len(b["texts"]) + len(b["rois"])),
]


def _open_editor_by_double_click(qapp, g, shape):
    pos = H.centre(g, shape)
    H.mouse(g, "press", pos)
    H.mouse(g, "release", pos)
    H.mouse(g, "double", pos)
    H.mouse(g, "release", pos)


def _panel_of(st, stem):
    return next(p for p in st["panels"] if p["name"] and str(p["name"]).startswith(stem))


@pytest.mark.parametrize("what,stem,edit,nested,check", EDITS, ids=[e[0] for e in EDITS])
def test_edit_in_the_image_editor(qapp, e2e_gui, base_pyf, tmp_path, watch, what, stem, edit, nested, check):
    g = e2e_gui
    H.load(qapp, g, base_pyf)
    before = H.snapshot(g, tmp_path)

    def annotate(dlg):
        edit(dlg.main_widget)
        qapp.processEvents()
        H.accept(dlg)
    with H.dialogs() as pilot:
        pilot.expect("Annotate the image", annotate)
        for match, handler in nested:
            pilot.expect(match, handler)
        _open_editor_by_double_click(qapp, g, H.by_name(g, stem))
        H.settle(qapp, g, lambda: not pilot.queue, timeout=20)
        H.settle(qapp, g)
    assert not pilot.queue and not pilot.unexpected, (pilot.seen, pilot.unexpected, pilot.queue)
    after = H.snapshot(g, tmp_path)
    b, a = _panel_of(before, stem), _panel_of(after, stem)
    assert check(b, a), (what, H.diff(before, after))
    def content(st, me):            # the row reflows: other panels' scale may change
        return [{k: v for k, v in p.items() if k != "scale"} for p in st["panels"] if p is not me]
    assert content(after, a) == content(before, b), f"{what} changed another panel"
    watch.check(what)
    H.check_invariants(qapp, g, tmp_path, before, after)
    watch.check(f"{what}: undo / redo / reopen")


def test_cancel_in_the_image_editor_changes_nothing(qapp, e2e_gui, base_pyf, tmp_path, watch):
    g = e2e_gui
    H.load(qapp, g, base_pyf)
    before = H.snapshot(g, tmp_path)

    def annotate(dlg):
        ed = dlg.main_widget
        _crop(ed)
        _rotate(ed)
        _shape_tool("Rectangle")(ed)
        H.reject(dlg)
    with H.dialogs() as pilot:
        pilot.expect("Annotate the image", annotate)
        _open_editor_by_double_click(qapp, g, H.by_name(g, "cells"))
        H.settle(qapp, g, lambda: not pilot.queue, timeout=20)
    assert not pilot.queue
    assert H.same(H.snapshot(g, tmp_path), before)
    assert not g._dirty
    watch.check("cancel")
