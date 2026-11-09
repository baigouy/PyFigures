"""Tools > Chat in a web page: an online chat page (no API) edits the figure.
The model writes PYFIGURES-CALLS blocks, the panel finds them in the page
text (any site), runs them when the user clicks Apply (look-ups by
themselves) and puts the results into the chat box.

Clipboard mode here (no Qt WebEngine offscreen); the page's own reading and
writing is JavaScript run by the same code paths. Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures.assistant import web_chat
from test_assistant_live import _figure, gui, runtime  # noqa: E402,F401  (fixtures)


@pytest.fixture(autouse=True)
def own_settings(monkeypatch):
    """The panel's settings in a test-only store: the user's own choices
    (Automatic ticked, their chat address) must neither change the tests nor
    be changed by them."""
    from qtpy.QtCore import QSettings
    import pyfigures.gui.web_chat_panel as wcp
    QSettings("PyFigures-tests", "web_chat").clear()
    monkeypatch.setattr(wcp, "QSettings", lambda org, app: QSettings(org + "-tests", app))
    yield
    QSettings("PyFigures-tests", "web_chat").clear()


def _reply(calls, before="Here is what I will do.", noise=""):
    return (f"{before}\n{web_chat.BEGIN}\n{noise}{json.dumps(calls)}\n{web_chat.END}\n")


def test_blocks_are_read_from_any_page_text():
    calls = [{"tool": "find_pyfigures_tools", "arguments": {"query": "scale bar"}}]
    (block,) = web_chat.parse_blocks(_reply(calls))
    assert block.error is None and block.calls == calls and block.read_only
    # a page's code block puts its own words around the JSON
    (block,) = web_chat.parse_blocks(_reply(calls, noise="json\nCopy code\n"))
    assert block.calls == calls
    # smart quotes and a trailing comma, as models write them in a chat
    text = f'{web_chat.BEGIN}\n[{{“tool”: “inspect_figure”, “arguments”: {{}},}}]\n{web_chat.END}'
    (block,) = web_chat.parse_blocks(text)
    assert block.calls == [{"tool": "inspect_figure", "arguments": {}}]
    # an inner operation called by its own name goes through the dispatcher
    (block,) = web_chat.parse_blocks(_reply([{"tool": "set_lut", "arguments": {"luts": ["RED"]}}]))
    assert block.calls == [{"tool": "use_pyfigures_tool",
                            "arguments": {"tool_name": "set_lut", "arguments": {"luts": ["RED"]}}}]
    assert not block.read_only
    # broken JSON is reported, not run
    (block,) = web_chat.parse_blocks(f"{web_chat.BEGIN}\n[{{tool: oops\n{web_chat.END}")
    assert block.error and not block.calls
    # an unfinished (still streaming) block is not read yet
    assert web_chat.parse_blocks(f"{web_chat.BEGIN}\n[{{\"tool\": \"inspect_figure\"") == []


def test_the_instructions_contain_no_block_of_their_own():
    tools = [{"name": "inspect_figure", "description": "Read the figure.", "inputSchema": {"type": "object"}}]
    prompt = web_chat.instructions_prompt(tools, "Guidance.", {"panels": 2})
    assert web_chat.BEGIN in prompt and web_chat.END in prompt and "inspect_figure" in prompt
    # once sent, the prompt is on the page: its example must not become a request
    assert web_chat.parse_blocks(prompt) == []
    # it says the chat's own tools cannot reach PyFigures (Vibe's code session tried them)
    assert "do not use any tool" in prompt
    # nor do the results written back, which remind the model of the block every time
    call = {"tool": "inspect_figure", "arguments": {}}
    results = web_chat.results_message([(call, True, '{"panels": 2}')])
    assert web_chat.parse_blocks(results) == [] and "marker lines" in results


def _wait(qapp, condition, timeout=60):
    end = time.time() + timeout
    while not condition():
        assert time.time() < end, "timed out"
        qapp.processEvents()
        time.sleep(0.01)


def test_a_round_with_the_figure(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    from qtpy.QtWidgets import QApplication
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.gui.web_chat_panel import WebChatPanel
    from pyfigures.assistant.partner_gui import panels
    monkeypatch.setattr("pyfigures.gui.web_chat_panel.QDesktopServices.openUrl", lambda *a: True)
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path, channels=3), append=False)
    dock = g.open_web_chat(use_web=False)
    assert dock is not None and g.web_chat_dock is dock and g.share_figure_action.isChecked()
    assert g.open_web_chat(use_web=False) is dock           # a second click shows the same dock
    panel = dock.widget()
    assert isinstance(panel, WebChatPanel) and panel.view is None
    clip = QApplication.clipboard()

    # Start: instructions, operations and the figure, ready to paste
    clip.setText("")
    panel.start()
    _wait(qapp, lambda: not panel.busy)
    first = clip.text()
    assert "find_pyfigures_tools" in first and "use_pyfigures_tool" in first and "panel_references" in first
    assert "paste it into the chat" in panel.status.text()

    # a look-up runs by itself and its results are ready for the next Send
    panel.read_text(_reply([{"tool": "find_pyfigures_tools", "arguments": {"query": "lut"}}]))
    _wait(qapp, lambda: not panel.busy and web_chat.RESULTS in clip.text())
    assert "set_lut" in clip.text() and "-> OK" in clip.text()
    assert not panel.pending

    # an edit waits for Apply
    first_panel = [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0]
    edit = [{"tool": "set_lut", "arguments": {"group_path": [0], "image_index": 0,
                                              "luts": [None, "YELLOW", None]}}]
    panel.read_text(_reply(edit))
    assert panel.pending and panel.apply_button.isEnabled()
    assert "set_lut" in panel.request_box.toPlainText()
    assert (first_panel.LUTs or [None, None])[1] != "YELLOW"
    # the same answer read again (the page is scanned repeatedly) is not asked twice
    panel.read_text(_reply(edit))
    assert len(panel.pending) == 1
    # …but the model asking for the very same operations again later is (the
    # page then shows the block twice): a repeat was skipped before
    panel.read_text(_reply(edit) + "\nresults…\n" + _reply(edit))
    assert len(panel.pending) == 2
    panel.read_text(_reply(edit) + "\nresults…\n" + _reply(edit))
    assert len(panel.pending) == 2
    panel.pending.pop()
    clip.setText("")
    panel.apply()
    _wait(qapp, lambda: not panel.busy and clip.text())
    assert "-> OK" in clip.text(), clip.text()
    first_panel = [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0]
    assert first_panel.LUTs[1] == "YELLOW"
    assert not panel.pending and not panel.apply_button.isEnabled()

    # Dismiss: nothing runs, the chat is told
    panel.read_text(_reply([{"tool": "undo_redo", "arguments": {"action": "undo"}}]))
    panel.dismiss()
    assert "did not run" in clip.text()
    assert [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0].LUTs[1] == "YELLOW"

    # an unreadable block: Apply is off, Dismiss asks the model to write it again
    panel.read_text(f"{web_chat.BEGIN}\n[{{tool: oops\n{web_chat.END}")
    assert panel.pending and not panel.apply_button.isEnabled() and panel.dismiss_button.isEnabled()
    panel.dismiss()
    assert "could not be read" in clip.text()

    # a failed edit is reported to the chat, and the next call of its block is not run
    panel.read_text(_reply([{"tool": "set_lut", "arguments": {"no_such_argument": 1}},
                            {"tool": "undo_redo", "arguments": {"action": "undo"}}]))
    clip.setText("")
    panel.apply()
    _wait(qapp, lambda: not panel.busy and clip.text())
    assert "-> ERROR" in clip.text() and "Not run" in clip.text()
    assert [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0].LUTs[1] == "YELLOW"
    assert isinstance(g, EZFIG_GUI)


def test_automatic_mode_applies_without_a_click(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    from qtpy.QtWidgets import QApplication
    from qtpy.QtCore import QSettings
    from pyfigures.gui import web_chat_panel as wcp
    from pyfigures.assistant.partner_gui import panels
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    settings = QSettings("PyFigures-tests", "web_chat")
    saved = settings.value("automatic")
    try:
        g = gui(shareable=True)
        g.reload_state(_figure(tmp_path, channels=3), append=False)
        panel = g.open_web_chat(use_web=False).widget()
        panel.automatic.setChecked(True)
        clip = QApplication.clipboard()
        # the first request from the panel carries the instructions and the figure
        panel.ask_edit.setText("make channel 2 yellow in a")
        panel.ask()
        _wait(qapp, lambda: not panel.busy)
        assert panel.started and "My request: make channel 2 yellow in a" in clip.text()
        assert "panel_references" in clip.text() and panel.rounds_left == wcp.MAX_ROUNDS
        # an edit is applied with no click
        panel.read_text(_reply([{"tool": "set_lut", "arguments": {"group_path": [0], "image_index": 0,
                                                                  "luts": [None, "YELLOW", None]}}]))
        _wait(qapp, lambda: not panel.busy and web_chat.RESULTS in clip.text())
        assert [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0].LUTs[1] == "YELLOW"
        assert panel.rounds_left == wcp.MAX_ROUNDS - 1
        # the next request goes without the instructions again
        panel.ask_edit.setText("now undo it")
        panel.ask()
        assert clip.text() == "now undo it"
        # Stop: what comes next waits for a click
        panel.stop()
        panel.read_text(_reply([{"tool": "undo_redo", "arguments": {"action": "undo"}}]))
        assert panel.pending and panel.apply_button.isEnabled()
        assert [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)][0].LUTs[1] == "YELLOW"
        # the round limit pauses it the same way
        panel.stop()
        panel.stopped = False
        panel.rounds_left = 0
        panel.read_text(_reply([{"tool": "undo_redo", "arguments": {"action": "redo"}}]))
        assert panel.pending and "Paused" in panel.status.text()
        panel.stop()
        # requests typed on the page itself (not in the panel) run automatically too:
        # ticking Automatic is enough, and a quiet page starts a new run
        panel.automatic.setChecked(False)
        panel.automatic.setChecked(True)
        assert panel.rounds_left == wcp.MAX_ROUNDS
        clip.setText("")
        panel.read_text(_reply([{"tool": "inspect_figure", "arguments": {}}], before="page request 1"))
        _wait(qapp, lambda: not panel.busy and web_chat.RESULTS in clip.text())
        panel.rounds_left = 0                     # this run used its rounds…
        for _ in range(wcp.IDLE_SCANS + 1):
            panel._idle_check("the same page")    # …and the chat went quiet
        assert panel.rounds_left == wcp.MAX_ROUNDS
        # after Stop, a quiet page does not restart it
        panel.stop()
        for _ in range(wcp.IDLE_SCANS + 1):
            panel._idle_check("the same page")
        assert panel.rounds_left == 0
    finally:
        if saved is None:
            settings.remove("automatic")
        else:
            settings.setValue("automatic", saved)


def test_launch_flag_docks_the_web_chat(qapp, gui, runtime, monkeypatch):  # noqa: F811
    from pyfigures.assistant import launch
    import pyfigures.gui.web_chat_panel as wcp
    monkeypatch.setattr(wcp, "web_engine", lambda: "not in tests")
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    g = gui(shareable=True)
    w = launch.apply_launch_flags(g, ["--web-chat"])
    assert launch.is_sharing(w) and w.web_chat_dock.widget().view is None


def test_typed_addresses_are_remembered(qapp, gui, runtime, monkeypatch):  # noqa: F811
    import pyfigures.gui.web_chat_panel as wcp
    from qtpy.QtCore import QSettings
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    settings = QSettings("PyFigures-tests", "web_chat")
    saved = {k: settings.value(k) for k in ("url", "urls")}
    try:
        g = gui(shareable=True)
        panel = g.open_web_chat(use_web=False).widget()
        panel.address.setEditText("emmy.example.org/chat")
        panel.go()
        assert settings.value("url") == "https://emmy.example.org/chat"
        assert "https://emmy.example.org/chat" in json.loads(settings.value("urls"))
        again = wcp.WebChatPanel(g, use_web=False)
        assert again.url() == "https://emmy.example.org/chat"
    finally:
        for k, v in saved.items():
            if v is None:
                settings.remove(k)
            else:
                settings.setValue(k, v)
