"""
Screenshot capture helper for PyFigures documentation.

Usage:
    cd /home/aigouy/mon_prog/Python/pyfigures_pkg
    PYTHONPATH=..:../BAtools_pkg python3 docs/capture_screenshots.py

Saves PNG files to docs/screenshots/.
Bypasses JVM/Fiji initialisation — no image files needed.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'BAtools_pkg'))

from batoolset.settings.global_settings import set_UI
set_UI()

from qtpy.QtWidgets import QApplication
from qtpy.QtCore import QTimer, Qt
from qtpy.QtGui import QScreen

OUT_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
os.makedirs(OUT_DIR, exist_ok=True)


def save(widget, name):
    path = os.path.join(OUT_DIR, name)
    pixmap = widget.grab()
    pixmap.save(path)
    print(f'  saved {path}')


def run():
    app = QApplication(sys.argv)

    from pyfigures.gui.pfgui import EZFIG_GUI
    win = EZFIG_GUI()
    win.show()
    win.resize(1280, 800)

    steps = iter(_build_steps(app, win))

    def tick():
        try:
            next(steps)
            QTimer.singleShot(350, tick)
        except StopIteration:
            print('Done.')
            app.quit()

    QTimer.singleShot(800, tick)
    app.exec_()


def _build_steps(app, win):
    """Generator: each yield is one captured screenshot."""

    app.processEvents()

    # ------------------------------------------------------------------ main window
    yield
    print('Capturing main window…')
    save(win, 'main_window.png')

    # ------------------------------------------------------------------ toolbar
    yield
    print('Capturing toolbar…')
    save(win.mainToolBar, 'toolbar.png')

    # ------------------------------------------------------------------ status bar
    yield
    print('Capturing status bar…')
    save(win.statusBar(), 'status_bar.png')

    # ------------------------------------------------------------------ menus
    menu_bar = win.menuBar
    for action in menu_bar.actions():
        menu = action.menu()
        if menu is None:
            continue
        label = action.text().strip().replace(' ', '_').replace('/', '_').lower()
        menu.popup(win.mapToGlobal(win.rect().topLeft()))
        app.processEvents()
        yield
        print(f'Capturing menu "{action.text()}"…')
        save(menu, f'menu_{label}.png')
        menu.close()
        app.processEvents()
        yield

    # ------------------------------------------------------------------ tip dialog
    try:
        from pyfigures.gui.tipdialog import TipDialog
        tip_dlg = TipDialog(win, win.tips)
        tip_dlg.show()
        app.processEvents()
        yield
        print('Capturing tip dialog…')
        save(tip_dlg, 'dialog_tips.png')
        tip_dlg.close()
        app.processEvents()
        yield
    except Exception as e:
        print(f'  skipped tip dialog: {e}')

    # ------------------------------------------------------------------ shortcuts dialog
    try:
        from qtpy.QtWidgets import QDialog
        # trigger via the menu action
        win.show_shortcuts_dialog.__func__  # just a check it exists
        # Can't call exec_() (blocks), so grab before it opens fully
        # Instead just save the already-open main window as a reminder
    except Exception:
        pass

    # ------------------------------------------------------------------ lettering dialog
    try:
        dlg = win._open_lettering_dialog() if hasattr(win, '_open_lettering_dialog') else None
        if dlg:
            dlg.show()
            app.processEvents()
            yield
            save(dlg, 'dialog_lettering.png')
            dlg.close()
            yield
    except Exception as e:
        print(f'  skipped lettering dialog: {e}')

    # ------------------------------------------------------------------ final full window
    yield
    save(win, 'main_window_final.png')


if __name__ == '__main__':
    run()
