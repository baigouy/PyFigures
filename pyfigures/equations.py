"""Equation panels: LaTeX mathematics rendered as a vector SVG panel.

Two engines:

- ``"mathtext"`` (default): Matplotlib's mathtext, a LaTeX maths subset; no
  TeX installation needed.
- ``"latex"``: the computer's LaTeX installation (TeX Live, MiKTeX, MacTeX),
  so full LaTeX: any environment (align, cases...), any package (siunitx,
  physics, bm...) given in the preamble. Compiled with ``latex`` and converted
  by ``dvisvgm``.

Either way the result is an SVG with the glyphs as outlines, so it looks the
same everywhere (a figure with LaTeX equations opens on a computer without
TeX) and stays vector in PDF/SVG exports. The SVG is an ordinary file panel;
its LaTeX source and settings are stored inside it (the SVG description), so
the equation can be edited again later.

Files go to an ``equations`` folder next to the figure (or to
~/.pyfigures/equations for a figure not saved yet), named from a hash of the
equation and its settings, so the same equation is written only once.
"""
from __future__ import annotations

import glob
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

FONTSETS = ("cm", "stix", "stixsans", "dejavusans", "dejavuserif")
ENGINES = ("mathtext", "latex")
DEFAULT_PREAMBLE = r"\usepackage{amsmath,amssymb,bm,siunitx}"
_MARKER = "pyfigures-equation:"


# ---------------------------------------------------------------------------
# the LaTeX installation
# ---------------------------------------------------------------------------
def _tex_bin_dirs():
    """Folders where TeX distributions put latex/dvisvgm when not on the PATH."""
    dirs = []
    if os.environ.get("PYFIGURES_TEX_BIN"):
        dirs.append(os.environ["PYFIGURES_TEX_BIN"])
    if sys.platform.startswith("win"):
        for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("ProgramFiles")):
            if base:
                dirs.append(os.path.join(base, "Programs", "MiKTeX", "miktex", "bin", "x64"))
                dirs.append(os.path.join(base, "MiKTeX", "miktex", "bin", "x64"))
        dirs += sorted(glob.glob(r"C:\texlive\*\bin\win*"), reverse=True)
    else:
        dirs += ["/Library/TeX/texbin", "/usr/local/texlive/bin", "/usr/bin", "/usr/local/bin"]
        dirs += sorted(glob.glob("/usr/local/texlive/*/bin/*"), reverse=True)
    return dirs


def find_tex_tool(name):
    """Full path of a TeX program (latex, dvisvgm), or None."""
    found = shutil.which(name)
    if found:
        return found
    exe = name + (".exe" if sys.platform.startswith("win") else "")
    for d in _tex_bin_dirs():
        p = os.path.join(d, exe)
        if os.path.isfile(p):
            return p
    return None


def latex_available() -> bool:
    """True if the "latex" engine can be used (latex and dvisvgm found)."""
    return find_tex_tool("latex") is not None and find_tex_tool("dvisvgm") is not None


# environments that start a paragraph-level block (used as written); any other
# (aligned, cases, pmatrix, split...) is mathematics and is put in display maths
_TEXT_LEVEL_ENVS = {"equation", "align", "gather", "multline", "flalign", "alignat", "displaymath",
                    "eqnarray", "math", "tikzpicture", "tabular", "itemize", "enumerate",
                    "center", "minipage", "picture"}


def _latex_body(latex):
    """The document body for *latex*: a bare formula (including math-only
    environments such as aligned or cases) is set in display style; text with
    $…$, \\[…\\], \\(…\\) or block environments (align, equation…) is used as
    written."""
    text = latex.strip()
    if "$" in text or "\\[" in text or "\\(" in text:
        return text
    envs = {e.rstrip("*") for e in re.findall(r"\\begin\{([^}]+)\}", text)}
    if envs & _TEXT_LEVEL_ENVS:
        return text
    return f"$\\displaystyle {text}$"


def _render_svg_latex(latex, out_path, font_size, color, preamble):
    from matplotlib.colors import to_hex
    tex = find_tex_tool("latex")
    dvisvgm = find_tex_tool("dvisvgm")
    if tex is None or dvisvgm is None:
        raise ValueError("the LaTeX engine needs a LaTeX installation with latex and dvisvgm "
                         "(TeX Live, MiKTeX or MacTeX)")
    rgb = to_hex(color)[1:].upper()
    size = float(font_size)
    doc = "\n".join([
        r"\documentclass[varwidth=\maxdimen,border=0.5pt]{standalone}",
        r"\usepackage{lmodern}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{xcolor}",
        preamble or "",
        r"\begin{document}",
        f"\\fontsize{{{size:g}}}{{{size * 1.2:g}}}\\selectfont\\color[HTML]{{{rgb}}}%",
        _latex_body(latex),
        r"\end{document}",
        ""])
    work = tempfile.mkdtemp(prefix="pyf_eq_")
    try:
        with open(os.path.join(work, "eq.tex"), "w", encoding="utf-8") as f:
            f.write(doc)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run([tex, "-interaction=nonstopmode", "-halt-on-error", "eq.tex"],
                           cwd=work, capture_output=True, text=True, timeout=300,
                           creationflags=flags)
        dvi = os.path.join(work, "eq.dvi")
        if r.returncode != 0 or not os.path.isfile(dvi):
            log = ""
            if os.path.isfile(os.path.join(work, "eq.log")):
                with open(os.path.join(work, "eq.log"), encoding="utf-8", errors="replace") as f:
                    log = f.read()
            errors = [ln[1:].strip() for ln in log.splitlines() if ln.startswith("!")]
            detail = "; ".join(errors[:3]) or (r.stdout or r.stderr or "").strip()[-300:]
            raise ValueError(f"LaTeX could not typeset the equation: {detail}")
        svg = os.path.join(work, "eq.svg")
        r = subprocess.run([dvisvgm, "--no-fonts", "--exact-bbox", "eq.dvi", "-o", "eq.svg"],
                           cwd=work, capture_output=True, text=True, timeout=300,
                           creationflags=flags)
        if not os.path.isfile(svg):
            raise ValueError(f"dvisvgm could not convert the equation: {(r.stderr or '').strip()[-300:]}")
        with open(svg, encoding="utf-8") as f:
            text = f.read()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return text


def _with_settings(svg_text, settings):
    """The SVG with the equation settings in its <desc> (read by read_settings)."""
    desc = "<desc>" + html.escape(_MARKER + json.dumps(settings), quote=False) + "</desc>"
    root = re.search(r"<svg\b[^>]*>", svg_text)
    return svg_text[:root.end()] + desc + svg_text[root.end():]


def read_tex_file(path) -> str:
    """The equation in a .tex file: its document body (or the whole file if it
    has none), comments removed. Usable by the "latex" engine as is; for
    mathtext, the first $$…$$, \\[…\\], $…$ or equation environment is taken."""
    with open(path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.S)
    if m:
        text = m.group(1)
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = text.strip()
    if not text:
        raise ValueError(f"{path} contains no equation")
    return text


def mathtext_formula(latex) -> str:
    """The formula of a LaTeX snippet that mathtext can typeset (display
    delimiters and equation environments removed)."""
    text = latex.strip()
    for pat in (r"\$\$(.+?)\$\$", r"\\\[(.+?)\\\]",
                r"\\begin\{(equation|displaymath|math)\*?\}(.+?)\\end\{\1\*?\}"):
        m = re.search(pat, text, re.S)
        if m:
            return " ".join(m.group(m.lastindex).split())
    return " ".join(text.split())


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
               fontset: str = "cm", engine: str = "mathtext", preamble: str | None = None) -> str:
    """Typeset *latex* to an SVG file at *out_path* (glyphs as outlines, tight box,
    transparent background). Returns *out_path*.

    *engine*: "mathtext" (Matplotlib, no TeX needed; *fontset* applies) or
    "latex" (the LaTeX installation: full LaTeX; *preamble* adds packages,
    default DEFAULT_PREAMBLE)."""
    import matplotlib
    from matplotlib.backends.backend_svg import FigureCanvasSVG
    from matplotlib.colors import to_hex
    from matplotlib.figure import Figure
    if engine not in ENGINES:
        raise ValueError(f"engine must be one of {', '.join(ENGINES)}")
    if not (latex or "").strip():
        raise ValueError("the equation is empty")
    if not (0 < float(font_size) <= 400):
        raise ValueError("font_size must be between 0 and 400 pt")
    try:
        to_hex(color)
    except ValueError:
        raise ValueError(f"unknown colour {color!r}") from None
    if engine == "latex":
        preamble = DEFAULT_PREAMBLE if preamble is None else preamble
        settings = {"latex": latex.strip(), "font_size": float(font_size), "color": color,
                    "fontset": fontset, "engine": "latex", "preamble": preamble}
        svg = _with_settings(_render_svg_latex(latex, out_path, font_size, color, preamble), settings)
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(svg)
        return out_path
    text = normalize(latex)
    check(text, fontset)
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


def equation_path(pyf_path, latex, font_size=12.0, color="black", fontset="cm",
                  engine="mathtext", preamble=None) -> str:
    parts = [latex.strip(), float(font_size), color, fontset]
    if engine == "latex":                       # (mathtext keys unchanged: existing files reused)
        parts += ["latex", DEFAULT_PREAMBLE if preamble is None else preamble]
    digest = hashlib.sha1(json.dumps(parts).encode("utf-8")).hexdigest()[:12]
    return os.path.join(equation_dir(pyf_path), f"eq_{digest}.svg")


def make_equation(pyf_path, latex, font_size=12.0, color="black", fontset="cm",
                  engine="mathtext", preamble=None) -> str:
    """Write the equation's SVG (if not already there) and return its path."""
    out = equation_path(pyf_path, latex, font_size, color, fontset, engine, preamble)
    if not os.path.isfile(out):
        render_svg(latex, out, font_size, color, fontset, engine, preamble)
    return out
