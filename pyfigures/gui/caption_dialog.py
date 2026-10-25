"""File → Figure caption / legend…: the caption with formatting (bold,
italic for species names, super/subscripts, Greek letters) in the same
rich-text editor as the poster texts — it was a plain text box.

The plain text stays the caption every tool reads (MCP server, checks,
alt text); the formatted version is kept beside it as Markdown
(export_caption fmt='md' writes it).
"""
from __future__ import annotations

from qtpy.QtGui import QTextDocument
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout

from pyfigures.gui.simple_text_editor import TextEditor


class CaptionDialog(QDialog):
    def __init__(self, parent=None, title="", caption="", caption_markdown=None):
        super().__init__(parent)
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
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(640, 420)

    def values(self) -> dict:
        """title, caption (plain) and caption_markdown (the formatting)."""
        plain = self.doc.toPlainText().strip()
        md = self.doc.toMarkdown().strip() if plain else None
        return {"title": self.title_edit.text().strip(), "caption": plain,
                "caption_markdown": md if md and md != plain else None}
