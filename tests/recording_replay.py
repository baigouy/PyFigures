"""Replays a bug recording (pyfigures/gui/bug_recorder.py) in the figure
editor with the e2e harness: the starting figure, then each step as the user
did it — menu actions, right-click / drag-menu choices, drops and the drop
menu, dialogs answered with the recorded values and button, file pickers
returning the recorded paths (saves go to the test's folder), double-clicks,
drags, keys. Returns the recording and the state of the figure at the end;
tests/test_recordings.py then runs the recording's checks."""
from __future__ import annotations

import json
import os
import sys

from qtpy.QtCore import QEvent, QPointF, Qt
from qtpy.QtGui import QKeyEvent, QKeySequence
from qtpy.QtWidgets import QApplication

import gui_e2e_harness as H

ACTIONABLE = ("action", "context", "drop", "drop_choice", "double_click", "drag", "drag_choice", "key")


def _mapped(rec_dir, sources, path):
    """Where a recorded source file is for the replay (its stand-in copy)."""
    copied = (sources or {}).get(path)
    if copied:
        return os.path.join(rec_dir, copied)
    return path


def _start_figure(rec_dir, d, tmp):
    """start.pyf with its source paths pointing at the stand-in copies."""
    with open(os.path.join(rec_dir, "start.pyf"), encoding="utf-8") as f:
        text = f.read()
    for orig, copied in (d.get("sources") or {}).items():
        if copied:
            new = os.path.join(rec_dir, copied).replace("\\", "/")
            for variant in {orig, orig.replace("\\", "/"), orig.replace("/", "\\")}:
                text = text.replace(variant, new)
    out = os.path.join(str(tmp), "start.pyf")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    return out


def find_panel(g, name):
    """The panel recorded as 'file.tif' / 'file.tif#2' / {'group_of': [...]}."""
    if isinstance(name, dict):
        first = find_panel(g, name["group_of"][0]) if name.get("group_of") else None
        if first is None:
            return None
        p = H.panel(g)
        for top in p.shapes_to_draw:
            stack = [top]
            while stack:
                s = stack.pop(0)
                kids = list(getattr(s, "content", None) or [])
                if first in kids:
                    return s
                stack.extend(kids)
        return first
    if not name:
        return None
    base, _, nth = str(name).partition("#")
    hits = [i for i in H.images(g) if os.path.basename(str(i.filename or "")) == base
            or (base == "text" and i.isText)]
    k = int(nth) - 1 if nth else 0
    return hits[k] if k < len(hits) else None


def _set_values(dlg, values):
    """Give the dialog's fields the recorded values (same traversal order and
    kind as bug_recorder.dialog_values)."""
    from qtpy.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit,
                                QPlainTextEdit, QRadioButton, QSpinBox, QTextEdit)
    live = []
    for w in dlg.findChildren(object):
        try:
            if not hasattr(w, "isVisible") or not w.isVisible():
                continue
        except RuntimeError:
            continue
        if isinstance(w, QLineEdit) and not isinstance(w.parent(), (QAbstractSpinBox, QComboBox)):
            live.append(("line", w))
        elif isinstance(w, (QSpinBox, QDoubleSpinBox)):
            live.append(("spin", w))
        elif isinstance(w, QComboBox):
            live.append(("combo", w))
        elif isinstance(w, (QCheckBox, QRadioButton)):
            live.append(("check", w))
        elif isinstance(w, (QTextEdit, QPlainTextEdit)) and not w.isReadOnly():
            live.append(("text", w))
    for (kind, w), v in zip(live, values):
        if kind != v["type"]:
            continue
        if kind == "line":
            w.setText(v["value"])
        elif kind == "spin":
            w.setValue(v["value"])
        elif kind == "combo":
            w.setCurrentText(v["value"])
        elif kind == "check":
            w.setChecked(bool(v["value"]))
        else:
            w.setPlainText(v["value"])


def _answer(step):
    def handler(dlg):
        if step.get("values"):
            _set_values(dlg, step["values"])
        if step.get("button") and H.click_button(dlg, step["button"]):
            return
        (H.accept if step.get("result") else H.reject)(dlg)
    return handler


def replay(qapp, g, rec_dir, tmp, menus, monkeypatch):
    """Replay the recording in *rec_dir*; returns (recording, final state, errors)."""
    with open(os.path.join(rec_dir, "recording.json"), encoding="utf-8") as f:
        d = json.load(f)
    sources = d.get("sources") or {}
    H.load(qapp, g, _start_figure(rec_dir, d, tmp))
    errors = []
    monkeypatch.setattr(sys, "excepthook", lambda t, v, tb: errors.append(f"{t.__name__}: {v}"))
    answers = []
    from pyfigures.gui import pfgui

    def picker(name):
        def pick(*a, **k):
            assert answers, f"{name}: no recorded answer"
            res = answers.pop(0)
            if res and name == "saveFileDialog":
                return os.path.join(str(tmp), os.path.basename(res))
            if isinstance(res, (list, tuple)):
                return [_mapped(rec_dir, sources, p) for p in res]
            return _mapped(rec_dir, sources, res) if res else res
        return pick
    for name in ("openFileNameDialog", "openFileNamesDialog", "saveFileDialog", "openDirectoryDialog"):
        if hasattr(pfgui, name):
            monkeypatch.setattr(pfgui, name, picker(name))
    steps = d["steps"]
    pilot = H.DialogPilot()
    try:
        for i, step in enumerate(steps):
            kind = step["kind"]
            if kind not in ACTIONABLE:
                continue
            # the dialogs and file pickers this step leads to, until the next step
            for later in steps[i + 1:]:
                if later["kind"] in ACTIONABLE:
                    break
                if later["kind"] == "dialog_close":
                    pilot.expect(later["title"] or later["cls"], _answer(later))
                elif later["kind"] == "file_dialog":
                    answers.append(later["result"])
            _do(qapp, g, menus, rec_dir, sources, steps, i)
            H.settle(qapp, g)
    finally:
        pilot.stop()
    return d, H.snapshot(g, tmp), errors + [f"unexpected dialog: {u}" for u in pilot.unexpected]


def _do(qapp, g, menus, rec_dir, sources, steps, i):
    step = steps[i]
    kind = step["kind"]
    nxt = next((s for s in steps[i + 1:] if s["kind"] in ACTIONABLE), None)
    if kind == "action":
        if step["key"].startswith("menu: Help > Debug"):
            return
        H.action(g, step["key"]).trigger()
    elif kind == "context":
        target = find_panel(g, step.get("selected"))
        H.right_click(g, menus, target, pos=None if target is not None else H.empty_point(g),
                      select=target is not None, pick=" / ".join(step["path"]))
    elif kind == "drop":
        target = find_panel(g, step.get("onto"))
        H.drop_files(g, [_mapped(rec_dir, sources, p) for p in step["files"]],
                     H.centre(g, target) if target is not None else None)
    elif kind == "drop_choice":
        H.click_drop_choice(g, step["label"])
    elif kind == "double_click":
        H.mouse(g, "double", H.centre(g, find_panel(g, step["panel"])))
    elif kind == "drag":
        if nxt is not None and nxt["kind"] == "drag_choice":
            menus.pick = " / ".join(nxt["path"])
        target = find_panel(g, step.get("onto"))
        s = H.panel(g).scale or 1
        to = H.centre(g, target) if target is not None else QPointF(step["to"][0] * s, step["to"][1] * s)
        H.drag(g, find_panel(g, step["panel"]), to)
        menus.pick = None
    elif kind == "key":
        seq = QKeySequence(step["key"])
        key = seq[0].key() if hasattr(seq[0], "key") else seq[0]
        for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(H.panel(g), QKeyEvent(t, key, Qt.KeyboardModifier.NoModifier))


def run_checks(d, state, errors):
    """Failures of the recording's checks: [{'rows': [...]}, {'panel': name,
    'projection': 'max', ...}, {'no_errors': true}, {'python': expr}] (expr
    sees ``state``, ``errors``)."""
    failed = []
    for chk in d.get("checks") or []:
        if "rows" in chk and state["rows"] != chk["rows"]:
            failed.append(f"rows {state['rows']} != {chk['rows']}")
        if chk.get("no_errors") and errors:
            failed.append(f"errors: {errors}")
        if "panel" in chk:
            hits = [p for p in state["panels"] if p["name"] == chk["panel"]]
            if not hits:
                failed.append(f"no panel {chk['panel']}")
            for k, v in chk.items():
                if k != "panel" and hits and hits[0].get(k) != v:
                    failed.append(f"{chk['panel']} {k} = {hits[0].get(k)!r}, expected {v!r}")
        if "python" in chk and not eval(chk["python"], {}, {"state": state, "errors": errors}):
            failed.append(f"check failed: {chk['python']}")
    return failed
