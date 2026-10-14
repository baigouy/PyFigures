"""Label maths (``$…$``) for office formats.

* ``latex_to_omml``    — an Office Math (OMML) ``<m:oMath>`` element, so
  PowerPoint shows the formula as a native, editable equation
  (LaTeX -> MathML with latex2mathml, MathML -> OMML with mathml2omml);
* ``latex_to_unicode`` — plain Unicode text (Greek letters, symbols, super-
  and subscript digits), for Illustrator and as the fallback of the equation.

siunitx commands (\\SI, \\si, \\num, \\qty, \\unit) are expanded to plain
maths first; neither converter knows them.
"""
from __future__ import annotations

import re

OMML_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

_UNITS = {
    "micro": "µ", "milli": "m", "nano": "n", "pico": "p", "kilo": "k", "mega": "M", "giga": "G",
    "centi": "c", "femto": "f",
    "metre": "m", "meter": "m", "second": "s", "gram": "g", "litre": "L", "liter": "L",
    "molar": "M", "mole": "mol", "hertz": "Hz", "percent": "%", "celsius": "°C", "degreeCelsius": "°C",
    "degree": "°", "hour": "h", "minute": "min", "volt": "V", "ampere": "A", "newton": "N",
    "pascal": "Pa", "joule": "J", "watt": "W", "kelvin": "K", "dalton": "Da", "ohm": "Ω",
    "siemens": "S", "farad": "F", "tesla": "T", "becquerel": "Bq", "candela": "cd", "lux": "lx",
    "angstrom": "Å", "bar": "bar", "electronvolt": "eV", "um": "µm", "nm": "nm", "mm": "mm",
    "ms": "ms", "us": "µs", "ns": "ns", "kDa": "kDa", "mM": "mM", "uM": "µM", "nM": "nM",
}
_SUP = dict(zip("0123456789+-=()niax", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃˣ"))
_SUB = dict(zip("0123456789+-=()aeoxijklmnprstuv", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓᵢⱼₖₗₘₙₚᵣₛₜᵤᵥ"))


def _group(s, i):
    """(content, end) of the brace group starting at s[i] == '{'."""
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
    return s[i + 1:], len(s)


def _unit_text(spec):
    """'\\micro\\metre\\per\\second' -> 'µm/s'; literal units pass through."""
    out = ""
    pending_power = ""
    for word, literal in re.findall(r"\\([A-Za-z]+)|([^\\\s{}]+)", spec):
        if literal:
            out += literal
        elif word == "per":
            out += "/"
        elif word == "squared":
            out += "^2"
        elif word == "cubed":
            out += "^3"
        elif word in ("square", "cubic"):
            pending_power = "^2" if word == "square" else "^3"
        else:
            out += _UNITS.get(word, word)
            if pending_power:
                out += pending_power
                pending_power = ""
    return out


def expand_siunitx(tex: str) -> str:
    """Replace siunitx commands by plain maths (numbers and upright units)."""
    out = ""
    i = 0
    while i < len(tex):
        m = re.match(r"\\(SI|qty|si|unit|num|ang)\b\s*(\[[^\]]*\])?\s*", tex[i:])
        if not m:
            out += tex[i]
            i += 1
            continue
        cmd = m.group(1)
        j = i + m.end()
        args = []
        need = 2 if cmd in ("SI", "qty") else 1
        while len(args) < need and j < len(tex) and tex[j] == "{":
            arg, j = _group(tex, j)
            args.append(arg)
            while j < len(tex) and tex[j] == " ":
                j += 1
        if len(args) < need:
            out += tex[i:j]
            i = j
            continue
        if cmd in ("SI", "qty"):
            out += args[0] + r"\,\mathrm{" + _unit_text(args[1]) + "}"
        elif cmd in ("si", "unit"):
            out += r"\mathrm{" + _unit_text(args[0]) + "}"
        elif cmd == "ang":
            out += args[0] + "°"
        else:
            out += args[0]
        i = j
    return out


def _prepare(tex: str) -> str:
    tex = expand_siunitx(tex)
    tex = re.sub(r"\\bm\b", r"\\boldsymbol", tex)
    tex = re.sub(r"\\(?:mathup|symup)\b", r"\\mathrm", tex)
    return tex.replace("µ", r"\mu ")


def latex_to_omml(tex: str):
    """The ``<m:oMath>`` XML string of *tex*, or None when it cannot be converted."""
    try:
        import latex2mathml.converter
        import mathml2omml
    except ImportError:
        return None
    try:
        omml = mathml2omml.convert(latex2mathml.converter.convert(_prepare(tex)))
    except Exception:
        return None
    if not omml.startswith("<m:oMath"):
        return None
    if "xmlns:m=" not in omml[:120]:
        omml = omml.replace("<m:oMath", '<m:oMath xmlns:m="%s"' % OMML_NS, 1)
    return omml


def _scripts(tex: str) -> str:
    """x^{2} -> x², c_{0} -> c₀ when every character has a Unicode form."""
    def repl(m):
        table = _SUP if m.group(1) == "^" else _SUB
        body = m.group(2) if m.group(2) is not None else m.group(3)
        if body and all(ch in table for ch in body):
            # '{}' ends a preceding command name (\beta_i -> \beta{}ᵢ)
            return "{}" + "".join(table[ch] for ch in body)
        return m.group(0)
    return re.sub(r"([\^_])(?:\{([^{}\\]*)\}|([A-Za-z0-9+\-]))", repl, tex)


def latex_to_unicode(tex: str) -> str:
    """Readable plain-text form of *tex* (Greek letters and symbols as Unicode)."""
    tex = _scripts(_prepare(tex))
    try:
        from pylatexenc.latex2text import LatexNodes2Text
        text = LatexNodes2Text(math_mode="text").latex_to_text(tex)
    except Exception:
        text = re.sub(r"\\[A-Za-z]+\s*|[{}]", "", tex)
    return re.sub(r"\s+", " ", text).strip()
