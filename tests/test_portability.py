"""Code paths that differ between Windows, macOS and Linux."""
from __future__ import annotations

import os


def test_fiji_cache_reset_never_deletes_a_folder_under_the_current_one(tmp_path, monkeypatch):
    """Without LOCALAPPDATA (macOS / Linux) the Windows JDK cache path used to
    become the relative 'cjdk/cache', deleted from the current folder."""
    import pytest
    ij_reader = pytest.importorskip("batoolset.IJ.ij_reader", exc_type=ImportError)   # the pyimagej reader (scyjava comes with pyimagej)
    home = tmp_path / "home"
    home.mkdir()
    work = tmp_path / "work"
    (work / "cjdk" / "cache").mkdir(parents=True)
    (home / ".cjdk" / "cache").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.chdir(work)
    ij_reader.reset_fiji_cache()
    assert (work / "cjdk" / "cache").is_dir()
    assert not (home / ".cjdk" / "cache").exists()


def test_ctrl_is_ctrl_on_every_platform(monkeypatch):
    """Qt maps Ctrl to Command on macOS by itself: returning Meta there (the
    physical Control key) made every shortcut Control+key and Cmd-click did
    not add to a selection (macOS CI failures of the Ctrl-click tests)."""
    import sys
    from qtpy.QtCore import Qt
    from pyfigures.gui import ctrl_key, ezfig, pfgui, annotation_editor
    for platform in ("darwin", "win32", "linux"):
        monkeypatch.setattr(sys, "platform", platform)
        assert ctrl_key.getCtrlModifier() == Qt.KeyboardModifier.ControlModifier
        assert ctrl_key.getCtrlModifierAsString() == "Ctrl"
    assert ezfig.getCtrlModifier is ctrl_key.getCtrlModifier
    assert annotation_editor.getCtrlModifier is ctrl_key.getCtrlModifier
    assert pfgui.getCtrlModifierAsString is ctrl_key.getCtrlModifierAsString


def test_replace_image_guide_compares_paths_not_strings(tmp_path):
    """The 'Replace a picture' guide took the same file written with the
    other slash for a new picture (Windows), so dropping the image the figure
    already had ended the guide."""
    from pyfigures.gui.show_me_how import _norm_file
    p = os.path.join(str(tmp_path), "sub", "a.tif")
    assert _norm_file(p) == _norm_file(p.replace(os.sep, "/"))
    assert _norm_file(p) != _norm_file(os.path.join(str(tmp_path), "sub", "b.tif"))
    assert _norm_file("@template@") == "@template@" and _norm_file(None) == "None"


def test_reading_a_posters_root_leaves_the_file_closed(tmp_path):
    """sniff_root_tag / is_photo_album used ET.iterparse(path) and returned
    at the first element: on Python 3.10 the file stayed open until garbage
    collection, so every save over that poster failed on Windows
    (PermissionError: Access is denied, in os.replace)."""
    import gc
    from pyfigures.poster.serialization import sniff_root_tag, is_photo_album, ALBUM_ROOT_TAG
    doc = tmp_path / "doc.pyfalbum"
    doc.write_text(f'<{ALBUM_ROOT_TAG} album_mode="1"><page/></{ALBUM_ROOT_TAG}>', encoding="utf-8")
    new = tmp_path / "new.tmp"
    gc.disable()
    try:
        assert sniff_root_tag(str(doc)) == ALBUM_ROOT_TAG
        assert is_photo_album(str(doc))
        new.write_text("<x/>", encoding="utf-8")
        os.replace(new, doc)                  # Windows refuses while a handle is open
    finally:
        gc.enable()
    assert sniff_root_tag(str(doc)) == "x" and not is_photo_album(str(doc))
    assert sniff_root_tag(str(tmp_path / "missing.pyfposter")) is None
