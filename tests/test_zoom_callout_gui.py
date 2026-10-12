"""GUI: Annotations -> Add zoom callout to selected panel (MCP add_zoom_callout).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _png(path, h, w):
    from PIL import Image
    Image.fromarray((np.indices((h, w)).sum(0) % 255).astype(np.uint8)).save(path)
    return path


def _gui_with_figure(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=2)
    add_image(pyf, [0], _png(os.path.join(d, "a.png"), 60, 80))
    add_image(pyf, [1], _png(os.path.join(d, "b.png"), 100, 200))
    add_image(pyf, [1], _png(os.path.join(d, "c.png"), 90, 120))
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    return g


def test_locate_panel(qapp, monkeypatch, tmp_path):
    g = _gui_with_figure(qapp, monkeypatch, tmp_path)
    groups = g.paint.EZFIG_panel.shapes_to_draw
    assert g._locate_panel(groups[1].content[1]) == ([1], 1)
    assert g._locate_panel(groups[0].content[0]) == ([0], 0)
    g._dirty = False


def test_zoom_callout_action(qapp, monkeypatch, tmp_path):
    from qtpy import QtWidgets
    from pyfigures.gui import pfgui
    g = _gui_with_figure(qapp, monkeypatch, tmp_path)
    target = g.paint.EZFIG_panel.shapes_to_draw[1].content[0]   # b.png, 200x100
    g.paint.EZFIG_panel.selected_shape = target

    class _Accept:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QtWidgets.QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _Accept)
    g.add_zoom_callout_action()

    # the reloaded figure: panel b now carries an inset + ROI box + 2 leaders
    b = g.paint.EZFIG_panel.shapes_to_draw[1].content[0]
    kinds = [type(a).__name__ for a in b.annotations]
    assert "Image2D" in kinds, kinds            # magnified inset
    assert kinds.count("Line2D") == 2, kinds     # leader lines
    assert any(k in ("Rectangle2D", "Rect2D") for k in kinds), kinds  # ROI box
    g._dirty = False


def test_zoom_callout_needs_selection(qapp, monkeypatch, tmp_path):
    g = _gui_with_figure(qapp, monkeypatch, tmp_path)
    g.paint.EZFIG_panel.selected_shape = None
    before = open(g.current_file, encoding="utf-8").read()
    g.add_zoom_callout_action()   # shows an info box, changes nothing
    assert open(g.current_file, encoding="utf-8").read() == before
    g._dirty = False
