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

from pyfigures.offscreen import ensure_offscreen_fonts
ensure_offscreen_fonts()      # run with QT_QPA_PLATFORM=offscreen: give it the system fonts
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
    # the offscreen platform has no system UI font: use the usual one
    from qtpy.QtGui import QFont
    app.setFont(QFont('Segoe UI' if sys.platform.startswith('win') else 'Helvetica', 9))

    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None          # no tip of the day on top
    win = EZFIG_GUI()
    win.show()
    win.resize(1280, 800)
    # a real figure in the window (an example from the documentation gallery)
    example = os.path.join(os.path.dirname(__file__), 'examples', 'plot', 'figure.pyf')
    if os.path.isfile(example):
        win.reload_state(example, append=False)
        import time
        t0 = time.time()
        while time.time() - t0 < 20 and (getattr(win, '_active_img_loaders', None)
                                         or getattr(win, '_lazy_img_queue', None)):
            app.processEvents()
            time.sleep(0.02)
        win._dirty = False
        panel = win.paint.EZFIG_panel                 # zoomed in to fill the window
        panel.scale = 2.2
        panel.update_size()
        panel.update()
        app.processEvents()

    steps = iter(_build_steps(app, win))

    def tick():
        try:
            next(steps)
            QTimer.singleShot(350, tick)
        except StopIteration:
            print('Done.')
            win._dirty = False
            sys.stdout.flush()
            os._exit(0)          # (closing the window would ask to save)

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
        real_exec = QDialog.exec

        def grab_instead_of_exec(dialog):
            # the dialog would block: show it, save it, close it
            dialog.show()
            dialog.resize(max(dialog.width(), 640), max(dialog.height(), 520))
            app.processEvents()
            save(dialog, 'dialog_shortcuts.png')
            dialog.close()
            return 0

        QDialog.exec = grab_instead_of_exec
        try:
            print('Capturing shortcuts dialog…')
            win.show_shortcuts_dialog()
        finally:
            QDialog.exec = real_exec
        yield
    except Exception as e:
        print(f'  skipped shortcuts dialog: {e}')

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
