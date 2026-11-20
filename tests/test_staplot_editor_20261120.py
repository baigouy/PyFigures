"""User, 2026-11-20: "if a graph is a staplot graph and I double click on it it should ... allow
me to edit it with staplot visually ... any object in a staplot graph could be clicked within
its GUI and changed (color, font, ...) ... a table view as half of the GUI". A data plot opens
in staplot's PlotEditor; what is changed there reaches the panel through edit_data_plot."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("staplot.ui.plot_editor")


@pytest.fixture(scope="module")
def app():
    from qtpy.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _figure_with_plot(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    csv = tmp_path / "counts.csv"
    csv.write_text("WT,KO\n10,15\n11,16\n9,14\n10.5,15.5\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    assert "ERROR" not in add_data_plot(pyf, [], str(csv), kind="bar")
    return pyf


def _spec(pyf):
    from pyfigures.mcp_tools.core import _load
    from pyfigures.assistant.plot_info import parse_data_plot
    from pyfigures.mcp_tools.content import text_parts_of
    _t, root = _load(pyf)
    img = list(root.iter("Image2D"))[-1]
    from pyfigures.mcp_tools.content import _child_text
    script = _child_text(img, "custom_loading_script") or ""
    return parse_data_plot(script), text_parts_of(img)


def _center(ed, artist):
    bb = artist.get_window_extent(ed.canvas.get_renderer())
    return (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2


def test_what_is_changed_in_the_editor_reaches_the_panel(app, tmp_path):
    from staplot import api
    from staplot.ui.plot_editor import PlotEditor
    from pyfigures.gui.staplot_editor import editor_arguments, edit_arguments
    from pyfigures.mcp_server import edit_data_plot
    pyf = _figure_with_plot(tmp_path)
    spec, _parts = _spec(pyf)
    args = editor_arguments(spec)
    ed = PlotEditor(args["path"], args["kind"], args["kwargs"], args["table_kwargs"], args["facet"])
    bars = [a for a in ed.fig.findobj() if api.plot_part(a) == "bar"]
    kind, group = ed.select_at(*_center(ed, bars[1]))
    assert (kind, group) == ("group", "KO")
    ed.set_in("colors", group, "#ff0000")
    ed.set("ylabel", "Cells")
    ed.set_part("title", "pt", 11)
    ed.set_part("ticks", "font", "DejaVu Serif")
    changes = edit_arguments(ed, args["kwargs"], args["kind"])
    assert changes == {"colors": {"KO": "#ff0000"}, "ylabel": "Cells",
                       "text_pt": {"title": 11}, "text_font": {"ticks": "DejaVu Serif"}}
    assert "ERROR" not in edit_data_plot(pyf, [], 0, **changes)
    spec, parts = _spec(pyf)
    assert spec["colors"] == {"KO": "#ff0000"} and spec["ylabel"] == "Cells"
    assert parts == {"title": {"pt": 11.0}, "ticks": {"font": "DejaVu Serif"}}


def test_a_setting_put_back_to_its_default_is_cleared(app, tmp_path):
    from staplot.ui.plot_editor import PlotEditor
    from pyfigures.gui.staplot_editor import editor_arguments, edit_arguments
    from pyfigures.mcp_server import edit_data_plot
    pyf = _figure_with_plot(tmp_path)
    assert "ERROR" not in edit_data_plot(pyf, [], 0, log_y=True, ylim=[1, 40], kind="box")
    spec, _ = _spec(pyf)
    args = editor_arguments(spec)
    assert args["kind"] == "box" and args["kwargs"]["log_y"] is True
    ed = PlotEditor(args["path"], args["kind"], args["kwargs"], args["table_kwargs"], args["facet"])
    ed.set("log_y", None)
    ed.set("ylim", None)
    ed._set_kind("violin")
    changes = edit_arguments(ed, args["kwargs"], args["kind"])
    assert changes == {"kind": "violin", "log_y": False, "ylim": []}
    assert "ERROR" not in edit_data_plot(pyf, [], 0, **changes)
    spec, _ = _spec(pyf)
    assert spec["kind"] == "violin" and not spec.get("log_y") and not spec.get("ylim")
