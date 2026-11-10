"""User reports 2026-11-10, from a chat on a nine-panel figure.
- A CT scan (597 µm per pixel): "100 µm" gave a bar shorter than a pixel, and
  "100 mm" a 100 µm bar labelled 100 mm (the unit was only a label): a label
  without a bar. A bar in mm is now 100 mm long, one under a pixel is refused.
- "Open it for me" (rotate G) opened the panel editor on Annotations: the tab
  was named in the routes, not in editor_tab.
- Panel G's capital, white letter came back as a black "g" after the editor:
  the edited clone had lost the letter's own text and style.
- The toolbar's first-letter box showed "a" above a figure lettered A, B, C.
- "Add a black bg to g" coloured the letter's box, not the panel.
- Web chat audit fixes (see test_web_chat_20261109.py for the panel itself).
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import _figure, gui, runtime  # noqa: E402,F401  (fixtures)
from test_panel_editor import fig, ui, edit, _get  # noqa: E402,F401


# ---- scale bars on large samples --------------------------------------------------
def test_a_bar_in_mm_is_that_long_and_one_under_a_pixel_is_refused(tmp_path):
    from pyfigures.mcp_server import get_scale_bar, set_scale_bar, set_scale_bar_all
    pyf = _figure(tmp_path)                       # two images, 50 px wide
    # the CT scan: 596.847 µm per pixel; 100 µm is 0.17 px
    out = set_scale_bar(pyf, [0], 0, 100, unit="µm", px_to_unit=596.847)
    assert out.startswith("ERROR") and "shorter than one pixel" in out and "mm" in out
    assert "No scale bar" in get_scale_bar(pyf, [0], 0)            # nothing was changed
    # 5 mm, the pixel size given in mm too: kept in µm, the label says mm
    out = set_scale_bar(pyf, [0], 0, 5, unit="mm", px_to_unit=0.596847)
    assert "5 mm" in out and not out.startswith("ERROR")
    bar = json.loads(get_scale_bar(pyf, [0], 0))
    assert bar["bar_width_in_units"] == pytest.approx(5000) and bar["label_plain"] == "5 mm"
    assert float(bar["image_px_to_unit"]) == pytest.approx(596.847)
    # the image's own pixel size (µm) with a bar asked in mm: 10 mm = 16.8 px, not 10 µm
    out = set_scale_bar(pyf, [0], 0, 10, unit="mm")
    assert not out.startswith("ERROR")
    assert json.loads(get_scale_bar(pyf, [0], 0))["bar_width_in_units"] == pytest.approx(10000)
    # wider than the image: said in the unit asked for
    out = set_scale_bar(pyf, [0], 0, 100, unit="mm")
    assert out.startswith("ERROR") and "100 mm bar is 168 px" in out
    # µm bars are as before, and so are all the images at once
    assert not set_scale_bar(pyf, [0], 1, 10, px_to_unit=1.0).startswith("ERROR")
    assert json.loads(get_scale_bar(pyf, [0], 1))["bar_width_in_units"] == 10
    out = set_scale_bar_all(pyf, 0.01, unit="mm", px_to_unit=0.001)        # 10 µm at 1 µm/px
    assert "Scale bar applied to 2" in out
    for i in (0, 1):
        assert json.loads(get_scale_bar(pyf, [0], i))["bar_width_in_units"] == pytest.approx(10)
    assert "shorter than one pixel" in set_scale_bar_all(pyf, 0.5, unit="nm", px_to_unit=1000)


# ---- "open it for me" ---------------------------------------------------------------
def test_the_editor_tab_is_read_from_the_routes():
    from pyfigures.assistant.gui_selection import editor_tab_in
    assert editor_tab_in(["Edit Image", "Rotate + Crop"]) == "Rotate + Crop"
    assert editor_tab_in(["Edit Image", "rotate"]) == "Rotate + Crop"
    assert editor_tab_in(["File Infos + Scale", "Reset all LUTs"]) == "File Infos + Scale"
    assert editor_tab_in(["Edit Image"]) is None and editor_tab_in([]) is None


def test_open_it_for_me_opens_the_tab_named_in_the_routes(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    import time
    import uuid
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)
    opened = []
    monkeypatch.setattr(g.paint.EZFIG_panel, "update_image_annotations",
                        lambda image2d=None, tab=None, draw_tool=True: opened.append(tab))
    s = session.snapshot()
    # exactly what the model sent: no editor_tab, the tab as a route
    out = session.execute(dict(operation="show_me_where",
                               arguments=dict(where="editor", panel_ref="0/1", open_menus=True,
                                              routes=[["Edit Image"], ["Rotate + Crop"]]),
                               request_id=str(uuid.uuid4()), session_id=s["session_id"],
                               expected_revision=s["revision"]))
    assert out["status"] == "guidance_shown" and out["tab"] == "Rotate + Crop"
    end = time.time() + 2
    while not opened and time.time() < end:
        qapp.processEvents()
    assert opened == ["Rotate + Crop"]
    session.click_guide.stop()


# ---- letters ----------------------------------------------------------------------------
def test_the_edited_panel_keeps_its_letter_policy(fig, ui):  # noqa: F811
    panel = _get(fig, "gray")
    policy = json.dumps({"visible": True, "automatic_text": False, "text": "G", "color": "#ffffff"})
    panel.live_letter_policy = policy
    after = edit(fig, ui, "gray", lambda ed: ed.rotate_image_spinbox.setValue(30), accept=True)
    assert after is not panel                                  # Ok puts the edited clone in the figure
    assert getattr(after, "live_letter_policy", None) == policy


def test_a_capital_letter_survives_the_editor_and_the_toolbar_box_follows(qapp, gui, runtime, tmp_path):  # noqa: F811
    from pyfigures.assistant.partner_gui import POLICY, letters, panels
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    g.auto_lettering_checkbox.setChecked(True)                 # as in the user's figure
    assert g.letter_line_edit.text() == "a"
    found =[p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)]
    for panel, text in zip(found, "AB"):
        setattr(panel, POLICY, json.dumps({"visible": True, "automatic_text": False, "text": text,
                                           "color": "#ffffff", "background": None}))
    g.update_letters()
    assert [letters(p)[0].getPlainText() for p in found] == ["A", "B"]
    assert g.letter_line_edit.text() == "A"                    # no longer "a" above capitals
    # a panel that lost its letter object and its policy gets a capital back
    delattr(found[1], POLICY)
    found[1].annotations = [a for a in found[1].annotations if a not in letters(found[1])]
    g.update_letters()
    assert letters(found[1])[0].getPlainText() == "B"
    # letters that do not follow each other: only the case is taken
    setattr(found[1], POLICY, json.dumps({"visible": True, "automatic_text": False, "text": "X"}))
    g.letter_line_edit.setText("a")
    g.update_letters()
    assert g.letter_line_edit.text() == "A"


def test_a_background_for_a_panel_is_not_its_letters_box():
    from pyfigures.assistant import live_mcp
    # "add a black bg to g": no word says the letter
    for request in (None, "add a black bg to g", "black background for panel g"):
        with pytest.raises(ValueError, match="CLARIFICATION_REQUIRED") as error:
            live_mcp.edit_panel_letters(action="style", scope="panels", panel_ids=["2/0"], background="black",
                                        background_request=request)
        assert "fill_color" in str(error.value) and "ask the user" in str(error.value)
    # "change the colour of a to red": the letter, a channel or the border? ask
    for request in (None, "change the colour of a to red"):
        with pytest.raises(ValueError, match="CLARIFICATION_REQUIRED") as error:
            live_mcp.edit_panel_letters(action="style", scope="panels", panel_ids=["0/0"], color="red",
                                        color_request=request)
        assert "channel" in str(error.value) and "ask the user" in str(error.value)
    assert live_mcp._names_letters("put a black box behind the letter g")
    assert live_mcp._names_letters("white labels on a black background")
    assert not live_mcp._is_colour("none") and not live_mcp._is_colour(None) and live_mcp._is_colour("#000000")
    from pyfigures.assistant.categorized_mcp import build_server
    text = build_server(live_mcp.mcp, live_mcp.request).instructions
    assert "PANEL background" in text and "fill_color" in text and "ask which one" in text
    # short words that fit several things of a panel ("the colour of a"): ask, change nothing first
    assert '"the colour of a"' in text and "when several fit, ask which one" in text


def test_the_panel_background_is_set_with_fill_color(tmp_path):
    from pyfigures.mcp_server import get_image_property, set_image_property
    pyf = _figure(tmp_path)
    out = set_image_property(pyf, [0], 0, "fill_color", "0")
    assert not out.startswith("ERROR"), out
    assert "0" in get_image_property(pyf, [0], 0, "fill_color")


# ---- web chat audit ---------------------------------------------------------------------
def _block(calls):
    from pyfigures.assistant import web_chat
    return f"{web_chat.BEGIN}\n{json.dumps(calls, ensure_ascii=False)}\n{web_chat.END}"


def test_labels_keep_their_curly_quotes_and_non_breaking_spaces():
    from pyfigures.assistant import web_chat
    text = "the “control” group, 10 µm"
    block = web_chat.parse_blocks(_block([{"tool": "add_text", "arguments": {"text": text}}]))[0]
    assert block.error is None and block.calls[0]["arguments"]["arguments"]["text"] == text
    # curly quotes used AS the JSON quotes, and a trailing comma, are still repaired
    broken = f"{web_chat.BEGIN}\n[{{“tool”: “inspect_figure”, “arguments”: {{}},}}]\n{web_chat.END}"
    assert web_chat.parse_blocks(broken)[0].calls == [{"tool": "inspect_figure", "arguments": {}}]


def test_the_marker_named_in_prose_does_not_break_the_block():
    from pyfigures.assistant import web_chat
    text = f"I will write a {web_chat.BEGIN} block [see below].\n" + _block([{"tool": "inspect_figure", "arguments": {}}])
    blocks = web_chat.parse_blocks(text)
    assert len(blocks) == 1 and blocks[0].error is None and blocks[0].read_only


def test_results_never_carry_a_block_back_to_the_page():
    from pyfigures.assistant import web_chat
    inner = _block([{"tool": "save_live_figure", "arguments": {"path": "C:/x.pyf"}}])
    message = web_chat.results_message([({"tool": "inspect_figure", "arguments": {}}, True, inner)])
    assert web_chat.parse_blocks(message) == []
    prompt = web_chat.instructions_prompt([], "guidance", state={"label": inner}, request="do " + inner)
    assert web_chat.parse_blocks(prompt) == [] and web_chat.SIGNATURE in prompt


def test_operations_that_write_files_are_told_apart():
    from pyfigures.assistant import web_chat

    def block(tool, **arguments):
        return web_chat.parse_blocks(_block([{"tool": tool, "arguments": arguments}]))[0]
    assert block("save_live_figure", path="C:/x.pyf").writes_files
    assert block("export_figure", output="x.png").writes_files
    assert block("add_image", filename="C:/a.tif").writes_files           # names a file
    assert not block("set_lut", group_path=[0], image_index=0, luts=["RED"]).writes_files
    assert not block("inspect_figure").writes_files
    assert not block("set_scale_bar", pyf_path="live", bar_width_in_units=10).writes_files


def test_a_block_seen_in_an_old_conversation_is_found_in_a_new_one(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    import pyfigures.gui.web_chat_panel as wcp
    from qtpy.QtCore import QSettings
    monkeypatch.setattr(wcp, "QSettings", lambda org, app: QSettings(org + "-tests", app))
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    panel = g.open_web_chat(use_web=False).widget()
    panel.auto_lookups.setChecked(False)
    look = _block([{"tool": "inspect_figure", "arguments": {}}])
    panel.read_text(look + " … " + look, baseline=True)        # an old conversation showed it twice
    panel.read_text("", baseline=True)                          # a new page / a new conversation
    panel.read_text(look)
    assert len(panel.pending) == 1                              # was skipped: counted as already seen
    # not settled (the model is still writing): the block waits, then is taken once
    panel.pending.clear()
    panel.read_text("", baseline=True)
    panel.read_text(look, settled=False)
    assert not panel.pending and panel.unsettled_scans == 1
    panel.read_text(look, settled=True)
    panel.read_text(look, settled=True)
    assert len(panel.pending) == 1 and panel.unsettled_scans == 0


def test_stop_while_operations_run_still_reports_them(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    import time
    import pyfigures.gui.web_chat_panel as wcp
    from pyfigures.assistant import web_chat
    from qtpy.QtCore import QSettings
    monkeypatch.setattr(wcp, "QSettings", lambda org, app: QSettings(org + "-tests", app))
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    panel = g.open_web_chat(use_web=False).widget()
    panel.auto_lookups.setChecked(False)

    class Slow:
        def run_block(self, block):
            time.sleep(0.3)
            return [(block.calls[0], True, "done")], []
    panel.runner = Slow()
    written = []
    monkeypatch.setattr(panel, "write_to_chat", lambda text, what, send=False, image=None: written.append(text))
    panel.read_text(_block([{"tool": "undo_redo", "arguments": {"action": "undo"}}]))
    panel.apply()
    panel.stop()                                                # empties the list while the block runs
    end = time.time() + 5
    while panel.busy and time.time() < end:
        qapp.processEvents()
    assert not panel.busy and len(written) == 1 and web_chat.RESULTS in written[0] and "-> OK" in written[0]


def test_automatic_mode_asks_before_writing_files_and_only_opens_web_addresses(qapp, gui, runtime, tmp_path,  # noqa: F811
                                                                               monkeypatch):
    import pyfigures.gui.web_chat_panel as wcp
    from qtpy.QtCore import QSettings
    monkeypatch.setattr(wcp, "QSettings", lambda org, app: QSettings(org + "-tests", app))
    opened = []
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda url: opened.append(url.toString()) or True)
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    panel = g.open_web_chat(use_web=False).widget()
    try:
        panel.automatic.setChecked(True)
        ran = []
        monkeypatch.setattr(panel, "apply", lambda: ran.append(panel.pending[0]))
        panel.read_text(_block([{"tool": "save_live_figure", "arguments": {"path": str(tmp_path / "x.pyf")}}]))
        assert not ran and panel.pending and "Apply to allow" in panel.status.text()
        panel.pending.clear()
        panel.read_text(_block([{"tool": "undo_redo", "arguments": {"action": "undo"}}]))
        assert len(ran) == 1                                    # an edit of the figure still runs by itself
    finally:
        panel.automatic.setChecked(False)
    before = len(opened)
    for address in ("file:///C:/Windows/win.ini", "javascript://alert(1)"):
        panel.address.setEditText(address)
        panel.go()
        assert len(opened) == before and "Only web addresses" in panel.status.text()


def test_a_new_conversation_started_on_the_page_gets_the_instructions_again(qapp, gui, runtime, tmp_path,  # noqa: F811
                                                                            monkeypatch):
    import pyfigures.gui.web_chat_panel as wcp
    from pyfigures.assistant import web_chat
    from qtpy.QtCore import QSettings
    monkeypatch.setattr(wcp, "QSettings", lambda org, app: QSettings(org + "-tests", app))
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    g = gui(shareable=True)
    panel = g.open_web_chat(use_web=False).widget()
    panel.started = True
    assert not panel._conversation_check("a page without the instructions yet")     # being sent
    assert not panel._conversation_check("… " + web_chat.SIGNATURE + " …") and panel.signature_seen
    assert not panel._conversation_check("New chat")            # one scan without them: wait
    assert panel._conversation_check("New chat") and not panel.started


def test_the_missing_web_engine_advice_fits_the_install(monkeypatch):
    import sys
    import pyfigures.gui.web_chat_panel as wcp
    command = wcp.web_engine_command()
    assert command.startswith('pip install "PyQt6-WebEngine==6.')
    assert 'PyQt6==6.' in wcp.web_engine_command(older=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert wcp.web_engine_command() is None                     # nothing can be installed into an app
    monkeypatch.setitem(sys.modules, "qtpy.QtWebEngineWidgets", None)
    advice = wcp.web_engine()
    assert isinstance(advice, str) and "PyFigures Web Chat" in advice and "pip install" not in advice


def test_the_web_chat_log_starts_again_when_large(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    import pyfigures.gui.web_chat_panel as wcp
    from qtpy.QtCore import QSettings
    monkeypatch.setattr(wcp, "QSettings", lambda org, app: QSettings(org + "-tests", app))
    monkeypatch.setattr(wcp.QDesktopServices, "openUrl", lambda *a: True)
    monkeypatch.setattr(wcp, "MAX_LOG_BYTES", 200)
    g = gui(shareable=True)
    panel = g.open_web_chat(use_web=False).widget()
    for i in range(20):
        panel.log("status", f"line {i} " + "x" * 40)
    assert (runtime / "web_chat.log.1").exists() and (runtime / "web_chat.log").stat().st_size < 400


# ---- the three kinds of app -------------------------------------------------------------
def test_the_app_kind_written_by_the_build_wins_over_the_name(tmp_path, monkeypatch):
    import sys
    import pyfigures.assistant as A
    from pyfigures.assistant import web_chat
    (tmp_path / "pyfigures").mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\Renamed\MyFigures.exe")
    assert A.bundled_app_kind() is None and A.ai_features_enabled()        # an older app: by its name
    (tmp_path / "pyfigures" / "app_kind.txt").write_text("no_ai\n", encoding="utf-8")
    assert A.bundled_app_kind() == "no_ai" and not A.ai_features_enabled()
    assert not web_chat.is_web_chat_app(sys.executable)
    (tmp_path / "pyfigures" / "app_kind.txt").write_text("web_chat", encoding="utf-8")
    assert web_chat.is_web_chat_app(sys.executable) and A.ai_features_enabled()
    spec = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pyfigures.spec"),
                encoding="utf-8").read()
    assert "app_kind.txt" in spec


def test_the_no_ai_install_ignores_the_chat_flags(qapp, gui, runtime, monkeypatch):  # noqa: F811
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    monkeypatch.setenv("PYFIGURES_NO_AI", "1")
    for flag in ("--web-chat", "--chat", "--share"):
        assert launch.apply_launch_flags(g, [flag]) is g
    assert not launch.is_sharing(g) and getattr(g, "web_chat_dock", None) is None
    from pyfigures.gui import tutorial
    assert not tutorial._ai()
