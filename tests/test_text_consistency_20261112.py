"""QC: the texts of a figure should look alike (user request 2026-11-12: "in a figure
letters should be consistent… this generally applies to scale bars and the rest of the
texts… QC should also check this consistency")."""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _figure(tmp_path, n=3, checks=None):
    from batoolset.img import Img
    from pyfigures.recipe import build_figure_from_recipe
    row = []
    for i in range(n):
        p = str(tmp_path / f"{i}.tif")
        Img(np.full((60, 80), 40 * i + 30, np.uint8), dimensions="hw").save(p)
        row.append({"image": p, "px_to_unit": 0.5, "scale_bar": {"units": 10, "unit": "um"}})
    rp = str(tmp_path / "r.json")
    recipe = {"output": "t.pyf", "rows": [row], "letter_panels": True}
    if checks:
        recipe["checks"] = checks
    with open(rp, "w") as f:
        json.dump(recipe, f)
    out = build_figure_from_recipe(rp)
    return out if checks else out["output"]


def _restyle_one(pyf, tag, nth, css):
    """Put *css* on the text of the *nth* element *tag* (a letter, a scale-bar label)."""
    tree = ET.parse(pyf)
    els = [e for e in tree.getroot().iter(tag) if tag != "TAText2D" or e.findtext("is_letter") == "True"]
    field = els[nth].find("legend" if tag == "ScaleBar" else "text")
    if "<body" not in field.text and "<span" not in field.text:
        field.text = f'<span style="{css};">{field.text}</span>'   # a plain legend: <font color=…>10 µm</font>
        tree.write(pyf)
        return
    field.text = re.sub(r'(<body[^>]*style="[^"]*)"', lambda m: m.group(1) + ' ' + css + ';"', field.text, count=1)
    field.text = re.sub(r'(<span style="[^"]*)"', lambda m: m.group(1) + ' ' + css + ';"', field.text, count=1)
    tree.write(pyf)


def test_a_consistent_figure_passes(tmp_path):
    from pyfigures.mcp_server import check_text_consistency
    d = json.loads(check_text_consistency(_figure(tmp_path)))
    assert d["consistent"] and d["kinds"]["panel letters"]["count"] == 3
    assert d["kinds"]["scale-bar labels"]["count"] == 3


def test_one_bold_letter_and_one_big_scale_bar_label_are_named(tmp_path):
    from pyfigures.mcp_server import check_text_consistency, check_journal_compliance
    pyf = _figure(tmp_path)
    _restyle_one(pyf, "TAText2D", 1, "font-weight:700")
    _restyle_one(pyf, "ScaleBar", 2, "font-size:20pt")
    d = json.loads(check_text_consistency(pyf))
    assert not d["consistent"]
    found = {(i["kind"], i["property"]): i for i in d["issues"]}
    assert found[("panel letters", "bold")]["most_have"] is False
    assert len(found[("panel letters", "bold")]["differ"]) == 1
    assert found[("scale-bar labels", "size")]["differ"][0].endswith("20.0")
    assert "[FAIL] consistent texts" in check_journal_compliance(pyf, width_mm=180) or \
        re.search(r"consistent texts.*FAIL|FAIL.*consistent texts", check_journal_compliance(pyf, width_mm=180))


def test_two_font_families_are_flagged(tmp_path):
    from pyfigures.mcp_server import check_text_consistency
    pyf = _figure(tmp_path, n=2)
    for nth in range(2):
        _restyle_one(pyf, "ScaleBar", nth, "font-family:'Times New Roman'")
    d = json.loads(check_text_consistency(pyf))
    assert any(i["kind"] == "all texts" and i["property"] == "font" for i in d["issues"])


def test_recipe_text_check(tmp_path):
    out = _figure(tmp_path, n=2, checks=["text"])
    assert "text" in json.dumps(out["checks"]) and "consistent" in json.dumps(out["checks"])


def test_qc_menu_shows_the_report(qapp, tmp_path, monkeypatch):
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    g = EZFIG_GUI()
    try:
        g.reload_state(_figure(tmp_path), append=False)
        shown = []
        monkeypatch.setattr(g, "_show_report", lambda title, text: shown.append((title, text)))
        action = next(a for m in g.menuBar.actions() if m.menu() for a in m.menu().actions()
                      if a.text() == "Check text consistency…")
        action.trigger()
        assert shown and shown[0][0] == "Text consistency" and "consistent" in shown[0][1]
    finally:
        g._dirty = False
        g.close()
        g.deleteLater()
