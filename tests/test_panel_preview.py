"""Cropping with the chat (2026-11-03): asked to "crop g so that nuclei occupy
the whole frame", a model saw only the small figure preview and cropped,
uncropped and cropped again until it ran out of steps; then the image editor
it opened for the user was not on its Rotate + Crop tab.

preview_panel (live) and preview_panel_source (file) show one panel's whole
source with pixel rulers and the current crop; open_annotation_editor takes a
tab. Run with PYTEST_QT_API=pyqt6. One Qt process at a time.
"""
from __future__ import annotations

import os
import time
import uuid

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import _figure, gui, runtime  # noqa: F401  (fixtures)


def test_editor_tab_words():
    from pyfigures.assistant.gui_selection import editor_tab
    assert editor_tab(None) == "Annotations"
    assert editor_tab("crop") == editor_tab("rotate") == editor_tab("Rotate + Crop") == "Rotate + Crop"
    assert editor_tab("crop tab") == "Rotate + Crop"
    assert editor_tab("scale") == "File Infos + Scale"
    assert editor_tab("text") == "Texts"
    with pytest.raises(ValueError, match="Unknown editor tab"):
        editor_tab("histogram")


def test_render_draws_rulers_and_the_crop(tmp_path):
    from PIL import Image
    from pyfigures.panel_source_preview import render, _step
    rgb = np.zeros((300, 400, 3), np.uint8)
    rgb[100:150, 200:260] = 40               # a dim object
    out = str(tmp_path / "p.png")
    text = render(rgb, (10, 20, 30, 40), out)
    assert "400x300" in text and "left=10, top=20, right=30, bottom=40" in text
    assert "kept x 10-370, y 20-260" in text and "Contrast stretched" in text
    assert Image.open(out).size[0] > 400
    assert _step(620) == 100 and _step(4000) == 500 and _step(40) == 5


def _session(qapp, gui, tmp_path):
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    session = launch.start_live_session(g)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))
    return g, session, cmd


def test_live_panel_source_is_read_only(qapp, gui, runtime, tmp_path):
    from pyfigures.assistant.partner_gui import panels
    g, session, cmd = _session(qapp, gui, tmp_path)
    panel = next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    panel.crop_left = 5
    panel.crop_bottom = 8
    g.paint.EZFIG_panel.update()      # the user's crop, made in the GUI
    session.snapshot()
    session.snapshot()                # the canvas settles the cropped size on the next paint
    before = session.revision
    result = cmd("panel_source", panel_ref="0/0")
    assert os.path.isfile(result["path"])
    assert "50x40" in result["description"] and "left=5" in result["description"] and "bottom=8" in result["description"]
    assert session.revision == before and panel.crop_left == 5      # nothing changed
    with pytest.raises(ValueError):
        cmd("panel_source", panel_ref="")


def test_editor_opens_on_the_crop_tab(qapp, gui, runtime, tmp_path):
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication, QDialog, QTabWidget
    g, session, cmd = _session(qapp, gui, tmp_path)
    result = cmd("open_annotation_editor", panel_ref="0/0", tab="crop")
    assert result["tab"] == "Rotate + Crop"
    seen = {}

    def dialogs():
        return [d for d in QApplication.topLevelWidgets() if isinstance(d, QDialog) and d.isVisible()
                and d.windowTitle() == "Annotate the image"]

    def check():
        found = dialogs()
        if not found:
            QTimer.singleShot(50, check)
            return
        widget = next((t for t in found[0].findChildren(QTabWidget)
                       if any(t.tabText(i) == "Rotate + Crop" for i in range(t.count()))), None)
        seen["tab"] = widget.tabText(widget.currentIndex()) if widget is not None else None
        found[0].reject()
    t0 = time.time()
    QTimer.singleShot(50, check)
    while time.time() - t0 < 10 and ("tab" not in seen or dialogs()):
        qapp.processEvents()
        time.sleep(0.01)
    assert seen.get("tab") == "Rotate + Crop", seen


def test_headless_panel_source(tmp_path):
    from mcp.server.fastmcp import Image
    from pyfigures.mcp_server import transform_image
    from pyfigures.mcp_tools.export import preview_panel_source
    pyf = _figure(tmp_path)
    transform_image(pyf, [0], 1, crop_left=4, crop_top=3)
    text, image = preview_panel_source(pyf, [0], 1)
    assert isinstance(image, Image) and "50x40" in text and "left=4, top=3" in text
    with pytest.raises(ValueError, match="out of range"):
        preview_panel_source(pyf, [0], 7)


def test_crop_requests_find_the_panel_preview():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(live_mcp.mcp, live_mcp.request)
    tools = server._tool_manager._tools
    names = [t["name"] for t in tools["find_pyfigures_tools"].fn(query="crop g so that nuclei occupy the whole frame")["tools"]]
    assert names[0] == "preview_panel" and "transform_image" in names[:4]
    found = tools["list_pyfigures_categories"].fn() if "list_pyfigures_categories" in tools else None
    assert "preview_panel_source" not in str(found)        # the live one is enough
