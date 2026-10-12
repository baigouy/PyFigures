"""
Tests for draft_figure (the "draft-a-figure" orchestration): folder of results
-> a complete first-pass .pyf (image grid + data plots + scale bars + A/B/C
letters + journal size + caption stub).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import csv
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _img_folder(d, names, with_csv=False):
    folder = os.path.join(d, "exp")
    os.makedirs(folder, exist_ok=True)
    from batoolset.img import Img
    for i, n in enumerate(names):
        Img(np.full((80, 80), 60 + i * 30, np.uint8), dimensions='hw').save(os.path.join(folder, n))
    if with_csv:
        with open(os.path.join(folder, "counts.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["WT", "KO"])
            rng = np.random.default_rng(0)
            for _ in range(10):
                w.writerow([rng.normal(10, 1), rng.normal(15, 1)])
    return folder


def _letters(pyf):
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_server import _iter_panel_elements, _panel_letter_label
    root = ET.parse(pyf).getroot()
    return [_panel_letter_label(im) for im in _iter_panel_elements(root)]


def test_draft_images_only(tmp_path):
    from pyfigures.mcp_server import draft_figure, export_figure
    d = str(tmp_path)
    folder = _img_folder(d, ["a.tif", "b.tif", "c.tif"])
    out = os.path.join(d, "fig.pyf")
    res = json.loads(draft_figure(folder, out))
    assert res["n_images"] == 3 and res["n_data_plots"] == 0
    assert res["panels_lettered"] == 3
    assert os.path.isfile(out)
    assert _letters(out) == ["A", "B", "C"]
    # it renders
    r = json.loads(export_figure(out, os.path.join(d, "f.png"), dpi=72))
    assert r["bytes"] > 0


def test_draft_images_and_csv(tmp_path):
    from pyfigures.mcp_server import draft_figure
    d = str(tmp_path)
    folder = _img_folder(d, ["a.tif", "b.tif"], with_csv=True)
    out = os.path.join(d, "fig.pyf")
    res = json.loads(draft_figure(folder, out, plot_kind="box"))
    assert res["n_images"] == 2 and res["n_data_plots"] == 1
    # 2 images + 1 plot all lettered
    assert res["panels_lettered"] == 3
    assert _letters(out) == ["A", "B", "C"]


def test_draft_scale_bars_on_micrographs(tmp_path):
    from pyfigures.mcp_server import draft_figure
    import xml.etree.ElementTree as ET
    d = str(tmp_path)
    folder = _img_folder(d, ["a.tif", "b.tif"], with_csv=True)
    out = os.path.join(d, "fig.pyf")
    res = json.loads(draft_figure(folder, out, px_to_unit=0.1, scale_bar_units=10))
    assert res["scale_bars"] == 2   # micrographs only, not the data plot
    root = ET.parse(out).getroot()
    bars = [sb for sb in root.iter("ScaleBar")]
    assert len(bars) == 2


def test_draft_caption_stub(tmp_path):
    from pyfigures.mcp_server import draft_figure, get_figure_caption
    d = str(tmp_path)
    folder = _img_folder(d, ["wt.tif", "ko.tif"])
    out = os.path.join(d, "fig.pyf")
    draft_figure(folder, out)
    cap = json.loads(get_figure_caption(out))["caption"]
    assert cap.startswith("Figure.") and "(A)" in cap and "(B)" in cap


def test_draft_journal_resize(tmp_path):
    from pyfigures.mcp_server import draft_figure
    d = str(tmp_path)
    folder = _img_folder(d, ["a.tif", "b.tif"])
    out = os.path.join(d, "fig.pyf")
    res = json.loads(draft_figure(folder, out, journal="nature", column="double"))
    assert res["journal"] == "nature (double)"
    assert any("nature" in s for s in res["steps"])


def test_draft_csv_only(tmp_path):
    from pyfigures.mcp_server import draft_figure
    d = str(tmp_path)
    folder = os.path.join(d, "exp")
    os.makedirs(folder)
    with open(os.path.join(folder, "data.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["A", "B"])
        for i in range(6):
            w.writerow([i, i + 3])
    out = os.path.join(d, "fig.pyf")
    res = json.loads(draft_figure(folder, out))
    assert res["n_images"] == 0 and res["n_data_plots"] == 1


def test_draft_bad_inputs(tmp_path):
    from pyfigures.mcp_server import draft_figure
    d = str(tmp_path)
    assert draft_figure(os.path.join(d, "nope"), os.path.join(d, "f.pyf")).startswith("ERROR")
    folder = _img_folder(d, ["a.tif"])
    assert draft_figure(folder, os.path.join(d, "f.txt")).startswith("ERROR")
    assert draft_figure(folder, os.path.join(d, "f.pyf"), plot_kind="pie").startswith("ERROR")
    empty = os.path.join(d, "empty")
    os.makedirs(empty)
    assert draft_figure(empty, os.path.join(d, "g.pyf")).startswith("ERROR")


def test_gui_draft_figure_action(qapp, monkeypatch, tmp_path):
    from qtpy import QtWidgets
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from batoolset.drawings.shapes.image2d import Image2D

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    folder = _img_folder(d, ["a.tif", "b.tif", "c.tif"], with_csv=True)

    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: folder))

    class _OK:
        def __init__(self, *a, **k):
            pass

        def exec_(self):
            return QtWidgets.QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _OK)

    g = EZFIG_GUI()
    g.draft_figure_action()

    assert os.path.isfile(os.path.join(folder, "DraftFigure.pyf"))
    imgs = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)]
    assert len(imgs) >= 1     # drafted figure was loaded into the GUI
    g._dirty = False
