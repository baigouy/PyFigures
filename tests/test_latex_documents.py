"""LaTeX documents as panels (pyfigures.latex_document) and label maths typeset
by LaTeX itself (batoolset.latex_tools + math_text). The compiling tests need
a LaTeX installation and are skipped without one.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset import latex_tools as LT
from pyfigures import latex_document as LD

needs_pdflatex = pytest.mark.skipif(LT.find_tex_tool("pdflatex") is None, reason="no pdflatex")
needs_latex = pytest.mark.skipif(not LT.latex_available(), reason="no latex + dvisvgm")

DOC = r"""\documentclass[11pt]{article}
\usepackage{graphicx}
\usepackage{tikz}
\usepackage[margin=2cm]{geometry}
\newcommand{\decay}{x_0 e^{-t/\tau}}
\begin{document}
\section{Results}
Text that is not part of the panel.
\begin{figure}[ht]
  \centering
  \includegraphics[width=3cm]{img/cells.png}\hspace{1em}
  \begin{tikzpicture}
    \draw[->] (0,0) -- (3,0) node[right] {$t$};
    \draw[blue, thick, domain=0:2.8] plot (\x, {1.5*exp(-\x)});
  \end{tikzpicture}
  \caption{Decay $\decay$.}
  \label{fig:decay}
\end{figure}
\end{document}
"""


@pytest.fixture
def tex_doc(tmp_path):
    from PIL import Image
    (tmp_path / "img").mkdir()
    Image.fromarray((np.random.default_rng(0).random((60, 80)) * 255).astype(np.uint8)).save(
        tmp_path / "img" / "cells.png")
    p = tmp_path / "figure.tex"
    p.write_text(DOC, encoding="utf-8")
    return str(p)


def test_which_part_becomes_the_panel():
    assert LD.is_full_document(DOC) and not LD.is_full_document(r"\frac{a}{b}")
    assert not LD.is_full_document("% \\documentclass{article}\nx")
    # a document holding only maths stays an (editable) equation
    assert not LD.is_full_document("\\documentclass{article}\\begin{document}\n\\[ E = mc^2 \\]\n"
                                   "\\begin{align*} a &= b \\end{align*}\\end{document}")
    _, body = LD.split_document(DOC)
    part = LD.panel_content(body)
    assert "includegraphics" in part and "tikzpicture" in part
    assert "caption" not in part and "label" not in part and "Results" not in part
    assert LD.panel_content(r"a \begin{tikzpicture}\draw (0,0);\end{tikzpicture} b") \
        == r"\begin{tikzpicture}\draw (0,0);\end{tikzpicture}"
    assert LD.panel_content("just text") == "just text"


@needs_pdflatex
def test_document_compiles_to_a_cropped_vector_panel(qapp, tmp_path, tex_doc):
    import fitz
    from pyfigures.mcp_server import create_figure, add_image, export_figure
    pyf = str(tmp_path / "out" / "f.pyf")
    os.makedirs(os.path.dirname(pyf))
    create_figure(pyf, mode="groups", num_groups=1)
    r = add_image(pyf, [0], tex_doc, label="A")
    assert not r.startswith("ERROR"), r
    pdfs = os.listdir(tmp_path / "out" / "latex")
    pdf = [p for p in pdfs if p.endswith(".pdf")]
    assert len(pdf) == 1 and LD.source_of(str(tmp_path / "out" / "latex" / pdf[0])) == tex_doc
    with fitz.open(str(tmp_path / "out" / "latex" / pdf[0])) as doc:
        page = doc[0]
        assert page.rect.width < 300 and page.rect.height < 150         # cropped, not a page
        assert len(page.get_images()) == 1 and "Results" not in page.get_text()
    out = str(tmp_path / "out" / "f.pdf")
    json.loads(export_figure(pyf, out))
    with fitz.open(out) as doc:
        assert len(doc[0].get_drawings()) >= 2                        # the plot stays vector
    # a broken document reports LaTeX's error
    bad = tmp_path / "bad.tex"
    bad.write_text(DOC.replace(r"\end{tikzpicture}", ""), encoding="utf-8")
    assert add_image(pyf, [0], str(bad)).startswith("ERROR: LaTeX could not compile")


@needs_pdflatex
def test_document_in_recipe_and_gui(qapp, tmp_path, tex_doc, monkeypatch):
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures.gui.pfgui import EZFIG_GUI
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": str(tmp_path / "r.pyf"),
                                  "rows": [[{"image": "figure.tex"}]]}), encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert "latex" in open(tmp_path / "r.pyf", encoding="utf-8").read()
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.current_file = str(tmp_path / "g.pyf")
        panel = g._equation_from_tex(tex_doc)
        assert panel and panel.endswith(".pdf") and os.path.isfile(panel)
    finally:
        g._dirty = False
        g.close()


@needs_latex
def test_label_maths_typeset_by_latex_travels_with_the_figure(qapp, tmp_path, monkeypatch):
    from batoolset.drawings.shapes.txt2d import TAText2D
    monkeypatch.setattr(LT, "CACHE_DIRS", [str(tmp_path / "equations" / "labels")])
    monkeypatch.setattr(LT, "USED", set())
    monkeypatch.setattr(LT, "user_cache_dir", lambda: str(tmp_path / "user_cache"))
    monkeypatch.setenv("PYFIGURES_LABEL_MATH", "auto")
    html = r"<span style='font-size:12pt'>D = $\SI{0.12}{\micro\metre\squared\per\second}$</span>"
    label = TAText2D(text=html)
    w_latex = label.getRect().width()
    assert w_latex > 40                                      # siunitx: impossible for mathtext
    stored = os.listdir(tmp_path / "equations" / "labels")
    assert any(f.endswith(".svg") for f in stored) and LT.USED
    # a computer without TeX: the stored formula is used, same size
    monkeypatch.setattr(LT, "find_tex_tool", lambda name: None)
    assert TAText2D(text=html).getRect().width() == pytest.approx(w_latex)
    # forcing mathtext: \SI is unknown there (the formula is left out)
    monkeypatch.setenv("PYFIGURES_LABEL_MATH", "mathtext")
    assert TAText2D(text=html).getRect().width() < w_latex
    # saving copies the formulas used next to the saved figure
    dest = tmp_path / "elsewhere" / "fig.pyf"
    dest.parent.mkdir()
    LT.save_used(str(dest))
    assert sorted(os.listdir(tmp_path / "elsewhere" / "equations" / "labels")) == sorted(stored)
