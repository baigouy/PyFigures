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


def test_options_nested_inside_the_source_are_accepted(images, qapp):
    """Qwen 3.5 9B / gpt-oss (2026-10-19 sweep): {split: {image: a.png, …}} was
    read as a file name, then refused with the corrected panel; gpt-oss still
    resent it 25 times. Unambiguous, so it is read as the flat panel."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    Image.new("RGB", (60, 40), (200, 100, 0)).save(images / "rgb.png")
    res = M.build_figure_from_recipe(str(images / "f.yaml"), recipe_text=(
        "output: f.pyf\nrows:\n"
        "  - - {split: {image: rgb.png, crop: {bottom: 4}, names: [r, g, b], "
        "lut: [Magenta, green, blue]}}\n"))
    assert not res.startswith("ERROR"), res
    imgs = list(ET.parse(images / "f.pyf").getroot().iter("Image2D"))
    assert len(imgs) == 4                                    # 3 channels + merge
    assert "MAGENTA" in (imgs[3].findtext("LUTs") or ""), imgs[3].findtext("LUTs")
    assert all(float(e.findtext("crop_bottom") or 0) == 4 for e in imgs)
    # a key that is not valid for the flat panel: the error names that key
    # (gpt-oss's real nested split also held `channels`; "flatten it" looped)
    res = M.build_figure_from_recipe(str(images / "g.yaml"), recipe_text=(
        "output: g.pyf\nrows:\n  - - {split: {image: rgb.png, channels: [0, 1, 2], "
        "colors: [red, green, blue]}}\n"))
    assert res.startswith("ERROR") and "['channels']" in res and "remove 'channels'" in res, res
    assert "put the other keys beside" not in res
    # no source key inside: still the corrected form
    res = M.build_figure_from_recipe(str(images / "h.yaml"), recipe_text=(
        "output: h.pyf\nrows:\n  - - {split: {wobble: 3}}\n"))
    assert res.startswith("ERROR") and "put the other keys beside" in res, res


def test_picture_with_unequal_rows_gets_the_stretched_picture(images):
    """Qwen3 30B resent pictures with unequal rows 16 times."""
    from pyfigures.layout_formula import FormulaError
    from pyfigures.layout_picture import parse
    with pytest.raises(FormulaError, match="a a a b b b\n  c c d d e e"):
        parse("a b\nc d e")
    # no candidate when the stretched picture is not valid (pinwheel / L)
    with pytest.raises(FormulaError) as e:
        parse("a b\na c d\na")
    assert "would be" not in str(e.value)


def test_table_as_image_is_refused_with_plot_form(images):
    """A CSV given as an image file became a black panel (Qwen3 30B)."""
    (images / "m.csv").write_text("A,B\n1,2\n", encoding="utf-8")
    res = M.build_figure_from_recipe(str(images / "t.yaml"), recipe_text=(
        "output: t.pyf\nrows:\n  - [a.png, m.csv]\n"))
    assert res.startswith("ERROR") and "{plot: m.csv, kind: box}" in res, res


def test_picture_crop_reports_how_much_is_shown(images, qapp):
    from PIL import Image
    Image.new("L", (300, 100), 90).save(images / "wide.png")
    Image.new("L", (100, 100), 90).save(images / "sq.png")
    res = json.loads(M.build_figure_from_recipe(str(images / "p.yaml"), recipe_text=(
        "output: p.pyf\nlayout: |\n  w s\n  w s\npanels:\n  w: wide.png\n  s: sq.png\n")))
    msg = " ".join(res["warnings"])
    assert "% of the image shown" in msg and "most of the image is cut away" in msg, msg


def test_rebuild_warns_when_a_zoom_size_changed(images, qapp):
    """Qwen3 30B rebuilt for a colour change and the enlarged inset went
    from 0.6 back to 0.4."""
    from PIL import Image
    Image.new("L", (200, 150), 120).save(images / "big.png")
    text = "output: z.pyf\nrows:\n  - - {image: big.png, zoom: {box: [10, 10, 40, 30]%s}}\n"
    M.build_figure_from_recipe(str(images / "z.yaml"), recipe_text=text % ", size: 0.6")
    res = json.loads(M.build_figure_from_recipe(str(images / "z.yaml"), recipe_text=text % ""))
    assert any("is now SMALLER" in w and "0.6 -> 0.4" in w and "size: 0.6 back" in w
               and "ABOVE 0.6" in w for w in res["warnings"]), res
    res = json.loads(M.build_figure_from_recipe(str(images / "z.yaml"), recipe_text=text % ""))
    assert not any("is now" in w for w in res["warnings"])
    res = json.loads(M.build_figure_from_recipe(str(images / "z.yaml"), recipe_text=text % ", size: 0.7"))
    assert any("is now LARGER" in w for w in res["warnings"]), res


def test_recipe_reference_explains_whole_figure_colours():
    ref = json.loads(M.recipe_reference())
    assert ref["whole_figure_colors"]["example"] == "colors: [magenta, green]"
    assert "set_figure_colors" in ref["whole_figure_colors"]["existing_figure"]
    assert "a a a b b b" in ref["layout_picture"]["more_examples"]["two panels above three"]
    assert any("illustrative" in n for n in ref["notes"])


def test_build_result_lists_zoom_inset_sizes(images, qapp):
    """Gemma 12B, asked for larger insets, rebuilt the zoom without a size."""
    from PIL import Image
    Image.new("L", (200, 150), 120).save(images / "big.png")
    res = json.loads(M.build_figure_from_recipe(str(images / "z.yaml"), recipe_text=(
        "output: z.pyf\nrows:\n  - - {image: big.png, zoom: {box: [10, 10, 40, 30]}}\n")))
    assert res["zoom_insets"] == [{"panel": "big.png", "box": [10, 10, 40, 30], "size": 0.4}]
    assert "raise its zoom's size" in res["zoom_note"]


def test_yaml_error_says_how_to_write_a_row(images):
    """Qwen3.5 9B sent '- [a]' then '    [b]' 30 times against the parser error."""
    res = M.build_figure_from_recipe(str(images / "f.yaml"), recipe_text=(
        "output: f.pyf\nrows:\n  - [a.png]\n    [b.png]\n  - [c.png]\n"))
    assert res.startswith("ERROR") and "'  - [a.png, b.png]'" in res, res


@pytest.mark.parametrize("rows, message", [
    # Gemma 12B: image + merge in one panel to get "each channel + merge"
    ("  - - {image: a.png, merge: true}", "{split: file.tif, names: [...], merge: true}"),
    # gpt-oss / Qwen: merge of one RGB file
    ("  - - {merge: a.png}", "a split already adds its merge panel"),
    # gpt-oss: a made-up key
    ("  - - {image: a.png, channel_split: true}", "use a split panel"),
])
def test_errors_tell_a_small_model_what_to_write(images, rows, message):
    res = M.build_figure_from_recipe(str(images / "f.yaml"),
                                     recipe_text=f"output: f.pyf\nrows:\n{rows}\n")
    assert res.startswith("ERROR") and message in res, res
    assert not (images / "f.pyf").exists()


@pytest.mark.parametrize("text, message", [
    ("lettering: true", "letter_panels: true"),
    ("defaults: {letter_panels: true}", "panel letters are a top-level key: letter_panels: true"),
    ("defaults: {journal: nature}", "go at the top of the recipe"),
])
def test_misplaced_letters_and_journal_say_where_they_go(images, text, message):
    res = M.build_figure_from_recipe(str(images / "f.yaml"), recipe_text=(
        f"output: f.pyf\n{text}\nrows:\n  - [a.png]\n"))
    assert res.startswith("ERROR") and message in res, res


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
    assert bad.startswith("ERROR") and "px_to_unit" in bad, bad


def test_errors_steer_a_small_model_back_to_what_the_user_asked(tmp_path, qapp):
    """From an 8B model's Figure 3 run: it invented 0.1 µm/px instead of the
    user's 1.24 and then followed 'use a shorter bar' down to 5 µm; it cropped
    left 400 + right 500 from a 922 px image meaning x 400 to 500 (22 px left,
    drawn stretched); it sent split colours as a mapping."""
    from PIL import Image
    src = tmp_path / "k.png"
    Image.new("RGB", (922, 700), (30, 60, 90)).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    before = pyf.read_bytes()

    # the pixel size is questioned first; the asked-for length is kept
    res = M.set_scale_bar(str(pyf), [0], 0, 100, px_to_unit=0.1)
    assert res.startswith("ERROR"), res
    assert res.index("px_to_unit") < res.index("quarter of the width"), res
    assert "Never guess" in res and "Do not shorten a bar length" in res, res

    # a sliver is refused like a crop that removes everything, with the margins meant
    res = M.transform_image(str(pyf), [0], 0, crop_left=400, crop_right=500)
    assert res.startswith("ERROR") and "leaves only 22 x 700 px" in res, res
    assert "not x1/y1/x2/y2" in res and "crop_left=400 and crop_right=422" in res, res
    assert pyf.read_bytes() == before
    assert not M.transform_image(str(pyf), [0], 0, crop_left=400, crop_right=422).startswith("ERROR")
    bad = M.build_figure_from_recipe(str(tmp_path / "r.yaml"), recipe_text=(
        "output: r.pyf\nrows:\n  - - {image: k.png, crop: {left: 400, right: 500}}\n"))
    assert bad.startswith("ERROR") and "left: 400 and right: 422" in bad, bad
    assert not (tmp_path / "r.pyf").exists()

    # colours: an ordered list, one per channel, never a mapping
    chans = []
    for i in range(3):
        chans.append(str(tmp_path / f"c{i}.png"))
        Image.new("L", (64, 64), 40 * (i + 1)).save(chans[-1])
    res = M.add_channel_split(str(pyf), channel_files=chans,
                              colors={"red": "magenta", "green": "green"})
    assert res.startswith("ERROR") and "ordered list" in res and "mapping" in res, res
    res = M.add_channel_split(str(pyf), channel_files=chans, colors=["magenta", "green"])
    assert res.startswith("ERROR") and "one colour per channel" in res, res


def test_caption_stub_matches_the_panel_letters(tmp_path, qapp):
    """One entry per letter: each channel-split panel names its channel (a
    montage would be one entry)."""
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
    assert "(A) cells (GFP); (B) cells (RFP); (C) cells (merge); (D) i; (E) data plot" in stub, stub
    assert "(F)" not in stub


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


def test_split_scale_bar_on_merge_unless_all(tmp_path, qapp):
    """A split gets one bar, on the merge (the author's choice: the panels
    share one scale); scale_bar_panels: all for one on every panel."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    Image.new("RGB", (80, 60), (200, 100, 0)).save(tmp_path / "cells.png")
    base = ("output: {o}.pyf\n"
            "defaults: {{px_to_unit: 0.1, scale_bar: {{units: 1}}}}\n"
            "rows:\n"
            "  - - {{split: cells.png, names: [R, G, B]{extra}}}\n")
    for name, extra, expected in (("default", "", 1), ("last", ", scale_bar_panels: last", 1),
                                  ("all", ", scale_bar_panels: all", 4)):
        M.build_figure_from_recipe(str(tmp_path / f"{name}.yaml"),
                                   recipe_text=base.format(o=name, extra=extra))
        root = ET.parse(tmp_path / f"{name}.pyf").getroot()
        bars = list(root.iter("ScaleBar"))
        assert len(bars) == expected, (name, len(bars))
        if expected == 1:
            # on the merge, the last panel
            assert list(root.iter("Image2D"))[-1].find("annotations/ScaleBar") is not None


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


def test_build_reply_shows_the_actual_saved_layout(images, qapp):
    """Qwen 9B put the second micrograph beside the split instead of beside
    the plot, and kept that through five edits while describing the asked
    layout: the reply now shows what was saved."""
    from PIL import Image
    Image.new("RGB", (60, 40), (200, 100, 0)).save(images / "rgb.png")
    (images / "m.csv").write_text("A,B\n1,2\n2,3\n", encoding="utf-8")
    wrong = json.loads(M.build_figure_from_recipe(str(images / "w.yaml"), recipe_text=(
        "output: w.pyf\nrows:\n  - - {split: rgb.png}\n    - a.png\n  - - {plot: m.csv}\n")))
    assert wrong["actual_layout"] == ["row 1: [rgb.png x4] | a.png", "row 2: m.csv (plot)"], wrong
    right = json.loads(M.build_figure_from_recipe(str(images / "r.yaml"), recipe_text=(
        "output: r.pyf\nrows:\n  - - {split: rgb.png}\n  - - a.png\n    - {plot: m.csv}\n")))
    assert right["actual_layout"] == ["row 1: [rgb.png x4]", "row 2: a.png | m.csv (plot)"], right
    assert "SAVED figure" in right["layout_note"]
    nested = json.loads(M.build_figure_from_recipe(str(images / "n.yaml"), recipe_text=(
        "output: n.pyf\nlayout: \"(a/b),m\"\npanels:\n  a: a.png\n  b: b.png\n"
        "  m: {plot: m.csv}\n")))
    assert nested["actual_layout"] == ["row 1: (a.png / b.png) | m.csv (plot)"], nested
    assert "row 2: a.png | m.csv (plot)" in M.describe_figure(str(images / "r.pyf"))


def test_scale_bar_calibration_provenance_is_flagged(images, qapp):
    """Qwen3 30B copied 0.1 µm/pixel from the examples into a layout given no
    calibration: a pixel size the file does not carry is flagged (not
    blocked), and one contradicting the file's metadata too."""
    from batoolset.img import Img
    import numpy as np
    res = json.loads(M.build_figure_from_recipe(str(images / "c.yaml"), recipe_text=(
        "output: c.pyf\ndefaults: {px_to_unit: 0.1, scale_bar: {units: 1}}\nrows:\n"
        "  - [a.png, b.png]\n")))
    msg = [w for w in res["warnings"] if "carry no pixel size" in w]
    assert msg and "a.png, b.png" in msg[0] and "only if the user gave" in msg[0], res["warnings"]
    # a TIFF calibrated at 0.5 µm/px given 0.1 in the recipe
    t = images / "cal.tif"
    import tifffile
    tifffile.imwrite(str(t), np.zeros((40, 60), np.uint8), imagej=True,
                     resolution=(2.0, 2.0), metadata={"unit": "um"})
    res = json.loads(M.build_figure_from_recipe(str(images / "d.yaml"), recipe_text=(
        "output: d.pyf\ndefaults: {px_to_unit: 0.1, scale_bar: {units: 1}}\nrows:\n  - [cal.tif]\n")))
    assert any("differs from the image metadata" in w and "0.5" in w for w in res["warnings"]), \
        res["warnings"]
    # no scale bar: nothing to say
    res = json.loads(M.build_figure_from_recipe(str(images / "e.yaml"), recipe_text=(
        "output: e.pyf\nrows:\n  - [a.png]\n")))
    assert not any("pixel size" in w for w in res["warnings"])


def test_same_failing_recipe_resent_gets_told_so(images):
    text = "output: x.pyf\nrows:\n  - [a.png, nothere.png]\n"
    first = M.build_figure_from_recipe(str(images / "x.yaml"), recipe_text=text)
    assert first.startswith("ERROR") and "already refused" not in first
    again = M.build_figure_from_recipe(str(images / "x.yaml"), recipe_text=text)
    assert again.startswith("ERROR") and "already refused for the same reason" in again
    assert "nothere.png" in again
    changed = M.build_figure_from_recipe(str(images / "x.yaml"),
                                         recipe_text=text.replace("nothere", "nope"))
    assert "already refused" not in changed


def test_compliance_says_it_checks_print_rules_only(images, qapp):
    M.build_figure_from_recipe(str(images / "j.yaml"), recipe_text=(
        "output: j.pyf\nrows:\n  - [a.png]\n"))
    rep = M.check_journal_compliance(str(images / "j.pyf"), journal="nature", column="single")
    assert "mechanical rules only" in rep and "describe_figure" in rep
