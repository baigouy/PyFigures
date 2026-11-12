"""
Regression tests for the file-safety cluster: dirty tracking, window title,
save-before-discard prompt, and Save writing back to the current file.
"""
import os
import tempfile

import numpy as np
import pytest


@pytest.fixture
def sample_tif():
    from batoolset.img import Img
    p = os.path.join(tempfile.mkdtemp(), 's.tif')
    Img(np.full((16, 16), 90, dtype=np.uint8), dimensions='hw').save(p)
    return p


@pytest.fixture
def gui(qapp):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    return EZFIG_GUI()   # not shown -> closeEvent/os._exit is never triggered


def _add_edit(gui, tif):
    from batoolset.drawings.shapes.image2d import Image2D
    gui.paint.EZFIG_panel.shapes_to_draw.append(Image2D(tif))
    gui.save_state(show_popup=False)


def test_fresh_launch_is_untitled_and_clean(gui):
    assert gui._dirty is False
    assert 'Untitled' in gui.windowTitle()
    assert '•' not in gui.windowTitle()   # no bullet


def test_edit_marks_dirty_with_bullet(gui, sample_tif):
    _add_edit(gui, sample_tif)
    assert gui._dirty is True
    assert '•' in gui.windowTitle()


def test_save_clears_dirty_and_shows_filename(gui, sample_tif):
    _add_edit(gui, sample_tif)
    pyf = os.path.join(tempfile.mkdtemp(), 'figA.pyf')
    gui.current_file = pyf
    assert gui.save_pyfigures() is True
    assert os.path.isfile(pyf)
    assert gui._dirty is False
    assert 'figA.pyf' in gui.windowTitle()
    assert '•' not in gui.windowTitle()


def test_save_writes_back_to_current_file_without_dialog(gui, sample_tif, monkeypatch):
    pyf = os.path.join(tempfile.mkdtemp(), 'fig.pyf')
    gui.current_file = pyf
    gui.save_pyfigures()                      # first write
    _add_edit(gui, sample_tif)
    assert gui._dirty is True

    def _boom(*a, **k):
        raise AssertionError('Save must not prompt when current_file is set')
    monkeypatch.setattr('pyfigures.gui.pfgui.saveFileDialog', _boom)
    assert gui.save_pyfigures() is True
    assert gui._dirty is False


def _saved_figure(gui, tif, name):
    pyf = os.path.join(tempfile.mkdtemp(), name)
    _add_edit(gui, tif)
    gui.current_file = pyf
    gui.save_pyfigures()
    return pyf


def test_one_pyf_dropped_on_an_empty_canvas_is_opened(gui, sample_tif, monkeypatch):
    """Drag a .pyf onto an empty window, edit it (through the chat), Save: it asked where
    to save, as for a new figure (2026-11-12). It writes back to the dropped file now."""
    pyf = _saved_figure(gui, sample_tif, 'dropped.pyf')
    gui.paint.EZFIG_panel.shapes_to_draw.clear()
    gui.current_file = None
    gui.add_image_from_an_external_source_context_menu([pyf], None)
    assert gui.wait_for_images(timeout=60)
    assert gui.current_file == pyf and gui._dirty is False
    assert len(gui.paint.EZFIG_panel.shapes_to_draw) == 1
    _add_edit(gui, sample_tif)

    def _boom(*a, **k):
        raise AssertionError('Save must not prompt for a dropped-and-opened figure')
    monkeypatch.setattr('pyfigures.gui.pfgui.saveFileDialog', _boom)
    assert gui.save_pyfigures() is True


def test_a_pyf_dropped_onto_a_figure_is_still_a_new_composition(gui, sample_tif):
    pyf = _saved_figure(gui, sample_tif, 'other.pyf')
    gui.current_file = None                      # an unsaved figure is on the canvas
    gui.add_image_from_an_external_source_context_menu([pyf], None)
    assert gui.wait_for_images(timeout=60)
    assert gui.current_file is None and gui._dirty is True


def test_save_as_starts_in_the_figure_folder(gui, sample_tif, monkeypatch):
    """Save As opened in the home folder although the figure had a file (2026-11-12)."""
    pyf = _saved_figure(gui, sample_tif, 'here.pyf')
    seen = {}

    def dialog(parent_window=None, path=None, **kw):
        seen['path'] = path
        return None                                   # cancelled
    monkeypatch.setattr('pyfigures.gui.pfgui.saveFileDialog', dialog)
    assert not gui.save_pyfigures(file=None)
    assert seen['path'] == pyf and gui.current_file == pyf      # cancelling keeps the file


def test_written_pyf_is_utf8(gui, sample_tif):
    pyf = os.path.join(tempfile.mkdtemp(), 'u.pyf')
    gui.current_file = pyf
    gui.save_pyfigures()
    with open(pyf, 'rb') as f:
        f.read().decode('utf-8')              # must not raise


class TestSaveBeforeDiscard:
    def test_clean_never_prompts(self, gui, monkeypatch):
        from qtpy.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, 'warning',
                            staticmethod(lambda *a, **k: pytest.fail('prompted while clean')))
        assert gui._maybe_save_before_discard('x') is True

    def test_cancel_blocks(self, gui, sample_tif, monkeypatch):
        from qtpy.QtWidgets import QMessageBox
        _add_edit(gui, sample_tif)
        monkeypatch.setattr(QMessageBox, 'warning',
                            staticmethod(lambda *a, **k: QMessageBox.Cancel))
        assert gui._maybe_save_before_discard('x') is False

    def test_discard_proceeds(self, gui, sample_tif, monkeypatch):
        from qtpy.QtWidgets import QMessageBox
        _add_edit(gui, sample_tif)
        monkeypatch.setattr(QMessageBox, 'warning',
                            staticmethod(lambda *a, **k: QMessageBox.Discard))
        assert gui._maybe_save_before_discard('x') is True
        assert gui._dirty is True             # discard does not clear the flag itself

    def test_save_choice_saves_then_proceeds(self, gui, sample_tif, monkeypatch):
        from qtpy.QtWidgets import QMessageBox
        pyf = os.path.join(tempfile.mkdtemp(), 'p.pyf')
        gui.current_file = pyf
        _add_edit(gui, sample_tif)
        monkeypatch.setattr(QMessageBox, 'warning',
                            staticmethod(lambda *a, **k: QMessageBox.Save))
        assert gui._maybe_save_before_discard('x') is True
        assert gui._dirty is False
        assert os.path.isfile(pyf)


def test_new_fig_resets_to_untitled_clean(gui, sample_tif, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    _add_edit(gui, sample_tif)
    # user chooses Discard on the unsaved-changes prompt
    monkeypatch.setattr(QMessageBox, 'warning',
                        staticmethod(lambda *a, **k: QMessageBox.Discard))
    gui.new_fig()
    assert gui.current_file is None
    assert gui._dirty is False
    assert 'Untitled' in gui.windowTitle()
    assert not gui.paint.EZFIG_panel.shapes_to_draw
