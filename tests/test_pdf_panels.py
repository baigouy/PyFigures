"""PDF files as figure panels, kept as vectors.

A PDF (e.g. a Matplotlib/pgfplots/gnuplot plot) is converted to SVG with
PyMuPDF and drawn by batoolset's PdfSvgRenderer, because Qt's SVG renderer
ignores clip paths (a curve leaving its axes would be drawn over the figure)
and Qt's SVG writer drops clipping.

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


@pytest.fixture
def plot_pdf(tmp_path):
    """A 4x3 in plot whose orange curve leaves the top of its axes."""
    import matplotlib
    from matplotlib.backends.backend_pdf import FigureCanvasPdf
    from matplotlib.figure import Figure
    # default style: other code may have changed rcParams (e.g. savefig.bbox)
    with matplotlib.style.context("default"):
        fig = Figure(figsize=(4, 3))
        FigureCanvasPdf(fig)
        ax = fig.add_axes([0.1, 0.1, 0.8, 0.6])
        x = np.linspace(0, 10, 200)
        ax.plot(x, np.exp(x / 2), color="#ff7f0e", lw=3)
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 10)
        ax.set_xticks([])
        ax.set_yticks([])
        path = str(tmp_path / "plot.pdf")
        fig.savefig(path, bbox_inches=None)
    return path


def _orange_fraction(rgb):
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    return float(((r > 200) & (g > 90) & (g < 170) & (b < 80)).mean())


def _render(path, dpi=100):
    with fitz.open(path) as doc:
        pix = doc[0].get_pixmap(dpi=dpi, alpha=False)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)


def _figure(tmp_path, plot):
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], plot)
    return pyf


def _check_clipped(img):
    h, w = img.shape[:2]
    above = img[: int(0.28 * h) - 3]          # above the axes (axes top at 70 % height)
    inside = img[int(0.32 * h): int(0.88 * h), int(0.12 * w): int(0.88 * w)]
    assert _orange_fraction(inside) > 0.002   # the curve is drawn...
    assert _orange_fraction(above) == 0.0     # ...but not outside its axes


@pytest.mark.parametrize("ext", ["pdf", "svg", "png"])
def test_pdf_panel_is_clipped_in_every_export(qapp, tmp_path, plot_pdf, ext):
    from pyfigures.mcp_server import export_figure
    pyf = _figure(tmp_path, plot_pdf)
    out = str(tmp_path / f"out.{ext}")
    json.loads(export_figure(pyf, out, dpi=100))
    if ext == "png":
        from PIL import Image
        img = np.asarray(Image.open(out).convert("RGB"))
    else:
        img = _render(out)
    _check_clipped(img)


def test_pdf_panel_stays_vector(qapp, tmp_path, plot_pdf):
    from pyfigures.mcp_server import export_figure
    pyf = _figure(tmp_path, plot_pdf)
    out = str(tmp_path / "out.pdf")
    json.loads(export_figure(pyf, out))
    with fitz.open(out) as doc:
        page = doc[0]
        assert not page.get_images()
        assert page.get_drawings()
        # true size: the 4 x 3 in plot is a 288 x 216 pt page
        assert abs(page.rect.width - 288) < 2 and abs(page.rect.height - 216) < 2


def test_pdf_is_an_image_file_and_has_no_pixel_size(tmp_path, plot_pdf):
    from batoolset.img import is_image_file
    from batoolset.drawings.shapes.image2d import is_vector_file
    from pyfigures.mcp_tools.core import _raw_size_from_file
    assert is_image_file(plot_pdf) and is_vector_file(plot_pdf)
    assert _raw_size_from_file(plot_pdf) is None


def test_unreadable_pdf_is_not_set(qapp, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    im = Image2D(str(bad))
    assert im.isSet is False


def test_path_parser_handles_relative_and_shorthand_commands(qapp):
    from batoolset.drawings.pdf_svg_renderer import parse_path, parse_transform
    p = parse_path("M10 10 h20 v20 H10 Z m40 0 l10 0 c0 10 10 10 10 0 s10 -10 10 0")
    r = p.boundingRect()
    # 'Z' returns to (10,10), 'm40 0' starts at (50,10); the reflected 's'
    # control point (70,0) lifts the last curve to y = 2.5
    assert r.left() == pytest.approx(10) and r.top() == pytest.approx(2.5)
    assert r.right() == pytest.approx(80) and r.bottom() == pytest.approx(30)
    t = parse_transform("translate(5,0) matrix(2,0,0,2,1,1)")
    pt = t.map(r.bottomRight())
    assert (pt.x(), pt.y()) == pytest.approx((166, 61))


def test_unsupported_svg_falls_back_to_qt(qapp):
    from qtpy.QtSvg import QSvgRenderer
    from batoolset.drawings.pdf_svg_renderer import PdfSvgRenderer, make_pdf_svg_renderer
    plain = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><path d="M0 0H10"/></svg>'
    fancy = (b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><defs>'
             b'<linearGradient id="g"/></defs><path d="M0 0H10" fill="url(#g)"/></svg>')
    assert isinstance(make_pdf_svg_renderer(plain), PdfSvgRenderer)
    r = make_pdf_svg_renderer(fancy)
    assert isinstance(r, QSvgRenderer) and not isinstance(r, PdfSvgRenderer)
