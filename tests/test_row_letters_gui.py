"""Row letters: ONE panel letter per row, drawn OUTSIDE the row in a left
margin (as in many journal figures), instead of a letter inside each panel.

GUI (Annotations -> Panel letters: "One per row, outside on the left"),
recipe (letter_layout: row), MCP (set_panel_letter_layout) and the live chat
state all set / read the same figure setting; the canvas keeps the margin
free and draws the letters, so no export cuts them.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _recipe_figure(tmp_path, name="rows", layout="row", align=None, label_rows=False):
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe
    Image.fromarray(np.full((40, 60), 120, np.uint8)).save(tmp_path / "a.png")
    Image.fromarray(np.full((40, 60), 200, np.uint8)).save(tmp_path / "b.png")
    out = str(tmp_path / f"{name}.pyf")
    recipe = {"output": out, "rows": [["a.png", "a.png"], ["b.png", "b.png", "b.png"]]}
    if layout is not None:
        recipe["letter_layout"] = layout
    if align is not None:
        recipe["row_letter_align"] = align
    if label_rows:
        recipe["rows"][0] = {"panels": ["a.png", "a.png"], "labels": ["WT", "KO"]}
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    result = build_figure_from_recipe(str(path))
    return out, result


def _panel_letters(root):
    return [ta for ta in root.iter("TAText2D")
            if (ta.findtext("is_letter") or "") in ("True", "b'True'")]


def _settle(qapp, seconds=1.0):
    t0 = time.time()
    while time.time() - t0 < seconds:
        qapp.processEvents()
        time.sleep(0.02)


@pytest.fixture
def gui(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


def _open(gui, qapp, pyf):
    gui.reload_state(pyf, append=False)
    _settle(qapp)
    canvas = gui.paint.EZFIG_panel
    canvas.update()
    canvas.ensure_layout()
    return canvas


def _image_rows(canvas):
    return [s for s in canvas.shapes_to_draw if not getattr(s, "isText", False)]


def _gui_panel_letters(gui):
    from batoolset.drawings.shapes.txt2d import TAText2D
    _, images = gui.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(
        exclude_images_without_filename=False, include_insets=False)
    return [a.getPlainText() for im in images for a in (im.annotations or [])
            if isinstance(a, TAText2D) and a.is_letter]


# ---------------------------------------------------------------------------
# recipe + file-based MCP
# ---------------------------------------------------------------------------

def test_recipe_row_letters_saved_in_the_file(tmp_path):
    from pyfigures.mcp_server import describe_figure, get_figure_properties
    out, result = _recipe_figure(tmp_path)
    root = ET.parse(out).getroot()
    gui_el = root.find("SerializableGUIparameters")
    assert gui_el.findtext("letter_layout").strip('"') == "row"
    assert gui_el.findtext("row_letter_align").strip('"') == "top"
    assert _panel_letters(root) == []                 # the panels carry none
    assert result["lettered"] == 2                    # one per row
    assert "one per row" in describe_figure(out) and "A, B" in describe_figure(out)
    assert json.loads(get_figure_properties(out))["gui"]["letter_layout"] == "row"


def test_recipe_rejects_unknown_layout(tmp_path):
    from pyfigures.recipe import RecipeError
    with pytest.raises(RecipeError, match="letter_layout"):
        _recipe_figure(tmp_path, layout="diagonal")
    with pytest.raises(RecipeError, match="row_letter_align"):
        _recipe_figure(tmp_path, align="bottom")


def test_mcp_switch_back_to_panel_letters(tmp_path):
    from pyfigures.mcp_server import set_panel_letter_layout
    out, _ = _recipe_figure(tmp_path)
    msg = set_panel_letter_layout(out, "panel")
    assert "one in each panel" in msg
    root = ET.parse(out).getroot()
    assert root.find("SerializableGUIparameters").find("letter_layout") is None
    assert [ta.findtext("text") for ta in _panel_letters(root)]     # lettered again
    assert len(_panel_letters(root)) == 5
    msg = set_panel_letter_layout(out, "row", "center")
    assert "middle" in msg and "5 letter(s) removed" in msg
    assert set_panel_letter_layout(out, "sideways").startswith("ERROR")
    assert set_panel_letter_layout(out, "row", "left").startswith("ERROR")


def test_qc_counts_row_letters(tmp_path):
    from pyfigures.mcp_tools.qc import check_journal_compliance
    out, _ = _recipe_figure(tmp_path)
    report = check_journal_compliance(out, journal="nature", require_panel_labels=True)
    line = next(ln for ln in report.splitlines() if "panel labels" in ln)
    assert "[ok]" in line and "row letter" in line


# ---------------------------------------------------------------------------
# GUI: layout, margin, save/reopen, undo, row order
# ---------------------------------------------------------------------------

def test_gui_draws_one_letter_per_row_outside(gui, qapp, tmp_path):
    out, _ = _recipe_figure(tmp_path)
    canvas = _open(gui, qapp, out)
    assert canvas.letter_layout == "row" and gui.auto_lettering_checkbox.isChecked()
    assert _gui_panel_letters(gui) == []              # none inside the panels
    items = canvas.row_letter_items()
    assert [t.getPlainText() for t in items] == ["A", "B"]
    rows = _image_rows(canvas)
    margin = canvas.row_letter_margin()
    assert margin > 0
    for text, row in zip(items, rows):
        r = text.getRect(all=True)
        row_rect = row.getRect(all=True)
        assert r.right() < row_rect.left()            # left of its row, not over it
        assert r.left() >= canvas._EXTRA_PADDING - 0.5
        assert abs(r.top() - row_rect.top()) < r.height()   # level with the top of the row
    # the figure keeps its width: the rows gave up the letter margin
    bounds = canvas.updateBounds()
    assert abs(bounds.width() - rows[0].size) < 1.5
    assert bounds.left() <= min(t.getRect(all=True).left() for t in items) + 1e-6


def test_center_alignment(gui, qapp, tmp_path):
    out, _ = _recipe_figure(tmp_path, align="center")
    canvas = _open(gui, qapp, out)
    for text, row in zip(canvas.row_letter_items(), _image_rows(canvas)):
        assert abs(text.getRect(all=True).center().y() - row.getRect(all=True).center().y()) < 1


def test_letter_level_with_column_titles(gui, qapp, tmp_path):
    """Top alignment = the top of the row together with its label row above."""
    out, _ = _recipe_figure(tmp_path, label_rows=True)
    canvas = _open(gui, qapp, out)
    labels = [s for s in canvas.shapes_to_draw if getattr(s, "isText", False)]
    assert labels, "the recipe made no label row"
    first = canvas.row_letter_items()[0].getRect(all=True)
    assert abs(first.top() - labels[0].getRect(all=True).top()) < first.height()
    assert first.top() < _image_rows(canvas)[0].getRect(all=True).top()


def test_saved_reopened_and_undone(gui, qapp, tmp_path):
    out, _ = _recipe_figure(tmp_path)
    canvas = _open(gui, qapp, out)
    resaved = str(tmp_path / "resaved.pyf")
    gui._save_state_to_file(resaved)
    text = open(resaved, encoding="utf-8").read()
    assert "<letter_layout>" in text and "row" in text
    gui.set_letter_layout("panel", checkpoint=False)
    gui.reload_state(resaved, append=False)
    canvas.ensure_layout()
    assert canvas.letter_layout == "row"
    assert [t.getPlainText() for t in canvas.row_letter_items()] == ["A", "B"]

    # undo: back to row letters after switching to panel letters
    gui.save_state(show_popup=False)
    gui.set_letter_layout("panel")
    canvas.ensure_layout()
    assert canvas.letter_layout == "panel" and canvas.row_letter_items() == []
    assert sorted(_gui_panel_letters(gui)) == ["A", "B", "C", "D", "E"]
    gui.undo()
    canvas.update()
    canvas.ensure_layout()
    assert canvas.letter_layout == "row"
    assert _gui_panel_letters(gui) == []
    assert [t.getPlainText() for t in canvas.row_letter_items()] == ["A", "B"]


def test_figure_lettered_per_panel_saved_as_before(gui, qapp, tmp_path):
    out, _ = _recipe_figure(tmp_path, name="panel", layout=None)
    canvas = _open(gui, qapp, out)
    assert canvas.letter_layout == "panel" and canvas.row_letter_margin() == 0
    resaved = str(tmp_path / "resaved_panel.pyf")
    gui._save_state_to_file(resaved)
    assert "letter_layout" not in open(resaved, encoding="utf-8").read()


def test_letters_follow_row_order(gui, qapp, tmp_path):
    out, _ = _recipe_figure(tmp_path)
    canvas = _open(gui, qapp, out)
    first, second = _image_rows(canvas)
    # keyboard: the second row moved up
    canvas.set_current_selection(second)
    canvas.up_pressed()
    canvas.update()
    canvas.ensure_layout()
    assert _image_rows(canvas)[0] is second
    items = canvas.row_letter_items()
    assert [t.getPlainText() for t in items] == ["A", "B"]
    assert abs(items[0].getRect(all=True).top() - second.getRect(all=True).top()) < items[0].height()
    # GUI swap (drag-and-drop 'Swap'): the letters stay A, B from the top
    canvas.swap(second, first, None, second, first)
    canvas.update()
    canvas.ensure_layout()
    assert [t.getPlainText() for t in canvas.row_letter_items()] == ["A", "B"]


def test_chat_swap_rows_keeps_row_letters(qapp, tmp_path):
    from pyfigures.assistant.partner_gui import PartnerGUI, state
    PartnerGUI.show_tips = lambda self: None
    w = PartnerGUI()
    try:
        out, _ = _recipe_figure(tmp_path)
        w.reload_state(out, append=False)
        _settle(qapp)
        canvas = w.paint.EZFIG_panel
        canvas.update()
        canvas.ensure_layout()
        before = _image_rows(canvas)
        result = w.swap_rows(1, 2)
        assert result["lettering_mode"] == "row_letters" and result["row_letters"] == ["A", "B"]
        assert _image_rows(canvas) == before[::-1]
        st = state(w)
        assert st["letter_layout"] == "row" and [r["text"] for r in st["row_letters"]] == ["A", "B"]
        assert st["unlettered_panel_ids"] == []
        from pyfigures.assistant.figure_state import specification
        spec = specification(st)
        assert spec["letter_layout"] == "row" and spec["row_letters"] == ["A", "B"]
        # no "no letter" policy was left on the panels
        from pyfigures.assistant.partner_gui import panels, POLICY
        assert all(not json.loads(getattr(p, POLICY, "{}")) for _, _, p in panels(canvas.shapes_to_draw))
    finally:
        w._dirty = False
        w._stop_all_img_loaders()
        w.close()


def test_dialog_sets_row_layout(gui, qapp, tmp_path):
    from pyfigures.gui.autolettering_widget import AutoLetteringOptions
    w = AutoLetteringOptions(font=gui.serializable_font, letter_layout="row", row_letter_align="center")
    assert w.get_letter_layout() == "row" and w.get_row_letter_align() == "center"
    assert not w.vertical_combo.isEnabled() and w.row_align_combo.isEnabled()
    w.layout_combo.setCurrentIndex(w.layout_combo.findData("panel"))
    assert w.get_letter_layout() == "panel" and w.vertical_combo.isEnabled()
    assert not w.row_align_combo.isEnabled()

    # the window's dialog applies it (and turns lettering on)
    out, _ = _recipe_figure(tmp_path, name="panel2", layout=None)
    canvas = _open(gui, qapp, out)
    gui.auto_lettering_checkbox.setChecked(False)
    from batoolset.GUI import customdialog
    from qtpy.QtWidgets import QDialog
    real_exec = customdialog.CustomDialog.exec_

    def fake_exec(self):
        main = self.findChild(AutoLetteringOptions)
        main.layout_combo.setCurrentIndex(main.layout_combo.findData("row"))
        return QDialog.Accepted
    customdialog.CustomDialog.exec_ = fake_exec
    try:
        gui.change_lettering_parameters()
    finally:
        customdialog.CustomDialog.exec_ = real_exec
    canvas.ensure_layout()
    assert canvas.letter_layout == "row" and gui.auto_lettering_checkbox.isChecked()
    assert [t.getPlainText() for t in canvas.row_letter_items()] == ["A", "B"]
    assert _gui_panel_letters(gui) == []


# ---------------------------------------------------------------------------
# exports: the letter is outside the row and never cut
# ---------------------------------------------------------------------------

def _ink_columns(png):
    from PIL import Image
    a = np.asarray(Image.open(png).convert("RGBA")).astype(int)
    opaque = a[..., 3] > 128
    dark = opaque & (a[..., :3].max(axis=2) < 70)          # black letter ink
    grey = opaque & (np.abs(a[..., :3] - 120).max(axis=2) < 12)   # the first panel
    return dark, grey


def test_headless_png_export_shows_uncut_letters(tmp_path):
    from pyfigures.mcp_server import export_figure
    out, _ = _recipe_figure(tmp_path)
    png = str(tmp_path / "rows.png")
    r = export_figure(out, png, dpi=150)
    assert not r.startswith("ERROR"), r
    dark, grey = _ink_columns(png)
    assert dark.any(), "no letter drawn"
    panel_left = np.nonzero(grey.any(axis=0))[0].min()
    ink_cols = np.nonzero(dark.any(axis=0))[0]
    assert ink_cols.max() < panel_left                 # in the margin, left of the rows
    assert not dark[:, 0].any()                        # not cut by the left edge
    # two letters (A and B), one per row: two separate bands of ink rows, of
    # the same (cap) height — the first one is not cut by the top edge
    ink_rows = np.nonzero(dark.any(axis=1))[0]
    breaks = np.nonzero(np.diff(ink_rows) > 3)[0]
    assert len(breaks) == 1
    first = ink_rows[:breaks[0] + 1]
    second = ink_rows[breaks[0] + 1:]
    assert abs(len(first) - len(second)) <= 1
    # level with the top of its row (the figure starts with the row: no blank band)
    panel_top = np.nonzero(grey.any(axis=1))[0].min()
    assert abs(int(first[0]) - int(panel_top)) <= 2 and panel_top <= 2


def test_vector_and_editable_exports_carry_the_letters(gui, qapp, tmp_path):
    out, _ = _recipe_figure(tmp_path)
    canvas = _open(gui, qapp, out)
    svg = str(tmp_path / "rows.svg")
    canvas.save(svg)
    text = open(svg, encoding="utf-8").read()
    assert ">A<" in text and ">B<" in text
    pdf = str(tmp_path / "rows.pdf")
    canvas.save(pdf)
    assert os.path.getsize(pdf) > 0
    from pyfigures.gui.editable_export import capture_scene
    scene = capture_scene(canvas)
    texts = [it for it in scene["items"] if it.get("kind") == "text"]
    assert sorted(it["text"].strip() for it in texts) == ["A", "B"]
    assert min(it["x"] for it in texts) >= 0           # inside the page: not cut
    # left of the panels (the editable PowerPoint / Illustrator path)
    assert max(it["x"] for it in texts) < min(x for x, _, _, _ in scene["panels"])
