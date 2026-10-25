"""Scale bars and calibration: a bar on an image with no pixel size was drawn
at 1 µm per pixel and labelled '10 µm' with no warning (user report,
error_scale_bars.pyf). Such a bar now says '10 px', the reply and QC say it
is not calibrated, and a typed pixel size can fill only the images that
have none instead of replacing the file's own.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def fig(tmp_path):
    """A row of a PNG (no pixel size) and an ImageJ TIFF at 0.25 µm/px."""
    import tifffile
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image
    d = str(tmp_path)
    png = os.path.join(d, "plain.png")
    Image.fromarray((np.random.default_rng(0).random((80, 100)) * 255).astype(np.uint8)).save(png)
    tif = os.path.join(d, "calibrated.tif")
    tifffile.imwrite(tif, (np.random.default_rng(1).random((80, 100)) * 255).astype(np.uint8),
                     imagej=True, resolution=(4.0, 4.0), metadata={"unit": "um"})
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], png)
    add_image(pyf, [0], tif)
    return pyf


def _legends(pyf):
    from pyfigures.mcp_tools.core import _load, _html_to_plain, _first_filename
    _t, root = _load(pyf)
    out = []
    for img in root.iter("Image2D"):
        sb = img.find("annotations/ScaleBar")
        if sb is not None:
            out.append((os.path.basename(str(_first_filename(img))),
                        _html_to_plain(sb.findtext("legend") or "").strip()))
    return out


def test_pixel_size_sources(fig):
    from pyfigures.mcp_tools.core import _load, _pixel_size, _set_child_text, _save
    tree, root = _load(fig)
    imgs = list(root.iter("Image2D"))
    assert _pixel_size(imgs[0]) == (None, "none")
    px, src = _pixel_size(imgs[1])
    assert src == "metadata" and abs(px - 0.25) < 1e-6
    _set_child_text(imgs[0], "px_to_unit_conversion_factor", "0.5")
    assert _pixel_size(imgs[0]) == (0.5, "figure")


def test_uncalibrated_bar_says_px(fig):
    from pyfigures.mcp_server import set_scale_bar_all
    r = set_scale_bar_all(fig, 10)
    assert "NOT CALIBRATED" in r and "plain.png" in r and "calibrated.tif" not in r.split("WARNING")[1]
    assert dict(_legends(fig)) == {"plain.png": "10 px", "calibrated.tif": "10 µm"}


def test_single_bar_says_px(fig):
    from pyfigures.mcp_server import set_scale_bar
    r = set_scale_bar(fig, [0], 0, 10)
    assert "NOT CALIBRATED" in r and dict(_legends(fig))["plain.png"] == "10 px"
    r = set_scale_bar(fig, [0], 1, 10)
    assert "NOT CALIBRATED" not in r and dict(_legends(fig))["calibrated.tif"] == "10 µm"


def test_typed_pixel_size_fills_only_missing(fig):
    from pyfigures.mcp_server import set_scale_bar_all
    from pyfigures.mcp_tools.core import _load
    r = set_scale_bar_all(fig, 10, px_to_unit=0.5, px_to_unit_scope="missing")
    assert "NOT CALIBRATED" not in r and "1 kept their own" in r
    _t, root = _load(fig)
    sizes = [float(i.findtext("px_to_unit_conversion_factor") or 0) for i in root.iter("Image2D")]
    assert sizes[0] == 0.5 and sizes[1] != 0.5          # the TIFF keeps its 0.25
    assert set_scale_bar_all(fig, 10, px_to_unit_scope="some").startswith("ERROR")


def test_audit_flags_uncalibrated_and_hand_set(fig):
    from pyfigures.mcp_server import audit_figure, set_scale_bar_all
    from pyfigures.gui.qc_reports import audit_report
    set_scale_bar_all(fig, 10)
    a = json.loads(audit_figure(fig))
    assert [os.path.basename(e["filename"]) for e in a["scale_bars_not_calibrated"]] == ["plain.png"]
    text = audit_report(audit_figure(fig))
    assert "NOT calibrated" in text and "plain.png" in text and "pixel size from the file" in text
    set_scale_bar_all(fig, 10, px_to_unit=0.5, px_to_unit_scope="missing")
    a = json.loads(audit_figure(fig))
    assert a["scale_bars_not_calibrated"] == [] and len(a["scale_bars_calibrated_by_hand"]) == 1
    assert "set in the figure" in audit_report(audit_figure(fig))


def test_gui_dialog_wording_and_scope(qapp):
    from qtpy.QtWidgets import QLabel
    from pyfigures.gui.pfgui import _ScaleBarAllDialog
    d = _ScaleBarAllDialog()
    labels = " ".join(w.text() for w in d.findChildren(QLabel))
    assert "pixels per unit" not in labels and "unit per pixel" in labels
    assert "px_to_unit" not in d.values()
    d.px_edit.setText("0.16")
    v = d.values()
    assert v["px_to_unit"] == 0.16 and v["px_to_unit_scope"] == "missing"     # the safe default


def test_editor_bar_on_uncalibrated_image_says_px(qapp):
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.gui.scalebareditor import ScaleBarEditor
    e = ScaleBarEditor(None, ScaleBar(bar_width_in_units=10, legend=TAText2D("")), calibrated=False)
    assert e.text_editor.associated_text.getPlainText().strip() == "10 px"
    e.size_spinner.setValue(25)
    assert e.getScaleBar().legend.getPlainText().strip() == "25 px"     # follows the size
    e = ScaleBarEditor(None, ScaleBar(bar_width_in_units=10, legend=TAText2D("")), calibrated=True)
    assert e.text_editor.associated_text.getPlainText().strip() == ""
