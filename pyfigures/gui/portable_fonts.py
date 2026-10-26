"""Portable publication fonts for PyFigures.

Journals routinely ask for Helvetica / Arial. Those exact fonts are not
installed everywhere (Helvetica is Mac-only; Arial is proprietary and absent on
many Linux boxes), so a figure authored on one machine can render with a
different substituted font on another — bad for a publication-quality tool.

This module makes the font situation *portable*:

  * every ``.ttf`` / ``.otf`` dropped in ``pyfigures/gui/fonts/`` is registered
    at startup via ``QFontDatabase.addApplicationFont`` — so a redistributable
    Helvetica clone (TeX Gyre Heros, Nimbus Sans, Arimo, Liberation Sans …)
    bundled there is available on *every* OS, no system install needed;
  * matplotlib's DejaVu Sans (always present as a dependency) is registered as a
    guaranteed last-resort fallback so text never silently drops to a random
    system font;
  * a substitution chain maps "Helvetica"/"Helvetica Neue"/"Arial" to the best
    available metric-compatible sans, consistently, so requesting Helvetica
    degrades predictably.

Call :func:`register_portable_fonts` once, right after the ``QApplication`` is
created (done for the GUI and every headless render/export path). It is
idempotent. Exported PDFs embed whatever font is used, so a bundled clone makes
the whole pipeline reproducible across machines.
"""
from __future__ import annotations

import os

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

# Requested family -> ordered preference of metric-compatible alternatives.
# The first that is actually available (installed or bundled) wins.
_SUBSTITUTIONS = {
    "Helvetica":       ["Helvetica", "TeX Gyre Heros", "Nimbus Sans",
                        "Arimo", "Liberation Sans", "Arial", "DejaVu Sans"],
    "Helvetica Neue":  ["Helvetica Neue", "TeX Gyre Heros", "Nimbus Sans",
                        "Arimo", "Liberation Sans", "Arial", "DejaVu Sans"],
    "Arial":           ["Arial", "Arimo", "Liberation Sans", "TeX Gyre Heros",
                        "Nimbus Sans", "Helvetica", "DejaVu Sans"],
}

# Redistributable Helvetica/Arial-metric clones we recognise as "portable".
PORTABLE_CLONES = ("TeX Gyre Heros", "Nimbus Sans", "Arimo",
                   "Liberation Sans", "DejaVu Sans")

_registered = False
_bundled_families: list[str] = []


def _matplotlib_dejavu_files():
    """Paths to matplotlib's bundled DejaVu Sans faces (always available)."""
    try:
        import matplotlib
        d = os.path.join(os.path.dirname(matplotlib.__file__),
                         "mpl-data", "fonts", "ttf")
        return [os.path.join(d, f) for f in (
            "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
            "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf")
            if os.path.isfile(os.path.join(d, f))]
    except Exception:
        return []


def register_portable_fonts(app=None) -> list[str]:
    """Register bundled + fallback fonts and install the substitution chain.

    Safe to call multiple times (registers only once). Returns the list of
    font-family names added from the bundle / fallbacks.
    """
    global _registered, _bundled_families
    if _registered:
        return _bundled_families
    try:
        from qtpy.QtGui import QFontDatabase, QFont
        from qtpy.QtWidgets import QApplication
    except Exception:
        return []
    if QApplication.instance() is None:
        # No GUI app yet — registering application fonts needs one.
        return []

    families: set[str] = set()

    def _add(path):
        try:
            fid = QFontDatabase.addApplicationFont(path)
            if fid != -1:
                for fam in QFontDatabase.applicationFontFamilies(fid):
                    families.add(fam)
        except Exception:
            pass

    # 1) user-/project-bundled fonts (the portable slot)
    if os.path.isdir(FONTS_DIR):
        for name in sorted(os.listdir(FONTS_DIR)):
            if name.lower().endswith((".ttf", ".otf")):
                _add(os.path.join(FONTS_DIR, name))

    # 2) guaranteed fallback so text is never lost to a random system font
    for f in _matplotlib_dejavu_files():
        _add(f)

    # 3) predictable Helvetica/Arial -> best-available substitution
    try:
        for requested, alts in _SUBSTITUTIONS.items():
            QFont.insertSubstitutions(requested, alts)
    except Exception:
        pass

    _bundled_families = sorted(families)
    _registered = True
    return _bundled_families


def available_families() -> set[str]:
    """All font families Qt currently knows (system + bundled). Empty if no app."""
    try:
        from qtpy.QtGui import QFontDatabase
        from qtpy.QtWidgets import QApplication
        if QApplication.instance() is None:
            return set()
        # Qt6: static families(); Qt5: needs an instance
        try:
            return set(QFontDatabase.families())
        except TypeError:
            return set(QFontDatabase().families())
    except Exception:
        return set()


def resolve_family(requested: str) -> str:
    """Return the best available family for *requested*, following the portable
    substitution chain. Falls back to the request itself if nothing matches."""
    avail = available_families()
    for cand in _SUBSTITUTIONS.get(requested, [requested]):
        if cand in avail:
            return cand
    return requested


def drawn_family(requested: str) -> str:
    """The family text asking for *requested* is actually drawn and exported in:
    the substitution chain, else the family itself when installed, else Qt's
    fallback font."""
    avail = available_families()
    resolved = resolve_family(requested)
    if resolved in avail:
        return resolved
    try:
        from qtpy.QtGui import QFont, QFontInfo
        return QFontInfo(QFont(requested)).family()
    except Exception:
        return resolved


# Common families by style, most journal-friendly first: alternatives to offer
# for a font that is not installed (only installed ones are offered).
_STYLE_FAMILIES = {
    "sans": ["Helvetica", "Arial", "TeX Gyre Heros", "Nimbus Sans", "Arimo", "Liberation Sans",
             "Helvetica Neue", "Source Sans 3", "Source Sans Pro", "Open Sans", "Roboto", "Lato",
             "Noto Sans", "Calibri", "Segoe UI", "Verdana", "Tahoma", "DejaVu Sans"],
    "serif": ["Times New Roman", "Times", "TeX Gyre Termes", "Nimbus Roman", "Tinos",
              "Liberation Serif", "Georgia", "Cambria", "Palatino Linotype", "Book Antiqua",
              "Garamond", "Noto Serif", "Source Serif 4", "DejaVu Serif"],
    "mono": ["Courier New", "Courier", "Cousine", "Liberation Mono", "Consolas",
             "Lucida Console", "Source Code Pro", "DejaVu Sans Mono"],
}


def font_style(family: str) -> str:
    """'sans', 'serif' or 'mono' for *family*: from the known lists, else
    guessed from its name (sans when nothing says otherwise)."""
    low = family.strip().lower()
    for style, fams in _STYLE_FAMILIES.items():
        if low in (f.lower() for f in fams):
            return style
    if any(w in low for w in ("mono", "courier", "code", "console")):
        return "mono"
    if "sans" not in low and any(w in low for w in ("serif", "times", "roman", "georgia",
                                                    "garamond", "palatino", "minion", "cambria")):
        return "serif"
    return "sans"


def font_status(requested: str, limit: int = 5) -> dict:
    """Is *requested* installed here, what is it really drawn and exported in,
    and which installed fonts could replace it (same style, the Helvetica/Arial
    look-alikes first, then names that look alike)."""
    import difflib
    avail = available_families()
    by_low = {f.lower(): f for f in avail if not f.startswith("@")}
    name = by_low.get(requested.strip().lower())
    # "helvetica" asks for the Helvetica substitution chain too
    canon = next((k for k in _SUBSTITUTIONS if k.lower() == requested.strip().lower()), requested)
    style = font_style(requested)
    alts = []
    for cand in _SUBSTITUTIONS.get(canon, []) + _STYLE_FAMILIES[style]:
        real = by_low.get(cand.lower())
        if real and real != name and real not in alts:
            alts.append(real)
    if name is None:
        # a misspelt or partial name ("helvetca", "Liberation"): offer the look-alike names too
        close = difflib.get_close_matches(requested.lower(), list(by_low), n=3, cutoff=0.6)
        close += [k for k in by_low if requested.strip().lower() in k][:3]
        front = list(dict.fromkeys(by_low[k] for k in close))
        alts = front + [a for a in alts if a not in front]
    return {
        "requested": requested,
        "installed": name is not None,
        "installed_name": name,
        "drawn_as": drawn_family(name or canon),
        "style": style,
        "alternatives": alts[:limit],
    }


def font_report(resolve=()) -> dict:
    """Structured report of the portable-font situation (for GUI + MCP).
    *resolve*: family names to report the actually drawn family, whether they
    are installed and installed alternatives for (``status``)."""
    avail = available_families()
    portable = sorted(f for f in PORTABLE_CLONES if f in avail)
    return {
        "bundled_families": list(_bundled_families),
        "fonts_dir": FONTS_DIR,
        "portable_clones_available": portable,
        "helvetica_resolves_to": resolve_family("Helvetica"),
        "arial_resolves_to": resolve_family("Arial"),
        "has_true_helvetica": "Helvetica" in avail,
        "has_arial": "Arial" in avail,
        # '@' families are Windows' vertical-writing duplicates
        "installed_families": sorted((f for f in avail if not f.startswith("@")), key=str.lower),
        "drawn_as": {f: drawn_family(f) for f in resolve},
        "status": {f: font_status(f) for f in resolve},
    }
