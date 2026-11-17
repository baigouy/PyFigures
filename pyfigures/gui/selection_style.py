"""How selections are outlined: dashes of their own colour alternating with black.

A plain yellow selection vanished on a yellow image (and a red one on red): the
user (2026-11-17) asked for every selection to be "dashed line intermingled
between their own current color and black". A solid black line is drawn first,
then the colour dashed on top, so whatever is behind, half of the outline shows.
"""
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor, QPen

DASH = (4.0, 4.0)       # colour dash, black gap: in pen widths


def two_tone_pens(colour, width=2.0, cosmetic=False):
    """(black pen, dashed colour pen) for an outline; draw with both, black first."""
    black = QPen(QColor(0, 0, 0), width)
    black.setCosmetic(cosmetic)
    black.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    dashed = QPen(QColor(colour), width)
    dashed.setCosmetic(cosmetic)
    dashed.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    dashed.setCapStyle(Qt.PenCapStyle.FlatCap)
    dashed.setDashPattern(list(DASH))
    return black, dashed


def draw_two_tone_rect(painter, rect, colour, width=2.0, cosmetic=False):
    """Outline *rect* in dashes of *colour* alternating with black; keeps the brush."""
    painter.save()
    try:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for pen in two_tone_pens(colour, width, cosmetic):
            painter.setPen(pen)
            painter.drawRect(rect)
    finally:
        painter.restore()
