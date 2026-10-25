"""QC menu reports read by people: plain text naming panels by their letter
and file, with what to do in the GUI — not the JSON / MCP-server wording the
tools return (a user got a page of JSON from QC → Audit figure).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def fig(tmp_path):
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe
    d = str(tmp_path)
    for i in range(3):
        arr = (np.random.default_rng(i).random((60, 80)) * 255).astype(np.uint8)
        Image.fromarray(arr).save(os.path.join(d, f"im{i}.png"))
    with open(os.path.join(d, "counts.csv"), "w") as f:
        f.write("WT,KO\n10,20\n11,22\n12,21\n9,23\n")
    rp = os.path.join(d, "r.json")
    with open(rp, "w") as f:
        json.dump({"output": "fig.pyf", "rows": [[{"image": "im0.png"}, {"image": "im1.png"}],
                                                 [{"image": "im2.png"}, {"plot": "counts.csv", "kind": "box"}]]}, f)
    return build_figure_from_recipe(rp)["output"]


def _plain(text):
    assert "{" not in text and "group_path" not in text and "image_index" not in text, text


def test_audit_report_names_panels_and_says_what_to_do(fig):
    from pyfigures.mcp_server import audit_figure
    from pyfigures.gui.qc_reports import audit_report
    text = audit_report(audit_figure(fig))
    _plain(text)
    assert "3 micrographs have no scale bar: A (im0.png), B (im1.png), C (im2.png)" in text
    assert "Annotations → Add scale bar to all panels" in text
    assert "✓ Every panel has a letter or a text." in text


def test_resolution_and_compliance_name_panels_by_letter(fig):
    from pyfigures.mcp_server import check_journal_compliance, check_resolution
    from pyfigures.gui.qc_reports import humanize
    res = check_resolution(fig, journal="nature")
    assert "panel A (group 0, img 0)" in res              # the MCP server still gets the place
    text = humanize(res)
    assert "panel A (im0.png)" in text and "group 0" not in text
    comp = humanize(check_journal_compliance(fig, journal="nature"))
    assert "tell the user" not in comp and "describe_figure" not in comp
    assert "Verdict: NOT READY" in comp and "Fix them before submitting." in comp


def test_compliance_reports_the_height(fig):
    """The page height never showed in the GUI check: only journals with a
    maximum height had a height line, and the dialog had no field for it."""
    from pyfigures.mcp_server import check_journal_compliance
    from pyfigures.gui.qc_reports import humanize
    plain = check_journal_compliance(fig, width_mm=85)
    assert "[ok] height: figure" in plain and "no maximum height" in plain
    assert "max_height_mm" not in humanize(plain)
    tight = check_journal_compliance(fig, width_mm=85, max_height_mm=5)
    assert "[FAIL] height:" in tight and "the maximum height you gave" in tight
    assert "resize_figure" not in humanize(tight)
    assert check_journal_compliance(fig, width_mm=85, max_height_mm=-3).startswith("ERROR")


def test_journal_dialog_max_height(qapp):
    from pyfigures.gui.pfgui import _JournalDialog
    d = _JournalDialog()
    d.journal_combo.setCurrentText("nature")
    assert "247" in d.max_height_edit.placeholderText()
    assert "max_height_mm" not in d.values()
    d.max_height_edit.setText("200")
    assert d.values()["max_height_mm"] == 200.0
    d.max_height_edit.setText("tall")
    with pytest.raises(ValueError):
        d.values()


def test_integrity_report_is_plain_and_skips_plots(fig):
    from pyfigures.mcp_server import check_image_integrity
    from pyfigures.gui.qc_reports import integrity_report
    raw = check_image_integrity(fig)
    d = json.loads(raw)
    # the data plot has no image file: it used to be "file not found"
    assert d["load_errors"] == [] and d["panels_total"] == 3
    text = integrity_report(raw)
    _plain(text)
    assert "3 of 3 panels checked" in text


def test_integrity_report_lists_duplicates(fig, tmp_path):
    from pyfigures.gui.qc_reports import integrity_report
    raw = json.dumps({"summary": "1 exact file reuse.", "panels_analyzed": 2, "panels_total": 2,
                      "exact_file_duplicates": [{"a": 0, "b": 1, "a_label": "A", "b_label": "C",
                                                 "a_file": "x.png", "b_file": "x.png",
                                                 "reason": "same file path"}],
                      "cross_panel_duplicates": [], "within_panel_clones": [], "load_errors": []})
    text = integrity_report(raw)
    assert "The same file in two panels: A (x.png) and C (x.png)" in text


def test_ledger_and_fonts_reports_are_plain(fig):
    from pyfigures.mcp_server import export_adjustment_ledger
    from pyfigures.gui.qc_reports import fonts_report, ledger_report
    text = ledger_report(export_adjustment_ledger(fig))
    _plain(text)
    assert "A (im0.png): no adjustment" in text and "Methods (ready to paste):" in text
    assert "WT vs KO" in text
    fonts = fonts_report({"bundled_families": [], "fonts_dir": "f", "portable_clones_available": [],
                          "helvetica_resolves_to": "Helvetica", "arial_resolves_to": "Arial",
                          "has_true_helvetica": False, "has_arial": True})
    _plain(fonts)
    assert "no real Helvetica" in fonts


@pytest.fixture
def gui(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    g = EZFIG_GUI()
    g.resize(1400, 1000)
    yield g
    g._dirty = False
    g.close()


def test_qc_runs_with_a_busy_bar(gui):
    seen = []

    def slow(x):
        import time
        time.sleep(0.4)
        seen.append(gui._busy_dialog is not None)
        return x * 2
    assert gui._run_busy("Working…", slow, 21) == 42
    assert seen == [True] and gui._busy_dialog is None

    def boom():
        raise ValueError("bad figure")
    with pytest.raises(ValueError, match="bad figure"):
        gui._run_busy("Working…", boom)


def test_report_window_is_not_screen_sized(gui, monkeypatch):
    from batoolset.GUI import customdialog
    sizes = []
    monkeypatch.setattr(customdialog.CustomDialog, "exec_", lambda self: sizes.append(self.size()) or 1)
    gui._show_report("Figure audit", "line\n" * 5)
    # it opened at 85 % of the screen, bigger than the main window
    assert sizes and sizes[0].width() <= 720 and sizes[0].height() <= 520


def test_undo_redo_say_they_are_working(gui, monkeypatch):
    """A slow undo gave no sign it was accepted."""
    from qtpy.QtWidgets import QApplication
    seen = []
    gui.undo_stack = ["a.xml", "b.xml"]
    gui.current_index = 2
    gui.last_called_state = "c.xml"
    monkeypatch.setattr(gui, "reload_state", lambda *a, **k: seen.append(
        (gui.statusBar().currentMessage(), QApplication.overrideCursor() is not None)))
    gui.undo()
    assert seen == [("Undoing…", True)] and gui.statusBar().currentMessage() == "Undone."
    assert QApplication.overrideCursor() is None
    gui.last_called_state = "z.xml"
    gui.redo()
    assert seen[-1] == ("Redoing…", True) and gui.statusBar().currentMessage() == "Redone."
    gui._dirty = False


def test_menus_show_their_tooltips(gui):
    """The explanations of menu entries were written but never shown (Qt
    hides menu tooltips unless asked)."""
    stack = [a.menu() for a in gui.menuBar.actions() if a.menu() is not None]
    assert stack
    while stack:
        m = stack.pop()
        assert m.toolTipsVisible(), m.title()
        stack += [a.menu() for a in m.actions() if a.menu() is not None]


def test_file_import_menu(gui):
    file_menu = next(a.menu() for a in gui.menuBar.actions() if a.text() == "File")
    imp = next(a.menu() for a in file_menu.actions() if a.text() == "Import")
    texts = [a.text() for a in imp.actions()]
    assert "Images from files" in texts and any("OME-Zarr" in t for t in texts) \
        and any("CSV" in t for t in texts)


def test_vector_pdf_entry_shows_its_state(gui, monkeypatch):
    import pyfigures.extras as extras
    monkeypatch.setattr(extras, "has_pymupdf", lambda: True)
    gui._update_vector_pdf_action()
    assert gui.pdf_vector_action.isChecked() and gui.pdf_vector_action.toolTip().startswith("Installed")
    monkeypatch.setattr(extras, "has_pymupdf", lambda: False)
    gui._update_vector_pdf_action()
    assert not gui.pdf_vector_action.isChecked() and "Not installed" in gui.pdf_vector_action.toolTip()


def test_remove_menu_says_its_scope(gui, tmp_path):
    """Annotations → Remove works on the selection, or on every panel when
    nothing is selected: the menu now says which."""
    from batoolset.drawings.shapes.image2d import Image2D
    panel = gui.paint.EZFIG_panel
    panel.selected_shape = None
    assert "every panel" in gui._update_remove_scope()
    img = Image2D(width=30, height=20)
    panel.selected_shape = img
    assert "selected panel only" in gui._update_remove_scope()
    panel.selected_shape = None


def test_menu_bar_right_click_entries_have_names(gui):
    """Right-clicking the menu bar showed an entry without text (it hid the
    toolbar)."""
    menu = gui.createPopupMenu()
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts and all(t.strip() for t in texts), texts
    assert "Show the toolbar" in texts


def test_scale_consistency_note_in_gui_words():
    from pyfigures.gui.qc_reports import humanize
    t = humanize("No panel has a pixel size set. Set px_to_unit via set_scale_bar or configure_image.\n"
                 "  - panel B (group 1, img 0)\n  - canvas img 2")
    assert "set_scale_bar" not in t and "panel B" in t and "loose panel 3" in t
