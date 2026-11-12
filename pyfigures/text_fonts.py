"""The font of a figure's texts other than the panel letters, for live objects.

In a figure the letters have one font and every other text (scale-bar labels, legends,
labels) shares one, which may differ from the letters' (user, 2026-11-12). A scale bar
added in the panel editor was saved in Qt's generic "Sans Serif", drawn in another font
than the labels next to it: it now takes the font of the other texts.
The file-tool counterpart is mcp_tools.core._scale_bars_in_text_font.
"""
from __future__ import annotations

from collections import Counter


def _texts(items):
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.txt2d import TAText2D
    from batoolset.drawings.shapes.scalebar import ScaleBar
    for obj in items or []:
        if isinstance(obj, Group):
            yield from _texts(obj.content)
        elif isinstance(obj, Image2D):
            for a in obj.annotations or []:
                if isinstance(a, ScaleBar):
                    if isinstance(a.legend, TAText2D):
                        yield a.legend
                elif isinstance(a, TAText2D) and not getattr(a, 'is_letter', False):
                    yield a
        elif isinstance(obj, TAText2D) and not getattr(obj, 'is_letter', False):
            yield obj


def other_text_family(items, fallback=None):
    """The font most texts other than letters use in *items* (figure objects), else
    *fallback* (the figure font)."""
    from .mcp_tools.core import _html_font_family
    counts = Counter()
    for text in _texts(items):
        try:
            family = _html_font_family(text.getHtmlText())
        except Exception:
            family = None
        if family:
            counts[family] += 1
    if counts:
        return counts.most_common(1)[0][0]
    return fallback


def open_figure_items():
    """(shapes, figure font family) of the open PyFigures window, else ([], None)."""
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance()
    for w in (app.topLevelWidgets() if app else []):
        canvas = getattr(getattr(w, 'paint', None), 'EZFIG_panel', None)
        if canvas is not None and w.isVisible():
            font = getattr(w, 'serializable_font', None)
            try:
                family = font.family() if font is not None else None
            except Exception:
                family = None
            return list(canvas.shapes_to_draw or []), family
    return [], None


def scale_bar_in_text_font(scale_bar, items=None, fallback=None):
    """Give *scale_bar*'s label the font of the other texts unless it has one of its own."""
    from batoolset.drawings.shapes.txt2d import TAText2D
    from .mcp_tools.core import _html_font_family, _with_font_family
    legend = getattr(scale_bar, 'legend', None)
    if not isinstance(legend, TAText2D):
        return False
    html = legend.getHtmlText()
    if not legend.getPlainText().strip() or _html_font_family(html):
        return False
    if items is None:
        items, fallback = open_figure_items()
    family = other_text_family(items, fallback)
    if not family:
        return False
    legend.setText(_with_font_family(html, family))
    return True
