"""User 2026-11-23: "I tried to ctrl select the three images myself and drop them on empty
space but they were not gathered as a row neither and nothing happened". Only a single panel
could be dragged; several selected panels dropped on empty space now offer a new row of them."""
import os
import tempfile

import numpy as np
import pytest
from qtpy.QtCore import QPointF


@pytest.fixture
def sample_tif():
    from batoolset.img import Img
    p = os.path.join(tempfile.mkdtemp(), 'g.tif')
    Img(np.full((20, 20), 100, dtype=np.uint8), dimensions='hw').save(p)
    return p


@pytest.fixture
def figure(qapp, sample_tif, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Yes))
    from pyfigures.gui.pfgui import EZFIG_GUI
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group
    EZFIG_GUI.show_tips = lambda self: None
    gui = EZFIG_GUI()
    panel = gui.paint.EZFIG_panel
    imgs = [Image2D(sample_tif) for _ in range(5)]
    panel.shapes_to_draw = [Group(*imgs[:3], orientation='X'), Group(*imgs[3:], orientation='X')]
    panel.update_size()
    yield gui, panel, imgs
    gui._dirty = False
    gui.close()
    gui.deleteLater()


def _all_images(shapes):
    out = []
    for s in shapes:
        content = getattr(s, 'content', None)
        out.extend(_all_images(content) if isinstance(content, list) else [s])
    return out


def test_selected_panels_from_two_rows_make_a_row(figure):
    gui, panel, imgs = figure
    a, b, c, d, e = imgs
    row = panel.row_from_panels([a, d, e])
    assert len(panel.shapes_to_draw) == 2                 # the emptied row (d, e) is gone
    assert panel.shapes_to_draw[-1] is row and row.orientation == 'X'
    assert [s for s in row.content] == [a, d, e]
    assert panel.shapes_to_draw[0].content == [b, c]
    found = _all_images(panel.shapes_to_draw)
    assert len(found) == 5 and all(any(f is im for f in found) for im in imgs)   # none lost or doubled


def test_dropped_on_empty_space_the_menu_offers_it(figure, monkeypatch):
    gui, panel, imgs = figure
    a, b, c, d, e = imgs
    panel.selected_shape = [a, b, e]
    panel.initial_position = [s.topLeft() for s in panel.selected_shape]
    offered = []

    def run(event=None):
        acts = [x for x in panel.contextMenu.actions() if x.text().startswith("New row of the 3")]
        offered.append(len(acts))
        acts[0].trigger()
    monkeypatch.setattr(panel, "_run_context_menu_at_click", run)
    empty = QPointF(panel.shapes_to_draw[-1].getRect(all=True).right() + 500, 5000)
    panel._multi_drop_menu(None, empty)
    assert offered == [1]
    assert panel.shapes_to_draw[-1].content == [a, b, e]
    # dropped on a panel: nothing is offered (as before)
    panel.selected_shape = [c, d]
    panel.initial_position = [s.topLeft() for s in panel.selected_shape]
    offered.clear()
    on_a_panel = c.getRect(all=False).center()
    assert panel._multi_drop_menu(None, on_a_panel) is None and offered == []
