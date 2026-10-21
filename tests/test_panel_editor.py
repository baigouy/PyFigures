"""The panel editor ("Edit Image" / double-click a panel): every control,
driven the way a user drives it, and the result checked on the figure after
pressing Ok (or unchanged after Cancel).

Covered: rotation + reset, crops + reset, comments, display range (whole
stack / displayed / custom min-max, per channel, hot pixels — and that they
come back correctly when the editor is reopened), channels on/off, LUTs
set/reset, z projection + range, dimension slider, px→unit factor, drawing a
ROI with the mouse (and the too-small-drag filter), every drawing tool button,
scale-bar and text buttons, the selected ROI's colour/opacity/rotation/stroke/
dash/arrowhead controls, ROI → crop and ROI → inset, the publication-style
tab, deleting an annotation from the list, and the script box.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPointF, QEvent
from qtpy.QtGui import QMouseEvent, QColor
from qtpy.QtWidgets import QDialog, QMessageBox, QColorDialog, QPushButton, QApplication


def _img(path, arr, dims):
    from batoolset.img import Img
    Img(arr, dimensions=dims).save(str(path))
    return str(path)


@pytest.fixture
def ui(monkeypatch):
    from batoolset.GUI.customdialog import CustomDialog
    st = {"edit": None, "accept": True, "inner": [], "inner_cfg": {}, "color": QColor(10, 200, 30)}

    def custom_exec(self, *a, **k):
        title = self.windowTitle()
        if title == "Annotate the image":
            if st["edit"] is not None:
                st["edit"](self.main_widget)
            return QDialog.Accepted if st["accept"] else QDialog.Rejected
        st["inner"].append(title)                     # nested dialogs (LUTs, scale bar...)
        cfg = st["inner_cfg"].get(title)
        if cfg is not None:
            cfg(self.main_widget)
        return QDialog.Accepted
    monkeypatch.setattr(CustomDialog, "exec_", custom_exec, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", custom_exec)
    # the colour buttons open a QColorDialog instance
    monkeypatch.setattr(QColorDialog, "exec_", lambda self: QDialog.Accepted, raising=False)
    monkeypatch.setattr(QColorDialog, "exec", lambda self: QDialog.Accepted)
    monkeypatch.setattr(QColorDialog, "selectedColor", lambda self: st["color"])
    monkeypatch.setattr(QColorDialog, "show", lambda self: None)
    # "Executing arbitrary code" confirmation and warnings
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: QMessageBox.Yes, raising=False)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Yes)
    for kind in ("warning", "information", "critical", "question"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(lambda *a, **k: QMessageBox.Yes))
    return st


@pytest.fixture
def fig(qapp, tmp_path, ui):
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    gray = np.tile(np.linspace(0, 250, 300, dtype=np.uint8), (200, 1))
    gray[10, 10] = 255
    rgb = np.zeros((200, 200, 3), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2] = 200, 90, 30
    z = np.stack([np.full((150, 150), v, np.uint8) for v in (20, 120, 220)])
    files = {"gray": _img(tmp_path / "gray.tif", gray, "hw"),
             "rgb": _img(tmp_path / "rgb.tif", rgb, "hwc"),
             "z": _img(tmp_path / "z.tif", z, "dhw")}
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    for k in ("gray", "rgb", "z"):
        M.add_image(pyf, [0], files[k])
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(1300, 900)
    g.show()
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    t0 = time.time()
    while time.time() - t0 < 60:
        qapp.processEvents()
        ims = _imgs(g)
        if len(ims) == 3 and all(i.img is not None for i in ims) and not getattr(g, "_active_img_loaders", None):
            break
        time.sleep(0.005)
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def _imgs(g):
    from batoolset.drawings.shapes.image2d import Image2D
    out, stack = [], list(g.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        s = stack.pop(0)
        if isinstance(s, Image2D):
            out.append(s)
        stack[0:0] = list(getattr(s, "content", None) or [])
    return out


def _get(g, name):
    return next(i for i in _imgs(g) if os.path.basename(i.filename) == f"{name}.tif")


def edit(g, ui, name, do=None, accept=True):
    """Open the editor on panel *name*, run do(editor), press Ok/Cancel.
    Returns the panel object now in the figure."""
    ui["edit"] = do
    ui["accept"] = accept
    g.paint.EZFIG_panel.update_image_annotations(image2d=_get(g, name))
    for _ in range(3):
        QApplication.processEvents()
    return _get(g, name)


def _mouse(w, kind, pos):
    t = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
         "release": QEvent.Type.MouseButtonRelease}[kind]
    btn = Qt.MouseButton.NoButton if kind == "move" else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.LeftButton if kind != "release" else Qt.MouseButton.NoButton
    ev = QMouseEvent(t, pos, w.mapToGlobal(pos), btn, held, Qt.KeyboardModifier.NoModifier)
    {"press": w.mousePressEvent, "move": w.mouseMoveEvent, "release": w.mouseReleaseEvent}[kind](ev)


def draw(ed, x0, y0, x1, y1, steps=5):
    """Mouse-drag on the editor's drawing pane (image pixel coordinates)."""
    v = ed.qt_viewer
    p0 = QPointF(x0 * v.scale, y0 * v.scale)
    _mouse(v, "press", p0)
    for i in range(1, steps + 1):
        _mouse(v, "move", QPointF((x0 + (x1 - x0) * i / steps) * v.scale, (y0 + (y1 - y0) * i / steps) * v.scale))
    _mouse(v, "release", QPointF(x1 * v.scale, y1 * v.scale))


def tool(ed, tooltip):
    btn = next(b for b in ed.findChildren(QPushButton) if b.toolTip() == tooltip)
    btn.click()
    return btn


def annot_types(img):
    return [type(a).__name__ for a in (img.annotations or [])]


# ---------------------------------------------------------------------------
# geometry, comments, cancel
# ---------------------------------------------------------------------------

def test_cancel_changes_nothing(fig, ui):
    before = _get(fig, "gray")

    def do(ed):
        ed.rotate_image_spinbox.setValue(45)
        ed.crop_left_spinbox.setValue(20)
        ed.comments_text_edit.setText("should vanish")
        draw(ed, 20, 20, 150, 120)
    after = edit(fig, ui, "gray", do, accept=False)
    assert after is before
    assert (after.theta or 0) == 0 and not after.crop_left and not after.user_comments
    assert "Rectangle2D" not in annot_types(after)


def test_rotation_crops_comments_applied(fig, ui):
    def do(ed):
        ed.rotate_image_spinbox.setValue(30)
        ed.crop_left_spinbox.setValue(10)
        ed.crop_right_spinbox.setValue(12)
        ed.crop_top_spinbox.setValue(5)
        ed.crop_bottom_spinbox.setValue(7)
        ed.comments_text_edit.setText("embryo 3, stage 12")
        assert "current AR" in ed.AR_display.text()
    img = edit(fig, ui, "gray", do)
    assert img.theta == 30
    assert (img.crop_left, img.crop_right, img.crop_top, img.crop_bottom) == (10, 12, 5, 7)
    assert img.user_comments == "embryo 3, stage 12"
    assert fig._dirty


def test_reset_buttons(fig, ui):
    edit(fig, ui, "gray", lambda ed: (ed.rotate_image_spinbox.setValue(20), ed.crop_left_spinbox.setValue(9)))

    def do(ed):
        assert ed.rotate_image_spinbox.value() == 20 and ed.crop_left_spinbox.value() == 9   # reloaded
        next(b for b in ed.findChildren(QPushButton) if b.text() == "Reset Angle").click()
        next(b for b in ed.findChildren(QPushButton) if b.text() == "Reset Crops").click()
    img = edit(fig, ui, "gray", do)
    assert (img.theta or 0) == 0 and not img.crop_left


# ---------------------------------------------------------------------------
# display range, channels, LUTs, projection
# ---------------------------------------------------------------------------

def test_custom_display_range_and_flags_round_trip(fig, ui):
    def do(ed):
        ed.min_max_combo_box.setCurrentIndex(ed.min_max_combo_box.findData("custom"))
        assert ed.min_spin_box.isEnabled() and ed.max_spin_box.isEnabled()
        ed.min_spin_box.setValue(40)
        ed.max_spin_box.setValue(180)
        ed.update_other_spin_box()            # what the debounce timer runs
        ed.per_channel_checkbox.setChecked(True)
        ed.ignore_hot_spots.setChecked(False)
    img = edit(fig, ui, "gray", do)
    n = img.normalization
    assert n["range"] == "custom" and (n["min_value"], n["max_value"]) == (40, 180)
    assert n["per_channel"] is True and n["ignore_hot_spots"] is False
    seen = {}

    def reopen(ed):
        seen.update(per=ed.per_channel_checkbox.isChecked(), hot=ed.ignore_hot_spots.isChecked(),
                    lo=ed.min_spin_box.value(), hi=ed.max_spin_box.value())
    edit(fig, ui, "gray", reopen, accept=False)
    assert seen == {"per": True, "hot": False, "lo": 40, "hi": 180}   # used to come back swapped


def test_min_above_max_is_corrected(fig, ui):
    def do(ed):
        ed.min_max_combo_box.setCurrentIndex(ed.min_max_combo_box.findData("custom"))
        ed.max_spin_box.setValue(100)
        ed.min_spin_box.setValue(150)
        ed.update_other_spin_box()
        assert ed.max_spin_box.value() > ed.min_spin_box.value()
    img = edit(fig, ui, "gray", do)
    assert img.normalization["max_value"] > img.normalization["min_value"]


def test_channels_toggle(fig, ui):
    def do(ed):
        assert len(ed.channel_boxes) == 3
        ed.channel_boxes[1].setChecked(False)
    img = edit(fig, ui, "rgb", do)
    assert list(img.channels) == [True, False, True]


def test_luts_set_and_reset(fig, ui):
    def pick(lut_widget):
        pass                                     # accept the widget's defaults
    ui["inner_cfg"]["Edit Look Up Tables (LUTs)"] = pick

    def do(ed):
        ed.set_LUTs()
    img = edit(fig, ui, "rgb", do)
    assert "Edit Look Up Tables (LUTs)" in ui["inner"]
    assert img.LUTs is not None and len(img.LUTs) == 3
    img = edit(fig, ui, "rgb", lambda ed: ed.reset_LUTs())
    assert img.LUTs is None


@pytest.mark.parametrize("proj", ["max", "min", "avg"])
def test_projection_and_z_range(fig, ui, proj):
    def do(ed):
        assert ed.dimsliders, "z-stack should offer a slider"
        ed.projection_combo_box.setCurrentIndex(ed.projection_combo_box.findData(proj))
        assert ed.proj_z_range_widget.isVisibleTo(ed)
        ed.proj_z_start_spin.setValue(1)
        ed.proj_z_end_spin.setValue(3)
    img = edit(fig, ui, "z", do)
    assert img.projection == proj
    assert (img.projection_z_start, img.projection_z_end) == (1, 3)
    # planes 1..2 hold 120 and 220: the panel shows their max / min / mean,
    # contrast-stretched over the whole stack (20..220 -> 0..255)
    raw = {"max": 220, "min": 120, "avg": 170}[proj]
    expected = round((raw - 20) / 200 * 255)
    q = img.qimage.convertToFormat(img.qimage.Format.Format_Grayscale8) if hasattr(img, "qimage") and img.qimage \
        else None
    if q is not None:
        assert abs(q.pixelColor(q.width() // 2, q.height() // 2).red() - expected) <= 3
    img = edit(fig, ui, "z", lambda ed: ed.projection_combo_box.setCurrentIndex(0))
    assert img.projection is None and img.projection_z_start is None


def test_typing_a_z_range_waits_for_a_pause_and_survives_a_style_change(qapp, tmp_path, ui):
    """Typing 100 in 'Z from' of a 300-slice stack went through 1 and 10
    (recomputing each time) and the box came back to 1; changing Max → Avg
    must keep the range."""
    from qtpy.QtTest import QTest
    from qtpy.QtCore import QEvent, Qt
    from qtpy.QtGui import QFocusEvent
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    stack = _img(tmp_path / "big.tif", np.stack([np.full((40, 50), v % 250, np.uint8) for v in range(300)]), "dhw")
    seen = {}

    def do(ed):
        ed.projection_combo_box.setCurrentIndex(ed.projection_combo_box.findData("max"))
        bg = ed.qt_viewer.background
        start = ed.proj_z_start_spin
        ed.show()
        start.setFocus()
        start.lineEdit().selectAll()
        QTest.keyClicks(start, "100")
        QApplication.processEvents()
        seen["while_typing"] = bg.projection_z_start          # nothing applied mid-typing
        ed.proj_z_end_spin.setFocus()                         # leaves the box: applied at once
        # an inactive offscreen window gets no focus-out from setFocus(): deliver the one a click sends
        QApplication.sendEvent(start, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason))
        QApplication.processEvents()
        seen["after"] = (start.value(), bg.projection_z_start, bg.projection_z_end)
        ed.projection_combo_box.setCurrentIndex(ed.projection_combo_box.findData("avg"))
        seen["after_avg"] = (start.value(), ed.proj_z_end_spin.value(), bg.projection_z_start)
    pyf = str(tmp_path / "big.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], stack)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    t0 = time.time()
    while time.time() - t0 < 60:
        qapp.processEvents()
        ims = _imgs(g)
        if ims and ims[0].img is not None and not getattr(g, "_active_img_loaders", None):
            break
        time.sleep(0.005)
    try:
        edit(g, ui, "big", do)
        assert seen["while_typing"] is None, seen
        assert seen["after"] == (100, 100, 300), seen
        assert seen["after_avg"] == (100, 300, 100), seen
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()


def test_z_start_not_past_end(fig, ui):
    def do(ed):
        ed.projection_combo_box.setCurrentIndex(ed.projection_combo_box.findData("max"))
        ed.proj_z_end_spin.setValue(2)
        ed.proj_z_start_spin.setValue(2)
        assert ed.proj_z_start_spin.value() < ed.proj_z_end_spin.value()
    edit(fig, ui, "z", do)


def test_dimension_slider_picks_plane(fig, ui):
    def do(ed):
        ed.dimsliders[0].setValue(2)
        ed.slider_dimension_value_changed()
    img = edit(fig, ui, "z", do)
    assert img.dimensions and img.dimensions["values"][0] == 2


def test_px_to_unit_factor(fig, ui):
    img = edit(fig, ui, "gray", lambda ed: ed.scale_conversion_spinner.setValue(0.25))
    assert img.px_to_unit_conversion_factor == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# drawing ROIs and annotations
# ---------------------------------------------------------------------------

def test_draw_rectangle_with_mouse(fig, ui):
    def do(ed):
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 150, 120)
        draw(ed, 200, 150, 205, 152)            # 5 px drag: treated as an accidental click
    img = edit(fig, ui, "gray", do)
    rects = [a for a in img.annotations if type(a).__name__ == "Rectangle2D"]
    assert len(rects) == 1
    r = rects[0].getRect()
    assert abs(r.width() - 130) < 2 and abs(r.height() - 100) < 2


@pytest.mark.parametrize("tip,cls", [
    ("Rectangle", "Rectangle2D"), ("Circle", "Circle2D"), ("Ellipse", "Ellipse2D"),
    ("square", "Square2D"), ("Line", "Line2D"), ("Arrow", "Line2D"),
    ("Dual Headed Arrow", "Line2D"), ("hand drawing", "Freehand2D"),
])
def test_each_drawing_tool(fig, ui, tip, cls):
    def do(ed):
        tool(ed, tip)
        draw(ed, 30, 30, 160, 140)
    img = edit(fig, ui, "gray", do)
    assert cls in annot_types(img), (tip, annot_types(img))
    if tip == "Dual Headed Arrow":
        line = [a for a in img.annotations if type(a).__name__ == "Line2D"][-1]
        assert line.arrow and line.arrow_at_both_ends


def test_scale_bar_and_text_buttons(fig, ui):
    def do(ed):
        tool(ed, "Scale Bar")
        ed.add_text_button.click()
    img = edit(fig, ui, "gray", do)
    assert "Add Scale Bar" in ui["inner"]
    assert "ScaleBar" in annot_types(img) and "TAText2D" in annot_types(img)


def test_selected_roi_style_controls(fig, ui):
    def do(ed):
        tool(ed, "Line")
        draw(ed, 20, 20, 200, 150)
        assert ed.qt_viewer.selected_shape
        ed.contourColor.click()                  # colour dialog answers st["color"]
        ed.opacity_spinner.setValue(0.5)
        ed.rotation_spinner.setValue(15)
        ed.line_stroke_size.setValue(3)
        ed.line_dotted_pattern_combo.setCurrentIndex(1)       # DashLine
    img = edit(fig, ui, "gray", do)
    line = [a for a in img.annotations if type(a).__name__ == "Line2D"][-1]
    assert line.color == 0x0AC81E
    assert line.opacity == pytest.approx(0.5) and line.theta == 15 and line.stroke == 3
    assert line.line_style == Qt.DashLine


def test_custom_dash_pattern_and_arrowheads(fig, ui):
    def do(ed):
        tool(ed, "Arrow")
        draw(ed, 20, 20, 200, 150)
        ed.line_dotted_pattern_combo.setCurrentText("CustomDashLine")
        ed.lineEdit.setText("1, 4, 5, 4")
        ed.arrow_width_scaler.setValue(7)
        ed.arrow_height_scaler.setValue(9)
    img = edit(fig, ui, "gray", do)
    line = [a for a in img.annotations if type(a).__name__ == "Line2D"][-1]
    assert list(line.line_style) == [1, 4, 5, 4]
    assert (line.arrowhead_width_scaler, line.arrowhead_height_scaler) == (7, 9)


def test_bad_custom_dash_pattern_is_ignored(fig, ui):
    def do(ed):
        tool(ed, "Line")
        draw(ed, 20, 20, 200, 150)
        ed.line_dotted_pattern_combo.setCurrentText("CustomDashLine")
        ed.lineEdit.setText("not, numbers")
    img = edit(fig, ui, "gray", do)
    assert "Line2D" in annot_types(img)


def test_fill_colour_and_reset(fig, ui):
    def do(ed):
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 150, 120)
        ed.fillColor.click()
        assert ed.qt_viewer.selected_shape[0].fill_color == 0x0AC81E
        ed.removeFillColor.click()
    img = edit(fig, ui, "gray", do)
    rect = [a for a in img.annotations if type(a).__name__ == "Rectangle2D"][-1]
    assert rect.fill_color is None


def test_roi_to_crop_and_to_inset(fig, ui):
    panel = fig.paint.EZFIG_panel
    n_top = len(panel.shapes_to_draw)

    def do(ed):
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 150, 120)
        ed.toCrop.click()
        ed.toInset.click()
    img = edit(fig, ui, "gray", do)
    insets = [a for a in img.annotations if type(a).__name__ == "Image2D"]
    assert len(insets) == 1
    assert len(panel.shapes_to_draw) == n_top + 1                # the crop added as a new row


def test_roi_to_crop_needs_a_rectangle(fig, ui):
    def do(ed):
        ed.toCrop.click()                          # nothing selected: a warning, no crash
        tool(ed, "Circle")
        draw(ed, 20, 20, 150, 120)
        ed.toCrop.click()                          # not a rectangle: warning again
    n = len(fig.paint.EZFIG_panel.shapes_to_draw)
    edit(fig, ui, "gray", do)
    assert len(fig.paint.EZFIG_panel.shapes_to_draw) == n


def test_delete_annotation_from_list(fig, ui):
    def add(ed):
        tool(ed, "Rectangle")
        draw(ed, 20, 20, 150, 120)
    edit(fig, ui, "gray", add)

    def delete(ed):
        ed.qt_viewer.selected_shape = [a for a in ed.qt_viewer.shapes if type(a).__name__ == "Rectangle2D"]
        ed.down()                                  # the Delete key / list delete
    img = edit(fig, ui, "gray", delete)
    assert "Rectangle2D" not in annot_types(img)


def test_publication_style_tab(fig, ui):
    def do(ed):
        ed.publication_style_checkbox.setChecked(True)
        ed.publication_font_size_spinbox.setValue(9)
        ed.publication_line_width_spinbox.setValue(1.5)
        ed.publication_font_radio_helvetica.setChecked(True)
        ed.on_publication_font_radio_changed()
        ed.publication_svg_stroke_check.setChecked(False)
    img = edit(fig, ui, "gray", do)
    assert img.publication_style is True and img.publication_font_size == 9
    assert img.publication_line_width == 1.5 and img.publication_font
    assert img.publication_svg_stroke_width is None


def test_script_box_runs_after_confirmation(fig, ui):
    script = "self.img = Img(file_path)[::2, ::2]"

    def do(ed):
        ed.script_text_edit.setText(script)
        ed.execute_script_button.click()
    img = edit(fig, ui, "gray", do)
    assert img.custom_loading_script == script
    assert img.img.shape[:2] == (100, 150)


def test_script_error_goes_to_the_log(fig, ui):
    seen = {}

    def do(ed):
        ed.script_text_edit.setText("self.img = undefined_name")
        ed.execute_script_button.click()
        seen["log"] = ed.script_log.toPlainText()
    img = edit(fig, ui, "gray", do)
    assert "undefined_name" in seen["log"]
    assert img.img is not None                       # the panel still shows its image
