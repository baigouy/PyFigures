"""User, 2026-11-20: a broken y axis, dose-response fits, stacked / % bars, histograms,
heatmaps, tick step / format / log base, one-sided error bars as data-plot options, and an
image drawn as a graph (its coordinate axes around it: add_image_plot)."""
import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("staplot.plots.extras")


def _spec(pyf, i=-1):
    from pyfigures.mcp_tools.core import _load, _child_text
    from pyfigures.assistant.plot_info import parse_data_plot
    _t, root = _load(pyf)
    return parse_data_plot(_child_text(list(root.iter("Image2D"))[i], "custom_loading_script") or "")


def _drawn(pyf, i=-1):
    from pyfigures.mcp_tools.core import _load, _child_text
    from batoolset.drawings.shapes.image2d import Image2D
    _t, root = _load(pyf)
    return Image2D(custom_loading_script=_child_text(list(root.iter("Image2D"))[i], "custom_loading_script")).img


@pytest.fixture
def pyf(tmp_path):
    from pyfigures.mcp_server import create_figure
    p = str(tmp_path / "f.pyf")
    create_figure(p)
    return p


def test_broken_axis_ticks_and_one_sided_errors(pyf, tmp_path):
    from pyfigures.mcp_server import add_data_plot, edit_data_plot
    g = tmp_path / "g.csv"
    g.write_text("WT,KO,big\n10,15,400\n11,16,420\n9,14,410\n10.5,15.5,405\n", encoding="utf-8")
    assert "ERROR" not in add_data_plot(pyf, [], str(g), kind="bar")
    out = edit_data_plot(pyf, [], 0, ybreak=[20, 350], error_side="up", y_format="{:.0f}")
    assert "ERROR" not in out, out
    spec = _spec(pyf)
    assert spec["ybreak"] == [20.0, 350.0] and spec["error_side"] == "up"
    fig = _drawn(pyf)
    assert len(fig.axes) == 2
    assert edit_data_plot(pyf, [], 0, ybreak=[50, 10]).startswith("ERROR")
    assert edit_data_plot(pyf, [], 0, y_format="fancy").startswith("ERROR")
    assert "ERROR" not in edit_data_plot(pyf, [], 0, ybreak=[], error_side="both")
    assert not _spec(pyf).get("ybreak") and not _spec(pyf).get("error_side")


def test_stacked_dose_response_histogram_heatmap(pyf, tmp_path):
    from pyfigures.mcp_server import add_data_plot, edit_data_plot
    ph = tmp_path / "pheno.csv"
    ph.write_text("phenotype,genotype,n\nnormal,WT,40\nnormal,KO,10\ndefect,WT,5\ndefect,KO,30\n", encoding="utf-8")
    out = add_data_plot(pyf, [], str(ph), kind="stacked", percent=True)
    assert "ERROR" not in out and "chi-square" in out, out
    rows = ["dose,drug"] + [f"{d},{5 + 95 / (1 + (3.0 / d) ** 1.2) + k}" for d in (0.01, 0.1, 1, 10, 100, 1000)
                            for k in (-1, 0, 1)]
    dr = tmp_path / "dr.csv"
    dr.write_text("\n".join(rows) + "\n", encoding="utf-8")
    out = add_data_plot(pyf, [], str(dr), kind="dose_response")
    assert "ERROR" not in out and "EC50" in out, out
    assert _drawn(pyf).axes[0].get_xscale() == "log"
    assert "ERROR" not in edit_data_plot(pyf, [], 1, log_x=False)
    assert _spec(pyf, 1)["log_x"] is False and _drawn(pyf, 1).axes[0].get_xscale() == "linear"
    assert "ERROR" not in edit_data_plot(pyf, [], 1, log_x=True)
    assert _spec(pyf, 1).get("log_x") is None
    g = tmp_path / "g.csv"
    g.write_text("WT,KO\n10,15\n11,16\n9,14\n10.5,15.5\n", encoding="utf-8")
    assert "ERROR" not in add_data_plot(pyf, [], str(g), kind="histogram", bins=4)
    assert "ERROR" not in add_data_plot(pyf, [], str(g), kind="heatmap", cmap="viridis")
    assert add_data_plot(pyf, [], str(g), kind="heatmap", cmap="nope").startswith("ERROR")
    assert _drawn(pyf).axes[0].images


def test_an_image_drawn_with_its_axes(pyf, tmp_path):
    from pyfigures.mcp_server import add_image_plot
    mask = np.zeros((40, 60), np.uint8)
    mask[10:30, 20:45] = 255
    from PIL import Image
    Image.fromarray(mask).save(tmp_path / "mask.png")
    out = add_image_plot(pyf, [], str(tmp_path / "mask.png"), pixel_size=0.5, cmap="viridis", colorbar=True,
                         contour_path=str(tmp_path / "mask.png"))
    assert "ERROR" not in out and "µm" in out, out
    fig = _drawn(pyf)
    assert fig.axes[0].get_xlabel() == "x (µm)" and fig.axes[0].get_xlim() == (0, 30) and len(fig.axes) == 2
    assert add_image_plot(pyf, [], str(tmp_path / "none.png")).startswith("ERROR")
    assert add_image_plot(pyf, [], str(tmp_path / "mask.png"), cmap="nope").startswith("ERROR")
    assert json  # noqa
