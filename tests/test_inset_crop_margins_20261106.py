"""User report 2026-11-06 ("there is no inset"): the chat set an inset's
crop_right=375 / crop_bottom=307 meaning "up to x 375 / y 307" next to
crop_left=275 / crop_top=207 on a 650 x 514 px image. Crops are margins cut
from each edge, so the inset kept 0 px and vanished; set_inset_property
accepted it. It now refuses a crop that removes the whole image (or leaves a
sliver), as set_image_property already did, and says what to do."""
from __future__ import annotations

import json
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _figure(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, add_inset
    img = tmp_path / "big.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (514, 650), dtype=np.uint8)).save(img)
    pyf = str(tmp_path / "fig.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], str(img))
    add_inset(pyf, [0], 0, str(img))
    return pyf


def _crops(pyf):
    from pyfigures.mcp_server import list_insets
    inset = json.loads(list_insets(pyf, [0], 0))[0]
    return {k: inset[f"crop_{k}"] for k in ("left", "right", "top", "bottom")}


def test_coordinates_given_as_crops_are_refused(tmp_path):
    from pyfigures.mcp_server import set_inset_property
    pyf = _figure(tmp_path)
    assert "read back" in set_inset_property(pyf, [0], 0, 0, "crop_left", 275)
    out = set_inset_property(pyf, [0], 0, 0, "crop_right", 375)
    assert out.startswith("ERROR") and "not x1/y1/x2/y2 coordinates" in out and "Nothing was changed" in out
    assert "crop_right=275" in out              # keep x 275 to 375 of 650 px: right margin 275
    assert _crops(pyf)["right"] == 0            # the file kept the inset visible


def test_margins_are_accepted(tmp_path):
    from pyfigures.mcp_server import set_inset_property
    pyf = _figure(tmp_path)
    for name, v in (("crop_left", 275), ("crop_right", 275), ("crop_top", 207), ("crop_bottom", 207)):
        assert "read back" in set_inset_property(pyf, [0], 0, 0, name, v)
    assert _crops(pyf) == {"left": 275, "right": 275, "top": 207, "bottom": 207}
