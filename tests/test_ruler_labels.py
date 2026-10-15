"""The canvas rulers never draw a number cut by the canvas edge.

The ticks start one padding into the canvas but ran to the canvas size, so the
last label was clipped (e.g. only "5" of 500 was visible). Labels are now
centred on their tick and dropped when they would not fit.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def test_ruler_labels_fit_in_the_canvas(qapp, monkeypatch):
    from qtpy.QtGui import QPainter
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    drawn = []
    original = QPainter.drawText

    def record(self, *args):
        if len(args) == 3 and isinstance(args[2], str) and args[2].isdigit():
            drawn.append((args[0], args[1], args[2], self.fontMetrics().horizontalAdvance(args[2]),
                          self.fontMetrics().ascent()))
        return original(self, *args)

    monkeypatch.setattr(QPainter, "drawText", record)
    win = EZFIG_GUI()
    win.show()
    for scale in (1.0, 2.2):
        for size in ((1280, 800), (731, 517)):
            win.resize(*size)
            panel = win.paint.EZFIG_panel
            panel.scale = scale
            panel.update_size()
            drawn.clear()
            panel.grab()
            assert drawn, "no ruler label drawn"
            visible_w = panel.width() / scale
            visible_h = panel.height() / scale
            for x, y, label, tw, ascent in drawn:
                assert x + tw <= visible_w + 1, (label, x, tw, visible_w)
                assert y <= visible_h + 1, (label, y, visible_h)
    win._dirty = False
    win.close()
