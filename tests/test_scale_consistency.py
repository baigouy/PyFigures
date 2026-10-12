"""
Tests for the physical-scale consistency check (QC #3): flag panels whose
displayed physical scale differs so features can't be honestly compared by eye.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _tif(path, size, val=100):
    from batoolset.img import Img
    Img(np.full((size, size), val, dtype=np.uint8), dimensions='hw').save(path)
    return path


def _fig_with_scales(d, scales):
    """Build a canvas .pyf with one 100x100 panel per entry in *scales*
    (px_to_unit or None). Returns the .pyf path."""
    from pyfigures.mcp_server import create_figure, add_image, set_image_property
    pyf = os.path.join(d, "fig.pyf")
    create_figure(pyf, mode="canvas")
    for i, s in enumerate(scales):
        f = _tif(os.path.join(d, f"img{i}.tif"), 100, 80 + i * 10)
        add_image(pyf, [], f)
        if s is not None:
            set_image_property(pyf, [], i, "px_to_unit_conversion_factor", str(s))
    return pyf


def test_raw_width_from_file(tmp_path):
    from pyfigures.mcp_server import _raw_width_from_file
    p = _tif(os.path.join(str(tmp_path), "w.tif"), 137)
    assert _raw_width_from_file(p) == 137
    assert _raw_width_from_file(None) is None
    assert _raw_width_from_file(os.path.join(str(tmp_path), "missing.tif")) is None


def test_flags_mismatched_scale(tmp_path):
    from pyfigures.mcp_server import check_scale_consistency
    # two panels at 0.1 µm/px, one at 0.2 (twice as coarse) → the 0.2 is flagged
    pyf = _fig_with_scales(str(tmp_path), [0.1, 0.1, 0.2])
    d = json.loads(check_scale_consistency(pyf, tolerance=0.05))
    assert d["panels_with_scale"] == 3
    assert d["inconsistent_count"] == 1
    bad = [p for p in d["panels"] if not p["consistent"]]
    assert len(bad) == 1
    assert bad[0]["deviation_pct"] > 50
    assert bad[0].get("recommended_display_w")   # tells you how to fix it


def test_all_consistent(tmp_path):
    from pyfigures.mcp_server import check_scale_consistency
    pyf = _fig_with_scales(str(tmp_path), [0.1, 0.1, 0.1])
    d = json.loads(check_scale_consistency(pyf, tolerance=0.05))
    assert d["inconsistent_count"] == 0
    assert all(p["consistent"] for p in d["panels"])
    assert "consistent displayed scale" in d["summary"]


def test_missing_pixel_size_reported(tmp_path):
    from pyfigures.mcp_server import check_scale_consistency
    pyf = _fig_with_scales(str(tmp_path), [0.1, None, 0.1])
    d = json.loads(check_scale_consistency(pyf, tolerance=0.05))
    assert d["panels_without_scale"] == 1
    assert len(d["missing_scale"]) == 1


def test_none_set_gives_note(tmp_path):
    from pyfigures.mcp_server import check_scale_consistency
    pyf = _fig_with_scales(str(tmp_path), [None, None])
    d = json.loads(check_scale_consistency(pyf, tolerance=0.05))
    assert d["reference_scale"] is None
    assert "cannot be checked" in d["note"]


def test_bad_tolerance_errors(tmp_path):
    from pyfigures.mcp_server import check_scale_consistency
    pyf = _fig_with_scales(str(tmp_path), [0.1, 0.1])
    assert check_scale_consistency(pyf, tolerance=-1).startswith("ERROR")


def test_gui_scale_consistency_action(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI

    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    pyf = _fig_with_scales(str(tmp_path), [0.1, 0.1, 0.2])
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)

    captured = {}
    monkeypatch.setattr(EZFIG_GUI, "_show_report",
                        lambda self, title, text: captured.update(title=title, text=text))
    g.check_scale_consistency_action()
    assert captured.get("title") == "Scale-bar consistency"
    assert "FAIL" in captured["text"]
    g._dirty = False
