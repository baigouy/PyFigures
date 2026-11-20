"""User, 2026-11-20: "dual y axes? or several plots for the same data such as point cloud and
lines", "invert axis(es) ... I often found it painful to do". A data plot takes layers
(lines through the means / medians, mean ± error), y2 (a measure on a right-hand axis,
reported by QC) and invert_y / invert_x; the recipe takes them too."""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("staplot.plots.layers")


def _figure(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    area = tmp_path / "area.csv"
    area.write_text("WT,KO\n10,15\n11,16\n9,14\n10.5,15.5\n", encoding="utf-8")
    counts = tmp_path / "counts.csv"
    counts.write_text("genotype,cells\nWT,100\nWT,110\nKO,50\nKO,60\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    assert "ERROR" not in add_data_plot(pyf, [], str(area), kind="box", layers=["mean_line"])
    return pyf, str(counts)


def _spec(pyf):
    from pyfigures.mcp_tools.core import _load, _child_text
    from pyfigures.assistant.plot_info import parse_data_plot
    _t, root = _load(pyf)
    return parse_data_plot(_child_text(list(root.iter("Image2D"))[-1], "custom_loading_script") or "")


def _figure_of(pyf):
    """The plot as the panel draws it (its script run)."""
    from pyfigures.mcp_tools.core import _load, _child_text
    from pyfigures.script_panels import check_script
    from batoolset.drawings.shapes.image2d import Image2D
    _t, root = _load(pyf)
    panel = Image2D(custom_loading_script=_child_text(list(root.iter("Image2D"))[-1], "custom_loading_script"))
    return panel.img


def test_layers_y2_and_inverted_axes_on_a_data_plot(tmp_path):
    from staplot import api
    from pyfigures.mcp_server import edit_data_plot, audit_figure
    pyf, counts = _figure(tmp_path)
    assert _spec(pyf)["layers"] == ["mean_line"]
    out = edit_data_plot(pyf, [], 0, y2={"csv": counts, "columns": ["genotype", "cells"], "label": "cells"},
                         invert_y=True)
    assert "ERROR" not in out, out
    spec = _spec(pyf)
    assert spec["y2"]["label"] == "cells" and spec["invert_y"] is True
    fig = _figure_of(pyf)
    assert len(fig.axes) == 2 and fig.axes[0].yaxis_inverted()
    assert [a for a in fig.findobj() if api.plot_part(a) == "layers"]
    audit = json.loads(audit_figure(pyf))
    assert audit["plots_dual_axis"] and audit["plots_dual_axis"][0]["right_axis"] == "cells"
    # removed again: {} / [] / False
    assert "ERROR" not in edit_data_plot(pyf, [], 0, y2={}, layers=[], invert_y=False)
    spec = _spec(pyf)
    assert not spec.get("y2") and not spec.get("layers") and not spec.get("invert_y")
    assert not json.loads(audit_figure(pyf))["plots_dual_axis"]


def test_bad_values_are_refused(tmp_path):
    from pyfigures.mcp_server import edit_data_plot
    pyf, counts = _figure(tmp_path)
    assert edit_data_plot(pyf, [], 0, layers=["spline"]).startswith("ERROR")
    assert edit_data_plot(pyf, [], 0, y2={"label": "x"}).startswith("ERROR")
    assert edit_data_plot(pyf, [], 0, kind="scatter", layers=["mean_line"]).startswith("ERROR")


def test_the_y2_table_defaults_to_the_plots_own(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    tidy = tmp_path / "tidy.csv"
    tidy.write_text("genotype,area,cells\nWT,10,100\nWT,11,110\nKO,15,50\nKO,16,60\n", encoding="utf-8")
    pyf = str(tmp_path / "g.pyf")
    create_figure(pyf)
    out = add_data_plot(pyf, [], str(tidy), kind="bar", columns=["genotype", "area"],
                        y2={"columns": ["genotype", "cells"]})
    assert "ERROR" not in out, out
    assert _spec(pyf)["y2"]["csv"] == str(tidy)
    assert len(_figure_of(pyf).axes) == 2
