"""
Tests for the interactive GUI tools that surface MCP-only capabilities:
- the significance-bracket tool in the annotation editor (VectorialDrawPane2)
- the multi-channel merge dialog action on the main window (EZFIG_GUI)

Both run headlessly (Qt offscreen); run with PYTEST_QT_API=pyqt6.
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


def _tif(path, val):
    from batoolset.img import Img
    Img(np.full((40, 50), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


# ── significance bracket (annotation editor) ────────────────────────────────

@pytest.fixture
def pane(qapp):
    from pyfigures.gui.annotation_editor import VectorialDrawPane2
    return VectorialDrawPane2(background=None)


def test_bracket_polyline_geometry(pane):
    from qtpy.QtCore import QPointF
    from batoolset.drawings.shapes.polyline2d import PolyLine2D
    # drag from (10,100) to (210,60): bar at the top edge (y=60), 4 vertices
    poly = pane._make_bracket_polyline(QPointF(10, 100), QPointF(210, 60))
    assert isinstance(poly, PolyLine2D)
    assert poly.count() == 4
    verts = [poly.at(i) for i in range(poly.count())]
    xs = sorted({round(v.x()) for v in verts})
    assert xs == [10, 210]                       # spans the drag horizontally
    assert min(v.y() for v in verts) == 60       # bar sits at the top of the box


def test_bracket_commit_adds_polyline_and_label(pane, monkeypatch):
    from qtpy.QtWidgets import QInputDialog
    from qtpy.QtCore import QPointF
    from batoolset.drawings.shapes.polyline2d import PolyLine2D
    from batoolset.drawings.shapes.txt2d import TAText2D
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("**", True)))
    n0 = len(pane.shapes)
    pane._bracket_mode = True
    pane._bracket_dragging = True
    pane._commit_bracket(QPointF(10, 100), QPointF(210, 60))
    added = pane.shapes[n0:]
    assert any(isinstance(s, PolyLine2D) for s in added)
    assert any(isinstance(s, TAText2D) for s in added)


def test_bracket_empty_label_is_bracket_only(pane, monkeypatch):
    from qtpy.QtWidgets import QInputDialog
    from qtpy.QtCore import QPointF
    from batoolset.drawings.shapes.txt2d import TAText2D
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", True)))
    n0 = len(pane.shapes)
    pane._commit_bracket(QPointF(0, 50), QPointF(100, 20))
    added = pane.shapes[n0:]
    assert added and all(not isinstance(s, TAText2D) for s in added)


def test_bracket_trivial_click_ignored(pane, monkeypatch):
    from qtpy.QtWidgets import QInputDialog
    from qtpy.QtCore import QPointF
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("*", True)))
    n0 = len(pane.shapes)
    pane._commit_bracket(QPointF(5, 5), QPointF(6, 6))    # < 3 px
    assert len(pane.shapes) == n0


def test_bracket_roundtrips_in_pyf(qapp, monkeypatch, tmp_path):
    """A committed bracket (polyline + label) survives a real .pyf save/reload
    when carried as image annotations (the editor merges shapes back on close)."""
    from qtpy.QtWidgets import QMessageBox
    from qtpy.QtCore import QPointF
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.polyline2d import PolyLine2D
    from batoolset.drawings.shapes.txt2d import TAText2D
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    a = _tif(os.path.join(d, "a.tif"), 80)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], a, label="A")
    g = EZFIG_GUI(); g.reload_state(pyf, append=False)

    img = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)][0]
    poly = PolyLine2D(5, 30, 5, 20, 45, 20, 45, 30, color=0xFF0000, stroke=2)
    lbl = TAText2D(text="**", placement=None); lbl.setTopLeft(QPointF(20, 8))
    img.annotations = (img.annotations or []) + [poly, lbl]

    out = os.path.join(d, "fig2.pyf")
    g._save_state_to_file(out); g._dirty = False
    g2 = EZFIG_GUI(); g2.reload_state(out, append=False)
    img2 = [s for s in g2.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)][0]
    polys = [x for x in img2.annotations if isinstance(x, PolyLine2D)]
    lbls = [x for x in img2.annotations
            if isinstance(x, TAText2D) and not getattr(x, "is_letter", False)]
    g2._dirty = False
    assert polys and polys[0].count() == 4
    assert any("*" in (t.getHtmlText() or "") for t in lbls)


# ── multi-channel merge dialog (main window) ────────────────────────────────

def test_channel_merge_action_adds_scripted_panel(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox, QDialog
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image
    from batoolset.drawings.shapes.image2d import Image2D
    import pyfigures.mcp_server as M

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    ch1 = _tif(os.path.join(d, "c1.tif"), 60)
    ch2 = _tif(os.path.join(d, "c2.tif"), 200)
    base = os.path.join(d, "base.tif"); _tif(base, 100)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas"); add_image(pyf, [], base, label="A")
    g = EZFIG_GUI(); g.reload_state(pyf, append=False)

    # patch the multi-file picker and the confirm dialog
    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [ch1, ch2]))

    class _OK:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _OK)

    n0 = len([s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)])
    g.add_channel_merge_action()
    imgs = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)]
    assert len(imgs) == n0 + 1

    merged = imgs[-1]
    script = getattr(merged, "custom_loading_script", None)
    assert script, "merge panel has no loading script"
    code = M._decode(script)
    assert "self.img" in code
    # the generated script must run under split globals/locals (no nested-def bug)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ns = {"self": type("S", (), {"img": None})()}
    exec(code, {"np": np, "plt": plt}, ns)     # must not raise
    assert ns["self"].img is not None
    plt.close("all")
    g._dirty = False
