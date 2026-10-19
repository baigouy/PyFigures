"""OME-Zarr in figures: what the 2026-10-19 stress run found.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import shutil

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

pytest.importorskip("zarr")
from batoolset import ome_zarr as Z
from pyfigures import mcp_server as M


@pytest.fixture
def pyramid(tmp_path):
    a = (np.arange(256 * 320).reshape(256, 320) % 251).astype(np.uint16)
    return Z.write_ome_zarr(str(tmp_path / "img.zarr"), a, axes="yx", levels=3, scale=[0.5, 0.5])


def test_a_level_fragment_reads_that_level(pyramid):
    from batoolset.img import Img
    assert Img(pyramid + "#level=2").shape == (64, 80)
    assert Img(pyramid + "#level=0").shape == (256, 320)


def test_a_hash_in_a_real_file_name_still_works(tmp_path):
    from PIL import Image
    from batoolset.img import Img
    p = tmp_path / "a#b.png"
    Image.new("L", (12, 7), 9).save(p)
    assert Img(str(p)).shape[:2] == (7, 12)


def test_add_image_checks_ome_zarr_paths(tmp_path, pyramid):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    assert "Added" in M.add_image(pyf, [0], pyramid + "#level=1")
    for frag, words in (("#level=9", "out of range"), ("#level=-1", "#level=N"),
                        ("#level=abc", "#level=N"), ("#lvl=1", "#level=N")):
        res = M.add_image(pyf, [0], pyramid + frag)
        assert res.startswith("ERROR") and words in res, res
    empty = tmp_path / "empty.zarr"
    empty.mkdir()
    assert M.add_image(pyf, [0], str(empty)).startswith("ERROR")
    broken = Z.write_ome_zarr(str(tmp_path / "broken.zarr"), np.zeros((8, 8), np.uint8), axes="yx",
                              levels=1)
    shutil.rmtree(os.path.join(broken, "0"))
    assert M.add_image(pyf, [0], broken).startswith("ERROR")
    assert M.add_image(pyf, [0], "http://127.0.0.1:9/x.zarr").startswith("ERROR")
    # not there yet: allowed, with a warning (as for files)
    later = M.add_image(pyf, [0], str(tmp_path / "later.zarr"))
    assert "WARNING" in later and not later.startswith("ERROR")


def test_export_says_which_panels_could_not_be_loaded(tmp_path):
    from PIL import Image
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for name in ("a.png", "b.png"):
        Image.new("RGB", (40, 30), (200, 0, 0)).save(tmp_path / name)
        M.add_image(pyf, [0], str(tmp_path / name))
    os.remove(tmp_path / "b.png")
    res = json.loads(M.export_figure(pyf, str(tmp_path / "out.png"), dpi=72))
    assert "b.png" in res["warning"] and "a.png" not in res["warning"]


def test_unloaded_images_ignores_console_formatted_lines():
    from pyfigures.mcp_tools.export import _unloaded_images
    log = ("ERROR - x - image2d.py - __init__ - line 404 - could not load image C:\\d\\b.png\n"
           "ERROR    could not load image                image2d.py:404\n")
    assert _unloaded_images(log) == ["C:\\d\\b.png"]
