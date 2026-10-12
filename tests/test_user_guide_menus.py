"""docs/pyfigures_user_guide.html keeps up with the real menus: every menu of
the main window has its own section, and every tutorial of the Help menu is
described.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import html
import os
import re

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _guide_text():
    with open(os.path.join(ROOT, "docs", "pyfigures_user_guide.html"), encoding="utf-8") as f:
        text = html.unescape(re.sub(r"<[^>]+>", " ", f.read()))
    return re.sub(r"\s+", " ", text)


def _clean(s):
    return re.sub(r"\s+", " ", s.replace("&&", "&").replace("▶", "")).strip()


def test_every_menu_and_tutorial_is_in_the_user_guide(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        bar = g.menuBar if not callable(g.menuBar) else g.menuBar()
        menus = {_clean(a.text()).replace("&", ""): a.menu() for a in bar.actions() if a.menu()}
        guide = _guide_text()
        missing = [m for m in menus if f"{m} menu" not in guide]
        assert not missing, f"menus without a section in the user guide: {missing}"
        tutorials = [_clean(a.text()) for a in menus["Help"].actions() if "Tutorial" in a.text()]
        assert len(tutorials) >= 8
        missing = [t for t in tutorials if t not in guide]
        assert not missing, f"tutorials not described in the user guide: {missing}"
    finally:
        g._dirty = False
        g.close()
