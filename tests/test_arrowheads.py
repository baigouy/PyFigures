"""Arrowheads (the head alone, larger, as in papers) next to arrows — user
request 25 Oct 2026. GUI (Add arrow dialog, editor tool), MCP and recipes,
and the MCP tells the two apart.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import math
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _fig(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    p = str(tmp_path / "a.tif")
    Img((np.random.default_rng(0).random((200, 300)) * 255).astype(np.uint8), dimensions="hw").save(p)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], p)
    return pyf


def test_mcp_arrow_and_arrowhead_are_told_apart(tmp_path):
    from pyfigures.mcp_server import add_arrow, get_annotations
    pyf = _fig(tmp_path)
    assert "Arrow added" in add_arrow(pyf, [0], 0, 150, 100, from_direction="nw")
    r = add_arrow(pyf, [0], 0, 60, 60, from_direction="e", style="arrowhead", head="large", label="cell")
    assert r.startswith("Arrowhead added"), r
    kinds = [a.get("kind") for a in json.loads(get_annotations(pyf))
             if a.get("type") == "Line2D"]
    assert kinds == ["arrow", "arrowhead"]
    assert add_arrow(pyf, [0], 0, 10, 10, style="dart").startswith("ERROR")


def test_arrowhead_point_stays_on_the_pixel_and_head_is_larger(tmp_path):
    from pyfigures.mcp_server import add_arrow
    from pyfigures.mcp_tools.core import _load
    pyf = _fig(tmp_path)
    add_arrow(pyf, [0], 0, 150, 100, from_direction="nw")
    add_arrow(pyf, [0], 0, 80, 40, from_direction="s", style="arrowhead")
    _t, root = _load(pyf)
    arrow, head = list(root.iter("Line2D"))
    assert (float(head.findtext("x2")), float(head.findtext("y2"))) == (80.0, 40.0)
    length = math.hypot(float(head.findtext("x2")) - float(head.findtext("x1")),
                        float(head.findtext("y2")) - float(head.findtext("y1")))
    assert length < 1.0 and float(head.findtext("y1")) > 40       # comes from below
    assert float(head.findtext("arrowhead_height_scaler")) > float(arrow.findtext("arrowhead_height_scaler"))


def test_recipe_arrowhead(tmp_path):
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures.mcp_server import get_annotations
    d = str(tmp_path)
    Image.fromarray((np.random.default_rng(1).random((60, 80)) * 255).astype(np.uint8)).save(
        os.path.join(d, "im.png"))
    rp = os.path.join(d, "r.json")
    with open(rp, "w") as f:
        json.dump({"output": "fig.pyf", "rows": [[{"image": "im.png", "arrows": [
            {"at": [40, 30], "from": "ne", "style": "arrowhead"}]}]]}, f)
    out = build_figure_from_recipe(rp)["output"]
    kinds = [a.get("kind") for a in json.loads(get_annotations(out))
             if a.get("type") == "Line2D"]
    assert kinds == ["arrowhead"]


def test_editor_arrowhead_tool(qapp, tmp_path):
    """The image editor's Arrowhead tool: a drag gives the head alone, its
    point where the drag ended."""
    from qtpy.QtCore import QEvent, QPointF, Qt
    from qtpy.QtGui import QMouseEvent
    from qtpy.QtWidgets import QApplication, QPushButton
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.line2d import Line2D
    from pyfigures.arrowheads import is_head_only
    from pyfigures.gui.annotation_editor_former_000_TOP_vectorial2 import VectorialDrawPane2, MainWindow
    p = str(tmp_path / "a.tif")
    from batoolset.img import Img
    Img((np.random.default_rng(0).random((200, 300)) * 255).astype(np.uint8), dimensions="hw").save(p)
    viewer = VectorialDrawPane2(background=Image2D(p))
    main = MainWindow(qt_viewer=viewer)
    main.show()
    qapp.processEvents()
    btn = next(b for b in main.findChildren(QPushButton) if b.toolTip().startswith("Arrowhead only"))
    btn.click()

    def mouse(kind, pos):
        t = {"press": QEvent.Type.MouseButtonPress, "release": QEvent.Type.MouseButtonRelease,
             "move": QEvent.Type.MouseMove}[kind]
        b = Qt.MouseButton.LeftButton
        QApplication.sendEvent(viewer, QMouseEvent(t, pos, QPointF(viewer.mapToGlobal(pos.toPoint())), b,
                                                   b if kind != "release" else Qt.MouseButton.NoButton,
                                                   Qt.KeyboardModifier.NoModifier))
    mouse("press", QPointF(40, 40))
    mouse("move", QPointF(70, 60))
    mouse("release", QPointF(100, 80))     # the release point is the tip
    lines = [s for s in viewer.shapes if isinstance(s, Line2D)]
    assert len(lines) == 1, viewer.shapes
    head = lines[0]
    assert is_head_only(head.x1(), head.y1(), head.x2(), head.y2(), head.arrow)
    assert (round(head.x2()), round(head.y2())) == (100, 80)
    assert head.arrowhead_height_scaler >= 16
    main.close()
