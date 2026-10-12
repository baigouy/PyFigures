"""Qt off-screen (headless) environment for exports, MCP tools and tests.

Must run before the QApplication is created. Portable: on Linux and macOS
nothing is changed (offscreen uses fontconfig / Core Text there). On Windows,
Qt's "offscreen" platform does not use the system font database: unless
QT_QPA_FONTDIR is set it finds NO fonts at all (0 families). Text is then laid out with no real font —
a figure set in Times or Calibri exports with a substitute while the GUI uses
the real font — and the font cache built that way crashes the process (access
violation in sip/Qt) when the QApplication is destroyed at exit.
"""
from __future__ import annotations

import os
import sys

__all__ = ["use_offscreen", "ensure_offscreen_fonts", "system_font_dir"]


def system_font_dir() -> str | None:
    """The fonts folder Qt's offscreen platform must be pointed at, or None
    where it finds the system fonts by itself. Offscreen picks its font
    database per OS: fontconfig on Linux and Core Text on macOS (both see every
    installed font; QT_QPA_FONTDIR is not needed there), but a bare FreeType
    directory scan on Windows — which reads only QT_QPA_FONTDIR."""
    if sys.platform == "win32":
        d = os.path.join(os.environ.get("WINDIR") or os.environ.get("SystemRoot")
                         or r"C:\Windows", "Fonts")
        return d if os.path.isdir(d) else None
    return None


def ensure_offscreen_fonts() -> None:
    """If the chosen platform is offscreen, point it at the system fonts
    (unless QT_QPA_FONTDIR is already set). Leaves other platforms alone."""
    if os.environ.get("QT_QPA_PLATFORM", "").split(":")[0] == "offscreen" \
            and not os.environ.get("QT_QPA_FONTDIR"):
        d = system_font_dir()
        if d:
            os.environ["QT_QPA_FONTDIR"] = d


def use_offscreen() -> None:
    """Select the offscreen platform (unless another one was chosen) and give
    it the system fonts."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    ensure_offscreen_fonts()
