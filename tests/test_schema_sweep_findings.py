"""Bugs found by sweeping every MCP tool with edge values (29 October 2026):
empty paths resolving to the working directory, raw colour exceptions, the
figure resized before a bad option was refused, out-of-range sizes, unknown
placements and projections."""
from __future__ import annotations

import hashlib
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402

import pyfigures.mcp_server as M  # noqa: E402


def _png(path, value=128, size=(64, 64)):
    Image.fromarray(np.full(size, value, np.uint8)).save(path)
    return str(path)


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


@pytest.fixture
def fig(tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=2)
    M.add_image(pyf, [0], _png(tmp_path / "a.png", 60))
    M.add_image(pyf, [0], _png(tmp_path / "b.png", 120))
    M.add_image(pyf, [1], _png(tmp_path / "c.png", 200))
    return pyf


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("call", [
    lambda p: M.index_figures(os.path.dirname(p), index_path=""),
    lambda p: M.export_caption(p, out_path=""),
    lambda p: M.get_xml(""),
    lambda p: M.resize_figure("", width_mm=89),
    lambda p: M.set_size("", 500),
    lambda p: M.export_source_data(p, ""),
    lambda p: M.create_poster(""),
    lambda p: M.create_album(""),
    lambda p: M.export_latex(p, ""),
])
def test_empty_paths_are_refused_and_write_nothing(fig, in_tmp, call):
    """'' resolved to the working directory: index_figures tried to replace the
    folder with its index file; create_poster('') wrote '.pyfposter' there."""
    before = set(os.listdir(in_tmp))
    res = call(fig)
    assert isinstance(res, str) and res.startswith("ERROR") and "empty" in res, res
    assert set(os.listdir(in_tmp)) == before


def test_show_me_how_keeps_its_empty_default(monkeypatch):
    from pyfigures.mcp_tools import app
    assert app._empty_path_argument(M.show_me_how.__wrapped__, (), {"operation": "x", "pyf_path": ""}) is None


@pytest.mark.parametrize("call", [
    lambda p: M.add_zoom_callout(p, [0], 0, 1, 1, 10, 10, 64, 64, box_color="zzz"),
    lambda p: M.add_zoom_callout(p, [0], 0, 1, 1, 10, 10, 64, 64, line_color=""),
    lambda p: M.set_roi_properties(p, [0], 0, 0, color="zzz"),
    lambda p: M.add_roi_rect(p, [0], 0, 5, 5, 10, 10, color=-1),
    lambda p: M.add_arrow(p, [0], 0, 10, 10, color=-1),
    lambda p: M.restyle_texts(p, color=-1),
])
def test_bad_colours_are_errors_not_exceptions(fig, call):
    """A raw ValueError reached the client; -1 was stored and drawn white."""
    M.add_roi_rect(fig, [0], 0, 5, 5, 20, 20)
    M.add_annotation(fig, [0], 0, "t")
    before = _sha(fig)
    res = call(fig)
    assert res.startswith("ERROR") and "color" in res.lower(), res
    assert _sha(fig) == before


def test_style_annotation_refuses_unknown_colour(fig):
    M.add_annotation(fig, [0], 0, "t")
    before = _sha(fig)
    assert M.style_annotation(fig, [0], 0, 0, color="zzz_bogus").startswith("ERROR")
    assert _sha(fig) == before
    assert not M.style_annotation(fig, [0], 0, 0, color="#ff0000").startswith("ERROR")


@pytest.mark.parametrize("tool", ["resize", "journal"])
def test_bad_fit_height_leaves_the_figure_untouched(fig, tool):
    """The figure was resized, then fit_height='zzz' was refused."""
    before = _sha(fig)
    res = (M.resize_figure(fig, width_mm=60, fit_height="zzz") if tool == "resize"
           else M.apply_journal_guidelines(fig, journal="nature", fit_height="zzz"))
    assert "fit_height" in res and "ERROR" in res, res
    assert _sha(fig) == before


@pytest.mark.parametrize("call", [
    lambda p: M.add_arrow(p, [0], 0, 10, 10, stroke=-1),
    lambda p: M.add_group(p, spacing=-1),
    lambda p: M.set_spacing(p, [0], 10 ** 7),
    lambda p: M.resize_figure(p, width_mm=1e9),
    lambda p: M.set_size(p, 10 ** 7),
    lambda p: M.restyle_texts(p, font_size=1e9),
    lambda p: M.set_figure_properties(p, font_size=10 ** 7),
    lambda p: M.enforce_min_font_size(p, min_pt=1e9),
    lambda p: M.check_resolution(p, journal="nature", min_dpi=-1),
    lambda p: M.export_source_data(p, os.path.join(os.path.dirname(p), "sd"), dpi=10 ** 7),
    lambda p: M.auto_configure_images(p, scale_bar_width=0),
    lambda p: M.add_significance_bracket(p, [0], 0, 5, 30, 10, font_pt=1e9),
    lambda p: M.set_scale_bar(p, [0], 0, 10, px_to_unit=-1),
    lambda p: M.resize_figure(p, width_mm=89, group_path=[-1]),
    lambda p: M.set_size(p, 500, group_path=[-1]),
])
def test_out_of_range_numbers_are_refused(fig, call):
    before = _sha(fig)
    res = call(fig)
    assert isinstance(res, str) and res.startswith("ERROR"), res
    assert _sha(fig) == before


@pytest.mark.parametrize("call", [
    lambda p, d: M.add_image(p, [0], d["img"], label="x", label_placement="zzz"),
    lambda p, d: M.add_image(p, [0], d["img"], label_placement=""),
    lambda p, d: M.add_data_plot(p, [0], d["csv"], label_placement="middle of nowhere"),
    lambda p, d: M.auto_configure_images(p, bar_placement="center"),
    lambda p, d: M.add_scripted_image(p, [0], "import matplotlib.pyplot as plt\nfig = plt.figure()\n",
                                      label_placement="zzz"),
])
def test_unknown_placements_are_refused(fig, tmp_path, call):
    """label_placement='zzz' was stored; the label then drew at a default spot."""
    csv = tmp_path / "d.csv"
    csv.write_text("group,value\nA,1\nA,2\nB,3\nB,4\n")
    before = _sha(fig)
    res = call(fig, {"img": str(tmp_path / "a.png"), "csv": str(csv)})
    assert res.startswith("ERROR") and "placement" in res, res
    assert _sha(fig) == before


def test_kymograph_frame_height_cannot_be_negative(tmp_path):
    import tifffile
    movie = str(tmp_path / "m.tif")
    tifffile.imwrite(movie, np.zeros((4, 32, 32), np.uint8), imagej=True, metadata={"axes": "TYX"})
    pyf = str(tmp_path / "k.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], movie)
    res = M.add_kymograph(pyf, [0], 0, 2, 2, 30, 30, frame_height=-1)
    assert res.startswith("ERROR") and "frame_height" in res, res
    assert not M.add_kymograph(pyf, [0], 0, 2, 2, 30, 30, frame_height=0).startswith("ERROR")


@pytest.mark.parametrize("kw", [dict(vmin=5, vmax=5), dict(vmin=10, vmax=1), dict(lut="")])
def test_calibration_bar_needs_a_lut_and_an_increasing_range(fig, kw):
    before = _sha(fig)
    assert M.add_lut_calibration_bar(fig, [0], **kw).startswith("ERROR")
    assert _sha(fig) == before


@pytest.mark.parametrize("call", [
    lambda p: M.enforce_min_font_size(p, font_family=""),
    lambda p: M.restyle_texts(p, font_family=""),
    lambda p: M.set_figure_properties(p, font_family=""),
])
def test_empty_font_family_is_refused(fig, call):
    """font_family='' was saved as the figure's font."""
    before = _sha(fig)
    assert call(fig).startswith("ERROR")
    assert _sha(fig) == before


def test_unknown_projection_is_refused(fig, tmp_path):
    a = str(tmp_path / "a.png")
    assert M.add_channel_split(fig, channel_files=[a, a], projection="zzz").startswith("ERROR")
    assert not M.configure_image(fig, [0], 0, projection="").startswith("ERROR")   # '' clears it


def test_channel_split_without_input_says_what_is_missing(fig):
    res = M.add_channel_split(fig)
    assert res.startswith("ERROR") and "not both" not in res


def test_zoom_callout_refuses_a_missing_inset_file(fig, tmp_path):
    before = _sha(fig)
    res = M.add_zoom_callout(fig, [0], 0, 1, 1, 10, 10, 64, 64,
                             inset_filename=str(tmp_path / "nope.png"))
    assert res.startswith("ERROR") and "nope.png" in res, res
    assert _sha(fig) == before


def test_set_image_filename_warns_about_a_missing_file(fig, tmp_path):
    res = M.set_image_filename(fig, [0], 0, str(tmp_path / "later.png"))
    assert not res.startswith("ERROR") and "WARNING" in res and "does not exist" in res


def test_label_row_over_a_column_is_a_row_and_the_figure_exports(fig, tmp_path):
    """A render walk found it: add_label_row copied a vertical group's
    orientation; the vertical label row's layout divided by zero, every panel
    below it went to y = 1e30 and export failed (QImage size overflow)."""
    import xml.etree.ElementTree as ET
    M.set_orientation(fig, [0], "vertical")
    assert M.add_label_row(fig, [0], ["A", "B"]).startswith("ERROR")    # a column: one header
    res = M.add_label_row(fig, [0], "Header", position="above")
    assert not res.startswith("ERROR"), res
    row = ET.parse(fig).getroot()[0]
    assert row.findtext("orientation").strip('"') == "X"
    out = str(tmp_path / "o.png")
    assert not M.export_figure(fig, out, dpi=72).startswith("ERROR")
    w, h = Image.open(out).size
    assert 50 < h < 5000 and 50 < w < 5000, (w, h)


def test_a_saved_vertical_label_row_loads_as_a_row():
    """Figures saved by the old add_label_row: the loader makes the row a row."""
    from batoolset.drawings.shapes.group import Group
    assert Group(orientation='"Y"', isText='"below"').orientation == "X"
    assert Group(orientation="Y").orientation == "Y"


def test_export_latex_never_overwrites_a_source_image(tmp_path):
    """export_latex('camera.tex', image_format='png') writes camera.png +
    camera.png_tex: it replaced the figure's own camera.png."""
    cam = _png(tmp_path / "camera.png", 77)
    before = _sha(cam)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], cam)
    res = M.export_latex(pyf, str(tmp_path / "camera.tex"), image_format="png")
    assert res.startswith("ERROR") and "overwrite" in res, res
    assert _sha(cam) == before
    assert not os.path.exists(str(tmp_path / "camera.png_tex"))


def test_pptx_export_keeps_tiny_text(fig, tmp_path):
    """A render walk found it: a 0.3 pt text made export_pptx fail with
    python-pptx's 'value must be in range 100 to 400000'."""
    pytest.importorskip("pptx")
    M.add_annotation(fig, [0], 0, "tiny")
    M.restyle_texts(fig, font_size=0.3)
    out = str(tmp_path / "f.pptx")
    res = M.export_pptx(fig, out)
    assert not res.startswith("ERROR"), res
    assert os.path.getsize(out) > 0


def test_colour_blindness_out_path_needs_an_image_extension(fig, tmp_path):
    with pytest.raises(ValueError, match="must end in"):
        M.simulate_color_blindness(fig, out_path=str(tmp_path / "sim"))


def test_empty_poster_page_index_message(tmp_path):
    poster = str(tmp_path / "p.pyfposter")
    M.create_poster(poster)
    res = M.remove_poster_image(poster, 0)
    assert "no images or text boxes" in res and "0..-1" not in res, res
