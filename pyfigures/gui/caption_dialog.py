"""File → Figure caption / legend…: the caption with formatting (bold,
italic for species names, super/subscripts, Greek letters) in the same
rich-text editor as the poster texts — it was a plain text box.

The plain text stays the caption every tool reads (MCP server, checks,
alt text); the formatted version is kept beside it as Markdown
(export_caption fmt='md' writes it).
"""
from __future__ import annotations

from qtpy.QtGui import QTextDocument
from qtpy.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                            QVBoxLayout)

from pyfigures.gui.simple_text_editor import TextEditor


class CaptionDialog(QDialog):
    def __init__(self, parent=None, title="", caption="", caption_markdown=None, statistics=None,
                 stored_statistics=None):
        """*statistics*: a callable giving the Statistics paragraph of the figure's
        plots (Insert statistics); *stored_statistics*: the one inserted last."""
        super().__init__(parent)
        self._statistics = statistics
        self.stored_statistics = stored_statistics
        self.setWindowTitle("Figure caption / legend")
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Title:"))
        self.title_edit = QLineEdit(title or "")
        self.title_edit.setPlaceholderText('optional, e.g. "Figure 1"')
        row.addWidget(self.title_edit)
        layout.addLayout(row)
        self.doc = QTextDocument(self)
        if caption_markdown:
            self.doc.setMarkdown(caption_markdown)
        else:
            self.doc.setPlainText(caption or "")
        self.editor = TextEditor(associated_text=self.doc, show_position=False, show_range=False,
                                 show_text_orientation=False)
        self.editor.textEdit.setPlaceholderText("Caption: what each panel shows, the scale bars, "
                                                "n and the statistical test…")
        # a caption is a paragraph: it wraps (labels on the figure do not)
        self.editor.textEdit.setLineWrapMode(self.editor.textEdit.LineWrapMode.WidgetWidth)
        layout.addWidget(self.editor, 1)
        if statistics is not None:
            # the tests of the data plots, for the legend (user, 2026-11-19: not
            # printed under the plots); edited by hand, it is never rewritten
            row2 = QHBoxLayout()
            self.stats_button = QPushButton("Insert statistics")
            self.stats_button.setToolTip("Add (or update) a Statistics paragraph: each data plot's test, "
                                         "result and n, and what the stars mean. You can edit it.")
            self.stats_button.clicked.connect(self.insert_statistics)
            self.stats_note = QLabel("")
            self.stats_note.setWordWrap(True)
            row2.addWidget(self.stats_button)
            row2.addWidget(self.stats_note, 1)
            layout.addLayout(row2)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(640, 420)

    def insert_statistics(self):
        """Statistics paragraph added at the end, or the one inserted before replaced
        while it is unchanged; an edited one is left alone (said beside the button)."""
        from pyfigures.stats_legend import merged_caption
        try:
            fresh = self._statistics()
        except Exception as e:
            self.stats_note.setText(f"Could not compute the statistics: {e}")
            return
        if not fresh:
            self.stats_note.setText("No tested data plot in this figure.")
            return
        text, status = merged_caption(self.doc.toPlainText(), self.stored_statistics, fresh)
        if status == "edited":
            self.stats_note.setText("The Statistics paragraph was edited by hand: not replaced. "
                                    "Press again to add the current one at the end.")
            self.stored_statistics = None          # the next press adds it
            return
        # edited in place, so the formatting of the rest of the caption is kept
        if status == "added":
            from qtpy.QtGui import QTextCursor
            cursor = QTextCursor(self.doc)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(("\n\n" if self.doc.toPlainText().strip() else "") + fresh)
        elif status == "updated":
            cursor = self.doc.find(self.stored_statistics)
            if cursor.isNull():
                self.doc.setPlainText(text)
            else:
                cursor.insertText(fresh)
        self.stored_statistics = fresh
        self.stats_note.setText({"added": "Statistics added.", "updated": "Statistics updated.",
                                 "unchanged": "The statistics are up to date."}[status])

    def values(self) -> dict:
        """title, caption (plain) and caption_markdown (the formatting)."""
        plain = self.doc.toPlainText().strip()
        md = self.doc.toMarkdown().strip() if plain else None
        return {"title": self.title_edit.text().strip(), "caption": plain,
                "caption_markdown": md if md and md != plain else None,
                "statistics": self.stored_statistics}
