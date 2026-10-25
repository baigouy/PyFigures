"""Empty channels and blank panels: splitting an RGB file with content in two
channels made a black panel for the third (user report, egg_chamber_Series016
.png). Splits (GUI and MCP) leave such channels out and QC lists panels with a
single value everywhere. The GUI's gray split also kept the source's coloured
LUT on each channel.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

REAL = r"C:\Users\aigouy\OneDrive\Desktop\test_images\sample_images_PA\egg_chamber_Series016.png"


@pytest.fixture
def rgb_two(tmp_path):
    """An RGB PNG: red and green hold cells, blue is 0 everywhere."""
    from PIL import Image
    rng = np.random.default_rng(0)
    arr = np.zeros((60, 80, 3), np.uint8)
    arr[..., 0] = (rng.random((60, 80)) * 200).astype(np.uint8)
    arr[..., 1] = (rng.random((60, 80)) * 200).astype(np.uint8)
    p = str(tmp_path / "two_channels.png")
    Image.fromarray(arr).save(p)
    return p


def test_helpers():
    from pyfigures.constant_panels import constant_free_channels, constant_value
    a = np.zeros((4, 5, 3))
    a[..., 0] = np.arange(20).reshape(4, 5)
    assert constant_free_channels(a) == [0]
    assert constant_free_channels(np.zeros((4, 5, 2))) == [0, 1]      # nothing to choose from
    assert constant_value(np.full((3, 3), 255)) == 255 and constant_value(a) is None


def test_mcp_split_leaves_out_the_empty_channel(rgb_two, tmp_path):
    from pyfigures.mcp_server import create_figure, add_channel_split, describe_figure
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=0)
    r = add_channel_split(pyf, stack_path=rgb_two, names=["R", "G", "B"])
    assert "left out B (channel 3" in r
    assert "[two_channels.png x3]" in describe_figure(pyf)          # R, G + merge
    pyf2 = str(tmp_path / "g.pyf")
    create_figure(pyf2, mode="groups", num_groups=0)
    add_channel_split(pyf2, stack_path=rgb_two, skip_constant_channels=False)
    assert "[two_channels.png x4]" in describe_figure(pyf2)


def test_audit_lists_constant_panels(rgb_two, tmp_path):
    from pyfigures.mcp_server import create_figure, add_channel_split, audit_figure
    from pyfigures.gui.qc_reports import audit_report
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=0)
    add_channel_split(pyf, stack_path=rgb_two, skip_constant_channels=False)
    a = json.loads(audit_figure(pyf))
    assert len(a["panels_constant"]) == 1 and a["panels_constant"][0]["value"] == 0
    assert "single value everywhere" in audit_report(audit_figure(pyf))


def _gui_with(qapp, path):
    from pyfigures.gui.pfgui import EZFIG_GUI
    from batoolset.drawings.shapes.image2d import Image2D
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.all_images_directly([path])
    t0 = time.time()
    while time.time() - t0 < 30:
        qapp.processEvents()
        ims = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)]
        if ims and isinstance(ims[0].img, np.ndarray):
            return g, ims[0]
        time.sleep(0.01)
    raise AssertionError("image not loaded")


def test_gui_split_is_gray_and_skips_the_empty_channel(qapp, rgb_two):
    g, img = _gui_with(qapp, rgb_two)
    try:
        msgs = []
        g.paint.EZFIG_panel.informative_message_required.connect(msgs.append)
        g.paint.EZFIG_panel.selected_shape = img
        g.paint.EZFIG_panel.split_channels(mode="gray")
        row = g.paint.EZFIG_panel.shapes_to_draw[-1]
        singles = row.content[:-1]
        assert len(singles) == 2                       # red, green (blue left out) + merge
        for k, s in enumerate(singles):
            assert s.channels == [c == k for c in range(3)]
            assert s.LUTs[k] == "GRAY"                 # it kept the source's colour LUT
        assert any("left out channel(s) 3" in m for m in msgs)
        # magenta / green mode: one panel for the two non-empty channels
        g.paint.EZFIG_panel.selected_shape = img
        g.paint.EZFIG_panel.split_channels(mode="magenta")
        row = g.paint.EZFIG_panel.shapes_to_draw[-1]
        assert len(row.content) == 2 and row.content[0].LUTs[:2] == ["MAGENTA", "GREEN"]
    finally:
        g._dirty = False
        g.close()


def test_gui_split_panels_get_automatic_letters(qapp, tmp_path):
    """23 Oct report: with automatic lettering ticked, the split panels got
    no letters of their own."""
    from PIL import Image
    rng = np.random.default_rng(3)
    p = str(tmp_path / "three.png")
    Image.fromarray((rng.random((60, 80, 3)) * 200).astype(np.uint8)).save(p)
    g, img = _gui_with(qapp, p)
    try:
        g.auto_lettering_checkbox.setChecked(True)
        g.update_letters()
        g.paint.EZFIG_panel.selected_shape = img
        g.paint.EZFIG_panel.split_channels(mode="gray")
        for _ in range(10):
            qapp.processEvents()
        from pyfigures.gui.pfgui import Image2D
        letters = []
        stack = list(g.paint.EZFIG_panel.shapes_to_draw)
        while stack:
            s = stack.pop(0)
            if isinstance(s, Image2D) and not s.isText:
                letters.append([a.getPlainText() for a in (s.annotations or []) if getattr(a, "is_letter", False)])
            stack[0:0] = list(getattr(s, "content", None) or [])
        # the original panel + 3 singles + merge, each with one letter, all different
        assert len(letters) == 5 and all(len(l) == 1 for l in letters), letters
        assert len({l[0] for l in letters}) == 5, letters
    finally:
        g._dirty = False
        g.close()


def test_insert_channel_split_gets_automatic_letters(qapp, tmp_path, monkeypatch):
    """Insert → Stack views → Channel split goes through the MCP tool and a
    reload, which skipped automatic lettering: the new row had no letters."""
    from PIL import Image
    from qtpy.QtWidgets import QDialog
    from pyfigures.gui import pfgui
    rng = np.random.default_rng(4)
    p = str(tmp_path / "three.tif")
    from batoolset.img import Img
    Img((rng.random((60, 80, 3)) * 200).astype(np.uint8), dimensions="hwc").save(p)
    g, img = _gui_with(qapp, p)
    try:
        class _OK:
            def __init__(self, *a, **k):
                pass

            def exec_(self):
                return QDialog.Accepted
        monkeypatch.setattr(pfgui, "CustomDialog", _OK)
        g.auto_lettering_checkbox.setChecked(True)
        g.paint.EZFIG_panel.selected_shape = img
        g.add_channel_split_action()
        from pyfigures.gui.pfgui import Image2D
        letters = []
        stack = list(g.paint.EZFIG_panel.shapes_to_draw)
        while stack:
            s = stack.pop(0)
            if isinstance(s, Image2D) and not s.isText:
                letters.append([a.getPlainText() for a in (s.annotations or []) if getattr(a, "is_letter", False)])
            stack[0:0] = list(getattr(s, "content", None) or [])
        comments = []
        stack = list(g.paint.EZFIG_panel.shapes_to_draw)
        while stack:
            s = stack.pop(0)
            if isinstance(s, Image2D) and not s.isText:
                comments.append(s.user_comments)
            stack[0:0] = list(getattr(s, "content", None) or [])
        # as in recipes and the MCP server: each panel of a channel split has
        # its own letter (it got no letter at all)
        assert all(len(l) == 1 for l in letters), (letters, comments)
        assert len(letters) == 5, (letters, comments)          # 3 channels + merge + the original
    finally:
        g._dirty = False
        g.close()


@pytest.mark.skipif(not os.path.isfile(REAL), reason="the user's test image is not on this computer")
def test_real_egg_chamber_file(tmp_path):
    from pyfigures.mcp_server import create_figure, add_channel_split
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=0)
    r = add_channel_split(pyf, stack_path=REAL)
    assert "left out" in r, r
