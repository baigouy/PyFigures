"""Bugs found by the second day of stress-testing figure building through the
MCP tools (29 October 2026): negative indices, NaN widths, remapping Windows
paths, invisible shapes, print-ready spreads without guides."""
from __future__ import annotations

import os

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
    return [_png(tmp_path / f"im{i}.png", 40 * i + 20) for i in range(3)]


@pytest.fixture
def fig(tmp_path, imgs):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=2)
    M.add_image(pyf, [0], imgs[0])
    M.add_image(pyf, [0], imgs[1])
    M.add_image(pyf, [1], imgs[2])
    return pyf


@pytest.mark.parametrize("call", [
    lambda p: M.move_image(p, [0], -5, [1], 0),
    lambda p: M.clone_image(p, [0], -5, [1], 0),
    lambda p: M.add_roi_rect(p, [0], -3, 1, 1, 5, 5),
    lambda p: M.set_image_property(p, [0], -9, "LUTs", "None"),
])
def test_negative_indices_are_refused_not_crashing(fig, call):
    """-5 raised a raw IndexError (only 'index >= len' was checked)."""
    assert call(fig).startswith("ERROR")


@pytest.mark.parametrize("kw", [dict(width_mm=float("nan")), dict(width_mm=0), dict(width_cm=-1),
                                dict(width_px=-10), dict(width_mm=180, max_height_mm=-1),
                                dict(width_in=float("inf"))])
def test_resize_refuses_non_positive_or_nan_widths(fig, kw):
    """width_mm=nan raised 'cannot convert float NaN to integer'."""
    assert M.resize_figure(fig, **kw).startswith("ERROR")


def test_remap_paths_matches_windows_separators_and_folder_boundaries(fig, tmp_path):
    """Stored paths use '/', so a folder typed with '\\' matched nothing; an
    empty old prefix prepended the new one to every path."""
    folder_bs = str(tmp_path).replace("/", "\\")
    r = M.remap_paths(fig, folder_bs, "Z:/moved", dry_run=True)
    assert r.startswith("Would change 3 path(s)"), r
    # 'tmp_pa' is not a folder boundary of '.../tmp_path0/im0.png'
    r = M.remap_paths(fig, folder_bs[:-2], "Z:/moved", dry_run=True)
    assert r.startswith("Would change 0 path(s)"), r
    assert M.remap_paths(fig, "", "X").startswith("ERROR")
    assert M.remap_paths(fig, "/", "X").startswith("ERROR")
    M.remap_paths(fig, folder_bs + "\\", "Z:/moved/")
    from pyfigures.mcp_tools.core import _load
    stored = [e.text for e in _load(fig, resolve=False)[1].iter("filename")]
    assert any("Z:/moved/im0.png" in s for s in stored), stored


@pytest.mark.parametrize("call", [
    lambda p: M.add_roi_rect(p, [0], 0, 500, 500, 10, 10),
    lambda p: M.add_roi_ellipse(p, [0], 0, -50, -50, 10, 10),
    lambda p: M.add_roi_line(p, [0], 0, 100, 0, 200, 50),
    lambda p: M.add_roi_polygon(p, [0], 0, [[-5, -5], [-9, -1], [-1, -9]]),
])
def test_shapes_entirely_outside_the_image_are_refused(fig, call):
    """Drawings are cropped to the panel, so such a shape never shows: it used
    to be saved with only a warning."""
    r = call(fig)
    assert r.startswith("ERROR") and "cropped to the panel" in r, r
    assert "shapes:" not in M.describe_figure(fig)


def test_shapes_partly_outside_are_kept(fig):
    assert not M.add_roi_rect(fig, [0], 0, 40, 40, 100, 100).startswith("ERROR")


def test_restyle_validates_font_size_and_names_what_it_restyled(fig):
    M.add_annotation(fig, [0], 0, "hello")
    assert M.restyle_texts(fig, font_size=-3).startswith("ERROR")
    assert M.restyle_texts(fig, font_size=float("nan")).startswith("ERROR")
    r = M.restyle_texts(fig, font_size=12)
    assert r.startswith("Restyled 1 text(s):"), r


@pytest.mark.parametrize("call", [
    lambda p: M.set_scale_bar(p, [0], 0, 10, px_to_unit=0.5, placement="centre-ish"),
    lambda p: M.set_scale_bar(p, [0], 0, 10, px_to_unit=0.5, placement="center"),
    lambda p: M.set_scale_bar_all(p, 10, px_to_unit=0.5, placement="top"),
    lambda p: M.add_inset(p, [0], 0, str(os.path.join(os.path.dirname(p), "im1.png")), border_size=-2),
    lambda p: M.add_side_label(p, [0], ""),
    lambda p: M.add_side_label(p, [0], "<b> </b>"),
])
def test_bad_scale_bar_inset_and_side_label_values_are_refused(fig, call):
    """A scale bar at 'centre-ish', an inset with a -2 px border and an empty
    side label (a blank strip beside the row) were all stored."""
    before = open(fig, encoding="utf-8").read()
    assert call(fig).startswith("ERROR")
    assert open(fig, encoding="utf-8").read() == before


def test_inset_property_checks_border_and_placement(fig, imgs):
    M.add_inset(fig, [0], 0, imgs[1])
    assert M.set_inset_property(fig, [0], 0, 0, "border_size", -1).startswith("ERROR")
    assert M.set_inset_property(fig, [0], 0, 0, "placement", "nowhere").startswith("ERROR")
    assert not M.set_inset_property(fig, [0], 0, 0, "placement", "bottom-left").startswith("ERROR")
    assert not M.set_scale_bar(fig, [0], 0, 10, px_to_unit=0.5, placement="Top-Left").startswith("ERROR")


@pytest.fixture
def zstack(tmp_path):
    """A 5-slice, 2-channel ImageJ hyperstack (ZCYX)."""
    import tifffile
    p = tmp_path / "z.tif"
    data = (np.arange(5 * 2 * 16 * 16) % 251).astype(np.uint8).reshape(5, 2, 16, 16)
    tifffile.imwrite(p, data, imagej=True, metadata={"axes": "ZCYX"})
    return str(p)


@pytest.fixture
def zfig(tmp_path, zstack):
    pyf = str(tmp_path / "z.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], zstack)
    return pyf


@pytest.mark.parametrize("kw", [
    dict(projection="max", projection_z_start=3, projection_z_end=1),
    dict(projection="max", projection_z_start=0, projection_z_end=99),
    dict(projection_z_start=7),
    dict(channels=[True, False, True]),
    dict(channels=[False, False]),
    dict(normalization="weird"),
    dict(normalization='{"range": "custom", "min_value": 9, "max_value": 2}'),
    dict(normalization='{"colour": 1}'),
    dict(serie_to_open=4),
])
def test_configure_image_refuses_values_the_file_cannot_take(zfig, kw):
    """configure_image stored every one of these as given."""
    before = open(zfig, encoding="utf-8").read()
    r = M.configure_image(zfig, [0], 0, **kw)
    assert r.startswith("ERROR"), r
    assert open(zfig, encoding="utf-8").read() == before


def test_configure_image_still_takes_good_values(zfig):
    r = M.configure_image(zfig, [0], 0, projection="max", projection_z_start=1,
                          projection_z_end=5, channels=[True, False], serie_to_open=0)
    assert not r.startswith("ERROR"), r


def test_json_normalization_is_stored_so_the_renderer_can_read_it(zfig):
    """The documented '{"per_channel": true}' was stored as JSON, which
    ast.literal_eval (the renderer) cannot read: the panel came out solid white."""
    import ast
    for call in (lambda: M.configure_image(zfig, [0], 0, normalization='{"per_channel": true}'),
                 lambda: M.set_lut(zfig, [0], 0, ["GREEN", "RED"], normalization='{"per_channel": true}'),
                 lambda: M.set_image_property(zfig, [0], 0, "normalization", '{"per_channel": true}')):
        assert not call().startswith("ERROR")
        stored = ET_text(zfig, "normalization")
        assert ast.literal_eval(stored) == {"per_channel": True}, stored


def ET_text(pyf, tag):
    import xml.etree.ElementTree as ET
    return ET.parse(pyf).getroot().find(f".//Image2D/{tag}").text


def test_renderer_reads_normalization_saved_as_json():
    """Figures saved before the fix still hold JSON: the renderer reads it."""
    from batoolset.drawings.shapes.image2d import Image2D
    assert Image2D(normalization='{"per_channel": true}').normalization == {"per_channel": True}
    assert Image2D(normalization="weird").normalization is None


@pytest.mark.parametrize("call", [
    lambda p: M.add_significance_bracket(p, [0], 0, 5, 30, 5, font_pt=0),
    lambda p: M.add_significance_bracket(p, [0], 0, 5, 30, 5, stroke=-1),
    lambda p: M.add_significance_bracket(p, [0], 0, 5, 30, 5, color="nope"),
    lambda p: M.add_significance_bracket_from_data(p, [0], 0, 5, 30, 5, [1, 2, float("nan")], [2, 3, 4]),
    lambda p: M.add_significance_bracket_from_data(p, [0], 0, 5, 30, 5, [2, 2, 2], [2, 2, 2]),
    lambda p: M.add_significance_bracket_from_data(p, [0], 0, 5, 30, 5, [1, 2, 3], [2, 3, 4], font_pt=0),
])
def test_brackets_refuse_invisible_or_meaningless_values(fig, call):
    """font_pt=0 drew no label; NaN values were dropped silently; two constant
    groups got an 'n/a' bracket with p=nan."""
    r = call(fig)
    assert r.startswith("ERROR"), r
    assert "shapes:" not in M.describe_figure(fig)


def test_kymograph_refuses_zero_width_and_unknown_colour_map(tmp_path):
    import tifffile
    movie = tmp_path / "t.tif"
    tifffile.imwrite(movie, (np.arange(6 * 32 * 32) % 251).astype(np.uint8).reshape(6, 32, 32),
                     imagej=True, metadata={"axes": "TYX"})
    pyf = str(tmp_path / "k.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], str(movie))
    assert M.add_kymograph(pyf, [0], 0, 2, 2, 28, 20, line_width=0).startswith("ERROR")
    assert M.add_kymograph(pyf, [0], 0, 2, 2, 28, 20, cmap="nope").startswith("ERROR")
    assert not M.add_kymograph(pyf, [0], 0, 2, 2, 28, 20, cmap="magma").startswith("ERROR")


def test_write_xml_refuses_xml_that_is_not_a_figure(fig):
    """Any well-formed XML ('<root/>') replaced the whole figure."""
    before = open(fig, encoding="utf-8").read()
    assert M.write_xml(fig, "<root/>").startswith("ERROR")
    assert open(fig, encoding="utf-8").read() == before
    assert not M.write_xml(fig, M.get_xml(fig)).startswith("ERROR")


@pytest.mark.parametrize("kw", [dict(font_size=0), dict(font_size=-4), dict(default_spacing=-2),
                                dict(background_color=-5), dict(foreground_color=2 ** 40)])
def test_figure_properties_refuse_impossible_values(fig, kw):
    assert M.set_figure_properties(fig, **kw).startswith("ERROR")


@pytest.mark.parametrize("call", [
    lambda p, im: M.add_group(p, spacing=-1),
    lambda p, im: M.create_figure(p + ".2.pyf", spacing=-3),
    lambda p, im: M.set_script(p, [0], 0, "this is not python("),
    lambda p, im: M.add_scripted_image(p, [0], "def f(:\n  pass"),
    lambda p, im: M.add_scripted_image(p, [0], "   "),
    lambda p, im: M.set_image_filename(p, [0], 0, ""),
    lambda p, im: M.add_image(p, [0], "   "),
    lambda p, im: M.add_inset(p, [0], 0, ""),
])
def test_negative_spacing_broken_scripts_and_empty_filenames_are_refused(fig, imgs, call):
    """Each of these was stored: spacing -1, a script that does not parse (a
    blank panel at draw time), an empty or blank filename."""
    before = open(fig, encoding="utf-8").read()
    assert call(fig, imgs).startswith("ERROR")
    assert open(fig, encoding="utf-8").read() == before


def test_exports_never_overwrite_the_figure_or_its_source_images(fig, imgs, tmp_path):
    """export_figure(fig, 'camera.png') replaced the camera.png the figure was
    built from; render_poster did the same to a poster's photo."""
    original = open(imgs[0], "rb").read()
    for call in (lambda: M.export_figure(fig, imgs[0]),
                 lambda: M.export_figure(fig, imgs[0].upper()),           # Windows: same file
                 lambda: M.export_figure(fig, fig),
                 lambda: M.export_print_ready(fig, imgs[0]),
                 lambda: M.export_pptx(fig, fig)):
        r = call()
        assert r.startswith("ERROR") and "overwrite" in r, r
    assert open(imgs[0], "rb").read() == original
    poster = str(tmp_path / "p.pyfposter")
    M.create_poster(poster)
    M.add_poster_image(poster, imgs[1])
    photo = open(imgs[1], "rb").read()
    assert "overwrite" in M.render_poster(poster, imgs[1])
    assert open(imgs[1], "rb").read() == photo
    assert not M.export_figure(fig, str(tmp_path / "out.png")).startswith("ERROR")


def test_every_decorated_tool_is_registered_and_no_helper_is():
    """A helper inserted between @mcp.tool() and configure_image was registered
    in its place: configure_image vanished from the server."""
    import asyncio
    import glob
    import re
    names = {t.name for t in asyncio.run(M.mcp.list_tools())}
    assert not [n for n in names if n.startswith("_")]
    src = os.path.join(os.path.dirname(M.__file__), "mcp_tools", "*.py")
    decorated = set()
    for f in glob.glob(src):
        text = open(f, encoding="utf-8").read()
        decorated |= set(re.findall(r"^@mcp\.tool\(\)\ndef (\w+)\(", text, re.M))
    assert "configure_image" in decorated
    assert decorated <= names, decorated - names


def _over_mcp(name, **args):
    import asyncio
    try:
        res = asyncio.run(M.mcp.call_tool(name, args))
    except Exception as e:
        return f"ERROR: {e}"
    content = res[0] if isinstance(res, tuple) else res
    return "\n".join(getattr(c, "text", "") for c in content)


def test_undo_never_deletes_the_figure_unless_forced(tmp_path, imgs):
    """undo_last(steps=500) undid create_figure too and deleted the .pyf."""
    pyf = str(tmp_path / "u.pyf")
    _over_mcp("create_figure", pyf_path=pyf, num_groups=1)
    _over_mcp("add_image", pyf_path=pyf, group_path=[0], filename=imgs[0])
    r = _over_mcp("undo_last", pyf_path=pyf, steps=500)
    assert "would delete the figure file" in r and "add_image" in r, r
    assert os.path.isfile(pyf)
    assert "would delete" in _over_mcp("undo_last", pyf_path=pyf)
    assert os.path.isfile(pyf)
    assert not _over_mcp("undo_last", pyf_path=pyf, force=True).startswith("ERROR")
    assert not os.path.isfile(pyf)


def test_set_lut_takes_a_single_lut_as_text_over_mcp(fig):
    r = _over_mcp("set_lut", pyf_path=fig, group_path=[0], image_index=0, luts="GREEN")
    assert not r.startswith("ERROR"), r
    assert "GREEN" in M.get_image_property(fig, [0], 0, "LUTs")


def test_recipe_properties_take_a_normalization_mapping(tmp_path, imgs):
    """properties: {normalization: {per_channel: true}} — the natural YAML —
    was refused ('must be a text, number, ...'); a bad one is still refused."""
    import ast
    from pyfigures.recipe import RecipeError, build_figure_from_recipe as build_recipe
    r = tmp_path / "r.yaml"
    r.write_text(f"output: n.pyf\nrows:\n  - - image: {os.path.basename(imgs[0])}\n"
                 f"      properties: {{normalization: {{per_channel: true}}}}\n", encoding="utf-8")
    build_recipe(str(r))
    assert ast.literal_eval(ET_text(str(tmp_path / "n.pyf"), "normalization")) == {"per_channel": True}
    r.write_text(f"output: n2.pyf\nrows:\n  - - image: {os.path.basename(imgs[0])}\n"
                 f"      properties: {{normalization: {{colour: 1}}}}\n", encoding="utf-8")
    with pytest.raises(RecipeError):
        build_recipe(str(r))


@pytest.fixture
def poster(tmp_path, imgs):
    p = str(tmp_path / "p.pyfposter")
    M.create_poster(p)
    M.add_poster_image(p, imgs[0])
    M.add_poster_image(p, imgs[1])
    return p


@pytest.mark.parametrize("call", [
    lambda p, im: M.add_poster_image(p, im[2], height_mm=float("inf")),
    lambda p, im: M.add_poster_image(p, im[2], theta=float("nan")),
    lambda p, im: M.add_poster_image(p, im[2], x_mm=float("nan")),
    lambda p, im: M.set_poster_background(p, im[2], pan_x=float("nan")),
    lambda p, im: M.arrange_poster_grid(p, margin_mm=200),
    lambda p, im: M.arrange_poster_scatter(p, max_rotation_deg=-10),
    lambda p, im: M.create_poster(p + "2.pyfposter", page_preset=None, page_width_mm=float("nan"),
                                  page_height_mm=100),
])
def test_poster_tools_refuse_non_finite_numbers_and_impossible_layouts(poster, imgs, call):
    """inf / nan were saved as positions, sizes, angles and pans (a photo at
    x=-Infinity); a 200 mm margin on A4 and a negative rotation were accepted."""
    before = open(poster, encoding="utf-8").read()
    r = call(poster, imgs)
    assert r.startswith("ERROR"), r
    assert open(poster, encoding="utf-8").read() == before


_NAN, _INF = float("nan"), float("inf")


@pytest.mark.parametrize("tool,kw", [
    ("add_arrow", dict(tip_x=10, tip_y=10, from_direction=_NAN)),
    ("add_arrow", dict(tip_x=10, tip_y=10, stroke=_NAN)),
    ("add_roi_rect", dict(x=_NAN, y=1, width=5, height=5)),
    ("add_roi_rect", dict(x=1, y=1, width=_INF, height=5)),
    ("add_roi_line", dict(x1=1, y1=1, x2=_INF, y2=5)),
    ("add_significance_bracket", dict(x1=1, x2=5, y=_INF)),
    ("add_zoom_callout", dict(source_x=_NAN, source_y=1, source_w=20, source_h=20,
                              parent_width=64, parent_height=64)),
    ("set_roi_properties", dict(annotation_index=0, move_by=[_NAN, 1])),
    ("set_scale_bar", dict(bar_width_in_units=10, px_to_unit=_INF)),
])
def test_no_tool_saves_nan_or_infinity(fig, tool, kw):
    """A rectangle at x=nan, a bracket at y=inf, an arrow tail at (nan, nan),
    px_to_unit=inf were all saved; a NaN zoom source crashed int()."""
    M.add_roi_rect(fig, [0], 0, 2, 2, 10, 10)
    before = open(fig, encoding="utf-8").read()
    r = getattr(M, tool)(fig, [0], 0, **kw)
    assert r.startswith("ERROR") and "finite" in r, r
    assert open(fig, encoding="utf-8").read() == before


def test_alt_text_without_a_title_starts_with_a_capital(fig):
    """(28 Oct, manuscript rebuild) the alt text opened with 'figure with ...'."""
    import json
    d = json.loads(M.generate_alt_text(fig))
    assert d["short"].startswith("Figure with 3 panels"), d["short"]
    assert d["long"][0].isupper()


def test_print_ready_spread_has_no_fold_line_or_page_border(tmp_path):
    """A spread's dashed fold line and the black page border were printed."""
    album = str(tmp_path / "book.pyfalbum")
    assert "error" not in M.create_album(album, page_width_mm=60, page_height_mm=40).lower()
    out = tmp_path / "print"
    r = M.export_poster_album_print_ready(album, str(out), format="tiff", color_mode="rgb", dpi=72)
    assert "error" not in r.lower(), r
    spread = [f for f in os.listdir(out) if "spread" in f]
    assert spread, os.listdir(out)
    a = np.asarray(Image.open(out / spread[0]).convert("L"))
    h, w = a.shape
    assert a[:, w // 2 - 2:w // 2 + 3].min() == 255, "fold line printed"
    assert min(a[0].min(), a[-1].min(), a[:, 0].min(), a[:, -1].min()) == 255, "page border printed"
