"""Canvas interactions not driven by the right-click menu: the keyboard
shortcuts (Delete/Backspace, arrows, Esc), Ctrl-click and Shift-click
selection, double-click editing (image -> panel editor, label row -> label
row editor) and the movie export of a figure holding a time-stack.

Keyboard shortcuts are fired through the window's own QShortcut objects (the
key sequence is looked up, so a re-wired or removed shortcut fails the test);
mouse events are synthetic QMouseEvents sent to the canvas handlers.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import Qt, QPointF, QEvent, QRect
from qtpy.QtGui import QMouseEvent, QKeySequence, QShortcut
from qtpy.QtWidgets import QApplication, QMessageBox

from test_canvas_context_menu import (  # noqa: E402,F401  (fixtures + helpers)
    ui, gui, cap, rows, images, right_click, _center, _settle,
)


def _process(n=5):
    for _ in range(n):
        QApplication.processEvents()


def press_key(gui, key):
    """Fire the window shortcut bound to *key*, as pressing it would."""
    seq = QKeySequence(key)
    hits = [s for s in gui.findChildren(QShortcut) if s.key() == seq]
    assert hits, f"no shortcut for {seq.toString()}"
    hits[0].activated.emit()
    _process()


def _mouse(panel, kind, pos, button=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier):
    t = {"press": QEvent.Type.MouseButtonPress, "release": QEvent.Type.MouseButtonRelease,
         "dbl": QEvent.Type.MouseButtonDblClick}[kind]
    held = Qt.MouseButton.NoButton if kind == "release" else button
    ev = QMouseEvent(t, pos, panel.mapToGlobal(pos), button, held, mods)
    {"press": panel.mousePressEvent, "release": panel.mouseReleaseEvent,
     "dbl": panel.mouseDoubleClickEvent}[kind](ev)


def click(panel, pos, mods=Qt.KeyboardModifier.NoModifier):
    _mouse(panel, "press", pos, mods=mods)
    _mouse(panel, "release", pos, mods=mods)
    _process()


def _wait_checkpoint(qapp, gui, n_before, timeout=5):
    t0 = time.time()
    while len(gui.undo_stack) <= n_before and time.time() - t0 < timeout:
        qapp.processEvents()
        time.sleep(0.01)
    assert len(gui.undo_stack) > n_before, "no undo checkpoint"


def _n_images(gui):
    return sum(len(images(s)) for s in gui.paint.EZFIG_panel.shapes_to_draw)


# ---------------------------------------------------------------------------
# Delete / Backspace
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [Qt.Key.Key_Delete, Qt.Key.Key_Backspace])
def test_delete_key_removes_selected_image_and_undo_restores(gui, qapp, key):
    panel = gui.paint.EZFIG_panel
    row = rows(gui)[0]
    victim = images(row)[0]
    n_img = _n_images(gui)
    n_undo = len(gui.undo_stack)
    panel.set_current_selection(victim)
    press_key(gui, key)
    assert victim not in images(row) and _n_images(gui) == n_img - 1
    assert panel.selected_shape is None
    _wait_checkpoint(qapp, gui, n_undo)
    gui.undo()
    _settle(qapp, gui)
    assert _n_images(gui) == n_img


def test_delete_multi_selection_and_empty_rows_disappear(gui):
    panel = gui.paint.EZFIG_panel
    row = rows(gui)[0]
    panel.set_current_selection(list(images(row)))       # every image of the row
    press_key(gui, Qt.Key.Key_Delete)
    assert row not in panel.shapes_to_draw                # the emptied row is removed too
    assert len(rows(gui)) == 1


def test_delete_whole_row(gui):
    panel = gui.paint.EZFIG_panel
    row = rows(gui)[1]
    panel.set_current_selection(row)
    press_key(gui, Qt.Key.Key_Delete)
    assert row not in panel.shapes_to_draw and len(rows(gui)) == 1


def test_delete_with_nothing_selected_is_a_no_op(gui):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(None)
    before = list(panel.shapes_to_draw)
    press_key(gui, Qt.Key.Key_Delete)
    assert panel.shapes_to_draw == before and not gui._dirty


def test_escape_clears_selection(gui):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(rows(gui)[0])
    press_key(gui, Qt.Key.Key_Escape)
    assert panel.selected_shape is None


# ---------------------------------------------------------------------------
# arrows: reorder inside a row, or reorder rows
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,start,end", [
    (Qt.Key.Key_Up, 1, 0), (Qt.Key.Key_Left, 1, 0),
    (Qt.Key.Key_Down, 0, 1), (Qt.Key.Key_Right, 0, 1),
])
def test_arrows_move_image_inside_its_row(gui, key, start, end):
    panel = gui.paint.EZFIG_panel
    row = rows(gui)[0]
    img = row.content[start]
    other = row.content[end]
    panel.set_current_selection(img)
    press_key(gui, key)
    assert row.content[end] is img and row.content[start] is other
    assert panel.selected_shape is img                    # selection follows the image
    r_img, r_other = img.boundingRect(), other.boundingRect()
    assert (r_img.x() < r_other.x()) == (end < start)     # the layout was redone


@pytest.mark.parametrize("key", [Qt.Key.Key_Up, Qt.Key.Key_Down])
def test_arrows_move_whole_row(gui, key):
    panel = gui.paint.EZFIG_panel
    r0, r1 = rows(gui)
    moving = r1 if key == Qt.Key.Key_Up else r0
    panel.set_current_selection(moving)
    press_key(gui, key)
    assert rows(gui) == [r1, r0]
    assert r1.boundingRect().y() < r0.boundingRect().y()


def test_arrows_do_nothing_without_selection(gui):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(None)
    before = [list(r.content) for r in rows(gui)]
    for key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
        press_key(gui, key)
    assert [list(r.content) for r in rows(gui)] == before


def test_arrows_keep_a_label_inside_its_label_row(gui, cap):
    panel = gui.paint.EZFIG_panel
    right_click(gui, cap, images(rows(gui)[0])[0], pick=["Add labels ▶", "Above the row"])
    text_row = next(s for s in panel.shapes_to_draw if getattr(s, "isText", False))
    labels = list(text_row.content)
    panel.set_current_selection(labels[-1])
    press_key(gui, Qt.Key.Key_Up)
    assert list(text_row.content) == labels                # labels are tied to their image


# ---------------------------------------------------------------------------
# Ctrl-click / Shift-click selection
# ---------------------------------------------------------------------------

def test_ctrl_click_adds_and_removes_from_selection(gui):
    panel = gui.paint.EZFIG_panel
    a = images(rows(gui)[0])[0]
    c = images(rows(gui)[1])[0]
    ctrl = Qt.KeyboardModifier.ControlModifier
    click(panel, _center(panel, a))
    panel.set_current_selection(a)                         # first click selects (as the release does)
    click(panel, _center(panel, c), mods=ctrl)
    assert isinstance(panel.selected_shape, list) and set(map(id, panel.selected_shape)) == {id(a), id(c)}
    click(panel, _center(panel, c), mods=ctrl)             # Ctrl-click again: deselect
    assert panel.selected_shape is a


def test_plain_click_on_empty_space_clears_selection(gui):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(rows(gui)[0])
    b = panel.updateBounds()
    click(panel, QPointF((b.right() + 40) * panel.scale, (b.bottom() + 40) * panel.scale))
    assert panel.selected_shape is None


def test_shift_click_selects_a_range_of_rows(gui, cap):
    panel = gui.paint.EZFIG_panel
    right_click(gui, cap, images(rows(gui)[1])[0], pick=["Add labels ▶", "Below the row"])
    top = panel.shapes_to_draw[0]
    last = panel.shapes_to_draw[-1]
    panel.set_current_selection(top)
    click(panel, _center(panel, last), mods=Qt.KeyboardModifier.ShiftModifier)
    assert panel.selected_shape == list(panel.shapes_to_draw)


# ---------------------------------------------------------------------------
# double-click editing
# ---------------------------------------------------------------------------

def test_double_click_image_opens_panel_editor(gui, ui):
    panel = gui.paint.EZFIG_panel
    ui["accept"] = False
    img = images(rows(gui)[0])[1]
    n_ann = len(img.annotations or [])
    _mouse(panel, "dbl", _center(panel, img))
    _process()
    assert ui["custom"] and ui["custom"][-1].lower().startswith(("edit", "annotate"))
    assert len(img.annotations or []) == n_ann            # cancelled: unchanged


def test_double_click_empty_space_does_nothing(gui, ui):
    panel = gui.paint.EZFIG_panel
    b = panel.updateBounds()
    _mouse(panel, "dbl", QPointF((b.right() + 40) * panel.scale, (b.bottom() + 40) * panel.scale))
    _process()
    assert ui["custom"] == []


def _label_row(gui, cap):
    panel = gui.paint.EZFIG_panel
    right_click(gui, cap, images(rows(gui)[0])[0], pick=["Add labels ▶", "Above the row"])
    panel.set_current_selection(None)
    return next(s for s in panel.shapes_to_draw if getattr(s, "isText", False))


def test_double_click_label_row_edits_labels(gui, cap, ui, qapp):
    panel = gui.paint.EZFIG_panel
    text_row = _label_row(gui, cap)
    n_labels = len(text_row.content)

    def configure(dialog):
        assert dialog.windowTitle() == "Edit labels"
        panel.all_text_editors[0].textEdit.setPlainText("Control")
        panel.add_new_text()                               # the dialog's "Add Text" button
        panel.all_text_editors[-1].textEdit.setPlainText("Extra")
    ui["configure"] = configure
    n_undo = len(gui.undo_stack)
    _mouse(panel, "dbl", _center(panel, text_row.content[0]))
    _process()
    assert ui["custom"][-1] == "Edit labels"
    assert text_row.content[0].annotations[0].getPlainText() == "Control"
    assert len(text_row.content) == n_labels + 1
    assert text_row.content[-1].annotations[0].getPlainText() == "Extra"
    _wait_checkpoint(qapp, gui, n_undo)


def test_cancelled_label_row_edit_restores_texts(gui, cap, ui):
    panel = gui.paint.EZFIG_panel
    text_row = _label_row(gui, cap)
    before = [t.annotations[0].getPlainText() for t in text_row.content]

    def configure(dialog):
        panel.all_text_editors[0].textEdit.setPlainText("typo")
    ui["configure"] = configure
    ui["accept"] = False
    _mouse(panel, "dbl", _center(panel, text_row.content[0]))
    _process()
    assert ui["custom"][-1] == "Edit labels"
    assert [t.annotations[0].getPlainText() for t in text_row.content] == before


def test_right_click_label_row_offers_edit_text_row(gui, cap, ui):
    text_row = _label_row(gui, cap)
    ui["accept"] = False
    tree = right_click(gui, cap, text_row.content[0], pick=None)
    assert "Edit text" in tree and "Edit text row" in tree
    right_click(gui, cap, text_row.content[0], pick=["Edit text row"])
    assert ui["custom"][-1] == "Edit labels"


# ---------------------------------------------------------------------------
# non-letter text font / background (right-click > Text & lettering)
# ---------------------------------------------------------------------------

def test_text_background_applies_to_non_letter_text_only(gui, cap, ui):
    from batoolset.drawings.shapes.txt2d import TAText2D
    img = images(rows(gui)[0])[0]
    img.annotations.append(TAText2D("caption"))

    def configure(dialog):
        dialog.main_widget.get_color = lambda: 0xFF00FF
    ui["configure"] = configure
    right_click(gui, cap, img, pick=["Text & lettering ▶", "Change background (non-Letter text)"])
    texts = [a for a in img.annotations if isinstance(a, TAText2D)]
    assert any(not t.is_letter and t.fill_color == 0xFF00FF for t in texts)
    assert all(t.fill_color != 0xFF00FF for t in texts if t.is_letter)


def test_text_font_applies_to_non_letter_text_only(gui, cap, ui):
    from batoolset.drawings.shapes.txt2d import TAText2D
    from qtpy.QtGui import QFont
    img = images(rows(gui)[0])[0]
    img.annotations.append(TAText2D("caption"))
    font = QFont("Courier New", 17)

    def configure(dialog):
        dialog.main_widget.get_font = lambda: font
    ui["configure"] = configure
    right_click(gui, cap, img, pick=["Text & lettering ▶", "Change font (non-Letter text)"])
    texts = [a for a in img.annotations if isinstance(a, TAText2D)]
    caption = next(t for t in texts if t.getPlainText() == "caption")
    assert "17" in caption.doc.toHtml() or "Courier" in caption.doc.toHtml()
    letters = [t for t in texts if t.is_letter]
    assert all("Courier" not in t.doc.toHtml() for t in letters)


# ---------------------------------------------------------------------------
# zoom shortcuts, fit, clicking the grey area around the figure
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seq", ["Ctrl++", "Ctrl+Shift+="])
def test_zoom_in_shortcuts(gui, seq):
    panel = gui.paint.EZFIG_panel
    gui.paint.zoom_reset()
    b = panel.updateBounds()
    press_key(gui, seq)
    # the canvas holds the zoomed figure (it is also never smaller than the
    # visible area, so a small figure does not make it wider)
    assert abs(panel.scale - 1.1) < 1e-6 and panel.width() >= (b.x() + b.width()) * 1.1


@pytest.mark.parametrize("seq", ["Ctrl+-", "Ctrl+Shift+-"])
def test_zoom_out_shortcuts_and_reset(gui, seq):
    panel = gui.paint.EZFIG_panel
    gui.paint.zoom_reset()
    press_key(gui, seq)
    assert abs(panel.scale - 0.9) < 1e-6
    press_key(gui, "Ctrl+0")
    assert panel.scale == 1.0


def test_fit_alternates_width_and_height(gui):
    paint = gui.paint
    panel = paint.EZFIG_panel
    paint.resize(900, 300)                                  # wide and short: the two fits differ
    _process()
    paint.fit_to_width_or_height()
    b = panel.updateBounds()
    fit_w = panel.scale
    assert abs(b.width() * fit_w - (paint.scrollArea.width() - 2
                                    - paint.scrollArea.verticalScrollBar().sizeHint().width())) < 2
    paint.fit_to_width_or_height()
    assert panel.scale != fit_w                             # now fitted to the height
    paint.fit_to_window()
    assert panel.scale <= min(fit_w, panel.scale) + 1e-9


def test_click_on_grey_area_clears_selection(gui):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(rows(gui)[0])
    sa = gui.paint.scrollArea
    pos = QPointF(sa.width() - 5, sa.height() - 5)
    ev = QMouseEvent(QEvent.Type.MouseButtonPress, pos, QPointF(sa.mapToGlobal(pos.toPoint())),
                     Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    sa.mousePressEvent(ev)
    assert panel.selected_shape is None


def test_status_popup(gui):
    paint = gui.paint
    paint.show_popup("Hello")
    assert paint.popup_label.isVisible() and paint.popup_label.text().strip() == "Hello"
    paint.show_popup("State Saved")                         # does not hide a more useful message
    assert paint.popup_label.text().strip() == "Hello"
    paint.show_popup("")                                    # empty: ignored
    assert paint.popup_label.text().strip() == "Hello"


def test_scroll_to_selected_item(gui):
    paint = gui.paint
    panel = paint.EZFIG_panel
    paint.scaleImage(4.0)
    paint.resize(400, 300)
    _process()
    last = rows(gui)[-1]
    panel.set_current_selection(last)
    paint.scroll_to_item()
    _process()
    vis = paint.scrollArea.viewport().rect().translated(paint.scrollArea.horizontalScrollBar().value(),
                                                        paint.scrollArea.verticalScrollBar().value())
    r = last.getRect(all=True)
    assert vis.intersects(QRect(int(r.x() * panel.scale), int(r.y() * panel.scale),
                                int(r.width() * panel.scale), int(r.height() * panel.scale)))


# ---------------------------------------------------------------------------
# movie export (File > Export as video)
# ---------------------------------------------------------------------------

@pytest.fixture
def movie_gui(qapp, tmp_path, ui):
    import tifffile
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    t = np.stack([np.full((32, 48), 30 + 40 * i, np.uint8) for i in range(5)])
    movie = str(tmp_path / "movie.tif")
    tifffile.imwrite(movie, t, imagej=True, metadata={"axes": "TYX"})
    still = str(tmp_path / "still.tif")
    tifffile.imwrite(still, np.full((32, 48), 200, np.uint8))
    pyf = str(tmp_path / "movie.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], movie)
    M.add_image(pyf, [0], still)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    _settle(qapp, g)
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def _answer_frame_mode(monkeypatch, label):
    def fake_exec(box, *a, **k):
        btn = next((b for b in box.buttons() if b.text() == label), None)
        if btn is not None:
            btn.click()
        return 0
    monkeypatch.setattr(QMessageBox, "exec_", fake_exec, raising=False)
    monkeypatch.setattr(QMessageBox, "exec", fake_exec)


def _frames(path):
    import cv2
    cap_ = cv2.VideoCapture(path)
    out = []
    while True:
        ok, fr = cap_.read()
        if not ok:
            break
        out.append(fr)
    cap_.release()
    return out


@pytest.mark.parametrize("mode", ["Freeze last frame", "Blank (background) frame"])
def test_export_as_video(movie_gui, monkeypatch, tmp_path, mode):
    from pyfigures.gui import pfgui
    out = str(tmp_path / "out.mp4")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
    _answer_frame_mode(monkeypatch, mode)
    movie_gui.export_as_video()
    frames = _frames(out)
    assert len(frames) == 5
    means = [float(f.mean()) for f in frames]
    assert means == sorted(means) and means[-1] > means[0] + 10   # the movie panel brightens
    assert "Exported 5 frame(s)" in movie_gui.statusBar().currentMessage()
    # the figure itself is back on its own frame afterwards
    mv = images(rows(movie_gui)[0])[0]
    assert getattr(mv, "dimensions", None) in (None, {}) or mv.qimage is not None


def test_export_as_video_cancelled_writes_nothing(movie_gui, monkeypatch, tmp_path):
    from pyfigures.gui import pfgui
    out = str(tmp_path / "never.mp4")
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
    _answer_frame_mode(monkeypatch, "Cancel")
    movie_gui.export_as_video()
    assert not os.path.exists(out)
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: None)
    movie_gui.export_as_video()
    assert not os.path.exists(out)


def test_save_video_restores_panel_state(movie_gui, tmp_path):
    panel = movie_gui.paint.EZFIG_panel
    mv = images(rows(movie_gui)[0])[0]
    before = (mv.dimensions, mv.projection)
    n = panel.save_video(str(tmp_path / "x.avi"), frame_mode="blank", bg_color=(255, 0, 0))
    assert n == 5 and os.path.getsize(str(tmp_path / "x.avi")) > 0
    assert (mv.dimensions, mv.projection) == before
