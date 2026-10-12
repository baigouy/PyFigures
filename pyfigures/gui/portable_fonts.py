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


def font_report() -> dict:
    """Structured report of the portable-font situation (for GUI + MCP)."""
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
    }
