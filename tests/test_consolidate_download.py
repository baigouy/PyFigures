"""Consolidation with "download remote images" (off by default): OMERO links
and remote OME-Zarr become local OME-Zarr stores of what the panel shows,
other links are saved as files; failures keep their link.

Uses the mock OMERO.web of test_omero and a local http server. Run with
PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import threading
import time

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

zarr = pytest.importorskip("zarr")

from batoolset import ome_zarr as Z  # noqa: E402
from batoolset.remote_download import download, local_name  # noqa: E402
from test_omero import DATA, O, server, fresh_sessions, fake_omero_py  # noqa: E402,F401  (fixtures)


@pytest.fixture
def web(tmp_path):
    """tmp_path/web served over http: a PNG and an OME-Zarr."""
    from PIL import Image
    root = tmp_path / "web"
    root.mkdir()
    rng = np.random.default_rng(3)
    Image.fromarray(rng.integers(0, 255, (30, 40, 3), dtype=np.uint8)).save(root / "photo.png")
    arr = np.zeros((2, 3, 64, 80), np.uint16)
    arr[0] = np.arange(80, dtype=np.uint16)[None, None, :] * 10
    arr[1] = 500
    Z.write_ome_zarr(str(root / "cells.zarr"), arr, axes="czyx", scale=[1.0, 0.5, 0.2, 0.2],
                     channel_names=["Membrane", "DNA"], channel_colors=["00FF00", "FF00FF"], levels=3)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{srv.server_address[1]}"
    finally:
        srv.shutdown()


def test_local_names(server, web):
    assert local_name(f"{server}/webclient/img_detail/1/#z=0") == "omero_image_1.ome.zarr"
    assert local_name(f"{server}/webclient/?show=image-7") == "omero_image_7.ome.zarr"
    assert local_name(f"{web}/cells.zarr#level=1") == "cells.zarr"
    assert local_name(f"{web}/photo.png") == "photo.png"


def test_omero_image_with_omero_py_is_saved_raw(server, fake_omero_py, tmp_path):
    O.login(server, "alice", "secret")
    url = f"{server}/webclient/img_detail/1/#t=1"
    dest = download(url, str(tmp_path / "b" / local_name(url)))
    meta, arr = Z.read_ome_zarr(dest)
    assert arr.dtype == np.uint16 and np.array_equal(arr, DATA[1][1])          # z h w c, all 16 bits
    assert meta["channel_names"] == ["Membrane", "DNA"] and meta["channel_colors"] == ["00FF00", "FF00FF"]
    assert meta["vx"] == pytest.approx(0.25) and meta["vz"] == pytest.approx(1.0)
    lo, hi = meta["channel_windows"][0]
    assert (lo, hi) == (DATA[1][..., 0].min(), DATA[1][..., 0].max())         # OMERO's display window
    assert zarr.open_group(dest, mode="r").attrs["pyfigures_source"] == url


def test_remote_zarr_and_plain_file(web, tmp_path):
    url = f"{web}/cells.zarr"
    dest = download(url, str(tmp_path / "b" / local_name(url)))
    m_remote, a_remote = Z.read_ome_zarr(url)
    m_local, a_local = Z.read_ome_zarr(dest)
    assert np.array_equal(a_remote, a_local) and m_local["vx"] == pytest.approx(m_remote["vx"])
    assert m_local["dimensions"] == m_remote["dimensions"]
    png = download(f"{web}/photo.png", str(tmp_path / "b" / "photo.png"))
    with open(png, "rb") as f, open(tmp_path / "web" / "photo.png", "rb") as g:
        assert f.read() == g.read()


def test_failed_download_keeps_the_link(web, tmp_path):
    from batoolset.files.tools import smartly_consolidate_files_to_reduce_dupes, consolidate_files2
    good = f"{web}/photo.png"
    bad = f"{web}/missing.png"
    names, consolidated = smartly_consolidate_files_to_reduce_dupes([good, bad], str(tmp_path / "f.files"),
                                                                    download_remote=True)
    failed = consolidate_files2(str(tmp_path / "f.files"), names, consolidated, download_remote=True)
    assert os.path.isfile(consolidated[0]) and consolidated[1] == bad
    assert [u for u, _ in failed] == [bad] and "404" in failed[0][1]
    # without the option nothing is downloaded and links stay
    names, consolidated = smartly_consolidate_files_to_reduce_dupes([good], str(tmp_path / "g.files"))
    assert consolidate_files2(str(tmp_path / "g.files"), names, consolidated) == [] and consolidated == [good]


def test_mcp_consolidation_off_by_default_and_on(qapp, server, web, tmp_path):
    from pyfigures import mcp_server as M
    omero = f"{server}/webclient/img_detail/1/#z=0&t=0"
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], omero)
    M.add_image(pyf, [0], f"{web}/photo.png")
    kept = str(tmp_path / "kept" / "f.pyf")
    os.makedirs(os.path.dirname(kept))
    r = json.loads(M.consolidate_figure(pyf, kept))
    text = open(kept, encoding="utf-8").read()
    assert "not_downloaded" not in r and "img_detail/1/" in text and f"{web}/photo.png" in text
    out = str(tmp_path / "local" / "f.pyf")
    os.makedirs(os.path.dirname(out))
    r = json.loads(M.consolidate_figure(pyf, out, download_remote=True))
    assert r["not_downloaded"] == []
    text = open(out, encoding="utf-8").read()
    assert "img_detail/1/" not in text and f"{web}/photo.png" not in text
    assert "omero_image_1.ome.zarr" in text and "photo.png" in text
    stores = [os.path.join(dp, d) for dp, ds, _ in os.walk(r["files_folder"]) for d in ds if d.endswith(".ome.zarr")]
    assert len(stores) == 1 and Z.is_ome_zarr(stores[0])
    meta, arr = Z.read_ome_zarr(stores[0])
    assert arr.shape == (40, 50, 2) and meta["vx"] == pytest.approx(0.25)
    png = str(tmp_path / "local.png")
    json.loads(M.export_figure(out, png, dpi=72))
    assert os.path.getsize(png) > 0


def test_recipe_download_remote(qapp, web, tmp_path):
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"output": str(tmp_path / "r.pyf"), "download_remote": True,
                                "rows": [[{"image": f"{web}/photo.png"}]]}), encoding="utf-8")
    with pytest.raises(RecipeError, match="consolidate"):
        build_figure_from_recipe(str(path))
    path.write_text(json.dumps({"output": str(tmp_path / "r.pyf"), "consolidate": True, "download_remote": True,
                                "rows": [[{"image": f"{web}/photo.png"}]]}), encoding="utf-8")
    res = build_figure_from_recipe(str(path))
    assert f"{web}/photo.png" not in open(str(tmp_path / "r.pyf"), encoding="utf-8").read()
    assert any(f == "photo.png" for _r, _d, fs in os.walk(res["consolidated"]) for f in fs)


@pytest.mark.parametrize("answer", [False, True])
def test_gui_asks_and_defaults_to_links(qapp, web, tmp_path, monkeypatch, answer):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "g.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], f"{web}/photo.png")
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.reload_state(pyf, append=False)
        # the real question box: No is its default button
        box_defaults = []
        real_exec = QMessageBox.exec

        def fake_exec(box):
            box_defaults.append(box.defaultButton() is box.button(QMessageBox.StandardButton.No))
            return QMessageBox.StandardButton.Yes if answer else QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        out = str(tmp_path / "out" / "g.pyf")
        os.makedirs(os.path.dirname(out))
        monkeypatch.setattr(pfgui, "saveFileDialog", lambda *a, **k: out)
        g.save_and_consolidate()
        t0 = time.time()
        while (getattr(g, "_active_img_loaders", None) or getattr(g, "_lazy_img_queue", None)) \
                and time.time() - t0 < 30:
            qapp.processEvents()
            time.sleep(0.01)
        monkeypatch.setattr(QMessageBox, "exec", real_exec)
        assert box_defaults == [True]
        text = open(out, encoding="utf-8").read()
        assert (f"{web}/photo.png" in text) is (not answer)
    finally:
        g._dirty = False
        g._stop_all_img_loaders()
        g.close()
