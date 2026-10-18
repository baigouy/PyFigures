"""
Tests for the figure-version diff (#6): diff_figures (semantic) and
export_figure_diff (visual HTML with a pixel-difference overlay).

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


def _tif(path, val=100, size=60):
    from batoolset.img import Img
    Img(np.full((size, size), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


def _base_figure(d):
    from pyfigures.mcp_server import (create_figure, add_image, set_scale_bar,
                                      set_figure_caption)
    a = _tif(os.path.join(d, "a.tif"), 80)
    b = _tif(os.path.join(d, "b.tif"), 120)
    pyf = os.path.join(d, "old.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], a, label="A")
    add_image(pyf, [], b, label="B")
    set_scale_bar(pyf, [], 0, 2, unit="um", px_to_unit=0.1)    # 20 px of a 60 px image
    set_figure_caption(pyf, "Original caption.", title="Figure 1")
    return pyf


def _copy_pyf(old, new):
    shutil.copy(old, new)
    cap = os.path.splitext(old)[0] + ".caption.json"
    if os.path.isfile(cap):
        shutil.copy(cap, os.path.splitext(new)[0] + ".caption.json")
    return new


# ── semantic diff ───────────────────────────────────────────────────────────

def test_diff_detects_no_change(tmp_path):
    from pyfigures.mcp_server import diff_figures
    d = str(tmp_path)
    old = _base_figure(d)
    new = _copy_pyf(old, os.path.join(d, "new.pyf"))
    res = json.loads(diff_figures(old, new))
    assert res["n_changes"] == 0
    assert "No differences" in res["summary"]


def test_diff_detects_edits(tmp_path):
    from pyfigures.mcp_server import (diff_figures, add_image, set_annotation_text,
                                      set_lut, remove_scale_bar, set_figure_caption)
    d = str(tmp_path)
    old = _base_figure(d)
    new = _copy_pyf(old, os.path.join(d, "new.pyf"))
    c = _tif(os.path.join(d, "c.tif"), 160)
    add_image(new, [], c, label="C")            # panel_added
    set_annotation_text(new, [], 1, 0, "B'")    # label_changed on B
    set_lut(new, [], 0, ["red"])                # adjustment_changed (lut) on A
    remove_scale_bar(new, [], 0)                # scale_bar_changed on A
    set_figure_caption(new, "Revised.", title="Figure 1")  # caption_changed

    res = json.loads(diff_figures(old, new))
    types = res["changes_by_type"]
    assert types.get("panel_added") == 1
    assert types.get("label_changed") == 1
    assert types.get("adjustment_changed") == 1
    assert types.get("scale_bar_changed") == 1
    assert types.get("caption_changed") == 1
    assert res["panels_old"] == 2 and res["panels_new"] == 3


def test_diff_panel_removed(tmp_path):
    from pyfigures.mcp_server import diff_figures, remove_image
    d = str(tmp_path)
    old = _base_figure(d)
    new = _copy_pyf(old, os.path.join(d, "new.pyf"))
    remove_image(new, [], 1)                     # drop panel B
    res = json.loads(diff_figures(old, new))
    assert res["changes_by_type"].get("panel_removed") == 1


def test_diff_missing_file_errors(tmp_path):
    from pyfigures.mcp_server import diff_figures
    d = str(tmp_path)
    old = _base_figure(d)
    assert diff_figures(old, os.path.join(d, "nope.pyf")).startswith("ERROR")


# ── pixel-diff helper ───────────────────────────────────────────────────────

def test_make_pixel_diff_fraction(tmp_path):
    from pyfigures.mcp_server import _make_pixel_diff
    from PIL import Image
    d = str(tmp_path)
    Image.fromarray(np.full((50, 50, 3), 255, np.uint8)).save(os.path.join(d, "o.png"))
    arr = np.full((50, 50, 3), 255, np.uint8)
    arr[10:30, 10:30] = 0                        # 400 / 2500 = 0.16 changed
    Image.fromarray(arr).save(os.path.join(d, "n.png"))
    frac = _make_pixel_diff(os.path.join(d, "o.png"), os.path.join(d, "n.png"),
                            os.path.join(d, "diff.png"))
    assert abs(frac - 0.16) < 0.01
    assert os.path.isfile(os.path.join(d, "diff.png"))


# ── visual HTML export ──────────────────────────────────────────────────────

def test_export_figure_diff_html(tmp_path):
    from pyfigures.mcp_server import export_figure_diff
    d = str(tmp_path)
    old = _base_figure(d)
    new = _copy_pyf(old, os.path.join(d, "new.pyf"))
    from pyfigures.mcp_server import set_lut
    set_lut(new, [], 0, ["green"])
    out = os.path.join(d, "diff.html")
    res = json.loads(export_figure_diff(old, new, out))
    assert os.path.isfile(out)
    txt = open(out, encoding="utf-8").read()
    assert txt.count("<img ") == 3                        # old | new | diff
    assert "data:image/png;base64" in txt                 # self-contained
    assert "http://" not in txt and "https://" not in txt # no external assets
    assert "adjustment_changed" in txt                    # change list embedded


def test_export_figure_diff_bad_ext(tmp_path):
    from pyfigures.mcp_server import export_figure_diff
    d = str(tmp_path)
    old = _base_figure(d)
    new = _copy_pyf(old, os.path.join(d, "new.pyf"))
    assert export_figure_diff(old, new, os.path.join(d, "x.txt")).startswith("ERROR")


# ── GUI action ──────────────────────────────────────────────────────────────

def test_gui_compare_version_action(qapp, monkeypatch, tmp_path):
    from qtpy import QtWidgets
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import add_image

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    old = _base_figure(d)
    # current figure = old + an extra panel
    cur = _copy_pyf(old, os.path.join(d, "cur.pyf"))
    add_image(cur, [], _tif(os.path.join(d, "c.tif"), 200), label="C")

    g = EZFIG_GUI()
    g.reload_state(cur, append=False)
    g.current_file = cur

    monkeypatch.setattr(pfgui, "openFileNameDialog", staticmethod(lambda *a, **k: old))
    opened = {}
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda url: opened.update(url=url))

    g.compare_version_action()
    assert opened.get("url", "").endswith("diff.html")
    g._dirty = False
