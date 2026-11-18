"""Zoom buttons at the bottom right of the main window (2026-11-16): the
canvas zoomed by keyboard only and fit-to-window was not reachable."""
from __future__ import annotations

import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_dnd_main_editor import ui, gui  # noqa: F401,E402


def _figure(gui, tmp_path):
    from batoolset.img import Img
    from batoolset.drawings.shapes.image2d import Image2D
    p = str(tmp_path / "a.tif")
    Img((np.random.default_rng(1).random((400, 300)) * 255).astype(np.uint8), dimensions="hw").save(p)
    gui._finish_add_single_images([Image2D(p)])


def test_buttons_zoom_and_show_the_zoom(gui, tmp_path):
    bar = gui.zoom_bar
    _figure(gui, tmp_path)
    assert bar.label.text() == "100 %"
    bar.in_button.click()
    assert bar.label.text() == "110 %" and abs(gui.paint.EZFIG_panel.scale - 1.1) < 1e-9
    bar.out_button.click()
    bar.out_button.click()
    assert bar.label.text() == "91 %"
    bar.reset_button.click()
    assert gui.paint.EZFIG_panel.scale == 1.0 and bar.label.text() == "100 %"


def test_fit_shows_the_whole_figure(gui, tmp_path):
    _figure(gui, tmp_path)
    gui.zoom_bar.set_scale(8)
    gui.zoom_bar.fit_button.click()
    panel = gui.paint.EZFIG_panel
    b = panel.updateBounds()
    area = gui.paint.scrollArea
    assert b.height() * panel.scale <= area.height() and b.width() * panel.scale <= area.width()
    assert gui.zoom_bar.label.text() == f"{panel.scale * 100:.0f} %"


def test_keyboard_zoom_updates_the_percentage(gui, tmp_path):
    _figure(gui, tmp_path)
    gui.paint.zoomIn()                       # what Ctrl + runs
    assert gui.zoom_bar.label.text() == "110 %"


def test_ctrl_wheel_zooms_and_the_wheel_alone_does_not(gui, tmp_path, qapp):
    from qtpy.QtCore import QPoint, QPointF, Qt
    from qtpy.QtGui import QWheelEvent
    _figure(gui, tmp_path)
    viewport = gui.paint.scrollArea.viewport()

    def wheel(mods):
        e = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, 120),
                        Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False)
        qapp.sendEvent(viewport, e)
    wheel(Qt.KeyboardModifier.NoModifier)
    assert gui.paint.EZFIG_panel.scale == 1.0
    wheel(Qt.KeyboardModifier.ControlModifier)
    assert abs(gui.paint.EZFIG_panel.scale - 1.1) < 1e-9


def test_fit_width_then_height_alternate(gui, tmp_path):
    """One button: fit the width, next click the height (the user, 2026-11-16)."""
    _figure(gui, tmp_path)
    bar, panel, area = gui.zoom_bar, gui.paint.EZFIG_panel, gui.paint.scrollArea
    b = panel.updateBounds()
    assert "width" in bar.fit_side_button.toolTip().split("(")[0]
    bar.fit_side_button.click()
    width_scale = panel.scale
    margin = gui.paint.FIT_MARGIN          # the rulers' margin before the figure fits too
    assert abs((b.x() + b.width() + margin) * width_scale
               - (area.width() - 2 - area.verticalScrollBar().sizeHint().width())) < 2
    assert "height" in bar.fit_side_button.toolTip().split("(")[0]
    bar.fit_side_button.click()
    assert abs((b.y() + b.height() + margin) * panel.scale
               - (area.height() - 2 - area.horizontalScrollBar().sizeHint().height())) < 2
    assert "width" in bar.fit_side_button.toolTip().split("(")[0]
