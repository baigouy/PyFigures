"""
Persistent user preferences for PyFigures.

All preferences are stored via QSettings (INI file on Linux/Mac:
~/.config/pyfigures/pyfigures.conf; registry on Windows).
QSettings flushes to disk automatically on destruction / app quit.
"""

from batoolset.settings.global_settings import set_UI
set_UI()
from qtpy.QtCore import QSettings

_ORG = 'pyfigures'
_APP = 'pyfigures'


def _s():
    return QSettings(_ORG, _APP)


# ── Theme ────────────────────────────────────────────────────────────
def load_theme():
    return _s().value('ui/theme', 'system')

def save_theme(value):
    _s().setValue('ui/theme', value)


# ── Tips ─────────────────────────────────────────────────────────────
def load_auto_show_tips():
    return _s().value('ui/auto_show_tips', True, type=bool)

def save_auto_show_tips(value):
    _s().setValue('ui/auto_show_tips', bool(value))
