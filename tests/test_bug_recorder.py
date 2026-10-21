"""Help > Debug > Record a bug (pyfigures/gui/bug_recorder.py): real user
events (sent through the application, as a mouse or a drop would) are logged
as replayable steps with the figure after each, an exception is caught, the
recording is saved in the user's folder (outside the repository), the MCP
server and the CLI read it, and make-test + the replayer give back the same
figure from tiny stand-in images."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import QMimeData, QPointF, Qt, QUrl
from qtpy.QtGui import QDropEvent
from qtpy.QtWidgets import QApplication, QPushButton

import gui_e2e_harness as H
from gui_e2e_harness import menus  # noqa: F401
import recording_replay as R
from pyfigures.gui import bug_recorder as B


def _png(path, value, shape=(60, 80)):
    from PIL import Image
    Image.fromarray(np.full(shape, value, np.uint8)).save(path)
    return str(path)


@pytest.fixture
def gui(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(B, "recordings_dir", lambda: str(tmp_path / "recordings"))
    g = H.new_gui(qapp)
    yield g
    if getattr(g, "_bug_recorder", None) is not None and g._bug_recorder.active:
        g._bug_recorder.stop(ask=False)
    g._mark_clean()
    H.close_gui(qapp, g)


def _drop(g, paths):
    """A drop delivered through the application (event filters see it)."""
    from qtpy.QtGui import QDragEnterEvent, QDragMoveEvent
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(p) for p in paths])
    pos = H.window_pos(g, H.empty_point(g))
    for cls in (QDragEnterEvent, QDragMoveEvent):
        QApplication.sendEvent(g, cls(pos.toPoint(), Qt.DropAction.CopyAction, mime,
                                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    ev = QDropEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(g, ev)
    for _ in range(5):
        QApplication.processEvents()
    g._keep_mime = mime


def _click(button):
    from qtpy.QtTest import QTest
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    QApplication.processEvents()


def _record_a_session(qapp, g, tmp_path):
    a = _png(tmp_path / "a.png", 40)
    g.start_bug_recording()
    rec = g._bug_recorder
    assert rec.active and g.stop_record_action.isEnabled() and not g.record_bug_action.isEnabled()
    _drop(g, [a])
    btn = next(b for b in H.drop_menu(g).findChildren(QPushButton) if b.text() == "➕  As single image(s)")
    _click(btn)
    H.settle(qapp, g, lambda: len(H.images(g)) == 1)
    QApplication.processEvents()
    rec._snapshot()
    return rec, a


def test_recordings_live_outside_the_repository():
    folder = B.recordings_dir()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert not os.path.abspath(folder).startswith(repo)
    assert folder.endswith(os.path.join("PyFigures", "recordings"))


def test_a_session_is_recorded_as_replayable_steps(qapp, gui, tmp_path):
    rec, a = _record_a_session(qapp, gui, tmp_path)
    folder = gui.stop_bug_recording(ask=False)
    assert folder and not gui._bug_recorder.active and gui.record_bug_action.isEnabled()
    d = json.load(open(os.path.join(folder, "recording.json"), encoding="utf-8"))
    kinds = [s["kind"] for s in d["steps"]]
    assert kinds[:3] == ["start", "drop", "drop_choice"], kinds
    drop = d["steps"][1]
    assert drop["files"] == [a.replace("\\", "/")] or [os.path.normpath(p) for p in drop["files"]] == [a]
    assert d["steps"][2]["label"] == "➕  As single image(s)"
    assert d["steps"][2]["state"]["rows"] and "a.png" in d["steps"][2]["state"]["rows"][0]
    assert os.path.isfile(os.path.join(folder, d["steps"][2]["screenshot"]))
    assert os.path.isfile(os.path.join(folder, "start.pyf"))
    assert d["sources"][next(iter(d["sources"]))] == "files/a.png"        # the dropped file is kept
    assert d["status"] == "open" and d["notes"] == {"what_went_wrong": "", "expected": "", "bad_steps": []}


def test_menu_clicks_and_exceptions_are_steps(qapp, gui, tmp_path):
    from qtpy.QtTest import QTest
    rec, _ = _record_a_session(qapp, gui, tmp_path)
    edit = next(m.menu() for m in gui.menuBar.actions() if m.text() == "Edit")
    edit.popup(gui.mapToGlobal(gui.rect().center()))
    QApplication.processEvents()
    undo = next(a for a in edit.actions() if a.text().split("\t")[0].lower().startswith("undo"))
    QTest.mouseClick(edit, Qt.MouseButton.LeftButton, pos=edit.actionGeometry(undo).center())
    QApplication.processEvents()
    saved = rec._saved["excepthook"]
    rec._saved["excepthook"] = lambda *a: None           # (pytest-qt would fail the test)
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec._excepthook(*sys.exc_info())
    finally:
        rec._saved["excepthook"] = saved
    steps = rec.steps
    assert any(s["kind"] == "action" and s["key"].startswith("menu: Edit > Undo") for s in steps), \
        [(s["kind"], s.get("key")) for s in steps]
    err = [s for s in steps if s["kind"] == "exception"]
    assert err and err[0]["error"] == "ValueError: boom" and "raise ValueError" in err[0]["traceback"]


def test_report_dialog_notes_and_discard(qapp, gui, tmp_path, monkeypatch):
    rec, _ = _record_a_session(qapp, gui, tmp_path)
    monkeypatch.setattr(B, "ask_report", lambda parent, r: {"what_went_wrong": "no letter",
                                                            "expected": "letter a", "bad_steps": [3]})
    folder = rec.stop(ask=True)
    d = json.load(open(os.path.join(folder, "recording.json"), encoding="utf-8"))
    assert d["notes"]["what_went_wrong"] == "no letter" and d["notes"]["bad_steps"] == [3]
    rec2, _ = _record_a_session(qapp, gui, tmp_path)
    monkeypatch.setattr(B, "ask_report", lambda parent, r: None)          # Discard
    assert rec2.stop(ask=True) is None and not os.path.exists(rec2.folder)


def test_quitting_while_recording_saves_it(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(B, "recordings_dir", lambda: str(tmp_path / "recordings"))
    g = H.new_gui(qapp)
    rec, _ = _record_a_session(qapp, g, tmp_path)
    g._mark_clean()
    H.close_gui(qapp, g)
    assert not rec.active and os.path.isfile(os.path.join(rec.folder, "recording.json"))


def test_mcp_and_cli_read_recordings(qapp, gui, tmp_path, capsys):
    rec, _ = _record_a_session(qapp, gui, tmp_path)
    folder = gui.stop_bug_recording(ask=False)
    import pyfigures.mcp_server as M
    listed = json.loads(M.list_bug_recordings(str(tmp_path / "recordings")))
    assert listed["recordings"][0]["path"] == folder and listed["recordings"][0]["steps"] >= 3
    one = json.loads(M.read_bug_recording(folder))
    assert one["steps"][1]["describe"].startswith("drop a.png")
    assert M.read_bug_recording(str(tmp_path / "nope")).startswith("ERROR")
    assert B.main(["show", folder]) == 0
    assert "drop menu: ➕  As single image(s)" in capsys.readouterr().out


def test_make_test_and_replay_give_back_the_figure(qapp, gui, tmp_path, menus, monkeypatch):
    big = _png(tmp_path / "big.png", 200, shape=(1200, 900))
    gui.start_bug_recording()
    rec = gui._bug_recorder
    _drop(gui, [big])
    _click(next(b for b in H.drop_menu(gui).findChildren(QPushButton) if b.text() == "➕  As single image(s)"))
    H.settle(qapp, gui, lambda: len(H.images(gui)) == 1)
    folder = gui.stop_bug_recording(ask=False)
    recorded_rows = rec.steps[-1]["state"]["rows"]
    out = tmp_path / "tests_rec" / "big_drop"
    B.make_test(folder, str(out))
    from PIL import Image
    small = Image.open(out / "files" / "big.png")
    assert max(small.size) <= 256                                       # a tiny stand-in, not the original
    d = json.load(open(out / "recording.json", encoding="utf-8"))
    assert not any("screenshot" in s for s in d["steps"])
    d["checks"] = [{"rows": recorded_rows}, {"no_errors": True}]
    json.dump(d, open(out / "recording.json", "w", encoding="utf-8"))
    g2 = H.new_gui(qapp)
    try:
        d2, state, errors = R.replay(qapp, g2, str(out), tmp_path, menus, monkeypatch)
        assert R.run_checks(d2, state, errors) == []
    finally:
        g2._mark_clean()
        gui._mark_clean()            # close_gui closes every other window too
        H.close_gui(qapp, g2)


def test_help_menu_entries(gui):
    keys = [k for k, _ in H.menu_actions(gui)]
    for k in ("menu: Help > Debug > Start recording a bug…",
              "menu: Help > Debug > Stop recording and describe the bug…",
              "menu: Help > Debug > Open the recordings folder"):
        assert k in keys, k
    assert gui.open_bug_recordings_folder() == B.recordings_dir()
