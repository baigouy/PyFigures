"""Install dialogs: the pip command can be selected and copied with a button
that does not close the box."""
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QApplication, QMessageBox

from pyfigures.gui.command_box import COPY_LABEL, command_box


def test_copy_button_copies_and_keeps_the_box_open(qapp):
    box = command_box(None, 'Chat sidebar', 'Reinstall it with pip install -U x', 'pip install -U x')
    assert box.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    seen = []

    def click():
        copy = [b for b in box.buttons() if b.text() == COPY_LABEL][0]
        copy.click()
        seen.append((box.isVisible(), QApplication.clipboard().text(), copy.text()))
        box.button(QMessageBox.StandardButton.Ok).click()
    QTimer.singleShot(100, click)
    box.exec()
    assert seen == [(True, 'pip install -U x', 'Copied')]
    assert not box.isVisible()
