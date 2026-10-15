"""Names available to panel scripts (Image2D custom_loading_script), besides
plt, np and Img.

``latex(code, preamble=None)``: compile LaTeX code — a TikZ / pgfplots
picture, a table, maths, or a whole document — into a vector panel::

    rows = "\\\\ ".join(f"{k} & {v:.2f}" for k, v in results.items())
    self.img = latex(r"\\begin{tabular}{lr}\\toprule gene & fold \\\\ \\midrule "
                     + rows + r" \\\\ \\bottomrule\\end{tabular}")

A panel script that *is* LaTeX code (it starts with a backslash or a %
comment) is compiled the same way, without any Python.
"""
from __future__ import annotations


def latex(code, preamble=None):
    """Compile LaTeX *code* (pyfigures.latex_document.latex_code_pdf); returns
    the PDF to show (set it as ``self.img``)."""
    from pyfigures.latex_document import latex_code_pdf
    return latex_code_pdf(str(code), preamble)


HELPERS = {"latex": latex}
