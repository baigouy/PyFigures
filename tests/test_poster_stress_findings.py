"""Poster / album tools: what the 2026-10-19 stress run found (bad arguments
must give one clear message; scientific images must load).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stderr, redirect_stdout

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import mcp_server as M
from pyfigures.mcp_tools import poster as poster_tools


def _run_inproc(op_args, timeout=120):
    from pyfigures.poster import poster_headless
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = poster_headless._main(list(op_args))
        except SystemExit as exc:
            code = exc.code or 2
    if code != 0:
        return False, err.getvalue().strip() or f"exit {code}"
    return True, json.loads(out.getvalue())


@pytest.fixture(autouse=True)
def inproc(qapp, monkeypatch):
    monkeypatch.setattr(poster_tools, "_run_poster_op", _run_inproc)


def ok(result):
    assert not result.startswith("ERROR"), result
    return json.loads(result)


def err(result, *needles):
    assert result.startswith("ERROR: "), result
    assert not result.startswith("ERROR: ERROR"), result
    for word in ("IndexError", "ValueError", "usage:", "Traceback"):
        assert word not in result, result
    for n in needles:
        assert n.lower() in result.lower(), result
    return result


@pytest.fixture
def photo(tmp_path):
    from PIL import Image
    p = tmp_path / "p.png"
    Image.new("RGB", (120, 80), (200, 30, 30)).save(p)
    return str(p)


@pytest.fixture
def poster(tmp_path, photo):
    p = str(tmp_path / "doc.pyfposter")
    ok(M.create_poster(p))
    ok(M.add_poster_image(p, photo))
    ok(M.add_poster_image(p, photo))
    ok(M.add_poster_text(p, html="<b>Title</b>"))
    return p


def test_scientific_tiffs_load_on_a_poster(tmp_path, poster):
    import tifffile
    rng = np.random.default_rng(0)
    f = rng.random((60, 80)).astype(np.float32)
    f[:5] = np.nan
    f[5:8] = np.inf
    files = {"float.tif": f,
             "u32.tif": rng.integers(0, 2 ** 31, (60, 80)).astype(np.uint32),
             "u16.tif": rng.integers(0, 65535, (60, 80)).astype(np.uint16),
             "stack.tif": rng.integers(0, 4000, (5, 60, 80)).astype(np.uint16)}
    for name, a in files.items():
        tifffile.imwrite(tmp_path / name, a)
        shape = ok(M.add_poster_image(poster, str(tmp_path / name)))
        assert shape["kind"] == "image"
    out = str(tmp_path / "out.png")
    ok(M.render_poster(poster, out, dpi=30))
    from pyfigures.poster.poster_shapes import load_pixmap
    pm = load_pixmap(str(tmp_path / "float.tif"))
    assert (pm.width(), pm.height()) == (80, 60)
    bad = tmp_path / "notes.png"
    bad.write_text("not an image")
    err(M.add_poster_image(poster, str(bad)), "cannot read")


def test_bad_arguments_give_one_clear_message(tmp_path, poster, photo):
    err(M.add_poster_image(poster, photo, page=7), "page 7")
    err(M.arrange_poster_grid(poster, indices="99"), "out of range")
    err(M.arrange_poster_grid(poster, indices="a,b"), "indices")
    err(M.arrange_poster_grid(poster, indices="-1"), "out of range")
    err(M.arrange_poster_grid(poster, indices="2"), "text box")
    err(M.arrange_poster_grid(poster, columns=0), "columns")
    err(M.arrange_poster_grid(poster, gap_mm=-1), "gap")
    err(M.arrange_poster_arc(poster, 100, 100, 0), "radius")
    err(M.remove_poster_image(poster, 999), "out of range")
    err(M.add_poster_text(poster, html="<p> </p>"), "empty")
    ok(M.set_poster_background(poster, photo))
    err(M.adjust_poster_background(poster, zoom=0), "zoom")
    err(M.adjust_poster_background(poster, zoom=-2), "zoom")
    err(M.ungroup_poster_images(poster, 0), "not in a group")
    err(M.set_poster_image_frame(poster, 0, frame="sparkly"))
    err(M.create_poster(str(tmp_path / "x.pyfposter"), page_preset="B17"), "unknown page preset")
    err(M.create_poster(str(tmp_path / "y.pyfposter"), page_preset=None, page_width_mm=100), "both")


def test_a_mistyped_path_is_not_a_new_poster(tmp_path, photo):
    missing = str(tmp_path / "typo.pyfposter")
    err(M.list_poster_images(missing), "no such poster")
    err(M.add_poster_image(missing, photo), "no such poster")
    assert not os.path.exists(missing)
    corrupt = tmp_path / "corrupt.pyfposter"
    corrupt.write_text("<poster><page>", encoding="utf-8")
    err(M.list_poster_pages(str(corrupt)), "cannot read")


def test_create_checks_the_extension_and_knows_more_page_sizes(tmp_path):
    err(M.create_poster(str(tmp_path / "fig.pyf")), ".pyfposter")
    for preset, size in (("A5", (148.0, 210.0)), ("letter", (215.9, 279.4)), ("A6", (105.0, 148.0))):
        doc = ok(M.create_poster(str(tmp_path / f"{preset}.pyfposter"), page_preset=preset))
        assert (doc["page_width_mm"], doc["page_height_mm"]) == size
    album = ok(M.create_album(str(tmp_path / "small.pyfalbum"), page_preset="A5"))
    assert album["ok"]
    from pyfigures.poster import poster_recipe, poster_window
    assert poster_recipe.PAGE_PRESETS is poster_window.PAGE_PRESETS


def test_web_export_makes_its_folder(tmp_path, poster):
    out = tmp_path / "new" / "folder" / "index.html"
    ok(M.export_poster_web(poster, str(out), dpi=30))
    assert out.is_file()
