"""User, 2026-11-20 (screenshot): on the empty canvas the red arrow to the chat was not
centred on the robot button (it was drawn at a fixed x), and its text was far below it.
The arrow is now on the button's centre."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_the_chat_arrow_points_at_the_robot(qapp, monkeypatch):
    from qtpy.QtCore import QPoint
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    monkeypatch.setattr(EZFIG_GUI, "show_tips", lambda self: None)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    win = EZFIG_GUI()
    try:
        win.resize(900, 600)
        win.show()
        qapp.processEvents()
        canvas = win.paint.EZFIG_panel
        canvas._compute_help_arrow_x()
        button = win.mainToolBar.widgetForAction(win.chat_toolbar_action)
        centre = canvas.mapFromGlobal(button.mapToGlobal(QPoint(button.width() // 2, 0))).x()
        assert canvas._chat_arrow_x is not None
        assert abs(canvas._chat_arrow_x - centre) <= 1
        canvas.grab()                          # the hint paints with it
    finally:
        win.close()
        win.deleteLater()
