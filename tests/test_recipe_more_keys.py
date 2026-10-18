"""The recipe keys added so a recipe can express (almost) everything the GUI
and the MCP tools can do: rotate / flip, channels, z_range, display_range,
text, corner_labels, rois, brackets, inset, zoom; merge / colorbar / script
panels; row mappings (orientation, spacing, label row, side label); and the
figure-wide width_* / dpi, font, min_font_pt, tidy_text, letter_placement,
auto_configure, alt_text, copy_style_from, exports, allow_scripts.

Each key is checked in the built .pyf (or the files it writes), and every
key's validation error is checked too.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

RECIPE = """
output: out/fig.pyf
width_mm: 120
dpi: 300
font: {family: Arial, size: 9}
min_font_pt: 6
tidy_text: true
letter_placement: top right
alt_text: auto
copy_style_from: style.pyf
copy_style_aspects: [letters]
allow_scripts: true
exports: [png, {format: pdf}, source_data, review, caption]
rows:
  - panels:
      - image: a.tif
        rotate: 15
        flip: h
        display_range: [10, 200]
        text: ["WT", {text: "n = 12", placement: bottom right}, "40*60, 37 degrees C"]
        corner_labels: {top_left: ["x"], bottom_right: "10x"}
        rois:
          - {rect: [5, 5, 20, 10], color: cyan}
          - {ellipse: [10, 10, 15, 15]}
          - {line: [0, 0, 30, 30], arrow: true}
          - {polygon: [[1, 1], [30, 2], [15, 25]]}
          - {circle: [30, 30, 6], color: magenta}
          - {square: [40, 20, 8]}
          - {points: [[5, 30], [12, 34]], color: red, size: 4}
        brackets: [{x1: 5, x2: 40, y: 8, label: "**"}]
      - image: rgb.tif
        channels: [true, false, true]
        inset: {image: b.tif, placement: bottom left, size: 0.3}
        zoom: {box: [10, 10, 15, 15], corner: top right}
    labels: [WT, KO]
    labels_position: above
    side_label: "Day 1"
  - orientation: Y
    spacing: 8
    panels:
      - {image: zstack.tif, projection: max, z_range: [1, 3]}
      - {merge: [c1.tif, c2.tif], colors: [green, magenta], label: Merge}
      - {colorbar: magenta, vmin: 0, vmax: 4095, label: "a.u."}
      - script: |
          import numpy as np
          self.img = np.full((40, 50), 128, np.uint8)
        label: Model
"""


def _write_data(d):
    import tifffile
    from batoolset.img import Img
    from pyfigures import mcp_server as M
    Img(np.tile(np.linspace(0, 250, 60).astype(np.uint8), (40, 1)), dimensions="hw").save(str(d / "a.tif"))
    Img(np.full((30, 30), 220, np.uint8), dimensions="hw").save(str(d / "b.tif"))
    c = np.zeros((40, 50, 3), np.uint8)
    c[..., 0] = 200
    c[..., 2] = 120
    Img(c, dimensions="hwc").save(str(d / "rgb.tif"))
    z = np.stack([np.full((40, 50), 40 * i, np.uint8) for i in range(4)])
    tifffile.imwrite(d / "zstack.tif", z, imagej=True, metadata={"axes": "ZYX"})
    Img(np.full((40, 50), 60, np.uint8), dimensions="hw").save(str(d / "c1.tif"))
    Img(np.full((40, 50), 180, np.uint8), dimensions="hw").save(str(d / "c2.tif"))
    M.create_figure(str(d / "style.pyf"), mode="groups", num_groups=1, spacing=9)
    M.add_image(str(d / "style.pyf"), [0], str(d / "c1.tif"))


@pytest.fixture(scope="module")
def built(tmp_path_factory, qapp):
    from pyfigures.recipe import build_figure_from_recipe
    d = tmp_path_factory.mktemp("recipe_more")
    _write_data(d)
    (d / "r.yaml").write_text(RECIPE, encoding="utf-8")
    res = build_figure_from_recipe(str(d / "r.yaml"))
    return res, d


def _annots(pyf):
    from pyfigures import mcp_server as M
    return json.loads(M.get_annotations(pyf))


def _props(pyf, gp, i):
    from pyfigures import mcp_server as M
    return json.loads(M.list_image_properties(pyf, gp, i))


def test_summary_and_no_warnings(built):
    res, _d = built
    assert res["warnings"] == [], res["warnings"]
    assert (res["rows"], res["images"], res["other_panels"]) == (2, 3, 3)


# After the build, top-level group 0 is the label row placed ABOVE row 1, so
# row 1 is group [1] (side label = image 0, a.tif = 1, rgb.tif = 2) and row 2
# is group [2].

def test_rotation_flip_and_display_range(built):
    res, _d = built
    from pyfigures import mcp_server as M
    p = _props(res["output"], [1], 1)
    assert p["filename"].endswith("a.tif")
    assert p["theta"] == 15.0
    assert "flip" in (M.get_script(res["output"], [1], 1) or "").lower()   # a flip is a script step
    norm = str(p["normalization"])
    assert "custom" in norm and "200" in norm and "10" in norm


def test_text_corner_labels_rois_brackets(built):
    res, _d = built
    mine = [a for a in _annots(res["output"]) if a.get("group_path") == [1] and a.get("image_index") == 1]
    kinds = [a["type"] for a in mine]
    texts = [str(a.get("text", "")) for a in mine]
    for t in ("WT", "n = 12", "x", "10x", "**"):
        assert any(t == s or t in s for s in texts), (t, texts)
    for k in ("Rectangle2D", "Ellipse2D", "Line2D", "Polygon2D"):
        assert k in kinds, (k, kinds)
    assert kinds.count("Line2D") >= 4          # the ROI line + the bracket's three strokes
    assert kinds.count("Ellipse2D") == 4       # ellipse + circle + 2 points
    assert kinds.count("Rectangle2D") == 2     # rect + square
    ell = [a for a in mine if a["type"] == "Ellipse2D"]
    assert any((a["x"], a["y"], a["width"], a["height"]) == (24, 24, 12, 12) for a in ell), ell
    assert any((a["x"], a["y"], a["width"], a["height"]) == (3, 28, 4, 4) for a in ell), ell
    rec = [a for a in mine if a["type"] == "Rectangle2D"]
    assert any((a["x"], a["y"], a["width"], a["height"]) == (36, 16, 8, 8) for a in rec), rec
    placements = {str(a.get("text")): a.get("placement") for a in mine if a["type"] == "TAText2D"}
    assert "bottom right" in str(placements.get("n = 12"))
    assert any("40×60, 37 °C" in s for s in texts), texts      # tidy_text


def test_channels_inset_and_zoom(built):
    res, _d = built
    from pyfigures import mcp_server as M
    p = _props(res["output"], [1], 2)
    assert p["filename"].endswith("rgb.tif") and p["channels"] == "[True, False, True]"
    insets = json.loads(M.list_insets(res["output"], [1], 2))
    assert len(insets) == 2                    # the b.tif inset + the zoom callout's magnified view
    assert insets[0]["filename"].endswith("b.tif") and insets[0]["placement"] == "bottom left"
    assert insets[0]["size_fraction"] == 0.3
    zoom_box = [a for a in _annots(res["output"])
                if a.get("group_path") == [1] and a.get("image_index") == 2 and a["type"] == "Rectangle2D"]
    assert zoom_box                            # the callout's box on the source


def test_row_mapping_orientation_spacing_labels_side_label(built):
    res, _d = built
    from pyfigures import mcp_server as M
    imgs = json.loads(M.list_images(res["output"]))
    assert imgs[0]["group_path"] == [1] and imgs[0].get("is_side_label")
    rows = json.loads(M.list_label_rows(res["output"]))
    assert rows and "WT" in json.dumps(rows) and "KO" in json.dumps(rows)
    xml = open(res["output"], encoding="utf-8").read()
    assert "Day 1" in xml
    root = ET.parse(res["output"]).getroot()
    groups = [g for g in root.iter("Group")]
    orientations = [g.findtext("orientation") for g in groups]
    assert any('"Y"' in (o or "") for o in orientations), orientations
    assert any(g.findtext("space") == "8" for g in groups) or "<space>8</space>" in xml


def test_projection_z_range_merge_colorbar_script(built):
    res, _d = built
    from pyfigures import mcp_server as M
    z = _props(res["output"], [2], 0)
    assert z["projection"] == "max" and (z["projection_z_start"], z["projection_z_end"]) == (1, 3)
    imgs = [i for i in json.loads(M.list_images(res["output"])) if i["group_path"] == [2]]
    assert len(imgs) == 4 and all(i["has_script"] for i in imgs[1:])
    scripts = [M.get_script(res["output"], [2], k) for k in (1, 2, 3)]
    assert "c1.tif" in scripts[0] and "c2.tif" in scripts[0]      # the merge reads both files
    assert "ColorbarBase" in scripts[1] and "4095" in scripts[1]
    assert "np.full((40, 50), 128" in scripts[2]
    texts = [str(a.get("text")) for a in _annots(res["output"])
             if a["type"] == "TAText2D" and a.get("group_path") == [2]]
    assert "Merge" in texts and "Model" in texts


def test_colour_bar_gets_no_panel_letter(built):
    res, _d = built
    letters = [a for a in _annots(res["output"]) if a["type"] == "TAText2D"
               and a.get("group_path") == [2] and a.get("image_index") == 2
               and len(str(a.get("text", ""))) == 1]
    assert letters == []


def test_letter_placement(built):
    res, _d = built
    letter = [a for a in _annots(res["output"]) if a["type"] == "TAText2D"
              and a.get("group_path") == [2] and a.get("image_index") == 0
              and len(str(a.get("text", ""))) == 1]
    assert letter and letter[0]["placement"] == "top right"


def test_figure_level_finishing(built):
    res, d = built
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.upkeep import read_alt_text
    props = json.loads(M.get_figure_properties(res["output"]))
    assert "Arial" in json.dumps(props)
    assert read_alt_text(res["output"])        # alt_text: auto
    assert res["size"] == "width_mm=120"
    stem = os.path.splitext(res["output"])[0]
    for path in (stem + ".png", stem + ".pdf", stem + "_source_data", stem + "_review.html",
                 stem + "_caption.txt"):
        assert os.path.exists(path), path
    assert sorted(res["exports"]) == sorted([stem + ".png", stem + ".pdf", stem + "_source_data",
                                             stem + "_review.html", stem + "_caption.txt"])


def test_auto_configure_reads_pixel_size_and_explicit_lut_wins(tmp_path, qapp):
    import tifffile
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures import mcp_server as M
    img = np.full((40, 50), 120, np.uint16)
    tifffile.imwrite(tmp_path / "cal.tif", img, imagej=True, resolution=(1 / 0.5, 1 / 0.5),
                     metadata={"unit": "um"})
    tifffile.imwrite(tmp_path / "cal2.tif", img, imagej=True, resolution=(1 / 0.5, 1 / 0.5),
                     metadata={"unit": "um"})
    (tmp_path / "r.yaml").write_text(
        "output: f.pyf\n"
        "auto_configure: {lut_preset: gray, scale_bar_width: 5}\n"
        "rows:\n  - - cal.tif\n    - {image: cal2.tif, lut: magenta}\n", encoding="utf-8")
    res = build_figure_from_recipe(str(tmp_path / "r.yaml"))
    sb = json.loads(M.get_scale_bar(res["output"], [0], 0))
    assert sb and "5" in json.dumps(sb)
    lut2 = json.dumps(_props(res["output"], [0], 1)).upper()
    assert "MAGENTA" in lut2


def test_copy_style_from_spacing(tmp_path, qapp):
    from pyfigures.recipe import build_figure_from_recipe
    _write_data(tmp_path)
    (tmp_path / "r.yaml").write_text(
        "output: f.pyf\nspacing: 2\ncopy_style_from: style.pyf\ncopy_style_aspects: [spacing]\n"
        "rows:\n  - [a.tif, b.tif]\n", encoding="utf-8")
    res = build_figure_from_recipe(str(tmp_path / "r.yaml"))
    root = ET.parse(res["output"]).getroot()
    spaces = {g.findtext("space") for g in root.iter("Group")}
    assert spaces == {"9"}, spaces             # the style figure's gap replaced 2


def test_journal_and_width_are_exclusive(tmp_path):
    from pyfigures.recipe import _plan, RecipeError
    (tmp_path / "a.tif").write_bytes(b"x")
    with pytest.raises(RecipeError, match="either 'journal' or an explicit width"):
        _plan({"output": "f.pyf", "journal": "nature", "width_mm": 80, "rows": [["a.tif"]]},
              str(tmp_path / "r.yaml"))


@pytest.mark.parametrize("patch,msg", [
    ({"rotate": "a lot"}, "rotate must be a number"),
    ({"flip": "x"}, "flip must be one of"),
    ({"channels": [1, 0]}, "channels must be a list of true/false"),
    ({"z_range": [3, 1]}, "z_range must be"),
    ({"display_range": [5]}, "display_range must be"),
    ({"text": [{"placement": "top left"}]}, "text 1 must be a mapping"),
    ({"corner_labels": {"middle": "x"}}, "corner_labels must map"),
    ({"rois": [{"rect": [1, 2, 3]}]}, "roi 1 rect must be a list of 4 numbers"),
    ({"rois": [{"rect": [1, 2, 3, 4], "ellipse": [1, 2, 3, 4]}]}, "needs exactly one of"),
    ({"rois": [{"polygon": [[1, 2]]}]}, "polygon needs a list"),
    ({"rois": [{"circle": [1, 2]}]}, "roi 1 circle must be a list of 3 numbers"),
    ({"rois": [{"square": [1, 2, 3, 4]}]}, "roi 1 square must be a list of 3 numbers"),
    ({"rois": [{"point": [1, 2, 3]}]}, "roi 1 point must be a list of 2 numbers"),
    ({"rois": [{"points": []}]}, "points needs a list"),
    ({"rois": [{"points": [[1, 2]], "size": 0}]}, "size must be a positive number"),
    ({"brackets": [{"x1": 1, "y": 2}]}, "bracket 1 must be a mapping"),
    ({"inset": {"image": "nope.tif"}}, "inset image not found"),
    ({"zoom": {"box": [1, 2]}}, "zoom 1 'box' must be a list of 4 numbers"),
])
def test_image_key_validation(tmp_path, patch, msg):
    from pyfigures.recipe import _plan, RecipeError
    from batoolset.img import Img
    Img(np.zeros((8, 8), np.uint8), dimensions="hw").save(str(tmp_path / "a.tif"))
    panel = {"image": "a.tif"}
    panel.update(patch)
    with pytest.raises(RecipeError, match=msg.replace("(", r"\(").replace("'", "'")):
        _plan({"output": "f.pyf", "rows": [[panel]]}, str(tmp_path / "r.yaml"))


@pytest.mark.parametrize("recipe_patch,msg", [
    ({"width_mm": 80, "width_px": 500}, "give one figure width"),
    ({"width_px": 10.5}, "'width_px' must be a positive number"),
    ({"dpi": "high"}, "'dpi' must be an integer"),
    ({"font": {"colour": "red"}}, "'font' must be"),
    ({"min_font_pt": 0}, "'min_font_pt' must be a positive"),
    ({"auto_configure": "yes"}, "'auto_configure' must be"),
    ({"alt_text": 3}, "'alt_text' must be"),
    ({"copy_style_from": "missing.pyf"}, "copy_style_from: file not found"),
    ({"copy_style_aspects": ["colours"]}, "'copy_style_aspects' must be"),
    ({"exports": "pdf"}, "'exports' must be a list"),
    ({"exports": ["gif"]}, "format must be one of"),
    ({"exports": [{"format": "png", "size": 3}]}, "allowed keys are"),
    ({"letter_placement": "middle"}, "'letter_placement' must be a corner"),
    ({"tidy_text": "yes"}, "'tidy_text' must be true or false"),
])
def test_figure_key_validation(tmp_path, recipe_patch, msg):
    from pyfigures.recipe import _plan, RecipeError
    from batoolset.img import Img
    Img(np.zeros((8, 8), np.uint8), dimensions="hw").save(str(tmp_path / "a.tif"))
    recipe = {"output": "f.pyf", "rows": [["a.tif"]]}
    recipe.update(recipe_patch)
    with pytest.raises(RecipeError, match=msg.replace("(", r"\(")):
        _plan(recipe, str(tmp_path / "r.yaml"))


@pytest.mark.parametrize("row,msg", [
    ({"orientation": "diagonal", "panels": ["a.tif"]}, "orientation must be X"),
    ({"spacing": -1, "panels": ["a.tif"]}, "spacing must be a non-negative"),
    ({"labels": ["A", "B"], "panels": ["a.tif"]}, "2 labels for 1 panels"),
    ({"labels_position": "left", "panels": ["a.tif"]}, "labels_position must be"),
    ({"side_label_position": "middle", "panels": ["a.tif"]}, "side_label_position must be"),
    ({"panels": ["a.tif"], "colour": "red"}, "unknown"),
    ({"labels": ["A"]}, "a row mapping needs 'panels'"),
])
def test_row_mapping_validation(tmp_path, row, msg):
    from pyfigures.recipe import _plan, RecipeError
    from batoolset.img import Img
    Img(np.zeros((8, 8), np.uint8), dimensions="hw").save(str(tmp_path / "a.tif"))
    with pytest.raises(RecipeError, match=msg):
        _plan({"output": "f.pyf", "rows": [row]}, str(tmp_path / "r.yaml"))


def test_script_panels_need_allow_scripts(tmp_path):
    from pyfigures.recipe import _plan, RecipeError
    recipe = {"output": "f.pyf", "rows": [[{"script": "self.img = None"}]]}
    with pytest.raises(RecipeError, match="allow_scripts: true"):
        _plan(recipe, str(tmp_path / "r.yaml"))
    recipe["allow_scripts"] = True
    assert _plan(recipe, str(tmp_path / "r.yaml"))["rows"][0][1][0][0] == "script"


def test_every_recipe_key_is_documented():
    from pyfigures import recipe as R
    doc = open(os.path.join(os.path.dirname(__file__), "..", "docs", "RECIPES.md"),
               encoding="utf-8").read()
    keys = set()
    for name in dir(R):
        if name.endswith("_KEYS") and isinstance(getattr(R, name), (set, frozenset)):
            keys |= getattr(R, name)
    keys |= set(R._PANEL_KINDS) | set(R._EXPORTS) | set(R._ROI_SHAPES) | set(R._CORNERS)
    keys |= set(R._CHECKS).union(*R._CHECKS.values())
    missing = sorted(k for k in keys if f"`{k}`" not in doc and f"{k}:" not in doc)
    assert missing == [], missing


def test_merge_needs_two_files(tmp_path):
    from pyfigures.recipe import _plan, RecipeError
    from batoolset.img import Img
    Img(np.zeros((8, 8), np.uint8), dimensions="hw").save(str(tmp_path / "a.tif"))
    with pytest.raises(RecipeError, match="at least two channel files"):
        _plan({"output": "f.pyf", "rows": [[{"merge": ["a.tif"]}]]}, str(tmp_path / "r.yaml"))
    with pytest.raises(RecipeError, match="merge must be a list"):
        _plan({"output": "f.pyf", "rows": [[{"merge": "a.tif"}]]}, str(tmp_path / "r.yaml"))
