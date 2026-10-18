"""Smaller MCP findings from the October 2026 external audit of the MCP tools,
each fixed and kept here as a regression."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


@pytest.mark.parametrize("script", [
    "import matplotlib.pyplot as plt\nself.img = plt.figure(figsize=(2, 2))",
    "import numpy as np\nself.img = np.zeros((40, 60), dtype=np.uint8)",
])
def test_scripted_panel_keeps_its_saved_position(qapp, script):
    """A plot (or array) made by a panel script moved to 0,0 when reopened, so
    top-level rows of a recipe-built figure overlapped."""
    from batoolset.drawings.shapes.image2d import Image2D
    panel = Image2D(x=125, y=350, custom_loading_script=script)
    assert (panel.x(), panel.y()) == (125, 350)
    assert panel.width() > 0 and panel.height() > 0


def test_draft_figure_by_subfolder_finds_the_subfolder_images(tmp_path, qapp):
    """Images only in condition sub-folders: the draft had a plot and no image."""
    import json
    import xml.etree.ElementTree as ET
    from PIL import Image
    data = tmp_path / "results"
    for cond in ("control", "treated"):
        (data / cond).mkdir(parents=True)
        Image.new("L", (64, 48), 90).save(data / cond / f"{cond}.png")
    (data / "lengths.csv").write_text("control,treated\n1,2\n2,3\n3,4\n", encoding="utf-8")
    out = tmp_path / "draft.pyf"
    res = json.loads(M.draft_figure(str(data), str(out), group_by="subfolder", plot_kind="box",
                                    px_to_unit=0.1, scale_bar_units=1))
    assert res["n_images"] == 2
    assert res["scale_bars"] == 2
    names = [e.text or "" for e in ET.parse(out).getroot().iter("filename")]
    assert any("control.png" in n for n in names) and any("treated.png" in n for n in names)


@pytest.mark.parametrize("ext", ["png", "tif", "jpg"])
def test_raster_export_records_its_dpi(tmp_path, qapp, ext):
    """A 300 DPI export said 96 DPI in the file."""
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (200, 100), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    out = tmp_path / f"o.{ext}"
    M.export_figure(str(pyf), str(out), dpi=300)
    with Image.open(out) as im:
        assert im.info["dpi"][0] == pytest.approx(300, abs=0.5)


def test_polaroid_caption_size_does_not_depend_on_the_device_dpi(tmp_path, qapp, monkeypatch):
    """The caption's point size was converted with the device dpi: ~12x too
    large (and cut off) in a 1200 dpi PDF compared to the PNG / screen."""
    from PIL import Image
    from qtpy.QtGui import QImage, QPainter, QFontMetricsF
    from pyfigures.poster import poster_shapes
    src = tmp_path / "p.png"
    Image.new("RGB", (80, 60), (200, 50, 50)).save(src)
    card = poster_shapes.PosterImage(str(src), 10, 10, 80, 60, frame="polaroid",
                                     caption="A fairly long caption for a small card")

    class Px:
        scale = 4.0

        def __call__(self, x, y):
            return x * self.scale, y * self.scale

    widths = []
    original = QPainter.drawText

    def record(painter, *args):
        text = args[-1]
        if text == card.caption:
            widths.append(QFontMetricsF(painter.font(), painter.device()).horizontalAdvance(text))
        return original(painter, *args)

    monkeypatch.setattr(QPainter, "drawText", record)
    for dpi in (96, 1200):
        img = QImage(600, 600, QImage.Format.Format_ARGB32)
        img.setDotsPerMeterX(int(dpi / 0.0254))
        img.setDotsPerMeterY(int(dpi / 0.0254))
        p = QPainter(img)
        card.paint(p, Px())
        p.end()
    assert len(widths) == 2
    assert widths[0] == pytest.approx(widths[1], rel=0.05)
    outer = card.outer_rect_mm() if hasattr(card, "outer_rect_mm") else None
    outer_w = outer.width() if outer is not None else 80 + 12      # 6 mm frame each side
    assert widths[0] <= outer_w * 4.0          # fits the card width


def test_automatic_scale_bar_label_is_si_style(tmp_path, qapp):
    """The automatic label read '10.0µm'; it is '10 µm' (also '0.5 µm')."""
    import json
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (400, 300), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_image(str(pyf), [0], str(src))
    M.set_scale_bar(str(pyf), [0], 0, 10, px_to_unit=0.1)
    M.set_scale_bar(str(pyf), [0], 1, 0.5, unit="mm", px_to_unit=0.01)
    labels = [json.loads(M.get_scale_bar(str(pyf), [0], i))["label_plain"] for i in (0, 1)]
    assert labels == ["10 µm", "0.5 mm"]
    M.set_scale_bar(str(pyf), [0], 0, 20, unit="um", px_to_unit=0.1)
    assert json.loads(M.get_scale_bar(str(pyf), [0], 0))["label_plain"] == "20 µm"


def test_zoom_inset_covering_its_box_is_warned(tmp_path, qapp):
    """An inset so large it hides the zoomed box and its leader lines (a model
    'made the inset larger' to 0.8): the tool says so and gives the limit."""
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (512, 512), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    ok = M.add_zoom_callout(str(pyf), [0], 0, 380, 250, 100, 100, inset_fraction=0.4,
                            inset_corner="top left", parent_width=512, parent_height=512)
    assert "WARNING" not in ok
    bad = M.add_zoom_callout(str(pyf), [0], 0, 380, 250, 100, 100, inset_fraction=0.8,
                             inset_corner="top right", parent_width=512, parent_height=512)
    assert "WARNING" in bad and "covers the zoomed region" in bad
    assert "inset_corner='top left'" in bad or "bottom left" in bad


def test_checks_use_the_target_the_figure_was_sized_for(tmp_path, qapp):
    """'Is it ready for submission?' asked later (no journal given) checks the
    target the figure was fitted to — a model used to guess another width."""
    import json
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("L", (100, 80), 99).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    assert M.check_journal_compliance(str(pyf)).startswith("ERROR")       # no target yet
    M.resize_figure(str(pyf), journal="nature", column="double")
    report = M.check_journal_compliance(str(pyf))
    assert "183" in report and "stored target" in report
    assert "stored target" in M.check_resolution(str(pyf))
    brief = json.loads(M.figure_review_brief(str(pyf)))
    assert "183" in str(brief["mechanical_checks"]["journal_compliance"])
    M.create_figure(str(pyf), num_groups=1)                             # a new figure
    assert not (tmp_path / "f.target.json").exists()


def test_scale_bar_rule_counts_a_split_once_and_ignores_plots(tmp_path, qapp):
    """A channel split with its bar on the last panel, a data plot and a
    calibrated image: every micrograph has its bar (was '2/7 have a bar')."""
    import numpy as np
    import tifffile
    from PIL import Image
    stack = tmp_path / "cells.tif"
    tifffile.imwrite(str(stack), np.zeros((2, 40, 50), np.uint8), imagej=True, metadata={"axes": "CYX"})
    img = tmp_path / "i.png"
    Image.new("L", (50, 40), 90).save(img)
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n", encoding="utf-8")
    text = ("output: f.pyf\n"
            "defaults: {px_to_unit: 0.1, scale_bar: {units: 1}}\n"
            "rows:\n"
            "  - - {split: cells.tif, names: [a, b]}\n"
            "  - - i.png\n"
            "    - {plot: d.csv, kind: box}\n")
    M.build_figure_from_recipe(str(tmp_path / "f.yaml"), recipe_text=text)
    report = M.check_journal_compliance(str(tmp_path / "f.pyf"), width_mm=180,
                                        require_scale_bars=True)
    line = next(l for l in report.splitlines() if "scale bar" in l)
    assert line.strip().startswith("[ok]") and "2/2 micrograph" in line, line


def test_plots_are_not_rated_for_print_resolution_and_labels_are_visible(tmp_path, qapp):
    """A box plot was reported at ~70 DPI (it is vector), and corner letters were
    black — invisible on fluorescence images."""
    import xml.etree.ElementTree as ET
    from PIL import Image
    src = tmp_path / "i.png"
    Image.new("RGB", (900, 600), (0, 0, 0)).save(src)
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n", encoding="utf-8")
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_data_plot(str(pyf), [0], str(csv), kind="box")
    report = M.check_resolution(str(pyf), width_mm=180)
    assert "d.csv" not in report and "(in-memory)" not in report
    assert "i.png" in report
    M.add_corner_labels(str(pyf), [0], 0, top_left=["A"])
    M.add_corner_labels(str(pyf), [0], 1, top_left=["B"])
    texts = [(t.findtext("text") or "").strip('"') for t in ET.parse(pyf).getroot().iter("TAText2D")]
    a = next(t for t in texts if ">A<" in t or t == "A")
    b = next(t for t in texts if ">B<" in t or t == "B")
    assert "#ffffff" in a.lower() and "#ffffff" not in b.lower()


def test_label_colour_follows_the_corner_brightness(tmp_path, qapp):
    """White letters are invisible on bright field / white backgrounds and black
    ones on fluorescence: the label colour follows the corner it sits on."""
    import xml.etree.ElementTree as ET
    import numpy as np
    from PIL import Image
    arr = np.full((100, 200), 20, np.uint8)
    arr[:, 100:] = 240                                  # dark left, bright right
    src = tmp_path / "half.png"
    Image.fromarray(arr).save(src)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(src))
    M.add_corner_labels(str(pyf), [0], 0, top_left=["A"], top_right=["WT"])
    texts = [(t.findtext("text") or "") for t in ET.parse(pyf).getroot().iter("TAText2D")]
    a = next(t for t in texts if ">A<" in t)
    wt = next(t for t in texts if ">WT<" in t)
    assert "#ffffff" in a.lower()
    assert "#000000" in wt.lower()
    M.set_image_property(str(pyf), [0], 0, "crop_right", "110")   # bright half cropped away
    M.add_annotation(str(pyf), [0], 0, "B", placement="top right")
    texts = [(t.findtext("text") or "") for t in ET.parse(pyf).getroot().iter("TAText2D")]
    assert "#ffffff" in next(t for t in texts if ">B<" in t).lower()


def test_gui_lettering_uses_the_same_corner_rule(tmp_path, qapp):
    """A white figure lettering turns black on a bright-field panel, a black one
    turns white on a fluorescence panel; plots keep black, unreadable panels the
    figure colour."""
    from types import SimpleNamespace
    import numpy as np
    from PIL import Image
    from pyfigures.gui.pfgui import EZFIG_GUI
    from batoolset.drawings.shapes.Position import Position
    bright = tmp_path / "bf.png"
    Image.fromarray(np.full((60, 80), 230, np.uint8)).save(bright)
    dark = tmp_path / "fluo.png"
    Image.fromarray(np.full((60, 80), 10, np.uint8)).save(dark)

    def panel(path):
        return SimpleNamespace(img=None, renderer=None, filename=str(path), custom_loading_script=None,
                               crop_left=0, crop_right=0, crop_top=0, crop_bottom=0, LUTs=None)

    def gui(fg):
        return SimpleNamespace(serializable_font=SimpleNamespace(foreground=fg, placement=Position("top left")))

    assert EZFIG_GUI._letter_colour_override(gui(0xFFFFFF), panel(bright)) == 0x000000
    assert EZFIG_GUI._letter_colour_override(gui(0xFFFFFF), panel(dark)) is None
    assert EZFIG_GUI._letter_colour_override(gui(0x000000), panel(dark)) == 0xFFFFFF
    assert EZFIG_GUI._letter_colour_override(gui(0x000000), panel(bright)) is None
    assert EZFIG_GUI._letter_colour_override(gui(0x000000), panel(tmp_path / "gone.png")) is None


def test_check_resolution_is_an_mcp_tool_and_helpers_are_not(qapp):
    """A helper inserted under @mcp.tool() was exposed instead of check_resolution."""
    import asyncio
    names = {t.name for t in asyncio.run(M.mcp.list_tools())}
    assert "check_resolution" in names
    assert not any(n.startswith("_") for n in names)


def test_recipe_scale_bar_check_uses_the_micrograph_rule(tmp_path, qapp):
    """A split with its bar on the last panel plus a data plot failed the
    recipe's scale_bars check ('4 panel(s) without a scale bar', the plot
    included) while check_journal_compliance passed it: a local model rebuilt
    the recipe 32 times trying to satisfy it."""
    import json
    import numpy as np
    import tifffile
    stack = tmp_path / "cells.tif"
    tifffile.imwrite(str(stack), np.zeros((2, 40, 50), np.uint8), imagej=True, metadata={"axes": "CYX"})
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n", encoding="utf-8")
    text = ("output: f.pyf\n"
            "defaults: {px_to_unit: 0.1}\n"
            "checks: [scale_bars]\n"
            "rows:\n"
            "  - - {split: cells.tif, names: [a, b], scale_bar: {units: 1}}\n"
            "  - - {split: cells.tif, names: [c, d]}\n"
            "    - {plot: d.csv, kind: box}\n")
    res = M.build_figure_from_recipe(str(tmp_path / "f.yaml"), recipe_text=text)
    assert res.startswith("ERROR") and "1 panel(s) without a scale bar" in res, res
    audit = json.loads(M.audit_figure(str(tmp_path / "f.pyf")))
    missing = audit["panels_missing_scale_bar"]
    series = [p for p in audit["panels"] if p["group_path"] == missing[0]["group_path"]]
    assert len(missing) == 1 and missing[0]["group_path"][0] == 1      # the bar-less split…
    assert missing[0]["image_index"] == len(series) - 1                 # …listed by its last panel
    fixed = text.replace("names: [c, d]}", "names: [c, d], scale_bar: {units: 1}}")
    res = M.build_figure_from_recipe(str(tmp_path / "f.yaml"), recipe_text=fixed)
    assert not res.startswith("ERROR"), res


def test_missing_figure_gives_a_clear_error(tmp_path):
    res = M.describe_figure(str(tmp_path / "nope.pyf"))
    assert res.startswith("ERROR: file not found") and "create_figure" in res


def test_low_resolution_advice_never_says_print_wider(tmp_path, qapp):
    """Printing wider LOWERS the effective DPI of a fixed number of pixels."""
    from PIL import Image
    img = tmp_path / "small.png"
    Image.new("L", (60, 60), 100).save(img)
    pyf = tmp_path / "f.pyf"
    M.create_figure(str(pyf), num_groups=1)
    M.add_image(str(pyf), [0], str(img))
    M.resize_figure(str(pyf), journal="nature", column="double")
    report = M.check_resolution(str(pyf), journal="nature", column="double")
    assert "BELOW" in report
    assert "wider" not in report.lower()
    assert "smaller" in report.lower()
