"""Chat findings 2026-11-04 (Mistral in the sidecar):

- "connect the ROI to the inset with 2 lines" ran out of steps searching for a
  tool, then lines drawn by hand stopped short of the inset: connect_roi_to_inset
  computes the ends from where the inset is really drawn (MCP / chat / editor),
- "make the whole fig 20 cm wide" changed the pixel width but the mm label kept
  the old value.
"""
from __future__ import annotations

import uuid

import numpy as np
import pytest
from qtpy.QtCore import QPointF
from qtpy.QtGui import QImage, QPainter

from test_assistant_live import runtime, gui, _figure  # noqa: F401  (fixtures)


def _big_figure(tmp_path, size=(400, 600)):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "big.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    p = str(tmp_path / "big.tif")
    Img((np.random.default_rng(3).random(size) * 255).astype(np.uint8), dimensions="hw").save(p)
    add_image(pyf, [0], p)
    return pyf


def _drawn_inset_corners(panel, inset):
    """The inset's corners in the panel's image pixels, from a real paint."""
    img = QImage(2000, 2000, QImage.Format.Format_ARGB32)
    painter = QPainter(img)
    panel.draw(painter)
    painter.end()
    r = inset.getRect(all=True)
    s = panel.scale or 1
    ox, oy = panel.topLeft().x(), panel.topLeft().y()
    to_px = lambda x, y: ((x - ox) * s, (y - oy) * s)     # shown size = raw size / scale
    return [to_px(r.left(), r.top()), to_px(r.right(), r.top()),
            to_px(r.left(), r.bottom()), to_px(r.right(), r.bottom())]


def test_live_lines_end_on_the_drawn_inset(qapp, gui, runtime, tmp_path):
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import panels, Image2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.line2d import Line2D
    g = gui(shareable=True)
    g.reload_state(_big_figure(tmp_path), append=False)
    session = launch.start_live_session(g)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))

    def panel():
        return next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    panel().annotations.append(Rectangle2D(60, 250, 90, 70, color=0xFFFF00, stroke=2))
    report = cmd("roi_to_inset", panel_ref="0/0")["operation_result"]
    assert "connect_roi_to_inset" in report["connect_hint"]
    for _ in range(2):                        # twice: the second replaces, never doubles
        cmd("original_tool", tool="connect_roi_to_inset",
            arguments={"pyf_path": "live", "group_path": [0], "image_index": 0})
    p = panel()
    lines = [a for a in p.annotations if isinstance(a, Line2D)]
    inset = next(a for a in p.annotations if isinstance(a, Image2D))
    assert len(lines) == 2
    corners = _drawn_inset_corners(p, inset)
    for line in lines:
        end = (line.p2().x(), line.p2().y())
        assert min(np.hypot(end[0] - cx, end[1] - cy) for cx, cy in corners) < 1.5, (end, corners)
        start = (line.p1().x(), line.p1().y())
        assert start in [(60, 250), (150, 250), (60, 320), (150, 320)]
    # the inset is drawn over the line ends
    assert p.annotations.index(inset) > max(p.annotations.index(l) for l in lines)


def test_chat_finds_the_connector_tool_first():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    find = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools['find_pyfigures_tools'].fn
    first = lambda q: find(query=q)['tools'][0]['name']
    assert first("connect the ROI to the inset with 2 lines") == "connect_roi_to_inset"
    assert first("connect ROI to inset callout lines draw connector lines between ROI and inset") == "connect_roi_to_inset"


def test_file_tool_errors_and_cropped_parent(tmp_path):
    """On a file: clear errors, and the inset follows the panel's crop window."""
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_server import add_roi_rect, add_inset, connect_roi_to_inset, transform_image
    pyf = _big_figure(tmp_path)
    src = str(tmp_path / "big.tif")
    assert "no rectangle ROI" in connect_roi_to_inset(pyf, [0], 0)
    add_roi_rect(pyf, [0], 0, 50, 60, 40, 40)
    assert "no inset" in connect_roi_to_inset(pyf, [0], 0)
    add_inset(pyf, [0], 0, src, placement="bottom left", size_fraction=0.5)
    transform_image(pyf, [0], 0, crop_left=100, crop_bottom=50)
    out = connect_roi_to_inset(pyf, [0], 0, connectors=1)
    assert out.startswith("1 leader line")
    root = ET.parse(pyf).getroot()
    line = root.find(".//Line2D")
    # shown window: x 100..600, y 0..350; inset 250 wide, 250 * 400/600 high, bottom left
    x2, y2 = float(line.findtext("x2")), float(line.findtext("y2"))
    assert x2 in (pytest.approx(100), pytest.approx(350))
    assert y2 in (pytest.approx(350 - 250 * 400 / 600), pytest.approx(350))


def test_editor_button_connects_and_undo_removes(qapp, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.line2d import Line2D
    from pyfigures.gui.annotation_editor import VectorialDrawPane2, MainWindow
    _big_figure(tmp_path)
    bg = Image2D(str(tmp_path / "big.tif"))
    main = MainWindow(qt_viewer=VectorialDrawPane2(background=bg))
    main.update_annotations_list(lst=[Rectangle2D(60, 250, 90, 70, color=0xFFFF00, stroke=2)], update=True,
                                 repopulate_list=True)
    main.qt_viewer.selected_shape = [main.qt_viewer.shapes[0]]
    main.ROI_to_crop_or_inset()
    assert main.connect_roi_to_inset()
    assert sum(isinstance(a, Line2D) for a in main.qt_viewer.shapes) == 2
    assert main.connect_roi_to_inset()                       # replaced, not doubled
    assert sum(isinstance(a, Line2D) for a in main.qt_viewer.shapes) == 2
    assert main.undo() and main.undo()
    assert sum(isinstance(a, Line2D) for a in main.qt_viewer.shapes) == 0
    assert bg.annotations is main.qt_viewer.shapes or len(bg.annotations) == len(main.qt_viewer.shapes)
    main.close()


def test_resize_updates_the_mm_label(qapp, gui, runtime, tmp_path):
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    g.unit_combobox.setCurrentText("mm")
    session = launch.start_live_session(g)
    s = session.snapshot()
    session.execute(dict(operation="original_tool", request_id=str(uuid.uuid4()), session_id=s["session_id"],
                         expected_revision=s["revision"],
                         arguments={"tool": "resize_figure", "arguments": {"pyf_path": "live", "width_cm": 20}}))
    value = float(g.value_label.text().split("≈")[1])
    assert value == pytest.approx(200, abs=3)
