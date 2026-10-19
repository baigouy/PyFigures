"""LaTeX documents as panels: what the 2026-10-19 stress run found. The
compiling tests need pdflatex and are skipped without it."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset import latex_tools as LT
from pyfigures import latex_document as LD

needs_pdflatex = pytest.mark.skipif(LT.find_tex_tool("pdflatex") is None, reason="no pdflatex")


def _png(path):
    from PIL import Image
    Image.new("RGB", (40, 30), (200, 30, 30)).save(path)


def test_a_commented_out_figure_is_not_a_part():
    body = ("% \\begin{figure}\\includegraphics{old.png}\\end{figure}\n"
            "\\begin{figure}\\includegraphics{new.png}\\end{figure}\n"
            "100\\% sure")
    parts = LD.candidate_parts(body)
    assert len(parts) == 1 and "new.png" in parts[0][1] and "old.png" not in parts[0][1]


def test_subfigures_keep_their_float_type():
    body = ("\\begin{figure}\\begin{subfigure}{0.4\\linewidth}x\\caption{a}\\end{subfigure}"
            "\\caption{Both}\\end{figure}")
    content = LD.panel_content(body)
    assert content.startswith("\\makeatletter\\def\\@captype{figure}\\makeatother")
    assert "Both" not in content


@needs_pdflatex
def test_documents_with_subfigures_and_comments_compile(tmp_path):
    _png(tmp_path / "plain.png")
    sub = tmp_path / "sub.tex"
    sub.write_text("\\documentclass{article}\\usepackage{graphicx}\\usepackage{subcaption}\n"
                   "\\begin{document}\\begin{figure}"
                   "\\begin{subfigure}{0.4\\linewidth}\\includegraphics[width=\\linewidth]{plain.png}"
                   "\\caption{left}\\end{subfigure}\\caption{Both}\\end{figure}\\end{document}\n",
                   encoding="utf-8")
    assert os.path.getsize(LD.compile_document(str(sub), str(tmp_path / "sub.pdf"))) > 0
    com = tmp_path / "com.tex"
    com.write_text("\\documentclass{article}\\usepackage{graphicx}\n\\begin{document}\n"
                   "% \\begin{figure}\\includegraphics{nope.png}\\end{figure}\n"
                   "\\begin{figure}\\includegraphics[width=2cm]{plain.png}\\end{figure}\n"
                   "\\end{document}\n", encoding="utf-8")
    assert os.path.getsize(LD.compile_document(str(com), str(tmp_path / "com.pdf"))) > 0


@needs_pdflatex
def test_part_zero_is_refused_even_when_part_one_is_compiled(tmp_path):
    from pyfigures import mcp_server as M
    _png(tmp_path / "plain.png")
    tex = tmp_path / "two.tex"
    tex.write_text("\\documentclass{article}\\usepackage{graphicx}\n\\begin{document}\n"
                   "\\begin{figure}\\includegraphics[width=2cm]{plain.png}\\end{figure}\n"
                   "\\begin{figure}\\includegraphics[width=3cm]{plain.png}\\end{figure}\n"
                   "\\end{document}\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    assert M.add_image(pyf, [0], str(tex)).startswith("Added")
    for part in (0, 3, -1):
        res = M.add_image(pyf, [0], str(tex), page=part)
        assert res.startswith("ERROR") and "between 1 and 2" in res, res
    assert M.add_image(pyf, [0], str(tex), page=2).startswith("Added")
