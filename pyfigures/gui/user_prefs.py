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


# ── MCP HTTP server ──────────────────────────────────────────────────
def load_mcp_http_autostart():
    """Start the MCP HTTP server when PyFigures opens (off by default)."""
    return _s().value('mcp/http_autostart', False, type=bool)

def save_mcp_http_autostart(value):
    _s().setValue('mcp/http_autostart', bool(value))

def load_mcp_http_port():
    return _s().value('mcp/http_port', 8765, type=int)

def save_mcp_http_port(value):
    _s().setValue('mcp/http_port', int(value))
