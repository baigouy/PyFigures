"""MCP stack_with_image = the GUI drop choice "Stack with it (column in the
row)": A | B plus C gives A | (B / C); the guides that teach it and the other
help supplements (arrowheads, text style, review comments) are found by the
words people use.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def fig(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    paths = []
    for name in "abcd":
        p = str(tmp_path / f"{name}.tif")
        Img((np.random.default_rng(ord(name)).random((40, 50)) * 255).astype(np.uint8), dimensions="hw").save(p)
        paths.append(p)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=2)
    add_image(pyf, [0], paths[0])
    add_image(pyf, [0], paths[1])
    add_image(pyf, [1], paths[2])
    add_image(pyf, [1], paths[3])
    return pyf


def _layout(pyf):
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _decode

    def node(e):
        if e.tag == "Image2D":
            return os.path.basename(_decode(e.findtext("filename")))[0]
        return (_decode(e.findtext("orientation")),
                [node(c) for c in e.find("content") if c.tag in ("Image2D", "Group")])
    return [node(e) for e in ET.parse(pyf).getroot() if e.tag == "Group"]


def test_stack_an_image_of_another_row_under_an_image_of_a_row(fig):
    from pyfigures.mcp_server import stack_with_image
    r = stack_with_image(fig, [1], 0, [0], 1)
    assert r.startswith("Stacked"), r
    assert _layout(fig) == [("X", ["a", ("Y", ["b", "c"])]), ("X", ["d"])]


def test_the_last_image_of_a_row_leaves_no_empty_row(fig):
    from pyfigures.mcp_server import stack_with_image
    stack_with_image(fig, [1], 0, [0], 0)
    # image indices count the group's own images: b is now image 0 of row 0
    stack_with_image(fig, [1], 0, [0], 0)
    assert _layout(fig) == [("X", [("Y", ["a", "c"]), ("Y", ["b", "d"])])]


def test_bad_targets_are_refused(fig):
    from pyfigures.mcp_server import stack_with_image
    assert stack_with_image(fig, [0], 0, [], 0).startswith("ERROR")
    assert stack_with_image(fig, [0], 0, [0], 0).startswith("ERROR")
    assert stack_with_image(fig, [0], 0, [0], 5).startswith("ERROR")
    assert stack_with_image(fig, [3], 0, [0], 1).startswith("ERROR")
    assert _layout(fig) == [("X", ["a", "b"]), ("X", ["c", "d"])]


@pytest.mark.parametrize("query, expected", [
    ("how do I stack an image under another one in a row", "stack_in_row"),
    ("add an arrowhead pointing at the nucleus", "arrowheads"),
    ("change the font of the scale bar numbers", "text_style"),
    ("make the labels bold", "text_style"),
    ("send the figure to my co-authors for comments", "review_comments"),
    ("italicize words in the caption", "figure_caption"),
])
def test_help_supplements_are_authored_guides(query, expected):
    from pyfigures import guides
    gid, cands = guides.find_guide(query)
    assert gid == expected, (query, gid, cands)
    assert guides.explain(query)["status"] == "explained"
