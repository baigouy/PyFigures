"""A real-file walk found it (30 October 2026): a figure whose images had
moved opened with every panel silently empty. The editor now says which
files are missing and offers Remap image paths with their folder filled in."""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from PIL import Image  # noqa: E402

import pyfigures.mcp_server as M  # noqa: E402
from test_dnd_main_editor import ui, gui, _wait  # noqa: F401,E402


def _figure_with_moved_images(tmp_path):
    old = tmp_path / "old_place"
    old.mkdir()
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for name in ("a.png", "b.png"):
        Image.fromarray(np.full((30, 30), 99, np.uint8)).save(old / name)
        M.add_image(pyf, [0], str(old / name))
    # gone, not just renamed next to the figure (the opener finds files that
    # moved along with the .pyf by themselves)
    import shutil
    shutil.rmtree(old)
    return pyf, str(old), None


def test_opening_a_figure_with_moved_images_says_so(gui, qapp, tmp_path):
    pyf, old, _new = _figure_with_moved_images(tmp_path)
    gui._start_pyf_loader([pyf], append=False, reset_undo=True)
    assert gui.wait_for_images(timeout=60)
    for _ in range(10):          # (_wait would wait for pixels these panels never get)
        qapp.processEvents()
    missing = gui._missing_image_files()
    assert sorted(os.path.basename(m) for m in missing) == ["a.png", "b.png"]
    assert "2 image file(s) not found" in gui.statusBar().currentMessage()
    # the loader's failure marker was set as the image: no qimage, every
    # repaint raised AttributeError ('NoneType' object has no attribute 'cacheKey')
    from test_dnd_main_editor import _all_images
    assert all(i.img is None for i in _all_images(gui)), [type(i.img) for i in _all_images(gui)]
    gui.paint.EZFIG_panel.repaint()


def test_the_warning_offers_remap_with_the_old_folder(gui, qapp, tmp_path, monkeypatch):
    pyf, old, new = _figure_with_moved_images(tmp_path)
    import pyfigures.gui.pfgui as P
    from qtpy.QtWidgets import QMessageBox
    monkeypatch.setattr(P, "_nobody_to_ask", lambda: False)
    shown, asked = [], []

    def fake_exec(box):
        shown.append(box.text())
        box._clicked = [b for b in box.buttons() if b.text().startswith("Remap")][0]

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: box._clicked)
    monkeypatch.setattr(type(gui), "remap_paths_action", lambda self, old_prefix="": asked.append(old_prefix))
    gui.reload_state(pyf, append=False)
    assert shown and "a.png" in shown[0] and "could not be found" in shown[0]
    assert [os.path.normcase(os.path.normpath(a)) for a in asked] == [os.path.normcase(os.path.normpath(old))]
    # the same figure again in the same session: no second dialog
    gui.reload_state(pyf, append=False)
    assert len(shown) == 1


def test_a_file_there_but_unreadable_is_reported_too(gui, tmp_path):
    """An online-only OneDrive file that cannot be downloaded (or a damaged
    file) exists but does not load: its panel was silently empty."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    bad = tmp_path / "damaged.png"
    Image.fromarray(np.full((30, 30), 99, np.uint8)).save(bad)
    M.add_image(pyf, [0], str(bad))
    bad.write_bytes(b"not an image at all")            # damaged after it was placed
    gui.reload_state(pyf, append=False)
    assert gui._missing_image_files() == []
    assert [os.path.basename(f) for f in gui._missing_image_files(unreadable=True)] == ["damaged.png"]
    assert "1 could not be read" in gui.statusBar().currentMessage()


def test_cloud_placeholder_note_is_empty_for_a_normal_file(tmp_path):
    from pyfigures.mcp_tools.core import cloud_placeholder_note
    f = tmp_path / "x.png"
    f.write_bytes(b"x")
    assert cloud_placeholder_note(str(f)) == ""
    assert cloud_placeholder_note(str(tmp_path / "nope.png")) == ""


def test_no_warning_when_every_image_is_there(gui, tmp_path):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    img = tmp_path / "a.png"
    Image.fromarray(np.full((30, 30), 99, np.uint8)).save(img)
    M.add_image(pyf, [0], str(img))
    gui.reload_state(pyf, append=False)
    assert gui._missing_image_files() == []


def test_relinking_missing_images_one_by_one_asks_only_once(gui, qapp, tmp_path, monkeypatch):
    """2026-11-05: the chat replaced 9 missing images one by one and the user had
    to close 'Images not found' after each one: fewer missing files than already
    reported means they are being fixed, so only the status bar says what is left."""
    import pyfigures.gui.pfgui as P
    from qtpy.QtWidgets import QMessageBox
    monkeypatch.setattr(P, "_nobody_to_ask", lambda: False)
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()))
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda box: None)
    missing = [f"C:/gone/{c}.tif" for c in "abc"]
    monkeypatch.setattr(type(gui), "_missing_image_files",
                        lambda self, unreadable=False: [] if unreadable else list(missing))
    gui._missing_warned_for = None                       # as after opening a figure
    gui._warn_missing_images()
    assert len(shown) == 1 and "3 image file(s)" in shown[0]
    for _ in range(2):                                   # relinked one at a time
        missing.pop(0)
        gui._warn_missing_images()
        assert len(shown) == 1
        assert f"{len(missing)} image file(s) still missing" in gui.statusBar().currentMessage()
    missing.append("C:/gone/new.tif")                    # a file not reported before: say it
    gui._warn_missing_images()
    assert len(shown) == 2 and "new.tif" in shown[1]
    missing.clear()
    gui._warn_missing_images()
    assert len(shown) == 2
