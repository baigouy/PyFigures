"""User, 2026-11-20: "if there are several graphs how will pyfig handle the letters maybe it
should plot side by side but still split". facet= draws the facets inside ONE panel (one
letter); facet_panels=True makes one panel per facet value, side by side in one row, each
with its own title, letter and statistics, on a shared y range."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("staplot")


def _table(tmp_path):
    rows = ["day,genotype,area"]
    for day, scale in ((1, 1.0), (7, 2.0), (14, 4.0)):
        for i in range(6):
            rows += [f"{day},WT,{10 * scale + i}", f"{day},KO,{14 * scale + i}"]
    path = tmp_path / "area.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


def _panels(pyf):
    from pyfigures.mcp_tools.core import _load, _child_text
    from pyfigures.assistant.plot_info import parse_data_plot
    _t, root = _load(pyf)
    return [parse_data_plot(_child_text(p, "custom_loading_script") or "") for p in root.iter("Image2D")]


def test_one_panel_per_facet_side_by_side_on_one_y_range(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    from pyfigures.mcp_tools.core import _load, _top_groups
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    out = add_data_plot(pyf, [], _table(tmp_path), kind="box", columns=["genotype", "area"],
                        facet="day", facet_panels=True, ylabel="Area")
    assert out.startswith("3 data-plot panels added side by side"), out
    assert "shared y range" in out
    specs = _panels(pyf)
    assert len(specs) == 3
    assert [s["title"] for s in specs] == ["day = 1", "day = 7", "day = 14"]
    assert all("`day` ==" in s["where"] for s in specs)
    assert not any(s.get("facet") for s in specs)
    assert len({tuple(s["ylim"]) for s in specs}) == 1                     # one y range
    low, high = specs[0]["ylim"]
    assert low <= 10 and high >= 14 * 4 + 5                                # every panel's data fits
    _t, root = _load(pyf)
    tops = _top_groups(root)
    assert len([c for c in root.iter("Image2D")]) == 3
    assert not tops or len(tops) == 1                                      # one row, not three


def test_facet_panels_into_a_figure_of_rows_go_into_one_new_row(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image, add_data_plot
    from pyfigures.mcp_tools.core import _load, _top_groups
    png = tmp_path / "cells.png"
    Image.new("L", (100, 80), 80).save(png)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    add_image(pyf, [], str(png))
    add_image(pyf, [], str(png))
    _t, root = _load(pyf)
    before = len(_top_groups(root))
    out = add_data_plot(pyf, [], _table(tmp_path), kind="bar", columns=["genotype", "area"],
                        facet="day", facet_panels=True)
    assert "3 data-plot panels" in out, out
    _t, root = _load(pyf)
    tops = _top_groups(root)
    if before:                       # rows existed: the three plots share ONE new row
        assert len(tops) == before + 1
        assert sum(c.tag == "Image2D" for c in tops[-1].find("content")) == 3


def test_facet_panels_needs_a_facet_and_refuses_facet_row(tmp_path):
    from pyfigures.mcp_server import create_figure, add_data_plot
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    csv = _table(tmp_path)
    assert add_data_plot(pyf, [], csv, kind="box", columns=["genotype", "area"], facet_panels=True).startswith("ERROR")
    assert add_data_plot(pyf, [], csv, kind="box", columns=["genotype", "area"], facet="day",
                         facet_row="genotype", facet_panels=True).startswith("ERROR")
    assert _panels(pyf) == []


def test_a_recipe_splits_the_facets_into_panels(tmp_path, qapp):
    from pyfigures.mcp_tools.workflow import build_figure_from_recipe
    csv = _table(tmp_path)
    recipe = tmp_path / "r.yaml"
    recipe.write_text("output: r.pyf\nrows:\n"
                      f"  - - {{plot: {csv}, kind: box, columns: [genotype, area], facet: day, facet_panels: true}}\n",
                      encoding="utf-8")
    out = build_figure_from_recipe(str(recipe))
    assert '"warnings": []' in out, out
    assert [s["title"] for s in _panels(str(tmp_path / "r.pyf"))] == ["day = 1", "day = 7", "day = 14"]


def test_the_gui_dialog_offers_separate_panels(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QCheckBox, QComboBox, QDialog, QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure
    from batoolset.drawings.shapes.image2d import Image2D

    EZFIG_GUI.show_tips = lambda self: None
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a)))
    csv = _table(tmp_path)
    pyf = str(tmp_path / "fig.pyf")
    create_figure(pyf, mode="canvas")
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    monkeypatch.setattr(pfgui, "openFileNamesDialog", staticmethod(lambda *a, **k: [csv]))

    class _Pick:
        def __init__(self, *a, main_widget=None, **k):
            combos = main_widget.findChildren(QComboBox)

            def pick(first_item, text):
                combo = next(c for c in combos if c.count() and c.itemText(0) == first_item)
                combo.setCurrentIndex(combo.findText(text))
                assert combo.currentText() == text, (first_item, text)
            pick("auto", "box")
            pick("x: whole table", "genotype")
            pick("value: -", "area")
            pick("facets: none", "day")
            next(c for c in main_widget.findChildren(QCheckBox) if c.text() == "separate panels").setChecked(True)

        def exec_(self):
            return QDialog.Accepted
    monkeypatch.setattr(pfgui, "CustomDialog", _Pick)
    g.add_data_plot_action()
    assert not warnings, warnings
    plots = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Image2D)]
    scripts = [p.custom_loading_script for p in plots]
    assert len(plots) == 3 and not any("plot_facets" in s for s in scripts)
    assert all("`day` ==" in s for s in scripts)
    g._dirty = False
