"""User report 2026-11-06: a rectangle moved in the panel editor was not on the
canvas after Ok, though the editor showed it. The panel's inset had been
cropped to 0 px (margins entered as coordinates): sizing it raised
ZeroDivisionError, which aborted ALL the panel's annotations. Moving the box
only shifted that broken crop. Now an inset cropped to nothing is skipped
(no image, no border bar), the other annotations are drawn, and the inset
of a moved box shows exactly what the box covers."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_user_findings_20261022 import _callout  # noqa: E402


def _parts(panel):
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.line2d import Line2D
    box = next(a for a in panel.annotations if type(a).__name__ == "Rectangle2D")
    inset = next(a for a in panel.annotations if isinstance(a, Image2D))
    lines = [a for a in panel.annotations if isinstance(a, Line2D)]
    return box, inset, lines


def test_an_inset_cropped_to_nothing_does_not_hide_the_other_annotations(qapp, tmp_path):
    from qtpy.QtGui import QImage, QPainter
    panel = _callout(tmp_path)
    box, inset, lines = _parts(panel)
    w, _ = inset.get_raw_size()
    inset.crop_left, inset.crop_right = 40, w - 40          # 0 px left
    assert inset._cropped_to_nothing()
    drawn = []
    for shape in [box, *lines]:
        real = shape.draw
        shape.draw = lambda *a, _r=real, _s=shape, **k: (drawn.append(_s), _r(*a, **k))[1]
    inset_drawn = []
    real_bg = inset.draw_bg
    inset.draw_bg = lambda *a, **k: (inset_drawn.append(1), real_bg(*a, **k))[1]
    img = QImage(600, 400, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    panel.draw(p)
    p.end()
    assert box in drawn and all(line in drawn for line in lines)
    assert inset_drawn == []                                # no stray border bar


def test_moving_the_box_gives_the_inset_the_box_region(qapp, tmp_path):
    from qtpy.QtCore import QPointF
    from pyfigures.gui.zoom_links import zoom_links, follow_zoom_links
    panel = _callout(tmp_path)
    box, inset, _ = _parts(panel)
    w, h = inset.get_raw_size()
    inset.crop(int(box.x()), int(w - box.x()), int(box.y()), int(h - box.y()))   # broken: 0 px
    links = zoom_links(panel.annotations, box)
    d = QPointF(15, -10)
    box.translate(d)
    follow_zoom_links(links, d)
    assert (inset.crop_left, inset.crop_top) == (int(box.x()), int(box.y()))
    assert (inset.crop_right, inset.crop_bottom) == (int(w - box.x() - box.width()), int(h - box.y() - box.height()))
    assert not inset._cropped_to_nothing()
