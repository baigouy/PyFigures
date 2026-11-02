"""Main figure editor: every menu entry and toolbar button.

1. A smoke test triggers EVERY QAction of the menu bar and toolbar on a real
   figure, with every dialog answered "Cancel" — nothing may raise, hang, open
   a browser or touch the user's settings, and the figure must survive.
2. Behaviour tests for the entries the rest of the suite didn't cover yet:
   each export format, the DPI prompt (Cancel really cancels), Save As,
   Merge, New, Undo/Redo, Selection and Remove-annotation menus, Template,
   Review, Theme and Help, and the toolbar's size / spacing / background /
   lettering controls.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtGui import QColor, QFont
from qtpy.QtWidgets import (QAction, QApplication, QColorDialog, QDialog, QFileDialog, QFontDialog,
                            QInputDialog, QMenu, QMessageBox)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def _tif(path, val, shape=(40, 60)):
    from batoolset.img import Img
    Img(np.full(shape, val, np.uint8), dimensions="hw").save(path)
    return str(path)


def _figure(d):
    """Two rows: a scale bar, a text label, a ROI and an inset on image 0."""
    from pyfigures import mcp_server as M
    pyf = os.path.join(d, "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    a = _tif(os.path.join(d, "a.tif"), 60)
    b = _tif(os.path.join(d, "b.tif"), 180)
    M.add_image(pyf, [0], a, label="A")
    M.add_image(pyf, [0], b, label="B")
    M.add_image(pyf, [1], a, label="C")
    M.set_scale_bar(pyf, [0], 0, 10)
    M.add_annotation(pyf, [0], 0, "note")
    M.add_roi_rect(pyf, [0], 0, 5, 5, 10, 10)
    M.add_inset(pyf, [0], 0, b)
    return pyf


@pytest.fixture
def dialogs(monkeypatch):
    """Every blocking UI element answers Cancel/No; records what was asked."""
    from pyfigures.gui import pfgui
    log = {"msg": [], "browser": [], "url": [], "dialog": []}

    def msg(kind, ret):
        def f(*a, **k):
            log["msg"].append((kind, a[1] if len(a) > 1 else ""))
            return ret
        return staticmethod(f)
    monkeypatch.setattr(QMessageBox, "question", msg("question", QMessageBox.No))
    monkeypatch.setattr(QMessageBox, "warning", msg("warning", QMessageBox.Cancel))
    monkeypatch.setattr(QMessageBox, "information", msg("information", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "critical", msg("critical", QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QMessageBox, "exec_", lambda self: 0, raising=False)

    def dlg_exec(self, *a, **k):
        log["dialog"].append(type(self).__name__)
        return 0
    monkeypatch.setattr(QDialog, "exec", dlg_exec)
    monkeypatch.setattr(QDialog, "exec_", dlg_exec, raising=False)
    monkeypatch.setattr(QMenu, "exec", lambda self, *a, **k: None)
    monkeypatch.setattr(QMenu, "exec_", lambda self, *a, **k: None, raising=False)
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (0, False)))
    monkeypatch.setattr(QInputDialog, "getDouble", staticmethod(lambda *a, **k: (0.0, False)))
    monkeypatch.setattr(QInputDialog, "getMultiLineText", staticmethod(lambda *a, **k: ("", False)))
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor()))
    monkeypatch.setattr(QFontDialog, "getFont", staticmethod(lambda *a, **k: (QFont(), False)))
    for name in ("getOpenFileName", "getSaveFileName"):
        monkeypatch.setattr(QFileDialog, name, staticmethod(lambda *a, **k: ("", "")))
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([], "")))
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    for name in ("saveFileDialog", "openFileNameDialog", "openFileNamesDialog"):
        if hasattr(pfgui, name):
            monkeypatch.setattr(pfgui, name, lambda *a, **k: None)
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: log["browser"].append(url) or True)
    from qtpy.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: log["url"].append(url) or True))
    return log


def _wait_loaded(qapp, g, timeout=60):
    t0 = time.time()
    while time.time() - t0 < timeout:
        qapp.processEvents()
        th = getattr(g, "_pyf_loader_thread", None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:
            running = False
        loaded = all(i.img is not None for i in _images(g) if i.filename and i.filename != "@template@")
        if not running and loaded and not getattr(g, "_lazy_img_queue", None) \
                and not getattr(g, "_active_img_loaders", None) and g.undo_stack:
            break
        time.sleep(0.005)
    for _ in range(5):
        qapp.processEvents()


@pytest.fixture
def gui(qapp, tmp_path, dialogs):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.resize(1200, 800)
    g.show()
    qapp.processEvents()
    pyf = _figure(str(tmp_path))
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    _wait_loaded(qapp, g)
    g._pyf_path = pyf
    yield g
    tut = getattr(g, "_tutorial", None)
    if tut is not None and hasattr(tut, "stop"):
        try:
            tut.stop()
        except Exception:
            pass
    g._dirty = False
    g._stop_all_img_loaders()
    for w in qapp.topLevelWidgets():
        if w is not g and w.isVisible():
            canvas = getattr(w, "canvas", None)
            if hasattr(canvas, "mark_saved"):
                canvas.mark_saved()
            w.close()
    g.close()


def _images(g):
    from batoolset.drawings.shapes.image2d import Image2D
    out, stack = [], list(g.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        s = stack.pop(0)
        if isinstance(s, Image2D):
            out.append(s)
        stack[0:0] = list(getattr(s, "content", None) or [])
    return out


def _annot_types(g):
    return sorted({type(a).__name__ for im in _images(g) for a in (im.annotations or [])})


def _all_actions(g):
    # wrappers are kept alive while walking: once a temporary wrapper dies its
    # id() is reused, and whole submenus (Insert > Images from files, Stack
    # views, Help > Show me how…) used to be skipped as "already seen"
    seen, out, keep = set(), [], []

    def walk(actions, where):
        for a in actions:
            keep.append(a)
            if id(a) in seen or a.isSeparator():
                continue
            seen.add(id(a))
            if a.menu() is not None:
                keep.append(a.menu())
                walk(a.menu().actions(), where + [a.text()])
            else:
                out.append((" > ".join(where + [a.text()]), a))
    walk(g.menuBar.actions(), [])
    walk(g.mainToolBar.actions(), ["toolbar"])
    btn_menu = g.page_background_button.menu()
    walk(btn_menu.actions(), ["toolbar", "Background"])
    return out


# ---------------------------------------------------------------------------
# 1. every action, everything cancelled
# ---------------------------------------------------------------------------

def test_every_menu_and_toolbar_action_survives_cancel(gui, qapp, dialogs, monkeypatch):
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda t, v, tb: errors.append((t.__name__, str(v))))
    actions = _all_actions(gui)
    assert len(actions) > 80, len(actions)
    n_before = len(_images(gui))
    triggered = []
    for label, act in actions:
        if not act.isEnabled() or label.endswith("—"):
            continue
        act.trigger()
        for _ in range(3):
            qapp.processEvents()
        triggered.append(label)
        assert not errors, f"{label}: {errors}"
    assert gui.isVisible()
    assert len(triggered) > 75
    # nothing reached the real browser / mail client
    assert all(u.startswith("file:") for u in dialogs["browser"])
    assert n_before >= 3


def test_every_action_has_a_handler(gui):
    from qtpy.QtWidgets import QWidgetAction
    missing = [label for label, act in _all_actions(gui)
               if act.isEnabled() and not label.endswith("—") and not isinstance(act, QWidgetAction)
               and act.text() and act.receivers(act.triggered) == 0]
    assert missing == []


# ---------------------------------------------------------------------------
# 2. exports
# ---------------------------------------------------------------------------

def _answer_dpi(monkeypatch, value="72", ok=True):
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: (value, ok)))


def _save_to(monkeypatch, path):
    from pyfigures.gui import pfgui
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: path)


@pytest.mark.parametrize("method,ext", [("export_as_png", "png"), ("export_as_tif", "tif"),
                                        ("export_as_jpg", "jpg"), ("export_as_svg", "svg"),
                                        ("export_as_pdf", "pdf")])
def test_export_formats(gui, monkeypatch, tmp_path, method, ext):
    out = str(tmp_path / f"o.{ext}")
    _save_to(monkeypatch, out)
    _answer_dpi(monkeypatch, "150")
    getattr(gui, method)()
    assert os.path.getsize(out) > 0
    if ext in ("png", "tif", "jpg"):
        from PIL import Image
        im = Image.open(out)
        bounds = gui.paint.EZFIG_panel.updateBounds()
        assert abs(im.size[0] - bounds.width() * 150 / 72) <= 2
        if ext == "jpg":
            # JPEG has no alpha: it must look like the PNG flattened on white
            png = str(tmp_path / "ref.png")
            _save_to(monkeypatch, png)
            gui.export_as_png()
            ref = Image.open(png).convert("RGBA")
            flat = Image.new("RGBA", ref.size, (255, 255, 255, 255))
            flat.alpha_composite(ref)
            diff = np.abs(np.asarray(flat.convert("RGB"), int) - np.asarray(im.convert("RGB"), int))
            assert diff.mean() < 3, diff.mean()


def test_raster_export_dpi_cancel_writes_nothing_and_returns(gui, monkeypatch, tmp_path):
    out = str(tmp_path / "cancelled.png")
    _save_to(monkeypatch, out)
    calls = []

    def cancel(*a, **k):
        calls.append(1)
        if len(calls) > 3:
            raise AssertionError("DPI prompt re-opened after Cancel")
        return ("", False)
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(cancel))
    gui.export_as_png()
    assert calls == [1] and not os.path.exists(out)


def test_toolbar_export_button_is_raster(gui, monkeypatch, tmp_path):
    out = str(tmp_path / "bar.tif")
    _save_to(monkeypatch, out)
    _answer_dpi(monkeypatch, "72")
    gui.export_as_tif_ico.trigger()
    assert os.path.getsize(out) > 0


def test_export_latex(gui, monkeypatch, tmp_path, dialogs):
    out = str(tmp_path / "fig.pdf")
    _save_to(monkeypatch, out)
    gui.export_as_latex()
    assert os.path.isfile(out) and os.path.isfile(str(tmp_path / "fig.pdf_tex"))
    assert dialogs["msg"][-1] == ("information", "PDF + LaTeX exported")


def test_export_video_without_time_stack_explains(gui, dialogs):
    gui.export_as_video()
    assert dialogs["msg"][-1] == ("information", "No time-stack to animate")


def test_print_ready_tiff(gui, monkeypatch, tmp_path, dialogs):
    out = str(tmp_path / "print.tif")
    _save_to(monkeypatch, out)
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("cmyk", True)))
    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (100, True)))
    gui.export_print_ready_action()
    from PIL import Image
    assert Image.open(out).mode == "CMYK"
    assert dialogs["msg"][-1] == ("information", "Print-ready TIFF exported")


# ---------------------------------------------------------------------------
# 3. file menu
# ---------------------------------------------------------------------------

def test_save_as_and_title(gui, monkeypatch, tmp_path):
    out = str(tmp_path / "copy.pyf")
    _save_to(monkeypatch, out)
    gui._mark_dirty()
    assert "•" in gui.windowTitle()
    gui.save_pyfigures(file=None)
    assert os.path.isfile(out) and gui.current_file == out
    assert "copy.pyf" in gui.windowTitle() and "•" not in gui.windowTitle()


def test_merge_appends_figure(gui, qapp, monkeypatch, tmp_path):
    from pyfigures.gui import pfgui
    n = len(_images(gui))
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: gui._pyf_path)
    gui.open_figure(append=True)
    _wait_loaded(qapp, gui)
    assert len(_images(gui)) == 2 * n


def test_new_respects_unsaved_prompt(gui, monkeypatch):
    gui._mark_dirty()
    n = len(_images(gui))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Cancel))
    gui.new_ico.trigger()
    assert len(_images(gui)) == n
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Discard))
    gui.new_ico.trigger()
    QApplication.processEvents()
    assert _images(gui) == [] and gui.current_file is None


def test_undo_redo_buttons(gui, qapp):
    panel = gui.paint.EZFIG_panel
    n = len(panel.shapes_to_draw)
    gui.save_state(show_popup=False)
    panel.shapes_to_draw.pop()
    gui.save_state(show_popup=False)
    assert len(panel.shapes_to_draw) == n - 1
    assert gui.undo_button.isEnabled()
    gui.undo_button.trigger()
    _wait_loaded(qapp, gui)
    assert len(panel.shapes_to_draw) == n
    gui.redo_button.trigger()
    _wait_loaded(qapp, gui)
    assert len(panel.shapes_to_draw) == n - 1


def test_undo_with_nothing_to_undo_keeps_figure_clean(qapp, dialogs):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.undo_stack, g.redo_stack, g.current_index = [], [], 0
    g._mark_clean()
    g.undo()
    g.redo()
    assert g._dirty is False
    g.close()


def test_templatify_turns_images_into_slots(gui, monkeypatch, tmp_path, qapp):
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Yes))
    out = str(tmp_path / "tpl.pyf")
    _save_to(monkeypatch, out)
    gui.templatify_figure()
    qapp.processEvents()
    names = [im.filename for im in _images(gui)]
    assert names and all(n == "@template@" for n in names if n), names


# ---------------------------------------------------------------------------
# 4. selection / annotations / lettering
# ---------------------------------------------------------------------------

def _menu_action(gui, *path):
    acts = gui.menuBar.actions()
    for i, name in enumerate(path):
        act = next(a for a in acts if a.text() == name)
        if i < len(path) - 1:
            acts = act.menu().actions()
    return act


def test_selection_reset_and_duplicate(gui):
    panel = gui.paint.EZFIG_panel
    first = panel.shapes_to_draw[0]
    panel.set_current_selection(first)
    n = len(panel.shapes_to_draw)
    _menu_action(gui, "Edit", "Duplicate Selection").trigger()
    assert len(panel.shapes_to_draw) == n + 1
    _menu_action(gui, "Edit", "Reset Selection").trigger()
    assert not panel.selected_shape


def _texts(gui):
    return sorted((a.getPlainText() if hasattr(a, "getPlainText") else str(a.text if hasattr(a, "text") else a),
                   bool(getattr(a, "is_letter", False)))
                  for im in _images(gui) for a in (im.annotations or []) if type(a).__name__ == "TAText2D")


@pytest.mark.parametrize("label,gone", [
    ("Remove all scale bars", {"ScaleBar"}),
    ("Remove all ROIs", {"Rectangle2D", "Rect2D"}),
    ("Remove all insets", {"Image2D"}),
])
def test_remove_annotation_kinds(gui, label, gone):
    before = set(_annot_types(gui))
    assert before & gone, before
    gui.paint.EZFIG_panel.set_current_selection(None)
    _menu_action(gui, "Annotations", "Remove", label).trigger()
    after = set(_annot_types(gui))
    assert not (after & gone), after
    assert after == before - gone                     # nothing else touched


def test_remove_all_texts_keeps_panel_letters(gui):
    texts = _texts(gui)
    assert any(not letter for _t, letter in texts) and any(letter for _t, letter in texts)
    gui.paint.EZFIG_panel.set_current_selection(None)
    _menu_action(gui, "Annotations", "Remove", "Remove all texts").trigger()
    after = _texts(gui)
    assert after and all(letter for _t, letter in after)


def test_remove_all_annotations(gui):
    assert _annot_types(gui)
    gui.paint.EZFIG_panel.set_current_selection(None)
    _menu_action(gui, "Annotations", "Remove",
                 "Remove all annotations (ROIs, scale bars, texts, ...)").trigger()
    assert set(_annot_types(gui)) <= {"TAText2D"}
    assert all(letter for _t, letter in _texts(gui))


def test_lettering_parameters_dialog(gui, dialogs):
    _menu_action(gui, "Annotations", "Panel letters (A, B, C…)…").trigger()
    assert dialogs["dialog"][-1] == "CustomDialog"


def test_auto_lettering_controls_change_letters(gui):
    gui.letter_line_edit.setText("A")
    assert gui.letter_line_edit.text() == "A"
    gui.auto_lettering_checkbox.setChecked(False)
    gui.auto_lettering_checkbox.setChecked(True)
    gui.letter_line_edit.setText("toolong")
    assert len(gui.letter_line_edit.text()) == 1


# ---------------------------------------------------------------------------
# 5. toolbar controls
# ---------------------------------------------------------------------------

def test_size_spinbox_resizes_selection(gui, qapp):
    panel = gui.paint.EZFIG_panel
    row = panel.shapes_to_draw[0]
    panel.set_current_selection(row)
    gui.size_spinbox.setValue(300)
    assert gui.value_changed_timer.isActive()
    gui.on_size_spinbox_value_changed_delayed()
    qapp.processEvents()
    assert abs(row.boundingRect().width() - 300) <= 2
    assert gui.unit_combobox.currentText() == "mm"      # default, as journals
    assert gui.value_label.text().endswith("105.8")     # 300 px at 72 dpi
    gui.unit_combobox.setCurrentText("Inches")
    assert gui.value_label.text().endswith("4.2")       # 300 px at 72 dpi
    gui.unit_combobox.setCurrentText("Cm")
    assert gui.value_label.text().endswith("10.6")
    gui.force_update_layout_button.trigger()
    qapp.processEvents()


def test_spacing_spinner_is_debounced_and_applied(gui):
    gui.main_space_spinner.setValue(9)
    assert gui.main_space_spinner_changed_timer.isActive()
    gui.update_space_and_paint()
    assert gui.paint.EZFIG_panel.space == 9


def test_background_menu(gui, monkeypatch):
    menu = gui.page_background_button.menu()
    by = {a.text(): a for a in menu.actions()}
    by["White"].trigger()
    assert gui.paint.EZFIG_panel.page_background == 0xFFFFFF and gui._dirty
    by["Black"].trigger()
    assert gui.paint.EZFIG_panel.page_background == 0
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(lambda *a, **k: QColor(10, 20, 30)))
    by["Other colour…"].trigger()
    assert gui.paint.EZFIG_panel.page_background == 0x0A141E
    by["None (transparent)"].trigger()
    assert gui.paint.EZFIG_panel.page_background is None


def test_page_bounds_checkbox(gui, dialogs):
    gui.page_bounds_checkbox.setChecked(True)          # dialog cancelled
    assert dialogs["dialog"][-1] == "CustomDialog"
    gui.page_bounds_checkbox.setChecked(False)
    assert gui.paint.EZFIG_panel.bounds is None


# ---------------------------------------------------------------------------
# 6. review / theme / help / tools
# ---------------------------------------------------------------------------

def test_export_for_review_writes_html_without_dpi_prompt(gui, monkeypatch, tmp_path):
    out = str(tmp_path / "review.html")
    _save_to(monkeypatch, out)
    monkeypatch.setattr(QInputDialog, "getItem",
                        staticmethod(lambda *a, **k: (_ for _ in ()).throw(AssertionError("DPI asked"))))
    gui.export_for_review()
    html = open(out, encoding="utf-8").read()
    assert "data:image/png;base64," in html


def test_review_comments_round_trip(gui, monkeypatch, tmp_path, dialogs):
    from pyfigures.gui import pfgui, review
    gui.current_file = gui._pyf_path
    gui.view_review_comments()
    assert dialogs["msg"][-1] == ("information", "No review comments")
    review.save_sidecar_comments(gui.current_file, [{"id": "c1", "x": 0.5, "y": 0.5, "text": "too dark"}])
    shown = []
    monkeypatch.setattr(pfgui, "show_review_comments_dialog", lambda *a, **k: shown.append(a[2]),
                        raising=False)
    import pyfigures.gui.review as rv
    monkeypatch.setattr(rv, "show_review_comments_dialog", lambda *a, **k: shown.append(a[2]))
    gui.view_review_comments()
    assert shown and shown[-1][0]["text"] == "too dark"


def test_theme_actions_switch_and_restore(gui, qapp):
    from pyfigures.gui import user_prefs
    original = user_prefs.load_theme()
    gui._theme_actions["dark"].trigger()
    assert gui._theme_actions["dark"].isChecked()
    assert qapp.palette().window().color().lightness() < 128
    gui._theme_actions["light"].trigger()
    assert qapp.palette().window().color().lightness() > 128
    gui._apply_theme(original)


def test_help_entries(gui, dialogs, qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    _menu_action(gui, "Help", "About").trigger()
    _menu_action(gui, "Help", "List shortcuts").trigger()
    # EZFIG_GUI.show_tips is stubbed for the whole suite (tips pop up at start-up)
    from pyfigures.gui.tipdialog import TipDialog
    TipDialog(gui, gui.tips).exec_()
    assert dialogs["dialog"][-3:] == ["AboutDialog", "QDialog", "TipDialog"]
    _menu_action(gui, "Help", "User Guide").trigger()
    assert dialogs["browser"] and dialogs["browser"][-1].startswith("file://")
    _menu_action(gui, "QC", "Show color-blind assistant").trigger()
    assert gui.color_assistant is not None and gui.color_assistant.isVisible()
    gui.color_assistant.close()


def test_colour_blindness_preview(gui, monkeypatch, dialogs):
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(lambda *a, **k: ("deuteranopia", True)))
    gui.preview_color_blindness()
    assert dialogs["dialog"], "no preview dialog shown"


def test_tutorial_entries_start_and_stop(gui, qapp):
    for label in ("▶  Beginner Tutorial", "▶  Medium Tutorial", "▶  Advanced Tutorial",
                  "▶  Publication && QC Tutorial", "▶  Sharing, Review && Accessibility Tutorial"):
        _menu_action(gui, "Help", label).trigger()
        qapp.processEvents()
        assert gui._tutorial.is_running() if hasattr(gui._tutorial, "is_running") else True
        if hasattr(gui._tutorial, "stop"):
            gui._tutorial.stop()


def test_poster_designer_opens_once(gui):
    _menu_action(gui, "Tools", "Poster / collage designer…").trigger()
    w1 = gui._poster_window
    assert w1.isVisible()
    _menu_action(gui, "Tools", "Poster / collage designer…").trigger()
    assert gui._poster_window is w1
    w1.close()


# ---------------------------------------------------------------------------
# 3. discoverability (2026-10-20): Insert menu, tooltips, hints, stacks
# ---------------------------------------------------------------------------

def test_menu_layout_groups_what_adds_panels(gui):
    tops = [a.text() for a in gui.menuBar.actions()]
    assert tops == ["File", "Edit", "Insert", "Annotations", "QC", "Tools", "View", "Help"], tops
    insert = [a.text() for a in _menu_action(gui, "Insert").menu().actions() if not a.isSeparator()]
    for item in ("Images from files", "Data plot from CSV…", "Multi-channel merge…", "Stack views",
                 "LUT colour bar…", "Add equation (LaTeX)…", "Add LaTeX code panel…",
                 "Add image from URL / OME-Zarr / OMERO…"):
        assert item in insert, (item, insert)
    annots = [a.text() for a in _menu_action(gui, "Annotations").menu().actions() if not a.isSeparator()]
    assert annots[-1] == "Remove"                      # destructive entries last, in a submenu
    assert _menu_action(gui, "File", "Convert figure to template")
    assert _menu_action(gui, "File", "Review comments", "Export for review…")
    assert _menu_action(gui, "Tools", "MCP call history / undo…")
    assert _menu_action(gui, "QC", "Preview figure under colour-blindness…")
    split = [a.text() for a in _menu_action(gui, "Insert", "Stack views").menu().actions()]
    assert "Channel split (Magenta/Green mode)…" in split


def test_every_menu_action_and_toolbar_control_explains_itself(gui):
    from qtpy.QtWidgets import QWidget
    for w in (gui.size_spinbox, gui.main_space_spinner, gui.auto_lettering_checkbox,
              gui.letter_line_edit, gui.page_bounds_checkbox, gui.unit_combobox,
              gui.force_update_layout_button_associated):
        assert w.toolTip(), w
    for label, act in _all_actions(gui):
        if label.split(" > ")[0] in ("Insert", "Annotations") and not label.endswith("—"):
            assert act.toolTip() and act.toolTip() != act.text(), label


def test_width_label_says_what_it_applies_to_and_mm(gui, qapp):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(None)
    gui.selectionUpdated()
    assert gui.force_update_layout_button_associated.text() == "→ all"
    assert "whole figure" in gui.force_update_layout_button_associated.toolTip()
    panel.set_current_selection(panel.shapes_to_draw[0])
    gui.selectionUpdated()
    assert gui.force_update_layout_button_associated.text() == "→ sel."
    assert "selected" in gui.force_update_layout_button_associated.toolTip()
    assert "Double-click a panel" in gui.statusBar().currentMessage()
    gui.size_spinbox.setValue(720)                   # 10 inches at 72 px per inch
    gui.unit_combobox.setCurrentText("mm")
    assert gui.value_label.text().endswith("254.0"), gui.value_label.text()


def _wait_images(qapp, g, n, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout and (len(_images(g)) < n or getattr(g, "_active_img_loaders", None)):
        qapp.processEvents()
        time.sleep(0.005)
    for _ in range(5):
        qapp.processEvents()


def test_insert_images_from_files_matches_the_drop_choices(gui, qapp, tmp_path, monkeypatch, dialogs):
    from pyfigures.gui import pfgui
    a = _tif(tmp_path / "n1.tif", 30)
    b = _tif(tmp_path / "n2.tif", 90)
    monkeypatch.setattr(pfgui, "openFileNamesDialog", lambda *x, **k: [a, b])
    n0 = len(_images(gui))
    n_top = len(gui.paint.EZFIG_panel.shapes_to_draw)
    _menu_action(gui, "Insert", "Images from files", "To a new row…").trigger()
    _wait_images(qapp, gui, n0 + 2)
    assert len(_images(gui)) == n0 + 2
    assert len(gui.paint.EZFIG_panel.shapes_to_draw) == n_top + 1     # one new row
    # next to the selected panel: needs a selection
    gui.paint.EZFIG_panel.set_current_selection(None)
    assert gui.add_images_from_files_action("with_row") is False
    assert dialogs["msg"][-1] == ("information", "Select a panel")
    # cancelled file dialog: nothing happens
    monkeypatch.setattr(pfgui, "openFileNamesDialog", lambda *x, **k: None)
    assert gui.add_images_from_files_action("single") is False


def test_new_z_stack_shows_max_projection_time_series_its_first_frame(gui, qapp, tmp_path):
    from batoolset.img import Img
    z = np.zeros((4, 30, 40), np.uint8)
    z[2, 5:10, 5:10] = 200                       # only in slice 2: invisible in slice 0
    Img(z, dimensions="dhw").save(str(tmp_path / "z.tif"))
    t = np.zeros((4, 30, 40), np.uint8)
    Img(t, dimensions="thw").save(str(tmp_path / "t.tif"))
    gui.max_proj_action.setChecked(True)      # the smoke test toggles every checkable action
    n0 = len(_images(gui))
    gui.add_images_to_new_row([str(tmp_path / "z.tif"), str(tmp_path / "t.tif")])
    _wait_images(qapp, gui, n0 + 2)
    new = {os.path.basename(i.filename): i for i in _images(gui)[-2:]}
    from batoolset.img import guess_dimensions
    dims = guess_dimensions(new["z.tif"].img)
    if "d" in dims:
        assert new["z.tif"].projection == "max"
    if "t" in guess_dimensions(new["t.tif"].img):
        assert new["t.tif"].projection is None
    # switched off in View: first slice again
    gui.max_proj_action.setChecked(False)
    from pyfigures.gui.user_prefs import load_max_project_z_stacks
    assert load_max_project_z_stacks() is False
    gui.add_images_to_new_row([str(tmp_path / "z.tif")])
    _wait_images(qapp, gui, n0 + 3)
    assert _images(gui)[-1].projection is None
    gui.max_proj_action.setChecked(True)


def test_edit_hint_bubble_once_and_dont_show_again(gui, qapp):
    from pyfigures.gui.user_prefs import load_show_edit_hint
    gui._edit_hint_shown = False
    gui.edit_hint_action.setChecked(True)
    box = gui._maybe_show_edit_hint()
    assert box is not None and "double-click an image" in box.text()
    # a bubble inside the window, not a (modal) dialog: the user keeps working
    assert box.parent() is gui and not box.isWindow() and QApplication.activeModalWidget() is None
    assert gui.rect().contains(box.geometry())
    assert gui._maybe_show_edit_hint() is None               # once per session
    gui._edit_hint_check.setChecked(True)                    # "Don't show this again"
    assert not gui.edit_hint_action.isChecked() and load_show_edit_hint() is False
    box.close()
    gui._edit_hint_shown = False
    assert gui._maybe_show_edit_hint() is None               # switched off: never shown
    gui.edit_hint_action.setChecked(True)
    assert load_show_edit_hint() is True
    gui._edit_hint_shown = False
    box = gui._maybe_show_edit_hint()
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest
    QTest.mouseClick(box, Qt.MouseButton.LeftButton)           # a click on the bubble closes it
    assert not box.isVisible()


def test_a_single_dropped_stack_offers_a_montage(gui, qapp, tmp_path, monkeypatch):
    from batoolset.img import Img
    Img(np.zeros((5, 30, 40), np.uint8), dimensions="thw").save(str(tmp_path / "movie.tif"))
    flat = _tif(tmp_path / "flat.tif", 50)

    def labels(files):
        gui.add_image_from_an_external_source_context_menu(files, None)
        return [a.text() for a in gui.paint.EZFIG_panel.contextMenu.actions()]
    assert any("Montage of frames" in t for t in labels([str(tmp_path / "movie.tif")]))
    assert not any("Montage" in t for t in labels([flat]))
    assert not any("Montage" in t for t in labels([str(tmp_path / "movie.tif"), flat]))
    # the montage dialog opens for a file that is not on the canvas
    seen = []
    monkeypatch.setattr(gui, "_stack_montage_dialog",
                        lambda sel, keep_crop_from=None: seen.append(sel.filename) or True)
    assert gui.montage_from_file(str(tmp_path / "movie.tif")) is True
    assert seen == [str(tmp_path / "movie.tif")]
    # a plain image: told so and added as one image
    n0 = len(_images(gui))
    assert gui.montage_from_file(flat) is False
    _wait_images(qapp, gui, n0 + 1)
    assert len(_images(gui)) == n0 + 1


def test_edit_image_and_magenta_green_split_need_a_selection(gui, monkeypatch, dialogs):
    panel = gui.paint.EZFIG_panel
    panel.set_current_selection(None)
    assert gui.edit_selected_image_action() is False
    assert gui._channel_split_selected(gray=False) is False
    opened = []
    monkeypatch.setattr(panel, "update_image_annotations", lambda image2d=None, tab=None: opened.append(image2d))
    first = _images(gui)[0]
    panel.set_current_selection(first)
    assert gui.edit_selected_image_action() is True and opened == [first]
