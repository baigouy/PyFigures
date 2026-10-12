"""
Tests for the MCP-side tools added for GUI<->MCP parity:
templatify_figure, export_review / list_review_comments / import_review_comments,
export_video, consolidate_figure, and simulate_color_blindness (+ the cvd module).
"""
from __future__ import annotations

import json
import os
import tempfile

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")
try:
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtWidgets import QApplication  # noqa: F401
    _QT = True
except Exception:
    _QT = False

needs_qt = pytest.mark.skipif(not _QT, reason="Qt not available")

from pyfigures.mcp_server import (
    create_figure, add_image, describe_figure, _load, _decode,
    templatify_figure, export_review, list_review_comments,
    import_review_comments, consolidate_figure, export_video,
    simulate_color_blindness,
)


def _tif(path, val, rgb=False):
    from batoolset.img import Img
    if rgb:
        arr = np.zeros((20, 20, 3), np.uint8)
        arr[..., 0] = val
        Img(arr, dimensions='hwc').save(path)
    else:
        Img(np.full((20, 20), val, np.uint8), dimensions='hw').save(path)
    return path


@pytest.fixture
def grouped(tmp_path):
    a = _tif(str(tmp_path / "a.tif"), 80)
    b = _tif(str(tmp_path / "b.tif"), 200)
    p = str(tmp_path / "fig.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(p, [0], a, label="A")
    add_image(p, [0], b, label="B")
    return p


# ------------------------------------------------------------ templatify
def test_templatify_converts_all_panels(grouped):
    msg = templatify_figure(grouped)
    assert "2" in msg
    _, root = _load(grouped)
    fns = [_decode(im.findtext("filename")) for im in root.iter("Image2D")]
    assert fns == ["@template@", "@template@"]


def test_templatify_reported_as_template_slots(grouped):
    templatify_figure(grouped)
    desc = describe_figure(grouped)
    assert "template" in desc.lower()


# --------------------------------------------------------------- review
@needs_qt
def test_export_review_writes_html(grouped, tmp_path):
    out = str(tmp_path / "review.html")
    r = json.loads(export_review(grouped, out, dpi=90))
    assert os.path.getsize(out) > 0 and r["output"] == os.path.abspath(out)


def test_export_review_rejects_non_html(grouped, tmp_path):
    r = export_review(grouped, str(tmp_path / "x.png"))
    assert r.startswith("ERROR")


def test_list_comments_empty(grouped):
    r = json.loads(list_review_comments(grouped))
    assert r["count"] == 0


def test_import_comments_roundtrip(grouped, tmp_path):
    # write a sidecar with one comment, re-list it
    from pyfigures.gui.review.html_export import save_sidecar_comments
    save_sidecar_comments(grouped, [{"x": 0.5, "y": 0.5, "text": "check this",
                                     "author": "me"}])
    r = json.loads(list_review_comments(grouped))
    assert r["count"] == 1 and r["comments"][0]["text"] == "check this"


def test_import_comments_missing_file(grouped):
    assert import_review_comments(grouped, "/no/such.html").startswith("ERROR")


# ---------------------------------------------------------- consolidate
@needs_qt
def test_consolidate_bundles_files(grouped, tmp_path):
    out = str(tmp_path / "bundle.pyf")
    r = json.loads(consolidate_figure(grouped, out))
    assert os.path.isfile(out)
    files_dir = os.path.splitext(out)[0] + ".files"
    assert os.path.isdir(files_dir) and len(os.listdir(files_dir)) >= 1
    # the bundled figure links the copies, not the originals
    from pyfigures.mcp_server import list_images
    paths = [i["path"] for i in json.loads(list_images(out)) if i["path"]]
    assert paths
    for p in paths:
        assert os.path.normcase(os.path.abspath(p)).startswith(os.path.normcase(files_dir)), p
        assert os.path.isfile(p)


def test_consolidate_rejects_non_pyf(grouped, tmp_path):
    assert consolidate_figure(grouped, str(tmp_path / "x.txt")).startswith("ERROR")


# --------------------------------------------------------------- video
@needs_qt
def test_export_video_no_timestack_errors(grouped, tmp_path):
    r = export_video(grouped, str(tmp_path / "out.mp4"))
    assert r.startswith("ERROR") and "time-stack" in r


@needs_qt
def test_export_video_from_mp4(tmp_path):
    cv2 = pytest.importorskip("cv2")
    mp4 = str(tmp_path / "movie.mp4")
    vw = cv2.VideoWriter(mp4, cv2.VideoWriter_fourcc(*"mp4v"), 5, (32, 24))
    for v in (40, 120, 200, 255):
        vw.write(np.full((24, 32, 3), v, np.uint8))
    vw.release()
    p = str(tmp_path / "vid.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(p, [0], mp4, label="T")
    out = str(tmp_path / "out.mp4")
    r = json.loads(export_video(p, out, frame_mode="freeze"))
    assert os.path.getsize(out) > 0 and r["output"] == os.path.abspath(out)


# ----------------------------------------------------------------- cvd
def test_cvd_module_changes_colours():
    from pyfigures.cvd import simulate_array, resolve_type
    assert resolve_type("green") == "deuteranopia"
    red = np.zeros((4, 4, 3), np.uint8)
    red[..., 0] = 255
    out = simulate_array(red, "deuteranopia")
    assert not np.array_equal(out, red)


def test_cvd_preserves_alpha():
    from pyfigures.cvd import simulate_array
    rgba = np.zeros((3, 3, 4), np.uint8)
    rgba[..., 0] = 200
    rgba[..., 3] = 123
    out = simulate_array(rgba, "protanopia")
    assert out.shape[2] == 4 and np.all(out[..., 3] == 123)


@needs_qt
def test_simulate_color_blindness_returns_image(grouped):
    img = simulate_color_blindness(grouped, cvd_type="deuteranopia", dpi=80)
    assert img._format == "png" and img.data[:8] == b"\x89PNG\r\n\x1a\n"


def test_simulate_color_blindness_bad_type(grouped):
    with pytest.raises(ValueError):
        simulate_color_blindness(grouped, cvd_type="nonsense")
