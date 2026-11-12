"""Sticky connectors and insets that follow their ROI (user requests 2026-11-12):
- "connector lines … that remain sticky to corners/ends of other ROIs, as in
  PowerPoint; also for insets when the user wants them connected (not by default)";
- an ROI moved by hand in the panel editor (then OK) left its inset showing the
  old region, and the leader lines where they were.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import _call, gui, runtime  # noqa: E402,F401  (fixtures)


def _image(tmp_path, size=(400, 600)):
    from batoolset.img import Img
    p = str(tmp_path / "big.tif")
    Img((np.random.default_rng(3).random(size) * 255).astype(np.uint8), dimensions="hw").save(p)
    return p


def _figure(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "c.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], _image(tmp_path))
    return pyf


def test_a_connector_follows_both_shapes(qapp):
    from pyfigures import connectors
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    connectors.install()
    parent = Image2D(data=np.zeros((400, 600), dtype=np.uint8))
    a, b = Rectangle2D(10, 10, 50, 40), Rectangle2D(300, 200, 60, 60)
    line = connectors.make_connector(a, b)
    parent.annotations = [a, b, line]
    connectors.snap(parent)
    assert (line.x1(), line.y1(), line.x2(), line.y2()) == (60, 50, 300, 200)   # nearest corners
    b.moveTo(400, 20)                                     # b moves up to the right of a
    connectors.snap(parent)
    assert (line.x1(), line.y1()) == (60, 50) and (line.x2(), line.y2()) == (400, 50)   # corner to edge middle
    fixed = connectors.make_connector(a, b, "top left", "center")
    parent.annotations.append(fixed)
    connectors.snap(parent)
    assert (fixed.x1(), fixed.y1(), fixed.x2(), fixed.y2()) == (10, 10, 430, 50)
    with pytest.raises(ValueError):
        connectors.normalise_site("north pole")
    # its target deleted, a connector stays as it is
    parent.annotations.remove(b)
    end = (line.x2(), line.y2())
    connectors.snap(parent)
    assert (line.x2(), line.y2()) == end and line in parent.annotations


def test_the_attachments_survive_save_and_open(qapp):
    from pyfigures import connectors
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.serializations.tools import clone_object
    connectors.install()
    a, b = Rectangle2D(10, 10, 50, 40), Rectangle2D(300, 200, 60, 60)
    line = connectors.make_connector(a, b, "top", "bottom")
    connectors.snap(None, [a, b, line])                  # (an empty line is not cloned)
    copy_a, copy_line = clone_object(a), clone_object(line)
    assert copy_a.link_id == a.link_id and not copy_a.link_id.isdigit()
    assert copy_line.connect_start == f"{a.link_id}:top" and copy_line.connect_end == f"{b.link_id}:bottom"


def test_mcp_connector_is_drawn_attached_in_the_gui(qapp, gui, runtime, tmp_path):  # noqa: F811
    """add_connector writes a connector; the opened figure keeps it attached."""
    import json
    from pyfigures.mcp_server import add_roi_rect, add_connector, get_annotations
    from pyfigures.assistant.partner_gui import panels
    from batoolset.drawings.shapes.line2d import Line2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    pyf = _figure(tmp_path)
    add_roi_rect(pyf, [0], 0, 10, 10, 50, 40)
    add_roi_rect(pyf, [0], 0, 300, 200, 60, 60)
    out = add_connector(pyf, [0], 0, 0, 1, arrow=True)
    assert out.startswith("Connector added") and "(60,50)→(300,200)" in out
    assert add_connector(pyf, [0], 0, 0, 0).startswith("ERROR")
    assert add_connector(pyf, [0], 0, 0, 1, from_site="north").startswith("ERROR")
    assert len(json.loads(get_annotations(pyf))) == 3
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    panel = next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    roi = [a for a in panel.annotations if type(a) is Rectangle2D][1]
    line = next(a for a in panel.annotations if isinstance(a, Line2D))
    assert line.connect_start and line.connect_end and line.arrow
    roi.moveTo(400, 20)
    g.paint.EZFIG_panel.grab()                            # a real paint snaps it
    assert (line.x2(), line.y2()) == (400, 50)


def test_recipe_connectors(tmp_path):
    import json
    from pyfigures.recipe import RecipeError, build_figure_from_recipe
    image = _image(tmp_path)
    panel = {"image": image, "rois": [{"rect": [10, 10, 50, 40]}, {"ellipse": [300, 200, 60, 60]}],
             "connectors": [{"from": 1, "to": 2, "color": "red", "to_site": "left"}]}
    rp = str(tmp_path / "r.json")
    with open(rp, "w") as f:
        json.dump({"output": "fig.pyf", "rows": [[panel]]}, f)
    out = build_figure_from_recipe(rp)["output"]
    line = ET.parse(out).getroot().find(".//Line2D")
    assert line is not None and "left" in line.findtext("connect_end")
    with open(rp, "w") as f:
        json.dump({"output": "fig2.pyf", "rows": [[dict(panel, connectors=[{"from": 1, "to": 3}])]]}, f)
    with pytest.raises(RecipeError, match="roi"):
        build_figure_from_recipe(rp)


def test_a_click_on_a_rotated_panel_gives_image_pixels(qapp, gui, tmp_path):  # noqa: F811
    """'add an arrowhead where i clicked' on the rotated panel I (user chat 2026-11-12): the
    click could not be converted to image pixels."""
    from pyfigures.zoom_geometry import scene_to_image_point
    from pyfigures.assistant.partner_gui import panels
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)          # one 600 x 400 image
    p = next(q for _, _, q in panels(g.paint.EZFIG_panel.shapes_to_draw))
    r = p.getRect(all=True)
    # upright: the same as the plain scale formula
    x, y = scene_to_image_point(p, (r.x() + 30, r.y() + 20))
    assert x == pytest.approx(30 * p.scale, abs=0.5) and y == pytest.approx(20 * p.scale, abs=0.5)
    p.theta = 25
    g.paint.EZFIG_panel.update()
    g.paint.EZFIG_panel.grab()
    r = p.getRect(all=True)
    x, y = scene_to_image_point(p, (r.center().x(), r.center().y()))
    assert (x, y) == (pytest.approx(300, abs=2), pytest.approx(200, abs=2))   # turns about its centre
    assert scene_to_image_point(p, (r.x() + 1, r.y() + 1)) is None            # the empty frame corner


def test_editor_connect_two_shapes(qapp, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.line2d import Line2D
    from pyfigures.gui.annotation_editor import VectorialDrawPane2, MainWindow
    bg = Image2D(_image(tmp_path))
    main = MainWindow(qt_viewer=VectorialDrawPane2(background=bg))
    a, b = Rectangle2D(10, 10, 50, 40, color=0xFFFF00, stroke=2), Rectangle2D(300, 200, 60, 60)
    main.update_annotations_list(lst=[a, b], update=True, repopulate_list=True)
    warned = []
    main.show_warning = warned.append                     # (a modal box otherwise)
    main.qt_viewer.selected_shape = [main.qt_viewer.shapes[0]]
    assert not main.connect_two_shapes() and warned       # one shape: asks for two
    main.qt_viewer.selected_shape = list(main.qt_viewer.shapes[:2])
    assert main.connect_two_shapes()
    line = next(s for s in main.qt_viewer.shapes if isinstance(s, Line2D))
    assert (line.x1(), line.y1(), line.x2(), line.y2()) == (60, 50, 300, 200)
    main.qt_viewer.shapes[1].moveTo(400, 20)
    main.qt_viewer.grab()                                # the editor's own paint snaps it
    assert (line.x2(), line.y2()) == (400, 50)
    # "the ROI centre": a connector between the centres of the two shapes
    main.connectSite.setCurrentIndex(main.connectSite.findData('center'))
    main.qt_viewer.selected_shape = [s for s in main.qt_viewer.shapes if isinstance(s, Rectangle2D)]
    assert main.connect_two_shapes()
    centres = [s for s in main.qt_viewer.shapes if isinstance(s, Line2D)][-1]
    assert (centres.x1(), centres.y1(), centres.x2(), centres.y2()) == (35, 30, 430, 50)


def test_a_row_emptied_by_a_move_is_said_to_need_nothing(tmp_path):
    """move_image left an empty third row and the model tried to delete it (user chat
    2026-11-12): it is kept (no renumbering mid-way) and the reply says so."""
    from pyfigures.mcp_server import create_figure, add_image, move_image
    pyf = str(tmp_path / "rows.pyf")
    create_figure(pyf, mode="groups", num_groups=2)
    image = _image(tmp_path)
    add_image(pyf, [0], image)
    add_image(pyf, [1], image)
    out = move_image(pyf, [1], 0, [0], -1)
    assert "is now empty" in out and "nothing needs removing" in out


def test_leader_lines_drawn_before_connectors_are_attached(qapp, gui, runtime, tmp_path):  # noqa: F811
    """A figure from before connectors: one leader line a few pixels off the ROI corner
    stayed behind when the ROI was moved in the editor, and the inset end, fine in the
    editor, missed the inset in the figure (user chat 2026-11-12)."""
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import panels, Image2D
    from pyfigures import connectors
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.line2d import Line2D
    from batoolset.serializations.tools import clone_object
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    launch.start_live_session(g)

    def panel():
        return next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    p = panel()
    roi = Rectangle2D(300, 100, 60, 40, color=0xFFFF00, stroke=2)
    p.annotations.append(roi)
    state = _call(qapp, "inspect")
    _call(qapp, "roi_to_inset", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"panel_ref": "0/0"}, request_id="r1")
    p = panel()
    roi = next(a for a in p.annotations if type(a) is Rectangle2D)
    inset = next(a for a in p.annotations if isinstance(a, Image2D))
    inset.follows_roi = None                              # as saved by an older version
    g.paint.EZFIG_panel.grab()
    x, y, w, h = connectors.shape_box(inset, p)
    # as drawn by hand: one end exactly on a corner, the other 4 px off, the inset ends 20 px off
    p.annotations += [Line2D(300, 100, x + w, y - 20), Line2D(304, 139, x + w + 3, y + h + 20)]
    g.paint.EZFIG_panel.grab()
    lines = [a for a in p.annotations if isinstance(a, Line2D)]
    assert inset.follows_roi == roi.link_id and all(connectors.is_connector(l) for l in lines)
    roi.moveTo(100, 250)
    g.paint.EZFIG_panel.grab()
    x, y, w, h = connectors.shape_box(inset, p)
    ends = sorted((l.x1(), l.y1(), l.x2(), l.y2()) for l in lines)
    assert (inset.crop_left, inset.crop_top) == (100, 250)
    assert all(e[0] in (100, 160) and e[1] in (250, 290) for e in ends)           # on the ROI's corners
    assert all(min(abs(e[2] - x), abs(e[2] - x - w)) < 1e-6 and min(abs(e[3] - y), abs(e[3] - y - h)) < 1e-6
               for e in ends)                                                   # on the inset's corners
    # saved and opened again, still attached
    copy = clone_object(lines[0])
    assert connectors.is_connector(copy)


def test_an_inset_follows_its_roi_and_its_lines_too(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'I made the changes then pressed ok yet changes did not make it to the figure': the
    ROI had moved, its inset and the leader lines had not."""
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import panels, Image2D
    from batoolset.drawings.shapes.rectangle2d import Rectangle2D
    from batoolset.drawings.shapes.line2d import Line2D
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    launch.start_live_session(g)

    def panel():
        return next(p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw))
    panel().annotations.append(Rectangle2D(60, 250, 90, 70, color=0xFFFF00, stroke=2))
    state = _call(qapp, "inspect")
    _call(qapp, "roi_to_inset", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"panel_ref": "0/0"}, request_id="r1")
    state = _call(qapp, "inspect")
    _call(qapp, "original_tool", session_id=state["session_id"], expected_revision=state["revision"],
          arguments={"tool": "connect_roi_to_inset", "arguments": {"pyf_path": "live", "group_path": [0],
                                                                   "image_index": 0}}, request_id="r2")
    p = panel()
    roi = next(a for a in p.annotations if type(a) is Rectangle2D)
    inset = next(a for a in p.annotations if isinstance(a, Image2D))
    lines = [a for a in p.annotations if isinstance(a, Line2D)]
    assert inset.follows_roi == roi.link_id and len(lines) == 2 and all(l.connect_start for l in lines)
    before = [(l.x1(), l.y1()) for l in lines]
    roi.moveTo(200, 100)                                  # moved by hand, as in the editor
    g.paint.EZFIG_panel.grab()
    assert (inset.crop_left, inset.crop_top) == (200, 100)              # the inset shows the new region
    assert [(l.x1(), l.y1()) for l in lines] != before
    assert all(200 - 1 <= l.x1() <= 290 + 1 and 100 - 1 <= l.y1() <= 170 + 1 for l in lines)
