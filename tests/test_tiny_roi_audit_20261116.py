"""QC: very small ROIs are listed for the user to check (2026-11-16): the
panel editor now keeps small ROIs (around dots), so a slip of the mouse is
no longer dropped there; the audit asks whether they are wanted."""
from __future__ import annotations

import json

import numpy as np

import pyfigures.mcp_server as M


def _figure(tmp_path):
    from batoolset.img import Img
    f = str(tmp_path / "a.tif")
    Img(np.zeros((400, 500), np.uint8), dimensions="hw").save(f)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], f)
    return pyf


def test_a_tiny_roi_is_flagged_and_a_normal_one_is_not(tmp_path):
    from pyfigures.gui.qc_reports import audit_report
    pyf = _figure(tmp_path)
    M.add_roi_rect(pyf, [0], 0, 10, 10, 3, 2)          # 3 x 2 px on a 500 px image
    M.add_roi_ellipse(pyf, [0], 0, 100, 100, 40, 30)       # a real ROI
    raw = M.audit_figure(pyf)
    tiny = json.loads(raw)["panels_with_tiny_rois"]
    assert len(tiny) == 1 and [r["size_px"] for r in tiny[0]["rois"]] == [[3.0, 2.0]], tiny
    assert "very small ROI" in audit_report(raw)


def test_no_tiny_rois_no_line(tmp_path):
    from pyfigures.gui.qc_reports import audit_report
    pyf = _figure(tmp_path)
    M.add_roi_ellipse(pyf, [0], 0, 100, 100, 40, 30)
    raw = M.audit_figure(pyf)
    assert json.loads(raw)["panels_with_tiny_rois"] == [] and "very small ROI" not in audit_report(raw)
