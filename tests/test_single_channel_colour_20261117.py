"""One channel of a multi-channel file, shown alone, keeps the file's colour.

Chat log 2026-11-17 (2chZT.lsm, red + green): "only keep the first channel
active in a" hid channel 2 and the panel turned GRAY; "keep its original
color" then called set_lut(["NONE"]) on a panel that had no LUT, got "LUTs
removed (the image's own colours)" and the model told the user the channel was
red again, which it never was ("channel was not red when I asked").

Two fixes: Image2D draws a lone channel with the file's own LUT (as the merge
does), and set_lut says NO CHANGE when there was no LUT to remove.
"""
from __future__ import annotations

import numpy as np
import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _lut(r, g, b):
    ramp = np.arange(256, dtype=np.uint8)
    return np.stack([ramp * r, ramp * g, ramp * b]).astype(np.uint8)


@pytest.fixture
def red_green_tif(tmp_path):
    import tifffile
    a = np.zeros((2, 40, 60), np.uint8)
    a[0, 10:30, 10:50] = 200          # channel 1 (red in the file)
    a[1, 5:35, 20:40] = 150           # channel 2 (green in the file)
    p = str(tmp_path / "rg.tif")
    tifffile.imwrite(p, a, imagej=True, metadata={"axes": "CYX", "mode": "composite",
                                                  "LUTs": [_lut(1, 0, 0), _lut(0, 1, 0)]})
    return p


def _mean_rgb(img_path, channels, luts=None):
    from batoolset.settings.global_settings import set_UI
    from pyfigures.mcp_tools.core import _ensure_qapp
    from pyfigures.panel_source_preview import panel_rgb
    from batoolset.drawings.shapes.image2d import Image2D
    set_UI()
    _ensure_qapp()
    panel = Image2D(img_path)
    panel.channels = channels
    panel.LUTs = luts
    panel.update_qimage()
    return panel_rgb(panel).astype(float).reshape(-1, 3).mean(0)


def test_file_has_its_channel_colours(red_green_tif):
    from batoolset.drawings.shapes.image2d import Image2D
    panel = Image2D(red_green_tif)
    if not (hasattr(panel.img, "metadata") and panel.img.metadata.get("LUTs")):
        pytest.skip("this reader gives no channel LUTs for an ImageJ TIFF")
    r, g, b = _mean_rgb(red_green_tif, None)
    assert r > 0 and g > 0 and b == 0                      # the merge: red + green


def test_one_channel_shown_alone_keeps_its_file_colour(red_green_tif):
    from batoolset.drawings.shapes.image2d import Image2D
    if not Image2D(red_green_tif).img.metadata.get("LUTs"):
        pytest.skip("this reader gives no channel LUTs for an ImageJ TIFF")
    r, g, b = _mean_rgb(red_green_tif, [True, False])
    assert r > 0 and g == 0 and b == 0, (r, g, b)          # red, not gray
    r, g, b = _mean_rgb(red_green_tif, [False, True])
    assert g > 0 and r == 0 and b == 0, (r, g, b)          # green, not gray
    # a LUT the user chose still wins
    r, g, b = _mean_rgb(red_green_tif, [True, False], ["GREEN", "RED"])
    assert g > 0 and r == 0 and b == 0, (r, g, b)
    # "NONE" for that channel = the file's own colour
    r, g, b = _mean_rgb(red_green_tif, [True, False], [None, "GREEN"])
    assert r > 0 and g == 0 and b == 0, (r, g, b)


def test_set_lut_none_on_a_panel_without_lut_says_no_change(red_green_tif, tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], red_green_tif)
    out = M.set_lut(pyf, [0], 0, ["NONE"])
    assert out.startswith("NO CHANGE") and "LUTs removed" not in out
    assert "render_preview" in out
    M.set_lut(pyf, [0], 0, ["MAGENTA", "GREEN"])
    out = M.set_lut(pyf, [0], 0, ["NONE", "NONE"])
    assert "LUTs removed" in out                           # a real removal is still reported
