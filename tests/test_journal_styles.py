"""Journal styles from a journal's own guidelines (pyfigures/journal_styles.py,
GUI QC → Journal styles…, MCP mcp_tools/journal.py), integrated from the
chatGPT prototype of 2026-10-19 (journal_style_lab). Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from pyfigures import journal_styles as js

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "data", "pnas_digital_art_excerpt.txt"), encoding="utf-8") as _f:
    PNAS = _f.read()

PNAS_REPLY = {"rules": [
    {"kind": "width", "label": "single column", "relation": "target", "value": 87,
     "unit": "mm", "applies_to": "1 column at publication size",
     "evidence_quote": "1 column wide (20.5 picas / 3.42” / 8.7 cm)"},
    {"kind": "width", "label": "1.5 columns", "relation": "target", "value": 114,
     "unit": "mm", "applies_to": "1.5 columns", "evidence_quote": "1.5 columns wide (27 picas / 4.5” / 11.4 cm)"},
    {"kind": "width", "label": "2 columns", "relation": "target", "value": 178, "unit": "mm",
     "applies_to": "2 columns", "evidence_quote": "2 columns wide (42.125 picas / 7” / 17.8 cm)"},
    {"kind": "height", "label": "maximum height", "relation": "recommended", "value": 225,
     "unit": "mm", "applies_to": "leave room for the legend",
     "evidence_quote": "Recommended max height: 54 picas / 9” / 22.5 cm."},
    {"kind": "resolution", "label": "halftones", "relation": "min", "value": 300, "unit": "dpi",
     "applies_to": "halftone (photographs, no text)",
     "evidence_quote": "The suggested minimum resolution for this type of image is 300 ppi at publication size."},
    {"kind": "resolution", "label": "combination halftones", "relation": "range", "value": 600,
     "maximum": 900, "unit": "dpi", "applies_to": "combination (images with text)",
     "evidence_quote": "The preferred resolution for this type of image is between 600 and 900 ppi at publication size."},
    {"kind": "font_size", "label": "text size", "relation": "range", "value": 6, "maximum": 8,
     "unit": "pt", "applies_to": "all text in figures",
     "evidence_quote": "Size any text in your figure to at least 6–8 points."},
    {"kind": "color_mode", "label": "colour mode", "relation": "allowed", "value": "RGB",
     "unit": "text", "applies_to": "colour images",
     "evidence_quote": "All color image files must be submitted in their original RGB color."},
]}


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFIGURES_JOURNAL_STYLES", str(tmp_path / "styles"))
    return tmp_path / "styles"


def _pnas_style(journal="PNAS", stage="final"):
    return js.import_model_reply(json.dumps(PNAS_REPLY), PNAS, journal, stage,
                                 "https://www.pnas.org/pb-assets/authors/digitalart.pdf")


# ---------------------------------------------------------------- evidence

def test_units_are_converted_from_the_quote():
    assert js.supported_numbers("(20.5 picas / 3.42” / 8.7 cm)", "mm") == pytest.approx([86.868, 87.0])
    assert js.supported_numbers("between 600 and 900 ppi", "dpi") == [600, 900]
    assert js.supported_numbers("600–900 ppi", "dpi") == [600, 900]
    assert js.supported_numbers("at least 6–8 points", "pt") == [6, 8]
    assert js.supported_numbers("width 85 mm", "dpi") == []


def test_a_real_pnas_extraction_validates_and_gives_the_columns():
    style, warnings = _pnas_style()
    assert style["status"] == "draft" and len(style["rules"]) == 8
    assert js.columns_mm(style) == {"single": 87, "1.5": 114, "double": 178}
    assert js.min_value(style, "font_size")[0] == 6
    assert js.min_value(style, "resolution", "halftone|photo")[0] == 300
    assert not [w for w in warnings if w.startswith("conflicting")]


@pytest.mark.parametrize("change, message", [
    ({"value": 120}, "not written in its quote"),                 # invented number
    ({"evidence_quote": "1 column wide (8.9 cm)"}, "not in the pasted text"),   # invented quote
    ({"unit": "pt"}, "not written in its quote"),                 # wrong unit
    ({"kind": "colour"}, "kind must be one of"),
    ({"maximum": 100}, "only used with relation 'range'"),
])
def test_unsupported_rules_are_refused(change, message):
    reply = json.loads(json.dumps(PNAS_REPLY))
    reply["rules"][0].update(change)
    with pytest.raises(js.StyleError, match=message):
        js.import_model_reply(json.dumps(reply), PNAS, "PNAS", "final")


def test_text_value_must_be_in_its_quote():
    reply = {"rules": [dict(PNAS_REPLY["rules"][-1], value="CMYK")]}
    with pytest.raises(js.StyleError, match="not in its quote"):
        js.import_model_reply(json.dumps(reply), PNAS, "PNAS", "final")


def test_a_model_cannot_change_provenance_or_approve_itself():
    reply = dict(PNAS_REPLY, journal="Nature", stage="initial", status="reviewed",
                 source_text="1 column wide (9.9 cm)")
    reply["rules"] = [dict(r, origin="manual") for r in PNAS_REPLY["rules"]]
    fenced = "Here it is:\n```json\n" + json.dumps(reply) + "\n```"
    style, _ = js.import_model_reply(fenced, PNAS, "PNAS", "final")
    assert style["journal"] == "PNAS" and style["stage"] == "final" and style["status"] == "draft"
    assert style["source_text"] == PNAS
    assert {r["origin"] for r in style["rules"]} == {"extracted"}


def test_truncated_or_empty_replies_save_nothing(store):
    for bad in ('{"rules": [{"kind": "width"', "no json here", ""):
        with pytest.raises(js.StyleError):
            js.import_model_reply(bad, PNAS, "PNAS", "final")
    assert not store.exists()


def test_three_column_journals_map_like_the_builtin_science_preset():
    text = ("The width of figures, when printed, will usually be 5.7 cm (2.24 inches or 1 column) "
            "or 12.1 cm (4.76 inches or 2 columns), or 18.4 cm (7.24 inches or 3 columns).")
    q = text
    reply = {"rules": [
        {"kind": "width", "label": label, "relation": "recommended", "value": v, "unit": "mm",
         "applies_to": "printed figures", "evidence_quote": q}
        for label, v in (("1 column", 57), ("2 columns", 121), ("3 columns", 184))]}
    style, _ = js.import_model_reply(json.dumps(reply), text, "Science test", "final")
    assert js.columns_mm(style) == {"single": 57, "double": 121, "triple": 184}
    assert js.width_mm(style, "2 columns")[0] == 121
    assert js.width_mm(style, "triple")[0] == 184
    assert js.width_mm(style, "3")[0] == 184


def test_numbers_codex_met_on_real_pages():
    # Cell's page (2026-10-19 Codex trial): thousands and "w x h" sizes
    assert js.supported_numbers("for line-art figures, at least 1,000 dpi", "dpi") == [1000]
    assert js.supported_numbers("6.5 x 8 in (16.5 x 20 cm)", "mm") == \
        pytest.approx([165.1, 203.2, 165, 200])


def test_two_layouts_on_one_page_and_sizes_that_are_not_columns():
    two = "two-column formats (such as research articles and reviews)"
    three = "three-column formats (such as previews and commentaries)"
    text = ("Two-column formats: 8.5 cm (1 column), 11.4 cm (1.5 columns), and 17.4 cm (full width). "
            "Three-column formats: 5.5 cm (1 column), 11.4 cm (2 columns), and 17.4 cm (full width). "
            "Medium: approximately 11 cm x 11 cm")
    rule = lambda label, v, scope, q: {"kind": "width", "label": label, "relation": "max",
                                       "value": v, "unit": "mm", "applies_to": scope,
                                       "evidence_quote": q}
    reply = {"rules": [rule("1 column", 85, two, "8.5 cm (1 column)"),
                       rule("1.5 columns", 114, two, "11.4 cm (1.5 columns)"),
                       rule("full width of the page", 174, two, "17.4 cm (full width)"),
                       rule("1 column", 55, three, "5.5 cm (1 column)"),
                       rule("2 columns", 114, three, "11.4 cm (2 columns)"),
                       rule("full width of the page", 174, three, "17.4 cm (full width)")]}
    style, _ = js.import_model_reply(json.dumps(reply), text, "Cell test", "final")
    assert js.columns_mm(style) == {"single": 85, "1.5": 114, "double": 174}   # first layout
    medium = {"rules": [dict(rule("Medium approximate figure dimensions", 110,
                                  "approximate figure size, not a column", "approximately 11 cm x 11 cm"),
                             relation="recommended")]}
    style, _ = js.import_model_reply(json.dumps(medium), text, "Size test", "final")
    assert js.columns_mm(style) == {}                  # a figure size is not a column


def test_journal_info_says_what_is_available_or_how_to_import():
    sci = js.journal_info("Science")
    assert sci["status"] == "built_in" and sci["columns_mm"]["triple"] == 184
    assert "science.org" in sci["source"]["url"]
    missing = js.journal_info("Natur Physics")
    assert missing["status"] == "not_available" and "paste" in missing["how_to_add"][0]
    assert js.journal_info("pnaas")["did_you_mean"] == ["pnas"]
    style, _ = _pnas_style("Journal of Fly Figures")
    js.save(style)
    got = js.journal_info("journal of fly figures")
    assert got["status"] == "saved_style" and got["columns_mm"]["1.5"] == 114
    import pyfigures.mcp_server as M
    assert json.loads(M.journal_info("cell"))["columns_mm"] == {"single": 85, "1.5": 114,
                                                                 "double": 174}


def test_manual_rules_need_no_quote_but_must_be_sane():
    style, _ = js.validate({"journal": "Lab Journal", "stage": "final", "rules": [
        {"kind": "width", "label": "single column", "relation": "max", "value": 80, "unit": "mm",
         "applies_to": "all", "origin": "manual"}]})
    assert js.columns_mm(style) == {"single": 80}
    with pytest.raises(js.StyleError, match="positive"):
        js.validate({"journal": "J", "rules": [{"kind": "width", "label": "w", "relation": "max",
                                                "value": -1, "unit": "mm", "applies_to": "a",
                                                "origin": "manual"}]})


def test_reviewed_styles_cannot_keep_conflicts():
    rule = {"kind": "width", "label": "single column", "relation": "max", "unit": "mm",
            "applies_to": "all", "origin": "manual"}
    data = {"journal": "J", "stage": "final", "status": "reviewed",
            "rules": [dict(rule, value=80), dict(rule, value=85)]}
    with pytest.raises(js.StyleError, match="conflicting"):
        js.validate(data)
    data["status"] = "draft"
    assert any(w.startswith("conflicting") for w in js.validate(data)[1])


# ---------------------------------------------------------------- store

def test_saves_are_versioned_and_drafts_from_models(store):
    style, _ = _pnas_style()
    style["status"] = "reviewed"
    r1 = js.save(style)                                   # MCP / CLI path: forced draft
    assert r1["version"] == 1 and r1["status"] == "draft" and r1["use_as"] == "custom:PNAS"
    r2 = js.save(style, allow_reviewed=True)              # the editor, ticked by a person
    assert r2["version"] == 2 and r2["status"] == "reviewed"
    assert os.path.exists(r1["path"]) and os.path.exists(r2["path"])
    rows = js.list_styles()
    assert len(rows) == 1 and rows[0]["version"] == 2 and rows[0]["status"] == "reviewed"
    assert js.find_style("custom:PNAS")["status"] == "reviewed"


def test_a_saved_style_is_used_by_resize_check_and_recipes(tmp_path):
    import pyfigures.mcp_server as M
    from pyfigures.mcp_tools.core import _width_mm_for_journal
    from PIL import Image
    style, _ = _pnas_style()
    js.save(style)
    unfamiliar, _ = _pnas_style("Journal of Fly Figures")
    js.save(unfamiliar)
    assert _width_mm_for_journal("pnas", "1.5") == 114                  # built-in untouched
    assert _width_mm_for_journal("custom:PNAS", "1.5") == 114           # the style
    assert _width_mm_for_journal("Journal of Fly Figures", "double") == 178
    assert _width_mm_for_journal("journal of fly figures", "2 columns") == 178   # own label
    with pytest.raises(ValueError, match="no 'triple'"):
        _width_mm_for_journal("Journal of Fly Figures", "triple")
    with pytest.raises(ValueError, match="saved journal styles: .*Journal of Fly Figures"):
        _width_mm_for_journal("Unknown Journal", "single")

    img = str(tmp_path / "a.png")
    Image.fromarray((np.random.default_rng(0).random((64, 64)) * 255).astype(np.uint8)).save(img)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, mode="groups", num_groups=1)
    M.add_image(pyf, [0], img)
    assert "ERROR" not in M.resize_figure(pyf, journal="Journal of Fly Figures", column="1.5")
    report = M.check_journal_compliance(pyf, journal="Journal of Fly Figures", column="1.5")
    assert "114mm" in report and "vs min 6pt" in report
    assert "Journal style 'Journal of Fly Figures' (draft" in report
    assert "colour mode: allowed RGB" in report and "not yet reviewed" in report
    assert "Journal style" not in M.check_journal_compliance(pyf, journal="pnas", column="1.5")

    recipe = tmp_path / "r.yaml"
    recipe.write_text(f"output: {tmp_path / 'r.pyf'}\njournal: Journal of Fly Figures\n"
                      f"column: double\nrows:\n  - - image: {img}\n", encoding="utf-8")
    res = M.build_figure_from_recipe(str(recipe))
    assert "ERROR" not in res, res
    listed = json.loads(M.list_journal_presets())["saved_journal_styles"]
    assert {s["use_as"] for s in listed} == {"custom:PNAS", "Journal of Fly Figures"}


# ---------------------------------------------------------------- MCP

def test_mcp_prepare_then_save(store):
    import pyfigures.mcp_server as M
    prep = json.loads(M.prepare_journal_style_import(PNAS, "PNAS", "final"))
    assert "evidence_quote" in json.dumps(prep["schema"]) and "untrusted" in prep["instructions"]
    out = json.loads(M.save_journal_style(json.dumps(PNAS_REPLY), PNAS, "PNAS", "final"))
    assert out["status"] == "draft" and out["columns_mm"]["1.5"] == 114
    bad = dict(PNAS_REPLY, rules=[dict(PNAS_REPLY["rules"][0], value=89)])
    assert M.save_journal_style(json.dumps(bad), PNAS, "PNAS", "final").startswith("ERROR")
    assert json.loads(M.list_journal_styles())[0]["use_as"] == "custom:PNAS"
    got = json.loads(M.get_journal_style("custom:PNAS"))
    assert got["columns_mm"]["double"] == 178 and "characters" in got["source_text"]
    assert M.prepare_journal_style_import("", "X").startswith("ERROR")


class _FakeModel(BaseHTTPRequestHandler):
    reply = None
    finish_reason = "stop"
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeModel.seen.append(body)
        out = {"choices": [{"finish_reason": _FakeModel.finish_reason,
                            "message": {"content": json.dumps(_FakeModel.reply)}}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_model():
    server = HTTPServer(("127.0.0.1", 0), _FakeModel)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    _FakeModel.reply = PNAS_REPLY
    _FakeModel.finish_reason = "stop"
    _FakeModel.seen = []
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()


def test_local_endpoint_extraction(fake_model):
    style, _ = js.extract_with_endpoint(PNAS, "PNAS", "some-model", "final", base_url=fake_model)
    assert js.columns_mm(style)["single"] == 87
    sent = _FakeModel.seen[-1]
    assert sent["model"] == "some-model" and sent["temperature"] == 0
    assert sent["response_format"]["type"] == "json_schema"
    _FakeModel.finish_reason = "length"
    with pytest.raises(js.StyleError, match="cut"):
        js.extract_with_endpoint(PNAS, "PNAS", "some-model", "final", base_url=fake_model)


# ---------------------------------------------------------------- GUI

def test_editor_import_edit_review_save_and_use_in_the_journal_dialog(qapp, store):
    from pyfigures.gui.journal_style_editor import JournalStyleEditor
    from pyfigures.gui.pfgui import _JournalDialog
    ed = JournalStyleEditor()
    ed.journal.setText("Journal of Fly Figures")
    ed.stage.setCurrentText("final")
    ed.source.setPlainText(PNAS)
    assert ed.import_reply(json.dumps(PNAS_REPLY))
    assert ed.table.rowCount() == 8 and "columns found: single 87 mm" in ed.status.text()
    # a person corrects a value: the rule becomes theirs ("manual")
    ed.table.item(0, 3).setText("85")
    assert ed.table.item(0, 8).text() == "manual"
    ed.add_manual_rule()
    row = ed.table.rowCount() - 1
    for col, text in ((1, "3 columns"), (3, "190"), (2, "max")):
        ed.table.item(row, col).setText(text)
    ed.reviewed.setChecked(True)
    res = ed.save_version()
    assert res and res["status"] == "reviewed" and res["version"] == 1
    assert ed.saved_combo.count() == 1

    dlg = _JournalDialog()
    assert "Journal of Fly Figures" in dlg._JOURNALS and "nature" in dlg._JOURNALS
    dlg.journal_combo.setCurrentText("Journal of Fly Figures")
    cols = [dlg.column_combo.itemData(i) for i in range(dlg.column_combo.count())]
    texts = [dlg.column_combo.itemText(i) for i in range(dlg.column_combo.count())]
    # the added "3 columns" rule is another layout than the page's 1 / 1.5 / 2
    # columns: offered under its own label
    assert cols == ["single", "1.5", "double", "3 columns"]
    assert texts[0] == "single — 85 mm" and texts[3] == "3 columns — 190 mm"
    dlg.column_combo.setCurrentIndex(3)
    assert dlg.values()["column"] == "3 columns"
    dlg.journal_combo.setCurrentText("science")             # a built-in: only its own sizes
    assert [dlg.column_combo.itemData(i) for i in range(dlg.column_combo.count())] == \
        ["single", "double", "triple"]
    assert "3 columns" in dlg.style_label.text()
    dlg.journal_combo.setCurrentText("Journal of Fly Figures")
    assert dlg.min_dpi_edit.text() == "300" and dlg.min_font_edit.text() == "6"
    assert "reviewed" in dlg.style_label.text()
    from pyfigures.mcp_tools.core import _width_mm_for_journal
    assert _width_mm_for_journal("Journal of Fly Figures", "single") == 85
    assert _width_mm_for_journal("Journal of Fly Figures", "3 columns") == 190


def test_editor_refuses_a_bad_reply_without_changing_the_table(qapp):
    from pyfigures.gui.journal_style_editor import JournalStyleEditor
    ed = JournalStyleEditor()
    ed.journal.setText("PNAS")
    ed.source.setPlainText(PNAS)
    bad = dict(PNAS_REPLY, rules=[dict(PNAS_REPLY["rules"][0], value=99)])
    assert not ed.import_reply(json.dumps(bad))
    assert ed.table.rowCount() == 0 and "refused" in ed.status.text()


def test_editor_extracts_off_the_gui_thread(qapp, fake_model):
    from qtpy.QtTest import QTest
    from pyfigures.gui.journal_style_editor import JournalStyleEditor
    ed = JournalStyleEditor()
    ed.journal.setText("PNAS")
    ed.source.setPlainText(PNAS)
    ed.base_url.setText(fake_model)
    ed.model.setText("some-model")
    ed.start_extract()
    assert not ed.extract_button.isEnabled()
    for _ in range(100):
        QTest.qWait(50)
        if ed.table.rowCount():
            break
    QTest.qWait(100)
    assert ed.table.rowCount() == 8 and ed.extract_button.isEnabled()


def test_qc_menu_opens_the_editor(qapp, monkeypatch):
    from pyfigures.gui.pfgui import EZFIG_GUI
    from pyfigures.gui import journal_style_editor as E
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(E.JournalStyleEditor, "exec_", lambda self: 0, raising=False)
    monkeypatch.setattr(E.JournalStyleEditor, "exec", lambda self: 0)
    w = EZFIG_GUI()
    try:
        from pyfigures.gui.show_me_how import find_action
        qc = find_action(w.menuBar, "QC").menu()
        act = find_action(qc, "Journal styles (from a journal's guidelines)…")
        dialogs = []
        monkeypatch.setattr(E.JournalStyleEditor, "exec", lambda self: dialogs.append(self) or 0)
        monkeypatch.setattr(E.JournalStyleEditor, "exec_", lambda self: dialogs.append(self) or 0,
                            raising=False)
        act.trigger()
        assert dialogs and isinstance(dialogs[0], E.JournalStyleEditor)
    finally:
        w._dirty = False
        w.hide()
