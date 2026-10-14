"""SVG clip paths (Qt ignores them; batoolset's ClippingSvgRenderer applies
them) in SVG files and Matplotlib panels, and multi-page PDFs as panels.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

fitz = pytest.importorskip("fitz")

CLIPPED = b'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100" viewBox="0 0 200 100">
  <defs><clipPath id="cA"><rect x="0" y="0" width="100" height="50"/></clipPath>
  <clipPath id="cB"><circle cx="150" cy="50" r="30"/></clipPath></defs>
  <rect x="0" y="0" width="200" height="100" fill="#ffffff"/>
  <g clip-path="url(#cA)"><circle cx="50" cy="50" r="45" fill="#ee3333"/></g>
  <g transform="translate(0,0)"><rect x="110" y="10" width="80" height="80" fill="#3333ee"
     style="clip-path:url(#cB)"/></g>
  <rect x="0" y="80" width="30" height="15" fill="#009900"/>
</svg>'''


def _rgb(img):
    return np.asarray(img.convert("RGB")).astype(int)


def _red(a):
    return (a[..., 0] > 200) & (a[..., 1] < 90) & (a[..., 2] < 90)


def _blue(a):
    return (a[..., 2] > 200) & (a[..., 0] < 90) & (a[..., 1] < 90)


def _check_clipped(a):
    h, w = a.shape[:2]
    assert _red(a[int(0.30 * h):int(0.45 * h), int(0.15 * w):int(0.35 * w)]).mean() > 0.9   # inside clip A
    assert not _red(a[int(0.55 * h):int(0.75 * h), :int(0.5 * w)]).any()                    # below clip A
    assert _blue(a[int(0.45 * h):int(0.55 * h), int(0.70 * w):int(0.80 * w)]).mean() > 0.9  # circle centre
    assert not _blue(a[int(0.12 * h):int(0.20 * h), int(0.57 * w):int(0.62 * w)]).any()     # square corner


def test_renderer_matches_qt_without_clips_and_clips(qapp):
    from qtpy.QtCore import QByteArray
    from qtpy.QtSvg import QSvgRenderer
    from batoolset.drawings.svg_clip_renderer import ClippingSvgRenderer, make_svg_renderer
    plain = CLIPPED.replace(b' clip-path="url(#cA)"', b"").replace(b'\n     style="clip-path:url(#cB)"', b"")
    assert type(make_svg_renderer(plain)) is QSvgRenderer                   # no clip: plain Qt
    assert isinstance(make_svg_renderer(CLIPPED), ClippingSvgRenderer)
    a_qt = _qimage_array(QSvgRenderer(QByteArray(plain)))
    a_me = _qimage_array(ClippingSvgRenderer(plain))
    assert np.abs(a_qt - a_me).max() == 0                                   # same drawing, element by element
    _check_clipped(_qimage_array(ClippingSvgRenderer(CLIPPED)))


def _qimage_array(renderer, w=400, h=200):
    from qtpy.QtCore import QRectF
    from qtpy.QtGui import QImage, QPainter, QColor
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor("white"))
    p = QPainter(img)
    renderer.render(p, QRectF(0, 0, w, h))
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(h, img.bytesPerLine())[:, :w * 3].reshape(h, w, 3).astype(int)


@pytest.mark.parametrize("ext", ["pdf", "svg", "png"])
def test_clipped_svg_panel_in_every_export(qapp, tmp_path, ext):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, export_figure
    src = tmp_path / "drawing.svg"
    src.write_bytes(CLIPPED)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], str(src))
    out = str(tmp_path / f"o.{ext}")
    json.loads(export_figure(pyf, out, dpi=100))
    if ext == "png":
        a = _rgb(Image.open(out))
    else:
        with fitz.open(out) as doc:
            pix = doc[0].get_pixmap(dpi=100, alpha=False)
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(int)
        if ext == "pdf":
            with fitz.open(out) as doc:
                assert not doc[0].get_images()                               # all vector in PDF
    _check_clipped(a)


def test_matplotlib_panel_curves_stay_inside_their_axes(qapp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.svg_clip_renderer import ClippingSvgRenderer
    with matplotlib.style.context("default"):
        fig = plt.figure(figsize=(4, 3))
        ax = fig.add_axes([0.1, 0.1, 0.8, 0.6])
        x = np.linspace(0, 10, 100)
        ax.plot(x, np.exp(x / 2), color="#ff0000", lw=4)
        ax.set_ylim(0, 10)
        ax.set_xticks([])
        ax.set_yticks([])
    im = Image2D()
    im.setFigure(fig)
    assert isinstance(im.renderer, ClippingSvgRenderer)
    # the axes = Matplotlib's clip rectangle, drawn at 2x the SVG's own size
    import re
    svg = im._toBuffer(bufferType="svg").read().decode()
    x, y, w, h = (float(v) for v in re.search(
        r'<clipPath[^>]*>\s*<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"', svg).groups())
    vb = im.renderer.viewBoxF()
    a = _qimage_array(im.renderer, int(vb.width() * 2), int(vb.height() * 2))
    top = int(y * 2)
    assert _red(a[top + 4:int((y + h) * 2)]).any()                          # the curve, in the axes
    assert not _red(a[:top - 2]).any()                                       # nothing above them
    plt.close(fig)


@pytest.fixture
def three_pages(tmp_path):
    path = str(tmp_path / "pages.pdf")
    doc = fitz.open()
    for k, color in enumerate([(1, 0, 0), (0, 0.6, 0), (0, 0, 1)]):
        page = doc.new_page(width=200, height=100 + 50 * k)          # each page its own size
        page.draw_rect(fitz.Rect(10, 10, 190, 90 + 50 * k), color=color, fill=color)
    doc.save(path)
    doc.close()
    return path


def _panel_colour(pyf, tmp_path, name):
    from PIL import Image
    from pyfigures.mcp_server import export_figure
    out = str(tmp_path / f"{name}.png")
    json.loads(export_figure(pyf, out, dpi=72))
    a = _rgb(Image.open(out))
    return a[a.shape[0] // 2, a.shape[1] // 2]


def test_pdf_pages_as_series(qapp, tmp_path, three_pages):
    from batoolset.img import get_series_info
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.mcp_server import create_figure, add_image
    assert get_series_info(three_pages) == (3, ["Page 1", "Page 2", "Page 3"])
    im = Image2D(three_pages, serie_to_open=2)
    assert im.renderer.defaultSize().height() == 200                        # page 3's own size
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    assert "page 2" in add_image(pyf, [], three_pages, page=2)
    assert tuple(_panel_colour(pyf, tmp_path, "p2")) == (0, 153, 0)
    assert add_image(pyf, [], three_pages, page=4).startswith("ERROR: page must be between 1 and 3")
    assert add_image(pyf, [], str(tmp_path / "x.svg"), page=1).startswith("ERROR: page applies to PDF")


def test_pdf_pages_without_pymupdf_use_pypdfium2(qapp, tmp_path, three_pages, monkeypatch):
    # the standalone apps have no PyMuPDF (AGPL): pages are rendered as images
    pytest.importorskip("pypdfium2")
    import sys
    from batoolset.img import get_series_info
    from batoolset.drawings.shapes.image2d import Image2D, pdf_to_svg_bytes
    from pyfigures.mcp_server import create_figure, add_image, export_figure
    monkeypatch.setitem(sys.modules, "fitz", None)                  # import fitz -> ImportError
    assert get_series_info(three_pages) == (3, ["Page 1", "Page 2", "Page 3"])
    assert b"<image" in pdf_to_svg_bytes(three_pages, page=1)
    im = Image2D(three_pages, serie_to_open=2)
    assert im.renderer.defaultSize().height() == 200                        # page 3's own size, in points
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    assert "page 2" in add_image(pyf, [], three_pages, page=2)
    assert add_image(pyf, [], three_pages, page=4).startswith("ERROR: page must be between 1 and 3")
    # drawn into a PDF, the page is one image at 600 dpi, not at screen resolution
    from qtpy.QtCore import QRectF, QSizeF
    from qtpy.QtGui import QPainter, QPdfWriter, QPageSize
    out = str(tmp_path / "o.pdf")
    writer = QPdfWriter(out)
    writer.setPageSize(QPageSize(QSizeF(200, 200), QPageSize.Unit.Point))
    p = QPainter(writer)
    im.renderer.render(p, QRectF(0, 0, 200, 200))
    p.end()
    monkeypatch.delitem(sys.modules, "fitz")
    with fitz.open(out) as doc:
        (xref, *_), = doc[0].get_images()
        assert doc.extract_image(xref)["width"] >= 200 * 600 / 72 - 1


def test_recipe_page(qapp, tmp_path, three_pages):
    from pyfigures.recipe import build_figure_from_recipe
    out = str(tmp_path / "r.pyf")
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"output": out, "rows": [[{"image": three_pages, "page": 3}]]}),
                    encoding="utf-8")
    build_figure_from_recipe(str(path))
    assert tuple(_panel_colour(out, tmp_path, "r")) == (0, 0, 255)


def test_gui_drop_asks_for_the_page(qapp, tmp_path, three_pages, monkeypatch):
    import time
    from batoolset.lists.tools import flatten_iterable
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    asked = []
    monkeypatch.setattr(g, "_show_series_dialog", lambda f, names: asked.append(names) or 1)
    try:
        g.add_images_to_new_row(g._resolve_series_for_files([three_pages]))
        t0 = time.time()
        while time.time() - t0 < 20 and not g.paint.EZFIG_panel.shapes_to_draw:
            qapp.processEvents()
            time.sleep(0.01)
        assert asked == [["Page 1", "Page 2", "Page 3"]]
        (im,) = [s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert im.serie_to_open == 1 and im.renderer is not None and im.img is im.renderer
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
