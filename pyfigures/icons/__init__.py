"""The three app icons as window icons: the figure editor ('pyfigures'), the
photo album designer ('pyfigures_album') and the poster designer
('pyfigures_poster'). The PNGs here, and the .ico/.icns used by the
standalone build in images/icons/, are drawn by packaging/make_icons.py.
"""
import os
import sys

ICON_DIR = os.path.dirname(os.path.abspath(__file__))
APP_IDS = {'pyfigures': 'PyFigures', 'pyfigures_album': 'PyFigures Album',
           'pyfigures_poster': 'PyFigures Poster'}


def icon_path(name):
    return os.path.join(ICON_DIR, name + '.png')


def app_icon(name):
    """QIcon for *name* (a key of APP_IDS); an empty QIcon if the file is missing."""
    from qtpy.QtGui import QIcon
    path = icon_path(name)
    return QIcon(path) if os.path.isfile(path) else QIcon()


def set_app_identity(name):
    """Make *name*'s icon the application icon. On Windows, outside the
    standalone app (where the .exe carries its own icon), also give the
    process its own taskbar identity, otherwise the taskbar shows Python's
    icon instead of this one. Call after the QApplication exists."""
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.setWindowIcon(app_icon(name))
    if sys.platform == 'win32' and not getattr(sys, 'frozen', False):
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                'aigouy.' + APP_IDS[name].replace(' ', ''))
        except Exception:
            pass
