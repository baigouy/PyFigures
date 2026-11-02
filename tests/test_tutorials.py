"""
Tests for the in-app guided tutorials (pyfigures/gui/tutorial.py).

There are five tutorials — beginner, medium, advanced, publication, sharing —
launched from the Help menu. These tests check that every step list is
well-formed, that the Help-menu wiring exists, and that each step's get_target
and completion_check run against a real loaded figure without raising.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")
try:
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication  # noqa: F401
    _QT = True
except Exception:
    _QT = False

pytestmark = pytest.mark.skipif(not _QT, reason="Qt not available")

from pyfigures.gui import tutorial as T

_TUTORIALS = {
    "beginner": T.beginner_steps,
    "medium": T.medium_steps,
    "advanced": T.advanced_steps,
    "publication": T.publication_steps,
    "sharing": T.sharing_steps,
    "stacks": T.stacks_steps,
    "automation": T.automation_steps,
    "chat": T.chat_steps,
}
# the poster tutorial runs on the poster window: see test_tutorial_controller.py

_START_METHODS = {
    "start_beginner_tutorial", "start_advanced_tutorial", "start_expert_tutorial",
    "start_publication_tutorial", "start_sharing_tutorial", "start_stacks_tutorial",
    "start_automation_tutorial", "start_chat_tutorial", "start_poster_tutorial", "start_album_tutorial",
}


def _tif(path, val):
    from batoolset.img import Img
    Img(np.full((32, 48), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


@pytest.fixture
def gui(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    d = tempfile.mkdtemp()
    a = _tif(os.path.join(d, "a.tif"), 60)
    b = _tif(os.path.join(d, "b.tif"), 200)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], a, label="A")
    add_image(pyf, [0], b, label="B")

    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    yield g
    g._dirty = False


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_step_list_well_formed(name):
    steps = _TUTORIALS[name]()
    assert steps, f"{name} tutorial is empty"
    for i, s in enumerate(steps):
        assert isinstance(s, T.TutorialStep)
        assert s.title and s.message, f"{name} step {i} missing title/message"
        assert s.get_target is None or callable(s.get_target)
        assert s.completion_check is None or callable(s.completion_check)
        assert s.on_show is None or callable(s.on_show)
    # every tutorial opens with a manual welcome and ends with a manual "done"
    assert steps[0].completion_check is None and steps[0].get_target is None
    assert steps[-1].completion_check is None and steps[-1].get_target is None


def test_help_menu_wires_every_tutorial(gui):
    # the start_* methods exist
    for m in _START_METHODS:
        assert hasattr(gui, m), f"missing {m}"
    # and each appears as a Help-menu entry
    entries = []
    for act in gui.menuBar.actions():
        if act.text() == "Help":
            entries = [a.text() for a in act.menu().actions() if "Tutorial" in a.text()]
    assert len(entries) == len(_START_METHODS), entries
    for word in ("Publication", "Sharing", "Stacks", "Automate", "Poster"):
        assert any(word in e for e in entries), (word, entries)


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_step_numbers_are_in_order(name):
    import re
    nums = [int(m.group(1)) for s in _TUTORIALS[name]()
            for m in [re.match(r"Step (\d+) ", s.title)] if m]
    assert nums == list(range(1, len(nums) + 1)), nums


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_requirements_are_well_formed(name):
    for s in _TUTORIALS[name]():
        assert s.requires is None or callable(s.requires)
        assert s.prepare is None or callable(s.prepare)
        if s.prepare is not None:
            assert s.requires is not None, s.title     # the button only shows when something is missing
        if s.requires is not None:
            assert s.requires_text, s.title


@pytest.mark.parametrize("name", list(_TUTORIALS))
def test_targets_and_checks_run_without_error(gui, name):
    """Every get_target / completion_check must be safe to call on a live figure
    (the controller polls them each tick)."""
    for i, s in enumerate(_TUTORIALS[name]()):
        if s.get_target is not None:
            tgt = s.get_target(gui)               # may return a widget or None
            assert tgt is None or hasattr(tgt, "size")
        if s.completion_check is not None:
            res = s.completion_check(gui)          # must be truthy/falsey, no raise
            assert res in (True, False) or isinstance(res, (int, bool))
        if s.requires is not None:
            assert s.requires(gui) in (True, False)


def test_count_scalebars_helper(gui):
    assert T._count_scalebars(gui) == 0
    # add scale bars to every panel and re-count
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.image2d import Image2D
    imgs = []
    stack = list(gui.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        o = stack.pop()
        if isinstance(o, Image2D):
            imgs.append(o)
        if hasattr(o, "content") and o.content:
            stack.extend(o.content)
    for im in imgs:
        im.annotations = (im.annotations or []) + [ScaleBar()]
    assert T._count_scalebars(gui) == len(imgs) >= 2


def test_has_caption_sidecar_helper(gui, tmp_path):
    from pyfigures.mcp_server import set_figure_caption
    # no file / no caption → False
    assert T._has_caption_sidecar(gui) is False
    # point at a real .pyf path; still no caption sidecar yet
    pyf = str(tmp_path / "fig.pyf")
    open(pyf, "w").close()
    gui.current_file = pyf
    assert T._has_caption_sidecar(gui) is False
    # write the caption sidecar and detect it
    set_figure_caption(pyf, "A legend.", title="Figure 1")
    assert T._has_caption_sidecar(gui) is True


def test_menu_paths_cited_in_tutorials_exist(gui):
    """Every '<b>Menu → item</b>' a tutorial tells the user to open is a real
    menu-bar path (right-click menu paths start with no menu-bar name)."""
    import html
    import re

    def norm(s):
        s = s.replace("&&", "\0").replace("&", "").replace("\0", "&")
        return re.sub(r"[….]+$", "", s.strip(' "▶')).strip()

    paths = set()

    def walk(menu, prefix):
        for a in menu.actions():
            t = norm(a.text())
            if t:
                paths.add(" → ".join(prefix + [t]))
                if a.menu() is not None:
                    walk(a.menu(), prefix + [t])

    for a in gui.menuBar.actions():
        if a.menu() is not None:
            walk(a.menu(), [norm(a.text())])
    tops = {p.split(" → ")[0] for p in paths}
    src = open(T.__file__, encoding="utf-8").read()
    wrong = []
    for m in re.finditer(r"<b>([^<]*?→[^<]*?)</b>", src):
        parts = [norm(p) for p in html.unescape(m.group(1)).split("→")]
        if parts[0] in tops and " → ".join(parts) not in paths:
            if parts[0] == "Help" and parts[-1].endswith("Movies"):
                continue                 # "Help → <tutorial name>": named, not a literal path
            wrong.append(" → ".join(parts))
    assert not wrong, wrong
