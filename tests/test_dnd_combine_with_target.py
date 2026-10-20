"""
Regression test for the drag-and-drop "combine with image below" options.

Dropping a file onto an EXISTING image/group should offer to merge the dropped
image(s) with that shape into a new row or column — not only "add as single".
Previously the To row / To column options appeared only when several files were
dropped at once (len(lst) > 1), so dropping a second image over the first gave
no way to lay them out side by side.
"""
import os
import tempfile

import numpy as np
import pytest


@pytest.fixture
def sample_tif():
    from batoolset.img import Img
    p = os.path.join(tempfile.mkdtemp(), 'combine.tif')
    Img(np.full((32, 48), 128, dtype=np.uint8), dimensions='hw').save(p)
    return p


@pytest.fixture
def gui(qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: QMessageBox.Yes))
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    yield g
    g._dirty = False  # avoid the unsaved-changes prompt on close in headless tests
    g.close()


def _labels(panel):
    return [a.text() for a in panel.contextMenu.actions()]


def test_no_combine_option_on_empty_canvas(gui, sample_tif):
    panel = gui.paint.EZFIG_panel
    gui.add_image_from_an_external_source_context_menu([sample_tif], [])
    labels = _labels(panel)
    assert any('single image' in l for l in labels)
    assert not any('with image below' in l for l in labels)


def test_combine_options_appear_over_existing_image(gui, sample_tif):
    from batoolset.drawings.shapes.image2d import Image2D
    panel = gui.paint.EZFIG_panel
    existing = Image2D(sample_tif)
    panel.shapes_to_draw.append(existing)

    gui.add_image_from_an_external_source_context_menu([sample_tif], [existing])
    labels = _labels(panel)
    assert any('To row (with image below)' in l for l in labels)
    assert any('To column (with image below)' in l for l in labels)
    # the plain single-image option is still offered
    assert any('single image' in l for l in labels)


def test_triggering_to_row_merges_target_and_dropped(gui, sample_tif, qtbot=None):
    from qtpy.QtWidgets import QApplication
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.group import Group
    panel = gui.paint.EZFIG_panel

    existing = Image2D(sample_tif)
    panel.shapes_to_draw.append(existing)
    panel.update_size()

    gui.add_image_from_an_external_source_context_menu([sample_tif], [existing])
    row_action = next(a for a in panel.contextMenu.actions()
                      if 'To row (with image below)' in a.text())
    gui.list = [sample_tif]
    row_action.trigger()

    # let series-resolution + background image load finish
    import time
    for _ in range(400):
        QApplication.processEvents()
        groups = [s for s in panel.shapes_to_draw if isinstance(s, Group)]
        if groups and not getattr(gui, '_active_img_loaders', []):
            break
        time.sleep(0.01)

    groups = [s for s in panel.shapes_to_draw if isinstance(s, Group)]
    loose = [s for s in panel.shapes_to_draw if isinstance(s, Image2D)]
    assert len(groups) == 1, f'expected one row group, got {len(groups)}'
    assert not loose, 'the original image should have been pulled into the row'
    imgs = [c for c in groups[0].content if isinstance(c, Image2D)]
    assert len(imgs) == 2
    assert groups[0].orientation == 'X'
    assert existing in groups[0].content
