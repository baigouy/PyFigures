"""OME-Zarr images (local .zarr folders and http(s) URLs).

- batoolset.ome_zarr: metadata, pyramid level choice, axis reordering, pixel
  sizes in µm, channel colours -> LUTs, the requests-based HTTP store
  (served here by a local http.server, no internet needed)
- PyFigures: Img / MCP add_image + inspect_ome_zarr + render, recipes, the
  source helpers, consolidation (URLs kept, local stores copied), GUI action

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import threading

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

zarr = pytest.importorskip("zarr")
from batoolset import ome_zarr as Z  # noqa: E402


def _sample(path, levels=3):
    """c=2, z=3, y=64, x=80 uint16; channel 0 ramps along x, channel 1 is constant."""
    arr = np.zeros((2, 3, 64, 80), np.uint16)
    arr[0] = np.arange(80, dtype=np.uint16)[None, None, :] * 10
    arr[1] = 500
    Z.write_ome_zarr(path, arr, axes="czyx", scale=[1.0, 0.5, 0.2, 0.2],
                     channel_names=["Membrane", "DNA"], channel_colors=["00FF00", "FF00FF"], levels=levels)
    return path


@pytest.fixture
def local_zarr(tmp_path):
    return _sample(str(tmp_path / "cells.ome.zarr"))


@pytest.fixture
def served(tmp_path):
    """Serve tmp_path over http; yields the base URL."""
    _sample(str(tmp_path / "remote.zarr"))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# batoolset.ome_zarr
# ---------------------------------------------------------------------------
def test_describe_and_read_local(local_zarr):
    info = Z.describe(local_zarr)
    assert info["axes"] == ["c", "z", "y", "x"] and len(info["levels"]) == 3
    assert info["levels"][1]["shape"] == [2, 3, 32, 40]
    assert [c["label"] for c in info["channels"]] == ["Membrane", "DNA"]
    meta, arr = Z.read_ome_zarr(local_zarr)
    assert arr.shape == (3, 64, 80, 2) and meta["dimensions"] == "dhwc"        # c moved last
    assert meta["vx"] == pytest.approx(0.2) and meta["vz"] == pytest.approx(0.5)
    assert meta["ome_zarr"]["level"] == 0 and meta["channel_names"] == ["Membrane", "DNA"]
    assert np.array_equal(arr[0, 0, :, 0], np.arange(80) * 10)                 # x ramp kept on w
    lut = meta["LUTs"][1]                                                     # magenta ramp
    assert lut.shape == (3, 256) and tuple(lut[:, 255]) == (255, 0, 255) and tuple(lut[:, 0]) == (0, 0, 0)


def test_level_choice_and_fragment(local_zarr):
    meta, arr = Z.read_ome_zarr(local_zarr + "#level=2")
    assert arr.shape == (3, 16, 20, 2) and meta["vx"] == pytest.approx(0.8)  # pixel size x 4
    levels = Z.describe(local_zarr)["levels"]
    # 2*3*64*80*2 bytes = 61 kB at level 0: a 20 kB budget picks level 1 (15 kB)
    assert Z.choose_level(levels, max_bytes=20_000, axes=["c", "z", "y", "x"]) == 1
    assert Z.choose_level(levels, max_side=30, axes=["c", "z", "y", "x"]) == 2
    assert Z.choose_level(levels, max_bytes=10, axes=["c", "z", "y", "x"]) == 2   # nothing fits: smallest
    assert Z.level_size(local_zarr) == (0, 80, 64)
    assert Z.level_size(local_zarr + "#level=1") == (1, 40, 32)
    with pytest.raises(ValueError):
        Z.read_ome_zarr(local_zarr, level=7)


def test_plain_zarr_is_not_ome(tmp_path):
    p = str(tmp_path / "plain.zarr")
    g = zarr.open_group(p, mode="w")
    g.create_array("mask", data=np.ones((4, 4), np.uint8))
    assert Z.is_zarr_path(p) and not Z.is_ome_zarr(p)
    with pytest.raises(ValueError):
        Z.describe(p)


def test_img_reads_ome_zarr_local_and_over_http(local_zarr, served):
    from batoolset.img import Img
    im = Img(local_zarr)
    assert im.shape == (3, 64, 80, 2) and im.metadata["dimensions"] == "dhwc"
    url = served + "/remote.zarr"
    assert Z.is_url(url) and Z.is_ome_zarr(url)
    im2 = Img(url + "#level=1")
    assert im2.shape == (3, 32, 40, 2) and im2.metadata["vx"] == pytest.approx(0.4)
    assert Z.describe(url)["levels"][0]["shape"] == [2, 3, 64, 80]


# ---------------------------------------------------------------------------
# PyFigures
# ---------------------------------------------------------------------------
def test_source_helpers(local_zarr, tmp_path):
    from pyfigures.path_resolution import is_remote, source_exists
    assert is_remote("https://x.org/a.zarr") and not is_remote("C:/a.zarr")
    assert source_exists(local_zarr) and source_exists(local_zarr + "#level=1")
    assert source_exists("https://example.org/img.zarr")
    assert not source_exists(str(tmp_path / "missing.zarr")) and not source_exists("")


def test_mcp_add_inspect_render(served, tmp_path):
    import pyfigures.mcp_server as M
    url = served + "/remote.zarr"
    info = json.loads(M.inspect_ome_zarr(url))
    assert info["default_level"] == 0 and info["default_level_size_px"] == [80, 64]
    assert info["levels"][1]["pixel_size_x_um"] == pytest.approx(0.4)
    assert M.inspect_ome_zarr(served + "/nope.zarr").startswith("ERROR")
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], url)
    M.add_image(pyf, [0], url + "#level=1")
    imgs = json.loads(M.list_images(pyf))
    assert [i["path"] for i in imgs] == [url, url + "#level=1"]
    M.configure_image(pyf, [0], 0, projection="max")
    png = M.render_preview(pyf, dpi=72)
    from PIL import Image
    import io
    im = np.asarray(Image.open(io.BytesIO(png.data)).convert("RGB"))
    assert im.shape[1] > 50 and im[..., 1].max() > 100                       # green membrane ramp drawn


def test_recipe_with_ome_zarr_url(served, tmp_path):
    import pyfigures.mcp_server as M
    from pyfigures.recipe import build_figure_from_recipe
    url = served + "/remote.zarr"
    recipe = tmp_path / "r.json"
    recipe.write_text(json.dumps({"output": "zfig.pyf", "rows": [[{"image": url + "#level=1"}]]}),
                      encoding="utf-8")
    build_figure_from_recipe(str(recipe))
    assert [i["path"] for i in json.loads(M.list_images(str(tmp_path / "zfig.pyf")))] == [url + "#level=1"]


def test_consolidation_keeps_urls_and_copies_local_stores(tmp_path, served):
    from batoolset.files.tools import smartly_consolidate_files_to_reduce_dupes, consolidate_files2
    local = _sample(str(tmp_path / "data" / "local.zarr"))
    url = served + "/remote.zarr"
    dest = str(tmp_path / "bundle.files")
    names, consolidated = smartly_consolidate_files_to_reduce_dupes([url, local], dest)
    assert consolidated[0] == url and consolidated[1] != local
    consolidate_files2(dest, names, consolidated)
    assert os.path.isdir(consolidated[1]) and Z.is_ome_zarr(consolidated[1])


def test_gui_add_image_from_url(qapp, served, monkeypatch):
    import time
    from qtpy.QtWidgets import QInputDialog, QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    url = served + "/remote.zarr"
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (url, True)))
    picked = {}

    def get_item(parent, title, label, items, current, editable):
        picked["items"], picked["current"] = list(items), current
        return items[1], True                                                  # choose level 1
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(get_item))
    msgs = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: msgs.append(a[1])))
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    g.show()
    try:
        g.add_image_from_url_action()
        t0 = time.time()
        while time.time() - t0 < 30 and not g.paint.EZFIG_panel.shapes_to_draw:
            qapp.processEvents()
            time.sleep(0.01)
        assert not msgs
        assert picked["items"][0].startswith("Level 0: 80 × 64 px, 0.2 µm/px") and picked["current"] == 0
        from batoolset.lists.tools import flatten_iterable
        imgs = [s for s in flatten_iterable(g.paint.EZFIG_panel.shapes_to_draw) if hasattr(s, "filename")]
        assert [i.filename for i in imgs] == [url + "#level=1"] and imgs[0].img.shape[1:3] == (32, 40)
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (served + "/nope.zarr", True)))
        g.add_image_from_url_action()
        assert msgs and msgs[-1] == "Cannot read OME-Zarr"
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
