"""LaTeX extras: maths in the figure's own font (XeLaTeX), choosing which
figure/table of a .tex document becomes the panel, recompiling document panels
when their .tex changes, data plots typeset by LaTeX, and label maths in the
editable PowerPoint / Illustrator exports. The compiling tests need a LaTeX
installation and are skipped without one.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time
import zipfile

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset import latex_tools as LT
from pyfigures import latex_document as LD
from pyfigures import office_math as OM

needs_pdflatex = pytest.mark.skipif(LT.find_tex_tool("pdflatex") is None, reason="no pdflatex")
needs_xelatex = pytest.mark.skipif(not LT.xelatex_available(), reason="no xelatex + dvisvgm")
needs_latex = pytest.mark.skipif(not LT.latex_available(), reason="no latex + dvisvgm")
ARIAL = LT.font_files_for("Arial")
needs_arial = pytest.mark.skipif(ARIAL is None, reason="Arial not installed")

DOC = r"""\documentclass{article}
\usepackage{tikz}
\begin{document}
Intro text.
\begin{figure}
  \centering
  \begin{tikzpicture}\draw[red] (0,0) rectangle (1,1);\end{tikzpicture}
  \caption{A red square.}
  \label{fig:red}
\end{figure}
\begin{table}
  \centering
  \begin{tabular}{cc} a & b \\ 1 & 2 \end{tabular}
  \caption{Numbers}
\end{table}
\begin{figure}
  \centering
  \begin{tikzpicture}\draw[blue] (0,0) circle (1);\end{tikzpicture}
\end{figure}
\end{document}
"""


@pytest.fixture
def three_parts(tmp_path):
    p = tmp_path / "doc.tex"
    p.write_text(DOC, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# 1. maths in the figure's font
# ---------------------------------------------------------------------------
@needs_arial
def test_font_preamble_takes_letters_digits_and_greek_from_the_font():
    assert len(ARIAL) == 4 and all(os.path.isfile(f) for f in ARIAL)
    pre = "\n".join(LT.font_preamble(ARIAL))
    assert "fontspec" in pre and "unicode-math" in pre and "latinmodern-math.otf" in pre
    assert "range=" in pre and os.path.basename(ARIAL[0]) in pre
    assert LT.font_files_for("No Such Font 123") is None


@needs_xelatex
@needs_arial
def test_label_maths_in_the_label_font(tmp_path, monkeypatch):
    monkeypatch.setattr(LT, "CACHE_DIRS", [str(tmp_path / "labels")])
    monkeypatch.setattr(LT, "user_cache_dir", lambda: str(tmp_path / "user"))
    plain = LT.inline_math_svg(r"\alpha v = 12", 12, sans=True)
    arial = LT.inline_math_svg(r"\alpha v = 12", 12, sans=True, font_files=ARIAL)
    assert plain and arial and plain[0] != arial[0]                 # its own cache entry
    assert arial[1] > 10 and arial[2] > 4 and arial[3] >= 0        # width, height, depth (pt)


@needs_xelatex
@needs_arial
def test_equation_panel_in_a_font(tmp_path):
    from pyfigures import equations as E
    from pyfigures.mcp_server import create_figure, add_equation
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    a = E.make_equation(pyf, r"F = m a", engine="latex")
    b = E.make_equation(pyf, r"F = m a", engine="latex", font="Arial")
    assert a != b and os.path.isfile(b) and E.read_settings(b)["font"] == "Arial"
    r = add_equation(pyf, [0], r"\Delta F / F_0", engine="latex", font="Arial")
    assert not r.startswith("ERROR"), r
    r = add_equation(pyf, [0], r"x", engine="latex", font="No Such Font 123")
    assert r.startswith("ERROR") and "not found" in r


def test_equation_dialog_font_option(qapp):
    from pyfigures.gui.equation_dialog import EquationDialog
    d = EquationDialog()
    assert d.values()["font"] is None                               # default: Latin Modern
    d.latex_font_combo.setEditText("Arial")
    if d.latex_font_combo.isEnabled():
        assert d.values()["font"] == "Arial"
    d.deleteLater()


# ---------------------------------------------------------------------------
# 2-3. which part of a document; recompiling
# ---------------------------------------------------------------------------
def test_candidate_parts_of_a_document():
    _, body = LD.split_document(DOC)
    parts = LD.candidate_parts(body)
    assert [d for d, _ in parts] == ["Figure 1: A red square.", "Table 1: Numbers", "Figure 2"]
    assert "red" in LD.panel_content(body) and "tabular" in LD.panel_content(body, 2)
    assert "blue" in LD.panel_content(body, 3) and "caption" not in LD.panel_content(body, 2)
    with pytest.raises(ValueError):
        LD.panel_content(body, 4)
    tikz_only = r"a \begin{tikzpicture}x\end{tikzpicture} \begin{tikzpicture}y\end{tikzpicture}"
    assert [d for d, _ in LD.candidate_parts(tikz_only)] == ["TikZ picture 1", "TikZ picture 2"]


@needs_pdflatex
def test_document_part_mcp_recipe_and_update(qapp, tmp_path, three_parts):
    import fitz
    from pyfigures.mcp_server import create_figure, add_image, update_latex_panels
    from pyfigures.recipe import build_figure_from_recipe
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    assert not add_image(pyf, [0], three_parts, page=2).startswith("ERROR")
    assert add_image(pyf, [0], three_parts, page=9).startswith("ERROR")
    pdf = LD.document_pdf_path(pyf, three_parts, 2)
    assert os.path.isfile(pdf) and LD.part_of(pdf) == 2 and LD.source_of(pdf) == three_parts
    with fitz.open(pdf) as doc:
        assert "1" in doc[0].get_text() and "Intro" not in doc[0].get_text()

    # nothing changed: nothing recompiled; the .tex changes: the panel follows
    assert json.loads(update_latex_panels(pyf))["updated"] == []
    time.sleep(0.05)
    with open(three_parts, "w", encoding="utf-8") as f:
        f.write(DOC.replace("1 & 2", "7 & 8"))
    os.utime(three_parts, (time.time() + 5, time.time() + 5))
    res = json.loads(update_latex_panels(pyf))
    assert len(res["updated"]) == 1 and not res["failed"]
    new = res["updated"][0]["panel"]
    assert new != pdf and LD.part_of(new) == 2 and new in open(pyf, encoding="utf-8").read()
    with fitz.open(new) as doc:
        assert "7" in doc[0].get_text()
    assert len(json.loads(update_latex_panels(pyf, force=True))["updated"]) == 1

    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": str(tmp_path / "r.pyf"),
                                  "rows": [[{"image": "doc.tex", "page": 3}]]}), encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert os.path.isfile(LD.document_pdf_path(str(tmp_path / "r.pyf"), three_parts, 3))


@needs_pdflatex
def test_gui_part_picker_and_recompile(qapp, tmp_path, three_parts, monkeypatch):
    from qtpy.QtWidgets import QInputDialog, QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    asked = []

    def pick(parent, title, label, items, *a, **k):
        asked.append(list(items))
        return items[1], True
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(pick))
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.current_file = str(tmp_path / "g.pyf")
        panel = g._equation_from_tex(three_parts)
        assert asked and len(asked[0]) == 3 and asked[0][1].startswith("Table 1")
        assert LD.part_of(panel) == 2

        class Shape:
            filename = panel
        replaced = []
        monkeypatch.setattr(g, "_replace_panel_file", lambda shape, path: replaced.append(path))
        assert g.recompile_latex_panel(Shape())
        assert replaced and LD.part_of(replaced[0]) == 2 and os.path.isfile(replaced[0])

        # a changed .tex is offered for recompiling
        os.utime(three_parts, (time.time() + 5, time.time() + 5))
        monkeypatch.setattr(g, "_stale_latex_panels", lambda: [Shape()])
        replaced.clear()
        g._offer_to_recompile_latex_panels()
        assert len(replaced) == 1
        Shape.filename = str(tmp_path / "gone.pdf")
        assert g.recompile_latex_panel(Shape(), quiet=True) is False
    finally:
        g._dirty = False
        g.close()


# ---------------------------------------------------------------------------
# 4. data plots typeset by LaTeX
# ---------------------------------------------------------------------------
def test_data_plot_script_carries_latex_settings(tmp_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pytest.importorskip("staplot")
    from types import SimpleNamespace
    from pyfigures.mcp_tools.content import _make_data_plot_script
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,4\n2,5\n3,6\n", encoding="utf-8")
    script = _make_data_plot_script(str(csv), "bar", "sem", False, True, "", "$D$", "", latex=True)
    me = SimpleNamespace()
    exec(script, {"plt": plt}, {"self": me, "plt": plt})
    rc = me.img._pyf_rc
    if LT.latex_available():
        assert rc["text.usetex"] is True and "siunitx" in rc["text.latex.preamble"]
        assert "upmu" in rc["text.latex.preamble"]          # µ not from (tiny) textcomp
        # the figure font is not forced on LaTeX text (usetex would fall back to serif)
        from batoolset.drawings.shapes.image2d import Image2D
        shape = SimpleNamespace(img=me.img, publication_font="Arial")
        assert Image2D._publication_family(shape) is None
    plain = SimpleNamespace()
    exec(_make_data_plot_script(str(csv), "bar", "sem", False, True, "", "", ""), {"plt": plt},
         {"self": plain, "plt": plt})
    assert plain.img._pyf_rc == {}
    from batoolset.drawings.shapes.image2d import Image2D
    assert Image2D._publication_family(SimpleNamespace(img=plain.img, publication_font="Arial")) == "Arial"
    plt.close("all")


@needs_latex
def test_data_plot_latex_mcp_recipe_and_export(qapp, tmp_path):
    pytest.importorskip("staplot")
    from pyfigures.mcp_server import create_figure, add_data_plot, export_figure
    from pyfigures.recipe import build_figure_from_recipe
    csv = tmp_path / "d.csv"
    csv.write_text("WT,KO\n1,4\n2,5\n3,6\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    r = add_data_plot(pyf, [0], str(csv), annotate_stats=False, latex=True,
                      ylabel=r"$D$ (\si{\micro\metre\squared\per\second})")
    assert not r.startswith("ERROR"), r
    out = str(tmp_path / "f.png")
    json.loads(export_figure(pyf, out))
    assert os.path.getsize(out) > 1000
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": str(tmp_path / "r.pyf"),
                                  "rows": [[{"plot": "d.csv", "latex": True,
                                             "annotate_stats": False}]]}), encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert "matplotlib_rc" in open(tmp_path / "r.pyf", encoding="utf-8").read()


def test_data_plot_dialog_latex_checkbox(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QCheckBox, QDialog
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,4\n2,5\n", encoding="utf-8")
    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [str(csv)]))

    class _OK:
        def __init__(self, *a, main_widget=None, **k):
            for cb in main_widget.findChildren(QCheckBox):
                if "LaTeX" in cb.text():
                    cb.setEnabled(True)
                    cb.setChecked(True)

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _OK)
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    calls = []
    monkeypatch.setattr(g, "_run_mcp_mutation", lambda fn, msg, **kw: calls.append(kw))
    try:
        g.add_data_plot_action()
        assert calls and calls[0]["latex"] is True
    finally:
        g._dirty = False
        g.close()


# ---------------------------------------------------------------------------
# 5. label maths in PowerPoint / Illustrator
# ---------------------------------------------------------------------------
def test_office_math_conversions():
    assert OM.latex_to_unicode(r"\alpha^2 + \beta_i") == "α² + βᵢ"
    assert OM.latex_to_unicode(r"\SI{5}{\micro\metre}") == "5 μm"
    assert OM.latex_to_unicode(r"\SI{3}{\metre\per\second\squared}") == "3 m/s²"
    assert OM.expand_siunitx(r"\si{\milli\molar}") == r"\mathrm{mM}"
    omml = OM.latex_to_omml(r"\frac{\Delta F}{F_0}")
    assert omml.startswith("<m:oMath") and "<m:f>" in omml and OM.OMML_NS in omml


def _marker(tex, width=20.0):
    return "PYFMATH:%.3f:%s" % (width, tex.encode("utf-8").hex())


def test_math_runs_join_the_label_text():
    from pyfigures.gui import editable_export as E
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
           '<g font-family="Arial" font-size="10" fill="#ff0000">'
           '<text x="10" y="20">k = </text>'
           '<text x="30" y="20">%s</text>'
           '<text x="50" y="20"> ok</text>'
           '<text x="10" y="80">far away</text></g></svg>') % _marker(r"\alpha^2")
    scene = E.parse_svg(svg.encode())
    texts = [it for it in scene["items"] if it["kind"] == "text"]
    assert len(texts) == 2
    joined = texts[0]
    assert [r.get("math") for r in joined["runs"]] == [None, r"\alpha^2", None]
    assert joined["text"] == "k = α² ok" and texts[1]["text"] == "far away"
    assert joined["runs"][1]["width"] == pytest.approx(20.0)


def test_pptx_native_equation_and_jsx_unicode(tmp_path):
    pytest.importorskip("pptx")
    from pyfigures.gui import editable_export as E
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100">'
           '<g font-family="Arial" font-size="10"><text x="10" y="20">D = </text>'
           '<text x="30" y="20">%s</text></g></svg>') % _marker(r"\SI{2}{\micro\metre}")
    scene = E.parse_svg(svg.encode())
    out = E.write_pptx(scene, str(tmp_path / "m.pptx"))
    with zipfile.ZipFile(out) as z:
        xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "a14:m" in xml and "m:oMath" in xml and "Cambria Math" in xml and 'sz="1000"' in xml
    assert "D = " in xml and "2 μm" in xml                   # text run + fallback
    from pptx import Presentation
    Presentation(out)                                          # still a valid file
    jsx, _ = E.write_jsx(scene, str(tmp_path / "m.jsx"))
    assert '"D = 2 μm"' in open(jsx, encoding="utf-8-sig").read()


def test_figure_label_maths_reach_powerpoint_as_equations(qapp, tmp_path):
    pytest.importorskip("pptx")
    import tifffile
    import pyfigures.mcp_server as M
    from batoolset.drawings import math_text
    tif = str(tmp_path / "a.tif")
    tifffile.imwrite(tif, np.tile(np.linspace(0, 255, 120).astype(np.uint8), (80, 1)))
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X")
    M.add_image(pyf, [0], tif)
    M.add_annotation(pyf, [0], 0, r"k = $\alpha^2$ ok", placement="top left")
    res = json.loads(M.export_pptx(pyf, str(tmp_path / "o.pptx")))
    assert res["texts"] == 1 and res["shapes"] == 0          # no glyph outlines left
    assert math_text.SOURCE_MARKERS is False                  # reset after the capture
    with zipfile.ZipFile(res["path"]) as z:
        xml = z.read("ppt/slides/slide1.xml").decode("utf-8")
    assert "m:oMath" in xml and "PYFMATH" not in xml
    jres = json.loads(M.export_illustrator_script(pyf, str(tmp_path / "o.jsx")))
    assert "k = α² ok" in open(jres["path"], encoding="utf-8-sig").read()
