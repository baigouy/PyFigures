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


# Menu-bar entries that need no description of their own: self-explanatory,
# or described in the guide under another wording. Anything new must be
# described (features added after the guide was last written went without
# documentation for weeks: the chat sidebar, the bug recorder, live sharing…).
_SELF_EXPLANATORY = {
    "Quit", "Open", "Save", "Save As", "New", "Close", "Undo", "Redo", "Copy", "Paste", "Cut",
    "Delete", "Select all", "Fit to Window", "Normal Size", "Zoom In (25%)", "Zoom Out (25%)",
}


def _label(action):
    """The entry as the user reads it: no mnemonic '&', no shortcut after a tab."""
    text = action.text().split("\t")[0].replace("&&", "\0").replace("&", "").replace("\0", "&")
    return re.sub(r"\s+", " ", text.replace("▶", "")).strip()


def _documented(name, guide):
    """Its name, or its name before a parenthesised hint ("Audit figure
    (missing scale bars / labels)" → "Audit figure"), is in the guide."""
    return _norm(name) in guide or _norm(name.split(" (")[0]) in guide


def _entries(menu, prefix=()):
    for a in menu.actions():
        text = _label(a)
        if not text or a.isSeparator() or text.startswith("—"):    # "— Vector —": a section title
            continue
        yield prefix + (text,)
        if a.menu() is not None:
            yield from _entries(a.menu(), prefix + (text,))


def _norm(s):
    s = re.sub(r"[…]|\.\.\.", "", s)
    return re.sub(r"\s+", " ", s).strip(" ▸▶").lower()


def test_no_menu_label_loses_an_ampersand(qapp):
    """A lone '&' is a keyboard accelerator for Qt, not shown: the Help menu
    read "Publication  QC Tutorial". A visible '&' is written '&&'."""
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        bar = g.menuBar if not callable(g.menuBar) else g.menuBar()
        bad = []

        def walk(menu):
            for a in menu.actions():
                if re.search(r"&(\s|$)", a.text().replace("&&", "")):     # "&File" is a real accelerator
                    bad.append(a.text())
                if a.menu() is not None:
                    walk(a.menu())
        for a in bar.actions():
            if a.menu() is not None:
                walk(a.menu())
        assert not bad, bad
    finally:
        g._dirty = False
        g.close()


def test_every_menu_entry_is_described_in_the_user_guide(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        bar = g.menuBar if not callable(g.menuBar) else g.menuBar()
        guide = _norm(_guide_text())
        missing = []
        for a in bar.actions():
            if a.menu() is None:
                continue
            for path in _entries(a.menu(), (_label(a),)):
                name = path[-1]
                if name in _SELF_EXPLANATORY or path[0] == "Help" and path[1:2] == ("Show me how…",) and len(path) > 2:
                    continue                    # the guides are listed by the menu itself
                if not _documented(name, guide):
                    missing.append(" → ".join(path))
        assert not missing, "menu entries the user guide does not describe:\n" + "\n".join(missing)
    finally:
        g._dirty = False
        g.close()
