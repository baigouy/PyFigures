"""
Regression test: merging two on-canvas shapes into a row/column (internal
drag-and-drop -> "To row"/"To column") must place the new group at the drop
target's position, not append it at the end of the figure.

create_row_with(item1, item2) / create_col_with(item1, item2) are wired from the
internal DnD menu as (drop_target, dragged_shape); the merged group should land
where drop_target was.
"""
import os
import tempfile

import numpy as np
import pytest


@pytest.fixture
def sample_tif():
    from batoolset.img import Img
    p = os.path.join(tempfile.mkdtemp(), 'g.tif')
    Img(np.full((20, 20), 100, dtype=np.uint8), dimensions='hw').save(p)
    return p


@pytest.fixture
def panel_with_four(qapp, sample_tif, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Yes))
    from pyfigures.gui.pfgui import EZFIG_GUI
    from batoolset.drawings.shapes.image2d import Image2D
    EZFIG_GUI.show_tips = lambda self: None
    gui = EZFIG_GUI()
    panel = gui.paint.EZFIG_panel
    imgs = [Image2D(sample_tif) for _ in range(4)]
    panel.shapes_to_draw = list(imgs)
    panel.update_size()
    yield gui, panel, imgs
    gui._dirty = False  # avoid the unsaved-changes prompt on close in headless tests
    gui.close()


def _layout(panel, imgs):
    from batoolset.drawings.shapes.group import Group
    tag = {id(im): 'ABCD'[i] for i, im in enumerate(imgs)}
    out = []
    for s in panel.shapes_to_draw:
        if isinstance(s, Group):
            out.append('(' + ''.join(tag.get(id(c), '?') for c in s.content) + ')')
        else:
            out.append(tag.get(id(s), '?'))
    return out


def test_row_lands_at_target_position_target_first(panel_with_four):
    gui, panel, imgs = panel_with_four
    A, B, C, D = imgs
    panel.create_row_with(A, B)          # drop B onto A
    assert _layout(panel, imgs) == ['(AB)', 'C', 'D']


def test_row_lands_at_target_position_target_after_dragged(panel_with_four):
    gui, panel, imgs = panel_with_four
    A, B, C, D = imgs
    panel.create_row_with(C, A)          # drop A onto C
    assert _layout(panel, imgs) == ['B', '(CA)', 'D']


def test_column_lands_at_target_position(panel_with_four):
    gui, panel, imgs = panel_with_four
    A, B, C, D = imgs
    panel.create_col_with(A, D)          # drop D onto A, vertical
    assert _layout(panel, imgs) == ['(AD)', 'B', 'C']
    assert panel.shapes_to_draw[0].orientation == 'Y'


def test_new_group_not_appended_at_end(panel_with_four):
    gui, panel, imgs = panel_with_four
    A, B, C, D = imgs
    panel.create_row_with(B, C)          # drop C onto B -> row should sit at B's slot (index 1)
    from batoolset.drawings.shapes.group import Group
    assert isinstance(panel.shapes_to_draw[1], Group)
    assert not isinstance(panel.shapes_to_draw[-1], Group)  # NOT at the end
