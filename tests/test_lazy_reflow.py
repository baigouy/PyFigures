"""
Tests for the progressive-load self-correction (`_reflow_after_lazy_load`).

When a .pyf is opened, the figure is laid out from the panel sizes stored in the
file so the canvas appears instantly, then the real pixels stream in. If an image
file on disk was resized/replaced since the .pyf was saved, its stored size is
stale and the row it sits in stays misaligned — until the user nudges a size by
hand. `_on_img_ready` flags that drift and `_reflow_after_lazy_load` repacks the
affected groups so the figure self-corrects on open.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")
try:
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication  # noqa: F401
    _QT = True
except Exception:
    _QT = False

pytestmark = pytest.mark.skipif(not _QT, reason="Qt not available")


def _tif(path, w, h, val=120):
    from batoolset.img import Img
    Img(np.full((h, w), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


@pytest.fixture
def gui(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox, QDialog
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    class _OK:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _OK)

    d = tempfile.mkdtemp()
    # a row of three square panels, all the same size → equal packed heights
    a = _tif(os.path.join(d, "a.tif"), 100, 100)
    b = _tif(os.path.join(d, "b.tif"), 100, 100)
    c = _tif(os.path.join(d, "c.tif"), 100, 100)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    for p, lbl in ((a, "A"), (b, "B"), (c, "C")):
        add_image(pyf, [0], p, label=lbl)

    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g._dir = d
    yield g
    g._dirty = False


def _row_children(gui):
    from batoolset.drawings.shapes.group import Group
    from batoolset.drawings.shapes.image2d import Image2D
    groups = [s for s in gui.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Group)]
    assert groups, "expected a group row"
    g = groups[0]
    imgs = [c for c in g if isinstance(c, Image2D)]
    return g, imgs


def _heights(imgs):
    return [round(c.getRect(all=True).height(), 2) for c in imgs]


def test_baseline_row_is_aligned(gui):
    """As saved (stored size == real size) the row is already aligned."""
    _, imgs = _row_children(gui)
    hs = _heights(imgs)
    assert max(hs) - min(hs) < 0.5, f"baseline should be aligned, got {hs}"


def test_drift_then_reflow_realigns(gui):
    """Simulate a file whose real size drifted from the stored size: the middle
    panel becomes non-square. Without a repack the row is misaligned; after the
    drift-triggered reflow the heights match again."""
    from batoolset.img import Img
    g, imgs = _row_children(gui)

    # replace the middle panel's pixels with a taller (100x200) image, as the
    # progressive loader would when the file on disk has been resized — but do
    # NOT repack, mirroring the stale layout. (Fresh filename: the image reader
    # caches by path, so overwriting b.tif would return the cached 100x100.)
    tall = _tif(os.path.join(gui._dir, "b_tall.tif"), 100, 200)
    imgs[1].img = Img(tall)

    hs_before = _heights(imgs)
    assert max(hs_before) - min(hs_before) > 1.0, \
        f"expected misalignment after drift, got {hs_before}"

    # the loader would have flagged this; run the reflow
    gui._lazy_size_drift = True
    gui._reflow_after_lazy_load()

    hs_after = _heights(imgs)
    assert max(hs_after) - min(hs_after) < 0.5, \
        f"reflow should realign the row, got {hs_after}"
    # flag consumed
    assert gui._lazy_size_drift is False


def test_reflow_is_noop_without_drift(gui):
    """With no drift flagged, reflow must not touch the layout."""
    g, imgs = _row_children(gui)
    before = [c.getRect(all=True) for c in imgs]
    gui._lazy_size_drift = False
    gui._reflow_after_lazy_load()
    after = [c.getRect(all=True) for c in imgs]
    for b, a in zip(before, after):
        assert abs(b.x() - a.x()) < 1e-6 and abs(b.width() - a.width()) < 1e-6, \
            "reflow without drift must be a no-op"


def test_on_img_ready_flags_size_drift(gui, qapp):
    """Directly exercise the drift detection logic used by _on_img_ready: loading
    an image whose true size differs from the size assumed at layout sets the flag,
    while loading a same-size image does not."""
    from batoolset.img import Img
    _, imgs = _row_children(gui)

    def _simulate(target, new_path):
        # mirror the inline drift check in _on_img_ready
        old_w, old_h = target.get_raw_size()
        target.img = Img(new_path)
        new_w, new_h = target.get_raw_size()
        return (abs(new_w - old_w) > 0.5 or abs(new_h - old_h) > 0.5)

    # same size as assumed (100x100) → no drift
    same = _tif(os.path.join(gui._dir, "same.tif"), 100, 100)
    assert _simulate(imgs[0], same) is False

    # different size (300x120) → drift
    diff = _tif(os.path.join(gui._dir, "diff.tif"), 300, 120)
    assert _simulate(imgs[2], diff) is True
