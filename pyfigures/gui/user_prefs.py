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
    """Open the chat sidebar every time PyFigures starts. Until the user
    chooses (View → Open the chat at start-up): on (pip installs and the
    standalone apps, which bundle the sidebar), except in the web chat app,
    which opens with the web page, and the MCP Edition, whose AI is an outside app."""
    return _s().value('ui/chat_at_start', chat_at_start_default(), type=bool)


def chat_at_start_default(frozen=None, executable=None):
    import sys
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    if not frozen:
        return True
    from pyfigures.assistant import is_mcp_app
    from pyfigures.assistant.web_chat import is_web_chat_app
    executable = sys.executable if executable is None else executable
    return not is_web_chat_app(executable) and not is_mcp_app(executable)

def save_chat_at_start(value):
    _s().setValue('ui/chat_at_start', bool(value))


def load_share_at_start():
    """Share the open figure with AI apps (pyfigures-live) every time PyFigures starts (user
    2026-11-23: Hermes used pyfigures-live but the window was not shared, so it built a file
    instead). Off until chosen (on in the MCP Edition app); Register in Tools > MCP server…
    turns it on."""
    from pyfigures.assistant import is_mcp_app
    return _s().value('ui/share_at_start', is_mcp_app(), type=bool)


def take_mcp_app_welcome():
    """True once: the MCP Edition's first launch, which offers Tools > MCP server…"""
    if _s().value('ui/mcp_app_welcomed', False, type=bool):
        return False
    _s().setValue('ui/mcp_app_welcomed', True)
    return True


def save_share_at_start(value):
    _s().setValue('ui/share_at_start', bool(value))


# ── Adding images ────────────────────────────────────────────────────
def load_max_project_z_stacks():
    """New Z stacks show their max projection (else the first slice)."""
    return _s().value('images/max_project_z', True, type=bool)

def save_max_project_z_stacks(value):
    _s().setValue('images/max_project_z', bool(value))


def load_fit_to_page():
    """Automatic layouts (images added, rows arranged) keep the figure within
    one printed page (View → Fit new layouts to the page)."""
    return _s().value('layout/fit_to_page', True, type=bool)

def save_fit_to_page(value):
    _s().setValue('layout/fit_to_page', bool(value))

def load_page_size():
    """Page that automatic layouts fit: 'A4' (default) or 'Letter'."""
    value = _s().value('layout/page_size', 'A4', type=str)
    return value if value in ('A4', 'Letter') else 'A4'

def save_page_size(value):
    _s().setValue('layout/page_size', value if value in ('A4', 'Letter') else 'A4')


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
