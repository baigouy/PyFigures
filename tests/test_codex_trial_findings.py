"""Problems found by the paid-model (Codex / ChatGPT) trial of the MCP server,
2026-10-19 (chatGPT_validation/2026-10-18_claude/runs/codex_tools).

- an HTML letter without a colour ("<b>A</b>") came out black, invisible on
  fluorescence; the model then added white copies on top (duplicate letters);
- re-adding a label with the same text at the same corner stacked a copy;
- the merge of a channel split turned magenta, its "Lamp1" label stayed red.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def dark_rgb(tmp_path):
    from PIL import Image
    a = np.zeros((60, 80, 3), np.uint8)
    a[20:40, 20:60] = (200, 80, 30)
    path = tmp_path / "cells.png"
    Image.fromarray(a).save(path)
    return str(path)


def _labels(pyf, group_path=(0,), index=0):
    from pyfigures.mcp_tools.core import _child_text
    root = ET.parse(pyf).getroot()
    node = root
    for k in group_path:
        node = node.findall("Group")[k] if node is root else node.find("content").findall("Group")[k]
    img = node.find("content").findall("Image2D")[index]
    return [_child_text(t, "text") for t in img.findall("annotations/TAText2D")]


def test_html_letter_without_colour_is_white_on_a_dark_image(tmp_path, dark_rgb):
    import pyfigures.mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], dark_rgb)
    M.add_corner_labels(pyf, [0], 0, top_left=["<b>A</b>"])
    M.add_annotation(pyf, [0], 0, "<i>x</i>", placement="bottom right")
    M.add_annotation(pyf, [0], 0, '<span style="color:yellow">y</span>', placement="top right")
    a, x, y = _labels(pyf)
    assert "#ffffff" in a.lower() and "<b>A</b>" in a
    assert "#ffffff" in x.lower()
    assert "#ffffff" not in y.lower() and "color:yellow" in y           # its own colour kept


def test_same_label_at_the_same_corner_replaces_the_old_one(tmp_path, dark_rgb):
    import pyfigures.mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], dark_rgb)
    M.add_corner_labels(pyf, [0], 0, top_left=["<b>A</b>"])
    res = M.add_corner_labels(pyf, [0], 0, top_left=['<span style="color:white"><b>A</b></span>'])
    assert "1 existing label(s) with the same text replaced" in res
    assert len(_labels(pyf)) == 1
    assert M.add_annotation(pyf, [0], 0, "A", placement="top left").startswith("Replaced")
    assert len(_labels(pyf)) == 1
    # another corner, other text, or repeats inside one call are added
    M.add_annotation(pyf, [0], 0, "A", placement="bottom left")
    M.add_corner_labels(pyf, [0], 0, top_right=["*", "*"])
    M.add_corner_labels(pyf, [0], 0, top_left=["WT"])
    assert len(_labels(pyf)) == 5


def test_merge_lut_change_recolours_the_split_channel_names(tmp_path, dark_rgb):
    import pyfigures.mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="Y")
    M.add_channel_split(pyf, stack_path=dark_rgb, parent_group_path=[0],
                        names=["Lamp1", "mito", "DNA"], colors=["red", "green", "blue"])
    res = M.set_lut(pyf, [0, 0], 3, ["MAGENTA", "GREEN", "BLUE"])
    assert "Lamp1 label magenta" in res
    lamp1 = _labels(pyf, (0, 0), 0)[0]
    assert "#ff40ff" in lamp1.lower() and "Lamp1" in lamp1
    assert "#40ff40" in _labels(pyf, (0, 0), 1)[0].lower()              # unchanged green

    # tinted singles take the new tint
    pyf2 = str(tmp_path / "g.pyf")
    M.create_figure(pyf2, mode="groups", num_groups=1, orientation="Y")
    M.add_channel_split(pyf2, stack_path=dark_rgb, parent_group_path=[0], gray=False,
                        names=["Lamp1", "mito", "DNA"], colors=["red", "green", "blue"])
    M.set_lut(pyf2, [0, 0], 3, ["MAGENTA", None, None])
    luts = M.get_image_property(pyf2, [0, 0], 0, "LUTs")
    assert "MAGENTA" in luts and "RED" not in luts


def test_zoom_corner_accepts_underscores_and_hyphens(tmp_path, dark_rgb):
    import pyfigures.mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], dark_rgb)
    for corner in ("top_left", "Bottom-Right"):
        res = M.add_zoom_callout(pyf, [0], 0, source_x=20, source_y=20, source_w=10, source_h=10,
                                 parent_width=80, parent_height=60, inset_corner=corner)
        assert not res.startswith("ERROR"), res
    assert M.add_zoom_callout(pyf, [0], 0, source_x=20, source_y=20, source_w=10, source_h=10,
                              parent_width=80, parent_height=60,
                              inset_corner="middle").startswith("ERROR")


def test_gui_merge_lut_change_recolours_the_split_channel_names(qapp, tmp_path, dark_rgb):
    import pyfigures.mcp_server as M
    from batoolset.lists.tools import flatten_iterable
    from pyfigures.gui.headless_ops import _build_gui
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="Y")
    M.add_channel_split(pyf, stack_path=dark_rgb, parent_group_path=[0],
                        names=["Lamp1", "mito", "DNA"], colors=["red", "green", "blue"])
    _app, gui = _build_gui(pyf)
    try:
        panel = gui.paint.EZFIG_panel
        imgs = [s for s in flatten_iterable(panel.shapes_to_draw) if hasattr(s, "LUTs")]
        merge = [s for s in imgs if str(s.user_comments).endswith("merge")][0]
        lamp1 = [s for s in imgs if str(s.user_comments).endswith("Lamp1")][0]
        merge.LUTs = ["MAGENTA", "GREEN", "BLUE"]
        panel._match_split_colours(merge)
        html = lamp1.annotations[0].getHtmlText().lower()
        assert "#ff40ff" in html and "#ff4040" not in html
    finally:
        gui._dirty = False
        gui.hide()
        gui._stop_all_img_loaders()
