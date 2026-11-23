"""Hermes Agent 2026-11-23: "make the fig 20 cm wide" became set_size(width_px=2362) (20 cm at
300 DPI), an 833 mm figure: set_size's width is in canvas units, 72 per inch, and its docstring
taught the 300 DPI conversion. It now says so, its result gives the width in mm, and
resize_figure (which converts) also takes a height."""
import json
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _figure(tmp_path):
    import tifffile
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for i in range(4):
        tif = str(tmp_path / f"{i}.tif")
        tifffile.imwrite(tif, np.full((60, 80), 40 * i + 20, np.uint8))
        M.add_image(pyf, [0], tif)
    return pyf


def _size(pyf):
    from pyfigures import mcp_server as M
    s = json.loads(M.get_figure_properties(pyf))["size"]
    return s["width_mm"], s["height_mm"]


def test_set_size_says_its_unit_and_points_to_resize_figure(tmp_path):
    from pyfigures import mcp_server as M
    first = M.set_size.__doc__.strip().splitlines()[0]
    assert "72 per inch" in first and "resize_figure" in first
    assert "300" not in M.set_size.__doc__.split("Converting")[0]      # no 300 DPI recipe
    pyf = _figure(tmp_path)
    out = M.set_size(pyf, 567)
    assert "200.0 mm" in out
    assert abs(_size(pyf)[0] - 200) < 1


def test_twenty_cm_wide_is_twenty_cm(tmp_path):
    from pyfigures import mcp_server as M
    pyf = _figure(tmp_path)
    out = M.resize_figure(pyf, width_cm=20)
    assert abs(_size(pyf)[0] - 200) < 1 and "200.0mm wide" in out and "mm tall" in out


def test_a_height_sets_the_height_aspect_kept(tmp_path):
    from pyfigures import mcp_server as M
    pyf = _figure(tmp_path)
    M.resize_figure(pyf, width_mm=180)
    w0, h0 = _size(pyf)
    out = M.resize_figure(pyf, height_mm=60)
    w, h = _size(pyf)
    assert abs(h - 60) < 0.5, out
    assert abs(w / h - w0 / h0) < 0.05 * (w0 / h0)
    assert M.resize_figure(pyf, height_cm=8).startswith("Figure resized to 80.0mm tall")
    assert M.resize_figure(pyf, height_mm=60, width_mm=100).startswith("ERROR")
    assert M.resize_figure(pyf, height_mm=60, group_path=[0]).startswith("ERROR")
