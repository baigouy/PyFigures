"""Half and split violins, plots from some columns of a tidy table, and the table tools
(PyFigures chat, 2026-11-18: "make it half violins" could not be done; the chat then
looped looking for the columns of the table, found no tool and stopped).

User: "I like them for split by conditions, which would require a label in the plot";
"add an xls file to test that, you could for example have sex split (facet) in a new
column"; "table tools maybe relying on a pandas backend could be useful"; "make all
these kinds of plots possible"; "make it also possible to list factorizable columns".
"""
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

pytest.importorskip("openpyxl")


@pytest.fixture
def mice(tmp_path):
    """sex_split.xlsx: a tidy sheet 'mice' (genotype, treatment, sex, day, area) and a
    three-column sheet 'by sex' (genotype, sex, area)."""
    rng = np.random.default_rng(7)
    rows = []
    for g, ge in (("WT", 0), ("mutA", -20), ("mutB", 5)):
        for t in ("ctrl", "drug"):
            for sx, se in (("female", 0), ("male", 30)):
                for day in (7, 14):
                    rows += [(g, t, sx, day, 200 + ge + se + rng.normal(0, 8)) for _ in range(8)]
    df = pd.DataFrame(rows, columns=["genotype", "treatment", "sex", "day", "area"])
    path = tmp_path / "sex_split.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="mice", index=False)
        df[["genotype", "sex", "area"]].to_excel(w, sheet_name="by sex", index=False)
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
    """The panel's figure, as PyFigures runs the script."""
    import matplotlib.pyplot as plt
    me = types.SimpleNamespace()
    exec(compile(script, "panel", "exec"), {"plt": plt}, {"self": me})
    return me.img


def test_make_it_half_violins(pyf, mice):
    out = C.add_data_plot(pyf, [], mice, sheet="mice", kind="violin", columns=["genotype", "area"])
    assert "violin" in out and not out.startswith("ERROR"), out
    assert "violin_side None -> 'left'" in C.edit_data_plot(pyf, [], 0, violin_side="half")
    script = _scripts(pyf)[-1]
    assert "violin_side='left'" in script and "columns=['genotype', 'area']" in script
    ax = _draw(script).axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["WT", "mutA", "mutB"]
    assert "violin_side 'left' -> None" in C.edit_data_plot(pyf, [], 0, violin_side="both")
    assert C.edit_data_plot(pyf, [], 0, violin_side="up").startswith("ERROR: violin_side")


def test_split_violins_by_sex_with_a_legend_naming_the_halves(pyf, mice):
    out = C.add_data_plot(pyf, [], mice, sheet="by sex", kind="split_violin", violin_inner="box")
    assert out.startswith("Data-plot panel (split_violin)"), out
    assert "each pair of halves compared" in out
    ax = _draw(_scripts(pyf)[-1]).axes[0]
    assert [t.get_text() for t in ax.get_legend().get_texts()] == ["female", "male"]
    # the chat sees the pairs' tests
    from pyfigures.assistant.plot_info import parse_data_plot, plot_statistics
    stats = plot_statistics(parse_data_plot(_scripts(pyf)[-1]))
    assert [c["x"] for c in stats["split_comparisons"]] == ["WT", "mutA", "mutB"]


def test_split_violins_from_three_columns_of_a_tidy_sheet(pyf, mice):
    out = C.add_data_plot(pyf, [], mice, sheet="mice", kind="split_violin",
                          columns=["treatment", "sex", "area"])
    assert not out.startswith("ERROR"), out
    ax = _draw(_scripts(pyf)[-1]).axes[0]
    assert [t.get_text() for t in ax.get_xticklabels()] == ["ctrl", "drug"]
    # switching the columns of the same panel; [] = the whole table again
    assert "columns ['treatment', 'sex', 'area'] -> ['genotype', 'sex', 'area']" in C.edit_data_plot(
        pyf, [], 0, columns=["genotype", "sex", "area"])
    bad = C.edit_data_plot(pyf, [], 0, columns=["genotype", "area"])
    assert bad.startswith("ERROR") and "3 columns" in bad
    bad = C.add_data_plot(pyf, [], mice, sheet="mice", kind="split_violin", columns=["genotype", "day", "area"])
    assert not bad.startswith("ERROR")          # day: 7 / 14, two levels
    bad = C.add_data_plot(pyf, [], mice, sheet="mice", kind="split_violin", columns=["genotype", "age", "area"])
    assert bad.startswith("ERROR") and "no column" in bad


def test_split_violin_needs_a_two_level_factor(pyf, tmp_path):
    path = tmp_path / "three.csv"
    pd.DataFrame({"g": list("aabbcc") * 3, "d": ["d1", "d2", "d3"] * 6, "v": range(18)}).to_csv(path, index=False)
    out = C.add_data_plot(pyf, [], str(path), kind="split_violin")
    assert out.startswith("ERROR") and "two levels" in out


def test_split_violins_faceted_with_seaborn(pyf, mice):
    out = C.add_seaborn_plot(pyf, [], mice, "catplot", sheet="mice", kind="violin", x="genotype", y="area",
                             hue="sex", col="treatment", options={"split": True})
    assert "faceted by treatment" in out, out
    fig = _draw(_scripts(pyf)[-1])
    legend = fig.legends[0].get_window_extent(fig.canvas.get_renderer())
    last = fig.axes[-1].get_window_extent(fig.canvas.get_renderer())
    assert legend.x0 >= last.x1 - 1                 # the legend beside the facets, not on one


def test_the_table_tools_say_the_columns_factors_and_numbers(mice):
    text = C.describe_table(mice, sheet="mice", rows=3)
    for word in ("192 rows", "Sheets: mice, by sex", "- sex: text, 2 levels: female (96), male (96)",
                 "- area: numbers", "First 3 rows", "split violins by treatment, sex"):
        assert word in text, (word, text)
    factors = C.list_factor_columns(mice, sheet="mice")
    for word in ("- genotype (text, 3 levels", "- sex (text, 2 levels", "split violin halves",
                 "- day (numbers, 2 levels: 7 (96), 14 (96))", "Value columns (numbers): area",
                 "kind='split_violin', columns=["):
        assert word in factors, (word, factors)
    summary = C.summarize_table(mice, value="area", by=["genotype", "sex"], where="day == 14", sheet="mice")
    assert "96 rows where day == 14" in summary and "female" in summary and "median" in summary
    assert C.summarize_table(mice, value="weight", sheet="mice").startswith("ERROR: no column")
    assert C.summarize_table(mice, where="nope ==", sheet="mice").startswith("ERROR: cannot apply")


def test_the_kinds_list_and_the_chat_hint_name_them():
    text = C.list_data_plot_kinds()
    for word in ("split_violin", "violin_side='left'", "options={'split': true}"):
        assert word in text, word
    from pyfigures.assistant.categorized_mcp import __file__ as hint_file
    hint = open(hint_file, encoding="utf-8").read()
    for word in ("describe_table(csv_path, sheet)", "list_factor_columns", '"split_violin"', 'violin_side="left"'):
        assert word in hint, word


def test_a_recipe_takes_columns_and_violin_side(tmp_path, mice, qapp):
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    recipe = tmp_path / "r.yaml"
    recipe.write_text(
        "output: r.pyf\nrows:\n"
        f"  - - {{plot: {mice}, sheet: mice, columns: [genotype, sex, area], kind: split_violin}}\n"
        f"    - {{plot: {mice}, sheet: mice, columns: [genotype, area], kind: violin, violin_side: right}}\n",
        encoding="utf-8")
    out = build_figure_from_recipe(str(recipe))
    assert '"plots": 2' in out and '"warnings": []' in out, out
    scripts = _scripts(str(tmp_path / "r.pyf"))
    assert any("kind='split_violin'" in s and "columns=['genotype', 'sex', 'area']" in s for s in scripts)
    assert any("violin_side='right'" in s for s in scripts)


def test_the_gui_dialog_picks_the_columns_and_half_violins(qapp, monkeypatch, mice, tmp_path):
    """Insert -> Data plot: the columns of a tidy sheet (x, split, value) and the violin
    options, as the MCP tools and the recipes take them."""
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
    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [mice]))

    class _Pick:
        def __init__(self, *a, main_widget=None, **k):
            combos = main_widget.findChildren(QComboBox)

            def pick(first_item, text):
                combo = next(c for c in combos if c.count() and c.itemText(0) == first_item)
                combo.setCurrentIndex(combo.findText(text))
                assert combo.currentText() == text, (first_item, text)
            sheet = next(c for c in combos if c.findText("by sex") >= 0)
            sheet.setCurrentIndex(sheet.findText("mice"))            # refills the column lists
            pick("auto", "split_violin")
            pick("x: whole table", "genotype")
            pick("split / colour: none", "sex")
            pick("value: -", "area")
            pick("lines inside", "mini box inside")

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _Pick)
    g.add_data_plot_action()
    assert not warnings, warnings
    imgs = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)]
    script = imgs[-1].custom_loading_script
    assert "columns=['genotype', 'sex', 'area']" in script and "violin_inner='box'" in script, script[-600:]
    assert [t.get_text() for t in imgs[-1].img.axes[0].get_legend().get_texts()] == ["female", "male"]
    g._dirty = False
