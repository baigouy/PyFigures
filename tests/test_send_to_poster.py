"""Tools > Send this figure to the poster designer (22 Oct report: "is direct
transfer from PyFigures to the poster tool possible?"): the saved .pyf is
placed on the poster as when it is dropped there, linked for vector exports.
MCP / recipe counterparts: add_poster_image and poster recipes take a .pyf.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture
def gui(qapp, tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    p = str(tmp_path / "a.tif")
    Img((np.random.default_rng(0).random((60, 80)) * 255).astype(np.uint8), dimensions="hw").save(p)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    add_image(pyf, [0], p)
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    g._mark_clean()
    yield g
    pw = getattr(g, "_poster_window", None)
    if pw is not None:
        pw.canvas.mark_saved()
        pw.close()
    g._dirty = False
    g.close()
    qapp.processEvents()


def _figures_on_poster(g):
    from pyfigures.poster.poster_shapes import PosterImage
    pw = getattr(g, "_poster_window", None)
    if pw is None:
        return []
    return [s for s in pw.canvas.shapes_to_draw if isinstance(s, PosterImage) and s.source_pyf]


def test_a_saved_figure_goes_onto_the_poster(qapp, gui):
    shape = gui.send_to_poster_designer()
    assert shape is not None and gui._poster_window.isVisible()
    assert [os.path.normcase(s.source_pyf) for s in _figures_on_poster(gui)] == [os.path.normcase(gui.current_file)]
    gui.send_to_poster_designer()                       # again: the same poster window, a second copy
    assert len(_figures_on_poster(gui)) == 2


def test_unsaved_work_is_saved_first_or_nothing_happens(qapp, gui, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    gui._mark_dirty()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Cancel)
    assert gui.send_to_poster_designer() is None and _figures_on_poster(gui) == []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Save)
    saved = []
    monkeypatch.setattr(gui, "save_pyfigures", lambda *a, **k: saved.append(1) or True)
    assert gui.send_to_poster_designer() is not None and saved == [1]
    assert len(_figures_on_poster(gui)) == 1


def test_tools_menu_entry(qapp, gui):
    act = next(a for m in gui.menuBar.actions() if m.text() == "Tools"
               for a in m.menu().actions() if a.text() == "Send this figure to the poster designer")
    act.trigger()
    assert len(_figures_on_poster(gui)) == 1
