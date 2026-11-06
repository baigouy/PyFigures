"""User report 2026-11-06: opening a figure, the panels first showed a red
"Error" while their pixels were still loading in the background. They now
show a grey "Loading…" until the pixels arrive; a file that really fails
still shows "Error". The mark is never saved with the panel.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_open_perf import _make_figure, _open  # noqa: E402


def _draw(img2d):
    from qtpy.QtGui import QImage, QPainter, QColor
    img = QImage(200, 160, QImage.Format.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)                 # no antialiasing: the editing view
    img2d.draw(p)
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    a = np.frombuffer(ptr, np.uint8).reshape(160, img.bytesPerLine())[:, :800].reshape(160, 200, 4)
    b, g, r = a[..., 0].astype(int), a[..., 1].astype(int), a[..., 2].astype(int)
    return {"red": int(((r > 200) & (g < 60) & (b < 60)).sum()),
            "grey": int(((abs(r - 150) < 8) & (abs(g - 150) < 8) & (abs(b - 150) < 8)).sum())}


def test_a_panel_still_loading_is_drawn_as_loading_not_error(qapp, tmp_path):
    from PIL import Image
    from batoolset.drawings.shapes.image2d import Image2D
    path = tmp_path / "a.png"
    Image.fromarray(np.zeros((60, 80), np.uint8)).save(path)
    Image2D._lazy_mode = True
    try:
        panel = Image2D(filename=str(path), width=180, height=140)
    finally:
        Image2D._lazy_mode = False
    panel.setTopLeft(10, 10)
    assert panel.img is None
    Image2D.pixels_pending.add(id(panel))
    try:
        loading = _draw(panel)
        assert "pixels_pending" not in panel.to_dict()
    finally:
        Image2D.pixels_pending.discard(id(panel))
    failed = _draw(panel)
    assert loading["grey"] > 50 and loading["red"] == 0
    assert failed["red"] > 50


def test_opening_marks_panels_loading_until_their_pixels_arrive(qapp, tmp_path, monkeypatch):
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.gui.pfgui import EZFIG_GUI
    pyf = _make_figure(str(tmp_path), n=4)
    seen = []
    real = EZFIG_GUI._load_next_lazy_image

    def spy(self):
        queue = getattr(self, "_lazy_img_queue", None) or []
        if queue and not seen:
            seen.append(all(id(i) in Image2D.pixels_pending for i in queue))
        return real(self)
    monkeypatch.setattr(EZFIG_GUI, "_load_next_lazy_image", spy)
    g, _ = _open(qapp, pyf, monkeypatch)
    try:
        imgs = [s for grp in g.paint.EZFIG_panel.shapes_to_draw
                for s in (getattr(grp, "content", None) or []) if isinstance(s, Image2D)]
        assert seen == [True]                                     # marked while queued
        assert imgs and all(i.img is not None for i in imgs)
        assert not any(id(i) in Image2D.pixels_pending for i in imgs)   # cleared once loaded
    finally:
        g.close()
