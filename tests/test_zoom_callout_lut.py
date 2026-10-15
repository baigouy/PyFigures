"""A zoom callout's magnified inset is shown like its parent panel.

The inset used to copy only the file and the crop, so on a panel with a colour
LUT (e.g. magenta nuclei) the magnified region was grey. It now copies the
parent's display settings and keeps following them (follow_parent_display), also
when the parent's LUT is changed afterwards.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _figure(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, set_lut, add_zoom_callout
    img = np.zeros((100, 100), np.uint8)
    img[40:60, 40:60] = 255
    Image.fromarray(img).save(tmp_path / "a.png")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], str(tmp_path / "a.png"))
    set_lut(pyf, [0], 0, ["MAGENTA"])
    add_zoom_callout(pyf, [0], 0, 40, 40, 20, 20, 100, 100, inset_corner="top right",
                     inset_fraction=0.4)
    return pyf


def _inset_colour(pyf, tmp_path, name):
    """Mean RGB of the bright pixels of the top-right inset in a render."""
    from PIL import Image
    from pyfigures.mcp_server import export_figure
    png = str(tmp_path / f"{name}.png")
    json.loads(export_figure(pyf, png, dpi=72))
    a = np.asarray(Image.open(png).convert("RGB")).astype(int)
    h, w, _ = a.shape
    ins = a[2:int(h * 0.38), int(w * 0.62):w - 2]
    bright = ins.max(2) > 150
    assert bright.any()
    return ins[bright].mean(0)


def test_inset_copies_parent_display(qapp, tmp_path):
    pyf = _figure(tmp_path)
    root = ET.parse(pyf).getroot()
    inset = [im for im in root.iter("Image2D") if im.findtext("follow_parent_display") == "True"]
    assert len(inset) == 1
    assert "MAGENTA" in inset[0].findtext("LUTs")


def test_inset_rendered_in_parent_lut(qapp, tmp_path):
    r, g, b = _inset_colour(_figure(tmp_path), tmp_path, "magenta")
    assert r > 150 and b > 150 and g < 60


def test_inset_follows_later_lut_change(qapp, tmp_path):
    from pyfigures.mcp_server import set_lut
    pyf = _figure(tmp_path)
    set_lut(pyf, [0], 0, ["GREEN"])          # changes the parent only
    r, g, b = _inset_colour(pyf, tmp_path, "green")
    assert g > 150 and r < 60 and b < 60


def test_plain_inset_keeps_its_own_display(qapp, tmp_path):
    """An ordinary inset (another picture) does not take the parent's LUT."""
    from batoolset.drawings.shapes.image2d import Image2D
    parent = Image2D(filename=None)
    parent.LUTs = ["MAGENTA"]
    inset = Image2D(filename=None)
    assert not inset._sync_display_from_parent(parent) and inset.LUTs is None
    inset.follow_parent_display = True
    assert inset._sync_display_from_parent(parent) and inset.LUTs == ["MAGENTA"]
    assert not inset._sync_display_from_parent(parent)   # nothing left to change
