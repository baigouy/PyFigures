"""Channels are counted from 1 everywhere (user, 2026-11-16: "I used to start
at 0 and the MCP seems to start at 1 and most people would start at 1 except
coders, we have the two views in the code").

The LUT dialog said "Channel 0", the annotation editor's channel boxes "0, 1,
2", while the rest of the GUI (Ch1, the ROI-statistics menu) said channel 1.
The MCP tools disagreed too: invert_lut, add_stack_montage, add_kymograph and
add_orthogonal_views took 0-based numbers (invert_lut even replied "channel
0"), detect_objects and the split export counted from 1. Now all count from 1,
and 0 is refused with a plain message instead of silently meaning the first
channel.
"""
from __future__ import annotations

import ast
import inspect
import xml.etree.ElementTree as ET

import numpy as np
import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _hyperstack(path, T=5, Z=3, C=2, H=40, W=60):
    import tifffile
    a = np.zeros((T, Z, C, H, W), np.uint16)
    for c in range(C):
        a[:, :, c] = 100 * (c + 1)
    tifffile.imwrite(path, a, imagej=True,
                     metadata={"axes": "TZCYX", "finterval": 2.0, "tunit": "min", "spacing": 0.5})
    return path


def _panels(pyf):
    return list(ET.parse(pyf).getroot().iter("Image2D"))


def test_channel_index_helper():
    from pyfigures.mcp_tools.stacks import _channel_index
    assert _channel_index(None, 3) == (None, None)
    assert _channel_index(1, 3) == (0, None)
    assert _channel_index(3, 3) == (2, None)
    assert _channel_index("2", 3) == (1, None)
    idx, err = _channel_index(0, 3)
    assert idx is None and "counted from 1" in err and "1 to 3" in err
    idx, err = _channel_index(4, 3)
    assert idx is None and "does not exist" in err


def test_montage_channel_counts_from_1(tmp_path):
    stack = _hyperstack(str(tmp_path / "h.tif"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    res = M.add_stack_montage(pyf, stack, axis="t", frames=2, channel=1)
    assert not res.startswith("ERROR"), res
    for img in _panels(pyf):
        assert ast.literal_eval(img.findtext("channels").strip('"')) == [True, False]
    pyf2 = str(tmp_path / "g.pyf")
    M.create_figure(pyf2)
    zero = M.add_stack_montage(pyf2, stack, axis="t", frames=2, channel=0)
    assert zero.startswith("ERROR") and "counted from 1" in zero
    assert M.add_stack_montage(pyf2, stack, axis="t", frames=2, channel=3).startswith("ERROR")


def test_kymograph_and_orthogonal_channel_count_from_1(tmp_path):
    from pyfigures.mcp_tools.core import _decode
    stack = _hyperstack(str(tmp_path / "h.tif"))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], stack)
    zero = M.add_kymograph(pyf, [0], 0, x1=0, y1=20, x2=59, y2=20, channel=0)
    assert zero.startswith("ERROR") and "counted from 1" in zero
    res = M.add_kymograph(pyf, [0], 0, x1=0, y1=20, x2=59, y2=20, channel=2)
    assert not res.startswith("ERROR"), res
    script = _decode(_panels(pyf)[1].findtext("custom_loading_script"))
    assert "_channel = 1\n" in script                  # the 2nd channel, 0-based inside the script
    zero = M.add_orthogonal_views(pyf, [0], 0, x=5, y=5, channel=0, z_scale=1)
    assert zero.startswith("ERROR") and "counted from 1" in zero
    res = M.add_orthogonal_views(pyf, [0], 0, x=5, y=5, channel=1, z_scale=1)
    assert not res.startswith("ERROR"), res
    script = _decode(_panels(pyf)[-1].findtext("custom_loading_script"))
    assert "_channel = 0\n" in script


def test_docstrings_say_counted_from_1():
    from pyfigures.mcp_tools import content, stacks
    for fn in (content.invert_lut, stacks.add_stack_montage, stacks.add_kymograph,
               stacks.add_orthogonal_views):
        doc = inspect.getdoc(fn)
        assert "counted from 1" in doc, fn.__name__
        assert "0-based channel" not in doc and "channel (0-based)" not in doc


def test_gui_lut_dialog_and_editor_number_channels_from_1():
    from qtpy.QtWidgets import QApplication, QGroupBox
    QApplication.instance() or QApplication([])
    from pyfigures.gui.lutmultiselector import LutWidget
    w = LutWidget(nb_channels=3)
    titles = [b.title() for b in w.findChildren(QGroupBox)]
    assert titles[:3] == ["Channel 1", "Channel 2", "Channel 3"]
    w.deleteLater()
    from pyfigures.gui import annotation_editor
    src = inspect.getsource(annotation_editor)
    assert 'QCheckBox(f"{i + 1}")' in src and 'QCheckBox(f"{i}")' not in src
