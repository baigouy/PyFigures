"""A figure taller than the journal's maximum height (Nature: "The full depth
of a Nature page is 247 mm"): narrowed to fit, put in a smaller column, or
kept — the user's choice — and reported by the compliance check."""
from __future__ import annotations

import json
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFIGURES_JOURNAL_STYLES", str(tmp_path / "styles"))


@pytest.fixture
def tall(tmp_path, qapp):
    """Two square images stacked: about twice as tall as wide."""
    from PIL import Image
    for k, name in enumerate("ab"):
        rng = np.random.default_rng(k)
        Image.fromarray((rng.random((200, 200)) * 200 + 20).astype(np.uint8)).save(
            tmp_path / f"{name}.png")
    import pyfigures.mcp_server as M
    res = M.build_figure_from_recipe(str(tmp_path / "r.yaml"),
                                     recipe_text="output: f.pyf\nletter_panels: false\n"
                                                 "layout: a/b\n")
    assert not res.startswith("ERROR"), res
    return str(tmp_path / "f.pyf")


def _width_mm(pyf):
    from pyfigures.mcp_tools.core import _stored_target
    return _stored_target(pyf)["width_mm"]


def test_sourced_max_heights():
    from pyfigures.journal_styles import journal_info
    from pyfigures.mcp_tools.core import _journal_max_height
    assert _journal_max_height("nature")[0] == 247
    assert _journal_max_height("plos one")[0] == 222.3               # alias
    assert _journal_max_height("pnas")[0] == 225
    assert _journal_max_height("science") is None                    # its page gives none
    assert journal_info("nature")["max_height_mm"] == 247
    assert "max_height_mm" not in journal_info("cell")


def test_too_tall_is_narrowed_and_the_choices_listed(tall):
    from pyfigures.mcp_server import resize_figure
    from pyfigures.mcp_tools.core import _figure_height_mm
    r = resize_figure(tall, journal="nature", column="double")
    assert "above the maximum height 247mm" in r and "Choices:" in r, r
    assert "fit_height='column' uses the single column" in r and "fit_height=false" in r
    h = _figure_height_mm(tall)
    assert 240 <= h <= 247.6, h
    assert _width_mm(tall) < 183


def test_column_choice_and_off(tall):
    from pyfigures.mcp_server import resize_figure
    from pyfigures.mcp_tools.core import _figure_height_mm, _stored_target
    r = resize_figure(tall, journal="nature", column="double", fit_height="column")
    assert "set to the single column (89mm)" in r, r
    assert _stored_target(tall)["column"] == "single" and _width_mm(tall) == 89
    assert _figure_height_mm(tall) <= 247
    r = resize_figure(tall, journal="nature", column="double", fit_height=False)
    assert "kept at 183.0mm" in r and _width_mm(tall) == 183
    assert resize_figure(tall, journal="nature", fit_height="maybe").startswith("ERROR")


def test_a_short_figure_is_left_alone(tall):
    from pyfigures.mcp_server import resize_figure
    r = resize_figure(tall, journal="nature", column="single")      # ~180 mm tall
    assert "maximum height" not in r and _width_mm(tall) == 89


def test_explicit_max_height(tall):
    from pyfigures.mcp_server import resize_figure
    from pyfigures.mcp_tools.core import _figure_height_mm
    r = resize_figure(tall, width_mm=100, max_height_mm=120)
    assert "maximum height 120mm" in r, r
    assert _figure_height_mm(tall) <= 120.3


def test_compliance_checks_the_height(tall):
    from pyfigures.mcp_server import check_journal_compliance, resize_figure
    resize_figure(tall, journal="nature", column="double", fit_height=False)
    rep = check_journal_compliance(tall, journal="nature", column="double")
    assert "height" in rep and "vs maximum 247mm" in rep, rep
    line = next(ln for ln in rep.splitlines() if "vs maximum 247mm" in ln)
    assert "✗" in line or "FAIL" in line.upper(), line
    resize_figure(tall, journal="nature", column="double")           # narrowed: both pass
    rep = check_journal_compliance(tall)                              # the stored target
    width = next(ln for ln in rep.splitlines() if "vs target" in ln)
    assert "narrower so that its height fits" in width, rep
    assert "✗" not in width and "FAIL" not in width.upper(), width


def test_saved_style_height_rule(tall):
    import pyfigures.journal_styles as js
    from pyfigures.mcp_server import resize_figure
    page = "Figures: 180 mm maximum width; maximum height 150 mm."
    reply = {"rules": [
        {"kind": "width", "label": "maximum width", "relation": "max", "value": 180,
         "unit": "mm", "applies_to": "figures", "evidence_quote": "180 mm maximum width"},
        {"kind": "height", "label": "maximum height", "relation": "max", "value": 150,
         "unit": "mm", "applies_to": "figures", "evidence_quote": "maximum height 150 mm"}]}
    js.save(js.import_model_reply(json.dumps(reply), page, "Journal Y", "final", "")[0])
    assert js.journal_info("Journal Y")["max_height_mm"] == 150
    r = resize_figure(tall, journal="Journal Y", column="maximum width")
    assert "maximum height 150mm" in r, r


def test_recipe_and_gui(tall, tmp_path):
    import pyfigures.mcp_server as M
    res = json.loads(M.build_figure_from_recipe(
        str(tmp_path / "r2.yaml"),
        recipe_text="output: g.pyf\nletter_panels: false\nlayout: a/b\njournal: nature\n"
                    "column: double\nfit_height: column\n"))
    assert any("Choices:" in w for w in res["warnings"]), res
    bad = M.build_figure_from_recipe(str(tmp_path / "r3.yaml"),
                                     recipe_text="output: h.pyf\nlayout: a/b\nfit_height: 3\n")
    assert bad.startswith("ERROR") and "fit_height" in bad
    from pyfigures.gui.pfgui import _JournalDialog
    d = _JournalDialog(with_apply_options=True)
    d.journal_combo.setCurrentText("nature")
    assert "Maximum height 247 mm" in d.style_label.text()
    d.fit_height_combo.setCurrentIndex(1)
    assert d.values()["fit_height"] == "column"
