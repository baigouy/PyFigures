"""Advanced edits by an MCP client, as the editor does them by hand:
one word of an existing text (bold, subscript…) without touching the rest,
and an existing ROI's outline / fill / dashes / geometry (2026-10-25).
The live session finds them through its categories like any native tool."""
from __future__ import annotations

import json
import os
import re

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pyfigures.mcp_server as M


@pytest.fixture
def fig(tmp_path):
    from PIL import Image
    png = tmp_path / "cells.png"
    Image.fromarray(np.full((100, 160), 80, np.uint8)).save(png)
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], str(png))
    M.add_roi_rect(pyf, [0], 0, x=10, y=10, width=40, height=30, color="yellow",
                   fill_color="red", stroke=2, opacity=0.5)
    M.add_annotation(pyf, [0], 0, "treated vs untreated CO2 at 2 h", placement="bottom left")
    M.add_roi_rect(pyf, [0], 0, x=90, y=50, width=20, height=20)
    return pyf


def _annots(pyf):
    return json.loads(M.get_annotations(pyf))


def _text_html(pyf):
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _decode
    el = next(ET.parse(pyf).getroot().iter("TAText2D"))
    return _decode(el.findtext("text"))


# ---------------------------------------------------------------- text ranges

def test_get_annotations_gives_the_index_text_tools_take(fig):
    a = _annots(fig)
    text = next(e for e in a if e["type"] == "TAText2D")
    assert text["annotation_index"] == 1 and text["text_index"] == 0
    assert all("text_index" not in e for e in a if e["type"] != "TAText2D")


def test_only_the_matched_word_turns_bold(fig):
    out = M.style_annotation(fig, [0], 0, 0, bold=True, match="treated", occurrence=1)
    assert not out.startswith("ERROR"), out
    html = _text_html(fig)
    bold = re.findall(r'<span style="[^"]*font-weight:\s*(?:700|bold)[^"]*">([^<]*)</span>', html)
    assert bold == ["treated"], html
    assert "untreated" in re.sub(r"<[^>]+>", "", html)


def test_the_one_whole_word_is_meant(fig):
    # "treated" is also inside "untreated", but only once a word of its own
    out = M.style_annotation(fig, [0], 0, 0, bold=True, match="treated")
    assert not out.startswith("ERROR"), out
    html = _text_html(fig)
    bold = re.findall(r'<span style="[^"]*font-weight:\s*(?:700|bold)[^"]*">([^<]*)</span>', html)
    assert bold == ["treated"], html


def test_a_character_found_twice_asks_which_and_changes_nothing(fig):
    # "2" in "CO2" and in "2 h": a lone 2 is not "the 2 in CO2", so ask
    before = _text_html(fig)
    out = M.style_annotation(fig, [0], 0, 0, vertical_align="subscript", match="2")
    assert out.startswith("ERROR") and "2 times" in out and "occurrence" in out, out
    assert _text_html(fig) == before


def test_a_word_found_twice_on_its_own_asks_which(tmp_path):
    from PIL import Image
    png = tmp_path / "c.png"
    Image.fromarray(np.full((50, 80), 80, np.uint8)).save(png)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], str(png))
    M.add_annotation(pyf, [0], 0, "control vs control", placement="bottom left")
    before = _text_html(pyf)
    out = M.style_annotation(pyf, [0], 0, 0, bold=True, match="control")
    assert out.startswith("ERROR") and "2 times" in out, out
    assert _text_html(pyf) == before


def test_subscript_of_one_character(fig):
    out = M.style_annotation(fig, [0], 0, 0, vertical_align="subscript", match="2", occurrence=1)
    assert not out.startswith("ERROR"), out
    html = _text_html(fig)
    subs = re.findall(r'<span style="[^"]*vertical-align:\s*sub[^"]*">([^<]*)</span>', html)
    assert subs == ["2"], html
    # the second "2" (in "2 h") is untouched
    body = html[html.index("<body"):]
    assert re.sub(r"<[^>]+>", "", body).count("2") == 2


def test_a_word_not_in_the_text_is_reported(fig):
    out = M.style_annotation(fig, [0], 0, 0, italic=True, match="Treated")
    assert out.startswith("ERROR") and "case-sensitive" in out, out


# ---------------------------------------------------------------- ROIs

def test_outline_only_keeps_geometry_and_fill(fig):
    before = _annots(fig)[0]
    out = json.loads(M.set_roi_properties(fig, [0], 0, 0, stroke=3))
    assert out["changed"] == ["stroke"]
    after = _annots(fig)[0]
    assert after["stroke"] == 3.0
    for k in ("x", "y", "width", "height", "color", "fill_color", "opacity"):
        assert after[k] == before[k], k


def test_remove_fill_dashes_move_and_resize(fig):
    M.set_roi_properties(fig, [0], 0, 0, fill_color="none", line_style="dashed",
                         move_by=[5, -2], width=60)
    a = _annots(fig)[0]
    assert a["fill_color"] is None and a["line_style"] == "dashed"
    assert (a["x"], a["y"], a["width"], a["height"]) == (15.0, 8.0, 60.0, 30.0)
    other = _annots(fig)[2]
    assert (other["x"], other["y"], other["fill_color"]) == (90.0, 50.0, None)   # untouched


def test_line_and_polygon_geometry(fig):
    M.add_roi_line(fig, [0], 0, 0, 0, 30, 30, arrow=True)
    M.add_roi_polygon(fig, [0], 0, points=[[0, 0], [10, 0], [10, 10]])
    a = _annots(fig)
    line = next(e["annotation_index"] for e in a if e["type"] == "Line2D")
    poly = next(e["annotation_index"] for e in a if e["type"] == "Polygon2D")
    M.set_roi_properties(fig, [0], 0, line, x2=50, arrow_at_both_ends=True)
    M.set_roi_properties(fig, [0], 0, poly, move_by=[1, 2])
    a = _annots(fig)
    assert a[line]["x2"] == 50.0 and a[line]["kind"] == "double arrow"
    assert a[poly]["points"] == [[1.0, 2.0], [11.0, 2.0], [11.0, 12.0]]


@pytest.mark.parametrize("kwargs, err", [
    ({"x1": 3}, "has no x1"),
    ({"points": [[0, 0], [1, 1]]}, "has no points"),
    ({"arrow": True}, "only a line"),
    ({"line_style": "wavy"}, "line_style must be"),
    ({"opacity": 2}, "between 0 and 1"),
    ({}, "nothing to change"),
])
def test_wrong_arguments_are_refused(fig, kwargs, err):
    out = M.set_roi_properties(fig, [0], 0, 0, **kwargs)
    assert out.startswith("ERROR") and err in out, out


def test_a_text_is_not_a_roi(fig):
    out = M.set_roi_properties(fig, [0], 0, 1, stroke=2)
    assert out.startswith("ERROR") and "style_annotation" in out


def test_the_gui_reads_the_edited_roi(qapp, fig):
    import gui_e2e_harness as H
    M.set_roi_properties(fig, [0], 0, 0, fill_color="none", line_style="dotted", stroke=4)
    g = H.new_gui(qapp)
    try:
        H.load(qapp, g, fig)
        img = H.images(g)[0]
        rect = next(a for a in img.annotations if type(a).__name__ == "Rectangle2D")
        assert rect.fill_color is None and rect.line_style == [1, 3] and rect.stroke == 4.0
    finally:
        g._mark_clean()
        H.close_gui(qapp, g)


def test_the_live_session_files_them_where_a_model_looks():
    from pyfigures.assistant.categorized_mcp import category_for
    assert category_for("set_roi_properties") == "annotations"
    assert category_for("style_annotation") == "lettering"
