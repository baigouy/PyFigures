"""Share the open figure editor with the MCP server and dock the chat.

``start_live_session(window)`` serves the window's figure on 127.0.0.1
(bearer token in ``runtime_dir()/connection.json``) for
``python -m pyfigures.assistant.live_mcp``; ``attach_sidecar(window)`` also
docks the optional ``qtpy_ai_sidecar`` chat on the right of the window.
Hand-written: packaging/port_assistant.py never overwrites this file.
"""
from __future__ import annotations

import json
import os
import secrets
import sys

from pyfigures.assistant import runtime_dir


def shareable_window(window):
    """The window to share: *window* itself when it already has the
    live-session behaviours (letter policies, structure guards, verified bulk
    edits: a PartnerGUI, as opened by --share / --chat), else a PartnerGUI
    that takes over its figure, file name, unsaved state and undo history,
    the plain window then closing. (A Qt window cannot change class once
    created: sip crashes.)"""
    from pyfigures.gui.pfgui import EZFIG_GUI
    from .partner_gui import PartnerGUI
    if isinstance(window, PartnerGUI):
        return window
    if type(window) is not EZFIG_GUI:
        raise TypeError('Only a figure editor window can share its figure')
    import shutil
    new = PartnerGUI()
    handover = os.path.join(new.temp_dir.name, 'handover.pyf')
    window._save_state_to_file(handover)
    new.reload_state(handover, append=False)
    moved = {}

    def carry(path):
        # undo states are files in the closing window's temp folder
        if not path or not os.path.isfile(path):
            return path
        if path not in moved:
            moved[path] = os.path.join(new.temp_dir.name, os.path.basename(path))
            shutil.copy2(path, moved[path])
        return moved[path]
    new.undo_stack = [carry(p) for p in window.undo_stack]
    new.redo_stack = [carry(p) for p in window.redo_stack]
    new.last_called_state = carry(window.last_called_state)
    new.current_index = window.current_index
    new.counter = getattr(window, 'counter', 0)
    new.current_file = window.current_file
    for name in ('main_space_spinner', 'size_spinbox'):
        getattr(new, name).setValue(getattr(window, name).value())
    new.auto_lettering_checkbox.setChecked(window.auto_lettering_checkbox.isChecked())
    new.letter_line_edit.setText(window.letter_line_edit.text())
    if window._dirty:
        new._mark_dirty()
    else:
        new._mark_clean()
    new.update_button_state()
    new.setGeometry(window.geometry())
    if window.isVisible():
        new.show()
    window._dirty = False
    window.close()
    return new


def is_sharing(window) -> bool:
    return getattr(window, '_live_server', None) is not None


def start_live_session(window):
    """Serve *window* for the MCP server (live_mcp) and the chat dock. One
    window at a time per runtime folder. Returns the Session; its
    ``window`` is the shared window (see shareable_window)."""
    if is_sharing(window):
        return window._live_session
    from qtpy.QtCore import QLockFile
    from pyfigures.atomic_io import write_atomic
    state = runtime_dir()
    lock = QLockFile(str(state / 'gui.lock'))
    if not lock.tryLock(0):
        raise RuntimeError('Another PyFigures window already shares its figure with the MCP server. '
                           'Stop it there (or close that window) first.')
    try:
        window = shareable_window(window)
        from .session import Session, serve
        session = Session(window)
        token = secrets.token_urlsafe(32)
        server = serve(session, token)
    except Exception:
        lock.unlock()
        raise
    descriptor = state / 'connection.json'
    write_atomic(str(descriptor), json.dumps({'url': f'http://127.0.0.1:{server.server_port}',
                                             'token': token, 'session_id': session.id, 'pid': os.getpid()}))
    window._live_server = server
    window._live_lock = lock
    window._live_descriptor = descriptor
    return session


def stop_live_session(window):
    """Stop serving *window*: a last recovery copy, server down, descriptor
    removed. False when it was not sharing."""
    session = getattr(window, '_live_session', None)
    server = getattr(window, '_live_server', None)
    if session is None or server is None:
        return False
    try:
        session.auto_recover()
    finally:
        session.timer.stop()
        session.recovery_timer.stop()
        server.shutdown()
        server.server_close()
        descriptor = window._live_descriptor
        try:
            if json.loads(descriptor.read_text(encoding='utf-8')).get('session_id') == session.id:
                descriptor.unlink()
        except (OSError, ValueError):
            pass
        window._live_lock.unlock()
        window._live_server = None
        window._live_session = None
    return True


def mcp_server_command() -> tuple[str, list]:
    """How to start the live MCP server. In a standalone app sys.executable is
    PyFigures itself (``-m`` would open a second window): it runs with
    ``--live-mcp``; on Windows through the console twin "PyFigures MCP.exe"
    built beside it, since a windowed exe has no usable stdio."""
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        if sys.platform == 'win32':
            twin = os.path.join(os.path.dirname(exe), 'PyFigures MCP.exe')
            if os.path.isfile(twin):
                exe = twin
        return exe, ['--live-mcp']
    return sys.executable, ['-m', 'pyfigures.assistant.live_mcp']


def mcp_server_entry() -> dict:
    """The MCP client configuration for the live figure (stdio)."""
    command, args = mcp_server_command()
    return {'command': command, 'args': args,
            'env': {'PYFIGURES_MCP_SURFACE': 'categories', 'PYFIGURES_LIVE_RUNTIME': str(runtime_dir())}}


LM_STUDIO_URL = 'http://127.0.0.1:1234/v1'


def lm_studio_model(timeout=1.0):
    """The model LM Studio is serving on this computer (the loaded one when
    it says which), or None when it is not running."""
    import urllib.request
    base = LM_STUDIO_URL.rsplit('/v1', 1)[0]
    try:
        with urllib.request.urlopen(base + '/api/v0/models', timeout=timeout) as r:
            models = json.load(r).get('data', [])
        loaded = [m['id'] for m in models if m.get('state') == 'loaded' and m.get('type', 'llm') != 'embeddings']
        if loaded:
            return loaded[0]
    except Exception:
        pass
    try:
        with urllib.request.urlopen(LM_STUDIO_URL + '/models', timeout=timeout) as r:
            ids = [m['id'] for m in json.load(r).get('data', []) if 'embed' not in m['id']]
        return ids[0] if ids else None
    except Exception:
        return None


def needs_model(config) -> bool:
    """The chat has no model to talk to: local mode without a model of its own."""
    return config.provider == 'local' and not config.runtime


def sidecar_config(descriptor=None):
    """The chat dock's profile: the user's own JSON (PYFIGURES_SIDECAR_CONFIG,
    else <runtime>/sidecar.json) when there is one, always pointed at this
    session and at ``python -m pyfigures.assistant.live_mcp``."""
    from qtpy_ai_sidecar.config import Config
    descriptor = str(descriptor or runtime_dir() / 'connection.json')
    profile = os.environ.get('PYFIGURES_SIDECAR_CONFIG') or str(runtime_dir() / 'sidecar.json')
    if not os.path.isfile(profile):
        # Config.load (not Config()) applies the model connection and settings
        # the user saved in the sidecar's own storage
        profile = str(runtime_dir() / 'sidecar.default.json')
        with open(profile, 'w', encoding='utf-8') as f:
            json.dump({'application': 'PyFigures'}, f)
    config = Config.load(profile)
    if needs_model(config):
        # nothing chosen yet: local mode only runs a model the chat manages
        # itself, and said so only after the first message ("the model did
        # not launch") although LM Studio was serving one
        model = lm_studio_model()
        if model:
            config.provider, config.base_url, config.model = 'compatible', LM_STUDIO_URL, model
    config.adapter ={**(config.adapter or {}), 'type': 'pyfigures', 'descriptor': descriptor}
    config.servers = {**(config.servers or {}), 'pyfigures': mcp_server_entry()}
    from pyfigures.mcp_control import MODEL_WARNING, REMOTE_MODEL_WARNING
    config.notice = MODEL_WARNING        # the line always shown under the chat
    config.remote_notice = REMOTE_MODEL_WARNING    # added only for an online provider
    return config


def apply_launch_flags(window, argv):
    """``--share``: share the figure with the MCP server at start-up;
    ``--chat``: also dock the chat (qtpy_ai_sidecar)."""
    if '--chat' in argv:
        return attach_sidecar(window).parent()
    if '--share' in argv:
        return start_live_session(window).window
    return window


def attach_sidecar(window):
    """Share the figure if needed and dock the qtpy_ai_sidecar chat on the
    right of *window*. Raises ImportError when that package is missing."""
    existing = getattr(window, 'local_chat_dock', None)
    if existing is not None:
        existing.show()
        existing.raise_()
        return existing
    from qtpy_ai_sidecar.adapters.pyfigures import attach_to_window
    window = start_live_session(window).window
    config = sidecar_config(window._live_descriptor)
    dock = attach_to_window(window, config, window._live_descriptor)
    dock.show()        # created hidden: it only appeared with the window's next show
    dock.needs_model = needs_model(config)
    return dock
