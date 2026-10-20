"""Coverage guard of the end-to-end GUI layer (marker ``gui_e2e``).

Every action a user can reach in the figure editor is enumerated from the
LIVE window — menu bar, toolbar (buttons, Background menu, widgets), the
canvas right-click menu for each kind of selection, the drop menu for each
drop situation and the internal-drag menu for each drag situation — and must
have a registered behaviour test (gui_e2e_registry.py) that exists. A new
menu entry without a test fails here.

With PYF_E2E_COVERAGE=<file.md> the actions × tests table is written there
(docs/GUI_E2E_COVERAGE.md is made that way).
"""
from __future__ import annotations

import ast
import os

import pytest

import gui_e2e_harness as H
from gui_e2e_harness import e2e_files, e2e_gui, menus, no_file_dialogs, watch  # noqa: F401

pytestmark = pytest.mark.gui_e2e

HERE = os.path.dirname(os.path.abspath(__file__))


def live_actions(qapp, g, menus, files, d):
    """{key: how to reach it} of everything the live window offers:
    ('action',) menu bar / toolbar, ('widget', name), ('ctx', selection kind,
    entry), ('drop', DROP_OFFERS row, button), ('drag', situation, entry)."""
    import test_gui_e2e_dnd as D
    out = {k: ("action",) for k, _a in H.menu_actions(g)}
    out.update({k: ("widget", k.split(": ", 1)[1]) for k, _w in H.toolbar_widgets(g)})
    H.prepare_selection_figure(qapp, g, d, files)
    for kind in H.SELECTION_KINDS:
        shape, pos, select = H.select_kind(qapp, g, kind)
        for entry in H.right_click(g, menus, shape, pos=pos, select=select):
            out.setdefault(H.ctx_key(entry), ("ctx", kind, entry))
    for row in D.DROP_OFFERS:
        situation, kind, names, where, _expected = row
        D.start(qapp, g, d, files, kind)
        H.drop_files(g, [files[n] for n in names], D._where(g, where))
        for c in H.drop_choices(g):
            out.setdefault(H.drop_key(situation, c), ("drop", row, c))
        H.dismiss_drop_menu(g)
    for situation in H.DRAG_SITUATIONS:
        D._drag_start(qapp, g, d, files)
        shape, to = D.DRAG_FROM_TO[situation](g)
        menus.pick = None
        H.drag(g, shape, to)
        for c in menus.last:
            out.setdefault(H.drag_key(situation, c), ("drag", situation, c))
    return out


@pytest.fixture(scope="module")
def live(qapp, e2e_gui, e2e_files, tmp_path_factory):
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    try:
        return live_actions(qapp, e2e_gui, H.MenuPilot(mp), e2e_files, tmp_path_factory.mktemp("live"))
    finally:
        mp.undo()


def _registered(live_keys):
    """(registry resolved onto the live keys, stale keys, moved keys)."""
    import gui_e2e_registry as R
    reg, stale, moved = {}, [], []
    for k, tests in R.registry().items():
        hit = H.resolve_key(live_keys, k)
        if hit is None:
            stale.append(k)
            continue
        if hit != k:
            moved.append(f"{k}  →  {hit}")
        reg.setdefault(hit, []).extend(t for t in tests if t not in reg.get(hit, []))
    return reg, stale, moved


def _tests_defined():
    out = set()
    for fn in os.listdir(HERE):
        if fn.startswith("test_") and fn.endswith(".py"):
            with open(os.path.join(HERE, fn), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            out.add(fn)
            out.update(f"{fn}::{n.name}" for n in tree.body if isinstance(n, ast.FunctionDef))
    return out


def test_every_reachable_action_has_a_behaviour_test(live):
    import warnings
    live = list(live)
    assert len(live) > 150, f"only {len(live)} actions found: is the enumeration broken?"
    # registry keys follow the GUI: a cosmetic rename or a move to another
    # menu still finds its live action (the tests resolve keys the same way)
    reg, stale, moved = _registered(live)
    missing = [k for k in live if not reg.get(k)]
    defined = _tests_defined()
    dangling = sorted({t for k in live for t in reg.get(k, []) if t not in defined})
    out = os.environ.get("PYF_E2E_COVERAGE")
    if out:
        _write_table(out, live, reg)
    if moved:
        warnings.warn("GUI entries renamed / moved (their tests follow them; update the tables "
                      "when convenient):\n  " + "\n  ".join(moved))
    if stale:
        warnings.warn("registered actions the GUI no longer offers (their tests skip):\n  "
                      + "\n  ".join(stale))
    assert not missing, "actions with no behaviour test — test_unregistered_actions_are_swept_generically " \
                        "already ran them; add a row checking their RESULT to the matching table " \
                        "(see docs/GUI_E2E_TESTS.md):\n  " + "\n  ".join(missing)
    assert not dangling, f"registered tests that do not exist: {dangling}"


def _run_generically(qapp, g, menus, files, d, how):
    """Do what a user does to reach an action, accepting its dialogs."""
    import test_gui_e2e_dnd as D
    kind = how[0]
    if kind == "action":
        H.load(qapp, g, H.base_figure(d, files))
        H.panel(g).set_current_selection(H.by_name(g, "gray8"))
        return lambda key: H.action(g, key).trigger()
    if kind == "widget":
        from qtpy.QtWidgets import QAbstractSpinBox, QCheckBox, QComboBox, QLineEdit
        H.load(qapp, g, H.base_figure(d, files))

        def poke(_key):
            w = getattr(g, how[1], None)
            if isinstance(w, QCheckBox):
                w.click()
            elif isinstance(w, QComboBox):
                w.setCurrentIndex((w.currentIndex() + 1) % max(1, w.count()))
            elif isinstance(w, QAbstractSpinBox):
                w.stepUp()
            elif isinstance(w, QLineEdit):
                w.setText(w.text() + "x")
        return poke
    if kind == "ctx":
        H.prepare_selection_figure(qapp, g, d, files)
        shape, pos, select = H.select_kind(qapp, g, how[1])
        return lambda _key: H.right_click(g, menus, shape, pos=pos, select=select, pick=how[2])
    if kind == "drop":
        situation, start, names, where, _expected = how[1]
        D.start(qapp, g, d, files, start)

        def drop(_key):
            H.drop_files(g, [files[n] for n in names], D._where(g, where))
            H.click_drop_choice(g, how[2])
        return drop
    if kind == "drag":
        D._drag_start(qapp, g, d, files)

        def drag(_key):
            shape, to = D.DRAG_FROM_TO[how[1]](g)
            menus.pick = how[2]
            H.drag(g, shape, to)
            menus.pick = None
        return drag
    raise AssertionError(how)


def test_unregistered_actions_are_swept_generically(qapp, e2e_gui, e2e_files, menus, no_file_dialogs, tmp_path,
                                                    watch, live):
    """Whatever the GUI offers that no table checks yet (a new menu entry,
    a new drop or drag choice, a new toolbar control) is still run as a user
    would — dialogs accepted with their defaults, file pickers cancelled —
    and must raise / warn / log nothing, close its dialogs, and keep undo /
    redo / reopen consistent. This is what makes the layer follow the GUI as
    it evolves; the guard above still asks for a test of the RESULT."""
    g = e2e_gui
    reg, _stale, _moved = _registered(list(live))
    todo = [k for k in live if not reg.get(k)]
    done = []
    for i, key in enumerate(todo):
        d = tmp_path / f"a{i}"
        d.mkdir()
        do = _run_generically(qapp, g, menus, e2e_files, d, live[key])
        before = H.snapshot(g, d)
        watch.check(f"{key}: start")
        with H.dialogs(accept_all=True) as pilot:
            do(key)
            H.settle(qapp, g, timeout=30)
            H.dismiss_drop_menu(g)
        failed = [u for u in pilot.unexpected if "failed" in u]
        assert not failed, (key, failed)
        assert H.drop_menu(g) is None, key
        watch.check(key)
        after = H.snapshot(g, d)
        H.check_invariants(qapp, g, d, before, after)
        watch.check(f"{key}: undo / redo / reopen")
        for w in qapp.topLevelWidgets():
            if w is not g and w.isVisible() and w.isWindow() and type(w).__name__ != "QMenu":
                w.close()
        done.append(key)
    if done:
        print("\nswept generically (no result test yet): " + ", ".join(done))


def _write_table(path, live, reg):
    groups = {}
    for k in live:
        groups.setdefault(k.split(":", 1)[0].split(" [")[0], []).append(k)
    lines = ["# GUI end-to-end coverage", "",
             "Generated by `tests/test_gui_e2e_coverage.py` (set `PYF_E2E_COVERAGE` to this file).",
             "Every action reachable in the figure editor and the tests that run it and check its result.",
             "", f"{len(live)} actions, {sum(1 for k in live if reg.get(k))} with a behaviour test.", ""]
    for name, keys in groups.items():
        lines += [f"## {name} ({len(keys)})", "", "| action | tested by |", "|---|---|"]
        for k in keys:
            label = k.split(": ", 1)[1] if k.startswith(name + ":") else k[len(name):].strip()
            tests = ", ".join(f"`{t}`" for t in reg.get(k, [])) or "**none**"
            lines.append(f"| {label.replace('|', '¦')} | {tests} |")
        lines.append("")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
