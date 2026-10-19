"""QC → Journal styles…: make a journal style from a journal's own figure
guidelines, review and correct it, save new versions (pyfigures/journal_styles.py).

Paste the guidelines, then either let a local model extract the rules
(LM Studio or any OpenAI-compatible server with a model already loaded; the
request runs off the GUI thread), or copy the prompt into any chat model and
paste its JSON reply. Extracted rules show their source quote; editing a
rule's value, unit or range turns it into a ``manual`` rule (your entry, not
evidence). Tick "I reviewed…" to save a reviewed style; otherwise it is saved
as a draft. Every save is a new version.
"""
from __future__ import annotations

import json

from qtpy.QtCore import QThread, Signal
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout,
                            QHeaderView, QInputDialog, QLabel, QLineEdit, QPlainTextEdit,
                            QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from pyfigures import journal_styles as js

COLUMNS = ["Kind", "Label", "Relation", "Value", "Maximum", "Unit", "Applies to", "Source quote",
           "Origin"]
_KEYS = ["kind", "label", "relation", "value", "maximum", "unit", "applies_to", "evidence_quote",
         "origin"]
_MANUAL_ON_EDIT = {3, 4, 5}          # value, maximum, unit: an edit makes the rule manual
_ORPHANS = []                        # extractions still running after their dialog closed


class _Extraction(QThread):
    done = Signal(object, object)            # (style, warnings)
    failed = Signal(str)

    def __init__(self, kwargs, parent=None):
        super().__init__(parent)
        self.kwargs = kwargs

    def run(self):
        try:
            style, warnings = js.extract_with_endpoint(**self.kwargs)
            self.done.emit(style, warnings)
        except Exception as e:      # noqa: BLE001 - reported in the dialog, never raised in Qt
            self.failed.emit(str(e))


class JournalStyleEditor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Journal styles — from a journal's figure guidelines")
        self.resize(1200, 860)
        self.worker = None
        self._filling = False
        lay = QVBoxLayout(self)
        intro = QLabel("Paste the figure-guidelines part of the journal's web page. A model "
                       "extracts the rules (each must quote the text), you check and correct "
                       "them, then save. Built-in journal presets are never changed; a saved "
                       "style is usable wherever a journal is chosen.")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        top = QHBoxLayout()
        top.addWidget(QLabel("Saved styles:"))
        self.saved_combo = QComboBox(self)
        top.addWidget(self.saved_combo, 1)
        load = QPushButton("Load", self)
        load.clicked.connect(self.load_selected)
        top.addWidget(load)
        new = QPushButton("New", self)
        new.clicked.connect(self.new_style)
        top.addWidget(new)
        lay.addLayout(top)

        form = QFormLayout()
        self.journal = QLineEdit(self)
        self.journal.setPlaceholderText("Journal title (one journal, not a publisher)")
        self.stage = QComboBox(self)
        self.stage.addItems(list(js.STAGES))
        self.stage.setCurrentText("final")
        self.article = QLineEdit("unspecified", self)
        self.url = QLineEdit(self)
        self.url.setPlaceholderText("Where the text comes from (kept as provenance)")
        form.addRow("Journal", self.journal)
        form.addRow("Submission stage", self.stage)
        form.addRow("Article / layout scope", self.article)
        form.addRow("Source URL", self.url)
        lay.addLayout(form)

        self.source = QPlainTextEdit(self)
        self.source.setPlaceholderText("Paste the guidelines: widths, heights, resolution, fonts, "
                                       "file formats…")
        self.source.setMaximumHeight(170)
        lay.addWidget(self.source)

        row = QHBoxLayout()
        row.addWidget(QLabel("Local model server:"))
        self.base_url = QLineEdit("http://127.0.0.1:1234/v1", self)
        row.addWidget(self.base_url)
        self.model = QLineEdit(self)
        self.model.setPlaceholderText("id of a model already loaded (e.g. in LM Studio)")
        row.addWidget(self.model)
        self.extract_button = QPushButton("Extract with this model", self)
        self.extract_button.clicked.connect(self.start_extract)
        row.addWidget(self.extract_button)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        copy = QPushButton("Copy the prompt for another chat model", self)
        copy.clicked.connect(self.copy_prompt)
        row2.addWidget(copy)
        paste = QPushButton("Paste the model's JSON reply…", self)
        paste.clicked.connect(self.paste_reply)
        row2.addWidget(paste)
        row2.addStretch(1)
        lay.addLayout(row2)

        self.table = QTableWidget(0, len(COLUMNS), self)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, w in ((1, 160), (6, 200), (7, 300)):
            self.table.setColumnWidth(col, w)
        self.table.itemChanged.connect(self._item_changed)
        lay.addWidget(self.table, 1)
        hint = QLabel("Kinds: " + ", ".join(js.KINDS) + ". Relations: " + ", ".join(js.RELATIONS)
                      + ". Units: mm, dpi, pt, text. Width labels such as 'single column', "
                      "'1.5 columns', 'double column' become the columns you can choose.")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        buttons = QHBoxLayout()
        for title, slot in (("Add a rule by hand", self.add_manual_rule),
                            ("Remove selected rule(s)", self.remove_rules),
                            ("Check", self.check),
                            ("Save as a new version", self.save_version)):
            b = QPushButton(title, self)
            b.clicked.connect(slot)
            buttons.addWidget(b)
        close = QPushButton("Close", self)
        close.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        self.reviewed = QCheckBox("I checked these values against the journal's page (saves a "
                                  "reviewed style)", self)
        lay.addWidget(self.reviewed)
        self.notes = QPlainTextEdit(self)
        self.notes.setPlaceholderText("Notes / uncertainties (one per line)")
        self.notes.setMaximumHeight(60)
        lay.addWidget(self.notes)
        self.status = QLabel("New draft — nothing saved", self)
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        self.refresh_saved()

    # ---- saved styles ------------------------------------------------------
    def refresh_saved(self):
        self.saved_combo.clear()
        self._saved = js.list_styles()
        for s in self._saved:
            self.saved_combo.addItem(f"{s['use_as']} — {s['stage']}, {s['status']}, v{s['version']}")

    def load_selected(self):
        i = self.saved_combo.currentIndex()
        if i < 0 or i >= len(self._saved):
            return
        try:
            with open(self._saved[i]["path"], encoding="utf-8") as f:
                self.set_style(json.load(f)["style"])
            self.status.setText(f"Loaded {self._saved[i]['path']}")
        except (OSError, ValueError, KeyError) as e:
            self.status.setText(f"Could not load: {e}")

    def new_style(self):
        for w in (self.journal, self.url, self.source, self.notes):
            w.clear()
        self.article.setText("unspecified")
        self.stage.setCurrentText("final")
        self.table.setRowCount(0)
        self.reviewed.setChecked(False)
        self.status.setText("New draft — nothing saved")

    # ---- table -------------------------------------------------------------
    def add_rule_row(self, rule):
        self._filling = True
        try:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, key in enumerate(_KEYS):
                v = rule.get(key, "")
                if isinstance(v, float):
                    v = f"{v:g}"
                self.table.setItem(row, col, QTableWidgetItem("" if v is None else str(v)))
        finally:
            self._filling = False

    def add_manual_rule(self):
        self.add_rule_row({"kind": "width", "label": "single column", "relation": "target",
                           "value": "", "unit": "mm", "applies_to": "all figures",
                           "evidence_quote": "", "origin": "manual"})

    def remove_rules(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    def _item_changed(self, item):
        if self._filling or item.column() not in _MANUAL_ON_EDIT:
            return
        origin = self.table.item(item.row(), 8)
        if origin is not None and origin.text() != "manual":
            self._filling = True
            origin.setText("manual")          # your value, no longer the quoted evidence
            self._filling = False

    # ---- data --------------------------------------------------------------
    def data(self) -> dict:
        rules = []
        for row in range(self.table.rowCount()):
            vals = [(self.table.item(row, c).text().strip() if self.table.item(row, c) else "")
                    for c in range(len(COLUMNS))]
            r = dict(zip(_KEYS, vals))
            r["maximum"] = r["maximum"] or None
            r["origin"] = r["origin"] or "manual"
            rules.append(r)
        return {"journal": self.journal.text().strip(), "stage": self.stage.currentText(),
                "article_type": self.article.text().strip() or "unspecified",
                "source_url": self.url.text().strip(), "source_text": self.source.toPlainText(),
                "rules": rules,
                "notes": [n for n in self.notes.toPlainText().splitlines() if n.strip()],
                "status": "reviewed" if self.reviewed.isChecked() else "draft"}

    def set_style(self, style, warnings=()):
        self.journal.setText(style["journal"])
        self.stage.setCurrentText(style["stage"])
        self.article.setText(style["article_type"])
        self.url.setText(style["source_url"])
        self.source.setPlainText(style["source_text"])
        self.notes.setPlainText("\n".join(style.get("notes") or []))
        self.reviewed.setChecked(style.get("status") == "reviewed")
        self.table.setRowCount(0)
        for r in style["rules"]:
            self.add_rule_row(r)
        cols = js.columns_mm(style)
        self.status.setText(f"{len(style['rules'])} rule(s); columns found: "
                            + (", ".join(f"{k} {v:g} mm" for k, v in cols.items()) or "none")
                            + (". " + "; ".join(warnings) if warnings else "")
                            + ". Check each value against the page before ticking 'I checked'.")

    def check(self):
        try:
            style, warnings = js.validate(self.data())
        except ValueError as e:
            self.status.setText(f"Not valid: {e}")
            return None
        cols = js.columns_mm(style)
        self.status.setText(f"{len(style['rules'])} rule(s) valid; columns: "
                            + (", ".join(f"{k} {v:g} mm" for k, v in cols.items()) or "none")
                            + (". " + "; ".join(warnings) if warnings else "."))
        return style

    def save_version(self):
        try:
            res = js.save(self.data(), allow_reviewed=True)
        except ValueError as e:
            self.status.setText(f"Not saved: {e}")
            return None
        self.status.setText(f"Saved version {res['version']} ({res['status']}) — use it as "
                            f"journal '{res['use_as']}'. {res['path']}"
                            + (". " + "; ".join(res["warnings"]) if res["warnings"] else ""))
        self.refresh_saved()
        return res

    # ---- models ------------------------------------------------------------
    def _inputs(self):
        return dict(text=self.source.toPlainText(), journal=self.journal.text().strip(),
                    stage=self.stage.currentText(), source_url=self.url.text().strip(),
                    article_type=self.article.text().strip() or "unspecified")

    def copy_prompt(self):
        try:
            p = js.extraction_prompt(**self._inputs())
        except ValueError as e:
            self.status.setText(str(e))
            return
        QApplication.clipboard().setText(
            p["system"] + "\n\nAnswer with one JSON object following this schema:\n"
            + json.dumps(p["schema"], indent=1) + "\n\nINPUT:\n"
            + json.dumps(p["input"], ensure_ascii=False, indent=1))
        self.status.setText("Prompt copied: paste it into the chat model, then use "
                            "'Paste the model's JSON reply…'.")

    def paste_reply(self, text=None):
        if not isinstance(text, str):
            text, ok = QInputDialog.getMultiLineText(self, "Model reply", "Paste the JSON reply:")
            if not ok:
                return
        self.import_reply(text)

    def import_reply(self, text):
        if not self.journal.text().strip():
            self.status.setText("Enter the journal title first.")
            return False
        try:
            style, warnings = js.import_model_reply(text, **self._inputs())
        except ValueError as e:
            self.status.setText(f"Reply refused, nothing changed: {e}")
            return False
        self.set_style(style, warnings)
        return True

    def start_extract(self):
        if self.worker is not None and self.worker.isRunning():
            return
        inp = self._inputs()
        if not inp["journal"] or not inp["text"].strip() or not self.model.text().strip():
            self.status.setText("Enter the journal, the pasted guidelines and the id of a model "
                                "already loaded in the server.")
            return
        inp.update(model=self.model.text().strip(), base_url=self.base_url.text().strip())
        self.worker = _Extraction(inp)
        self.worker.done.connect(self._extracted)
        self.worker.failed.connect(lambda msg: self.status.setText(
            f"Extraction failed, nothing changed: {msg}"))
        self.worker.finished.connect(lambda: self.extract_button.setEnabled(True))
        self.extract_button.setEnabled(False)
        self.status.setText("Extracting… (the window stays usable; nothing is saved until you "
                            "click Save)")
        self.worker.start()

    def _extracted(self, style, warnings):
        self.set_style(style, warnings)

    def done(self, result):
        # closing while a model is still answering: forget its answer, let the
        # request end in the background (an HTTP request cannot be interrupted)
        w = self.worker
        if w is not None and w.isRunning():
            for sig in (w.done, w.failed, w.finished):    # no slot on a deleted dialog
                try:
                    sig.disconnect()
                except (TypeError, RuntimeError):
                    pass
            w.setParent(None)
            _ORPHANS.append(w)
            w.finished.connect(lambda w=w: _ORPHANS.remove(w) if w in _ORPHANS else None)
        self.worker = None
        super().done(result)
