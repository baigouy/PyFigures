"""Copy to the clipboard and show it happened (user 2026-11-24: "it's not obvious that the text
is copied as nothing changes when I press the button"): the copied text's widget blinks twice
and the button says "✓ Copied" for a moment. The chat sidebar (qtpy_ai_sidecar) does the same
for its bubbles; this copy serves PyFigures' own windows, also in the no-AI app."""
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication

FLASH_STYLE = 'background:#ffe9a8;'
COPIED_LABEL = '✓ Copied'


def copy_with_feedback(text, button=None, flash=None):
    """Put *text* on the clipboard; *flash* blinks, *button* says Copied. False when refused."""
    try:
        QApplication.clipboard().setText(text)
    except Exception:
        return False
    try:                                  # a slot error would abort the application
        old = flash.styleSheet() if flash is not None else None
    except RuntimeError:                  # deleted meanwhile
        flash = None
    if flash is not None:
        for i, delay in enumerate((0, 160, 320, 480)):
            QTimer.singleShot(delay, lambda on=(i % 2 == 0), w=flash: _set(w, old + FLASH_STYLE if on else old))
    if button is not None:
        if not getattr(button, '_copy_label', None):
            button._copy_label = button.text()
        label = button._copy_label
        button.setText(COPIED_LABEL)

        def restore(b=button):
            try:
                b.setText(label)
                b._copy_label = None
            except RuntimeError:          # deleted meanwhile
                pass
        QTimer.singleShot(1500, restore)
    return True


def _set(widget, style):
    try:
        widget.setStyleSheet(style)
    except RuntimeError:
        pass
