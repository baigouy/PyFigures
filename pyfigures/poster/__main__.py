"""Standalone launcher: `python -m pyfigures.poster` opens the poster/collage
designer directly — the same PosterWindow reached from the main scientific-
figure editor's `Tools > Poster / collage designer…` menu (see poster_window.py's
docstring), just without going through pfgui.py first.
"""
from batoolset.settings.global_settings import set_UI
set_UI()

import sys

from qtpy.QtWidgets import QApplication


def run_poster_designer(album=False):
    app = QApplication(sys.argv)

    # Same Qt-safe global exception hook the main editor installs: without
    # it, an unhandled exception in a slot/timer/event aborts the whole
    # process (0xC0000409) instead of just logging and carrying on.
    from batoolset.GUI.exception_handler import install_global_exception_handler
    install_global_exception_handler()

    try:
        from pyfigures.gui.portable_fonts import register_portable_fonts
        register_portable_fonts(app)
    except Exception:
        pass

    from pyfigures.gui.theme import apply_theme, load_saved_theme
    apply_theme(load_saved_theme())

    from pyfigures.poster.poster_window import PosterWindow
    win = PosterWindow(album=album)
    win.show()
    win.raise_()
    win.activateWindow()

    exit_code = app.exec_() if hasattr(app, 'exec_') else app.exec()
    sys.exit(exit_code)


if __name__ == '__main__':
    run_poster_designer()
