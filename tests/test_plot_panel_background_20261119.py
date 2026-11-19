"""2026-11-19 (user, live app): "make the bg of each panel that of its image" failed on
the two data plots ("no pixel image"), then "add white bg also for the two plots"
changed the plot's inner background instead of the panel behind its rotated corners,
and the figure preview, drawn on white, told the model the plot was "96% white"
while the user saw empty corners. A plot's colour is now read from the plot as
drawn, and the preview shows (and says) what the panel leaves empty."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PG = os.path.join(os.path.dirname(__file__), "..", "demo_figures", "plots_playground")


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


def test_auto_background_works_on_a_plot(tmp_path):
    from pyfigures.mcp_server import set_image_property
    pyf = _plot_figure(tmp_path)
    out = set_image_property(pyf, [0], 0, "fill_color", "auto")
    assert "fill_color = 16777215" in out, out           # the plot is white


def test_the_preview_shows_the_empty_corners_of_a_rotated_plot(tmp_path):
    from pyfigures.mcp_server import transform_image, set_image_property, preview_panel_source
    pyf = _plot_figure(tmp_path)
    transform_image(pyf, [0], 0, rotation=25)
    text, _img = preview_panel_source(pyf, [0], 0, view="figure")
    assert "EMPTY:" in text and "fill_color" in text
    set_image_property(pyf, [0], 0, "fill_color", "auto")
    text, _img = preview_panel_source(pyf, [0], 0, view="figure")
    assert "EMPTY:" not in text


def test_an_unrotated_plot_has_no_empty_part(tmp_path):
    from pyfigures.mcp_server import preview_panel_source
    pyf = _plot_figure(tmp_path)
    text, _img = preview_panel_source(pyf, [0], 0, view="figure")
    assert "EMPTY:" not in text


def test_a_box_plot_with_brackets_fills_its_panel(tmp_path):
    """User, 2026-11-19 (twice): plots g and h left white strips left and right. A box
    plot with significance brackets was drawn 6% narrower than its panel: its text was
    sized for the page under other settings than it was drawn with, and its target
    shape was re-measured after the brackets had changed it. It was letterboxed."""
    import numpy as np
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, add_data_plot, preview_panel_source
    img = tmp_path / "cells.png"
    Image.fromarray((np.random.default_rng(1).random((120, 160)) * 255).astype(np.uint8)).save(img)
    pyf = str(tmp_path / "row.pyf")
    create_figure(pyf, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(pyf, [0], str(img))
    out = add_data_plot(pyf, [0], os.path.join(PG, "measurements.xlsx"))
    assert "bracketed" in out, out                                   # the plot has brackets
    text, _img = preview_panel_source(pyf, [0], 1, view="figure")
    assert "EMPTY:" not in text, text


def test_the_background_rule_tells_a_plot_from_its_panel():
    from pyfigures.assistant.categorized_mcp import request_rules
    rules = request_rules("add white bg also for the two plots")
    assert "behind its rotated corners" in rules
