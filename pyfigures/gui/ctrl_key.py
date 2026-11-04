"""The 'Ctrl' key of shortcuts and Ctrl-click.

Qt already maps "Ctrl" / ControlModifier to the Command key on macOS ("Meta" is
the physical Control key there). batoolset-gui <= 0.2.1 returned Meta on macOS:
every shortcut was Control+key and Cmd-click did not add to a selection.
"""
from qtpy.QtCore import Qt


def getCtrlModifierAsString():
    """'Ctrl' in a QKeySequence: Ctrl on Windows/Linux, Command on macOS."""
    return "Ctrl"


def getCtrlModifier():
    """ControlModifier: Ctrl on Windows/Linux, Command on macOS."""
    return Qt.KeyboardModifier.ControlModifier
