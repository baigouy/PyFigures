"""Poster / photo-album designer: every MCP tool, through the real
poster_headless CLI.

The MCP tools shell out to ``python -m pyfigures.poster.poster_headless``; here
that call is redirected to the same CLI entry point (``_main``) in-process, so
each test exercises the MCP argument mapping, the CLI parser and the canvas
code together without paying a Qt start-up per call. Two tests at the end go
through the real subprocess to keep that wiring honest.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import io
import json
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import mcp_server as M
from pyfigures.mcp_tools import poster as poster_tools

_REAL_RUN = poster_tools._run_poster_op     # the subprocess runner, before any patching


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

COLORS = {"red": (220, 30, 30), "green": (30, 200, 60), "blue": (30, 60, 220), "yellow": (240, 220, 40)}


def _png(path, size, rgb):
    from PIL import Image
    Image.new("RGB", size, rgb).save(path)
    return str(path)


@pytest.fixture
def photos(tmp_path):
    d = tmp_path / "photos"
    d.mkdir()
    return {
        "red": _png(d / "red.png", (200, 100), COLORS["red"]),         # 2:1
        "green": _png(d / "green.png", (100, 200), COLORS["green"]),   # 1:2
        "blue": _png(d / "blue.png", (150, 150), COLORS["blue"]),      # 1:1
        "yellow": _png(d / "yellow.jpg", (120, 80), COLORS["yellow"]),  # 3:2, jpeg
    }


def _run_inproc(op_args, timeout=120):
    from pyfigures.poster import poster_headless
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = poster_headless._main(list(op_args))
        except SystemExit as exc:          # argparse rejecting an argument
            code = exc.code or 2
    if code != 0:
        return False, err.getvalue().strip() or f"exit {code}"
    return True, json.loads(out.getvalue())


@pytest.fixture(autouse=True)
def inproc(qapp, monkeypatch):
    monkeypatch.setattr(poster_tools, "_run_poster_op", _run_inproc)


def ok(result):
    assert not result.startswith("ERROR"), result
    return json.loads(result)


def err(result, *needles):
    assert result.startswith("ERROR"), result
    for n in needles:
        assert n.lower() in result.lower(), result
    return result


def _poster(tmp_path, preset="A4", **kw):
    p = str(tmp_path / "doc.pyfposter")
    ok(M.create_poster(p, page_preset=preset, **kw))
    return p


def _album(tmp_path, photo=None):
    """A new photo album (create_album), *photo* on its spread."""
    p = str(tmp_path / "book.pyfalbum")
    ok(M.create_album(p))
    if photo:
        ok(M.add_poster_image(p, photo, page=1))
    return p


def _imgs(p, page=None):
    return ok(M.list_poster_images(p, page=page))["images"]


def _render(p, tmp_path, name="out.png", dpi=254, page=None):
    """dpi 254 = exactly 10 px per mm."""
    from PIL import Image
    out = str(tmp_path / name)
    ok(M.render_poster(p, out, dpi=dpi, page=page))
    return np.asarray(Image.open(out).convert("RGB")).astype(int)


def _close(px, rgb, tol=40):
    return all(abs(int(a) - b) <= tol for a, b in zip(px, rgb))


def _inside_page(img, w, h, tol=0.01):
    """Axis-aligned box of a (possibly rotated, framed) shape lies on the page."""
    import math
    l, t, r, b = {"none": (0, 0, 0, 0), "simple": (3, 3, 3, 3), "polaroid": (6, 6, 6, 22)}[img.get("frame") or "none"]
    ow, oh = img["width_mm"] + l + r, img["height_mm"] + t + b
    cx, cy = img["x_mm"] - l + ow / 2, img["y_mm"] - t + oh / 2
    th = math.radians(img["theta"])
    bw = abs(ow * math.cos(th)) + abs(oh * math.sin(th))
    bh = abs(ow * math.sin(th)) + abs(oh * math.cos(th))
    return (cx - bw / 2 >= -tol and cy - bh / 2 >= -tol
            and cx + bw / 2 <= w + tol and cy + bh / 2 <= h + tol)


# ---------------------------------------------------------------------------
# create / add / list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("preset,size", [("A4", (210, 297)), ("A3", (297, 420)), ("A0", (841, 1189))])
def test_create_poster_presets(tmp_path, preset, size):
    d = ok(M.create_poster(str(tmp_path / "p.pyfposter"), page_preset=preset))
    assert (d["page_width_mm"], d["page_height_mm"]) == size
    assert d["images"] == [] and d["page_count"] == 1 and d["album_mode"] is False


def test_create_poster_custom_size_and_validation(tmp_path):
    d = ok(M.create_poster(str(tmp_path / "c.pyfposter"), page_width_mm=100, page_height_mm=50))
    assert (d["page_width_mm"], d["page_height_mm"]) == (100, 50)
    err(M.create_poster(str(tmp_path / "bad.pyfposter"), page_preset="A9"), "unknown page preset")
    err(M.create_poster(str(tmp_path / "neg.pyfposter"), page_width_mm=-5, page_height_mm=50), "positive")
    assert not os.path.exists(tmp_path / "neg.pyfposter")


def test_add_image_defaults_center_and_keep_aspect(tmp_path, photos):
    p = _poster(tmp_path)
    d = ok(M.add_poster_image(p, photos["red"]))
    assert d["index"] == 0 and d["kind"] == "image"
    assert d["width_mm"] / d["height_mm"] == pytest.approx(2.0, rel=1e-3)
    assert d["x_mm"] + d["width_mm"] / 2 == pytest.approx(105, abs=0.01)
    assert d["y_mm"] + d["height_mm"] / 2 == pytest.approx(148.5, abs=0.01)
    # width only -> height follows the photo's aspect ratio (was left at the default)
    d = ok(M.add_poster_image(p, photos["green"], x_mm=10, y_mm=10, width_mm=30))
    assert (d["width_mm"], d["height_mm"]) == pytest.approx((30, 60))
    d = ok(M.add_poster_image(p, photos["red"], x_mm=10, y_mm=10, height_mm=20))
    assert (d["width_mm"], d["height_mm"]) == pytest.approx((40, 20))
    d = ok(M.add_poster_image(p, photos["blue"], x_mm=5, y_mm=6, width_mm=30, height_mm=10, theta=12))
    assert (d["x_mm"], d["y_mm"], d["width_mm"], d["height_mm"], d["theta"]) == (5, 6, 30, 10, 12)
    assert [i["index"] for i in _imgs(p)] == [0, 1, 2, 3]


def test_add_image_frames_captions_and_errors(tmp_path, photos):
    p = _poster(tmp_path)
    d = ok(M.add_poster_image(p, photos["blue"], frame="polaroid", caption="Summer 2026"))
    assert d["frame"] == "polaroid" and d["caption"] == "Summer 2026"
    err(M.add_poster_image(p, photos["blue"], frame="gold"), "unknown frame")
    err(M.add_poster_image(p, str(tmp_path / "nope.png")), "no such image")
    bad = tmp_path / "corrupt.png"
    bad.write_bytes(b"\x89PNG not really")
    err(M.add_poster_image(p, str(bad)), "cannot read")
    err(M.add_poster_image(p, photos["blue"], width_mm=-3), "positive")
    assert len(_imgs(p)) == 1          # failed calls left the document alone


def test_add_text_styles_scale_with_page(tmp_path):
    p4 = _poster(tmp_path, "A4")
    p0 = str(tmp_path / "a0.pyfposter")
    ok(M.create_poster(p0, page_preset="A0"))
    h1_a4 = ok(M.add_poster_text(p4, style="h1"))
    h1_a0 = ok(M.add_poster_text(p0, style="h1"))
    body = ok(M.add_poster_text(p4, "Hello", style="body"))
    assert h1_a4["kind"] == "text" and h1_a4["style"] == "h1"
    assert h1_a4["height_mm"] == pytest.approx(297 * 0.05)
    assert h1_a0["height_mm"] / h1_a4["height_mm"] == pytest.approx(1189 / 297, rel=1e-3)
    assert body["height_mm"] < h1_a4["height_mm"]
    assert "Hello" in body["html"]
    err(M.add_poster_text(p4, style="h7"), "unknown style")


def test_add_text_one_side_keeps_text_aspect(tmp_path):
    p = _poster(tmp_path)
    t = ok(M.add_poster_text(p, "<b>A fairly long title</b>"))
    aspect = t["width_mm"] / t["height_mm"]
    w = ok(M.add_poster_text(p, "<b>A fairly long title</b>", width_mm=100))
    assert w["width_mm"] == pytest.approx(100)
    assert w["width_mm"] / w["height_mm"] == pytest.approx(aspect, rel=1e-3)
    # still centred on the page
    assert w["x_mm"] + 50 == pytest.approx(105, abs=0.01)


def test_add_text_html_is_kept_safely(tmp_path):
    p = _poster(tmp_path)
    ok(M.add_poster_text(p, 'R&D <i>"quoted"</i> αβγ'))
    html = _imgs(p)[0]["html"]
    assert "R&amp;D" in html and "αβγ" in html and "font-style:italic" in html


# ---------------------------------------------------------------------------
# background
# ---------------------------------------------------------------------------

def test_background_set_adjust_clear(tmp_path, photos):
    p = _poster(tmp_path)
    d = ok(M.set_poster_background(p, photos["blue"], zoom=2.0, pan_x=0.2, pan_y=1.7))
    assert d["background"]["zoom"] == 2.0
    assert (d["background"]["pan_x_frac"], d["background"]["pan_y_frac"]) == (0.2, 1.0)   # clamped
    d = ok(M.adjust_poster_background(p, zoom=99))
    assert d["background"]["zoom"] == 6.0                                              # MAX_ZOOM
    d = ok(M.adjust_poster_background(p, zoom=0.1))
    assert d["background"]["zoom"] == 1.0                                              # never gaps
    d = ok(M.adjust_poster_background(p, reset=True))
    assert d["background"] == {"path": photos["blue"], "zoom": 1.0, "pan_x_frac": 0.5, "pan_y_frac": 0.5}
    assert ok(M.list_poster_images(p))["background"]["path"] == photos["blue"]
    ok(M.clear_poster_background(p))
    assert ok(M.list_poster_images(p))["background"] is None
    err(M.adjust_poster_background(p, zoom=2), "no background")
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"nope")
    err(M.set_poster_background(p, str(bad)), "cannot read")


def test_background_covers_page_in_render(tmp_path, photos):
    p = str(tmp_path / "bg.pyfposter")
    ok(M.create_poster(p, page_width_mm=50, page_height_mm=30))
    ok(M.set_poster_background(p, photos["green"]))     # portrait image on a landscape page
    px = _render(p, tmp_path)
    assert px.shape[:2] == (300, 500)
    for y, x in [(2, 2), (2, 497), (297, 2), (297, 497), (150, 250)]:
        assert _close(px[y, x], COLORS["green"]), (y, x, px[y, x])


# ---------------------------------------------------------------------------
# remove / frame / list
# ---------------------------------------------------------------------------

def test_remove_reindexes_and_validates(tmp_path, photos):
    p = _poster(tmp_path)
    for k in ("red", "green", "blue"):
        ok(M.add_poster_image(p, photos[k]))
    d = ok(M.remove_poster_image(p, 1))
    assert [os.path.basename(i["path"]) for i in d["images"]] == ["red.png", "blue.png"]
    assert [i["index"] for i in d["images"]] == [0, 1]
    err(M.remove_poster_image(p, 5), "out of range")
    err(M.remove_poster_image(p, -1), "out of range")


def test_set_frame_and_caption(tmp_path, photos):
    p = _poster(tmp_path)
    ok(M.add_poster_image(p, photos["red"]))
    ok(M.add_poster_text(p, "title"))
    d = ok(M.set_poster_image_frame(p, 0, frame="polaroid", caption="cap"))
    assert (d["frame"], d["caption"]) == ("polaroid", "cap")
    d = ok(M.set_poster_image_frame(p, 0, frame="simple"))
    assert (d["frame"], d["caption"]) == ("simple", "cap")            # caption kept
    d = ok(M.set_poster_image_frame(p, 0, caption=""))
    assert d["caption"] is None
    err(M.set_poster_image_frame(p, 0, frame="wood"), "unknown frame")
    err(M.set_poster_image_frame(p, 1, frame="simple"), "text box")     # was silently accepted
    err(M.set_poster_image_frame(p, 9, frame="simple"), "out of range")


def test_polaroid_caption_is_drawn(tmp_path, photos):
    p = str(tmp_path / "pol.pyfposter")
    ok(M.create_poster(p, page_width_mm=100, page_height_mm=100))
    ok(M.add_poster_image(p, photos["blue"], x_mm=20, y_mm=20, width_mm=40, height_mm=40,
                          frame="polaroid", caption="WWWW"))
    px = _render(p, tmp_path)
    strip = px[600 + 10:600 + 210, 140:660]          # 22 mm caption strip under the photo
    assert (strip.sum(axis=2) < 450).any(), "caption text not drawn"
    p2 = str(tmp_path / "nocap.pyfposter")
    ok(M.create_poster(p2, page_width_mm=100, page_height_mm=100))
    ok(M.add_poster_image(p2, photos["blue"], x_mm=20, y_mm=20, width_mm=40, height_mm=40, frame="polaroid"))
    px2 = _render(p2, tmp_path, "b.png")
    assert not (px2[600 + 10:600 + 210, 140:660].sum(axis=2) < 450).any()


def test_list_reports_missing_files(tmp_path, photos):
    p = _poster(tmp_path)
    tmp_img = shutil.copy(photos["red"], tmp_path / "gone.png")
    ok(M.add_poster_image(p, str(tmp_img)))
    ok(M.add_poster_image(p, photos["blue"]))
    os.remove(tmp_img)
    imgs = _imgs(p)
    assert [i["missing"] for i in imgs] == [True, False]
    out = str(tmp_path / "r.png")
    d = ok(M.render_poster(p, out, dpi=50))
    assert d["missing_files"] == [{"page": 0, "role": "image", "path": str(tmp_img)}]


# ---------------------------------------------------------------------------
# arrangements
# ---------------------------------------------------------------------------

def _four(tmp_path, photos, text=True):
    p = _poster(tmp_path)
    for k in ("red", "green", "blue", "yellow"):
        ok(M.add_poster_image(p, photos[k]))
    if text:
        ok(M.add_poster_text(p, "<b>Title</b>", style="h1", x_mm=20, y_mm=10))
    return p


def test_scatter_reproducible_on_page_and_leaves_text(tmp_path, photos):
    p = _four(tmp_path, photos)
    title = _imgs(p)[4]
    a = ok(M.arrange_poster_scatter(p, seed=7))["images"]
    b = ok(M.arrange_poster_scatter(p, seed=7))["images"]
    assert [(i["x_mm"], i["y_mm"], i["theta"]) for i in a] == [(i["x_mm"], i["y_mm"], i["theta"]) for i in b]
    assert all(abs(i["theta"]) <= 25 for i in a[:4])
    assert all(_inside_page(i, 210, 297) for i in a[:4])
    # the title text box is not tilted or moved by "scatter every image"
    assert (a[4]["x_mm"], a[4]["y_mm"], a[4]["theta"]) == (title["x_mm"], title["y_mm"], 0.0)
    c = ok(M.arrange_poster_scatter(p, seed=8))["images"]
    assert [i["theta"] for i in c[:4]] != [i["theta"] for i in a[:4]]


def test_scatter_indices_subset(tmp_path, photos):
    p = _four(tmp_path, photos, text=False)
    before = _imgs(p)
    after = ok(M.arrange_poster_scatter(p, indices="1,3", seed=1))["images"]
    assert after[0] == before[0] and after[2] == before[2]
    assert after[1] != before[1] and after[3] != before[3]
    err(M.arrange_poster_scatter(p, indices="0,9"), "out of range")


def test_scatter_no_fit_may_bleed(tmp_path, photos):
    p = _four(tmp_path, photos, text=False)
    d = ok(M.arrange_poster_scatter(p, seed=3, margin_mm=0, max_rotation_deg=45, fit_to_page=False))
    fitted = ok(M.arrange_poster_scatter(p, seed=3, margin_mm=0, max_rotation_deg=45))
    assert all(_inside_page(i, 210, 297) for i in fitted["images"])
    assert len(d["images"]) == 4


def test_arc_fits_page_and_faces(tmp_path, photos):
    p = _four(tmp_path, photos)
    d = ok(M.arrange_poster_arc(p, 105, 400, 300, start_angle_deg=-40, end_angle_deg=40))
    imgs = d["images"][:4]
    assert [i["theta"] for i in imgs] == pytest.approx([-40, -40 + 80 / 3, 40 - 80 / 3, 40])
    assert all(_inside_page(i, 210, 297) for i in imgs)
    assert d["images"][4]["theta"] == 0
    d = ok(M.arrange_poster_arc(p, 105, 400, 300, face="inward"))
    assert d["images"][0]["theta"] == pytest.approx(-60 + 180)
    d = ok(M.arrange_poster_arc(p, 105, 400, 300, face="none"))
    assert all(i["theta"] == 0 for i in d["images"])
    err(M.arrange_poster_arc(p, 105, 400, 300, face="sideways"), "face")


def test_grid_tidy_no_overlap(tmp_path, photos):
    p = _four(tmp_path, photos)
    d = ok(M.arrange_poster_scatter(p, seed=2))
    d = ok(M.arrange_poster_grid(p, columns=2, gap_mm=6))
    imgs = d["images"][:4]
    assert all(i["theta"] == 0 for i in imgs)
    assert all(_inside_page(i, 210, 297) for i in imgs)
    boxes = [(i["x_mm"], i["y_mm"], i["x_mm"] + i["width_mm"], i["y_mm"] + i["height_mm"]) for i in imgs]
    for a in range(4):
        for b in range(a + 1, 4):
            A, B = boxes[a], boxes[b]
            assert A[2] <= B[0] or B[2] <= A[0] or A[3] <= B[1] or B[3] <= A[1], (A, B)
    # aspect ratios kept (2:1, 1:2, 1:1, 3:2)
    assert [i["width_mm"] / i["height_mm"] for i in imgs] == pytest.approx([2, 0.5, 1, 1.5], rel=1e-3)
    # two columns: images 0 and 2 share a column centre
    c0 = imgs[0]["x_mm"] + imgs[0]["width_mm"] / 2
    c2 = imgs[2]["x_mm"] + imgs[2]["width_mm"] / 2
    assert c0 == pytest.approx(c2)


# ---------------------------------------------------------------------------
# align / distribute
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["left", "right", "top", "bottom", "center_h", "center_v"])
def test_align_modes(tmp_path, photos, mode):
    p = _poster(tmp_path)
    ok(M.add_poster_image(p, photos["red"], x_mm=10, y_mm=20, width_mm=40))
    ok(M.add_poster_image(p, photos["blue"], x_mm=60, y_mm=90, width_mm=30))
    ok(M.add_poster_text(p, "T", x_mm=120, y_mm=150))
    imgs = ok(M.align_poster_shapes(p, mode))["images"]
    edges = {
        "left": [i["x_mm"] for i in imgs],
        "right": [i["x_mm"] + i["width_mm"] for i in imgs],
        "top": [i["y_mm"] for i in imgs],
        "bottom": [i["y_mm"] + i["height_mm"] for i in imgs],
        "center_h": [i["x_mm"] + i["width_mm"] / 2 for i in imgs],
        "center_v": [i["y_mm"] + i["height_mm"] / 2 for i in imgs],
    }[mode]
    assert max(edges) - min(edges) < 1e-6, edges


def test_align_and_distribute_need_enough_shapes(tmp_path, photos):
    p = _poster(tmp_path)
    ok(M.add_poster_image(p, photos["red"]))
    err(M.align_poster_shapes(p, "left"), "at least 2")
    err(M.align_poster_shapes(p, "middle"), "unknown mode")
    ok(M.add_poster_image(p, photos["red"]))
    err(M.distribute_poster_shapes(p, "x"), "at least 3")
    err(M.distribute_poster_shapes(p, "z"), "axis")


def test_distribute_even_centres(tmp_path, photos):
    p = _poster(tmp_path)
    for x in (10, 25, 150, 60):
        ok(M.add_poster_image(p, photos["blue"], x_mm=x, y_mm=50, width_mm=10, height_mm=10))
    imgs = ok(M.distribute_poster_shapes(p, "x"))["images"]
    centres = sorted(i["x_mm"] + 5 for i in imgs)          # were 15, 30, 65, 155
    assert centres == pytest.approx([15, 15 + 140 / 3, 15 + 280 / 3, 155])
    before = [(i["x_mm"], i["y_mm"]) for i in imgs]
    imgs = ok(M.distribute_poster_shapes(p, "y", indices="0,1,2"))["images"]
    assert [(i["x_mm"], i["y_mm"]) for i in imgs] == pytest.approx(before)   # same y: nothing to spread


# ---------------------------------------------------------------------------
# layouts / templates / groups
# ---------------------------------------------------------------------------

def test_list_layouts():
    d = ok(M.list_poster_layouts())
    names = {l["name"]: l["slot_count"] for l in d["layouts"]}
    assert names["single"] == 1 and names["big_plus_three_side"] == 4 and names["grid_3x3"] == 9
    counts = [l["slot_count"] for l in d["layouts"]]
    assert counts == sorted(counts)


def test_apply_layout_groups_and_repeats(tmp_path, photos):
    p = _four(tmp_path, photos)                       # 4 photos + 1 title
    d = ok(M.apply_poster_layout(p, "diptych"))      # 2 slots, 4 photos -> 2 bands
    imgs = d["images"]
    gids = {i["group_id"] for i in imgs[:4]}
    assert len(gids) == 1 and None not in gids
    assert imgs[4]["group_id"] is None                # title untouched
    assert imgs[2]["y_mm"] > imgs[0]["y_mm"] + imgs[0]["height_mm"] - 1e-6   # second band below
    assert all(_inside_page(i, 210, 297) for i in imgs[:4])
    d = ok(M.ungroup_poster_images(p, 2))
    assert all(i["group_id"] is None for i in d["images"])


def test_apply_layout_no_repeat_and_no_group(tmp_path, photos):
    p = _four(tmp_path, photos, text=False)
    before = _imgs(p)
    d = ok(M.apply_poster_layout(p, "diptych", repeat=False, group=False))
    assert d["images"][2] == before[2] and d["images"][3] == before[3]
    assert all(i["group_id"] is None for i in d["images"])
    err(M.apply_poster_layout(p, "nonexistent"), "unknown layout")


def test_sketch_then_fill_slots(tmp_path, photos):
    p = _poster(tmp_path)
    d = ok(M.sketch_poster_layout(p, "hero_with_strip"))
    imgs = d["images"]
    assert len(imgs) == 4 and all(i["is_template"] for i in imgs) and not any(i["missing"] for i in imgs)
    slot = imgs[0]
    f = ok(M.fill_poster_template_slot(p, 0, photos["green"]))   # portrait into a landscape slot
    assert f["is_template"] is False and f["path"] == photos["green"]
    assert f["width_mm"] / f["height_mm"] == pytest.approx(0.5, rel=1e-3)
    assert f["height_mm"] <= slot["height_mm"] + 1e-6 and f["width_mm"] <= slot["width_mm"] + 1e-6
    assert f["x_mm"] + f["width_mm"] / 2 == pytest.approx(slot["x_mm"] + slot["width_mm"] / 2)
    assert f["group_id"] == slot["group_id"]
    err(M.fill_poster_template_slot(p, 0, photos["red"]), "not an empty template slot")
    bad = tmp_path / "x.png"
    bad.write_bytes(b"x")
    err(M.fill_poster_template_slot(p, 1, str(bad)), "cannot read")
    assert _imgs(p)[1]["is_template"] is True
    # apply_layout skips the remaining empty slots (they are a layout already)
    d = ok(M.apply_poster_layout(p, "single"))
    assert d["images"][1]["is_template"] and d["images"][1]["x_mm"] == imgs[1]["x_mm"]


def test_sketch_no_group(tmp_path):
    p = _poster(tmp_path)
    d = ok(M.sketch_poster_layout(p, "grid_2x2", group=False))
    assert all(i["group_id"] is None for i in d["images"])
    err(M.sketch_poster_layout(p, "bogus"), "unknown layout")


# ---------------------------------------------------------------------------
# pages / album
# ---------------------------------------------------------------------------

def test_pages_add_list_duplicate_move_remove(tmp_path, photos):
    p = _poster(tmp_path)
    ok(M.add_poster_image(p, photos["red"]))
    d = ok(M.add_poster_page(p))                               # spread, double width
    assert [(pg["kind"], pg["width_mm"]) for pg in d["pages"]] == [("single", 210), ("spread", 420)]
    ok(M.add_poster_image(p, photos["blue"], page=1))
    d = ok(M.add_poster_page(p, kind="cover_front", index=0))
    assert [pg["kind"] for pg in d["pages"]] == ["cover_front", "single", "spread"]
    d = ok(M.duplicate_poster_page(p, 2))
    assert [pg["shape_count"] for pg in d["pages"]] == [0, 1, 1, 1]
    # the copy is independent
    ok(M.remove_poster_image(p, 0, page=3))
    assert [pg["shape_count"] for pg in ok(M.list_poster_pages(p))["pages"]] == [0, 1, 1, 0]
    d = ok(M.move_poster_page(p, 1, 3))
    assert [pg["kind"] for pg in d["pages"]] == ["cover_front", "spread", "spread", "single"]
    d = ok(M.set_poster_page_kind(p, 3, "cover_back"))
    assert d["pages"][3]["kind"] == "cover_back"
    d = ok(M.remove_poster_page(p, 2))
    assert len(d["pages"]) == 3
    err(M.set_poster_page_kind(p, 0, "poster"), "unknown kind")
    err(M.remove_poster_page(p, 7), "out of range")
    err(M.add_poster_page(p, kind="leaflet"), "unknown kind")
    err(M.add_poster_page(p, width_mm=-1), "positive")
    lst = ok(M.list_poster_images(p, page=1))
    assert lst["page_index"] == 1 and lst["page_kind"] == "spread" and lst["page_count"] == 3
    err(M.list_poster_images(p, page=9), "out of range")


def test_last_page_cannot_be_removed(tmp_path):
    p = _poster(tmp_path)
    err(M.remove_poster_page(p, 0), "last remaining page")


def test_album_mode_structure_and_rules(tmp_path, photos):
    p = _album(tmp_path, photos["red"])
    d = ok(M.list_poster_pages(p))
    assert d["album_mode"] is True
    assert [(pg["kind"], pg["width_mm"], pg["shape_count"]) for pg in d["pages"]] == [
        ("cover_front", 210, 0), ("spread", 420, 1), ("cover_back", 210, 0)]
    d = ok(M.add_poster_page(p))                               # inserted between the covers
    assert [pg["kind"] for pg in d["pages"]] == ["cover_front", "spread", "spread", "cover_back"]
    d = ok(M.add_poster_page(p, index=4))                      # past the back cover -> clamped
    assert d["pages"][-1]["kind"] == "cover_back" and len(d["pages"]) == 5
    # every refusal is an error now, not a silent "ok"
    err(M.add_poster_page(p, kind="cover_front"), "album mode")
    err(M.remove_poster_page(p, 0), "cover")
    err(M.remove_poster_page(p, 4), "cover")
    err(M.duplicate_poster_page(p, 0), "cover")
    err(M.duplicate_poster_page(p, 4), "cover")
    err(M.move_poster_page(p, 0, 2), "cover")
    err(M.move_poster_page(p, 1, 4), "cover")
    err(M.set_poster_page_kind(p, 0, "spread"), "album mode")
    err(M.set_poster_page_kind(p, 2, "single"), "album mode")
    d = ok(M.move_poster_page(p, 1, 3))
    assert d["pages"][3]["shape_count"] == 1
    assert not hasattr(M, "set_poster_album_mode")             # an album stays an album


def test_create_album_only_as_a_new_pyfalbum(tmp_path, photos):
    d = ok(M.create_album(str(tmp_path / "a3"), page_preset="A3"))     # extension added
    assert d["path"] == str(tmp_path / "a3.pyfalbum")
    assert d["album_mode"] is True and d["page_count"] == 3 and d["page_kind"] == "cover_front"
    pages = ok(M.list_poster_pages(str(tmp_path / "a3.pyfalbum")))["pages"]
    assert [(pg["width_mm"], pg["height_mm"]) for pg in pages] == [(297, 420), (594, 420), (297, 420)]
    d = ok(M.create_album(str(tmp_path / "custom.pyfalbum"), page_width_mm=200, page_height_mm=200))
    assert d["page_width_mm"] == 200
    err(M.create_album(str(tmp_path / "x.pyfposter")), "pyfalbum")
    err(M.create_album(str(tmp_path / "bad.pyfalbum"), page_preset="A9"), "unknown page preset")
    poster = str(tmp_path / "old.pyfalbum")                   # a plain multi-page document
    ok(M.create_poster(poster))
    ok(M.add_poster_page(poster))
    err(M.create_album(poster), "already exists")             # never converted
    assert ok(M.list_poster_pages(poster))["album_mode"] is False
    d = ok(M.create_poster(str(tmp_path / "plain.pyfposter")))
    assert d["album_mode"] is False and d["page_count"] == 1
    import inspect
    assert "album" not in inspect.signature(M.create_poster).parameters


def test_no_page_argument_means_page_zero(tmp_path, photos):
    p = _poster(tmp_path)
    ok(M.add_poster_page(p))                                   # new page becomes current in the file
    ok(M.add_poster_page(p))
    d = ok(M.add_poster_image(p, photos["red"]))
    pages = ok(M.list_poster_pages(p))["pages"]
    assert [pg["shape_count"] for pg in pages] == [1, 0, 0]
    assert ok(M.list_poster_images(p))["page_index"] == 0
    assert d["index"] == 0


def test_album_document_keeps_working_under_the_same_path(tmp_path, photos):
    p = _poster(tmp_path)
    ok(M.add_poster_page(p))
    with open(p, encoding="utf-8") as f:
        assert "<PosterAlbum" in f.read()
    ok(M.add_poster_image(p, photos["red"], page=1))
    assert len(_imgs(p, page=1)) == 1


# ---------------------------------------------------------------------------
# rendering / export
# ---------------------------------------------------------------------------

def test_render_places_pixels_where_the_geometry_says(tmp_path, photos):
    p = str(tmp_path / "px.pyfposter")
    ok(M.create_poster(p, page_width_mm=100, page_height_mm=100))
    ok(M.add_poster_image(p, photos["red"], x_mm=10, y_mm=10, width_mm=40, height_mm=20))
    ok(M.add_poster_image(p, photos["blue"], x_mm=60, y_mm=60, width_mm=20, height_mm=20, theta=45))
    px = _render(p, tmp_path)
    assert px.shape[:2] == (1000, 1000)
    assert _close(px[200, 300], COLORS["red"])
    assert _close(px[95, 95], (255, 255, 255))          # just outside the red box
    assert _close(px[700, 700], COLORS["blue"])         # rotated square centre
    assert _close(px[605, 605], (255, 255, 255))        # corner cut off by the 45° turn
    assert _close(px[700, 570], COLORS["blue"])         # ...but the diamond reaches further left


@pytest.mark.parametrize("ext", ["png", "jpg", "tif", "bmp", "svg", "pdf"])
def test_render_formats(tmp_path, photos, ext):
    p = _four(tmp_path, photos)
    out = str(tmp_path / f"o.{ext}")
    d = ok(M.render_poster(p, out, dpi=40))
    assert d["path"] == out and os.path.getsize(out) > 0
    if ext in ("png", "jpg", "tif", "bmp"):
        from PIL import Image
        im = Image.open(out)
        assert im.size == (round(210 * 40 / 25.4), round(297 * 40 / 25.4))
        if ext == "jpg":
            assert _close(np.asarray(im.convert("RGB"))[2, 2], (255, 255, 255))   # white, not black
    with open(out, "rb") as f:
        head = f.read(64)
    if ext == "pdf":
        assert head.startswith(b"%PDF")
    if ext == "svg":
        assert b"<?xml" in head or b"<svg" in head


def test_render_rejects_bad_format_and_dpi(tmp_path, photos):
    p = _four(tmp_path, photos)
    err(M.render_poster(p, str(tmp_path / "o.xyz")), "unsupported")
    err(M.render_poster(p, str(tmp_path / "o.png"), dpi=0), "dpi")
    err(M.render_poster(p, str(tmp_path / "o.png"), page=3), "out of range")


def test_render_specific_page(tmp_path, photos):
    p = str(tmp_path / "pg.pyfposter")
    ok(M.create_poster(p, page_width_mm=50, page_height_mm=50))
    ok(M.add_poster_page(p, kind="single"))
    ok(M.set_poster_background(p, photos["red"], page=0))
    ok(M.set_poster_background(p, photos["blue"], page=1))
    assert _close(_render(p, tmp_path, "a.png", page=0)[250, 250], COLORS["red"])
    assert _close(_render(p, tmp_path, "b.png", page=1)[250, 250], COLORS["blue"])


def test_preview_poster_returns_png(tmp_path, photos):
    p = _four(tmp_path, photos)
    im = M.preview_poster(p, dpi=30, max_dimension=200)
    from PIL import Image
    pil = Image.open(io.BytesIO(im.data))
    assert pil.format == "PNG" and max(pil.size) <= 200
    with pytest.raises(ValueError):
        M.preview_poster(str(tmp_path / "missing.pyfposter"))


def test_render_album_pdf_page_sizes(tmp_path, photos):
    p = _album(tmp_path, photos["red"])
    out = str(tmp_path / "book.pdf")
    d = ok(M.render_poster_album(p, out, dpi=50))
    assert d["page_count"] == 3
    fitz = pytest.importorskip("fitz")
    doc = fitz.open(out)
    sizes = [(round(pg.rect.width / 72 * 25.4), round(pg.rect.height / 72 * 25.4)) for pg in doc]
    assert sizes == [(210, 297), (420, 297), (210, 297)]


def test_print_ready_single_page(tmp_path, photos):
    from PIL import Image
    p = _four(tmp_path, photos)
    d = ok(M.export_poster_print_ready(p, str(tmp_path / "p.tif"), dpi=50))
    im = Image.open(d["path"])
    assert im.mode == "CMYK" and round(im.info["dpi"][0]) == 50
    d = ok(M.export_poster_print_ready(p, str(tmp_path / "rgb.tif"), color_mode="rgb", dpi=50))
    assert Image.open(d["path"]).mode == "RGB"
    for fmt in ("eps", "pdf", "svg"):
        d = ok(M.export_poster_print_ready(p, str(tmp_path / f"p.{fmt}"), format=fmt, dpi=50))
        assert os.path.getsize(d["path"]) > 0
    err(M.export_poster_print_ready(p, str(tmp_path / "x.gif"), format="gif"), "format")
    err(M.export_poster_print_ready(p, str(tmp_path / "x.tif"), color_mode="lab"), "color_mode")


def test_print_ready_album_folder_and_pdf(tmp_path, photos):
    p = _album(tmp_path, photos["red"])
    folder = str(tmp_path / "print")
    d = ok(M.export_poster_album_print_ready(p, folder, format="tiff", dpi=30))
    assert d["mode"] == "folder" and d["page_count"] == 3
    names = sorted(os.listdir(folder))
    assert names == ["manifest.json", "page_01_cover_front.tif", "page_02_spread.tif", "page_03_cover_back.tif"]
    with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    assert man["color_mode"] == "CMYK" and [m["kind"] for m in man["pages"]] == ["cover_front", "spread", "cover_back"]
    d = ok(M.export_poster_album_print_ready(p, str(tmp_path / "book.pdf"), format="pdf", dpi=30))
    assert d["mode"] == "single_file" and os.path.getsize(d["path"]) > 0


def test_web_export_is_self_contained(tmp_path, photos):
    p = _album(tmp_path, photos["red"])
    out = str(tmp_path / "book.html")
    d = ok(M.export_poster_web(p, out, dpi=20, quality=60))
    assert d["page_count"] == 3
    with open(out, encoding="utf-8") as f:
        html = f.read()
    assert html.count("data:image/jpeg;base64,") == 3
    assert "http://" not in html and "https://" not in html      # nothing fetched from outside
    err(M.export_poster_web(p, out, quality=150), "quality")


def test_source_data_bundle_reopens_after_moving(tmp_path, photos):
    p = _poster(tmp_path)
    ok(M.add_poster_image(p, photos["red"]))
    ok(M.set_poster_background(p, photos["blue"]))
    ok(M.add_poster_page(p))
    ok(M.add_poster_image(p, photos["green"], page=1))
    out = str(tmp_path / "bundle")
    d = ok(M.export_poster_source_data(p, out, dpi=50))
    assert d["n_files"] == 3 and d["page_count"] == 2
    assert os.path.isfile(os.path.join(out, "manifest.json")) and os.path.isfile(os.path.join(out, "MANIFEST.txt"))
    # The bundle is meant to travel: move it, delete the originals, reopen.
    moved = str(tmp_path / "elsewhere" / "bundle")
    shutil.move(out, moved)
    shutil.rmtree(tmp_path / "photos")
    doc = os.path.join(moved, os.path.basename(d["document"]))
    pages = ok(M.list_poster_pages(doc))["pages"]
    assert len(pages) == 2
    for pg in range(2):
        lst = ok(M.list_poster_images(doc, page=pg))
        assert not any(i["missing"] for i in lst["images"])
        for i in lst["images"]:
            assert os.path.normcase(i["path"]).startswith(os.path.normcase(moved))
    assert ok(M.list_poster_images(doc))["background"]["path"].startswith(moved)
    assert "missing_files" not in ok(M.render_poster(doc, str(tmp_path / "r.png"), dpi=30))


def test_pyf_figure_on_a_poster_and_nested_bundle(tmp_path, photos):
    """MCP parity with the GUI drop: a .pyf added as a photo is flattened,
    remembered, and its own source-data bundle nested in the poster's."""
    pyf = str(tmp_path / "Figure1.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], photos["red"])
    M.add_image(pyf, [0], photos["blue"])
    p = _poster(tmp_path)
    d = ok(M.add_poster_image(p, pyf, x_mm=10, y_mm=10, width_mm=120))
    assert d["source_pyf"] == os.path.abspath(pyf) and d["path"].endswith(".png")
    assert os.path.isfile(d["path"]) and str(tmp_path) in d["path"]       # tmp cache, not ~
    assert d["width_mm"] == 120
    out = str(tmp_path / "bundle")
    b = ok(M.export_poster_source_data(p, out, dpi=50))
    assert b["nested_pyf_bundles"] == 1
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    entry = next(e for e in man["files"] if e.get("source_pyf"))
    assert entry["source_pyf"] == "Figure1.pyf"
    nested = os.path.join(out, entry["source_pyf_bundle"])
    assert {"figure.png", "MANIFEST.txt", "sources"} <= set(os.listdir(nested))
    assert len(os.listdir(os.path.join(nested, "sources"))) >= 2          # the figure's two images
    # filling a template slot with a figure works the same way
    ok(M.sketch_poster_layout(p, "single"))
    f = ok(M.fill_poster_template_slot(p, 1, pyf))
    assert f["source_pyf"] == os.path.abspath(pyf)


def test_source_data_reports_missing_files(tmp_path, photos):
    p = _poster(tmp_path)
    gone = shutil.copy(photos["red"], tmp_path / "gone.png")
    ok(M.add_poster_image(p, str(gone)))
    os.remove(gone)
    d = ok(M.export_poster_source_data(p, str(tmp_path / "b"), dpi=30))
    assert d["n_files"] == 0 and len(d["missing_files"]) == 1


# ---------------------------------------------------------------------------
# the real subprocess path (what the MCP server actually runs)
# ---------------------------------------------------------------------------

def test_real_subprocess_round_trip(tmp_path, photos, monkeypatch):
    monkeypatch.setattr(poster_tools, "_run_poster_op", _REAL_RUN)
    p = str(tmp_path / "real.pyfposter")
    ok(M.create_poster(p, page_width_mm=60, page_height_mm=40))
    ok(M.add_poster_image(p, photos["red"], x_mm=0, y_mm=0, width_mm=60, height_mm=40))
    out = str(tmp_path / "real.png")
    ok(M.render_poster(p, out, dpi=50))
    from PIL import Image
    assert _close(np.asarray(Image.open(out).convert("RGB"))[40, 60], COLORS["red"])
    err(M.remove_poster_image(p, 4), "out of range")
