"""Layout formulas (pyfigures/layout_formula.py) and the recipe key ``layout:``.

``(a,b,c)/(d,e,f)`` — ``,`` or ``|`` side by side, ``/`` stacked, ``( )``
nesting to any depth (a group spans the rows / columns it holds), ``[ ]`` a
grid of equal cells. Notation inspired by Griphus.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import layout_formula as L


# ---------------------------------------------------------------- parser

@pytest.mark.parametrize("text, normalised, ids", [
    ("(1,2,3)/(4,5,6)", "(1,2,3)/(4,5,6)", list("123456")),
    ("a,b/c,d", "(a,b)/(c,d)", list("abcd")),                   # , binds tighter than /
    ("a|b|c / d|e|f", "(a,b,c)/(d,e,f)", list("abcdef")),        # | = , ; spaces ignored
    ("(a,(b/c))/d", "(a,(b/c))/d", list("abcd")),
    ("((A/D),((B,C)/E/F))/(H,G)", "((A/D),((B,C)/E/F))/(H,G)", list("ADBCEFHG")),   # Griphus
    ("((a,b),c)", "a,b,c", list("abc")),                         # same direction: flattened
    ("[a,b/c,d]/e", "[(a,b)/(c,d)]/e", list("abcde")),
    ("img_1.png|img_2.tif", "img_1.png,img_2.tif", ["img_1.png", "img_2.tif"]),
])
def test_parse(text, normalised, ids):
    tree = L.parse(text)
    assert L.to_text(tree) == normalised
    assert L.panel_ids(tree) == ids
    assert L.to_text(L.parse(L.to_text(tree))) == normalised     # stable


def test_tree_shape_of_a_spanning_panel():
    t = L.parse("(a,(b/c))/d")
    assert t["type"] == "col"
    top = t["children"][0]
    assert top["type"] == "row" and top["children"][1]["type"] == "col"


@pytest.mark.parametrize("text, where", [
    ("(a,b))/c", "character 6"),
    ("(a,(b/c)", "found the end"),
    ("a,,b", "unexpected ','"),
    ("()", "empty ( )"),
    ("[a]", "at least two cells"),
    ("", "empty"),
    ("a/", "is missing"),
])
def test_errors_point_at_the_problem(text, where):
    with pytest.raises(L.FormulaError, match=where.replace("(", r"\(").replace(")", r"\)")):
        L.parse(text)


def test_grid_cells():
    t = L.parse("[a,b,c/d,e,f]")
    assert L.grid_cells(t) == [["a", "b", "c"], ["d", "e", "f"]]


# ---------------------------------------------------------------- recipes

def _img(path, w, h, value):
    from PIL import Image
    rng = np.random.default_rng(value)
    Image.fromarray((rng.random((h, w)) * 200 + 20).astype(np.uint8)).save(path)
    return str(path)


@pytest.fixture
def files(tmp_path):
    out = {}
    for name, (w, h) in {"a": (100, 80), "b": (100, 80), "c": (100, 80), "d": (100, 80),
                         "e": (100, 80), "f": (100, 80), "wide": (200, 80),
                         "tall": (80, 160)}.items():
        out[name] = _img(tmp_path / f"{name}.png", w, h, len(out) + 1)
    (tmp_path / "data.csv").write_text("Control,Treated\n1,2\n2,3\n3,4\n", encoding="utf-8")
    from PIL import Image
    rgb = (np.random.default_rng(9).random((80, 120, 3)) * 255).astype(np.uint8)
    Image.fromarray(rgb).save(tmp_path / "rgb.png")
    return tmp_path


def _build(folder, text):
    import pyfigures.mcp_server as M
    res = M.build_figure_from_recipe(str(folder / "r.yaml"), recipe_text=text)
    return res if res.startswith("ERROR") else json.loads(res)


def _tree(pyf):
    """Nested structure of the saved figure: groups as (orientation, [children]),
    images as their file's base name (letters in brackets)."""
    from pyfigures.mcp_tools.core import _child_text, _decode
    root = ET.parse(pyf).getroot()

    def node(el):
        if el.tag == "Group":
            o = _decode(_child_text(el, "orientation"))
            return (o, [node(c) for c in el.find("content")])
        name = os.path.splitext(os.path.basename(str(_decode(_child_text(el, "filename")))))[0]
        letters = [_child_text(t, "text") for t in el.findall("annotations/TAText2D")
                   if _child_text(t, "is_letter") is True]
        return name + (f"[{letters[0]}]" if letters else "")

    return [node(g) for g in root.findall("Group")]


def _letter(s):
    import re
    from pyfigures.mcp_tools.core import _label_plain_text
    return re.sub(r"\[(.*)\]", lambda m: "[" + _label_plain_text(m.group(1)).strip() + "]", s,
                  flags=re.S)


def test_two_rows_of_three(files, qapp):
    res = _build(files, "output: f.pyf\nlayout: (a,b,c)/(d,e,f)\n")
    assert res["images"] == 6, res
    t = _tree(str(files / "f.pyf"))
    assert [g[0] for g in t] == ["X", "X"]
    assert [[_letter(x) for x in g[1]] for g in t] == \
        [["a[A]", "b[B]", "c[C]"], ["d[D]", "e[E]", "f[F]"]]


def test_nested_spanning_panel_geometry(files, qapp):
    from pyfigures.mcp_tools.core import _load_objects_lazy
    res = _build(files, "output: f.pyf\nletter_panels: false\nlayout: (tall,(a/b))/wide\n")
    assert not isinstance(res, str), res
    t = _tree(str(files / "f.pyf"))
    assert t == [("X", ["tall", ("Y", ["a", "b"])]), ("X", ["wide"])]
    objs, Group, Image2D = _load_objects_lazy(str(files / "f.pyf"))
    top = [o for o in objs if isinstance(o, Group)][0]
    tall, col = top.content
    a, b = col.content
    ra, rb, rt = a.getRect(all=True), b.getRect(all=True), tall.getRect(all=True)
    # the tall panel spans both stacked panels: same top, same bottom
    assert abs(rt.top() - ra.top()) < 1.5 and abs(rt.bottom() - rb.bottom()) < 1.5
    assert ra.left() > rt.right() and abs(ra.width() - rb.width()) < 1


def test_griphus_example(files, qapp):
    text = ("output: f.pyf\nletter_panels: false\n"
            "layout: ((a/d),((b,c)/e/f))/(wide,tall)\n")
    res = _build(files, text)
    assert not isinstance(res, str), res
    assert _tree(str(files / "f.pyf")) == [
        ("X", [("Y", ["a", "d"]), ("Y", [("X", ["b", "c"]), "e", "f"])]),
        ("X", ["wide", "tall"])]


def test_named_panels_keep_their_settings(files, qapp):
    import pyfigures.mcp_server as M
    text = ("output: f.pyf\nlayout: (s,plot)/(x|y)\n"
            "panels:\n"
            "  x: {image: a.png, crop: {left: 10}, lut: green, px_to_unit: 0.5, "
            "scale_bar: {units: 10, unit: um}}\n"
            "  y: b.png\n"
            "  s: {split: rgb.png, names: [r, g, b]}\n"
            "  plot: {plot: data.csv, kind: box}\n")
    res = _build(files, text)
    assert not isinstance(res, str), res
    t = _tree(str(files / "f.pyf"))
    assert t[0][0] == "X" and t[0][1][0][0] == "X"          # the split row kept as a group
    assert [_letter(x) for x in t[1][1]] == ["a[F]", "b[G]"]  # A-D = split (r, g, b, merge), E = plot
    assert M.get_image_property(str(files / "f.pyf"), [1], 0, "crop_left").endswith("10")
    assert "GREEN" in M.get_image_property(str(files / "f.pyf"), [1], 0, "LUTs")
    assert "scale bar" in M.describe_figure(str(files / "f.pyf")).lower()


def test_grid_cells_line_up(files, qapp):
    from pyfigures.mcp_tools.core import _load_objects_lazy
    res = _build(files, "output: f.pyf\nletter_panels: false\nlayout: '[a,wide/tall,b]'\n")
    assert not isinstance(res, str), res
    objs, Group, Image2D = _load_objects_lazy(str(files / "f.pyf"))
    rows = [o for o in objs if isinstance(o, Group)]
    cells = [c for g in rows for c in g.content]
    ratios = {round(c.getRect(all=True).width() / c.getRect(all=True).height(), 2) for c in cells}
    assert len(ratios) == 1, ratios                    # one aspect ratio: aligned cells
    r1, r2 = [[c.getRect(all=True) for c in g.content] for g in rows]
    assert abs(r1[0].left() - r2[0].left()) < 1 and abs(r1[1].left() - r2[1].left()) < 1
    assert any("cropped" in w for w in res["warnings"])


@pytest.mark.parametrize("text, message", [
    ("layout: (a,zz)", "'zz'"),
    ("layout: (a,a)", "twice"),
    ("layout: (a,b)\npanels:\n  a: a.png\n  b: b.png\n  c: c.png", "not in the layout"),
    ("layout: (a,b))", "more ')' than '('"),
    ("layout: (a,b)\nrows:\n  - [a.png]", "either"),
    ("layout: (a,b)\npanels: [a.png, b.png]", "mapping"),
])
def test_bad_layouts_are_refused_before_building(files, text, message):
    res = _build(files, "output: bad.pyf\n" + text + "\n")
    assert isinstance(res, str) and res.startswith("ERROR") and message in res, res
    assert not (files / "bad.pyf").exists()


# ---------------------------------------------------------------- pictures

@pytest.mark.parametrize("picture, formula", [
    ("a a b\na a c\nd e f", "(a,(b/c))/(d,e,f)"),
    ("a b c\nd e f", "(a,b,c)/(d,e,f)"),
    ("x x y\nz w w", "(x,y)/(z,w)"),
    ("a b\na c\na d", "a,(b/c/d)"),
])
def test_picture_is_cut_into_rows_and_columns(picture, formula):
    from pyfigures import layout_picture as P
    assert P.is_picture(picture)
    assert P.to_formula(P.parse(picture)) == formula


@pytest.mark.parametrize("picture, message", [
    ("a a b\nd e b\nd c c", "pinwheel"),
    ("a a\na b", "not a rectangle"),
    ("a b\nc", "line 2 has 1 cells"),
])
def test_bad_pictures(picture, message):
    from pyfigures import layout_picture as P
    with pytest.raises(L.FormulaError, match=message):
        P.parse(picture)


def test_picture_recipe_lines_up_spanning_panels(files, qapp):
    from pyfigures.mcp_tools.core import _load_objects_lazy
    text = ("output: f.pyf\nletter_panels: false\nlayout: |\n"
            "  wide wide b\n  wide wide c\n  d e f\n")
    res = _build(files, text)
    assert not isinstance(res, str), res
    assert _tree(str(files / "f.pyf")) == [("X", ["wide", ("Y", ["b", "c"])]), ("X", ["d", "e", "f"])]
    objs, Group, Image2D = _load_objects_lazy(str(files / "f.pyf"))
    top, bottom = [o for o in objs if isinstance(o, Group)]
    wide, col = top.content
    rw, rc = wide.getRect(all=True), col.getRect(all=True)
    assert abs(rw.top() - rc.top()) < 1.5 and abs(rw.bottom() - rc.bottom()) < 1.5
    d, e, f = [x.getRect(all=True) for x in bottom.content]
    # 2 x 2 cells: the wide panel is about two cells wide and tall (gaps aside)
    assert abs(rw.width() - 2 * d.width()) < 0.05 * rw.width()
    assert abs(f.left() - rc.left()) < 0.05 * rw.width()           # columns line up
    assert any("cells'" in w for w in res["warnings"])


def test_recipe_reference_and_cli_document_the_formula(capsys):
    import pyfigures.mcp_server as M
    ref = json.loads(M.recipe_reference())
    assert "layout" in ref["top_level_keys"] and "Griphus" in json.dumps(ref)
    assert L.main(["(a,b)/c"]) == 0
    assert '"panels_in_reading_order"' in capsys.readouterr().out
