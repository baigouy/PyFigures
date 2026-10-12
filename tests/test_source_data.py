"""
Tests for the source-data export bundle (#5): export_source_data gathers the
rendered figure + each panel's underlying source file + caption + statistics +
Methods into a submission folder.

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


def _tif(path, val=120, size=60):
    from batoolset.img import Img
    Img(np.full((size, size), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


def _csv(path, seed=0):
    rng = np.random.default_rng(seed)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["WT", "KO"])
        for _ in range(10):
            w.writerow([rng.normal(10, 1), rng.normal(15, 1)])
    return path


def test_panel_source_files_parsing():
    from pyfigures.mcp_server import _panel_source_files
    # data-plot script
    assert _panel_source_files(None, "_csv = '/data/counts.csv'\n") == ["/data/counts.csv"]
    # channel-merge script
    files = _panel_source_files(
        "None", "_files = ['/d/a.tif', '/d/b.tif']\n")
    assert files == ["/d/a.tif", "/d/b.tif"]
    # linked image + dedup
    assert _panel_source_files("/d/x.tif", "_csv = '/d/x.tif'") == ["/d/x.tif"]
    # sentinels ignored
    assert _panel_source_files("@template@", None) == []


def test_export_bundle_full(tmp_path):
    from pyfigures.mcp_server import (create_figure, add_image, add_data_plot,
                                      set_figure_caption, export_source_data)
    d = str(tmp_path)
    a = _tif(os.path.join(d, "micro.tif"))
    csvp = _csv(os.path.join(d, "counts.csv"))
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], a, label="A")
    add_data_plot(pyf, [], csvp, kind="box", label="B")
    set_figure_caption(pyf, "Cells (A) and quantification (B).", title="Figure 1")

    out = os.path.join(d, "Fig1_SourceData")
    res = json.loads(export_source_data(pyf, out))

    assert res["figure"] and os.path.isfile(res["figure"])
    assert res["caption"] and res["statistics"] and res["methods"]
    # per-panel sources copied and renamed by panel label
    names = sorted(os.listdir(os.path.join(out, "sources")))
    assert any(n.startswith("panelA__") and n.endswith(".tif") for n in names)
    assert any(n.startswith("panelB__") and n.endswith(".csv") for n in names)
    # manifest + methods content
    manifest = open(os.path.join(out, "MANIFEST.txt"), encoding="utf-8").read()
    assert "Panel A:" in manifest and "Panel B:" in manifest
    methods = open(os.path.join(out, "methods.txt"), encoding="utf-8").read()
    assert "Statistical analysis" in methods
    caption = open(os.path.join(out, "caption.txt"), encoding="utf-8").read()
    assert "Figure 1" in caption


def test_export_bundle_images_only(tmp_path):
    from pyfigures.mcp_server import create_figure, add_image, export_source_data
    d = str(tmp_path)
    a = _tif(os.path.join(d, "a.tif"))
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], a, label="A")
    out = os.path.join(d, "bundle")
    res = json.loads(export_source_data(pyf, out))
    assert res["caption"] is False and res["statistics"] is False
    assert os.path.isfile(os.path.join(out, "MANIFEST.txt"))
    assert res["n_source_files"] >= 1


def test_export_bundle_bad_format(tmp_path):
    from pyfigures.mcp_server import create_figure, export_source_data
    d = str(tmp_path)
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    assert export_source_data(pyf, os.path.join(d, "b"),
                              image_format="gif").startswith("ERROR")


def test_gui_export_source_data_action(qapp, monkeypatch, tmp_path):
    from qtpy import QtWidgets
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure, add_image, set_figure_caption

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    d = str(tmp_path)
    a = _tif(os.path.join(d, "a.tif"))
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    add_image(pyf, [], a, label="A")
    set_figure_caption(pyf, "A caption.", title="Figure 1")

    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g.current_file = pyf   # so the caption sidecar is carried into the bundle

    parent = os.path.join(d, "out")
    os.makedirs(parent, exist_ok=True)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: parent))
    g.export_source_data_action()

    bundle = os.path.join(parent, "fig_SourceData")
    assert os.path.isfile(os.path.join(bundle, "MANIFEST.txt"))
    assert os.path.isfile(os.path.join(bundle, "caption.txt"))  # sidecar carried over
    g._dirty = False
