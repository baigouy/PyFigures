"""Poster designer: file format (.pyfposter / .pyfalbum) round trips,
portability (relative paths when a folder is moved), atomic saves, legacy
files, undo / modified-state bookkeeping, and the poster recipe (YAML) through
its three entry points — CLI (poster_headless build), MCP
(build_poster_from_recipe) and GUI (PosterWindow "Build from recipe…").

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import io
import json
import os
import shutil
from contextlib import redirect_stderr, redirect_stdout

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _png(path, size, rgb):
    from PIL import Image
    Image.new("RGB", size, rgb).save(path)
    return str(path)


@pytest.fixture
def photos(tmp_path):
    d = tmp_path / "proj" / "photos"
    d.mkdir(parents=True)
    return {
        "red": _png(d / "red.png", (200, 100), (220, 30, 30)),
        "green": _png(d / "green.png", (100, 200), (30, 200, 60)),
        "blue": _png(d / "blue.png", (150, 150), (30, 60, 220)),
    }


@pytest.fixture
def canvas(qapp):
    from pyfigures.poster.poster_canvas import PosterCanvas
    return PosterCanvas()


def _fresh(qapp):
    from pyfigures.poster.poster_canvas import PosterCanvas
    return PosterCanvas()


# ---------------------------------------------------------------------------
# round trips
# ---------------------------------------------------------------------------

def test_pyfposter_round_trip_every_field(qapp, canvas, photos, tmp_path):
    a = canvas.add_image(photos["red"], x_mm=11.5, y_mm=22.25, width_mm=40, theta=-7.5)
    a.frame, a.caption, a.group_id = "polaroid", 'Café & "friends" <3', "g1"
    a.crop_left, a.crop_top, a.crop_right, a.crop_bottom = 0.1, 0.05, 0.2, 0.0
    a.source_pyf = photos["blue"]
    t = canvas.add_text('<b>Title</b> αβ', x_mm=5, y_mm=6, theta=3, style="h2")
    t.group_id = "g1"
    canvas.set_background(photos["green"])
    canvas.background.set_zoom(1.7)
    canvas.background.pan_x_frac = 0.25
    canvas.sketch_layout("diptych", group=False)
    doc = str(tmp_path / "proj" / "p.pyfposter")
    canvas.save(doc, filetype="pyfposter")

    c2 = _fresh(qapp)
    c2.load(doc)
    a2, t2, s1, s2 = c2.shapes_to_draw
    for attr in ("path", "x_mm", "y_mm", "width_mm", "height_mm", "theta", "frame", "caption",
                 "group_id", "crop_left", "crop_top", "crop_right", "crop_bottom", "source_pyf"):
        assert getattr(a2, attr) == getattr(a, attr), attr
    assert (t2.x_mm, t2.y_mm, t2.width_mm, t2.height_mm, t2.theta, t2.style, t2.group_id) == \
        (t.x_mm, t.y_mm, t.width_mm, t.height_mm, t.theta, t.style, t.group_id)
    assert "αβ" in t2.html
    assert (c2.background.path, c2.background.zoom, c2.background.pan_x_frac) == (photos["green"], 1.7, 0.25)
    assert s1.is_template and s2.is_template and s1.group_id is None
    assert not c2.is_modified() and c2.file_path == doc and not c2.can_undo()


def test_pyfalbum_round_trip_pages(qapp, canvas, photos, tmp_path):
    canvas.new_document(album=True)
    assert canvas.album_mode and not canvas.is_modified()
    canvas.goto_page(1)
    canvas.add_image(photos["red"])
    canvas.add_page()                                 # after the current page, and becomes current
    canvas.add_image(photos["blue"])
    doc = str(tmp_path / "a.pyfalbum")
    canvas.save(doc, filetype="pyfalbum")
    c2 = _fresh(qapp)
    c2.load(doc)
    assert c2.album_mode and [p.kind for p in c2.pages] == ["cover_front", "spread", "spread", "cover_back"]
    assert [len(p.shapes_to_draw) for p in c2.pages] == [0, 1, 1, 0]
    assert c2.base_page_width_mm == 210 and c2.base_page_height_mm == 297


def test_album_mode_cannot_be_toggled_on_a_document(canvas):
    assert not hasattr(canvas, "set_album_mode")      # albums are only made as albums


def test_pyfposter_refuses_multipage(canvas, tmp_path):
    canvas.add_page("spread")
    with pytest.raises(ValueError, match="pyfalbum"):
        canvas.save(str(tmp_path / "x.pyfposter"), filetype="pyfposter")


def test_load_rejects_non_poster_xml(canvas, tmp_path):
    p = tmp_path / "fig.pyfposter"
    p.write_text('<?xml version="1.0"?><SomethingElse/>', encoding="utf-8")
    with pytest.raises(ValueError, match="not a poster"):
        canvas.load(str(p))
    p.write_text('<?xml version="1.0"?><PosterAlbum version="1"/>', encoding="utf-8")
    with pytest.raises(ValueError, match="no <Page>"):
        canvas.load(str(p))


def test_legacy_file_without_rel_paths_loads(qapp, photos, tmp_path):
    p = tmp_path / "old.pyfposter"
    p.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<PosterDocument version="1" page_width_mm="210.0" page_height_mm="297.0">\n'
        f'  <Background path="{photos["blue"]}" zoom="1.0" pan_x_frac="0.5" pan_y_frac="0.5" />\n'
        f'  <Image path="{photos["red"]}" x_mm="10" y_mm="10" width_mm="40" height_mm="20" theta="0" frame="none" />\n'
        '  <Text x_mm="5" y_mm="5" width_mm="30" height_mm="10" theta="0">hello</Text>\n'
        '</PosterDocument>\n', encoding="utf-8")
    c = _fresh(qapp)
    c.load(str(p))
    assert c.shapes_to_draw[0].path == photos["red"] and c.background.path == photos["blue"]
    assert c.missing_files() == []


# ---------------------------------------------------------------------------
# portability + atomic writes
# ---------------------------------------------------------------------------

def test_moved_project_folder_still_finds_images(qapp, canvas, photos, tmp_path):
    canvas.add_image(photos["red"])
    canvas.set_background(photos["blue"])
    canvas.add_page("single")
    canvas.add_image(photos["green"])
    doc = str(tmp_path / "proj" / "album.pyfalbum")
    canvas.save(doc, filetype="pyfalbum")
    moved = tmp_path / "usb" / "proj"
    shutil.move(str(tmp_path / "proj"), str(moved))
    c2 = _fresh(qapp)
    c2.load(str(moved / "album.pyfalbum"))
    assert c2.missing_files() == []
    assert c2.pages[0].shapes_to_draw[0].path == os.path.normpath(str(moved / "photos" / "red.png"))
    assert c2.pages[0].background.path == os.path.normpath(str(moved / "photos" / "blue.png"))
    assert c2.pages[1].shapes_to_draw[0].path == os.path.normpath(str(moved / "photos" / "green.png"))


def test_really_missing_files_are_listed(qapp, canvas, photos, tmp_path):
    canvas.add_image(photos["red"])
    canvas.sketch_layout("single")                    # template slots are not files
    doc = str(tmp_path / "proj" / "p.pyfposter")
    canvas.save(doc, filetype="pyfposter")
    os.remove(photos["red"])
    c2 = _fresh(qapp)
    c2.load(doc)
    assert c2.missing_files() == [(0, "image", photos["red"])]


def test_failed_save_keeps_previous_file(qapp, canvas, photos, tmp_path, monkeypatch):
    import xml.etree.ElementTree as ET
    doc = str(tmp_path / "keep.pyfposter")
    canvas.add_image(photos["red"])
    canvas.save(doc, filetype="pyfposter")
    good = open(doc, "rb").read()
    canvas.add_image(photos["blue"])

    def broken_write(self, f, *a, **k):
        f.write(b"<PosterDocument partial")
        raise OSError("disk full")
    monkeypatch.setattr(ET.ElementTree, "write", broken_write)
    with pytest.raises(OSError):
        canvas.save(doc, filetype="pyfposter")
    assert open(doc, "rb").read() == good
    assert [n for n in os.listdir(tmp_path) if n.endswith(".tmp")] == []
    assert canvas.is_modified()                       # the failed save did not mark it clean


# ---------------------------------------------------------------------------
# undo / modified bookkeeping
# ---------------------------------------------------------------------------

def test_modified_follows_undo_back_to_saved_state(canvas, photos, tmp_path):
    assert not canvas.is_modified()
    canvas.add_image(photos["red"])
    assert canvas.is_modified()
    canvas.save(str(tmp_path / "m.pyfposter"), filetype="pyfposter")
    assert not canvas.is_modified()
    canvas.add_image(photos["blue"])
    assert canvas.is_modified()
    canvas.undo()
    assert not canvas.is_modified()                   # back at the saved state
    canvas.undo()
    assert canvas.is_modified()
    canvas.redo()
    assert not canvas.is_modified()
    canvas.undo()
    canvas.add_image(photos["green"])                 # new branch: saved state unreachable
    canvas.undo()
    assert canvas.is_modified()


def test_page_operations_are_undoable(canvas, photos):
    canvas.add_image(photos["red"])
    steps = [lambda: canvas.add_page("spread"), lambda: canvas.duplicate_page(0),
             lambda: canvas.move_page(0, 2), lambda: canvas.set_page_kind("cover_back", 2),
             lambda: canvas.remove_page(1), lambda: canvas.set_page_size_mm(297, 420)]
    states = []
    for step in steps:
        states.append([(p.kind, p.width_mm, len(p.shapes_to_draw)) for p in canvas.pages])
        step()
    for expected in reversed(states):
        canvas.undo()
        assert [(p.kind, p.width_mm, len(p.shapes_to_draw)) for p in canvas.pages] == expected


def test_move_page_onto_current_index_switches_page(canvas, photos):
    canvas.add_page("single")
    canvas.add_page("single")
    canvas.goto_page(1)
    canvas.add_image(photos["red"])                   # page 1 has the photo
    canvas.goto_page(2)
    canvas.move_page(1, 2)                            # current index stays 2, page changes
    assert canvas.current_page_index == 2 and len(canvas.shapes_to_draw) == 1


def test_set_page_kind_rejects_unknown(canvas):
    assert canvas.set_page_kind("leaflet") is False
    assert canvas.pages[0].kind == "single"


def test_arrangements_never_move_text(canvas, photos):
    from pyfigures.poster import poster_layouts, poster_templates
    canvas.add_image(photos["red"])
    t = canvas.add_text("T", x_mm=10, y_mm=10)
    g = (t.x_mm, t.y_mm, t.width_mm, t.theta)
    poster_layouts.scatter_layout(canvas.shapes_to_draw, 210, 297, seed=1)
    poster_layouts.arc_layout(canvas.shapes_to_draw, 100, 300, 200, page_width_mm=210, page_height_mm=297)
    poster_layouts.grid_layout(canvas.shapes_to_draw, 210, 297)
    poster_templates.apply_layout(canvas.shapes_to_draw, 210, 297, "single")
    assert (t.x_mm, t.y_mm, t.width_mm, t.theta) == g
    assert canvas.arrange("grid") == 1
    assert canvas.arrange("layout", layout_name="single") == 1


def test_arrange_nothing_is_not_an_edit(canvas):
    canvas.add_text("only text")
    n = len(canvas._undo_stack)
    assert canvas.arrange("scatter") == 0 and len(canvas._undo_stack) == n


# ---------------------------------------------------------------------------
# recipe
# ---------------------------------------------------------------------------

def _write_recipe(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


ALBUM_RECIPE = """
output: out/trip.pyfalbum
page: A4
album: true
render: out/trip.pdf
render_dpi: 40
web: out/trip.html
front_cover:
  background: photos/blue.png
  text:
    - {html: "<b>Trip 2026</b>", style: h1, x_mm: 20, y_mm: 30}
spreads:
  - images: ["photos/*.png"]
    arrange: {grid: {columns: 3}}
  - images:
      - {image: photos/red.png, frame: polaroid, caption: Red}
      - photos/green.png
    arrange: {layout: diptych}
    text: "plain caption"
back_cover:
  text: [{html: "<i>the end</i>", style: caption}]
"""


def _check_album(result, root):
    from pyfigures.poster.poster_canvas import PosterCanvas
    assert result["page_count"] == 4 and result["image_count"] == 5 and result["album_mode"] is True
    out = root / "out"
    assert (out / "trip.pyfalbum").is_file() and (out / "trip.pdf").stat().st_size > 0
    assert (out / "trip.html").read_text(encoding="utf-8").count("data:image/jpeg;base64,") == 4
    c = PosterCanvas()
    c.load(str(out / "trip.pyfalbum"))
    assert [p.kind for p in c.pages] == ["cover_front", "spread", "spread", "cover_back"]
    assert c.pages[0].background is not None and len(c.pages[0].shapes_to_draw) == 1
    grid = c.pages[1].shapes_to_draw
    assert [os.path.basename(s.path) for s in grid] == ["blue.png", "green.png", "red.png"]
    assert all(s.theta == 0 for s in grid)
    centres_y = {round(s.center_mm().y(), 3) for s in grid}
    assert len(centres_y) == 1                       # 3 columns -> one row
    d = c.pages[2].shapes_to_draw
    assert d[0].frame == "polaroid" and d[0].caption == "Red"
    assert d[0].group_id is not None and d[0].group_id == d[1].group_id
    assert type(d[2]).__name__ == "PosterText"
    assert type(c.pages[3].shapes_to_draw[0]).__name__ == "PosterText"


def test_recipe_cli_builds_album(qapp, photos, tmp_path):
    from pyfigures.poster import poster_headless
    root = tmp_path / "proj"
    r = _write_recipe(root / "album.yaml", ALBUM_RECIPE)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        assert poster_headless._main(["build", r]) == 0
    _check_album(json.loads(out.getvalue()), root)


def test_recipe_mcp_tool(qapp, photos, tmp_path, monkeypatch):
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools import poster as poster_tools
    from pyfigures.poster import poster_headless

    def inproc(args, timeout=120):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = poster_headless._main(args)
        return (code == 0), (json.loads(out.getvalue()) if code == 0 else err.getvalue())
    monkeypatch.setattr(poster_tools, "_run_poster_op", inproc)
    root = tmp_path / "proj"
    r = _write_recipe(root / "album.yaml", ALBUM_RECIPE)
    _check_album(json.loads(M.build_poster_from_recipe(r)), root)
    bad = _write_recipe(root / "bad.yaml", "output: x.pyfposter\nimages: [photos/nope.png]\n")
    res = M.build_poster_from_recipe(bad)
    assert res.startswith("ERROR") and "no such file" in res
    assert not (root / "x.pyfposter").exists()


def test_recipe_gui_button(qapp, photos, tmp_path, monkeypatch):
    from qtpy.QtWidgets import QFileDialog, QMessageBox
    from pyfigures.poster.poster_window import PosterWindow
    seen = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: seen.append(a[1])))
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: seen.append(a[2])))
    root = tmp_path / "proj"
    r = _write_recipe(root / "album.yaml", ALBUM_RECIPE)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (r, "")))
    w = PosterWindow(album=True)                       # an album recipe: the album designer
    w.recipe_action.trigger()
    assert seen == ["Recipe built"]
    assert w.page_list.count() == 4 and w.canvas.album_mode and not w.canvas.is_modified()
    assert w.canvas.file_path == str(root / "out" / "trip.pyfalbum")
    w.canvas.undo()                                    # the build is one undo step back to blank
    assert [p.kind for p in w.canvas.pages] == ["cover_front", "spread", "cover_back"]
    assert w.canvas.album_mode
    w.canvas.redo()
    bad = _write_recipe(root / "bad.yaml", "output: y.pyfposter\narrange: spiral\n")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (bad, "")))
    w.canvas.mark_saved()
    w.recipe_action.trigger()
    assert "arrange" in seen[-1]
    assert w.page_list.count() == 4                    # a bad recipe leaves the open album alone
    w.canvas.mark_saved()
    w.close()


def test_single_page_recipe(qapp, photos, tmp_path):
    from pyfigures.poster.poster_recipe import build_poster_from_recipe
    root = tmp_path / "proj"
    r = _write_recipe(root / "one.yaml", """
output: poster.pyfposter
page: {width_mm: 300, height_mm: 200}
background: {image: photos/blue.png, zoom: 1.5, pan_x: 0}
images: [photos/red.png, {image: photos/green.png, x_mm: 10, y_mm: 20, width_mm: 30}]
arrange: none
text: [{html: Hello, style: h1, width_mm: 100}]
render: poster.png
render_dpi: 30
""")
    res = build_poster_from_recipe(r)
    assert res["page_count"] == 1 and res["image_count"] == 2
    from pyfigures.poster.poster_canvas import PosterCanvas
    c = PosterCanvas()
    c.load(str(root / "poster.pyfposter"))
    assert (c.page_width_mm, c.page_height_mm) == (300, 200)
    assert (c.background.zoom, c.background.pan_x_frac) == (1.5, 0.0)
    g = c.shapes_to_draw[1]
    assert (g.x_mm, g.y_mm, g.width_mm, g.height_mm) == (10, 20, 30, 60)
    assert c.shapes_to_draw[2].width_mm == pytest.approx(100)
    from PIL import Image
    assert Image.open(root / "poster.png").size == (round(300 * 30 / 25.4), round(200 * 30 / 25.4))


def test_pages_recipe_without_album(qapp, photos, tmp_path):
    from pyfigures.poster.poster_recipe import build_poster_from_recipe
    root = tmp_path / "proj"
    r = _write_recipe(root / "pages.json", json.dumps({
        "output": "doc.pyfalbum",
        "pages": [{"images": ["photos/red.png"]}, {"kind": "spread", "images": ["photos/*.png"],
                                                    "arrange": {"scatter": {"seed": 4}}}],
    }))
    res = build_poster_from_recipe(r)
    assert res["page_count"] == 2 and res["album_mode"] is False and res["image_count"] == 4


@pytest.mark.parametrize("text,needle", [
    ("output: a.pyfposter\nfoo: 1\n", "unknown key"),
    ("images: [photos/red.png]\n", "output"),
    ("output: a.png\n", ".pyfposter or .pyfalbum"),
    ("output: a.pyfposter\npage: A7\n", "unknown preset"),
    ("output: a.pyfposter\npage: {width_mm: -2, height_mm: 3}\n", "positive"),
    ("output: a.pyfposter\nimages: ['photos/*.gif']\n", "no image matches"),
    ("output: a.pyfposter\nimages: [{image: photos/red.png, frame: gold}]\n", "unknown frame"),
    ("output: a.pyfposter\nimages: [{image: photos/red.png, x_mm: 3}]\n", "both x_mm and y_mm"),
    ("output: a.pyfposter\narrange: {layout: hexagon}\n", "unknown layout"),
    ("output: a.pyfposter\narrange: {grid: {rows: 2}}\n", "unknown key"),
    ("output: a.pyfposter\ntext: [{html: x, style: h9}]\n", "unknown style"),
    ("output: a.pyfposter\nalbum: true\nspreads: [{}]\n", "pyfalbum"),
    ("output: a.pyfalbum\nalbum: true\n", "spreads"),
    ("output: a.pyfalbum\nalbum: yes please\n", "true or false"),
    ("output: a.pyfalbum\nspreads: [{}]\n", "only with album"),
    ("output: a.pyfalbum\npages: [{kind: brochure}]\n", "unknown kind"),
    ("output: a.pyfalbum\npages: []\n", "non-empty"),
    ("output: a.pyfposter\nrender: a.gif\n", "unsupported format"),
    ("output: a.pyfposter\nweb: a.htm\n", ".html"),
    ("output: a.pyfposter\nrender_dpi: 0\n", "render_dpi"),
    ("output: a.pyfposter\nbackground: photos/none.png\n", "no such file"),
    ("- just\n- a list\n", "mapping"),
    ("output: [unclosed\n", "cannot parse"),
])
def test_recipe_errors_are_reported_before_writing(qapp, photos, tmp_path, text, needle):
    from pyfigures.poster.poster_recipe import build_poster_from_recipe, PosterRecipeError
    root = tmp_path / "proj"
    r = _write_recipe(root / "r.yaml", text)
    with pytest.raises(PosterRecipeError) as exc:
        build_poster_from_recipe(r)
    assert needle.lower() in str(exc.value).lower(), str(exc.value)
    assert not [n for n in os.listdir(root) if n.endswith((".pyfposter", ".pyfalbum"))]


def test_recipe_unreadable_image_is_a_recipe_error(qapp, photos, tmp_path):
    from pyfigures.poster.poster_recipe import build_poster_from_recipe, PosterRecipeError
    root = tmp_path / "proj"
    (root / "photos" / "broken.png").write_bytes(b"nope")
    r = _write_recipe(root / "r.yaml", "output: a.pyfposter\nimages: [photos/broken.png]\n")
    with pytest.raises(PosterRecipeError, match="cannot read"):
        build_poster_from_recipe(r)
    assert not (root / "a.pyfposter").exists()
