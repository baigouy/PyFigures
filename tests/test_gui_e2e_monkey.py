"""Seeded random "monkey" test of the figure editor (marker ``gui_e2e``).

From the base figure, a random but reproducible sequence of user actions:
a right-click on a random panel / row / empty canvas then a random entry of
the menu that really pops up; a drag of a random panel onto another then a
random entry of the drop menu; files dropped at a random place then a random
button of the drop menu; undo; redo. Dialogs that open are accepted with
their defaults (colour pickers: their default colour).

After EVERY action: no exception / Qt warning / logged error, undo gives the
figure before the action back and redo the one after it, and (every few
steps) a save / reopen keeps it. A failure prints the seed and the actions so
far; replay one sequence with

    PYF_E2E_SEED=<seed> pytest -m gui_e2e tests/test_gui_e2e_monkey.py
"""
from __future__ import annotations

import os
import random

import pytest

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, menus, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e

SEEDS = [int(os.environ["PYF_E2E_SEED"])] if os.environ.get("PYF_E2E_SEED") else [11, 2026]
STEPS = int(os.environ.get("PYF_E2E_MONKEY_STEPS", "18"))

# entries that leave to another window / need a human (covered elsewhere)
SKIP_ENTRIES = ("Edit Image", "Edit text", "Edit equation", "Edit LaTeX", "Ignore", "Text & lettering")


def _shapes(g):
    p = H.panel(g)
    return [s for s in list(p.shapes_to_draw) + H.images(g) if not getattr(s, "isText", False)]


def _right_click(rng, qapp, g, menus, log):
    shapes = _shapes(g)
    if not shapes or rng.random() < 0.1:
        shape, pos = None, H.empty_point(g)
        H.panel(g).set_current_selection(None)
    else:
        shape, pos = rng.choice(shapes), None
    offered = H.right_click(g, menus, shape, pos=pos, select=shape is not None)
    entries = [e for e in offered if not any(s in e for s in SKIP_ENTRIES)]
    if not entries:
        return None
    entry = rng.choice(entries)
    log.append(f"right-click {_name(shape)} → {entry}")
    H.right_click(g, menus, shape, pos=pos, select=False, pick=entry)
    return entry


def _drag(rng, qapp, g, menus, log):
    shapes = _shapes(g)
    if len(shapes) < 2:
        return None
    a, b = rng.sample(shapes, 2)
    if a in H.images(b) or b in H.images(a):
        return None
    menus.pick = None
    H.drag(g, a, H.centre(g, b))
    offered = list(menus.last or [])
    if not offered:
        return None
    choice = rng.choice(offered)
    log.append(f"drag {_name(a)} onto {_name(b)} → {choice}")
    menus.pick = choice
    H.drag(g, a, H.centre(g, b))
    menus.pick = None
    return choice


def _drop(rng, qapp, g, files, log):
    names = rng.sample(["png2", "tif16", "zstack", "tstack", "rgb"], rng.choice([1, 1, 2]))
    targets = [None] + [H.centre(g, s) for s in _shapes(g)]
    where = rng.choice(targets)
    if not H.drop_files(g, [files[n] for n in names], where):
        return None
    choices = H.drop_choices(g)
    if not choices:
        return None
    choice = rng.choice(choices)
    log.append(f"drop {names} at {'empty canvas' if where is None else 'a panel'} → {choice}")
    if "Montage" in choice:
        H.dismiss_drop_menu(g)                    # its frame choice is covered by test_gui_e2e_dnd
        return None
    H.click_drop_choice(g, choice)
    return choice


def _name(shape):
    if shape is None:
        return "empty canvas"
    imgs = H.images(shape)
    names = [os.path.basename(str(i.filename)) for i in imgs[:3]]
    return ("row " if type(shape).__name__ == "Group" else "") + "/".join(names)


@pytest.mark.parametrize("seed", SEEDS)
def test_monkey(qapp, e2e_gui, e2e_files, tmp_path, menus, watch, seed):
    g = e2e_gui
    rng = random.Random(seed)
    H.load(qapp, g, H.base_figure(tmp_path, e2e_files))
    log = []
    state = H.snapshot(g, tmp_path)
    try:
        for step in range(STEPS):
            kind = rng.choices(["right-click", "drag", "drop", "undo"], weights=[5, 3, 3, 1])[0]
            with H.dialogs(accept_all=True) as pilot:
                if kind == "right-click":
                    did = _right_click(rng, qapp, g, menus, log)
                elif kind == "drag":
                    did = _drag(rng, qapp, g, menus, log)
                elif kind == "drop":
                    did = _drop(rng, qapp, g, e2e_files, log)
                else:
                    log.append("undo + redo")
                    g.undo()
                    H.settle(qapp, g)
                    g.redo()
                    did = "undo"
                H.settle(qapp, g, timeout=30)
                H.dismiss_drop_menu(g)
            if did is None:
                continue
            assert not [u for u in pilot.unexpected if "failed" in u], pilot.unexpected
            watch.check(log[-1])
            after = H.snapshot(g, tmp_path)
            if kind == "undo":
                assert H.same(after, state), "undo + redo did not come back: " + H.diff(state, after)
            else:
                H.check_invariants(qapp, g, tmp_path, state, after, roundtrip=step % 4 == 0)
                watch.check(log[-1] + ": undo / redo / reopen")
            state = H.snapshot(g, tmp_path)
    except BaseException:
        print(f"\nmonkey seed {seed} — actions so far:\n  " + "\n  ".join(log))
        raise
    assert len(log) >= STEPS // 2, log
