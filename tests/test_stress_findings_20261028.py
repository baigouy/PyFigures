"""Bugs found by building varied figures through the MCP tools (stress test of
28 October 2026): nested-group numbering, alt text, frame ranges, French CSVs,
grouped plots, calibration-bar LUTs, label rows, scale bars on text, cut-off
side labels, letter colours on scripted / LUT panels, recipe checks."""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402

import pyfigures.mcp_server as M  # noqa: E402


def _png(path, value=128, size=(64, 64)):
    Image.fromarray(np.full(size, value, np.uint8)).save(path)
    return str(path)


@pytest.fixture
def imgs(tmp_path):
    return [_png(tmp_path / f"im{i}.png", 40 * i + 20) for i in range(4)]


def test_describe_names_nested_groups_and_images_as_the_tools_address_them(tmp_path, imgs):
    """Sub-groups are numbered among sub-groups and images among images: the
    description said 'Group Group 1.1' for group_path [1, 0], and 'Image 2' for
    the image the tools call image 1."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    M.add_group(pyf, orientation="Y", parent_group_path=[0])
    M.add_image(pyf, [0, 0], imgs[1])
    M.add_group(pyf, orientation="X", parent_group_path=[0, 0])
    M.add_image(pyf, [0, 0, 0], imgs[2])
    M.add_image(pyf, [0], imgs[3])
    d = M.describe_figure(pyf)
    assert "Group Group" not in d
    assert "Group [0, 0] [" in d and "Group [0, 0, 0] [" in d
    # im3 is the second image of group [0], after the sub-group
    assert re.search(r"Image 1: im3\.png", d), d
    # and that is how the tools address it
    assert "im3" in M.get_image_property(pyf, [0], 1, "filename")


def test_alt_text_numbers_panels_without_letters(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    for p in imgs[:3]:
        M.add_image(pyf, [0], p)
    alt = json.loads(M.generate_alt_text(pyf))["long"]
    assert "A panel" not in alt
    assert "Panel 1:" in alt and "Panel 3:" in alt


def test_frames_accept_fiji_style_inclusive_ranges():
    from pyfigures.stack_info import parse_frames
    assert parse_frames("0-11:3", 12) == [0, 3, 6, 9]
    assert parse_frames("2-4", 12) == [2, 3, 4]
    with pytest.raises(ValueError, match="first-last"):
        parse_frames("zz", 12)
    with pytest.raises(ValueError, match="out of range"):
        parse_frames("0-20", 12)


def test_csv_with_semicolons_and_decimal_commas(tmp_path):
    """Excel in French writes '1,5;2,5': it was read as 'no numbers to plot'."""
    from staplot.api import csv_format, table_from_csv
    assert csv_format("A;B\n1,5;2,5\n") == (";", ",")
    assert csv_format("A,B\n1.5,2.5\n") == (",", ".")
    assert csv_format("A\tB\n1.5\t2.5\n") == ("\t", ".")
    csv = tmp_path / "eu.csv"
    csv.write_text("Ctrl;Drug\n1,5;2,5\n1,7;2,9\n1,2;3,1\n1,4;2,7\n", encoding="utf-8")
    t = table_from_csv(str(csv))
    assert t.group_arrays()["Drug"][0] == pytest.approx(2.5)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    r = M.add_data_plot(pyf, [0], str(csv), kind="box")
    assert not r.startswith("ERROR"), r


def test_grouped_plot_refuses_a_wide_table(tmp_path):
    wide = tmp_path / "wide.csv"
    wide.write_text("Group,Day 1,Day 1,Day 2\nWT,1,2,3\nKO,4,5,6\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    r = M.add_data_plot(pyf, [0], str(wide), kind="grouped")
    assert r.startswith("ERROR") and "long CSV" in r
    assert "Image2D" not in open(pyf, encoding="utf-8").read()
    long = tmp_path / "long.csv"
    long.write_text("G,Day,V\nWT,D1,1\nWT,D1,2\nKO,D1,3\nKO,D1,4\n", encoding="utf-8")
    assert not M.add_data_plot(pyf, [0], str(long), kind="grouped").startswith("ERROR")


def test_calibration_bar_refuses_an_unknown_lut_and_hints_fiji_names(tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    r = M.add_lut_calibration_bar(pyf, [0], lut="FIRE")
    assert r.startswith("ERROR") and "nothing was added" in r
    assert "MATPLOTLIB_inferno" in r            # nearest look to Fiji's Fire
    assert "Image2D" not in open(pyf, encoding="utf-8").read()
    assert not M.add_lut_calibration_bar(pyf, [0], lut="afm_hot").startswith("ERROR")


def test_label_row_reply_says_the_group_paths_moved(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    r = M.add_label_row(pyf, [0], ["WT"], position="above")
    assert "moved down one index" in r and "now [1]" in r
    assert "LABEL ROW, above the next group" in M.describe_figure(pyf)


def test_scale_bars_skip_label_text_and_vector_panels(tmp_path, imgs):
    """set_scale_bar_all drew a white bar across every label-row word."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    M.add_image(pyf, [0], imgs[1])
    M.add_label_row(pyf, [0], ["a", "b"], position="above")
    M.add_side_label(pyf, [1], "row", position="left")
    r = M.set_scale_bar_all(pyf, 5, px_to_unit=0.5)
    assert "applied to 2 image(s)" in r, r
    root = ET.parse(pyf).getroot()
    for img in root.iter("Image2D"):
        if (img.findtext("isText") or "False") != "False":
            assert img.find("annotations/ScaleBar") is None


def test_side_label_longer_than_its_row_fails_the_compliance_check(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    M.add_image(pyf, [0], imgs[1])
    M.add_side_label(pyf, [0], "A very long side label that cannot fit", position="right",
                     text_orientation="vertical")
    M.resize_figure(pyf, 60)
    r = M.check_journal_compliance(pyf, width_mm=60)
    assert "[FAIL] labels fit" in r and "A very long side label" in r


def test_scatter_legend_never_prints_p_0(tmp_path):
    from staplot.api import table_from_csv
    from staplot.plots.scatter import plot_scatter
    import matplotlib.pyplot as plt
    csv = tmp_path / "s.csv"
    xs = np.linspace(0, 10, 30)
    csv.write_text("x,y\n" + "".join(f"{x},{2 * x + 0.01 * i}\n" for i, x in enumerate(xs)),
                   encoding="utf-8")
    fig = plot_scatter(table_from_csv(str(csv)))
    labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    plt.close(fig)
    assert any("p < 0.0001" in t for t in labels), labels
    assert not any("p=0.0000" in t for t in labels)


def test_data_plot_panel_leaves_no_open_pyplot_figure(tmp_path):
    """Every plot panel stayed in pyplot's list ('More than 20 figures')."""
    import matplotlib.pyplot as plt
    from pyfigures.mcp_tools.content import _make_data_plot_script
    csv = tmp_path / "c.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n", encoding="utf-8")
    script = _make_data_plot_script(str(csv), "bar", "sem", True, True, "", "", "")
    before = set(plt.get_fignums())

    class Panel:
        img = None
    panel = Panel()
    exec(script, {"plt": plt, "self": panel})
    assert set(plt.get_fignums()) == before
    import io
    buf = io.BytesIO()
    panel.img.savefig(buf, format="svg")         # how the panel draws it
    assert buf.getvalue()


def test_recipe_accepts_an_empty_checks_list(tmp_path, imgs):
    rec = tmp_path / "r.json"
    rec.write_text(json.dumps({"output": "o.pyf", "rows": [[imgs[0]]], "checks": []}),
                   encoding="utf-8")
    r = M.build_figure_from_recipe(str(rec))
    assert not r.startswith("ERROR"), r


def test_set_image_property_takes_numbers_and_booleans(tmp_path, imgs):
    """crop_left=100 raised "'int' object has no attribute 'strip'"."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    assert "crop_left = 10" in M.set_image_property(pyf, [0], 0, "crop_left", 10)
    assert "flip_h = True" in M.set_image_property(pyf, [0], 0, "flip_h", True)
    assert M.get_image_property(pyf, [0], 0, "crop_left").strip() == "10"


def test_index_error_in_a_group_of_sub_groups_names_them(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_group(pyf, orientation="Y", parent_group_path=[0])
    M.add_image(pyf, [0, 0], imgs[0])
    r = M.set_lut(pyf, [0], 0, ["GREEN"])
    assert r.startswith("ERROR") and "only sub-group(s) [0, 0]" in r


def test_poster_grid_and_scatter_keep_the_title_clear(tmp_path, imgs):
    """arrange_poster_grid laid its first row over the poster's title."""
    poster = str(tmp_path / "p.pyfposter")
    M.create_poster(poster, page_preset="A4")
    M.add_poster_text(poster, "<b>Title</b>", style="h1", x_mm=10, y_mm=10, width_mm=190, height_mm=30)
    for p in imgs:
        M.add_poster_image(poster, p, x_mm=20, y_mm=20, width_mm=60, height_mm=60)
    for arrange in ("arrange_poster_grid", "arrange_poster_scatter"):
        getattr(M, arrange)(poster)
        photos = [s for s in json.loads(M.list_poster_images(poster))["images"]
                  if s["kind"] == "image"]
        # the title ends at 40 mm (x_mm / y_mm: the untilted top-left corner)
        assert len(photos) == 4 and min(s["y_mm"] for s in photos) >= 40, (arrange, photos)


def test_poster_indices_accept_ranges():
    from pyfigures.poster.poster_headless import _parse_indices
    assert _parse_indices("1-3,5") == [1, 2, 3, 5]
    with pytest.raises(ValueError, match="1-3"):
        _parse_indices("a")


def test_label_background_keeps_text_readable_and_spares_label_rows(tmp_path, imgs):
    """Black boxes behind black letters and label-row words: solid rectangles."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    M.add_annotation(pyf, [0], 0, '<span style="color:#000000">A</span>')
    M.add_annotation(pyf, [0], 0, '<span style="color:#ff0000">red</span>', placement="top right")
    M.add_label_row(pyf, [0], ["WT"], position="above")
    r = M.set_label_background(pyf, color="black")
    assert "1 text(s) the colour of the box now white" in r, r
    from pyfigures.mcp_tools.core import _label_plain_text
    root = ET.parse(pyf).getroot()
    seen = set()
    for img in root.iter("Image2D"):
        for ta in img.iter("TAText2D"):
            text = (ta.findtext("text") or "").lower()
            plain = _label_plain_text(ta.findtext("text"))
            seen.add(plain)
            if (img.findtext("isText") or "False") != "False":
                assert ta.findtext("fill_color") in (None, "None")      # the row: no box
            elif plain == "A":
                assert "#ffffff" in text and "#000000" not in text
            elif plain == "red":
                assert "#ff0000" in text                              # red reads on black
    assert {"A", "red", "WT"} <= seen


def test_values_that_break_a_panel_are_refused(tmp_path, imgs):
    """NaN rotation, a crop wider than the image or negative (through
    set_image_property, which skipped transform_image's check), more LUTs than
    channels, and a one-file 'merge' (a blank panel) were all stored."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])                     # 64 x 64 grey
    assert M.transform_image(pyf, [0], 0, rotation=float("nan")).startswith("ERROR")
    assert M.set_image_property(pyf, [0], 0, "crop_left", 1000).startswith("ERROR")
    assert M.set_image_property(pyf, [0], 0, "crop_left", -5).startswith("ERROR")
    assert M.set_image_property(pyf, [0], 0, "theta", "nan").startswith("ERROR")
    assert M.set_lut(pyf, [0], 0, ["GREEN", "RED"]).startswith("ERROR")
    assert M.add_channel_merge(pyf, [0], [imgs[0]]).startswith("ERROR")
    root = ET.parse(pyf).getroot()
    img = root.find(".//Image2D")
    assert (img.findtext("crop_left") or "0") in ("0", "None")
    assert len(root.findall(".//Image2D")) == 1
    assert not M.set_image_property(pyf, [0], 0, "crop_left", 10).startswith("ERROR")


def test_montage_on_the_missing_axis_says_which_axis_to_use(tmp_path):
    import tifffile
    stack = tmp_path / "t.tif"
    tifffile.imwrite(str(stack), np.zeros((5, 16, 16), np.uint8), imagej=True,
                     metadata={"axes": "TYX"})
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    r = M.add_stack_montage(pyf, str(stack), axis="z")
    assert r.startswith("ERROR") and "use axis='t'" in r


def test_empty_annotation_is_refused(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    assert M.add_annotation(pyf, [0], 0, "").startswith("ERROR")
    assert M.add_annotation(pyf, [0], 0, "<b> </b>").startswith("ERROR")
    assert "TAText2D" not in open(pyf, encoding="utf-8").read()


def test_constant_panel_check_does_not_read_vector_files(tmp_path, monkeypatch):
    """audit_figure read an equation's .svg through the image reader, which
    started Fiji's JVM to fail and fall back."""
    from pyfigures.constant_panels import constant_panel_value
    import batoolset.img as I
    svg = tmp_path / "eq.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>',
                   encoding="utf-8")

    def boom(*a, **k):
        raise AssertionError("an .svg was read as an image")
    monkeypatch.setattr(I, "Img", boom)
    assert constant_panel_value(str(svg)) is None


def test_letter_brightness_of_lut_scripted_and_vector_panels(tmp_path):
    """Black letters vanished on a green-LUT image, a channel merge, an
    orthogonal view and a kymograph: their corners were 'unknown' and took
    the figure's colour."""
    from pyfigures.mcp_tools.core import corner_brightness, script_corner_brightness, \
        _lut_peak_luminance
    bright = _png(tmp_path / "bright.png", 230)
    assert corner_brightness(bright, "top left", luts=["GREEN"]) == pytest.approx(
        230 / 255 * _lut_peak_luminance(["GREEN"]), rel=1e-3)
    assert _lut_peak_luminance(["BLUE"]) < 0.1 < _lut_peak_luminance(["GREEN"])
    assert script_corner_brightness("# pyfigures:channel_merge mode=sum\n") == 0.0
    assert script_corner_brightness("x = 1\nfrom staplot import api as _api\n") == 1.0
    # a kymograph's left corners are the start of its line, not the stack's corner
    a = np.full((50, 100), 250, np.uint8)
    a[:, :20] = 5                                 # dark where the line starts
    Image.fromarray(a).save(tmp_path / "k.png")
    kymo = (f"# pyfigures:kymograph\n_path = {str(tmp_path / 'k.png')!r}\n"
            f"_line = (0.0, 25.0, 99.0, 25.0)\n")
    assert script_corner_brightness(kymo, "top left") < 0.1
    assert script_corner_brightness(kymo, "top right") > 0.9


@pytest.fixture
def messy(tmp_path):
    """A results folder as people have them: a good image, a broken and an
    empty one at the top, images and a CSV in condition sub-folders, an x-y CSV."""
    f = tmp_path / "messy"
    (f / "WT").mkdir(parents=True)
    (f / "KO").mkdir()
    _png(f / "a.png", 100)
    (f / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\n garbage")
    (f / "empty.tif").write_bytes(b"")
    _png(f / "WT" / "w1.png", 50)
    _png(f / "KO" / "k1.png", 150)
    (f / "KO" / "groups.csv").write_text("WT,KO\n1,3\n2,4\n1.5,3.5\n1.2,3.9\n", encoding="utf-8")
    (f / "dose.csv").write_text("Dose,Response\n" + "".join(f"{i},{2 * i + 1}\n" for i in range(8)),
                                encoding="utf-8")
    return f


def test_folder_figure_drops_unreadable_files_before_the_layout(messy, tmp_path):
    """A broken and an empty file each left an empty row: '3 group(s), 1 image(s)'."""
    pyf = str(tmp_path / "f.pyf")
    r = M.create_figure_from_folder(pyf, str(messy))
    assert "1 group(s), 1 image(s)" in r
    assert "broken.png" in r and "empty.tif" in r
    assert str(messy) + os.sep not in r.split("WARNING:")[1].split("\n")[0]   # names, not paths
    # the sub-folder images left out are said
    assert "NOTE: 2 image(s) in sub-folder(s) KO (1), WT (1)" in r


def test_folder_figure_refuses_an_unknown_layout_or_grouping(messy, tmp_path):
    pyf = str(tmp_path / "f.pyf")
    assert M.create_figure_from_folder(pyf, str(messy), layout="spiral").startswith("ERROR")
    assert M.create_figure_from_folder(pyf, str(messy), group_by="colour").startswith("ERROR")
    assert not os.path.exists(pyf)


def test_draft_counts_laid_out_images_plots_subfolder_csvs_and_xy_as_scatter(messy, tmp_path):
    """draft_figure said 'laid out 9 image(s)' for 7, left the sub-folder CSVs
    out, and drew a dose-response table as two bars with a t-test."""
    out = str(tmp_path / "d.pyf")
    res = json.loads(M.draft_figure(str(messy), out, group_by="subfolder"))
    assert res["n_images"] == 3
    assert res["n_data_plots"] == 2
    assert any("broken.png" in w for w in res["warnings"])
    assert "bar" in res["steps"][1] and "scatter" in res["steps"][1]
    from pyfigures.mcp_tools.workflow import _auto_plot_kind
    assert _auto_plot_kind(str(messy / "dose.csv")) == "scatter"
    assert _auto_plot_kind(str(messy / "KO" / "groups.csv")) == "bar"


@pytest.fixture
def one_panel(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="X")
    M.add_group(pyf, orientation="X")
    M.add_image(pyf, [0], imgs[0])
    return pyf


@pytest.mark.parametrize("call", [
    lambda p: M.add_roi_rect(p, [0], 0, 1, 1, 10, 10, color="notacolour"),
    lambda p: M.add_roi_rect(p, [0], 0, 1, 1, 10, 10, opacity=2),
    lambda p: M.add_roi_ellipse(p, [0], 0, 1, 1, 10, 10, stroke=0),
    lambda p: M.add_roi_ellipse(p, [0], 0, 1, 1, 10, 10, fill_color="nope"),
    lambda p: M.add_roi_line(p, [0], 0, 10, 10, 10, 10),
    lambda p: M.add_roi_line(p, [0], 0, 1, 1, 9, 9, opacity=-1),
    lambda p: M.add_roi_polygon(p, [0], 0, [[1, 1], [9, 9]]),
    lambda p: M.add_roi_polygon(p, [0], 0, [[1, 1], "x", [9, 9]]),
    lambda p: M.add_roi_polygon(p, [0], 0, [1, 1, 9, 9, 5]),
    lambda p: M.add_significance_bracket(p, [0], 0, 20, 20, 5),
    lambda p: M.add_inset(p, [0], 0, p, placement="middle-ish"),
])
def test_bad_shapes_are_refused_not_stored_or_raised(one_panel, call):
    """An opacity of 2, a zero-length line, a 2-point polygon, a zero-width
    bracket and an unknown inset corner were stored; a bad colour or point
    raised a raw ValueError."""
    before = open(one_panel, encoding="utf-8").read()
    assert call(one_panel).startswith("ERROR")
    assert open(one_panel, encoding="utf-8").read() == before


def test_a_two_point_polyline_is_still_fine(one_panel):
    assert not M.add_roi_polygon(one_panel, [0], 0, [[1, 1], [9, 9]], style="polyline").startswith("ERROR")


def test_inset_of_a_missing_file_warns_and_a_broken_one_is_refused(one_panel, tmp_path):
    r = M.add_inset(one_panel, [0], 0, str(tmp_path / "later.png"))
    assert not r.startswith("ERROR") and "does not exist (yet)" in r
    (tmp_path / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\n garbage")
    assert M.add_inset(one_panel, [0], 0, str(tmp_path / "broken.png")).startswith("ERROR")


def test_describe_lists_shapes_and_free_texts(one_panel):
    """Brackets and arrow labels showed as '"**" ()'; ROIs were not listed."""
    M.add_roi_rect(one_panel, [0], 0, 1, 1, 10, 10)
    M.add_roi_rect(one_panel, [0], 0, 5, 5, 10, 10)
    M.add_roi_ellipse(one_panel, [0], 0, 1, 1, 10, 10)
    M.add_significance_bracket(one_panel, [0], 0, 5, 50, 10, label="**")
    d = M.describe_figure(one_panel)
    assert '"**" (free)' in d and "()" not in d
    assert "2 rectangles" in d and "1 ellipse" in d


def test_journal_guidelines_do_not_letter_a_lettered_figure_twice(tmp_path, imgs):
    """add_panel_labels put 'a' beside the 'A' draft_figure had added."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, orientation="Y")
    for i in range(2):
        M.add_group(pyf, orientation="X")
        M.add_image(pyf, [i], imgs[i])
    M.add_label_row(pyf, [0], ["WT"])
    r = M.apply_journal_guidelines(pyf, journal="nature", add_panel_labels=True)
    assert "added 2 bold letter(s)" in r            # not the label row
    r = M.apply_journal_guidelines(pyf, journal="nature", add_panel_labels=True)
    assert "already has 2 panel letter(s) — none added" in r


def test_non_positive_widths_and_font_minimum_are_refused(one_panel):
    assert M.check_resolution(one_panel, width_mm=-5).startswith("ERROR")
    assert M.check_resolution(one_panel, width_in=0).startswith("ERROR")
    assert M.enforce_min_font_size(one_panel, min_pt=0).startswith("ERROR")


def test_template_fills_check_their_files(one_panel, tmp_path, imgs):
    M.templatify_figure(one_panel)
    r = M.fill_template(one_panel, [0], 0, str(tmp_path / "later.png"))
    assert "does not exist (yet)" in r
    M.templatify_figure(one_panel)
    (tmp_path / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\n garbage")
    assert M.batch_fill_templates(one_panel, [0], [str(tmp_path / "broken.png")]).startswith("ERROR")
    r = M.batch_fill_templates(one_panel, [0], [imgs[1], imgs[2]])
    assert "1 more filename(s) than slots were not used" in r


def test_filling_a_slot_with_fewer_channels_resets_its_colours(one_panel, imgs):
    """A grey image put in a GREEN+RED slot was drawn dark green."""
    M.set_lut(one_panel, [0], 0, ["GRAY"])
    M.templatify_figure(one_panel)
    assert "did not fit" not in M.fill_template(one_panel, [0], 0, imgs[1])   # 1 channel, 1 LUT
    from pyfigures.mcp_tools.core import _load, _save, _encode_str
    tree, root = _load(one_panel)
    img = root.find(".//Image2D")
    img.find("LUTs").text = "['GREEN', 'RED']"
    img.find("filename").text = _encode_str("@template@")
    _save(tree, one_panel)
    r = M.fill_template(one_panel, [0], 0, imgs[2])
    assert "did not fit the file's 1 channel(s)" in r
    assert M.list_image_properties(one_panel, [0], 0).count('"LUTs": null') == 1
