"""User, 2026-11-20: "in QC you could warn if graphs are rotated, ... that would most
likely never make sense for them to be rotated". QC > Audit figure lists rotated or
mirrored data plots, and transform_image warns when it turns one."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _plot_figure(tmp_path):
    import pandas as pd
    from pyfigures.mcp_server import create_figure, add_data_plot
    csv = tmp_path / "values.csv"
    pd.DataFrame({"WT": [1, 2, 3, 2, 3], "mutA": [4, 5, 4, 6, 5]}).to_csv(csv, index=False)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    out = add_data_plot(pyf, [0], str(csv))
    assert not out.startswith("ERROR"), out
    return pyf


def test_a_rotated_plot_is_warned_and_reported(tmp_path):
    from pyfigures.mcp_server import transform_image, audit_figure
    from pyfigures.gui.qc_reports import audit_report
    pyf = _plot_figure(tmp_path)
    assert json.loads(audit_figure(pyf))["plots_turned"] == []
    out = transform_image(pyf, [0], 0, rotation=25)
    assert "WARNING" in out and "data plot" in out, out
    raw = audit_figure(pyf)
    turned = json.loads(raw)["plots_turned"]
    assert len(turned) == 1 and "rotated 25°" in turned[0]["how"], turned
    assert "rotated or mirrored" in audit_report(raw)
    out = transform_image(pyf, [0], 0, rotation=0)
    assert "WARNING" not in out, out
    assert json.loads(audit_figure(pyf))["plots_turned"] == []


def test_a_mirrored_plot_is_reported(tmp_path):
    from pyfigures.mcp_server import transform_image, audit_figure
    pyf = _plot_figure(tmp_path)
    transform_image(pyf, [0], 0, flip_h=True)
    turned = json.loads(audit_figure(pyf))["plots_turned"]
    assert len(turned) == 1 and turned[0]["how"] == "mirrored", turned


def test_a_rotated_image_is_not_a_plot(tmp_path):
    import numpy as np
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, transform_image, audit_figure
    png = tmp_path / "cells.png"
    Image.fromarray(np.zeros((40, 50), np.uint8)).save(png)
    pyf = str(tmp_path / "g.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], str(png))
    assert "WARNING" not in transform_image(pyf, [0], 0, rotation=25)
    assert json.loads(audit_figure(pyf))["plots_turned"] == []
