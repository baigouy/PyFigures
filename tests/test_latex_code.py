"""LaTeX code panels: a panel whose script is LaTeX code (or a Python script
calling latex(...)), compiled to a vector PDF kept with the figure. The
compiling tests need pdflatex and are skipped without it.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset import latex_tools as LT
from pyfigures import latex_document as LD

needs_pdflatex = pytest.mark.skipif(LT.find_tex_tool("pdflatex") is None, reason="no pdflatex")

TIKZ = r"\begin{tikzpicture}\draw[red, thick] (0,0) circle (1) node {$\alpha$};\end{tikzpicture}"


@pytest.fixture
def caches(tmp_path, monkeypatch):
    fig_dir = tmp_path / "fig"
    fig_dir.mkdir()
    monkeypatch.setattr(LT, "CACHE_DIRS", [str(fig_dir / "equations" / "labels")])
    monkeypatch.setattr(LT, "FIGURE_DIR", [str(fig_dir)])
    monkeypatch.setattr(LT, "USED", set())
    monkeypatch.setattr(LT, "user_cache_dir", lambda: str(tmp_path / "user_cache"))
    return fig_dir


def test_latex_or_python_and_wrapping():
    assert LD.is_latex_code(TIKZ) and LD.is_latex_code("% a table\n\\begin{tabular}{c}x\\end{tabular}")
    assert not LD.is_latex_code("self.img = latex(r'x')") and not LD.is_latex_code(None)
    text, whole = LD.code_document(TIKZ, r"\usepackage{physics}")
    assert whole and "pgfplots" in text and "physics" in text and TIKZ in text
    doc = "\\documentclass{article}\\begin{document}x\\end{document}"
    assert LD.code_document(doc) == (doc, False)


@needs_pdflatex
def test_code_panel_compiles_caches_and_travels(qapp, caches, tmp_path, monkeypatch):
    from batoolset.drawings.shapes.image2d import Image2D
    a = Image2D(custom_loading_script=TIKZ)
    assert a.renderer is not None and a.filename is None and 40 < a.width() < 80
    stored = [f for f in os.listdir(caches / "equations" / "labels") if f.endswith(".pdf")]
    assert len(stored) == 1 and LT.USED
    # a Python script can build the code from data
    b = Image2D(custom_loading_script=(
        "rows = r' \\\\ '.join(f'{k} & {v}' for k, v in {'WT': 12, 'mutant': 9}.items())\n"
        "self.img = latex(r'\\begin{tabular}{lr}' + rows + r'\\end{tabular}')"))
    assert b.renderer is not None and b.width() > 20
    # broken code: the panel shows an error, LaTeX's message is in the log
    c = Image2D(custom_loading_script=r"\begin{tikzpicture}\draw (0,0) -- (1,1) \end{tikzpicture}")
    assert c.renderer is None and "LaTeX could not compile" in c.script_log
    # a computer without TeX uses the stored PDF
    monkeypatch.setattr(LT, "find_tex_tool", lambda name: None)
    import pyfigures.equations as E
    monkeypatch.setattr(E, "find_tex_tool", lambda name: None)
    assert Image2D(custom_loading_script=TIKZ).renderer is not None
    # saving copies the compiled code next to the saved figure
    dest = tmp_path / "elsewhere" / "f.pyf"
    dest.parent.mkdir()
    LT.save_used(str(dest))
    assert any(f.endswith(".pdf") for f in os.listdir(tmp_path / "elsewhere" / "equations" / "labels"))


@needs_pdflatex
def test_mcp_recipe_and_vector_export(qapp, tmp_path, monkeypatch):
    import fitz
    import pyfigures.mcp_server as M
    from pyfigures.recipe import build_figure_from_recipe
    monkeypatch.setattr(LT, "user_cache_dir", lambda: str(tmp_path / "user_cache"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    r = M.add_latex_code(pyf, [0], TIKZ, label="A")
    assert not r.startswith("ERROR"), r
    assert any(f.endswith(".pdf") for f in os.listdir(tmp_path / "equations" / "labels"))
    r = M.add_latex_code(pyf, [0], r"\begin{tikzpicture}\draw (0,0) -- (1,1) \end{tikzpicture}")
    assert r.startswith("ERROR") and "semicolon" in r
    r = M.add_latex_code(pyf, [0], r"$\dv{f}{x}$", preamble=r"\usepackage{physics}")
    assert not r.startswith("ERROR"), r
    out = str(tmp_path / "f.pdf")
    json.loads(M.export_figure(pyf, out))
    with fitz.open(out) as doc:
        assert len(doc[0].get_drawings()) >= 1                     # the circle stays vector
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": str(tmp_path / "r.pyf"),
                                  "rows": [[{"tex": TIKZ, "label": "B"}]]}), encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert "tikzpicture" in open(tmp_path / "r.pyf", encoding="utf-8").read()


@needs_pdflatex
def test_gui_add_edit_and_context_menu(qapp, tmp_path, caches, monkeypatch):
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui import latex_code_dialog as LCD
    from pyfigures.gui.pfgui import EZFIG_GUI
    codes = iter([TIKZ, TIKZ.replace("red", "blue")])

    def fake_exec(self):
        self.code_edit.setPlainText(next(codes))
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(LCD.LatexCodeDialog, "exec", fake_exec)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.current_file = str(caches / "g.pyf")
        shape = g.add_latex_code_action()
        assert shape is not None and shape.custom_loading_script == TIKZ
        assert shape in [s for grp in g.paint.EZFIG_panel.shapes_to_draw
                         for s in getattr(grp, "content", [grp])]
        assert g.edit_latex_code(shape) and "blue" in shape.custom_loading_script
        assert shape.renderer is not None and shape.filename is None
        # the dialog shows LaTeX's error and a preview
        d = LCD.LatexCodeDialog(None, r"\begin{tikzpicture}\draw (0,0) \end{tikzpicture}")
        assert d.update_preview() is False and "LaTeX could not compile" in d.error.text()
        d.code_edit.setPlainText(LCD.EXAMPLES["Table"])
        assert d.update_preview() is True and not d.preview.pixmap().isNull()
        # a preview bigger than its space scrolls (it was cut, no scrollbar)
        assert d.preview_scroll.widget() is d.preview
        d.deleteLater()
    finally:
        g._dirty = False
        g.close()
