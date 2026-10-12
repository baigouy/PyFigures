"""GUI: arrows, stack views, changed sources, copy style and alt text menu
actions (thin wrappers over the MCP tools).

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

from test_stack_tools import _hyperstack, _png, _zstack   # noqa: E402


class _Accept:
    def __init__(self, *a, **k):
        pass

    def exec_(self):
        from qtpy import QtWidgets
        return QtWidgets.QDialog.Accepted


def _gui(qapp, monkeypatch, tmp_path, files):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image
    EZFIG_GUI.show_tips = lambda self: None
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a)))
    monkeypatch.setattr(pfgui, "CustomDialog", _Accept)
    pyf = os.path.join(str(tmp_path), "f.pyf")
    create_figure(pyf, num_groups=len(files))
    for i, f in enumerate(files):
        add_image(pyf, [i], f)
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    g._shown = shown
    return g


def _select(g, row, idx=0):
    g.paint.EZFIG_panel.selected_shape = g.paint.EZFIG_panel.shapes_to_draw[row].content[idx]


def _annot_kinds(panel):
    return [type(a).__name__ for a in panel.annotations]


def test_arrow_action(qapp, monkeypatch, tmp_path):
    g = _gui(qapp, monkeypatch, tmp_path, [_png(str(tmp_path / "a.png"), 100, 200)])
    _select(g, 0)
    g.add_arrow_action()
    panel = g.paint.EZFIG_panel.shapes_to_draw[0].content[0]
    arrows = [a for a in panel.annotations if type(a).__name__ == "Line2D" and a.arrow]
    assert len(arrows) == 1
    assert (arrows[0].x2(), arrows[0].y2()) == (100.0, 50.0)       # tip = dialog default
    g._dirty = False


def test_stack_view_actions(qapp, monkeypatch, tmp_path):
    stack = _hyperstack(str(tmp_path / "h.tif"))
    z = _zstack(str(tmp_path / "z.tif"))
    g = _gui(qapp, monkeypatch, tmp_path, [stack, z])
    shapes = lambda: g.paint.EZFIG_panel.shapes_to_draw
    _select(g, 0)
    g.add_stack_montage_action()                        # new row, 5 frames (all of them)
    assert len(shapes()) == 3 and len(shapes()[2].content) == 5
    _select(g, 0)
    g.add_channel_split_action()                        # 2 channels + merge
    assert len(shapes()) == 4 and len(shapes()[3].content) == 3
    _select(g, 0)
    g.add_kymograph_action()                            # next to the source
    assert len(shapes()[0].content) == 2
    assert "Line2D" in _annot_kinds(shapes()[0].content[0])
    _select(g, 1)
    g.add_orthogonal_views_action()
    assert len(shapes()[1].content) == 2
    assert not [s for s in g._shown if "failed" in str(s).lower()], g._shown
    g._dirty = False


def test_stack_actions_refuse_flat_images(qapp, monkeypatch, tmp_path):
    g = _gui(qapp, monkeypatch, tmp_path, [_png(str(tmp_path / "a.png"))])
    before = open(g.current_file, encoding="utf-8").read()
    for act in (g.add_stack_montage_action, g.add_kymograph_action,
                g.add_orthogonal_views_action):
        _select(g, 0)
        act()
    assert open(g.current_file, encoding="utf-8").read() == before
    assert len(g._shown) == 3
    g._dirty = False


def test_changed_sources_reported_on_open_and_saved_on_save(qapp, monkeypatch, tmp_path):
    from pyfigures.source_snapshot import compare
    a = _png(str(tmp_path / "a.png"), value=10)
    g = _gui(qapp, monkeypatch, tmp_path, [a])
    assert g.save_pyfigures(g.current_file)
    assert compare(g.current_file)["recorded"]
    _png(a, value=200)
    later = time.time() + 10
    os.utime(a, (later, later))
    g._shown.clear()
    g._warn_changed_sources(g.current_file)
    assert g._shown and "a.png" in g._shown[0][2]
    g._shown.clear()
    g.save_pyfigures(g.current_file)                                 # accepts the new file
    g._warn_changed_sources(g.current_file)
    assert not g._shown
    g._dirty = False


def test_copy_style_and_alt_text_actions(qapp, monkeypatch, tmp_path):
    from pyfigures.gui import pfgui
    from pyfigures.mcp_server import create_figure, add_image, set_figure_properties
    img = _png(str(tmp_path / "a.png"))
    src = str(tmp_path / "src.pyf")
    create_figure(src, num_groups=1)
    add_image(src, [0], img)
    set_figure_properties(src, font_family="Courier New", font_size=17)
    g = _gui(qapp, monkeypatch, tmp_path, [img])
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda *a, **k: src)
    g.copy_style_action()
    import xml.etree.ElementTree as ET
    root = ET.parse(g._save_current_to_temp_pyf()).getroot()
    assert root.find("SerializableQFont/size").text == "17"
    assert "Courier New" in root.find("SerializableQFont/family").text
    g.alt_text_action()
    alt = os.path.splitext(g.current_file)[0] + ".alttext.json"
    assert os.path.isfile(alt)
    d = json.load(open(alt, encoding="utf-8"))
    assert d["long"].startswith("figure with 1 panel")
    g._dirty = False
