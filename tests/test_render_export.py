"""
Tests for the figure-rendering tools of the PyFigures MCP server:
export_figure (writes a final image file) and render_preview (returns a PNG
image object). Both render through the same off-screen Qt path as the GUI, in
a subprocess, so these are skipped if Qt cannot be imported here.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

# Rendering needs Qt (offscreen). Skip the whole module if it isn't available.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")
try:
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication  # noqa: F401
    _QT = True
except Exception:
    _QT = False

pytestmark = pytest.mark.skipif(not _QT, reason="Qt not available for rendering")

from pyfigures.mcp_server import (
    create_figure, add_image, export_figure, render_preview,
    export_latex, set_figure_caption,
)


def _tif(path, val, size=24):
    from batoolset.img import Img
    Img(np.full((size, size), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


@pytest.fixture
def real_figure(tmp_path):
    """A 2-panel canvas figure backed by real on-disk images."""
    a = _tif(str(tmp_path / "a.tif"), 60)
    b = _tif(str(tmp_path / "b.tif"), 200)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="canvas")
    add_image(p, [], a, label="A")
    add_image(p, [], b, label="B")
    return p


def _png_ok(path):
    with open(path, "rb") as f:
        return f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_export_png(real_figure, tmp_path):
    out = str(tmp_path / "out.png")
    r = json.loads(export_figure(real_figure, out, dpi=150))
    assert r["output"] == os.path.abspath(out)
    assert r["format"] == "png" and r["dpi"] == 150
    assert os.path.getsize(out) > 0 and _png_ok(out)


@pytest.mark.parametrize("ext", ["tif", "jpg", "svg", "pdf"])
def test_export_other_formats(real_figure, tmp_path, ext):
    out = str(tmp_path / f"out.{ext}")
    r = json.loads(export_figure(real_figure, out, dpi=120))
    assert r["format"] == ext
    # vector formats report no dpi
    assert (r["dpi"] is None) == (ext in {"svg", "pdf"})
    assert os.path.getsize(out) > 0


def test_export_bad_extension(real_figure, tmp_path):
    r = export_figure(real_figure, str(tmp_path / "out.bmp"))
    assert r.startswith("ERROR") and "unsupported" in r


def test_export_missing_pyf(tmp_path):
    r = export_figure(str(tmp_path / "nope.pyf"), str(tmp_path / "o.png"))
    assert r.startswith("ERROR") and "no such" in r


def test_render_preview_returns_png_image(real_figure):
    img = render_preview(real_figure, dpi=80, max_dimension=600)
    assert img._format == "png"
    assert img.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_preview_is_downscaled(real_figure):
    from PIL import Image as PILImage
    import io as _io
    img = render_preview(real_figure, dpi=300, max_dimension=500)
    im = PILImage.open(_io.BytesIO(img.data))
    assert max(im.size) <= 500


def test_render_preview_missing_pyf(tmp_path):
    with pytest.raises(ValueError):
        render_preview(str(tmp_path / "nope.pyf"))


# --- PDF + LaTeX export, incl. optional caption float ---

def test_export_latex_plain_no_float(real_figure, tmp_path):
    """Without a caption the overlay is a bare picture group (no figure float)."""
    out = str(tmp_path / "plain.pdf")
    r = json.loads(export_latex(real_figure, out, with_caption=False))
    assert r["caption_embedded"] is False
    tex = open(r["latex_overlay"], encoding="utf-8").read()
    assert r"\begin{picture}" in tex
    assert r"\begin{figure}" not in tex
    assert r"\caption{" not in tex


def test_export_latex_with_caption_float(real_figure, tmp_path):
    """with_caption wraps the picture in a figure float carrying \\caption,
    with the title in bold and LaTeX specials in the caption escaped."""
    set_figure_caption(real_figure, "Cells at 63x; 100% confluent.", title="Figure 1")
    out = str(tmp_path / "cap.pdf")
    r = json.loads(export_latex(real_figure, out, with_caption=True))
    assert r["caption_embedded"] is True
    tex = open(r["latex_overlay"], encoding="utf-8").read()
    assert r"\begin{figure}" in tex and r"\end{figure}" in tex
    assert r"\caption{" in tex
    assert r"\textbf{Figure 1}" in tex          # title bolded
    assert r"100\%" in tex                       # % escaped
    assert r"\begin{picture}" in tex             # graphics group still present


def test_export_latex_with_caption_but_none_set(real_figure, tmp_path):
    """with_caption=True but no caption stored → plain overlay + a note."""
    out = str(tmp_path / "nocap.pdf")
    r = json.loads(export_latex(real_figure, out, with_caption=True))
    assert r["caption_embedded"] is False
    assert "note" in r
    tex = open(r["latex_overlay"], encoding="utf-8").read()
    assert r"\begin{figure}" not in tex
