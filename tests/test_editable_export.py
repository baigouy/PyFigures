"""Editable exports: PowerPoint (.pptx) and Adobe Illustrator script (.jsx).

- SVG path / transform parsing and scene building (pure Python)
- the PowerPoint writer (reopened with python-pptx) and the .jsx writer
- CroppingPainter: Qt's SVG engine ignores drawImage source rects (cropped
  panels used to be exported uncropped and squeezed); the painter crops itself
- end to end: GUI actions, MCP tools and recipe exports on a real figure

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures.gui import editable_export as E  # noqa: E402

pptx = pytest.importorskip("pptx")


def _png(w=8, h=4, color=(255, 0, 0)):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def test_parse_path_lines_curves_relative_and_close():
    subs = E.parse_path_d("M0,0 L10,0 L10,10 Z m20,0 l5,0 l0,5")
    assert len(subs) == 2
    (p0, c0), (p1, c1) = subs
    assert c0 is True and p0[:3] == [(0, 0), (10, 0), (10, 10)]
    # after Z the pen is back at the subpath start (0, 0)
    assert c1 is False and p1 == [(20.0, 0.0), (25.0, 0.0), (25.0, 5.0)]
    curve = E.parse_path_d("M0,0 C0,10 10,10 10,0")[0][0]
    assert len(curve) == 1 + E._CURVE_STEPS and curve[-1] == pytest.approx((10, 0))
    assert max(y for _, y in curve) == pytest.approx(7.5)      # bezier peak


def test_parse_svg_transforms_styles_text_and_images():
    png = base64.b64encode(_png()).decode()
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
      viewBox="0 0 200 100">
     <g fill="#ff0000" stroke="none" transform="matrix(2,0,0,2,10,5)">
       <path d="M0,0 L10,0 L10,10 L0,10 L0,0"/></g>
     <g fill="none" stroke="#00ff00" stroke-width="1.5" transform="matrix(1,0,0,1,0,0)">
       <polyline points="0,50 100,50"/></g>
     <g fill="#0000ff" font-family="Sans Serif" font-size="9" font-weight="700"
        transform="matrix(0,1,-1,0,50,20)"><text x="0" y="7">10 µm</text></g>
     <g transform="matrix(1,0,0,1,100,0)"><image x="0" y="0" width="40" height="20"
        xlink:href="data:image/png;base64,{png}"/></g>
    </svg>""".encode("utf-8")
    sc = E.parse_svg(svg)
    assert sc["width"] == 200 and sc["height"] == 100
    path, line, text, img = sc["items"]
    assert path["fill"] == (255, 0, 0) and path["stroke"] is None
    assert path["subpaths"][0][0][2] == pytest.approx((30, 25))       # (10,10) scaled x2 + offset
    assert line["stroke"] == (0, 255, 0) and line["stroke_width"] == 1.5 and line["fill"] is None
    assert text["text"] == "10 µm" and text["bold"] and text["family"] == "Arial"
    assert text["rotation"] == pytest.approx(90)
    assert (text["x"], text["y"]) == pytest.approx((43, 20))          # (0,7) rotated + offset
    assert img["kind"] == "image" and (img["cx"], img["cy"], img["w"], img["h"]) == pytest.approx((120, 10, 40, 20))


def test_portable_family_maps_generic_and_clones_to_arial():
    for f in ("Sans Serif", "Helvetica", "TeX Gyre Heros", "'Arimo'", ""):
        assert E.portable_family(f) == "Arial"
    assert E.portable_family("Times New Roman") == "Times New Roman"


def test_assign_groups_puts_insets_in_their_panel():
    scene = {"items": [
        {"kind": "image", "png": b"", "cx": 50, "cy": 50, "w": 100, "h": 100, "rotation": 0, "opacity": 1},
        {"kind": "image", "png": b"", "cx": 80, "cy": 20, "w": 30, "h": 30, "rotation": 0, "opacity": 1},
        {"kind": "text", "text": "B", "x": 205, "y": 15, "size": 10, "family": "Arial",
         "bold": True, "italic": False, "color": (0, 0, 0), "rotation": 0},
        {"kind": "text", "text": "title", "x": 400, "y": 400, "size": 10, "family": "Arial",
         "bold": False, "italic": False, "color": (0, 0, 0), "rotation": 0}]}
    E.assign_groups(scene, [(0, 0, 100, 100), (65, 5, 30, 30), (200, 0, 100, 100)])
    assert [it["group"] for it in scene["items"]] == [0, 0, 2, None]


# ---------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------
def _scene():
    return {"width": 300.0, "height": 150.0, "panels": [(0, 0, 150, 150)], "items": [
        {"kind": "image", "png": _png(), "cx": 75, "cy": 75, "w": 150, "h": 150, "rotation": 0,
         "opacity": 1.0, "group": 0},
        {"kind": "path", "subpaths": [([(10, 140), (60, 140)], False)], "fill": None, "fill_opacity": 1,
         "stroke": (255, 255, 255), "stroke_opacity": 1, "stroke_width": 3, "group": 0},
        {"kind": "text", "text": "A", "x": 4, "y": 14, "size": 12, "family": "Arial", "bold": True,
         "italic": False, "color": (255, 255, 255), "rotation": 0, "group": 0},
        {"kind": "path", "subpaths": [([(200, 20), (280, 20), (280, 100), (200, 100), (200, 20)], False)],
         "fill": (58, 143, 199), "fill_opacity": 0.5, "stroke": None, "stroke_opacity": 1,
         "stroke_width": 1, "group": None},
        {"kind": "text", "text": "Control µ", "x": 200, "y": 130, "size": 9, "family": "Arial",
         "bold": False, "italic": True, "color": (0, 0, 0), "rotation": -90, "group": None}]}


def test_write_pptx_native_objects(tmp_path):
    from pptx import Presentation
    from pptx.util import Emu
    out = str(tmp_path / "f.pptx")
    E.write_pptx(_scene(), out)
    prs = Presentation(out)
    assert prs.slide_width == Emu(300 * E.EMU_PER_PT) and prs.slide_height == Emu(150 * E.EMU_PER_PT)
    shapes = list(prs.slides[0].shapes)
    group = next(s for s in shapes if s.shape_type == 6)               # MSO_SHAPE_TYPE.GROUP
    kinds = sorted(s.shape_type for s in group.shapes)
    assert group.name == "Panel 1" and len(kinds) == 3
    letter = next(s for s in group.shapes if s.shape_type == 17)        # TEXT_BOX
    run = letter.text_frame.paragraphs[0].runs[0]
    assert run.text == "A" and run.font.bold and run.font.name == "Arial"
    pic = next(s for s in group.shapes if s.shape_type == 13)          # PICTURE
    assert (pic.left, pic.top, pic.width) == (0, 0, Emu(150 * E.EMU_PER_PT))
    texts = [s for s in shapes if s.shape_type == 17]
    assert texts[0].text_frame.text == "Control µ" and texts[0].rotation == pytest.approx(270)
    box = next(s for s in shapes if s.shape_type == 5)                 # FREEFORM, filled
    assert box.fill.fore_color.rgb == pptx.dml.color.RGBColor(58, 143, 199)
    assert 'alpha val="50000"' in box._element.xml                     # 50 % transparency kept


def test_write_jsx_script_and_assets(tmp_path):
    out = str(tmp_path / "fig.jsx")
    jsx, assets = E.write_jsx(_scene(), out)
    raw = open(jsx, "rb").read()
    assert raw.startswith(b"\xef\xbb\xbf")                               # BOM: ExtendScript reads UTF-8
    s = raw.decode("utf-8-sig")
    assert "#target illustrator" in s and "fig_assets" in s
    assert os.listdir(assets) == ["img_000.png"]
    assert re.search(r'img\(grp, "img_000.png", 75\.0, 75\.0, 150\.0, 150\.0, 0, 1\.0\);', s)
    assert '"Control µ"' in s and '"Arial-ItalicMT"' in s and '"Arial-BoldMT"' in s
    assert "grp.name = 'Panel 1'" in s
    assert "shape(layer, [[[[200.0, -20.0]" in s                        # y flipped for Illustrator
    assert s.count("(") == s.count(")") and s.count("{") == s.count("}")


# ---------------------------------------------------------------------------
# CroppingPainter (Qt)
# ---------------------------------------------------------------------------
def _svg_images(svg_text):
    from PIL import Image
    out = []
    for m in re.finditer(r'base64,([^"]+)"', svg_text):
        out.append(Image.open(io.BytesIO(base64.b64decode(m.group(1)))).size)
    return out


def test_cropping_painter_honours_source_rects(qapp):
    from qtpy.QtCore import QBuffer, QByteArray, QIODevice, QRect, QRectF, QSize
    from qtpy.QtGui import QColor, QImage
    from qtpy.QtSvg import QSvgGenerator
    from pyfigures.gui.svg_painter import CroppingPainter
    img = QImage(100, 60, QImage.Format.Format_RGB32)
    img.fill(QColor(10, 20, 30))
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    gen = QSvgGenerator()
    gen.setOutputDevice(buf)
    gen.setSize(QSize(200, 200))
    p = CroppingPainter(gen)
    p.drawImage(QRectF(0, 0, 40, 20), img, QRectF(10, 5, 40, 20))     # cropped
    p.drawImage(QRectF(0, 50, 100, 60), img)                          # whole image
    p.drawImage(0, 120, img, 0, 0, 30, 30)                            # x, y, sx, sy, sw, sh
    p.end()
    assert _svg_images(bytes(data).decode("utf-8")) == [(40, 20), (100, 60), (30, 30)]


# ---------------------------------------------------------------------------
# end to end on a real figure: MCP tools, recipe, GUI
# ---------------------------------------------------------------------------
@pytest.fixture
def cropped_figure(tmp_path):
    import tifffile
    import pyfigures.mcp_server as M
    a = np.zeros((80, 120), np.uint8)
    a[:, 60:] = 200
    tif = str(tmp_path / "half.tif")
    tifffile.imwrite(tif, a)
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X")
    M.add_image(pyf, [0], tif)
    M.add_image(pyf, [0], tif)
    M.transform_image(pyf, [0], 1, crop_right=60)                      # second panel: dark half only
    M.add_annotation(pyf, [0], 0, "<b>A</b>", placement="top left")
    M.set_scale_bar_all(pyf, 10, px_to_unit=0.5)
    return pyf


def test_mcp_export_pptx_and_jsx(cropped_figure, tmp_path):
    import pyfigures.mcp_server as M
    from pptx import Presentation
    res = json.loads(M.export_pptx(cropped_figure, str(tmp_path / "out.pptx")))
    assert res["images"] == 2 and res["texts"] >= 3 and res["panel_groups"] == 2
    prs = Presentation(res["path"])
    texts = [s.text_frame.text for g in prs.slides[0].shapes if g.shape_type == 6
             for s in g.shapes if s.has_text_frame]
    assert "A" in texts and sum(t.replace(" ", "") == "10µm" for t in texts) == 2
    pics = [s for g in prs.slides[0].shapes if g.shape_type == 6 for s in g.shapes if s.shape_type == 13]
    from PIL import Image
    sizes = sorted(Image.open(io.BytesIO(p.image.blob)).size for p in pics)
    assert sizes == [(60, 80), (120, 80)]                              # the crop is kept

    jres = json.loads(M.export_illustrator_script(cropped_figure, str(tmp_path / "out.jsx")))
    assert os.path.isfile(jres["path"]) and len(os.listdir(jres["assets"])) == 2
    assert "Other Script" in jres["usage"]
    assert M.export_pptx(cropped_figure, str(tmp_path / "x.ppt")).startswith("ERROR")
    assert M.export_illustrator_script(str(tmp_path / "nope.pyf"), str(tmp_path / "x.jsx")).startswith("ERROR")


def _decode_mp4(data):
    av = pytest.importorskip("av")
    with av.open(io.BytesIO(data)) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


def test_movie_frames_to_mp4_enlarges_small_frames_sharply_and_evenly():
    frames = [np.full((5, 7, 3), 40 * i, np.uint8) for i in range(3)]
    out = _decode_mp4(E.movie_frames_to_mp4(frames, fps=5))
    # 7 px wide -> x74 (>= 512 px), then padded to even sizes
    assert len(out) == 3 and out[0].shape == (370, 518, 3)
    assert [int(round(f.mean())) for f in out] == pytest.approx([0, 40, 80], abs=3)


def test_movie_panels_play_in_powerpoint(tmp_path):
    """The editable PowerPoint showed a video panel as a still picture although
    PowerPoint plays mp4: it is now a movie (poster frame = the shown frame)."""
    import tifffile
    import pyfigures.mcp_server as M
    from pptx import Presentation
    t = np.zeros((6, 40, 60), np.uint8)
    for i in range(6):
        t[i, :, 10 * i:10 * i + 10] = 255                               # a stripe moving right
    movie = str(tmp_path / "movie.tif")
    tifffile.imwrite(movie, t, imagej=True, metadata={"axes": "TYX"})
    still = str(tmp_path / "still.tif")
    tifffile.imwrite(still, np.full((40, 60), 90, np.uint8))
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X")
    M.add_image(pyf, [0], still, label="A")
    M.add_image(pyf, [0], movie, label="B")
    M.transform_image(pyf, [0], 1, crop_right=20)                       # the movie keeps the crop

    res = json.loads(M.export_pptx(pyf, str(tmp_path / "out.pptx")))
    assert res["movies"] == 1 and res["images"] == 2 and res["panel_groups"] == 2
    prs = Presentation(res["path"])
    groups = [g for g in prs.slides[0].shapes if g.shape_type == 6]
    kinds = [sorted(s.shape_type for s in g.shapes) for g in groups]
    assert kinds == [[13, 17], [16, 17]]                                # picture / movie + its label
    mov = [s for s in groups[1].shapes if s.shape_type == 16][0]
    pic = [s for s in groups[0].shapes if s.shape_type == 13][0]
    assert mov.top == pic.top and mov.height == pic.height and mov.left > pic.left
    assert abs(mov.width / mov.height - 40 / 40) < 0.02                 # 40 x 40 after the crop
    video = [r.target_part for r in mov.part.rels.values() if r.reltype.endswith("/video")]
    assert len(video) == 1
    frames = _decode_mp4(video[0].blob)
    assert len(frames) == 6 and frames[0].shape[0] == frames[0].shape[1] >= 512
    scale = frames[0].shape[1] / 40
    lit = [np.where(f[..., 0].mean(0) > 128)[0] for f in frames]
    assert [int(round(c.min() / scale)) for c in lit[:4]] == [0, 10, 20, 30]
    assert len(lit[5]) == 0                                             # last stripe is cropped away
    xml = prs.slides[0]._element.xml
    assert "p:timing" in xml and "videoFile" in xml

    # Illustrator has no movies: the shown frame only
    jres = json.loads(M.export_illustrator_script(pyf, str(tmp_path / "out.jsx")))
    assert jres["movies"] == 0 and len(os.listdir(jres["assets"])) == 2


def test_labels_keep_the_size_they_have_in_the_other_exports(cropped_figure, tmp_path, qapp):
    """Labels and scale-bar text drawn by PyFigures came out at 72/96 of their
    size in PowerPoint / Illustrator (and so off-centre on the scale bar)."""
    import pyfigures.mcp_server as M
    from PIL import Image
    from pptx import Presentation
    png = str(tmp_path / "ref.png")
    json.loads(M.export_figure(cropped_figure, png, dpi=288))            # 4 px per point
    a = np.asarray(Image.open(png).convert("L"))
    h, w = a.shape
    corner = a[int(h * 0.8):, int(w * 0.8):] > 128        # the white "10 µm" + bar, bottom right
    widths = corner.sum(axis=1)
    bar_top = np.where(widths > widths.max() * 0.9)[0].min()
    cols = np.where(corner[:bar_top - 2].any(axis=0))[0]
    text_width_pt = (cols.max() - cols.min() + 1) / 4.0
    res = json.loads(M.export_pptx(cropped_figure, str(tmp_path / "out.pptx")))
    prs = Presentation(res["path"])
    sizes = [r.font.size.pt for g in prs.slides[0].shapes if g.shape_type == 6
             for s in g.shapes if s.has_text_frame and s.text_frame.text.replace(" ", "") == "10µm"
             for r in s.text_frame.paragraphs[0].runs]
    assert sizes
    # "10 µm" in Arial is 2.799 em wide
    assert abs(sizes[0] * 2.799 - text_width_pt) < 0.1 * text_width_pt, (sizes[0], text_width_pt)


def test_svg_export_keeps_crops(cropped_figure, tmp_path):
    """Regression: File > Export As > SVG embedded cropped panels uncropped,
    squeezed into the cropped box (Qt's SVG engine ignores source rects)."""
    import pyfigures.mcp_server as M
    out = str(tmp_path / "fig.svg")
    M.export_figure(cropped_figure, out)
    sizes = sorted(_svg_images(open(out, encoding="utf-8").read()))
    assert sizes == [(60, 80), (120, 80)]


def test_vector_exports_have_the_figure_true_size(cropped_figure, tmp_path):
    """Regression: PDF/SVG used a fixed A4 page at 96 dpi — figures came out at
    75 % of their size and anything beyond the page was cut off."""
    import pyfigures.mcp_server as M
    fitz = pytest.importorskip("fitz")
    M.resize_figure(cropped_figure, width_mm=300)
    pdf = str(tmp_path / "big.pdf")
    M.export_figure(cropped_figure, pdf)
    page = fitz.open(pdf)[0]
    assert page.rect.width / 72 * 25.4 == pytest.approx(300, abs=0.5)
    content = None
    for b in page.get_bboxlog():
        r = fitz.Rect(b[1])
        content = r if content is None else content | r
    assert content.width / 72 * 25.4 == pytest.approx(300, abs=0.5)      # not shrunk, not clipped
    assert content.y1 <= page.rect.y1 + 0.5
    svg = str(tmp_path / "big.svg")
    M.export_figure(cropped_figure, svg)
    head = open(svg, encoding="utf-8").read(600)
    width_mm = float(re.search(r'width="([\d.]+)mm"', head).group(1))
    assert width_mm == pytest.approx(300, abs=0.5)


def test_recipe_exports_pptx_and_illustrator(tmp_path):
    import tifffile
    from pyfigures.recipe import build_figure_from_recipe
    tif = str(tmp_path / "a.tif")
    tifffile.imwrite(tif, (np.arange(64 * 64).reshape(64, 64) % 255).astype(np.uint8))
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": "fig.pyf", "rows": [[{"image": "a.tif"}]],
                                  "exports": ["pptx", "illustrator"]}), encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert os.path.isfile(str(tmp_path / "fig.pptx")) and os.path.isfile(str(tmp_path / "fig.jsx"))
    assert os.path.isdir(str(tmp_path / "fig_assets"))


def test_gui_export_actions(qapp, tmp_path, monkeypatch, cropped_figure):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    import time
    msgs = []
    for kind in ("warning", "information"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(lambda *a, _k=kind, **k: msgs.append((_k, a[1])) or QMessageBox.Ok))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    g._start_pyf_loader([cropped_figure], append=False, reset_undo=True)
    t0 = time.time()
    while time.time() - t0 < 60:
        qapp.processEvents()
        if g.paint.EZFIG_panel.shapes_to_draw and not getattr(g, "_active_img_loaders", None):
            break
        time.sleep(0.01)
    try:
        out = str(tmp_path / "gui.pptx")
        monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
        g.export_as_pptx()
        assert os.path.isfile(out) and msgs[-1] == ("information", "PowerPoint exported")
        out2 = str(tmp_path / "gui.jsx")
        monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out2)
        g.export_as_illustrator()
        assert os.path.isfile(out2) and os.path.isdir(str(tmp_path / "gui_assets"))
        assert msgs[-1] == ("information", "Illustrator script exported")
        monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: None)
        n = len(msgs)
        g.export_as_pptx()                                             # cancel: nothing happens
        assert len(msgs) == n
        names = [a.text() for a in g.findChildren(pfgui.QAction)]
        assert "PowerPoint (editable)…" in names and "Adobe Illustrator script (.jsx)…" in names
        out3 = str(tmp_path / "gui.vectorcraft")
        monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out3)
        g.export_as_vectorcraft()
        assert os.path.isfile(out3) and msgs[-1] == ("information", "VectorCraft document exported")
        assert "VectorCraft (editable)…" in names or "VectorCraft (editable)…" in \
            [a.text() for a in g.findChildren(pfgui.QAction)]
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()


# ---------------------------------------------------------------------------
# VectorCraft (.vectorcraft native document)
# ---------------------------------------------------------------------------
def test_write_vectorcraft_native_document(tmp_path):
    out = str(tmp_path / "fig.vectorcraft")
    E.write_vectorcraft(_scene(), out)
    d = json.load(open(out, encoding="utf-8"))
    assert d["format"] == "vectorcraft" and d["version"] == 3       # images inline: every version reads it
    doc = d["document"]
    assert doc["units"] == "Points"
    assert doc["artboards"][0]["rect"] == {"x0": 0.0, "y0": 0.0, "x1": 300.0, "y1": 150.0}
    layer = doc["layers"][0]
    assert layer["name"] == "PyFigures" and layer["kind"]["type"] == "layer"
    group, box, label = layer["kind"]["children"]
    assert group["name"] == "Panel 1" and group["kind"]["clip"] is True
    clip, img, bar, letter = group["kind"]["children"]
    # the panel clips its content, as in the figure (a clip group's first child)
    assert clip["kind"]["clipping"] is True
    assert [a["p"] for a in clip["kind"]["path"]["subpaths"][0]["anchors"]] == \
        [[0, 0], [150, 0], [150, 150], [0, 150]]
    # the 8 x 4 px image stretched over 150 x 150 pt, embedded as base64 PNG
    ik = img["kind"]
    assert (ik["type"], ik["width"], ik["height"]) == ("image", 8, 4)
    assert ik["xf"] == [18.75, 0.0, -0.0, 37.5, 0.0, 0.0]
    assert base64.b64decode(d["images"][ik["key"]]["data"]) == _png()
    assert doc["images"][ik["key"]] == {"mime": "image/png"}
    assert bar["appearance"]["items"][1]["width"] == 3 and bar["kind"]["path"]["subpaths"][0]["closed"] is False
    run = letter["kind"]["runs"][0]
    assert run["text"] == "A" and run["style"]["font_style"] == "Bold" and run["style"]["size"] == 12
    assert letter["kind"]["xf"][4:] == [4, 14]
    # outside every panel: no group; transparency kept; rotated italic text
    assert box["opacity"] == 0.5 and box["appearance"]["items"][0]["paint"]["color"]["r"] == round(58 / 255, 6)
    assert label["kind"]["runs"][0]["style"]["font_style"] == "Italic"
    a, b, c, dd = label["kind"]["xf"][:4]
    assert (a, b, c, dd) == pytest.approx((0, -1, 1, 0), abs=1e-6)       # -90°
    ids = []

    def walk(n):
        ids.append(n["id"])
        for ch in n["kind"].get("children", []):
            walk(ch)
    walk(layer)
    assert len(ids) == len(set(ids)) and doc["next_id"] > max(ids)


def test_mcp_and_recipe_export_vectorcraft(cropped_figure, tmp_path):
    import pyfigures.mcp_server as M
    res = json.loads(M.export_vectorcraft(cropped_figure, str(tmp_path / "out.vectorcraft")))
    assert res["images"] == 2 and res["panel_groups"] == 2 and "File > Open" in res["usage"]
    d = json.load(open(res["path"], encoding="utf-8"))
    from PIL import Image
    sizes = sorted(Image.open(io.BytesIO(base64.b64decode(v["data"]))).size for v in d["images"].values())
    assert sizes == [(60, 80), (120, 80)]                              # the crop is kept
    assert M.export_vectorcraft(cropped_figure, str(tmp_path / "x.svg")).startswith("ERROR")
    import tifffile
    from pyfigures.recipe import build_figure_from_recipe
    tifffile.imwrite(str(tmp_path / "a.tif"), np.zeros((32, 32), np.uint8))
    (tmp_path / "r.json").write_text(json.dumps({"output": "r.pyf", "rows": [[{"image": "a.tif"}]],
                                                  "exports": ["vectorcraft"]}), encoding="utf-8")
    build_figure_from_recipe(str(tmp_path / "r.json"))
    assert os.path.isfile(str(tmp_path / "r.vectorcraft"))


def test_svg_labels_have_their_size_and_the_page_its_true_size(cropped_figure, tmp_path):
    """SVG text came out at 72/96 of its size in every SVG reader (VectorCraft
    showed it, browsers too): font sizes were converted at 72 dpi while every
    other export draws text at the image resolution."""
    import pyfigures.mcp_server as M
    from pptx import Presentation
    svg = str(tmp_path / "f.svg")
    M.export_figure(cropped_figure, svg)
    text = open(svg, encoding="utf-8").read()
    m = re.search(r'font-size="([\d.]+)"[^>]*>\s*10\s*µm<', text)
    res = json.loads(M.export_pptx(cropped_figure, str(tmp_path / "f.pptx")))
    prs = Presentation(res["path"])
    size = next(r.font.size.pt for g in prs.slides[0].shapes if g.shape_type == 6
                for s in g.shapes if s.has_text_frame and s.text_frame.text.replace(" ", "") == "10µm"
                for r in s.text_frame.paragraphs[0].runs)
    assert m and float(m.group(1)) == pytest.approx(size, abs=0.6), (m and m.group(1), size)
    w_mm = float(re.search(r'<svg[^>]*?width="([\d.]+)mm"', text).group(1))
    vb_w = float(re.search(r'viewBox="0 0 ([\d.]+)', text).group(1))
    assert w_mm == pytest.approx(vb_w / 72 * 25.4, abs=0.05)            # 1 unit = 1 point


def _vectorcraft_cli():
    import glob
    exe = os.environ.get("VECTORCRAFT_CLI")
    if exe and os.path.isfile(exe):
        return exe
    for pattern in (r"C:\Softwares\vectorcraft*\vectorcraft-cli.exe",
                    r"C:\Program Files\VectorCraft\vectorcraft-cli.exe", "/usr/bin/vectorcraft-cli"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[-1]
    return None


def test_vectorcraft_itself_opens_the_exports(cropped_figure, tmp_path):
    """With VectorCraft installed (or VECTORCRAFT_CLI set), its own reader opens
    the .vectorcraft and SVG exports without import warnings."""
    import subprocess
    exe = _vectorcraft_cli()
    if exe is None:
        pytest.skip("VectorCraft is not installed")
    import pyfigures.mcp_server as M
    vc = str(tmp_path / "f.vectorcraft")
    json.loads(M.export_vectorcraft(cropped_figure, vc))
    svg = str(tmp_path / "f.svg")
    M.export_figure(cropped_figure, svg)
    for path in (vc, svg):
        out = subprocess.run([exe, "info", path], capture_output=True, text=True, timeout=120,
                             encoding="utf-8")
        assert out.returncode == 0, out.stderr
        info = json.loads(out.stdout)
        assert info["warnings"] == [], info["warnings"]
    kinds = json.loads(subprocess.run([exe, "info", vc], capture_output=True, text=True,
                                      timeout=120, encoding="utf-8").stdout)["kinds"]
    assert kinds.get("Clip Group") == 2 and kinds.get("Image") == 2 and kinds.get("Type", 0) >= 3
    png = str(tmp_path / "vc.png")
    out = subprocess.run([exe, "convert", vc, png], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and os.path.getsize(png) > 1000, out.stderr
