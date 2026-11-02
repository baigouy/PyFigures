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


# ── Hints ────────────────────────────────────────────────────────────
def load_show_edit_hint():
    """The 'double-click an image to crop, rotate or annotate it' bubble."""
    return _s().value('ui/show_edit_hint', True, type=bool)

def save_show_edit_hint(value):
    _s().setValue('ui/show_edit_hint', bool(value))


def load_chat_at_start():
    """Open the chat sidebar every time PyFigures starts."""
    return _s().value('ui/chat_at_start', False, type=bool)

def save_chat_at_start(value):
    _s().setValue('ui/chat_at_start', bool(value))


# ── Adding images ────────────────────────────────────────────────────
def load_max_project_z_stacks():
    """New Z stacks show their max projection (else the first slice)."""
    return _s().value('images/max_project_z', True, type=bool)

def save_max_project_z_stacks(value):
    _s().setValue('images/max_project_z', bool(value))


# ── Optional extras ──────────────────────────────────────────────────
def load_offer_pymupdf():
    """Offer to install PyMuPDF (vector PDF panels) when a PDF needs it."""
    return _s().value('extras/offer_pymupdf', True, type=bool)

def save_offer_pymupdf(value):
    _s().setValue('extras/offer_pymupdf', bool(value))


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
