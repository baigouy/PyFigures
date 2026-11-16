"""ROIs around small dots (panel m, 2026-11-16) could not be drawn: a shape
under 40 screen pixels in both directions was dropped as a slip of the
mouse, whatever the window. The limit is now 1 % of the visible editor area
(at least 4 px): a real small ROI stays, a click that barely moved does not."""
from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtCore import QRect, QRectF  # noqa: E402

from pyfigures.gui.annotation_editor import VectorialDrawPane2  # noqa: E402


def _pane(view_px, w, h, scale=1.0):
    pane = SimpleNamespace(
        filter_out_unwanted_shapes_based_on_distance=True, scale=scale, ctrl_key="Ctrl",
        currently_drawn_shape=SimpleNamespace(getRect=lambda: QRectF(10, 10, w, h)),
        visibleRegion=lambda: SimpleNamespace(boundingRect=lambda: QRect(0, 0, view_px, view_px)),
        width=lambda: view_px, height=lambda: view_px, update=lambda: None,
        ACCIDENTAL_DRAG_FRACTION=VectorialDrawPane2.ACCIDENTAL_DRAG_FRACTION,
        ACCIDENTAL_DRAG_MIN_PX=VectorialDrawPane2.ACCIDENTAL_DRAG_MIN_PX)
    pane.accidental_drag_limit = lambda: VectorialDrawPane2.accidental_drag_limit(pane)
    return pane


def check(pane):
    return VectorialDrawPane2.check_shape_size_before_adding_it(pane)


def test_a_small_roi_around_a_dot_is_kept():
    assert check(_pane(800, 12, 12))                 # 12 screen px: was dropped (< 40)
    assert check(_pane(800, 6, 6, scale=2.0))        # zoomed in: 12 screen px too


def test_a_click_that_barely_moved_is_still_dropped():
    pane = _pane(800, 3, 2)
    assert not check(pane) and pane.currently_drawn_shape is None


def test_the_limit_follows_the_window_size():
    assert VectorialDrawPane2.accidental_drag_limit(_pane(2000, 1, 1)) == 20
    assert VectorialDrawPane2.accidental_drag_limit(_pane(200, 1, 1)) == 4      # the floor
