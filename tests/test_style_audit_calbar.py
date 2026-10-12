"""
Tests for three PyFigures MCP tools:
  * audit_figure           - figure-wide scale-bar / label inventory (pure XML)
  * style_annotation       - rich-text-preserving font styling (needs Qt)
  * add_lut_calibration_bar - LUT intensity colour bar as a scripted panel
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")
try:
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication  # noqa: F401
    _QT = True
except Exception:
    _QT = False

from pyfigures.mcp_server import (
    create_figure, add_image, add_annotation, set_scale_bar,
    audit_figure, style_annotation, add_lut_calibration_bar,
    _load, _decode, _html_to_plain,
)

needs_qt = pytest.mark.skipif(not _QT, reason="Qt not available")


def _tif(path, val):
    from batoolset.img import Img
    Img(np.full((16, 16), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


# ---------------------------------------------------------------- audit
@pytest.fixture
def audited(tmp_path):
    a = _tif(str(tmp_path / "a.tif"), 60)
    b = _tif(str(tmp_path / "b.tif"), 200)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(p, [0], a, label="A")            # panel 0: label + bar
    add_image(p, [0], b)                        # panel 1: nothing
    set_scale_bar(p, [0], 0, 10.0, unit="um")
    return p


def test_audit_counts_and_missing(audited):
    r = json.loads(audit_figure(audited))
    assert r["n_panels"] == 2
    assert r["n_with_scale_bar"] == 1
    assert r["n_with_label"] == 1
    assert [x["image_index"] for x in r["panels_missing_scale_bar"]] == [1]
    assert [x["image_index"] for x in r["panels_missing_label"]] == [1]


def test_audit_reports_label_text(audited):
    r = json.loads(audit_figure(audited))
    p0 = next(p for p in r["panels"] if p["image_index"] == 0)
    assert "A" in p0["labels"] and p0["scale_bar"] is True


# ---------------------------------------------------------- style_annotation
@needs_qt
def test_style_preserves_bold_while_setting_size(tmp_path):
    a = _tif(str(tmp_path / "a.tif"), 60)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(p, [0], a, label="<b>A</b>")
    r = json.loads(style_annotation(p, [0], 0, 0, font_size=18, font_family="Arial"))
    assert r["applied"]["font_size"] == 18
    _, root = _load(p)
    img0 = next(root.iter("Image2D"))
    html = _decode(img0.find("annotations").find("TAText2D").findtext("text"))
    assert "18pt" in html and "Arial" in html
    assert "font-weight" in html          # the bold from <b>A</b> survived
    assert _html_to_plain(html).strip() == "A"


@needs_qt
def test_style_color_override(tmp_path):
    a = _tif(str(tmp_path / "a.tif"), 60)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="canvas")
    add_image(p, [], a, label="lbl")
    style_annotation(p, [], 0, 0, color="#ff0000")
    _, root = _load(p)
    img0 = next(root.iter("Image2D"))
    html = _decode(img0.find("annotations").find("TAText2D").findtext("text"))
    assert "#ff0000" in html.lower()


def test_style_noop_is_rejected(tmp_path):
    a = _tif(str(tmp_path / "a.tif"), 60)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="canvas")
    add_image(p, [], a, label="x")
    r = style_annotation(p, [], 0, 0)
    assert r.startswith("ERROR") and "nothing to change" in r


def test_style_bad_annotation_index(tmp_path):
    a = _tif(str(tmp_path / "a.tif"), 60)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="canvas")
    add_image(p, [], a)                    # no annotations
    r = style_annotation(p, [], 0, 0, bold=True)
    assert r.startswith("ERROR") and "out of range" in r


# ------------------------------------------------------ calibration bar
def test_calbar_adds_panel(tmp_path):
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    r = add_lut_calibration_bar(p, [0], lut="AFM_HOT", vmin=0, vmax=255,
                                label="Intensity (a.u.)", ticks=[0, 128, 255])
    assert "index" in r
    _, root = _load(p)
    # a scripted Image2D panel now exists carrying our colourbar script
    scripts = [_decode(img.findtext("custom_loading_script")) or ""
               for img in root.iter("Image2D")]
    assert any("ColorbarBase" in s for s in scripts)


def test_calbar_bad_orientation(tmp_path):
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    r = add_lut_calibration_bar(p, [0], lut="GRAY", orientation="diagonal")
    assert r.startswith("ERROR") and "orientation" in r


def test_calbar_tick_label_mismatch(tmp_path):
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    r = add_lut_calibration_bar(p, [0], lut="GRAY", ticks=[0, 255],
                                tick_labels=["only-one"])
    assert r.startswith("ERROR") and "same length" in r


@needs_qt
def test_calbar_renders_in_color(tmp_path):
    from pyfigures.gui.render_headless import render_pyf
    from PIL import Image as PILImage
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_lut_calibration_bar(p, [0], lut="AFM_HOT", vmin=0, vmax=255)
    out = str(tmp_path / "bar.png")
    render_pyf(p, out, dpi=120)
    im = np.asarray(PILImage.open(out).convert("RGB"))
    # AFM_HOT is not grayscale: some pixels must have unequal R/G/B
    diff = np.abs(im[..., 0].astype(int) - im[..., 2].astype(int))
    assert diff.max() > 30
