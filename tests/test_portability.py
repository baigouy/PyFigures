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
