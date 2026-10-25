"""pyfigures.assistant: the open figure editor shared with the MCP server
(live_mcp) and the optional qtpy_ai_sidecar chat. Tools > Share the open
figure…, Tools > Chat sidebar…, `--share` / `--chat` on the command line.

Run with PYTEST_QT_API=pyqt6. One Qt process at a time.
"""
from __future__ import annotations

import importlib
import json
import os
import threading

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

MODULES = ["categorized_mcp", "existing_tools", "original_registry", "partner_gui", "figure_state",
           "gui_selection", "letter_sequence", "live_structure", "plot_lifecycle", "pointer_context",
           "readability", "recovery", "submission_review", "manual_help", "native_gui",
           "assistant_actions", "live_mcp", "session", "launch"]


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    """Connection file, recovery copies and workspaces in a throw-away folder."""
    monkeypatch.setenv("PYFIGURES_LIVE_RUNTIME", str(tmp_path / "runtime"))
    from pyfigures.assistant import session
    monkeypatch.setattr(session, "STATE", tmp_path / "runtime")
    (tmp_path / "runtime").mkdir(exist_ok=True)
    return tmp_path / "runtime"


@pytest.fixture
def gui(qapp, runtime):
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.assistant.partner_gui import PartnerGUI
    EZFIG_GUI.show_tips = lambda self: None
    before = set(map(id, qapp.topLevelWidgets()))

    def make(shareable=False):
        return PartnerGUI() if shareable else EZFIG_GUI()
    yield make
    from pyfigures.assistant.launch import stop_live_session
    # every editor window opened here, the ones a handover created included
    for g in qapp.topLevelWidgets():
        if isinstance(g, EZFIG_GUI) and id(g) not in before:
            stop_live_session(g)
            g._dirty = False
            g.close()
    qapp.processEvents()


def _call(qapp, operation, **kw):
    """live_mcp.request from another thread (the bridge answers on the Qt thread)."""
    from pyfigures.assistant import live_mcp
    box = {}

    def run():
        try:
            box["result"] = live_mcp.request(operation, **kw)
        except Exception as e:
            box["error"] = e
    t = threading.Thread(target=run)
    t.start()
    while t.is_alive():
        qapp.processEvents()
        t.join(0.02)
    if "error" in box:
        raise box["error"]
    return box["result"]


def _figure(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    for name in "ab":
        p = str(tmp_path / f"{name}.tif")
        Img((np.random.default_rng(ord(name)).random((40, 50)) * 255).astype(np.uint8), dimensions="hw").save(p)
        add_image(pyf, [0], p)
    return pyf


def test_every_ported_module_imports():
    for name in MODULES:
        importlib.import_module("pyfigures.assistant." + name)


def test_runtime_folder_is_outside_the_repository(monkeypatch):
    from pyfigures.assistant import runtime_dir
    monkeypatch.delenv("PYFIGURES_LIVE_RUNTIME", raising=False)
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = str(runtime_dir())
    assert not path.startswith(repo) and path.endswith(os.path.join("PyFigures", "assistant"))


def test_share_edit_undo_and_stop(qapp, gui, runtime):
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    session = launch.start_live_session(g)
    assert session.window is g and launch.is_sharing(g)
    descriptor = json.loads((runtime / "connection.json").read_text(encoding="utf-8"))
    assert descriptor["url"].startswith("http://127.0.0.1:") and descriptor["session_id"] == session.id
    state = _call(qapp, "inspect")
    assert state["session_id"] == session.id and state["objects"] == []
    after = _call(qapp, "add_label", session_id=state["session_id"], expected_revision=state["revision"],
                  arguments={"text": "live <hello>"}, request_id="r1")
    assert [o["text"] for o in after["objects"]] == ["live <hello>"]          # escaped, plain text
    assert len(g.paint.EZFIG_panel.shapes_to_draw) == 1 and g._dirty
    with pytest.raises(ValueError, match="REVISION_CONFLICT"):
        _call(qapp, "add_label", session_id=state["session_id"], expected_revision=state["revision"],
              arguments={"text": "stale"}, request_id="r2")
    undone = _call(qapp, "undo", session_id=after["session_id"], expected_revision=after["revision"],
                   request_id="r3")
    assert undone["objects"] == [] and g.paint.EZFIG_panel.shapes_to_draw == []
    assert launch.stop_live_session(g) and not launch.is_sharing(g)
    assert not (runtime / "connection.json").exists()
    with pytest.raises(ValueError, match="GUI_OFFLINE"):
        _call(qapp, "inspect")


def test_a_plain_window_hands_its_figure_over(qapp, gui, runtime, tmp_path):
    """A Qt window cannot change class: sharing a plain editor opens a
    shareable one with the same figure, file, unsaved state and undo history."""
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import PartnerGUI
    g = gui()
    pyf = _figure(tmp_path)
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    g.save_state(show_popup=False)
    g.paint.EZFIG_panel.shapes_to_draw[0].content.pop()       # an unsaved, undoable change
    g.paint.EZFIG_panel.update()
    g.save_state(show_popup=False)
    g._mark_dirty()
    n_undo = len(g.undo_stack)
    w = launch.start_live_session(g).window
    assert isinstance(w, PartnerGUI) and w is not g and launch.is_sharing(w)
    assert w.current_file == pyf and w._dirty and len(w.undo_stack) == n_undo
    assert len(w.paint.EZFIG_panel.shapes_to_draw[0].content) == 1
    assert all(os.path.isfile(p) and p.startswith(w.temp_dir.name) for p in w.undo_stack)
    w.undo()
    assert len(w.paint.EZFIG_panel.shapes_to_draw[0].content) == 2           # the old history works
    assert not g.isVisible()


def test_one_window_shares_at_a_time(qapp, gui, runtime):
    from pyfigures.assistant import launch
    first, second = gui(shareable=True), gui(shareable=True)
    launch.start_live_session(first)
    with pytest.raises(RuntimeError, match="Another PyFigures window"):
        launch.start_live_session(second)
    assert not launch.is_sharing(second)
    launch.stop_live_session(first)
    launch.start_live_session(second)
    assert launch.is_sharing(second)


def test_closing_the_window_stops_sharing(qapp, gui, runtime):
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    launch.start_live_session(g)
    g._dirty = False
    g.close()
    qapp.processEvents()
    assert not launch.is_sharing(g) and not (runtime / "connection.json").exists()


def test_tools_menu_share_toggle(qapp, gui, runtime, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self.detailedText()) or 0)
    g = gui()
    g.share_figure_action.trigger()
    w = next(x for x in qapp.topLevelWidgets() if getattr(x, "_live_server", None) is not None)
    assert w.share_figure_action.isChecked() and (runtime / "connection.json").exists()
    config = json.loads(shown[0])["mcpServers"]["pyfigures-live"]
    assert config["args"] == ["-m", "pyfigures.assistant.live_mcp"]
    assert config["env"]["PYFIGURES_LIVE_RUNTIME"] == str(runtime)
    w.share_figure_action.trigger()
    assert not w.share_figure_action.isChecked() and not (runtime / "connection.json").exists()


def test_chat_sidebar_without_the_package_says_how_to_install(qapp, gui, runtime, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    import pyfigures.assistant as A
    said = []
    monkeypatch.setattr(A, "sidecar_available", lambda: False)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: said.append(a[2]))
    g = gui()
    assert g.open_chat_sidebar() is None
    assert "pip install qtpy-ai-sidecar" in said[0] and not g.share_figure_action.isChecked()


@pytest.mark.skipif(not __import__("pyfigures.assistant", fromlist=["x"]).sidecar_available(),
                    reason="qtpy_ai_sidecar not installed")
def test_chat_sidebar_docks_the_sidecar(qapp, gui, runtime):
    from qtpy.QtCore import Qt
    g = gui(shareable=True)
    dock = g.open_chat_sidebar()
    assert dock is not None and dock.parent() is g and not dock.isFloating()
    assert g.dockWidgetArea(dock) == Qt.DockWidgetArea.RightDockWidgetArea
    assert g.share_figure_action.isChecked()
    from pyfigures.assistant.launch import sidecar_config
    config = sidecar_config()
    assert config.servers["pyfigures"]["args"] == ["-m", "pyfigures.assistant.live_mcp"]
    assert config.adapter["descriptor"] == str(runtime / "connection.json")
    assert g.open_chat_sidebar() is dock                      # a second click shows the same dock


def test_launch_flags(qapp, gui, runtime):
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    assert launch.apply_launch_flags(g, ["--share"]) is g and launch.is_sharing(g)
    assert launch.apply_launch_flags(g, []) is g


def test_how_to_questions_use_the_authored_guides():
    from pyfigures.assistant.manual_help import explain
    r = explain("how do I stack an image under another one in a row")
    assert r["status"] == "explained" and r["guide"] == "stack_in_row" and not r["operation_executed"]
    r = explain("add an arrowhead")
    assert r["guide"] == "arrowheads"


def test_live_mcp_server_builds_its_tools():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(live_mcp.mcp, live_mcp.request)
    assert server is not None and live_mcp.ORIGINAL_TOOL_COUNT > 100
