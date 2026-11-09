"""Message boxes that show a shell command (pip install …) the user can
select and copy: the text is selectable and a "Copy the command" button puts
the command on the clipboard without closing the box."""
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMessageBox

COPY_LABEL = 'Copy the command'


def command_box(parent, title, text, command, warning=False):
    """The (not yet shown) QMessageBox: *text* is selectable, its Copy button
    copies *command* and stays open; OK closes."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    copy = box.addButton(COPY_LABEL, QMessageBox.ButtonRole.ActionRole)
    copy.setToolTip(command)
    # QMessageBox closes on any button: drop its own connection, copy instead
    copy.clicked.disconnect()

    def copied(_checked=False):
        QApplication.clipboard().setText(command)
        copy.setText('Copied')
    copy.clicked.connect(copied)
    box.addButton(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(QMessageBox.StandardButton.Ok)
    return box


def show_command(parent, title, text, command, warning=False):
    """Show the box modally; returns it once closed."""
    box = command_box(parent, title, text, command, warning)
    box.exec()
    return box
