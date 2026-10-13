"""Poster designer: a .pyf figure placed on a poster is exported as vectors.

On screen the figure is a PNG flatten; in a PDF/SVG export it is drawn from
the figure itself, so its text and drawings stay vectors (text as outlines)
and its images keep their native resolution. Also: cropped photos keep their crop in the poster's SVG export
(Qt's SVG engine ignores drawPixmap source rects).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import base64
import io
import os
import re

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _noise_png(path, w, h, seed):
    from PIL import Image
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(0, 255, (h, w, 3), dtype=np.uint8)).save(path)
    return str(path)


def _svg_image_sizes(svg_text):
    from PIL import Image
    sizes = []
    for b64 in re.findall(r'data:image/[a-z]+;base64,([A-Za-z0-9+/=\s]+)', svg_text):
        im = Image.open(io.BytesIO(base64.b64decode(re.sub(r'\s', '', b64))))
        sizes.append(im.size)
    return sizes


@pytest.fixture
def poster_with_figure(qapp, tmp_path):
    from pyfigures import mcp_server as M
    from pyfigures.poster.poster_canvas import PosterCanvas, _render_pyf_subprocess
    a = _noise_png(tmp_path / "a.png", 400, 300, 1)
    b = _noise_png(tmp_path / "b.png", 300, 300, 2)
    pyf = str(tmp_path / "Figure1.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    M.add_image(pyf, [0], a, label="A")
    M.add_image(pyf, [0], b, label="B")
    flat = str(tmp_path / "flat.png")
    _render_pyf_subprocess(pyf, flat, 72)
    canvas = PosterCanvas()
    shape = canvas.add_image(flat, x_mm=20, y_mm=20, width_mm=120)
    shape.source_pyf = pyf
    return canvas, shape


def test_pdf_export_draws_the_figure_as_vectors(poster_with_figure, tmp_path):
    import fitz
    canvas, shape = poster_with_figure
    out = str(tmp_path / "poster.pdf")
    canvas.save(out, filetype="pdf", dpi=150)
    assert shape._vector is None                         # only set during the export
    with fitz.open(out) as doc:
        page = doc[0]
        sizes = {(i[2], i[3]) for i in page.get_images(full=True)}
        black = [d for d in page.get_drawings() if d.get("fill") == (0.0, 0.0, 0.0)]
    assert (400, 300) in sizes and (300, 300) in sizes   # native image resolution
    assert len(sizes) == 2                               # no flatten underneath
    # the letters A and B are drawn as vector outlines, inside the figure
    assert len(black) >= 2
    mm = 72 / 25.4
    xs = [(round(d["rect"].x0 / mm, 1), round(d["rect"].x1 / mm, 1)) for d in black]
    assert all(19 <= x0 and x1 <= 141 for x0, x1 in xs), xs


def test_poster_pdf_page_has_no_margin_shift(qapp, tmp_path):
    """Qt's default PDF margins shifted the poster by ~3.5 mm and clipped its
    right and bottom edges."""
    import fitz
    from pyfigures.poster.poster_canvas import PosterCanvas
    canvas = PosterCanvas()
    canvas.add_image(_noise_png(tmp_path / "p.png", 100, 100, 4), x_mm=0, y_mm=0, width_mm=30)
    for name, export in (("one.pdf", lambda o: canvas.save(o, filetype="pdf", dpi=100)),
                         ("album.pdf", lambda o: canvas.export_album_pdf(o, dpi=100))):
        out = str(tmp_path / name)
        export(out)
        with fitz.open(out) as doc:
            page = doc[0]
            info = page.get_image_info()
            assert abs(info[0]["bbox"][0]) < 0.5 and abs(info[0]["bbox"][1]) < 0.5, name
            border = max(page.get_drawings(), key=lambda d: d["rect"].width)
            assert border["rect"].x1 <= page.rect.x1 + 0.5, name


def test_svg_export_draws_the_figure_as_vectors(poster_with_figure, tmp_path):
    canvas, shape = poster_with_figure
    out = str(tmp_path / "poster.svg")
    canvas.save(out, filetype="svg", dpi=150)
    with open(out, encoding="utf-8") as f:
        svg = f.read()
    sizes = _svg_image_sizes(svg)
    assert (400, 300) in sizes and (300, 300) in sizes and len(sizes) == 2


def test_cropped_figure_is_clipped_in_pdf(poster_with_figure, tmp_path):
    """Cropping the right half away leaves only image A visible."""
    import fitz
    canvas, shape = poster_with_figure
    shape.crop_right = 0.5
    shape.width_mm = 60
    out = str(tmp_path / "crop.pdf")
    canvas.save(out, filetype="pdf", dpi=150)
    with fitz.open(out) as doc:
        pix = doc[0].get_pixmap(dpi=72)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
    mm = 72 / 25.4
    # right of the visible part (x > 20 + 60 mm) the page is blank
    right = img[int(25 * mm):int(40 * mm), int(85 * mm):int(140 * mm), :3]
    assert right.min() >= 250
    inside = img[int(25 * mm):int(40 * mm), int(25 * mm):int(75 * mm), :3]
    assert inside.std() > 15                               # the noise image is there


def test_failed_figure_render_keeps_the_flatten(poster_with_figure, tmp_path):
    import fitz
    canvas, shape = poster_with_figure
    shape.source_pyf = str(tmp_path / "gone.pyf")             # missing: skipped
    out = str(tmp_path / "flat.pdf")
    canvas.save(out, filetype="pdf", dpi=150)
    with fitz.open(out) as doc:
        assert len(doc[0].get_images()) == 1                  # the PNG flatten


def test_album_pdf_and_print_ready_svg_use_vectors(poster_with_figure, tmp_path):
    import fitz
    canvas, shape = poster_with_figure
    out = str(tmp_path / "album.pdf")
    canvas.export_album_pdf(out, dpi=150)
    with fitz.open(out) as doc:
        assert {(i[2], i[3]) for i in doc[0].get_images(full=True)} == {(400, 300), (300, 300)}
    out = str(tmp_path / "pr.svg")
    canvas.export_print_ready(out, filetype="svg", dpi=150)
    with open(out, encoding="utf-8") as f:
        assert (400, 300) in _svg_image_sizes(f.read())


def test_cropped_photo_keeps_its_crop_in_svg(qapp, tmp_path):
    from pyfigures.poster.poster_canvas import PosterCanvas
    photo = _noise_png(tmp_path / "p.png", 200, 100, 3)
    canvas = PosterCanvas()
    s = canvas.add_image(photo, x_mm=10, y_mm=10, width_mm=50)
    s.crop_left = 0.5
    out = str(tmp_path / "c.svg")
    canvas.save(out, filetype="svg", dpi=100)
    with open(out, encoding="utf-8") as f:
        assert _svg_image_sizes(f.read()) == [(100, 100)]
