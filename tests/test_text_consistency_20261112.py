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


def test_letters_may_have_their_own_font_the_other_texts_share_one(tmp_path):
    """"Letters usually have one font, the rest of the text of the figure (legends,
    extra labels) the same font, which can differ from the letters'" (user, 2026-11-12)."""
    from pyfigures.mcp_server import check_text_consistency
    pyf = _figure(tmp_path, n=2)
    for nth in range(2):
        _restyle_one(pyf, "ScaleBar", nth, "font-family:'Times New Roman'")
    assert json.loads(check_text_consistency(pyf))["consistent"]        # letters in another font: fine
    _restyle_one(pyf, "ScaleBar", 1, "font-family:'Courier New'")
    d = json.loads(check_text_consistency(pyf))
    assert not d["consistent"] and any(i["property"] == "font" for i in d["issues"])


def _label_font(pyf, family):
    """Give the first non-letter text (or a new one) the font *family*."""
    from pyfigures.mcp_server import add_annotation
    add_annotation(pyf, [0], 0, "control")
    tree = ET.parse(pyf)
    ta = next(e for e in tree.getroot().iter("TAText2D") if e.findtext("is_letter") != "True")
    field = ta.find("text")
    raw = field.text
    quoted = raw.startswith('""')
    html = raw[2:-2] if quoted else raw
    html = f"<span style=\"font-family:'{family}';\">{html}</span>" if "<span" not in html else \
        re.sub(r'(<span style=")', rf"\1font-family:'{family}'; ", html, count=1)
    field.text = f'""{html}""' if quoted else html
    tree.write(pyf)


def test_new_scale_bars_take_the_font_of_the_other_texts(tmp_path):
    """Scale-bar labels were saved in Qt's generic "Sans Serif", drawn in another font
    than the labels next to them (user request 2026-11-12)."""
    from pyfigures.mcp_server import set_scale_bar_all, set_scale_bar, check_text_consistency
    from pyfigures.mcp_tools.core import _html_font_family
    pyf = _figure(tmp_path, n=2)
    _label_font(pyf, "Courier New")
    set_scale_bar_all(pyf, bar_width_in_units=5, px_to_unit=0.5)
    fams = [_html_font_family(e.findtext("legend")) for e in ET.parse(pyf).getroot().iter("ScaleBar")]
    assert fams == ["Courier New", "Courier New"]
    d = json.loads(check_text_consistency(pyf))
    assert d["consistent"], d["summary"]
    # a label given its own font keeps it
    _restyle_one(pyf, "ScaleBar", 0, "font-family:'Arial'")
    set_scale_bar(pyf, [0], 1, bar_width_in_units=8)
    fams = [_html_font_family(e.findtext("legend")) for e in ET.parse(pyf).getroot().iter("ScaleBar")]
    assert fams[0] == "Arial"


def test_a_scale_bar_added_in_the_panel_editor_takes_that_font(qapp):
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.drawings.shapes.scalebar import ScaleBar
    from batoolset.drawings.shapes.txt2d import TAText2D
    from pyfigures.text_fonts import scale_bar_in_text_font
    from pyfigures.mcp_tools.core import _html_font_family
    panel = Image2D(data=np.zeros((50, 50), dtype=np.uint8))
    panel.annotations = [TAText2D("<span style=\"font-family:'Courier New';\">control</span>")]
    sb = ScaleBar(bar_width_in_units=10, legend=TAText2D("10 µm"))
    assert scale_bar_in_text_font(sb, [panel], fallback="Arial")
    assert _html_font_family(sb.legend.getHtmlText()) == "Courier New"
    alone = ScaleBar(bar_width_in_units=10, legend=TAText2D("10 µm"))
    assert scale_bar_in_text_font(alone, [], fallback="Arial")              # no other text: the figure font
    assert _html_font_family(alone.legend.getHtmlText()) == "Arial"
    assert not scale_bar_in_text_font(sb, [panel], fallback="Arial")        # it has its own now


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
