"""The recipe route as used by an MCP client (a language model).

A model writes the whole figure as one recipe and builds it in one call; it may
have no file-writing tool, so the recipe can be given inline. Invalid values
are refused before anything is built (``journal: true`` used to save a partial
figure and then crash), and recipe_reference lists every accepted key.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


@pytest.fixture
def images(tmp_path):
    from PIL import Image
    for name in ("a.png", "b.png"):
        Image.new("L", (64, 48), 120).save(tmp_path / name)
    return tmp_path


def test_inline_recipe_is_saved_and_built(images, qapp):
    text = ("output: fig.pyf\n"
            "journal: nature\n"
            "column: double\n"
            "rows:\n"
            "  - [a.png, b.png]\n")
    recipe = images / "fig.yaml"
    res = json.loads(M.build_figure_from_recipe(str(recipe), recipe_text=text))
    assert res["images"] == 2
    assert recipe.read_text(encoding="utf-8") == text
    assert (images / "fig.pyf").is_file()


def test_inline_json_recipe(images, qapp):
    text = json.dumps({"output": "f.pyf", "rows": [["a.png"]]})
    res = json.loads(M.build_figure_from_recipe(str(images / "f.json"), recipe_text=text))
    assert res["images"] == 1


@pytest.mark.parametrize("bad, message", [
    ("journal: true", "journal"),
    ("journal: natur", "Unknown journal"),
    ("journal: nature\ncolumn: triple", "column"),
])
def test_bad_journal_is_refused_before_building(images, qapp, bad, message):
    text = f"output: bad.pyf\n{bad}\nrows:\n  - [a.png]\n"
    res = M.build_figure_from_recipe(str(images / "bad.yaml"), recipe_text=text)
    assert res.startswith("ERROR") and message.lower() in res.lower(), res
    assert not (images / "bad.pyf").exists()


def test_panel_key_at_the_top_says_to_use_defaults(images):
    """A local model put 'scale_bar:' at the top of the recipe 46 times in a
    row: the error only listed the allowed keys."""
    res = M.build_figure_from_recipe(str(images / "f.yaml"), recipe_text=(
        "output: f.pyf\nscale_bar: {units: 10}\nrows:\n  - [a.png, b.png]\n"))
    assert res.startswith("ERROR") and "defaults: {scale_bar: {\"units\": 10}}" in res, res
    assert not (images / "f.pyf").exists()


def test_pixel_size_inside_the_scale_bar_and_zoom_inset_fraction(images, qapp):
    """scale_bar: {units, px_to_unit} and zoom inset_fraction were refused (a
    local model retried them ~50 times); they are natural, so accepted."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    Image.new("L", (400, 300), 120).save(images / "big.png")
    res = M.build_figure_from_recipe(str(images / "f.yaml"), recipe_text=(
        "output: f.pyf\n"
        "defaults: {scale_bar: {units: 2, unit: um, px_to_unit: 0.1}}\n"
        "rows:\n"
        "  - - {image: big.png, zoom: {box: [100, 100, 40, 40], inset_fraction: 0.3}}\n"
        "    - a.png\n"))
    assert not res.startswith("ERROR"), res
    root = ET.parse(images / "f.pyf").getroot()
    assert len(list(root.iter("ScaleBar"))) >= 2
    bad = M.build_figure_from_recipe(str(images / "g.yaml"), recipe_text=(
        "output: g.pyf\nrows:\n  - - {image: big.png, zoom: {box: [100, 100, 40, 40], size: 1.5}}\n"))
    assert bad.startswith("ERROR") and "fraction" in bad and "1.5" in bad, bad
    two = M.build_figure_from_recipe(str(images / "h.yaml"), recipe_text=(
        "output: h.pyf\nrows:\n  - - {image: a.png, px_to_unit: 0.2, "
        "scale_bar: {units: 1, px_to_unit: 0.1}}\n"))
    assert two.startswith("ERROR") and "two pixel sizes" in two, two


def test_misuses_of_an_rgb_image_are_refused_or_warned(tmp_path, qapp):
    """From a local model's final figure: a crop larger than the image was
    drawn stretched; 'lut: red' on an RGB image and a merge of the same RGB file
    three times changed nothing, silently."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    rgb = tmp_path / "rgb.png"
    Image.new("RGB", (512, 400), (30, 60, 90)).save(rgb)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(rgb))
    before = pyf.read_bytes()
    res = M.transform_image(str(pyf), [0], 0, crop_left=430, crop_right=430)
    assert res.startswith("ERROR") and "512 x 400" in res and "860" in res, res
    assert pyf.read_bytes() == before
    assert M.transform_image(str(pyf), [0], 0, crop_bottom=-3).startswith("ERROR")
    assert not M.transform_image(str(pyf), [0], 0, crop_bottom=24).startswith("ERROR")
    assert "WARNING" in M.set_lut(str(pyf), [0], 0, ["RED"])
    assert "WARNING" not in M.set_lut(str(pyf), [0], 0, ["MAGENTA", "GREEN", "BLUE"])
    res = M.add_channel_merge(str(pyf), [0], [str(rgb)] * 3, colors=["red", "green", "blue"])
    assert "WARNING" in res and "same file" in res and "add_channel_split" in res
    grey = tmp_path / "g.png"
    Image.new("L", (64, 64), 50).save(grey)
    grey2 = tmp_path / "g2.png"
    Image.new("L", (64, 64), 90).save(grey2)
    assert "WARNING" not in M.add_channel_merge(str(pyf), [0], [str(grey), str(grey2)])
    bad = M.build_figure_from_recipe(str(tmp_path / "r.yaml"), recipe_text=(
        "output: r.pyf\nrows:\n  - - {image: rgb.png, crop: {left: 430, right: 430}}\n"))
    assert bad.startswith("ERROR") and "removes the whole image" in bad and "zoom" in bad, bad
    assert not (tmp_path / "r.pyf").exists()            # refused before building
    ET.parse(pyf)                                       # the figure stays valid


def test_bar_longer_than_the_image_and_zoom_box_outside_are_refused(tmp_path, qapp):
    """From a 28B model's final figure: a 100 µm bar at 0.1 µm/px (1000 px) on
    512 / 672 px images was drawn cut to the panel (a wrong length), and a zoom
    box given as x1, y1, x2, y2 ran past the image and magnified a smear."""
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (512, 400), 90).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    before = pyf.read_bytes()
    res = M.set_scale_bar(str(pyf), [0], 0, 100, px_to_unit=0.1)
    assert res.startswith("ERROR") and "1000 px" in res and "512 px" in res and "10 µm" in res, res
    assert pyf.read_bytes() == before
    assert M.set_scale_bar_all(str(pyf), 100, px_to_unit=0.1).startswith("ERROR")
    assert not M.set_scale_bar(str(pyf), [0], 0, 10, px_to_unit=0.1).startswith("ERROR")
    res = M.add_zoom_callout(str(pyf), [0], 0, 400, 250, 460, 350,
                             parent_width=512, parent_height=400)
    assert res.startswith("ERROR") and "outside" in res, res
    assert not M.add_zoom_callout(str(pyf), [0], 0, 400, 250, 60, 100,
                                  parent_width=512, parent_height=400).startswith("ERROR")
    bad = M.build_figure_from_recipe(str(tmp_path / "r.yaml"), recipe_text=(
        "output: r.pyf\ndefaults: {px_to_unit: 0.1, scale_bar: {units: 100}}\n"
        "rows:\n  - [i.png]\n"))
    assert bad.startswith("ERROR") and "shorter bar" in bad, bad


def test_caption_stub_matches_the_panel_letters(tmp_path, qapp):
    """A channel split is one lettered panel: the stub listed (A)-(F) for a
    figure lettered A-C."""
    import numpy as np
    import tifffile
    from pyfigures.mcp_tools.workflow import _caption_stub
    stack = tmp_path / "cells.tif"
    tifffile.imwrite(str(stack), np.zeros((2, 40, 50), np.uint8), imagej=True, metadata={"axes": "CYX"})
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n", encoding="utf-8")
    from PIL import Image
    Image.new("L", (50, 40), 90).save(tmp_path / "i.png")
    res = M.build_figure_from_recipe(str(tmp_path / "f.yaml"), recipe_text=(
        "output: f.pyf\nrows:\n  - - {split: cells.tif, names: [GFP, RFP]}\n"
        "  - - i.png\n    - {plot: d.csv, kind: box}\n"))
    assert not res.startswith("ERROR"), res
    stub = _caption_stub(str(tmp_path / "f.pyf"))
    assert "(A) cells (GFP, RFP" in stub and "(B) i" in stub and "(C) data plot" in stub, stub
    assert "(D)" not in stub


def test_bad_stats_mode_says_what_it_got(tmp_path, qapp):
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n", encoding="utf-8")
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    res = M.add_data_plot(str(pyf), [0], str(csv), kind="box", stats_mode="t-test")
    assert "'t-test'" in res and "'parametric'" in res


def test_invalid_recipe_text_is_refused(images):
    res = M.build_figure_from_recipe(str(images / "x.yaml"), recipe_text="- just\n- a list\n")
    assert res.startswith("ERROR")
    assert M.build_figure_from_recipe(str(images / "x.txt"), recipe_text="output: a.pyf").startswith("ERROR")


def test_split_crop_applies_to_every_panel(tmp_path, qapp):
    """The paper's first request — a channel split with the burned-in text
    cropped away — could not be written as a recipe: split took no crop."""
    import numpy as np
    import xml.etree.ElementTree as ET
    from PIL import Image
    rgb = np.zeros((60, 80, 3), np.uint8)
    rgb[..., 0] = 200
    rgb[..., 1] = 100
    Image.fromarray(rgb).save(tmp_path / "cells.png")
    text = ("output: s.pyf\n"
            "rows:\n"
            "  - - {split: cells.png, names: [R, G, B], crop: {bottom: 12}}\n")
    res = json.loads(M.build_figure_from_recipe(str(tmp_path / "s.yaml"), recipe_text=text))
    assert res["stack_series"] == 1
    root = ET.parse(tmp_path / "s.pyf").getroot()
    panels = [e for e in root.iter("Image2D") if e.findtext("isText", "False") != "True"
              and e.findtext("crop_bottom") not in (None, "None")]
    crops = [float(e.findtext("crop_bottom")) for e in panels]
    assert len(crops) >= 4 and all(c == 12 for c in crops), crops


def test_scale_bar_on_every_split_panel(tmp_path, qapp):
    """'add a 10 µm scale bar to every image' — a split put it on its last panel only."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    Image.new("RGB", (80, 60), (200, 100, 0)).save(tmp_path / "cells.png")
    base = ("output: {o}.pyf\n"
            "defaults: {{px_to_unit: 0.1, scale_bar: {{units: 1}}}}\n"
            "rows:\n"
            "  - - {{split: cells.png, names: [R, G, B]{extra}}}\n")
    for name, extra, expected in (("last", "", 1), ("all", ", scale_bar_panels: all", 4)):
        M.build_figure_from_recipe(str(tmp_path / f"{name}.yaml"),
                                   recipe_text=base.format(o=name, extra=extra))
        bars = list(ET.parse(tmp_path / f"{name}.pyf").getroot().iter("ScaleBar"))
        assert len(bars) == expected, (name, len(bars))


def test_missing_space_after_colon_is_understood(tmp_path):
    """YAML reads {bottom:24} as a key 'bottom:24' with no value."""
    from pyfigures.recipe import load_recipe
    p = tmp_path / "r.yaml"
    p.write_text("output: a.pyf\nrows:\n  - - {image: a.png, crop: {bottom:24, left:3}}\n",
                 encoding="utf-8")
    panel = load_recipe(str(p))["rows"][0][0]
    assert panel["crop"] == {"bottom": 24, "left": 3}
    assert panel["image"] == "a.png"


def test_recipe_reference_lists_every_key():
    from pyfigures import recipe as R
    ref = json.loads(M.recipe_reference())
    assert set(ref["top_level_keys"]) == R._TOP_KEYS
    assert set(ref["keys_per_panel_kind"]) == set(R._PANEL_KINDS)
    assert "nature" in ref["journals"] and "pptx" in ref["exports"]
