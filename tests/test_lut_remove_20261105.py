"""'remove all LUTs' (chat, 2026-11-05): removing a LUT must give back the image
file's own colours. set_lut's "DEFAULT" was documented as that but was stored
as a palette name and drew the DNA rainbow; "NONE" / "DEFAULT" now clear it."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from PIL import Image  # noqa: E402

import pyfigures.mcp_server as M  # noqa: E402


def _ramp_figure(tmp_path, name):
    src = tmp_path / "ramp.png"
    if not src.exists():
        Image.fromarray(np.tile(np.arange(256, dtype=np.uint8), (40, 1))).save(src)
    pyf = str(tmp_path / f"{name}.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], str(src))
    return pyf


def _pixels(pyf):
    out = pyf[:-4] + ".png"
    M.export_figure(pyf, out)
    a = np.asarray(Image.open(out).convert("RGB"))
    row = a[a.shape[0] // 2]
    return [tuple(int(x) for x in row[int(a.shape[1] * f)]) for f in (0.2, 0.4, 0.6, 0.8)]


def _stored(pyf):
    from pyfigures.mcp_tools.core import _load
    return _load(pyf, resolve=False)[1].find(".//Image2D/LUTs").text


@pytest.mark.parametrize("clear", ["NONE", "DEFAULT", "none", "default"])
def test_removing_a_lut_gives_back_the_file_colours(tmp_path, clear):
    original = _pixels(_ramp_figure(tmp_path, "original"))
    assert all(r == g == b for r, g, b in original)                  # a grey ramp
    pyf = _ramp_figure(tmp_path, "edited")
    M.set_lut(pyf, [0], 0, ["DNA"])
    assert _pixels(pyf) != original
    out = M.set_lut(pyf, [0], 0, [clear])
    assert "LUTs removed" in out and _stored(pyf) == "None"
    assert _pixels(pyf) == original                                  # not the DNA rainbow


def test_null_still_keeps_a_channel_and_none_clears_only_its_own(tmp_path):
    import ast
    pyf = _three_channel_figure(tmp_path)
    M.set_lut(pyf, [0], 0, ["RED", "GREEN", "BLUE"])
    M.set_lut(pyf, [0], 0, [None, "NONE"])                 # channel 3 not given: kept
    assert ast.literal_eval(_stored(pyf)) == ["RED", None, "BLUE"]


def _three_channel_figure(tmp_path):
    src = tmp_path / "rgb.png"
    a = np.zeros((40, 60, 3), np.uint8)
    a[..., 0], a[..., 1], a[..., 2] = 200, 100, 30
    Image.fromarray(a).save(src)
    pyf = str(tmp_path / "rgb.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], str(src))
    return pyf


def test_the_same_lut_on_several_channels_is_flagged(tmp_path):
    """'try GRAY' put GRAY on every channel of RGB panels (2026-11-05): set_lut
    warns and the figure audit (QC → Audit figure, pre-submission review) lists it."""
    import json
    pyf = _three_channel_figure(tmp_path)
    assert json.loads(M.audit_figure(pyf))["panels_channels_share_a_lut"] == []
    out = M.set_lut(pyf, [0], 0, ["GRAY", "GRAY", "GRAY"])
    assert "cannot be told apart" in out
    found = json.loads(M.audit_figure(pyf))["panels_channels_share_a_lut"]
    assert found and found[0]["lut"] == "GRAY" and found[0]["channels"] == [1, 2, 3]
    from pyfigures.gui.qc_reports import audit_report
    assert "channels 1, 2, 3 all use the GRAY LUT" in audit_report(M.audit_figure(pyf))
    M.set_lut(pyf, [0], 0, ["RED", "GREEN", "BLUE"])
    assert json.loads(M.audit_figure(pyf))["panels_channels_share_a_lut"] == []
    M.set_lut(pyf, [0], 0, ["NONE"])
    assert json.loads(M.audit_figure(pyf))["panels_channels_share_a_lut"] == []


def test_one_lut_warning_no_longer_suggests_one_lut_per_channel(tmp_path):
    pyf = _three_channel_figure(tmp_path)
    out = M.set_lut(pyf, [0], 0, ["GRAY"])
    assert "Never give the SAME LUT to several channels" in out


def test_help_requests_offer_to_open_the_editor_on_the_lut_tab():
    """'help me change channel color in e' (2026-11-05): correct choices, but no
    offer to open the panel editor where the user can do it."""
    import inspect
    from pyfigures.assistant import categorized_mcp, live_mcp
    source = inspect.getsource(categorized_mcp)
    assert "Whenever you list choices for a change" in source
    assert "open_native_menu" in source and "yellow selection outline" in source
    doc = live_mcp.mcp._tool_manager._tools["open_annotation_editor"].description
    assert "channels and their colours / LUTs" in doc


def test_the_tool_says_none_removes_the_lut():
    from pyfigures.mcp_tools.content import set_lut
    assert '"NONE"' in set_lut.__doc__ and "remove / reset / clear" in set_lut.__doc__
