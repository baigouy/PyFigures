"""Fixes from ChatGPT's 20 October local-model trials and MCP stress test.

Qwen3.5 9B lost its builds to YAML and panel-shape slips the server could
read or correct precisely; the stress test found a one-line layout picture
refused and a single corner label refused for not being a list; two models
called a figure ready right after a [FAIL] resolution; and Fiji's sample
notice burned into a source image stayed in the final figure."""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _call(name, **args):
    try:
        res = asyncio.run(M.mcp.call_tool(name, args))
    except Exception as e:
        return f"ERROR: {e}"
    content = res[0] if isinstance(res, tuple) else res
    return "\n".join(getattr(c, "text", "") for c in content)


def _footer_image(path, size=(256, 200), text_rows=(176, 190)):
    """A dark fluorescence-like RGB image with a light-grey info line burned
    in at the bottom right (like Fiji's sample images)."""
    import numpy as np
    from PIL import Image
    rng = np.random.default_rng(0)
    w, h = size
    a = np.zeros((h, w, 3), np.uint8)
    a[..., 1] = rng.integers(0, 120, (h, w))          # green signal
    a[..., 0] = rng.integers(0, 60, (h, w))
    y0, y1 = text_rows
    for x in range(120, 240, 3):                      # strokes of the "text"
        a[y0:y1, x] = 200
    Image.fromarray(a).save(path)


@pytest.fixture
def images(tmp_path):
    from PIL import Image
    for name in ("a.png", "b.png"):
        Image.new("L", (64, 48), 120).save(tmp_path / name)
    Image.new("RGB", (64, 48), (200, 40, 40)).save(tmp_path / "rgb.png")
    (tmp_path / "c.csv").write_text("group,value\nA,1\nA,2\nA,3\nB,4\nB,5\nB,6\n", encoding="utf-8")
    return tmp_path


# --- 1. the recipe as a JSON object ---------------------------------------

def test_recipe_as_an_object_is_built_and_saved_as_yaml(images, qapp):
    recipe = {"output": "o.pyf", "rows": [[{"image": "a.png"}, "b.png"], ["rgb.png"]]}
    res = json.loads(M.build_figure_from_recipe(str(images / "o.yaml"), recipe_text=recipe))
    assert res["images"] == 3
    import yaml
    assert yaml.safe_load((images / "o.yaml").read_text(encoding="utf-8")) == recipe


def test_recipe_object_over_the_protocol(images, qapp):
    recipe = {"output": "p.pyf", "rows": [["a.png", "b.png"]]}
    res = _call("build_figure_from_recipe", recipe_path=str(images / "p.json"), recipe_text=recipe)
    assert not res.startswith("ERROR"), res
    assert (images / "p.pyf").is_file()
    # YAML text stays text (not parsed as JSON on the way in)
    res = _call("build_figure_from_recipe", recipe_path=str(images / "q.yaml"),
                recipe_text="output: q.pyf\nrows:\n  - [a.png]\n")
    assert not res.startswith("ERROR"), res


def test_yaml_error_offers_the_object_form(images):
    res = M.build_figure_from_recipe(str(images / "y.yaml"), recipe_text=(
        "output: y.pyf\nrows:\n  - - {image: a.png}\n    , {image: b.png}\n"))
    assert res.startswith("ERROR") and "JSON object" in res


# --- 2. corrections that show the right text -------------------------------

def test_image_with_split_options_is_read_as_a_split(images, qapp):
    res = json.loads(M.build_figure_from_recipe(str(images / "s.yaml"), recipe_text=(
        "output: s.pyf\nrows:\n"
        "  - - {image: rgb.png, split: {names: [R, G, B]}, merge: true, crop: {bottom: 4}}\n")))
    assert "[rgb.png x4]" in res["actual_layout"][0]


def test_options_only_panel_names_the_panel_to_write(images):
    res = M.build_figure_from_recipe(str(images / "i.yaml"), recipe_text=(
        "output: i.pyf\nrows:\n"
        "  - - {image: a.png}\n"
        "    - {inset: {at: [10, 10], size: [20, 15]}}\n"))
    assert res.startswith("ERROR")
    assert "INSIDE the image panel" in res
    assert '{"image": "a.png", "zoom": {"box": [10, 10, 20, 15], "size": 0.4}}' in res
    assert not (images / "i.pyf").exists()


def test_inset_without_image_suggests_a_zoom(images):
    res = M.build_figure_from_recipe(str(images / "z.yaml"), recipe_text=(
        "output: z.pyf\nrows:\n  - - {image: a.png, inset: {at: [5, 5], size: [20, 10]}}\n"))
    assert res.startswith("ERROR") and 'zoom: {"box": [5, 5, 20, 10], "size": 0.4}' in res


@pytest.mark.parametrize("text, expected", [
    # Qwen3.5 9B, ten builds in a row
    ("rows:\n  - - {split: a.png}\n    , {image: b.png}\n", "starts with ','"),
    ("rows:\n  - - {image: a.png}\n      inset: {image: b.png}\n",
     "put it INSIDE the braces, e.g. {image: a.png, inset: {image: b.png}}"),
])
def test_yaml_slips_get_the_right_form(images, text, expected):
    res = M.build_figure_from_recipe(str(images / "t.yaml"), recipe_text="output: t.pyf\n" + text)
    assert res.startswith("ERROR") and expected in res, res


# --- 3. a one-line layout picture -----------------------------------------

def test_one_line_picture_is_one_row(images, qapp):
    from pyfigures import layout_picture as P
    assert P.is_picture("a b c") and not P.is_picture("a") and not P.is_picture("(a,b)")
    res = json.loads(M.build_figure_from_recipe(str(images / "l.yaml"), recipe_text=(
        "output: l.pyf\nlayout: |\n  x y\npanels:\n  x: a.png\n  y: b.png\n")))
    assert res["actual_layout"] == ["row 1: a.png | b.png"]


# --- 4. one label as a plain string ---------------------------------------

def test_corner_label_given_as_a_string(images, qapp):
    pyf = images / "c.pyf"
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    _call("add_image", pyf_path=str(pyf), group_path=[0], filename=str(images / "a.png"))
    res = _call("add_corner_labels", pyf_path=str(pyf), group_path=[0], image_index=0,
                top_right="phalloidin α / β", bottom_left="dose 10 µM")
    assert not res.startswith("ERROR"), res
    texts = json.dumps(json.loads(M.audit_figure(str(pyf)))["panels"][0]["labels"], ensure_ascii=False)
    assert "phalloidin α / β" in texts and "10 µM" in texts


# --- 5. key names models used ---------------------------------------------

def test_inset_and_zoom_aliases(images, qapp):
    res = json.loads(M.build_figure_from_recipe(str(images / "k.yaml"), recipe_text=(
        "output: k.pyf\nrows:\n  - - image: a.png\n"
        "      inset: {filename: b.png, size_fraction: 0.3}\n"
        "      zoom: {region: [5, 5, 20, 20], size_fraction: 0.4}\n")))
    assert res["images"] == 1
    res = M.build_figure_from_recipe(str(images / "k2.yaml"), recipe_text=(
        "output: k2.pyf\nrows:\n  - - {image: a.png, zoom: {box: [5, 5, 20, 20], size: 40}}\n"))
    assert res.startswith("ERROR") and "a percentage? write size: 0.4" in res


# --- 6. an explicit verdict -----------------------------------------------

def test_compliance_verdict(images, qapp):
    M.build_figure_from_recipe(str(images / "v.yaml"), recipe_text=(
        "output: v.pyf\njournal: nature\ncolumn: double\nrows:\n  - [a.png, b.png]\n"))
    rep = M.check_journal_compliance(str(images / "v.pyf"), journal="nature", column="double")
    assert "[FAIL] resolution" in rep
    assert "VERDICT: NOT READY" in rep and "resolution" in rep.split("VERDICT")[1]
    assert "x more pixels per side" in rep


# --- 7. text burned into a source -----------------------------------------

def test_burned_in_text_is_found_and_the_crop_suggested(tmp_path):
    from pyfigures.burned_text import find_burned_in_text
    _footer_image(tmp_path / "f.png")
    found = find_burned_in_text(str(tmp_path / "f.png"))
    assert found["side"] == "bottom" and found["rows"] == [176, 189]
    assert found["crop"] == {"bottom": 26}
    assert find_burned_in_text(str(tmp_path / "f.png"), {"bottom": 30}) is None


def test_no_burned_text_in_plain_or_grey_images(tmp_path):
    import numpy as np
    from PIL import Image
    from pyfigures.burned_text import find_burned_in_text
    rng = np.random.default_rng(1)
    Image.fromarray(rng.integers(0, 255, (200, 200), dtype=np.uint8)).save(tmp_path / "g.png")
    a = np.zeros((200, 200, 3), np.uint8)
    a[..., 2] = rng.integers(0, 200, (200, 200))
    Image.fromarray(a).save(tmp_path / "blue.png")
    white = np.full((200, 200, 3), 250, np.uint8)
    white[150:170, 20:180] = (30, 30, 30)
    Image.fromarray(white).save(tmp_path / "white.png")
    for name in ("g.png", "blue.png", "white.png"):
        assert find_burned_in_text(str(tmp_path / name)) is None, name


def test_burned_text_warned_by_build_and_audit(tmp_path, qapp):
    _footer_image(tmp_path / "f.png")
    res = json.loads(M.build_figure_from_recipe(str(tmp_path / "f.yaml"), recipe_text=(
        "output: f.pyf\nrows:\n  - [f.png]\n")))
    assert any("burned into its pixels at the bottom" in w and "crop: {bottom: 26}" in w
               for w in res["warnings"]), res["warnings"]
    audit = json.loads(M.audit_figure(str(tmp_path / "f.pyf")))
    assert audit["panels_with_burned_in_text"][0]["filename"].endswith("f.png")
    res = json.loads(M.build_figure_from_recipe(str(tmp_path / "g.yaml"), recipe_text=(
        "output: g.pyf\nrows:\n  - - {image: f.png, crop: {bottom: 30}}\n")))
    assert not any("burned" in w for w in res["warnings"])
    assert json.loads(M.audit_figure(str(tmp_path / "g.pyf")))["panels_with_burned_in_text"] == []
