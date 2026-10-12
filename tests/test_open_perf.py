"""Opening a figure in the GUI: images streaming in refresh the canvas at most
every _LAZY_REFRESH_MS (it used to repaint the whole figure once per image),
the canvas ends up complete, and the deferred undo baseline neither marks the
figure as modified nor goes missing.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _make_figure(d, n=12):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    rng = np.random.default_rng(0)
    for i in range(n):
        p = os.path.join(d, f"im{i}.png")
        Image.fromarray(rng.integers(0, 255, (60, 80), dtype=np.uint8)).save(p)
        add_image(pyf, [i % 2], p, label=chr(65 + i))
    return pyf


def _open(qapp, pyf, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    g = EZFIG_GUI()
    g.resize(1200, 800)
    g.show()
    paints = {"n": 0}
    panel = g.paint.EZFIG_panel
    real = panel.paintEvent

    def counting(ev):
        paints["n"] += 1
        return real(ev)
    panel.paintEvent = counting
    qapp.processEvents()
    paints["n"] = 0
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    t0 = time.time()
    while time.time() - t0 < 60:
        qapp.processEvents()
        th = getattr(g, "_pyf_loader_thread", None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:
            running = False
        imgs = [s for grp in g.paint.EZFIG_panel.shapes_to_draw
                for s in (getattr(grp, "content", None) or []) if type(s).__name__ == "Image2D"]
        # also wait for the pixels: under a slow run (coverage) the loader queue
        # can be momentarily empty between the .pyf parse and the image reads
        if not running and not getattr(g, "_lazy_img_queue", None) \
                and not getattr(g, "_active_img_loaders", None) and g.undo_stack \
                and imgs and all(i.img is not None for i in imgs):
            break
        time.sleep(0.005)
    for _ in range(5):
        qapp.processEvents()
    return g, paints["n"]


def _grab(w):
    img = w.grab().toImage()
    ptr = img.constBits()
    ptr.setsize(img.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine()).copy()


def test_open_refreshes_are_coalesced_and_canvas_is_complete(qapp, tmp_path, monkeypatch):
    n = 12
    g, n_paints = _open(qapp, _make_figure(str(tmp_path), n), monkeypatch)
    try:
        imgs = [s for grp in g.paint.EZFIG_panel.shapes_to_draw
                for s in (getattr(grp, "content", None) or []) if type(s).__name__ == "Image2D"]
        assert len(imgs) == n and all(i.img is not None for i in imgs)
        assert n_paints < n                       # was ≥ one full repaint per image
        before = _grab(g.paint.EZFIG_panel)
        g.paint.EZFIG_panel.repaint()
        qapp.processEvents()
        assert np.array_equal(before, _grab(g.paint.EZFIG_panel))   # nothing left stale
    finally:
        g._dirty = False
        g._stop_all_img_loaders()


def test_deferred_undo_baseline_keeps_figure_clean(qapp, tmp_path, monkeypatch):
    pyf = _make_figure(str(tmp_path), 4)
    g, _ = _open(qapp, pyf, monkeypatch)
    try:
        assert g.undo_stack, "undo baseline missing after open"
        assert g._dirty is False                  # opening is not an edit
        assert os.path.normcase(g.current_file) == os.path.normcase(pyf)
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
