"""
Tests for #2 (figure_review_brief — pre-submission reviewer brief) and
#4 (index_figures / search_figures — figure library search).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _tif(path, val=120, size=60):
    from batoolset.img import Img
    Img(np.full((size, size), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


def _figure(d, name="fig.pyf", img="a.tif", caption="Cells at 63x.", sub=None):
    from pyfigures.mcp_server import create_figure, add_image, set_figure_caption
    base = os.path.join(d, sub) if sub else d
    os.makedirs(base, exist_ok=True)
    ip = _tif(os.path.join(base, img))
    pyf = os.path.join(base, name)
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], ip, label="A")
    if caption:
        set_figure_caption(pyf, caption, title="Figure")
    return pyf


# ── #2 figure_review_brief ──────────────────────────────────────────────────

def test_review_brief_aggregates(tmp_path):
    from pyfigures.mcp_server import figure_review_brief
    d = str(tmp_path)
    pyf = _figure(d)
    r = json.loads(figure_review_brief(pyf, journal="nature", column="single"))
    assert r["caption_present"] is True
    mk = r["mechanical_checks"]
    for key in ("audit", "scale_consistency", "image_integrity", "fonts",
                "journal_compliance", "resolution"):
        assert key in mk
    assert len(r["visual_rubric"]) >= 5
    assert "deuteranopia" in r["cvd_checks_recommended"]
    assert mk["audit"]["n_panels"] == 1


def test_review_brief_no_journal(tmp_path):
    from pyfigures.mcp_server import figure_review_brief
    d = str(tmp_path)
    pyf = _figure(d, caption=None)
    r = json.loads(figure_review_brief(pyf))
    assert r["caption_present"] is False
    assert "resolution" in r["mechanical_checks"]
    assert "journal_compliance" not in r["mechanical_checks"]


def test_review_brief_missing_file(tmp_path):
    from pyfigures.mcp_server import figure_review_brief
    assert figure_review_brief(os.path.join(str(tmp_path), "no.pyf")).startswith("ERROR")


def test_gui_review_action(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    d = str(tmp_path)
    pyf = _figure(d)
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    captured = {}
    monkeypatch.setattr(EZFIG_GUI, "_show_report",
                        lambda self, title, text: captured.update(title=title, text=text))
    g.figure_review_action()
    assert captured["title"] == "Pre-submission review"
    assert "Reviewer questions" in captured["text"]
    assert "Mechanical checks" in captured["text"]
    g._dirty = False


# ── #4 index_figures / search_figures ───────────────────────────────────────

def test_index_and_search(tmp_path):
    from pyfigures.mcp_server import index_figures, search_figures
    d = str(tmp_path)
    _figure(d, sub="2023_gut", img="WT_gut_immunofluorescence.tif",
            caption="WT gut immunofluorescence, DAPI + GFP.")
    _figure(d, sub="2024_brain", img="KO_brain_section.tif",
            caption="KO brain section, cell counts.")
    idx = json.loads(index_figures(d))
    assert idx["figures_indexed"] == 2 and idx["new"] == 2

    r = json.loads(search_figures("gut immunofluorescence", idx["index"]))
    assert r["n_results"] == 1
    assert "2023_gut" in r["results"][0]["path"]
    assert r["results"][0]["matched"] == ["gut", "immunofluorescence"]
    assert any("gut" in p.lower() for p in r["results"][0]["matching_panels"])

    assert json.loads(search_figures("brain", idx["index"]))["n_results"] == 1
    assert json.loads(search_figures("zzz nope", idx["index"]))["n_results"] == 0


def test_index_incremental(tmp_path):
    from pyfigures.mcp_server import index_figures
    d = str(tmp_path)
    _figure(d, sub="a", caption="one")
    _figure(d, sub="b", caption="two")
    idx1 = json.loads(index_figures(d))
    assert idx1["new"] == 2
    idx2 = json.loads(index_figures(d))
    assert idx2["unchanged"] == 2 and idx2["new"] == 0


def test_index_thumbnails(tmp_path):
    from pyfigures.mcp_server import index_figures
    d = str(tmp_path)
    _figure(d, sub="a")
    idx = json.loads(index_figures(d, with_thumbnails=True, thumb_dpi=30))
    assert idx["thumbnails"] is True
    data = json.load(open(idx["index"], encoding="utf-8"))
    thumb = data["figures"][0].get("thumbnail")
    assert thumb and os.path.isfile(thumb)


def test_search_no_index_errors(tmp_path):
    from pyfigures.mcp_server import search_figures
    assert search_figures("x", os.path.join(str(tmp_path), "none.json")).startswith("ERROR")


def test_extract_figure_meta(tmp_path):
    from pyfigures.mcp_server import _extract_figure_meta
    d = str(tmp_path)
    pyf = _figure(d, img="mycell.tif", caption="hello world")
    meta = _extract_figure_meta(pyf)
    assert meta["n_panels"] == 1
    assert meta["panels"][0]["file"] == "mycell.tif"
    assert meta["caption"] == "hello world"


def test_gui_search_library_action(qapp, monkeypatch, tmp_path):
    from qtpy import QtWidgets
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    _figure(d, sub="proj", img="WT_gut.tif", caption="WT gut section.")

    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: d))
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText",
                        staticmethod(lambda *a, **k: ("gut", True)))

    class _Open:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QtWidgets.QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _Open)

    g = EZFIG_GUI()
    opened = {}
    monkeypatch.setattr(EZFIG_GUI, "reload_state",
                        lambda self, path, append=False: opened.update(path=path))
    g.search_library_action()
    assert opened.get("path", "").endswith(".pyf") and "proj" in opened["path"]
    g._dirty = False
