"""Full LaTeX support: $…$ maths typeset inside labels and poster text
(batoolset.drawings.math_text), equation panels from .tex files, and the
"latex" engine that uses the computer's LaTeX installation (skipped without
one).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import equations as E

needs_latex = pytest.mark.skipif(not E.latex_available(), reason="no LaTeX installation (latex + dvisvgm)")
LABEL = r"$\Delta F/F_0 = \frac{F-F_0}{F_0}$ at $t = 12\,\mathrm{min}$ costs \$5"


# ---------------------------------------------------------------------------
# $…$ in labels
# ---------------------------------------------------------------------------
def test_math_detection_and_typeset_copy(qapp):
    from qtpy.QtGui import QTextDocument
    from batoolset.drawings import math_text as MT
    assert MT.has_math(r"a $x^2$ b") and not MT.has_math(r"costs \$5 and \$6") and not MT.has_math("$ x$")
    doc = QTextDocument()
    doc.setPlainText(LABEL)
    out = MT.typeset(doc)
    assert out is not doc and doc.toPlainText() == LABEL                  # the original is untouched
    assert out.toPlainText().count("￼") == 2 and "costs $5" in out.toPlainText()
    plain = QTextDocument()
    plain.setPlainText("no maths here")
    assert MT.typeset(plain) is plain


def test_label_with_maths_draws_vector_formulas(qapp):
    from qtpy.QtGui import QImage, QPainter, QColor
    from batoolset.drawings.shapes.txt2d import TAText2D
    with_math = TAText2D(text=r"<span style='font-size:14pt'>$\frac{a}{b}$</span>")
    raw = TAText2D(text=r"<span style='font-size:14pt'>\frac{a}{b}</span>")
    assert with_math.getPlainText() == r"$\frac{a}{b}$"                   # saved/edited as typed
    # the fraction is narrower and taller than its source text
    assert with_math.getRect().width() < raw.getRect().width()
    assert with_math.getRect().height() > raw.getRect().height()
    img = QImage(200, 120, QImage.Format.Format_RGB32)
    img.fill(QColor("white"))
    p = QPainter(img)
    with_math.draw(p)
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(120, 200, 4)[..., :3]
    assert (a < 100).any()                                                  # something was drawn


def test_figure_export_with_math_label(qapp, tmp_path):
    import fitz
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, add_annotation, export_figure
    Image.fromarray(np.full((100, 150), 200, np.uint8)).save(tmp_path / "i.png")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], str(tmp_path / "i.png"))
    assert not add_annotation(pyf, [0], 0, LABEL, "top_left").startswith("ERROR")
    for ext in ("pdf", "svg", "png"):
        out = str(tmp_path / f"o.{ext}")
        json.loads(export_figure(pyf, out, dpi=150))
        if ext == "pdf":
            with fitz.open(out) as doc:
                text = doc[0].get_text()
                assert "costs $5" in text and "frac" not in text and "\\Delta" not in text
                assert len(doc[0].get_drawings()) >= 2                    # the 2 formulas, as paths
        if ext == "svg":
            svg = open(out, encoding="utf-8").read()
            assert "frac" not in svg and "costs $5" in svg


def test_poster_text_box_maths(qapp, tmp_path):
    import fitz
    from pyfigures.poster.poster_canvas import PosterCanvas
    canvas = PosterCanvas()
    box = canvas.add_text(x_mm=20, y_mm=20) if hasattr(canvas, "add_text") else None
    if box is None:
        pytest.skip("no add_text on this canvas")
    box.set_html(r"<span style='font-size:24pt'>Energy $E = mc^2$</span>")
    out = str(tmp_path / "p.pdf")
    canvas.save(out, filetype="pdf", dpi=100)
    with fitz.open(out) as doc:
        text = doc[0].get_text()
    assert "Energy" in text and "mc^2" not in text


# ---------------------------------------------------------------------------
# .tex files
# ---------------------------------------------------------------------------
TEX_DOC = r"""\documentclass{article}
\usepackage{amsmath}
% a comment
\begin{document}
\[ \nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0} \]
\end{document}
"""


def test_read_tex_file_and_mathtext_formula(tmp_path):
    p = tmp_path / "eq.tex"
    p.write_text(TEX_DOC, encoding="utf-8")
    body = E.read_tex_file(str(p))
    assert body.startswith(r"\[") and "comment" not in body and "documentclass" not in body
    assert E.mathtext_formula(body) == r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}"
    assert E.mathtext_formula(r"\begin{equation*} a = b \end{equation*}") == "a = b"
    (tmp_path / "empty.tex").write_text("% nothing\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no equation"):
        E.read_tex_file(str(tmp_path / "empty.tex"))


def test_tex_file_in_mcp_and_recipe_with_mathtext(qapp, tmp_path, monkeypatch):
    from pyfigures.mcp_server import create_figure, add_equation
    from pyfigures.recipe import build_figure_from_recipe
    monkeypatch.setattr(E, "latex_available", lambda: False)
    p = tmp_path / "eq.tex"
    p.write_text(TEX_DOC, encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    r = add_equation(pyf, [0], str(p))
    assert not r.startswith("ERROR"), r
    assert r"\nabla" in E.read_settings(r.rsplit("(file: ", 1)[1].rstrip(")"))["latex"]
    assert add_equation(pyf, [0], "x", engine="latex").startswith("ERROR: engine='latex' needs")
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": str(tmp_path / "r.pyf"),
                                  "rows": [[{"equation": "eq.tex"}]]}), encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert os.path.isfile(tmp_path / "r.pyf")


def test_gui_drop_tex_and_dialog(qapp, tmp_path, monkeypatch):
    from batoolset.lists.tools import flatten_iterable
    from pyfigures.gui.equation_dialog import EquationDialog
    from pyfigures.gui.pfgui import EZFIG_GUI
    p = tmp_path / "eq.tex"
    p.write_text(TEX_DOC, encoding="utf-8")
    dlg = EquationDialog()
    dlg.engine_check.setChecked(False)
    dlg.load_tex(str(p))
    assert dlg.values()["latex"] == r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}"
    assert dlg.engine_check.isEnabled() is E.latex_available()
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    try:
        g.current_file = str(tmp_path / "fig.pyf")
        eq = g._equation_from_tex(str(p))
        assert eq and E.is_equation(eq)
        g.add_images_to_new_row([eq])
        t0 = time.time()
        while time.time() - t0 < 20 and not g.paint.EZFIG_panel.shapes_to_draw:
            qapp.processEvents()
            time.sleep(0.01)
        imgs = [s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert len(imgs) == 1 and E.is_equation(imgs[0].filename)
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()


# ---------------------------------------------------------------------------
# the "latex" engine (real LaTeX)
# ---------------------------------------------------------------------------
@needs_latex
def test_latex_engine_environments_packages_and_errors(tmp_path):
    from qtpy.QtSvg import QSvgRenderer
    cases = {"aligned": r"\begin{aligned} D &= \SI{0.12}{\micro\metre\squared\per\second} \\ "
                        r"\bm{F} &= -\nabla U \end{aligned}",
             "align": r"\begin{align*} a &= b + c \\ x &= \frac{1}{2} \end{align*}",
             "cases": r"f(x) = \begin{cases} 1 & x > 0 \\ 0 & \text{otherwise} \end{cases}"}
    for name, tex in cases.items():
        out = E.render_svg(tex, str(tmp_path / f"{name}.svg"), 14, "#003399", engine="latex")
        s = E.read_settings(out)
        assert s["engine"] == "latex" and s["latex"] == tex and "siunitx" in s["preamble"]
        r = QSvgRenderer(out)
        size = r.defaultSize()
        assert r.isValid() and 20 < size.width() < 400 and 8 < size.height() < 100, (name, size)
        assert "<text" not in open(out, encoding="utf-8").read()
    with pytest.raises(ValueError, match="LaTeX could not typeset"):
        E.render_svg(r"\frac{1}{", str(tmp_path / "bad.svg"), engine="latex")
    a = E.equation_path(None, "x", engine="latex")
    assert a != E.equation_path(None, "x") and a != E.equation_path(None, "x", engine="latex",
                                                                     preamble=r"\usepackage{physics}")


@needs_latex
def test_latex_engine_in_mcp_recipe_and_export(qapp, tmp_path):
    import fitz
    from pyfigures.mcp_server import create_figure, add_equation, export_figure
    from pyfigures.recipe import build_figure_from_recipe
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    r = add_equation(pyf, [0], r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}", engine="latex",
                     preamble=r"\usepackage{amsmath}")
    assert not r.startswith("ERROR"), r
    out = str(tmp_path / "o.pdf")
    json.loads(export_figure(pyf, out))
    with fitz.open(out) as doc:
        assert not doc[0].get_images() and len(doc[0].get_drawings()) > 5     # vector glyphs
    p = tmp_path / "eq.tex"
    p.write_text(TEX_DOC, encoding="utf-8")
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": str(tmp_path / "r.pyf"),
                                  "rows": [[{"equation": "eq.tex", "engine": "latex", "font_size": 10}]]}),
                      encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    eqs = os.listdir(tmp_path / "equations")
    assert any(E.read_settings(str(tmp_path / "equations" / f)).get("engine") == "latex" for f in eqs)
