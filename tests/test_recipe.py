"""
build_figure_from_recipe — declarative, reproducible figure recipes.

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import builtins
import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _png(path, h=40, w=60, val=100):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.full((h, w), val, np.uint8)).save(path)
    return path


def _project(d):
    _png(os.path.join(d, "wt.png"))
    _png(os.path.join(d, "ko.png"), 60, 60)
    for i in range(3):
        _png(os.path.join(d, "reps", f"rep{i}.png"), 30, 45, 50 + i)
    with open(os.path.join(d, "counts.csv"), "w") as f:
        f.write("WT,KO\n10,20\n11,22\n12,21\n9,23\n")


YAML = """\
output: out/Figure1.pyf
letter_panels: true
defaults:
  px_to_unit: 0.1
  scale_bar: {units: 1, unit: "um"}
rows:
  - - {image: wt.png, lut: red}
    - {image: ko.png, crop: {left: 5, right: 5}}
  - - {glob: "reps/rep*.png", lut: gray}
  - - {plot: counts.csv, kind: box, ylabel: "cells / field", label: "G"}
"""


def _write(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def _structure(pyf):
    root = ET.parse(pyf).getroot()
    rows = []
    for g in root.findall("Group"):
        panels = []
        for img in g.find("content").findall("Image2D"):
            fn = (img.findtext("filename") or "").strip('"')
            panels.append((os.path.basename(fn), img.findtext("LUTs"),
                           img.findtext("crop_left"),
                           img.find("annotations/ScaleBar") is not None))
        rows.append(panels)
    return rows


def test_build_yaml_recipe(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    d = str(tmp_path)
    _project(d)
    res = build_figure_from_recipe(_write(d, "fig1.yaml", YAML))
    assert res["rows"] == 3 and res["images"] == 5 and res["plots"] == 1
    assert res["lettered"] >= 5
    rows = _structure(res["output"])
    assert [len(r) for r in rows] == [2, 3, 1]
    assert [p[0] for p in rows[1]] == ["rep0.png", "rep1.png", "rep2.png"]  # sorted glob
    assert "RED" in rows[0][0][1] and "GRAY" in rows[1][0][1]
    assert rows[0][1][2] == "5"                                  # crop applied
    assert all(p[3] for r in rows[:2] for p in r)                # default scale bar
    assert res["caption"] == "auto stub"


def test_letters_and_caption(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures.mcp_server import get_figure_caption
    d = str(tmp_path)
    _project(d)
    res = build_figure_from_recipe(_write(d, "r.json", json.dumps({
        "output": "f.pyf", "caption": "My caption.", "title": "Figure 2",
        "panels": [{"image": "wt.png"}, {"image": "ko.png"}, {"image": "wt.png"}],
        "columns": 2})))
    assert [len(r) for r in _structure(res["output"])] == [2, 1]
    cap = json.loads(get_figure_caption(res["output"]))
    assert cap["caption"] == "My caption." and cap["title"] == "Figure 2"
    letters = [ta.findtext("text") for ta in ET.parse(res["output"]).getroot().iter("TAText2D")
               if ta.findtext("is_letter") == "True"]
    assert len(letters) == 3


def test_journal_resize(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    d = str(tmp_path)
    _project(d)
    res = build_figure_from_recipe(_write(d, "r.json", json.dumps({
        "output": "f.pyf", "journal": "nature", "column": "single",
        "rows": [[{"image": "wt.png"}, {"image": "ko.png"}]]})))
    assert res["journal"] == "nature (single)"


def test_bare_file_names_are_image_panels(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    d = str(tmp_path)
    _project(d)
    res = build_figure_from_recipe(_write(d, "r.yaml", "output: f.pyf\n"
                                          "rows:\n  - [wt.png, ko.png]\n"))
    assert res["images"] == 2
    assert [p[0] for p in _structure(res["output"])[0]] == ["wt.png", "ko.png"]


def test_numeric_column_from_yaml(tmp_path):
    # YAML reads `column: 1.5` as a float — it used to crash the resize
    from pyfigures.recipe import build_figure_from_recipe
    d = str(tmp_path)
    _project(d)
    res = build_figure_from_recipe(_write(d, "r.yaml", "output: f.pyf\njournal: cell\n"
                                          "column: 1.5\nrows:\n  - - {image: wt.png}\n"))
    assert res["journal"] == "cell (1.5)" and not res["warnings"]


def test_json_recipe_without_pyyaml(tmp_path, monkeypatch):
    from pyfigures import recipe
    d = str(tmp_path)
    _project(d)
    real_import = builtins.__import__

    def no_yaml(name, *a, **k):
        if name == "yaml":
            raise ImportError("no yaml")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_yaml)
    ok = recipe.build_figure_from_recipe(_write(d, "r.json", json.dumps(
        {"output": "f.pyf", "rows": [[{"image": "wt.png"}]]})))
    assert ok["images"] == 1
    with pytest.raises(recipe.RecipeError, match="PyYAML"):
        recipe.build_figure_from_recipe(_write(d, "r.yaml", "output: f.pyf\n"))


@pytest.mark.parametrize("recipe_obj, msg", [
    ({"output": "f.pyf", "rows": [[{"image": "missing.png"}]]}, "file not found"),
    ({"output": "f.pyf", "rows": [[{"image": "wt.png", "colour": "red"}]]}, "unknown key"),
    ({"output": "f.pyf", "rows": [[{"image": "wt.png", "plot": "counts.csv"}]]}, "exactly one"),
    ({"output": "f.pyf", "rows": [[{"glob": "nothing*.png"}]]}, "matched no files"),
    ({"output": "f.pyf", "rows": [[{"image": "wt.png"}]], "colour": 1}, "top-level"),
    ({"rows": [[{"image": "wt.png"}]]}, "'output'"),
    ({"output": "f.pyf", "rows": [[{"image": "wt.png", "lut": "NOT_A_LUT"}]]}, "lut"),
    ({"output": "f.pyf", "rows": [[{"image": "wt.png", "crop": {"left": -1}}]]}, "crop"),
])
def test_invalid_recipes_fail_loudly(tmp_path, recipe_obj, msg):
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    d = str(tmp_path)
    _project(d)
    with pytest.raises(RecipeError, match=msg):
        build_figure_from_recipe(_write(d, "r.json", json.dumps(recipe_obj)))


def test_mcp_tool_and_determinism(tmp_path):
    from pyfigures.mcp_server import build_figure_from_recipe
    d = str(tmp_path)
    _project(d)
    rp = _write(d, "fig1.yaml", YAML)
    r1 = json.loads(build_figure_from_recipe(rp))
    s1 = _structure(r1["output"])
    xml1 = open(r1["output"], encoding="utf-8").read()
    r2 = json.loads(build_figure_from_recipe(rp))
    assert _structure(r2["output"]) == s1
    assert open(r2["output"], encoding="utf-8").read() == xml1   # byte-identical rebuild
    assert build_figure_from_recipe(os.path.join(d, "nope.yaml")).startswith("ERROR")


def test_cli_build_and_exit_codes(tmp_path, capsys):
    from pyfigures.recipe import main
    d = str(tmp_path)
    _project(d)
    rp = _write(d, "fig1.yaml", YAML)
    assert main(["build", rp]) == 0
    out = json.loads(capsys.readouterr().out)
    assert os.path.isfile(out["output"])
    bad = _write(d, "bad.json", json.dumps({"output": "x.pyf",
                                            "rows": [[{"image": "missing.png"}]]}))
    assert main(["build", bad]) == 1
    assert "file not found" in capsys.readouterr().err


def test_gui_build_from_recipe(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import pfgui
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    shown = {}
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.update(msg=a[2])))
    monkeypatch.setattr(QMessageBox, "warning",
                        staticmethod(lambda *a, **k: shown.update(err=a[2])))
    d = str(tmp_path)
    _project(d)
    rp = _write(d, "fig1.yaml", YAML)
    monkeypatch.setattr(pfgui, "openFileNameDialog", lambda **k: rp)
    g = EZFIG_GUI()
    g.build_from_recipe_action()
    assert "err" not in shown, shown.get("err")
    assert g.current_file.endswith("Figure1.pyf")
    assert len(g.paint.EZFIG_panel.shapes_to_draw) >= 3
    g._dirty = False


def test_built_figure_renders(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    from pyfigures.mcp_server import export_figure
    d = str(tmp_path)
    _project(d)
    res = build_figure_from_recipe(_write(d, "fig1.yaml", YAML))
    png = os.path.join(d, "fig.png")
    out = export_figure(res["output"], png, dpi=72)
    assert not out.startswith("ERROR"), out
    assert os.path.isfile(png) and os.path.getsize(png) > 1000
