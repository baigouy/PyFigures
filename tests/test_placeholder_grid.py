"""Empty placeholder panels to fill later: MCP add_placeholder_grid, recipe key
placeholder_grid and Insert -> Empty panel grid... (a chat asked for "3 rows per
2 cols with fake images" and spent 25 steps inventing scripted images, 2026-11-03).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _slots(pyf):
    from pyfigures.mcp_tools.core import _is_template
    root = ET.parse(pyf).getroot()
    return [[sum(_is_template(i) for i in row.iter("Image2D")) for row in g.find("content") if row.tag == "Group"]
            for g in root if g.tag == "Group"]


def test_mcp_tool_adds_rows_of_empty_slots_that_can_be_filled(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_placeholder_grid, fill_template
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    result = add_placeholder_grid(pyf, rows=3, columns=2, aspect_ratio="4:3")
    assert "group [0]" in result and "ERROR" not in result
    assert _slots(pyf) == [[2, 2, 2]]
    assert "QRectF(0.0, 0.0, 512.0, 384.0)" in open(pyf, encoding="utf-8").read()     # 4:3 slots
    png = str(tmp_path / "a.png")
    Image.fromarray(np.zeros((30, 40), np.uint8)).save(png)
    assert "ERROR" not in fill_template(pyf, [0, 1], 0, png)
    assert _slots(pyf) == [[2, 1, 2]]
    for bad in (dict(rows=0), dict(columns=21), dict(aspect_ratio="wide"), dict(aspect_ratio=0)):
        assert add_placeholder_grid(pyf, **bad).startswith("ERROR")


def test_aspect_ratio_forms():
    from pyfigures.mcp_tools.core import parse_aspect_ratio
    assert parse_aspect_ratio("3:2") == 1.5 and parse_aspect_ratio("4/3") == pytest.approx(4 / 3)
    assert parse_aspect_ratio("16x9") == pytest.approx(16 / 9) and parse_aspect_ratio(2) == 2.0
    assert parse_aspect_ratio("0:1") is None and parse_aspect_ratio("x") is None and parse_aspect_ratio(-1) is None


def test_recipe_key_builds_a_grid_alone_or_below_rows(tmp_path):
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    png = tmp_path / "a.png"
    Image.fromarray(np.zeros((30, 40), np.uint8)).save(png)
    alone = tmp_path / "alone.yaml"
    alone.write_text("output: alone.pyf\nplaceholder_grid: {rows: 2, columns: 3, aspect_ratio: '3:2'}\n", encoding="utf-8")
    build_figure_from_recipe(str(alone))
    assert _slots(str(tmp_path / "alone.pyf")) == [[3, 3]]
    below = tmp_path / "below.yaml"
    below.write_text("output: below.pyf\nrows:\n  - [a.png]\nplaceholder_grid: {rows: 1, columns: 2}\n", encoding="utf-8")
    build_figure_from_recipe(str(below))
    root = ET.parse(str(tmp_path / "below.pyf")).getroot()
    assert len([g for g in root if g.tag == "Group"]) == 2
    bad = tmp_path / "bad.yaml"
    bad.write_text("output: bad.pyf\nplaceholder_grid: {rows: 2, colums: 2}\n", encoding="utf-8")
    with pytest.raises(RecipeError, match="placeholder_grid"):
        build_figure_from_recipe(str(bad))


def test_insert_menu_entry(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.mcp_server import create_figure
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: pytest.fail(str(a))))
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g.current_file = pyf
    entry = [a for m in g.menuBar.findChildren(type(g.menuBar.actions()[0].menu())) for a in m.actions()
             if a.text() == "Empty panel grid…"]
    assert entry
    monkeypatch.setattr(g, "_ask_placeholder_grid", lambda: (3, 2, "4:3"))
    entry[0].trigger()
    from batoolset.drawings.shapes.group import Group
    outer = [s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Group)]
    assert len(outer) == 1 and [len(r.content) for r in outer[0].content] == [2, 2, 2]
    assert all(i.is_template() for r in outer[0].content for i in r.content)
    monkeypatch.setattr(g, "_ask_placeholder_grid", lambda: None)
    g.add_placeholder_grid_action()            # cancelled: nothing added
    assert len([s for s in g.paint.EZFIG_panel.shapes_to_draw if isinstance(s, Group)]) == 1
    g._dirty = False
    g.close()
