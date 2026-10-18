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
