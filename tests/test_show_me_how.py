"""“Show me how” guides (pyfigures/guides.py, gui/show_me_how.py, MCP
mcp_tools/guidance.py), integrated from the chatGPT prototype of 2026-10-19
(chatGPT_validation/2026-10-19_show_me_how).

Showing or closing a guide never edits the figure; the user performs the
operation and the guide only detects it. Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import threading

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import guides as G


# ---------------------------------------------------------------- registry

def test_every_guide_names_an_existing_do_it_tool():
    import pyfigures.mcp_server as M
    for gid, g in G.GUIDES.items():
        assert callable(getattr(M, g["mcp"], None)), (gid, g["mcp"])
        assert g["steps"] and g["done"] and g["title"] and g["summary"]


@pytest.mark.parametrize("query, expected", [
    ("split_channels", "split_channels"),
    ("split channels", "split_channels"),
    ("Show me how to split the channels of my RGB image", "split_channels"),
    ("how do I crop the burned-in text", "crop_image"),
    ("make it magenta and green", "set_lut"),
    ("add a 10 µm scale bar", "add_scale_bars"),
    ("magnify a detail with a zoom inset", "zoom_inset"),
    ("export to powerpoint", "export_pptx"),
    ("is it colour blind safe", "colour_blind_preview"),
])
def test_find_guide_from_ids_and_words(query, expected):
    assert G.find_guide(query)[0] == expected


def test_unknown_request_is_not_guessed():
    gid, cands = G.find_guide("bake a cake")
    assert gid is None and cands == []
    assert G.explain("bake a cake")["status"] == "unknown_operation"
    assert G.show("bake a cake")["status"] == "unknown_operation"


def test_explain_returns_the_authored_steps():
    r = G.explain("crop")
    assert r["status"] == "explained" and r["guide"] == "crop_image"
    assert r["do_it_tool"] == "transform_image" and r["operation_executed"] is False
    assert any("Rotate + Crop" in s for s in r["steps"])
    assert all("<" not in s for s in r["steps"])                 # plain text


def test_no_gui_open_is_an_explicit_error_with_text_steps(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFIGURES_GUI_SESSIONS", str(tmp_path / "none"))
    r = G.show("split_channels")
    assert r["status"] == "gui_unavailable" and r["operation_executed"] is False
    assert any("Channel split" in s for s in r["steps_as_text"])


def test_dead_window_sessions_are_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFIGURES_GUI_SESSIONS", str(tmp_path))
    dead = tmp_path / "999999_dead"
    dead.mkdir()
    (dead / "session.json").write_text(json.dumps({"pid": 2 ** 22 + 12345, "token": "x",
                                                   "created": 1}), encoding="utf-8")
    assert G.live_sessions() == []
    assert not dead.exists()


# ---------------------------------------------------------------- GUI

def _rgb(path):
    from PIL import Image
    y, x = np.mgrid[:96, :128]
    a = np.zeros((96, 128, 3), np.uint8)
    for c, (cx, cy) in enumerate(((40, 40), (80, 50), (60, 70))):
        a[..., c] = (220 * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * 15 ** 2))).astype(np.uint8)
    Image.fromarray(a).save(path)
    return str(path)


@pytest.fixture
def win(qapp, tmp_path, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    import pyfigures.mcp_server as M
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], _rgb(tmp_path / "cells.png"))
    w = EZFIG_GUI()
    w.resize(1200, 800)
    w.show()
    w.reload_state(pyf, append=False)
    qapp.processEvents()
    w._test_pyf = pyf
    yield w
    w._guides.stop()
    if w._guide_mailbox is not None:
        w._guide_mailbox.close()
    w._dirty = False
    w._stop_all_img_loaders()
    w.hide()


def _images(w):
    from pyfigures.gui.tutorial import _image_stack
    return list(_image_stack(w))


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _pump(qapp, ms=100):
    from qtpy.QtTest import QTest
    QTest.qWait(ms)
    qapp.processEvents()


def test_every_guide_route_exists_in_the_real_gui(win):
    from pyfigures.gui.show_me_how import resolve_menu_path
    for gid, g in G.GUIDES.items():
        for step in g["steps"]:
            if "menu" in step:
                chain = resolve_menu_path(win, step["menu"])
                assert len(chain) == len(step["menu"]), gid


def test_help_menu_lists_the_guides(win):
    from pyfigures.gui.show_me_how import find_action
    help_menu = find_action(win.menuBar, "Help").menu()
    how = find_action(help_menu, "Show me how…").menu()
    titles = [a.text() for a in how.actions()]
    assert titles == [g["title"] for g in G.GUIDES.values()]
    find_action(how, G.GUIDES["set_lut"]["title"]).trigger()
    assert win._guides.status()["guide"] == "set_lut"
    assert win._tutorial._bubble.isVisible()


def test_showing_and_closing_a_guide_does_not_edit_the_figure(win, qapp):
    from qtpy.QtCore import Qt
    from qtpy.QtTest import QTest
    before = _sha(win._test_pyf)
    n = len(_images(win))
    st = win.show_me_how("split_channels")
    _pump(qapp)
    assert st["status"] == "guidance_shown" and st["operation_executed"] is False
    assert win._tutorial._bubble.isVisible()
    assert win.rect().contains(win._tutorial._bubble.geometry())
    QTest.mouseClick(win._tutorial._bubble._btn_skip, Qt.LeftButton)       # close
    _pump(qapp)
    assert not win._tutorial._bubble.isVisible()
    assert win._guides.status()["status"] == "cancelled"
    assert len(_images(win)) == n and _sha(win._test_pyf) == before


def test_split_guide_follows_the_user_through_the_real_menu(win, qapp):
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication, QDialog
    from pyfigures.gui.show_me_how import resolve_menu_path
    runner = win._guides
    win.show_me_how("split_channels")
    _pump(qapp)
    assert win._tutorial._index == 0                     # nothing selected yet
    win.paint.EZFIG_panel.selected_shape = _images(win)[0]
    _pump(qapp, 1700)                                     # poll + auto-advance
    assert win._tutorial._index == 1                     # now: open Annotations
    menu_step = win._tutorial._steps[1]
    anchor = menu_step.get_target(win)
    action = resolve_menu_path(win, ["Annotations"])[0][1]
    assert anchor.geometry().adjusted(0, 0, 1, 1) == win.menuBar.actionGeometry(action)

    accepted = []

    def accept_dialog():
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible() and "channel split" in w.windowTitle().lower():
                accepted.append(w.windowTitle())
                w.accept()
                return
        QTimer.singleShot(30, accept_dialog)

    QTimer.singleShot(50, accept_dialog)
    leaf = resolve_menu_path(win, G.GUIDES["split_channels"]["steps"][1]["menu"])[-1][1]
    leaf.trigger()                                        # the user picks the real action
    _pump(qapp, 1800)
    assert accepted, "the real channel-split dialog did not open"
    assert len(_images(win)) == 5                         # original + 3 channels + merge
    st = runner.status()
    assert st["status"] == "completed" and st["user_result_detected"] is True
    assert st["operation_executed"] is False


def test_an_unrelated_image_does_not_complete_the_split_guide(win, qapp):
    from batoolset.drawings.shapes.image2d import Image2D
    img = _images(win)[0]
    win.paint.EZFIG_panel.selected_shape = img
    win.show_me_how("split_channels")
    win.paint.EZFIG_panel.shapes_to_draw.append(Image2D(str(img.filename)))
    _pump(qapp, 900)
    assert win._guides.status()["status"] == "guidance_shown"


def test_lut_guide_detects_the_colour_change_on_the_selected_image(win, qapp):
    img = _images(win)[0]
    win.paint.EZFIG_panel.selected_shape = img
    win.show_me_how("set_lut")
    _pump(qapp, 600)
    assert win._guides._target_image is img
    img.LUTs = ["MAGENTA", "GREEN", "GRAY"]
    _pump(qapp, 900)
    assert win._guides.status()["user_result_detected"] is True


def test_a_help_tutorial_started_later_is_not_closed_by_the_guide(win, qapp):
    from pyfigures.gui.tutorial import TutorialStep
    win.show_me_how("crop_image")
    other = [TutorialStep("Other tutorial", "belongs to another Help tour")]
    win._tutorial.start(other)
    win._guides.stop()
    _pump(qapp)
    assert win._tutorial._bubble.isVisible() and win._tutorial._steps is other
    win._tutorial.stop()


def test_missing_menu_route_is_reported_not_invented(win, monkeypatch):
    monkeypatch.setitem(G.GUIDES, "split_channels",
                        dict(G.GUIDES["split_channels"],
                             steps=[{"menu": ["Annotations", "No such entry…"]}]))
    with pytest.raises(LookupError):
        win._guides.start("split_channels")
    mailbox_reply = __import__("pyfigures.gui.show_me_how", fromlist=["x"])
    box = win.open_guide_mailbox()
    assert box is not None
    assert box.handle("show", "split_channels")["status"] == "target_unavailable"
    assert box.handle("show", "invented")["status"] == "unknown_operation"
    assert mailbox_reply


# ---------------------------------------------------------------- mailbox

def _in_thread(fn, qapp, timeout=8.0):
    """Run a blocking client call while the Qt loop keeps polling the mailbox."""
    import time
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("r", fn()))
    t.start()
    end = time.monotonic() + timeout
    while t.is_alive() and time.monotonic() < end:
        _pump(qapp, 20)
    t.join(1)
    return out.get("r")


def test_command_line_client_round_trip(win, qapp, tmp_path, monkeypatch):
    root = tmp_path / "sessions"
    monkeypatch.setenv("PYFIGURES_GUI_SESSIONS", str(root))
    box = win.open_guide_mailbox()
    assert box is not None and (root / os.path.basename(box.folder) / "session.json").exists()
    before = _sha(win._test_pyf)
    r = _in_thread(lambda: G.show("how do I add scale bars"), qapp)
    assert r["status"] == "guidance_shown" and r["guide"] == "add_scale_bars"
    assert _in_thread(lambda: G.status(), qapp)["step"] == 1
    assert _in_thread(lambda: G.close(), qapp)["status"] == "cancelled"
    assert not win._tutorial._bubble.isVisible() and _sha(win._test_pyf) == before
    box.close()
    win._guide_mailbox = None
    assert not os.path.exists(box.folder)


def test_mailbox_refuses_wrong_token_and_expired_requests(win, qapp, tmp_path, monkeypatch):
    import time
    monkeypatch.setenv("PYFIGURES_GUI_SESSIONS", str(tmp_path / "s"))
    box = win.open_guide_mailbox()
    for name, req in (("a", {"token": "wrong", "created": time.time(), "action": "show",
                             "topic": "set_lut"}),
                      ("b", {"token": box.token, "created": time.time() - 120, "action": "show",
                             "topic": "set_lut"})):
        with open(os.path.join(box.folder, name + ".request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f)
    box.poll()
    for name in ("a", "b"):
        with open(os.path.join(box.folder, name + ".response.json"), encoding="utf-8") as f:
            assert json.load(f)["status"] == "error"
    assert not win._tutorial._bubble.isVisible()


def test_real_mcp_server_opens_and_closes_the_guide(win, qapp, tmp_path, monkeypatch):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    root = tmp_path / "sessions"
    monkeypatch.setenv("PYFIGURES_GUI_SESSIONS", str(root))
    win.open_guide_mailbox()
    before = _sha(win._test_pyf)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYFIGURES_GUI_SESSIONS=str(root))

    async def scenario():
        params = StdioServerParameters(command=sys.executable, args=["-m", "pyfigures.mcp_server"],
                                       env=env)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {"show_me_how", "guidance_status", "close_guidance",
                        "list_how_to_guides", "explain_how"} <= names
                shown = json.loads((await session.call_tool(
                    "show_me_how", {"operation": "split_channels",
                                    "pyf_path": win._test_pyf})).content[0].text)
                status = json.loads((await session.call_tool("guidance_status", {})).content[0].text)
                bad = json.loads((await session.call_tool(
                    "show_me_how", {"operation": "fly to the moon"})).content[0].text)
                closed = json.loads((await session.call_tool("close_guidance", {})).content[0].text)
                return shown, status, bad, closed

    async def pump():
        task = asyncio.create_task(scenario())
        while not task.done():
            qapp.processEvents()
            await asyncio.sleep(0.01)
        return await task

    shown, status, bad, closed = asyncio.run(pump())
    assert shown["status"] == "guidance_shown" and shown["operation_executed"] is False
    assert status["status"] == "guidance_shown" and status["guide"] == "split_channels"
    assert bad["status"] == "unknown_operation"
    assert closed["status"] == "cancelled"
    assert not win._tutorial._bubble.isVisible()
    assert _sha(win._test_pyf) == before
