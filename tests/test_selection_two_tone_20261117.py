"""Selections are outlined in dashes of their colour alternating with black.

User, 2026-11-17: "if image is yellow then the selection does not see well, can
we have all selections be dashed line intermingled between their own current
color and black". The canvas selection was solid yellow, the panel editor's
selection red dash-dot (gaps showed the image), the drag-layout frames cyan.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest


def _outline_on(background, colour):
    from qtpy.QtCore import QRectF
    from qtpy.QtGui import QColor, QImage, QPainter
    from qtpy.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from pyfigures.gui.selection_style import draw_two_tone_rect
    img = QImage(120, 80, QImage.Format.Format_RGB32)
    img.fill(QColor(*background))
    p = QPainter(img)
    draw_two_tone_rect(p, QRectF(10, 10, 100, 60), QColor(*colour), 3)
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(80, 120, 4)[..., [2, 1, 0]].copy()
    return a[10, 15:105]          # along the top edge


@pytest.mark.parametrize("background", [(255, 255, 0), (0, 0, 0), (255, 255, 255)])
def test_yellow_selection_shows_on_any_background(background):
    edge = _outline_on(background, (255, 255, 0))
    black = (edge.sum(-1) < 60).sum()
    yellow = ((edge[:, 0] > 200) & (edge[:, 1] > 200) & (edge[:, 2] < 60)).sum()
    assert black > 20 and yellow > 20        # both tones along the edge, whatever is behind


def test_every_selection_outline_uses_two_tones():
    from pyfigures.gui import ezfig, annotation_editor
    assert "draw_two_tone_rect" in inspect.getsource(ezfig.EZFIG_panel.draw_selection) \
        if hasattr(ezfig, "EZFIG_panel") else "draw_two_tone_rect" in inspect.getsource(ezfig)
    src = inspect.getsource(annotation_editor)
    assert "draw_two_tone_rect(painter, sel, col, 2, cosmetic=True)" in src
    from batoolset.drawings.shapes.image2d import Image2D
    layout = inspect.getsource(Image2D.draw_inner_layout_selection)
    assert "QColor(0, 0, 0)" in layout and "setDashPattern" in layout
