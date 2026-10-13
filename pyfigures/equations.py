"""Equation panels: LaTeX mathematics rendered as a vector SVG panel.

The equation is typeset by Matplotlib's mathtext (a LaTeX maths subset: no TeX
installation needed) and written as an SVG with the glyphs as outlines, so it
looks the same everywhere and stays vector in PDF/SVG exports. The SVG is an
ordinary file panel; its LaTeX source and settings are stored inside it (the
SVG description), so the equation can be edited again later.

Files go to an ``equations`` folder next to the figure (or to
~/.pyfigures/equations for a figure not saved yet), named from a hash of the
equation and its settings, so the same equation is written only once.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

FONTSETS = ("cm", "stix", "stixsans", "dejavusans", "dejavuserif")
_MARKER = "pyfigures-equation:"


def normalize(latex: str) -> str:
    """Wrap a bare formula in $...$ (mathtext only typesets maths between dollars)."""
    text = (latex or "").strip()
    if not text:
        raise ValueError("the equation is empty")
    if "$" not in text:
        text = f"${text}$"
    return text


def check(latex: str, fontset: str = "cm") -> None:
    """Raise ValueError with Matplotlib's message if *latex* cannot be typeset."""
    from matplotlib.mathtext import MathTextParser
    text = normalize(latex)
    if fontset not in FONTSETS:
        raise ValueError(f"fontset must be one of {', '.join(FONTSETS)}")
    parser = MathTextParser("path")
    import matplotlib
    with matplotlib.rc_context({"mathtext.fontset": fontset}):
        for i, part in enumerate(text.split("$")):
            if i % 2 == 1 and part.strip():
                try:
                    parser.parse(f"${part}$", dpi=72, prop=None)
                except ValueError as e:
                    raise ValueError(f"cannot typeset {part!r}: {str(e).strip()}") from None


def render_svg(latex: str, out_path: str, font_size: float = 12.0, color: str = "black",
               fontset: str = "cm") -> str:
    """Typeset *latex* to an SVG file at *out_path* (glyphs as outlines, tight box,
    transparent background). Returns *out_path*."""
    import matplotlib
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    from matplotlib.colors import to_hex
    from matplotlib.figure import Figure
    text = normalize(latex)
    check(text, fontset)
    if not (0 < float(font_size) <= 400):
        raise ValueError("font_size must be between 0 and 400 pt")
    try:
        to_hex(color)
    except ValueError:
        raise ValueError(f"unknown colour {color!r}") from None
    settings = {"latex": latex.strip(), "font_size": float(font_size), "color": color,
                "fontset": fontset}
    with matplotlib.rc_context({"svg.fonttype": "path", "mathtext.fontset": fontset,
                                "svg.hashsalt": "pyfigures"}):
        fig = Figure(figsize=(1, 1))
        FigureCanvasSVG(fig)
        fig.text(0, 0, text, fontsize=float(font_size), color=color)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        fig.savefig(out_path, format="svg", bbox_inches="tight", pad_inches=0.02,
                    transparent=True,
                    metadata={"Description": _MARKER + json.dumps(settings), "Date": None})
    return out_path


def read_settings(svg_path: str):
    """The settings stored in an equation SVG ({'latex', 'font_size', 'color',
    'fontset'}), or None if the file is not an equation panel."""
    try:
        with open(svg_path, encoding="utf-8") as f:
            head = f.read(4096)
    except (OSError, UnicodeDecodeError):
        return None
    m = re.search(re.escape(_MARKER) + r"(\{.*?\})\s*<", head, re.S)
    if not m:
        return None
    from html import unescape
    try:
        return json.loads(unescape(m.group(1)))
    except ValueError:
        return None


def is_equation(path) -> bool:
    return isinstance(path, str) and path.lower().endswith(".svg") and read_settings(path) is not None


def equation_dir(pyf_path: str | None) -> str:
    if pyf_path:
        return os.path.join(os.path.dirname(os.path.abspath(pyf_path)), "equations")
    return os.path.join(os.path.expanduser("~"), ".pyfigures", "equations")


def equation_path(pyf_path, latex, font_size=12.0, color="black", fontset="cm") -> str:
    key = json.dumps([latex.strip(), float(font_size), color, fontset])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return os.path.join(equation_dir(pyf_path), f"eq_{digest}.svg")


def make_equation(pyf_path, latex, font_size=12.0, color="black", fontset="cm") -> str:
    """Write the equation's SVG (if not already there) and return its path."""
    out = equation_path(pyf_path, latex, font_size, color, fontset)
    if not os.path.isfile(out):
        render_svg(latex, out, font_size, color, fontset)
    return out
