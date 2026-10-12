"""Modal editor for a PosterText's rich-text content.

Reuses pyfigures.gui.simple_text_editor.TextEditor — the same rich-text
toolbar (bold/italic/underline/font/colors/Greek letters) the main
scientific-figure editor uses for its own text annotations — rather than
building a second one from scratch. TextEditor is handed the PosterText's
own QTextDocument directly (not a TAText2D), so typing in it mutates that
document in place; no separate sync step is needed. Standalone dialog: talks
to the poster module only via the PosterText instance passed in, same
isolation as every other poster_* file (see poster_canvas.py's docstring).
"""
from batoolset.settings.global_settings import set_UI
set_UI()

from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox, QLabel, QComboBox
)

from pyfigures.gui.simple_text_editor import TextEditor
from pyfigures.poster.poster_shapes import TEXT_STYLE_PRESETS, TEXT_STYLE_ORDER


class PosterTextDialog(QDialog):
    def __init__(self, poster_text, parent=None, on_change=None, page_height_mm=297.0):
        super().__init__(parent)
        self.setWindowTitle('Edit text')
        self.poster_text = poster_text
        self.page_height_mm = page_height_mm
        self.on_change = on_change
        layout = QVBoxLayout(self)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel('Size preset:'))
        self.style_combo = QComboBox()
        for key in TEXT_STYLE_ORDER:
            self.style_combo.addItem(TEXT_STYLE_PRESETS[key]['label'], key)
        # Reflect the size actually applied right now (set when this box was
        # created/last leveled — see PosterText.style) rather than a neutral
        # placeholder, so opening the dialog right after picking "Heading 1"
        # shows "Heading 1" selected, not an unrelated "nothing chosen" entry.
        current_index = self.style_combo.findData(getattr(poster_text, 'style', None))
        self.style_combo.setCurrentIndex(current_index if current_index != -1 else
                                         self.style_combo.findData('body'))
        self.style_combo.currentIndexChanged.connect(self._apply_style_preset)
        style_row.addWidget(self.style_combo)
        style_row.addStretch()
        layout.addLayout(style_row)

        self.editor = TextEditor(associated_text=poster_text.doc, show_position=False,
                                 show_range=False, show_text_orientation=False, select_all=True)
        layout.addWidget(self.editor)

        if on_change is not None:
            # Live preview on the poster canvas while the dialog is open —
            # the box itself re-fits to the new text only once (on close),
            # see PosterCanvas.edit_text.
            self.editor.textEdit.textChanged.connect(on_change)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.resize(560, 400)

    def _apply_style_preset(self, index):
        """Jump the box straight to a heading level's target size (a
        fraction of the page height — see TEXT_STYLE_PRESETS), the same
        move as re-adding the text box at a different level, without
        losing the words already typed. Every selection reapplies its size
        (there is no neutral "do nothing" entry) — this only fires on an
        actual combo change, so opening/closing the dialog without touching
        it never overwrites a manually corner-resized box."""
        key = self.style_combo.itemData(index)
        preset = TEXT_STYLE_PRESETS[key]
        self.poster_text.height_mm = self.page_height_mm * preset['height_frac']
        self.poster_text.refit_box()
        self.poster_text.style = key
        if self.on_change is not None:
            self.on_change()
