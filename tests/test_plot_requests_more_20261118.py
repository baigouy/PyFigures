"""More of what people ask of plots and tables (user, 2026-11-18: "users may ask for
titles, split plots / facets, cumulative histogram plots, ... to change colors of some
plot elements, names of cols, ... if the table could get axes labels from the table in
some cases. the table import should also allow to skip lines, that is smthg I so often
had to do")."""
from __future__ import annotations

import os
import types

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures.mcp_tools import content as C  # noqa: E402
from pyfigures.mcp_tools.core import _child_text, _load  # noqa: E402


@pytest.fixture
def tidy(tmp_path):
    rng = np.random.default_rng(11)
    rows = []
    for g, ge in (("WT", 0), ("mutA", -20), ("mutB", 5)):
        for sx, se in (("female", 0), ("male", 30)):
            for day in (7, 14):
                rows += [(g, sx, day, round(200 + ge + se + rng.normal(0, 8), 2)) for _ in range(10)]
    path = tmp_path / "mice.csv"
    pd.DataFrame(rows, columns=["genotype", "sex", "day", "area_um2"]).to_csv(path, index=False)
    return str(path)


@pytest.fixture
def plate(tmp_path):
    """A plate reader export: three lines above the table."""
    rng = np.random.default_rng(2)
    path = tmp_path / "plate.csv"
    body = "\n".join(",".join(f"{v:.2f}" for v in rng.normal((10, 14, 10), 1)) for _ in range(10))
    path.write_text("Plate reader export v2.1\nDate: 2026-11-18, operator: XX\n# wells A1-H12\n"
                    "WT,mutA,mutB\n" + body + "\n", encoding="utf-8")
    return str(path)


@pytest.fixture
def pyf(tmp_path, qapp):
    path = str(tmp_path / "f.pyf")
    import pyfigures.mcp_server as M
    M.create_figure(path, num_groups=0)
    return path


def _scripts(pyf):
    _tree, root = _load(pyf)
    return [C._decode_text(_child_text(i, "custom_loading_script")) for i in root.iter("Image2D")]


def _draw(script):
    import matplotlib.pyplot as plt
    me = types.SimpleNamespace()
    exec(compile(script, "panel", "exec"), {"plt": plt}, {"self": me})
    return me.img


def test_the_lines_above_a_table_are_skipped_and_said(pyf, plate):
    out = C.add_data_plot(pyf, [], plate, kind="box")
    assert not out.startswith("ERROR"), out
    assert "3 line(s) above the table were skipped" in out and "Plate reader export" in out
    ax = _draw(_scripts(pyf)[-1]).axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["WT", "mutA", "mutB"]
    assert "Skipped above the table (3 line(s)" in C.describe_table(plate)
    # by hand: the number of lines
    assert "skip_rows None -> 3" in C.edit_data_plot(pyf, [], 0, skip_rows=3)
    assert "skip_rows=3" in _scripts(pyf)[-1]
    assert C.edit_data_plot(pyf, [], 0, skip_rows="many").startswith("ERROR: skip_rows")
    assert "skip_rows 3 -> None" in C.edit_data_plot(pyf, [], 0, skip_rows="auto")


def test_only_some_rows(pyf, tidy):
    out = C.add_data_plot(pyf, [], tidy, kind="violin", columns=["genotype", "area_um2"], where="day == 14")
    assert not out.startswith("ERROR"), out
    assert "where='day == 14'" in _scripts(pyf)[-1]
    from pyfigures.assistant.plot_info import parse_data_plot, _groups
    spec = parse_data_plot(_scripts(pyf)[-1])
    assert _groups(spec) == {"WT": 20, "mutA": 20, "mutB": 20}
    assert "where 'day == 14' -> \"sex == 'male'\"" in C.edit_data_plot(pyf, [], 0, where="sex == 'male'")
    assert C.edit_data_plot(pyf, [], 0, where="age > 3").startswith("ERROR")
    assert "-> None" in C.edit_data_plot(pyf, [], 0, where="")


def test_the_axis_labels_come_from_the_table(pyf, tidy):
    C.add_data_plot(pyf, [], tidy, kind="split_violin", columns=["genotype", "sex", "area_um2"])
    ax = _draw(_scripts(pyf)[-1]).axes[0]
    assert (ax.get_ylabel(), ax.get_xlabel()) == ("area_um2", "genotype")
    assert ax.get_legend().get_title().get_text() == "sex"
    C.edit_data_plot(pyf, [], 0, ylabel="Area (µm²)")
    assert _draw(_scripts(pyf)[-1]).axes[0].get_ylabel() == "Area (µm²)"


def test_colour_parts_of_a_plot(pyf, tidy):
    from matplotlib.colors import to_rgba
    out = C.add_data_plot(pyf, [], tidy, kind="box", columns=["genotype", "area_um2"],
                          element_colors={"medians": "red", "points": "black"})
    assert not out.startswith("ERROR"), out
    ax = _draw(_scripts(pyf)[-1]).axes[0]
    from staplot.api import plot_part
    meds = [a for a in ax.findobj() if plot_part(a) == "median"]
    assert meds and all(to_rgba(m.get_color()) == to_rgba("red") for m in meds)
    # merged with the earlier ones; "" puts one back
    out = C.edit_data_plot(pyf, [], 0, element_colors={"brackets": "grey", "points": ""})
    assert "element_colors" in out
    assert "'median': 'red'" in _scripts(pyf)[-1] and "'brackets': 'grey'" in _scripts(pyf)[-1]
    assert "'points'" not in _scripts(pyf)[-1]
    bad = C.edit_data_plot(pyf, [], 0, element_colors={"tails": "red"})
    assert bad.startswith("ERROR") and "the elements are" in bad
    assert C.edit_data_plot(pyf, [], 0, element_colors={"points": "blurple"}).startswith("ERROR: unknown colour")
    assert "-> None" in C.edit_data_plot(pyf, [], 0, element_colors={})


def test_seaborn_cumulative_histogram_rename_and_rows(pyf, tidy):
    out = C.add_seaborn_plot(pyf, [], tidy, "histplot", x="area_um2", hue="sex", where="day == 7",
                             options={"cumulative": True, "element": "step", "fill": False},
                             rename={"area_um2": "area (µm²)", "female": "F", "male": "M"},
                             title="Cumulative areas")
    assert not out.startswith("ERROR"), out
    fig = _draw(_scripts(pyf)[-1])
    ax = fig.axes[0]
    assert ax.get_xlabel() == "area (µm²)" and ax.get_title() == "Cumulative areas"
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["F", "M"]
    assert "30 of 60" not in out                                   # 60 rows on day 7, none dropped
    assert "rename" in C.edit_seaborn_plot(pyf, [], 0, rename={"mutA": "mutant A"})
    assert C.add_seaborn_plot(pyf, [], tidy, "histplot", x="area_um2", where="age > 2").startswith("ERROR")
    assert "cumulative" in C.add_seaborn_plot.__doc__


def test_a_recipe_takes_the_new_keys(tmp_path, tidy, plate, qapp):
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    recipe = tmp_path / "r.yaml"
    recipe.write_text(
        "output: r.pyf\nrows:\n"
        f"  - - {{plot: {plate}, skip_rows: 3, kind: bar, element_colors: {{points: black}}}}\n"
        f"    - {{plot: {tidy}, columns: [genotype, area_um2], where: 'day == 14', kind: violin}}\n"
        f"    - {{seaborn: {tidy}, function: ecdfplot, x: area_um2, hue: genotype, rename: {{area_um2: area}}}}\n",
        encoding="utf-8")
    out = build_figure_from_recipe(str(recipe))
    assert '"plots": 3' in out and '"warnings": []' in out, out


def test_facets_one_plot_per_day_each_tested(pyf, tidy):
    """"split plots / facets": one plot per value of a column, each with its statistics."""
    out = C.add_data_plot(pyf, [], tidy, kind="violin", columns=["genotype", "area_um2"], facet="day",
                          title="Areas")
    assert not out.startswith("ERROR"), out
    assert "2 facets, each tested" in out
    fig = _draw(_scripts(pyf)[-1])
    shown = [a for a in fig.axes if a.get_visible()]
    assert [a.get_title() for a in shown] == ["day = 7", "day = 14"]
    assert fig._suptitle.get_text() == "Areas"
    from pyfigures.assistant.plot_info import parse_data_plot, plot_statistics, data_plot_code
    spec = parse_data_plot(_scripts(pyf)[-1])
    assert spec["facet"] == "day"
    stats = plot_statistics(spec)
    assert set(stats["facets"]) == {"day = 7", "day = 14"}
    assert "api.plot_facets(" in data_plot_code(spec)
    # a grid of facets, then back to one plot
    assert "facet_row None -> 'sex'" in C.edit_data_plot(pyf, [], 0, facet_row="sex")
    assert len([a for a in _draw(_scripts(pyf)[-1]).axes if a.get_visible()]) == 4
    out = C.edit_data_plot(pyf, [], 0, facet="")
    assert "facet 'day' -> None" in out and "plot_facets" not in _scripts(pyf)[-1]
    assert C.edit_data_plot(pyf, [], 0, facet="age").startswith("ERROR")
    assert C.edit_data_plot(pyf, [], 0, facet_row="sex").startswith("ERROR: facet_row needs a facet")


def test_the_gui_dialog_takes_facets_rows_and_skipped_lines(qapp, monkeypatch, tidy, tmp_path):
    from qtpy.QtWidgets import QComboBox, QDialog, QLineEdit, QMessageBox, QSpinBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure
    from batoolset.drawings.shapes.image2d import Image2D

    EZFIG_GUI.show_tips = lambda self: None
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a)))
    pyf = str(tmp_path / "fig.pyf")
    create_figure(pyf, mode="canvas")
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [tidy]))

    class _Pick:
        def __init__(self, *a, main_widget=None, **k):
            combos = main_widget.findChildren(QComboBox)

            def pick(first_item, text):
                combo = next(c for c in combos if c.count() and c.itemText(0) == first_item)
                combo.setCurrentIndex(combo.findText(text))
                assert combo.currentText() == text, (first_item, text)
            pick("auto", "box")
            pick("x: whole table", "genotype")
            pick("value: -", "area_um2")
            pick("facets: none", "day")
            edit = next(e for e in main_widget.findChildren(QLineEdit) if "day == 14" in e.placeholderText())
            edit.setText("sex == 'male'")
            spin = next(s for s in main_widget.findChildren(QSpinBox) if s.specialValueText() == "skip: auto")
            spin.setValue(0)

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _Pick)
    g.add_data_plot_action()
    assert not warnings, warnings
    script = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)][-1].custom_loading_script
    for word in ("api.plot_facets(_csv, facet='day'", "columns=['genotype', 'area_um2']",
                 "where=\"sex == 'male'\"", "skip_rows=0"):
        assert word in script, (word, script[-700:])
    g._dirty = False


def test_elements_sharing_an_id_are_all_drawn(qapp):
    """A plot whose parts share an SVG id (gid) lost all but one of them on the canvas
    (every significance bracket line but the last, 2026-11-18): each gets its own id."""
    from batoolset.drawings.svg_clip_renderer import ClippingSvgRenderer
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
           b'<g id="brackets"><path d="M0 0 L5 0"/></g><g id="brackets"><path d="M0 5 L5 5"/></g></svg>')
    r = ClippingSvgRenderer(svg)
    ids = [k for k in r._ids if k.startswith("brackets")]
    assert len(ids) == 2 and len(set(ids)) == 2
    import matplotlib
    matplotlib.use("Agg")
    from staplot import api
    import io as _io
    t = api.table_from_columns({"a": [1, 2, 3, 4, 5.0], "b": [9, 8, 9, 10, 9.0]})
    fig = api.plot(t, "box")[0]
    buf = _io.BytesIO()
    fig.savefig(buf, format="svg")
    assert b'id="brackets"' not in buf.getvalue() and b'id="median"' not in buf.getvalue()


def test_journal_details(pyf, tidy):
    out = C.add_data_plot(pyf, [], tidy, kind="box", columns=["genotype", "area_um2"], show_n=True,
                          p_format="p values", hlines=[{"y": 200, "label": "baseline"}])
    assert not out.startswith("ERROR"), out
    script = _scripts(pyf)[-1]
    assert "show_n=True" in script and "p_format='p'" in script and "'label': 'baseline'" in script
    ax = _draw(script).axes[0]
    assert ax.get_xticklabels()[0].get_text() == "WT\n(n=40)"
    out = C.edit_data_plot(pyf, [], 0, p_format="stars", show_mean=True, hlines=[])
    assert "p_format 'p' -> None" in out and "show_mean None -> True" in out and "hlines" in out
    assert C.edit_data_plot(pyf, [], 0, p_format="words").startswith("ERROR: p_format")
    assert C.edit_data_plot(pyf, [], 0, hlines=["high"]).startswith("ERROR: hlines")


def test_a_paired_plot_of_before_and_after(pyf, tmp_path):
    rng = np.random.default_rng(6)
    b = rng.normal(10, 2, 10)
    path = tmp_path / "mice_before_after.csv"
    pd.DataFrame({"mouse": [f"M{i}" for i in range(10)], "before": b.round(2),
                  "after": (b + rng.normal(1.5, 0.5, 10)).round(2)}).to_csv(path, index=False)
    out = C.add_data_plot(pyf, [], str(path), kind="paired", columns=["before", "after"])
    assert out.startswith("Data-plot panel (paired)"), out
    assert "Paired t-test" in out or "Wilcoxon" in out
    from pyfigures.assistant.plot_info import parse_data_plot, plot_statistics
    stats = plot_statistics(parse_data_plot(_scripts(pyf)[-1]))
    assert stats["n_subjects"] == 10 and stats["comparisons"][0]["p"] < 0.01
    assert "paired" in C.list_data_plot_kinds()


def test_seaborn_colour_per_group_legend_and_axis_range(pyf, tidy):
    from matplotlib.colors import to_rgba
    out = C.add_seaborn_plot(pyf, [], tidy, "catplot", kind="box", x="genotype", y="area_um2", hue="sex",
                             col="day", palette={"female": "#d55e00", "male": "#0072b2"}, legend="top",
                             ylim=[150, 300])
    assert not out.startswith("ERROR"), out
    fig = _draw(_scripts(pyf)[-1])
    assert fig.axes[0].get_ylim() == (150, 300)
    leg = fig.legends[0]
    assert [t.get_text() for t in leg.get_texts()] == ["female", "male"]
    # seaborn desaturates box colours a little: orange (female) and blue (male) all the same
    female, male = (to_rgba(h.get_facecolor()) for h in leg.legend_handles[:2])
    assert female[0] > female[2] and male[2] > male[0]
    renderer = fig.canvas.get_renderer()
    assert leg.get_window_extent(renderer).y0 >= fig.axes[0].get_window_extent(renderer).y1 - 1    # above
    out = C.edit_seaborn_plot(pyf, [], 0, legend="none", remove=["ylim"])
    assert "legend 'top' -> 'none'" in out
    assert not _draw(_scripts(pyf)[-1]).legends
    assert C.edit_seaborn_plot(pyf, [], 0, legend="left").startswith("ERROR: legend")
    assert C.edit_seaborn_plot(pyf, [], 0, ylim=[0]).startswith("ERROR: ylim")


def test_a_table_panel_raw_rows_or_a_summary(pyf, tidy, tmp_path):
    """"add a table of mean ± SD per genotype", "show the values as a table"."""
    out = C.add_table_panel(pyf, [], tidy, by=["genotype", "sex"], value="area_um2",
                            stats=["n", "mean±sd", "median [iqr]"], decimals=1, title="Areas")
    assert out.startswith("Table panel (a summary by genotype, sex: 6 row(s), 5 column(s))"), out
    fig = _draw(_scripts(pyf)[-1])
    texts = [t.get_text() for t in fig.findobj() if hasattr(t, "get_text")]
    assert "mean ± sd" in texts and "WT" in texts and "20" in texts
    from pyfigures.assistant.plot_info import describe_code_panel
    from pyfigures.table_panel import parse
    assert parse(_scripts(pyf)[-1])["by"] == ["genotype", "sex"]
    # the raw rows, some of them
    out = C.edit_table_panel(pyf, [], 0, remove=["by", "stats", "value"], columns=["genotype", "area_um2"],
                             where="day == 7", max_rows=5)
    assert "Table panel changed" in out
    from pyfigures.table_panel import table_cells, parse as p2
    header, rows, note = table_cells(p2(_scripts(pyf)[-1]))
    assert header == ["genotype", "area_um2"] and len(rows) == 5 and note == "55 more row(s) not shown"
    assert C.edit_table_panel(pyf, [], 0, stats=["average"]).startswith("ERROR: unknown statistic")
    assert C.add_table_panel(pyf, [], tidy, by="age").startswith("ERROR: no column")
    # consolidation copies the table and points the panel at the copy
    from pyfigures.plot_tables import consolidate_plot_tables
    copied = consolidate_plot_tables(pyf)
    assert copied and parse(_scripts(pyf)[-1])["csv"].startswith(os.path.splitext(pyf)[0] + ".files")


def test_a_recipe_table_panel(tmp_path, tidy, qapp):
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    recipe = tmp_path / "t.yaml"
    recipe.write_text("output: t.pyf\nrows:\n"
                      f"  - - {{table: {tidy}, by: [genotype], value: area_um2, stats: [n, mean±sem]}}\n"
                      f"    - {{plot: {tidy}, columns: [genotype, area_um2], kind: box}}\n", encoding="utf-8")
    out = build_figure_from_recipe(str(recipe))
    assert '"warnings": []' in out, out


def test_the_gui_inserts_a_table_panel(qapp, monkeypatch, tidy, tmp_path):
    from qtpy.QtWidgets import QComboBox, QDialog, QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure
    from batoolset.drawings.shapes.image2d import Image2D

    EZFIG_GUI.show_tips = lambda self: None
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a)))
    pyf = str(tmp_path / "fig.pyf")
    create_figure(pyf, mode="canvas")
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [tidy]))

    class _Pick:
        def __init__(self, *a, main_widget=None, **k):
            combos = main_widget.findChildren(QComboBox)
            by = next(c for c in combos if c.itemText(0).startswith("(no summary"))
            by.setCurrentIndex(by.findText("genotype"))
            val = next(c for c in combos if c.itemText(0).startswith("(every number"))
            val.setCurrentIndex(val.findText("area_um2"))

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _Pick)
    g.add_table_panel_action()
    assert not warnings, warnings
    script = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)][-1].custom_loading_script
    assert script.startswith("# pyfigures-table: ") and '"by": ["genotype"]' in script
    g._dirty = False


def test_compare_everything_to_one_group(pyf, tidy):
    out = C.add_data_plot(pyf, [], tidy, kind="box", columns=["genotype", "area_um2"], control="wt",
                          only_significant=False)
    assert not out.startswith("ERROR"), out
    assert "control='WT'" in _scripts(pyf)[-1]
    from pyfigures.assistant.plot_info import parse_data_plot, plot_statistics
    stats = plot_statistics(parse_data_plot(_scripts(pyf)[-1]))
    assert ("Dunnett" in stats["test"] or "vs WT" in stats["test"]) and all(c["a"] == "WT" for c in stats["comparisons"])
    assert C.edit_data_plot(pyf, [], 0, control="KO").startswith("ERROR: no group")
    assert "control 'WT' -> None" in C.edit_data_plot(pyf, [], 0, control="")


def test_a_summary_saved_for_the_source_data(tidy, tmp_path):
    out_csv = tmp_path / "summary.csv"
    out = C.summarize_table(tidy, value="area_um2", by=["genotype", "sex"], out_path=str(out_csv))
    assert "Saved to" in out
    df = pd.read_csv(out_csv)
    assert {"genotype", "sex", "n", "mean", "sd"} <= set(df.columns) and len(df) == 6
    out_x = tmp_path / "summary.xlsx"
    assert "Saved to" in C.summarize_table(tidy, by="genotype", out_path=str(out_x))
    assert set(pd.ExcelFile(out_x).sheet_names) == {"day", "area_um2"}
