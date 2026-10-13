"""Equation panels: LaTeX maths typeset by Matplotlib mathtext as a vector SVG
panel — module, MCP tool (add_equation), recipe (`equation:` panels) and GUI
(File > Add equation, right-click > Edit equation).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import equations as E

DFF = r"\Delta F/F_0 = \frac{F - F_0}{F_0}"


def test_normalize_and_check():
    assert E.normalize(r" \alpha ") == r"$\alpha$"
    assert E.normalize(r"rate $k_{on}$") == r"rate $k_{on}$"        # text + maths kept
    E.check(DFF)
    with pytest.raises(ValueError, match="cannot typeset"):
        E.check(r"\frac{a}{")
    with pytest.raises(ValueError, match="empty"):
        E.normalize("  ")
    with pytest.raises(ValueError, match="fontset"):
        E.check("x", fontset="comic")


def test_render_stores_its_settings_and_is_reused(tmp_path):
    pyf = str(tmp_path / "fig.pyf")
    p = E.make_equation(pyf, DFF, 14, "navy", "stix")
    assert os.path.dirname(p) == str(tmp_path / "equations")
    assert E.read_settings(p) == {"latex": DFF, "font_size": 14.0, "color": "navy", "fontset": "stix"}
    assert E.is_equation(p)
    mtime = os.path.getmtime(p)
    assert E.make_equation(pyf, DFF, 14, "navy", "stix") == p and os.path.getmtime(p) == mtime
    assert E.make_equation(pyf, DFF, 15, "navy", "stix") != p          # other settings: other file
    text = open(p, encoding="utf-8").read()
    assert "<text" not in text                                          # glyphs as outlines
    with pytest.raises(ValueError, match="colour"):
        E.render_svg("x", str(tmp_path / "c.svg"), color="notacolour")


def test_mcp_add_equation_and_vector_export(qapp, tmp_path):
    import fitz
    from pyfigures.mcp_server import create_figure, add_equation, export_figure, list_images
    pyf = str(tmp_path / "fig.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    r = add_equation(pyf, [0], DFF, font_size=12, label="A")
    assert not r.startswith("ERROR") and "equation $" in r
    assert add_equation(pyf, [0], r"\frac{").startswith("ERROR")
    listing = list_images(pyf)
    assert "eq_" in listing
    out = str(tmp_path / "out.pdf")
    json.loads(export_figure(pyf, out))
    with fitz.open(out) as doc:
        page = doc[0]
        assert not page.get_images() and len(page.get_drawings()) > 5


def test_recipe_equation_panel(qapp, tmp_path):
    from pyfigures.recipe import build_figure_from_recipe as build_from_recipe, RecipeError
    out = str(tmp_path / "eq.pyf")
    recipe = {"output": out, "rows": [[{"equation": DFF, "font_size": 10, "fontset": "cm",
                                        "label": "B"}]]}
    path = tmp_path / "r.json"
    path.write_text(json.dumps(recipe), encoding="utf-8")
    res = build_from_recipe(str(path))
    assert os.path.isfile(out)
    assert any(f.startswith("eq_") for f in os.listdir(tmp_path / "equations"))
    bad = dict(recipe, rows=[[{"equation": r"\frac{"}]])
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RecipeError, match="cannot typeset"):
        build_from_recipe(str(path))
    unknown = dict(recipe, rows=[[{"equation": "x", "size": 3}]])
    path.write_text(json.dumps(unknown), encoding="utf-8")
    with pytest.raises(RecipeError, match="unknown key"):
        build_from_recipe(str(path))


def test_dialog_preview_and_errors(qapp):
    from qtpy.QtWidgets import QDialogButtonBox
    from pyfigures.gui.equation_dialog import EquationDialog
    dlg = EquationDialog(latex=DFF, font_size=16, fontset="stix")
    ok = dlg.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert dlg.update_preview() and ok.isEnabled() and not dlg.preview.pixmap().isNull()
    dlg.latex_edit.setText(r"\frac{a}{")
    assert not dlg.update_preview() and not ok.isEnabled() and "cannot typeset" in dlg.error.text()
    dlg.latex_edit.setText("x^2")
    dlg.update_preview()
    assert dlg.values() == {"latex": "x^2", "font_size": 16.0, "color": "black", "fontset": "stix"}


def test_gui_add_and_edit_equation(qapp, tmp_path, monkeypatch):
    from qtpy.QtWidgets import QDialog
    from batoolset.lists.tools import flatten_iterable
    from pyfigures.gui import equation_dialog
    from pyfigures.gui.pfgui import EZFIG_GUI

    answers = [{"latex": DFF, "font_size": 12.0, "color": "black", "fontset": "cm"},
               {"latex": r"E = mc^2 + \sum_{i=1}^{n} \alpha_i", "font_size": 12.0,
                "color": "black", "fontset": "cm"}]

    class FakeDialog:
        def __init__(self, parent=None, **settings):
            FakeDialog.seen = settings

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return answers.pop(0)

    monkeypatch.setattr(equation_dialog, "EquationDialog", FakeDialog)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    try:
        g.current_file = str(tmp_path / "fig.pyf")
        g.add_equation_action()
        t0 = time.time()
        while time.time() - t0 < 20 and not g.paint.EZFIG_panel.shapes_to_draw:
            qapp.processEvents()
            time.sleep(0.01)
        imgs = [s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert len(imgs) == 1 and E.is_equation(imgs[0].filename)
        shape = imgs[0]
        first = shape.filename
        row = g.paint.EZFIG_panel.shapes_to_draw[0]
        row_width = row.getRect(all=True).width()
        aspect = shape.width() / shape.height()
        g.edit_equation(shape)
        assert FakeDialog.seen["latex"] == DFF                         # prefilled from the panel
        assert shape.filename != first and E.read_settings(shape.filename)["latex"].startswith("E = mc^2")
        # the new equation's own aspect ratio, in a row that keeps its width
        assert shape.width() / shape.height() != pytest.approx(aspect, rel=0.05)
        assert row.getRect(all=True).width() == pytest.approx(row_width, rel=0.02)
        assert g._dirty
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
