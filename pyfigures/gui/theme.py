"""
Centralized theme management for PyFigures.

Provides light, dark, and system-default QPalette-based themes that can be
applied to the entire QApplication and persisted via QSettings.
"""

from batoolset.settings.global_settings import set_UI
set_UI()
from qtpy.QtGui import QColor, QPalette
from qtpy.QtWidgets import QApplication
from pyfigures.gui.user_prefs import load_theme, save_theme

THEMES = ('system', 'light', 'dark')


def detect_system_theme():
    """Return 'dark' or 'light' based on the OS colour scheme."""
    # Qt 6.5+ exposes colorScheme() on QStyleHints
    try:
        from qtpy.QtCore import Qt
        scheme = QApplication.instance().styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return 'dark'
        if scheme == Qt.ColorScheme.Light:
            return 'light'
    except AttributeError:
        pass
    # Fallback: measure luminance of the default window colour
    try:
        c = QApplication.instance().palette().color(QPalette.Window)
        luminance = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        return 'dark' if luminance < 128 else 'light'
    except Exception:
        pass
    return 'light'


def _dark_palette():
    palette = QPalette()
    palette.setColor(QPalette.Window,          QColor(45, 45, 45))
    palette.setColor(QPalette.WindowText,      QColor(220, 220, 220))
    palette.setColor(QPalette.Base,            QColor(30, 30, 30))
    palette.setColor(QPalette.AlternateBase,   QColor(55, 55, 55))
    palette.setColor(QPalette.ToolTipBase,     QColor(40, 40, 40))
    palette.setColor(QPalette.ToolTipText,     QColor(220, 220, 220))
    palette.setColor(QPalette.Text,            QColor(220, 220, 220))
    palette.setColor(QPalette.Button,          QColor(55, 55, 55))
    palette.setColor(QPalette.ButtonText,      QColor(220, 220, 220))
    palette.setColor(QPalette.BrightText,      QColor(255, 80, 80))
    palette.setColor(QPalette.Link,            QColor(80, 150, 255))
    palette.setColor(QPalette.Highlight,       QColor(42, 100, 190))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    # Dark role is used by the figure/scroll area background (setBackgroundRole(QPalette.Dark))
    palette.setColor(QPalette.Dark,            QColor(50, 50, 50))
    palette.setColor(QPalette.Mid,             QColor(30, 30, 30))
    palette.setColor(QPalette.Shadow,          QColor(0, 0, 0))
    # Disabled state
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(120, 120, 120))
    palette.setColor(QPalette.Disabled, QPalette.Text,       QColor(120, 120, 120))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    return palette


def _light_palette():
    # Return an empty palette so Qt uses the platform/system default
    return QPalette()


def resolve_theme(theme_name):
    """Resolve 'system' to the actual detected theme; return other names unchanged."""
    if theme_name == 'system':
        return detect_system_theme()
    return theme_name


def apply_theme(theme_name):
    """Apply *theme_name* ('system', 'light', or 'dark') to the running QApplication.
    Returns the resolved theme name ('light' or 'dark') so callers can update icons."""
    app = QApplication.instance()
    if app is None:
        return theme_name
    resolved = resolve_theme(theme_name)
    if resolved == 'dark':
        app.setPalette(_dark_palette())
        app.setStyleSheet("""
            QToolTip {
                color: #dcdcdc;
                background-color: #282828;
                border: 1px solid #555555;
            }
        """)
    else:
        app.setPalette(_light_palette())
        app.setStyleSheet('')
    save_theme(theme_name)   # from user_prefs
    return resolved


def load_saved_theme():
    """Return the last saved theme name, defaulting to 'system'."""
    return load_theme()
