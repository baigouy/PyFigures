"""Stack views (montage, channel split, kymograph, orthogonal views), arrows,
changed-source detection, copy_style, alt text and their recipe keys.

Run with PYTEST_QT_API=pyqt6 QT_API=pyqt6.
"""
from __future__ import annotations

import ast
import json
import os
import time
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

M = pytest.importorskip("pyfigures.mcp_server")


# ---------------------------------------------------------------------------
# synthetic data
# ---------------------------------------------------------------------------
def _hyperstack(path, T=5, Z=4, C=2, H=40, W=60, finterval=2.0):
    """ImageJ hyperstack; channel c of frame t, slice z has value 10*t + z + 100*c,
    plus a bright dot at x = 10 + 5*t, y = 20 (moves right over time)."""
    import tifffile
    a = np.zeros((T, Z, C, H, W), np.uint16)
    for t in range(T):
        for z in range(Z):
            for c in range(C):
                a[t, z, c] = 10 * t + z + 100 * c
        a[t, :, :, 20, 10 + 5 * t] = 4000
    tifffile.imwrite(path, a, imagej=True, resolution=(1 / 0.25, 1 / 0.25),
                     metadata={"axes": "TZCYX", "finterval": finterval, "tunit": "min",
                               "spacing": 0.5, "unit": "um"})
    return path


def _zstack(path, Z=6, H=30, W=50):
    import tifffile
    a = np.zeros((Z, H, W), np.uint16)
    for z in range(Z):
        a[z, 5:10, 7:9] = 1000 * (z + 1)      # a column whose brightness grows with z
    tifffile.imwrite(path, a, imagej=True, resolution=(1 / 0.5, 1 / 0.5),
                     metadata={"axes": "ZYX", "spacing": 1.0, "unit": "um"})
    return path


def _png(path, h=100, w=200, value=0):
    from PIL import Image
    Image.fromarray(np.full((h, w), value, np.uint8)).save(path)
    return path


def _panels(pyf):
    from pyfigures.mcp_tools.core import _iter_panel_elements
    return list(_iter_panel_elements(ET.parse(pyf).getroot()))


def _texts(img):
    from pyfigures.mcp_tools.core import _decode, _html_to_plain
    return [_html_to_plain(_decode(t.findtext("text")) or "").strip()
            for t in img.find("annotations").findall("TAText2D")]


# ---------------------------------------------------------------------------
# stack_info / parse_frames
# ---------------------------------------------------------------------------
def test_stack_info_reads_order_timing_and_voxels(tmp_path):
    from pyfigures.stack_info import stack_info
    info = stack_info(_hyperstack(str(tmp_path / "h.tif")))
    assert info["order"] == "tdhwc"
    assert info["sizes"] == {"t": 5, "d": 4, "h": 40, "w": 60, "c": 2}
    assert info["interval"] == 2.0 and info["time_unit"] == "min"
    assert info["vx"] == pytest.approx(0.25) and info["vz"] == pytest.approx(0.5)


def test_parse_frames():
    from pyfigures.stack_info import parse_frames, format_stamp
    assert parse_frames(None, 17) == [0, 3, 6, 10, 13, 16]
    assert parse_frames(5, 17) == [0, 4, 8, 12, 16]           # N evenly spaced
    assert parse_frames("5", 17) == [0, 4, 8, 12, 16]
    assert parse_frames("::5", 17) == [0, 5, 10, 15]          # every 5th
    assert parse_frames("all", 3) == [0, 1, 2]
    assert parse_frames([0, 2], 3) == [0, 2]
    assert parse_frames("1, 2", 3) == [1, 2]
    assert parse_frames(10, 3) == [0, 1, 2]
    with pytest.raises(ValueError):
        parse_frames([5], 3)
    assert format_stamp(4.0, "min") == "4 min" and format_stamp(2.5, "s") == "2.5 s"


# ---------------------------------------------------------------------------
# montage (opt-in)
# ---------------------------------------------------------------------------
def test_montage_time_native_panels_stamps_and_one_letter(tmp_path):
    from pyfigures.mcp_tools.workflow import _finalize_draft
    stack = _hyperstack(str(tmp_path / "h.tif"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    res = M.add_stack_montage(pyf, stack, axis="t", frames=3, channel=1)
    assert "3 time points" in res and "0 min" in res and "8 min" in res
    imgs = _panels(pyf)
    assert len(imgs) == 3
    for img, t in zip(imgs, (0, 2, 4)):
        dims = ast.literal_eval(img.findtext("dimensions"))
        assert dims == {"order": "tdhwc", "values": [t, 0]}
        assert img.findtext("projection").strip('"') == "max"       # Z collapsed
        assert img.findtext("custom_loading_script") == "None"      # native, no script
        assert ast.literal_eval(img.findtext("channels").strip('"')) == [False, True]
    assert [_texts(i)[0] for i in imgs] == ["0 min", "4 min", "8 min"]
    lettered, _ = _finalize_draft(pyf, True, "top left", None, None, "")
    assert lettered == 1                                             # one panel = one letter


def test_montage_z_uses_voxel_depth_and_columns(tmp_path):
    stack = _hyperstack(str(tmp_path / "h.tif"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    res = M.add_stack_montage(pyf, stack, axis="z", frames="all", columns=2)
    assert "2 row(s)" in res
    imgs = _panels(pyf)
    assert len(imgs) == 4
    assert [_texts(i)[0] for i in imgs] == ["0 µm", "0.5 µm", "1 µm", "1.5 µm"]
    assert all(i.findtext("projection") in ("None", '""None""') for i in imgs)


def test_montage_errors(tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    flat = _png(str(tmp_path / "a.png"))
    assert M.add_stack_montage(pyf, flat, axis="t").startswith("ERROR")
    stack = _hyperstack(str(tmp_path / "h.tif"))
    assert M.add_stack_montage(pyf, stack, frames=[99]).startswith("ERROR")
    assert M.add_stack_montage(pyf, stack, axis="q").startswith("ERROR")


# ---------------------------------------------------------------------------
# channel split
# ---------------------------------------------------------------------------
def test_channel_split_from_stack(tmp_path):
    stack = _hyperstack(str(tmp_path / "h.tif"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    res = M.add_channel_split(pyf, stack_path=stack, names=["GFP", "RFP"])
    assert "GFP (green)" in res and "RFP (magenta)" in res
    imgs = _panels(pyf)
    assert len(imgs) == 3
    ch = [ast.literal_eval(i.findtext("channels").strip('"')) for i in imgs]
    assert ch == [[True, False], [False, True], [True, True]]
    luts = [ast.literal_eval(i.findtext("LUTs")) for i in imgs]
    assert luts == [["GRAY", None], [None, "GRAY"], ["GREEN", "MAGENTA"]]
    # name written in the channel's colour on the gray panel
    raw = imgs[0].find("annotations").find("TAText2D").findtext("text")
    assert "40ff40" in raw.lower()
    assert _texts(imgs[2]) == ["Merge"]


def test_channel_split_from_files_uses_merge_script(tmp_path):
    a = _png(str(tmp_path / "a.png"), value=50)
    b = _png(str(tmp_path / "b.png"), value=90)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    assert not M.add_channel_split(pyf, channel_files=[a, b], gray=False).startswith("ERROR")
    imgs = _panels(pyf)
    assert len(imgs) == 3
    assert ast.literal_eval(imgs[0].findtext("LUTs")) == ["GREEN"]
    assert "pyfigures:channel_merge" in imgs[2].findtext("custom_loading_script")
    assert M.add_channel_split(pyf, channel_files=[a]).startswith("ERROR")
    assert M.add_channel_split(pyf, stack_path=a).startswith("ERROR")          # 1 channel


# ---------------------------------------------------------------------------
# kymograph + orthogonal views (scripts executed for real)
# ---------------------------------------------------------------------------
def _run_panel_script(script):
    """Execute a panel script as Image2D does; returns the figure's pixels."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from batoolset.img import Img

    class _Panel:
        img = None
    self = _Panel()
    ns = {"plt": plt, "Img": Img, "np": np}
    exec(script, {"self": self}, ns)
    fig = self.img
    fig.canvas.draw()
    rgba = np.asarray(fig.canvas.buffer_rgba())[..., :3].copy()
    plt.close(fig)
    return fig, rgba


def test_kymograph_shows_the_moving_dot_as_a_diagonal(tmp_path):
    stack = _hyperstack(str(tmp_path / "h.tif"), T=5, C=1)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], stack)
    res = M.add_kymograph(pyf, [0], 0, x1=0, y1=20.5, x2=59, y2=20.5, line_width=1,
                          frame_height=1)
    assert "5 frames" in res and "2 min" in res
    imgs = _panels(pyf)
    kymo = imgs[1]
    assert kymo.findtext("width") == "60.0" and kymo.findtext("height") == "5.0"
    # the sampled line is drawn on the source panel
    assert imgs[0].find("annotations").find("Line2D") is not None
    from pyfigures.mcp_tools.core import _decode
    _, rgb = _run_panel_script(_decode(kymo.findtext("custom_loading_script")))
    assert rgb.shape[:2] == (5, 60)
    for t in range(5):
        # brightest column of row t = the dot's x at time t (pixel 10 + 5t, centre +0.5)
        assert abs(int(np.argmax(rgb[t, :, 0])) - (10 + 5 * t)) <= 1


def test_orthogonal_views_layout_and_content(tmp_path):
    stack = _zstack(str(tmp_path / "z.tif"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], stack)
    res = M.add_orthogonal_views(pyf, [0], 0, x=8, y=7, z=2, gap=2)
    assert "side views 12 px deep" in res            # 6 slices x (1.0 / 0.5)
    ov = _panels(pyf)[1]
    assert (ov.findtext("width"), ov.findtext("height")) == ("64.0", "44.0")
    lines = ov.find("annotations").findall("Line2D")
    assert len(lines) == 6                            # crosshair incl. the z marks
    from pyfigures.mcp_tools.core import _decode
    _, rgb = _run_panel_script(_decode(ov.findtext("custom_loading_script")))
    assert rgb.shape[:2] == (44, 64)
    xz = rgb[32:44, 0:50, 0]                          # below XY (30 + gap 2)
    # the column at x=7..8 gets brighter with depth, 2 rows per slice
    assert xz[1, 8] < xz[11, 8]
    assert xz[5, 30] == 0                             # background of the volume
    assert rgb[31, 10, 0] == 255                      # white gap
    assert M.add_orthogonal_views(pyf, [0], 0, x=99, y=1).startswith("ERROR")


# ---------------------------------------------------------------------------
# arrows
# ---------------------------------------------------------------------------
def test_arrow_tip_is_stored_exactly_and_tail_stays_inside(tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(str(tmp_path / "a.png"), 100, 200))
    res = M.add_arrow(pyf, [0], 0, tip_x=150, tip_y=40, from_direction="ne",
                      length=100, label="nucleus")
    assert "shortened" in res                         # would leave the image
    line = _panels(pyf)[0].find("annotations").find("Line2D")
    assert (float(line.findtext("x2")), float(line.findtext("y2"))) == (150.0, 40.0)
    x1, y1 = float(line.findtext("x1")), float(line.findtext("y1"))
    assert x1 > 150 and y1 < 40 and 0 <= x1 <= 200 and 0 <= y1 <= 100
    assert line.findtext("arrow") == "True"
    assert "nucleus" in "".join(_texts(_panels(pyf)[0]))
    assert M.add_arrow(pyf, [0], 0, tip_x=150, tip_y=40, from_direction=90).startswith("Arrow")
    assert M.add_arrow(pyf, [0], 0, tip_x=500, tip_y=40).startswith("ERROR")
    assert M.add_arrow(pyf, [0], 0, tip_x=1, tip_y=1, from_direction="nw").startswith("ERROR")
    assert M.add_arrow(pyf, [0], 0, tip_x=5, tip_y=5, from_direction="up-ish").startswith("ERROR")


# ---------------------------------------------------------------------------
# changed sources
# ---------------------------------------------------------------------------
def test_source_snapshot_changed_touched_missing(tmp_path):
    from pyfigures.source_snapshot import compare, snapshot_path
    a = _png(str(tmp_path / "a.png"), value=10)
    b = _png(str(tmp_path / "b.png"), value=20)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], a)
    M.add_image(pyf, [0], b)
    assert os.path.isfile(snapshot_path(pyf))
    assert "unchanged" in M.check_source_changes(pyf)
    # touched only (same content): not reported
    later = time.time() + 5
    os.utime(a, (later, later))
    assert compare(pyf)["changed"] == []
    # content changed
    _png(a, value=99)
    os.utime(a, (later + 5, later + 5))
    res = compare(pyf)
    assert [os.path.basename(p) for p in res["changed"]] == ["a.png"]
    assert "a.png" in M.check_source_changes(pyf)
    # the next MCP edit reports it, then accepts it
    out = M.set_spacing(pyf, [0], 5)
    assert "WARNING" in out and "a.png" in out
    assert compare(pyf)["changed"] == []
    os.remove(b)
    assert [os.path.basename(p) for p in compare(pyf)["missing"]] == ["b.png"]
    M.check_source_changes(pyf, accept=True)
    assert compare(pyf)["missing"] == []


def test_source_snapshot_covers_script_sources(tmp_path):
    from pyfigures.source_snapshot import figure_sources
    csv = tmp_path / "d.csv"
    csv.write_text("A,B\n1,2\n2,3\n3,4\n")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_data_plot(pyf, [0], str(csv), annotate_stats=False)
    assert [os.path.basename(p) for p in figure_sources(pyf)] == ["d.csv"]


# ---------------------------------------------------------------------------
# copy style
# ---------------------------------------------------------------------------
def test_copy_style(tmp_path):
    from pyfigures.mcp_tools.workflow import _finalize_draft
    img = _png(str(tmp_path / "a.png"))
    src, tgt = str(tmp_path / "src.pyf"), str(tmp_path / "tgt.pyf")
    for p, sp in ((src, 12), (tgt, 3)):
        M.create_figure(p, num_groups=1, spacing=sp)
        M.add_image(p, [0], img)
        M.add_image(p, [0], img)
        _finalize_draft(p, True, "top left", 0.1, 10, "µm")
    M.set_spacing(src, [0], 12)
    M.set_figure_properties(src, font_family="Times New Roman", font_size=14)
    # a distinctive letter + scale-bar style in the source
    root = ET.parse(src).getroot()
    for ta in root.iter("TAText2D"):
        if ta.findtext("is_letter") == "True":
            ta.find("text").text = '""<b><span style="font-size:20pt; color:#ff0000;">a</span></b>""'
            ta.find("placement").text = "bottom left"
    for sb in root.iter("ScaleBar"):
        sb.find("bar_color").text = str(0xFFFF00)
        sb.find("placement").text = "top right"
    ET.ElementTree(root).write(src, encoding="unicode", xml_declaration=True)

    res = M.copy_style(src, tgt, dry_run=True)
    assert res.startswith("Would apply")
    res = M.copy_style(src, tgt)
    assert "letters: 2 letter(s)" in res and "lower case" in res
    t = ET.parse(tgt).getroot()
    letters = [ta for ta in t.iter("TAText2D") if ta.findtext("is_letter") == "True"]
    from pyfigures.mcp_tools.core import _decode
    htmls = [_decode(ta.findtext("text")) for ta in letters]
    assert ">a<" in htmls[0] and ">b<" in htmls[1] and "font-size:20pt" in htmls[1]
    assert all(ta.findtext("placement") == "bottom left" for ta in letters)
    assert {sb.findtext("bar_color") for sb in t.iter("ScaleBar")} == {str(0xFFFF00)}
    assert {sb.findtext("placement") for sb in t.iter("ScaleBar")} == {"top right"}
    assert t.find("SerializableQFont/size").text == "14"
    assert {g.findtext("space") for g in t.iter("Group")} == {"12"}
    assert M.copy_style(src, tgt, aspects=["colour"]).startswith("ERROR")


# ---------------------------------------------------------------------------
# alt text
# ---------------------------------------------------------------------------
def test_alt_text_describes_panels(tmp_path):
    from pyfigures.mcp_tools.workflow import _finalize_draft
    stack = _hyperstack(str(tmp_path / "h.tif"))
    csv = tmp_path / "d.csv"
    csv.write_text("WT,KO\n1,5\n2,6\n1.5,7\n1.2,6.5\n")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    M.add_stack_montage(pyf, stack, frames=3)
    M.add_channel_split(pyf, stack_path=stack, names=["GFP", "RFP"])
    M.add_group(pyf)
    M.add_data_plot(pyf, [2], str(csv), kind="box", ylabel="length")
    _finalize_draft(pyf, True, "top left", None, None, "")
    M.set_figure_caption(pyf, "text", title="Figure 2")
    d = json.loads(M.generate_alt_text(pyf))
    assert d["panels"] == 3
    assert d["short"].startswith("Figure 2: figure with 3 panels") and len(d["short"]) <= 250
    long = d["long"]
    assert "Panel A: a montage of 3 frames (0 min to 8 min)" in long
    assert "Panel B: the same field shown channel by channel (GFP and RFP), then merged" in long
    assert "Panel C: box plot of length comparing WT and KO" in long
    assert "significant" in long
    assert M.set_alt_text(pyf, "Custom. More.").startswith("Alt text saved")
    from pyfigures.mcp_tools.upkeep import read_alt_text
    assert read_alt_text(pyf) == {"short": "Custom.", "long": "Custom. More."}


# ---------------------------------------------------------------------------
# recipe keys
# ---------------------------------------------------------------------------
def test_recipe_stack_keys(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    stack = _hyperstack(str(tmp_path / "h.tif"))
    z = _zstack(str(tmp_path / "z.tif"))
    rec = tmp_path / "r.json"
    rec.write_text(json.dumps({
        "output": "out/F.pyf",
        "rows": [
            [{"montage": "h.tif", "frames": 3}],
            [{"split": "h.tif", "names": ["G", "R"]}],
            [{"image": "h.tif", "projection": "max",
              "arrows": [{"at": [30, 20], "from": "s"}],
              "kymograph": {"line": [0, 20, 59, 20], "width": 1}},
             {"image": "z.tif", "orthogonal": {"at": [8, 7]}}],
        ]}))
    res = build_figure_from_recipe(str(rec))
    assert res["stack_series"] == 2 and res["images"] == 2
    assert res["lettered"] == 6                       # A montage, B split, C-F
    imgs = _panels(res["output"])
    assert len(imgs) == 3 + 3 + 4
    src = imgs[6]
    assert src.findtext("projection").strip('"') == "max"
    assert len(src.find("annotations").findall("Line2D")) == 2      # arrow + kymo line
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"output": "o.pyf", "rows": [[
        {"image": "h.tif", "arrows": [{"at": [1]}]}]]}))
    with pytest.raises(RecipeError):
        build_figure_from_recipe(str(bad))
    bad.write_text(json.dumps({"output": "o.pyf", "rows": [[
        {"montage": "h.tif", "zoom": 2}]]}))
    with pytest.raises(RecipeError):
        build_figure_from_recipe(str(bad))


# ---------------------------------------------------------------------------
# pre-existing bugs found on the way
# ---------------------------------------------------------------------------
def test_set_size_restacks_rows(tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=2)
    M.add_image(pyf, [0], _png(str(tmp_path / "a.png"), 100, 100))
    M.add_image(pyf, [1], _png(str(tmp_path / "b.png"), 100, 100))
    M.set_size(pyf, 900)
    rows = [g for g in ET.parse(pyf).getroot() if g.tag == "Group"]
    imgs = [r.find("content").find("Image2D") for r in rows]
    y0, y1 = float(imgs[0].findtext("y")), float(imgs[1].findtext("y"))
    h0 = float(imgs[0].findtext("height")) / float(imgs[0].findtext("scale"))
    assert y1 >= y0 + h0 - 0.5                       # second row below the first


def test_scale_bar_colour_is_drawn_and_survives_layout(qapp, tmp_path):
    """set_scale_bar(bar_color=...) used to be ignored: ScaleBar always drew a
    white bar, and any layout pass reset the stored colour to white."""
    from qtpy.QtGui import QImage, QPainter, QColor
    from batoolset.drawings.shapes.scalebar import ScaleBar
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(str(tmp_path / "a.png")))
    M.set_scale_bar(pyf, [0], 0, 10, bar_color="yellow", px_to_unit=0.1)
    M.set_spacing(pyf, [0], 7)                        # runs the layout engine
    sb_el = next(ET.parse(pyf).getroot().iter("ScaleBar"))
    assert sb_el.findtext("bar_color") == str(0xFFFF00)
    sb = ScaleBar(bar_width_in_units=10, legend="", unit_to_pixel_conversion_factor=0.5,
                  bar_color=0xFFFF00)
    sb.setTopLeft(5, 5)
    sb.updateBoudingRect()
    img = QImage(60, 30, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0))
    p = QPainter(img)
    sb.draw(p)
    p.end()
    r = sb.bar
    c = img.pixelColor(int(r.center().x()), int(r.center().y()))
    assert (c.red(), c.green(), c.blue()) == (255, 255, 0)
    assert ScaleBar(bar_width_in_units=10).bar.fill_color == 0xFFFFFF   # default white


def test_flip_script_renders(qapp, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.mcp_tools.content import _make_flip_script
    src = _png(str(tmp_path / "a.png"), 20, 30, value=128)
    from matplotlib.figure import Figure
    panel = Image2D(src, custom_loading_script=_make_flip_script(True, False))
    assert "NameError" not in (panel.script_log or ""), panel.script_log
    assert isinstance(panel.img, Figure)
