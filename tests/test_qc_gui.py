"""
Tests for the GUI-side QC / journal wrappers that expose MCP-only capabilities
in the GUI: audit, journal compliance, print resolution, apply guidelines,
enforce min font, scale-bar-to-all, remap paths.
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
    Img(np.full((32, 48), val, dtype=np.uint8), dimensions='hw').save(path)
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

    # a real grouped figure (a row of two panels) loaded into the GUI
    d = tempfile.mkdtemp()
    a = _tif(os.path.join(d, "a.tif"), 60)
    b = _tif(os.path.join(d, "b.tif"), 200)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], a, label="A")
    add_image(pyf, [0], b, label="B")

    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g._dir = d
    yield g
    g._dirty = False


def _images(gui):
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.lists.tools import flatten_iterable
    return [s for s in flatten_iterable(gui.paint.EZFIG_panel.shapes_to_draw)
            if isinstance(s, Image2D)]


def test_audit_report(gui):
    captured = {}
    gui._show_report = lambda title, text: captured.setdefault(title, text)
    gui.audit_figure_report()
    assert "n_panels" in captured.get("Figure audit", "")


def test_journal_compliance_report(gui, monkeypatch):
    from pyfigures.gui import pfgui
    monkeypatch.setattr(pfgui._JournalDialog, "values", lambda self: {
        "journal": "nature", "column": "single", "min_dpi": 300, "min_font_pt": 7.0})
    captured = {}
    gui._show_report = lambda title, text: captured.setdefault(title, text)
    gui.check_journal_compliance_report()
    assert captured.get("Journal compliance")


def test_resolution_report(gui, monkeypatch):
    from pyfigures.gui import pfgui
    monkeypatch.setattr(pfgui._JournalDialog, "values", lambda self: {
        "journal": "nature", "column": "single", "min_dpi": 300, "min_font_pt": 7.0})
    captured = {}
    gui._show_report = lambda title, text: captured.setdefault(title, text)
    gui.check_resolution_report()
    assert captured.get("Print resolution")


def test_scale_bar_all_adds_bars(gui, monkeypatch):
    from pyfigures.gui import pfgui
    from batoolset.drawings.shapes.scalebar import ScaleBar
    monkeypatch.setattr(pfgui._ScaleBarAllDialog, "values", lambda self: {
        "bar_width_in_units": 10.0, "unit": "um", "placement": "bottom right"})
    gui.add_scale_bar_all()
    imgs = _images(gui)
    assert imgs, "expected panels in the figure"
    assert all(any(isinstance(a, ScaleBar) for a in (getattr(im, "annotations", None) or []))
               for im in imgs)


def test_enforce_min_font_runs(gui, monkeypatch):
    from pyfigures.gui import pfgui
    monkeypatch.setattr(pfgui.QInputDialog, "getDouble",
                        staticmethod(lambda *a, **k: (9.0, True)))
    gui.enforce_min_font_action()          # must not raise / must reload cleanly
    assert _images(gui)


def test_apply_journal_guidelines_runs(gui, monkeypatch):
    from pyfigures.gui import pfgui
    monkeypatch.setattr(pfgui._JournalDialog, "values", lambda self: {
        "journal": "nature", "column": "single", "min_dpi": 300,
        "min_font_pt": 7.0, "add_panel_labels": True})
    gui.apply_journal_guidelines_action()  # grouped figure -> should succeed
    assert _images(gui)


def test_remap_paths_rewrites_filenames(gui, monkeypatch):
    from pyfigures.gui import pfgui
    import shutil
    from batoolset.drawings.shapes.image2d import Image2D
    new_dir = tempfile.mkdtemp()
    for f in os.listdir(gui._dir):
        if f.endswith(".tif"):
            shutil.copy(os.path.join(gui._dir, f), os.path.join(new_dir, f))
    monkeypatch.setattr(pfgui._RemapPathsDialog, "values", lambda self: {
        "old_prefix": gui._dir, "new_prefix": new_dir})
    gui.remap_paths_action()
    names = [str(getattr(im, "filename", "")) for im in _images(gui)]
    assert any(new_dir in n for n in names)


# ---- dialog parsers (no full GUI) ----------------------------------
def test_journal_dialog_custom_width(qapp):
    from pyfigures.gui.pfgui import _JournalDialog
    d = _JournalDialog()
    d.journal_combo.setCurrentText("(custom width)")
    d.width_mm_edit.setText("85")
    v = d.values()
    assert v["width_mm"] == 85.0 and "journal" not in v


def test_journal_dialog_requires_width_when_custom(qapp):
    from pyfigures.gui.pfgui import _JournalDialog
    d = _JournalDialog()
    d.journal_combo.setCurrentText("(custom width)")
    with pytest.raises(ValueError):
        d.values()


def test_remap_dialog_requires_old_prefix(qapp):
    from pyfigures.gui.pfgui import _RemapPathsDialog
    d = _RemapPathsDialog()
    with pytest.raises(ValueError):
        d.values()
