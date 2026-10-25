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
           "assistant_actions", "advanced_annotations", "live_mcp", "session", "launch"]


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


def test_advanced_text_and_roi_edits_on_the_live_figure(qapp, gui, runtime, tmp_path):
    """ChatGPT's live advanced editing, as ported: one word of a text, a ROI's
    outline/fill, stale tokens refused, one undo step each."""
    import uuid
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.assistant import launch
    from pyfigures.assistant.advanced_annotations import describe
    from pyfigures.assistant.partner_gui import panels
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))

    def panel():
        return next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    p = panel()
    text = TAText2D('<span style="color:#ffffff">CO2 and <i>control</i></span>')
    p.annotations.append(text)
    ti = len(p.annotations) - 1
    token = describe(text)["token"]
    out = cmd("edit_annotation_properties", panel_ref="0/0",annotation_index=ti, token=token,
              changes={"bold": True}, substring="CO2")
    assert out["changed"]
    assert text.doc.find("CO2").charFormat().fontWeight() > 400
    control = text.doc.find("control").charFormat()
    assert control.fontItalic() and control.foreground().color().name() == "#ffffff"
    with pytest.raises(ValueError, match="STALE_ANNOTATION"):
        cmd("edit_annotation_properties", panel_ref="0/0",annotation_index=ti, token=token,
            changes={"color": "red"})
    cmd("undo")
    assert panel().annotations[ti].doc.find("CO2").charFormat().fontWeight() < 600
    both = TAText2D("treated and untreated")       # "treated" is a word of its own only once
    panel().annotations.append(both)
    bi = len(panel().annotations) - 1
    assert cmd("edit_annotation_properties", panel_ref="0/0", annotation_index=bi, token=describe(both)["token"],
               changes={"bold": True}, substring="treated")["changed"]
    assert both.doc.find("treated").charFormat().fontWeight() > 400
    assert both.doc.find("untreated").charFormat().fontWeight() < 600
    cmd("edit_annotation_properties", panel_ref="0/0", annotation_index=bi, token=describe(both)["token"],
        changes={"italic": True}, substring="treated", occurrence="all")
    assert both.doc.find("treated").charFormat().fontItalic()
    in_untreated = both.doc.find("treated", both.doc.find("untreated").selectionStart())
    assert in_untreated.charFormat().fontItalic() and both.doc.toPlainText() == "treated and untreated"
    twice = TAText2D("control vs control")
    panel().annotations.append(twice)
    with pytest.raises(ValueError, match="CLARIFICATION_REQUIRED"):
        cmd("edit_annotation_properties", panel_ref="0/0", annotation_index=len(panel().annotations) - 1,
            token=describe(twice)["token"], changes={"bold": True}, substring="control")
    roi = Rectangle2D(5, 6, 30, 40, color=0xffffff, fill_color=0x333333, stroke=2)
    panel().annotations.append(roi)
    ri = len(panel().annotations) - 1
    cmd("edit_annotation_properties", panel_ref="0/0",annotation_index=ri, token=describe(roi)["token"],
        changes={"stroke": 3, "fill_color": "none"})
    assert roi.stroke == 3 and roi.fill_color is None and roi.width() == 30 and roi.color == 0xffffff


def test_edits_while_the_image_editor_is_open_go_into_its_draft(qapp, gui, runtime, tmp_path):
    """With the panel's annotation editor open, an edit changes the editor's
    draft only (OK/Cancel still decide); a rectangle has no properties dialog
    and is refused by name; an inset's properties open inside that editor."""
    import time
    import uuid
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication, QDialog
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from pyfigures.assistant import launch
    from pyfigures.assistant.advanced_annotations import describe, inspect_objects
    from pyfigures.assistant.partner_gui import panels
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))

    def panel():
        return next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))

    def dialogs():
        return {d.windowTitle(): d for d in QApplication.topLevelWidgets() if isinstance(d, QDialog) and d.isVisible()}
    panel().annotations.append(Rectangle2D(5, 6, 20, 15, color=0xFF0000, fill_color=0x333333))
    cmd("roi_to_inset", panel_ref="0/0")
    panel().annotations.append(Rectangle2D(2, 3, 10, 10, color=0x00FF00, fill_color=0x333333))
    kinds = [type(a).__name__ for a in panel().annotations]
    inset, box = kinds.index("Image2D"), len(kinds) - 1
    cmd("open_annotation_editor", panel_ref="0/0")
    seen = {}

    def in_editor():
        if "Annotate the image" not in dialogs():
            QTimer.singleShot(50, in_editor)
            return
        try:
            token = next(o["token"] for o in inspect_objects(session, "0/0")["objects"] if o["annotation_index"] == box)
            seen["edit"] = cmd("edit_annotation_properties", panel_ref="0/0", annotation_index=box,
                               token=token, changes={"fill_color": "none"})
            seen["main_fill"] = panel().annotations[box].fill_color
            token = next(o["token"] for o in inspect_objects(session, "0/0")["objects"] if o["annotation_index"] == box)
            try:
                cmd("open_annotation_properties", panel_ref="0/0", annotation_index=box, token=token)
            except ValueError as e:
                seen["refused"] = str(e)
            token = next(o["token"] for o in inspect_objects(session, "0/0")["objects"] if o["annotation_index"] == inset)
            cmd("open_annotation_properties", panel_ref="0/0", annotation_index=inset, token=token)
        except Exception as e:
            seen["error"] = repr(e)
        QTimer.singleShot(50, close_inset)

    def close_inset():
        d = dialogs()
        if "Edit Inset" in d:
            seen["inset_dialog"] = True
            d["Edit Inset"].reject()
        elif time.time() - t0 < 5:
            QTimer.singleShot(50, close_inset)
            return
        QTimer.singleShot(50, lambda: [d.reject() for t, d in dialogs().items() if t == "Annotate the image"])
    t0 = time.time()
    QTimer.singleShot(50, in_editor)
    while (time.time() - t0 < 10) and ("inset_dialog" not in seen or dialogs()):
        qapp.processEvents()
        time.sleep(0.01)
    assert "error" not in seen, seen
    assert seen["edit"]["target"] == "editor_draft" and seen["edit"]["changed"] and not seen["edit"]["document_changed"]
    assert seen["main_fill"] is not None                  # the figure waits for OK
    assert "Rectangle2D" in seen["refused"] and f"{inset} (inset)" in seen["refused"]
    assert seen.get("inset_dialog")
    assert not dialogs()
    assert panel().annotations[box].fill_color is not None  # Cancel dropped the draft


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
    # a plain window asks before handing its figure over; Cancel changes nothing
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    g.share_figure_action.trigger()
    assert not g.share_figure_action.isChecked() and not (runtime / "connection.json").exists()
    assert g.open_chat_sidebar() is None and not (runtime / "connection.json").exists()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Ok)
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
    # the task guides win over the word routes (rectangle -> edit_roi, text -> edit_text…)
    for question, guide in [
            ("Where do I draw a rectangle with an outline and no filled interior?", "draw_roi"),
            ("How can I remove a magnified inset while leaving its rectangle on the original image?",
             "remove_inset"),
            ("How do I make a maximum-intensity projection from a Z stack?", "max_projection"),
            ("How can I reconnect a missing image after moving its folder?", "remap_images"),
            ("How do I export slides with editable text rather than one flattened screenshot?",
             "export_pptx"),
            ("How do I make the outline of the existing box thicker?", "edit_roi"),
            ("How do I put the 2 in CO2 in subscript?", "edit_text"),
            ("How do I resize an existing inset?", "edit_inset")]:
        assert explain(question)["guide"] == guide, question


def test_live_mcp_server_builds_its_tools():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(live_mcp.mcp, live_mcp.request)
    assert server is not None and live_mcp.ORIGINAL_TOOL_COUNT > 100
