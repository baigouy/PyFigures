"""Chat 2026-11-23 (local Qwen3.5 9B): "double figure width" right after "two columns max" became
arrange_live_images(columns=4), then 8: the layout changed, not the size. resize_figure now
takes scale=2 (no width to read first) and a SIZE note comes with width requests."""
import json
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _figure(tmp_path):
    import tifffile
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for i in range(3):
        tif = str(tmp_path / f"{i}.tif")
        tifffile.imwrite(tif, np.full((60, 80), 40 * i + 20, np.uint8))
        M.add_image(pyf, [0], tif)
    return pyf


def _width(pyf):
    from pyfigures import mcp_server as M
    return json.loads(M.get_figure_properties(pyf))["size"]["width_mm"]


def test_scale_two_doubles_the_width_and_keeps_the_layout(tmp_path):
    from pyfigures import mcp_server as M
    pyf = _figure(tmp_path)
    M.resize_figure(pyf, width_mm=80)
    rows_before = M.describe_figure(pyf).count("Group")
    M.resize_figure(pyf, scale=2)
    assert abs(_width(pyf) - 160) < 2
    assert M.describe_figure(pyf).count("Group") == rows_before
    M.resize_figure(pyf, scale=0.5)
    assert abs(_width(pyf) - 80) < 2
    assert M.resize_figure(pyf, scale=-1).startswith("ERROR")


def test_width_requests_bring_the_size_note():
    from pyfigures.assistant import categorized_mcp as C
    rules = C.request_rules("double figure width")
    assert "resize_figure(scale=2" in rules and "never the size" in rules
    assert "SIZE" not in C.request_rules("make the font size 8")
    assert "SIZE" not in C.request_rules("make the fig rows two cols max")
