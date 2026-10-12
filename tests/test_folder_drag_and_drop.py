"""
Regression tests for folder drag-and-drop: dropping a folder loads every image
within it (recursively, images only) and offers the usual drop menu.
"""
import os
import tempfile

import numpy as np
import pytest

from batoolset.img import Img, is_image_file, list_image_files_in_folder


def _mk_img(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Img(np.full((8, 8), 100, dtype=np.uint8), dimensions='hw').save(path)


@pytest.fixture
def tree():
    """A folder with images (incl. a subfolder) plus non-image files to ignore."""
    root = tempfile.mkdtemp()
    _mk_img(os.path.join(root, 'b.png'))
    _mk_img(os.path.join(root, 'a.tif'))
    _mk_img(os.path.join(root, 'sub', 'c.jpg'))
    open(os.path.join(root, 'notes.txt'), 'w').write('x')
    open(os.path.join(root, 'fig.pyf'), 'w').write('x')
    open(os.path.join(root, 'scan.lifext'), 'w').write('x')   # forbidden sidecar
    return root


class TestIsImageFile:
    @pytest.mark.parametrize('name', ['a.png', 'a.TIF', 'x.lsm', 'y.czi', 'm.mp4', 'v.svg'])
    def test_accepts_images(self, name):
        assert is_image_file(name)

    @pytest.mark.parametrize('name', ['a.txt', 'a.pyf', 'a.lifext', 'a.db', 'a.xlsx'])
    def test_rejects_non_images(self, name):
        assert not is_image_file(name)

    def test_non_string(self):
        assert not is_image_file(None)
        assert not is_image_file(123)


class TestListImageFilesInFolder:
    def test_recursive_images_only_sorted(self, tree):
        names = [os.path.basename(f) for f in list_image_files_in_folder(tree)]
        assert names == ['a.tif', 'b.png', 'c.jpg']   # natural sort, no txt/pyf/lifext

    def test_non_recursive_skips_subfolders(self, tree):
        names = [os.path.basename(f) for f in list_image_files_in_folder(tree, recursive=False)]
        assert names == ['a.tif', 'b.png']

    def test_empty_or_missing(self):
        empty = tempfile.mkdtemp()
        assert list_image_files_in_folder(empty) == []
        assert list_image_files_in_folder(os.path.join(empty, 'nope')) == []
        assert list_image_files_in_folder(None) == []


class TestFolderDrop:
    @pytest.fixture
    def gui(self, qapp):
        from qtpy.QtWidgets import QMessageBox
        QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Yes)
        from pyfigures.gui.pfgui import EZFIG_GUI
        EZFIG_GUI.show_tips = lambda self: None
        g = EZFIG_GUI()
        yield g
        g._dirty = False
        g.close()

    @staticmethod
    def _drop(gui, path):
        from qtpy.QtCore import QMimeData, QUrl, QPointF, Qt
        from qtpy.QtGui import QDropEvent
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        try:
            ev = QDropEvent(QPointF(20, 20), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        except Exception:
            ev = QDropEvent(QPointF(20, 20), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        gui.dropEvent(ev)

    def test_folder_drop_queues_images_and_offers_menu(self, gui, tree):
        self._drop(gui, tree)
        from qtpy.QtWidgets import QApplication
        QApplication.processEvents()
        assert [os.path.basename(f) for f in gui.list] == ['a.tif', 'b.png', 'c.jpg']
        labels = [a.text() for a in gui.paint.EZFIG_panel.contextMenu.actions()]
        assert any('To row' in l for l in labels)
        assert any('To column' in l for l in labels)
        assert any('To panel' in l for l in labels)
        assert any('single image' in l for l in labels)

    def test_empty_folder_drop_is_noop(self, gui):
        empty = tempfile.mkdtemp()
        open(os.path.join(empty, 'readme.txt'), 'w').write('x')
        gui.list = []
        self._drop(gui, empty)
        from qtpy.QtWidgets import QApplication
        QApplication.processEvents()
        assert gui.list == []
