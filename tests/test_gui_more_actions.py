"""Main editor actions not covered elsewhere, checked for what they produce:
combine selected panels into a row / column, select all, Save and
Consolidate, and the read-only QC reports (image integrity, adjustment
ledger, fonts, changed source files).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from qtpy.QtWidgets import QDialog, QMessageBox


def _tif(path, val, shape=(40, 60)):
    from batoolset.img import Img
    Img(np.full(shape, val, np.uint8), dimensions="hw").save(str(path))
    return str(path)


def _imgs(g):
    from batoolset.drawings.shapes.image2d import Image2D
    out, stack = [], list(g.paint.EZFIG_panel.shapes_to_draw)
    while stack:
        s = stack.pop(0)
        if isinstance(s, Image2D):
            out.append(s)
        stack[0:0] = list(getattr(s, "content", None) or [])
    return out


@pytest.fixture
def ui(monkeypatch):
    from batoolset.GUI.customdialog import CustomDialog
    st = {"reports": [], "msg": []}

    def custom_exec(self, *a, **k):
        from qtpy.QtWidgets import QTextBrowser
        view = self.main_widget.findChild(QTextBrowser) if self.main_widget is not None else None
        st["reports"].append((self.windowTitle(), view.toPlainText() if view is not None else ""))
        return QDialog.Accepted
    monkeypatch.setattr(CustomDialog, "exec_", custom_exec, raising=False)
    monkeypatch.setattr(CustomDialog, "exec", custom_exec)
    for kind in ("warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, kind,
                            staticmethod(lambda *a, _k=kind, **kw: st["msg"].append((_k, a[1], a[2] if len(a) > 2 else ""))
                                         or QMessageBox.Ok))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    return st


@pytest.fixture
def gui(qapp, tmp_path, ui):
    from pyfigures import mcp_server as M
    from pyfigures.gui.pfgui import EZFIG_GUI
    src = tmp_path / "src"
    src.mkdir()
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=2, orientation="X", spacing=3)
    a = _tif(src / "a.tif", 60)
    M.add_image(pyf, [0], a)
    M.add_image(pyf, [0], a)                         # the same image twice: an integrity finding
    M.add_image(pyf, [1], _tif(src / "b.tif", 180))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    g._start_pyf_loader([pyf], append=False, reset_undo=True)
    t0 = time.time()
    while time.time() - t0 < 60:
        qapp.processEvents()
        ims = _imgs(g)
        if len(ims) == 3 and all(i.img is not None for i in ims) and not getattr(g, "_active_img_loaders", None) \
                and g.undo_stack:
            break
        time.sleep(0.005)
    for _ in range(5):
        qapp.processEvents()
    g._pyf = pyf
    g._src = str(src)
    yield g
    g._dirty = False
    g._stop_all_img_loaders()
    g.close()


@pytest.mark.parametrize("method,orientation", [("combine_in_new_row", "X"), ("combine_in_new_col", "Y")])
def test_combine_top_level_rows(gui, qapp, method, orientation):
    panel = gui.paint.EZFIG_panel
    rows = list(panel.shapes_to_draw)
    assert len(rows) == 2
    panel.selected_shape = list(rows)
    n_undo = len(gui.undo_stack)
    getattr(gui, method)()
    qapp.processEvents()
    assert len(panel.shapes_to_draw) == 1
    new = panel.shapes_to_draw[0]
    assert new.orientation == orientation and list(new.content) == rows
    assert len(_imgs(gui)) == 3
    t0 = time.time()
    while len(gui.undo_stack) == n_undo and time.time() - t0 < 3:   # checkpoint is debounced
        qapp.processEvents()
        time.sleep(0.01)
    assert gui._dirty


def test_combine_refuses_panels_inside_a_row(gui):
    panel = gui.paint.EZFIG_panel
    inner = list(panel.shapes_to_draw[0].content)
    panel.selected_shape = inner
    before = list(panel.shapes_to_draw)
    gui.combine_in_new_row()                      # used to raise ValueError (slot abort)
    assert panel.shapes_to_draw == before
    assert "right-click" in gui.statusBar().currentMessage()


def test_select_all(gui):
    gui.select_all()
    assert gui.paint.EZFIG_panel.selected_shape == list(gui.paint.EZFIG_panel.shapes_to_draw)


def test_save_and_consolidate(gui, monkeypatch, tmp_path, qapp):
    from pyfigures.gui import pfgui
    out = str(tmp_path / "packed" / "final.pyf")
    os.makedirs(os.path.dirname(out))
    monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
    gui.save_and_consolidate()
    t0 = time.time()
    while (getattr(gui, "_active_img_loaders", None) or getattr(gui, "_lazy_img_queue", None)) \
            and time.time() - t0 < 30:
        qapp.processEvents()
        time.sleep(0.01)
    folder = os.path.join(os.path.dirname(out), "final.files")
    assert os.path.isdir(folder)
    # one sub-folder per source file (keeps original names, no clashes)
    copied = sorted(f for _r, _d, fs in os.walk(folder) for f in fs)
    assert copied == ["a.tif", "b.tif"]               # a.tif used twice is copied once
    assert gui.current_file == out and not gui._dirty
    from pyfigures import mcp_server as M
    _tree, root = M._load(out)
    names = [M._decode(i.findtext("filename")) for i in root.iter("Image2D") if i.findtext("filename")]
    assert names and all(os.path.normcase(folder) in os.path.normcase(n) for n in names), names
    # the consolidated figure no longer depends on the originals
    import shutil
    shutil.rmtree(gui._src)
    assert "No raster" not in M.check_resolution(out, width_mm=80)


def test_integrity_report_finds_the_duplicate(gui, ui):
    gui.check_integrity_action()
    title, text = ui["reports"][-1]
    assert title == "Image integrity"
    assert "a.tif" in text and ("identical" in text.lower() or "duplicate" in text.lower())


def test_adjustment_ledger_report(gui, ui):
    gui.adjustment_ledger_action()
    title, text = ui["reports"][-1]
    assert title == "Adjustment provenance ledger" and "a.tif" in text


def test_fonts_report(gui, ui):
    gui.fonts_report_action()
    title, text = ui["reports"][-1]
    assert title.startswith("Fonts") and "bundled_families" in text


def test_changed_sources_report(gui, ui, monkeypatch, tmp_path):
    from pyfigures.gui import pfgui
    gui.current_file = None
    gui.check_source_changes_action()
    assert ui["msg"][-1][1] == "Save the figure first"
    out = str(tmp_path / "saved.pyf")
    gui.save_pyfigures(file=out)                      # writes the source snapshot
    gui.check_source_changes_action()
    assert ui["msg"][-1][1] == "Changed source files" and "unchanged" in ui["msg"][-1][2]
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: asked.append(a[2]) or QMessageBox.No))
    _tif(os.path.join(gui._src, "b.tif"), 7, (40, 61))   # change one source on disk
    gui.check_source_changes_action()                 # now reports it and offers to re-read
    assert asked and "b.tif" in asked[-1]
