"""Live link between the open figure editor and an MCP client or the
qtpy_ai_sidecar chat dock.

``start_live_session(window)`` serves the open document on 127.0.0.1 (bearer
token in ``connection.json``); ``python -m pyfigures.assistant.live_mcp`` is
the stdio MCP server that forwards to it. The chat dock itself is the separate
``qtpy_ai_sidecar`` package (optional): ``attach_sidecar(window)`` docks it
when it is installed.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def default_runtime_dir() -> Path:
    """The runtime folder when PYFIGURES_LIVE_RUNTIME is not set. On Windows
    ~/.pyfigures/live, not under AppData: a program started from a Microsoft
    Store app (Claude, Codex, Hermes Agent...) has its AppData writes redirected
    into that app's private copy, so a PyFigures started from one app wrote a
    connection.json that an MCP server started by another app never saw
    (user 2026-11-23, Hermes Agent: GUI_OFFLINE while the window was shared)."""
    if sys.platform == "win32":
        return Path.home() / ".pyfigures" / "live"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PyFigures" / "assistant"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "PyFigures" / "assistant"


def legacy_runtime_dir():
    """Where PyFigures 0.2.24 and older kept it on Windows (None elsewhere)."""
    if sys.platform != "win32":
        return None
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "PyFigures" / "assistant"


def runtime_dir() -> Path:
    """Connection descriptor, recovery copies and transaction workspaces:
    ``PYFIGURES_LIVE_RUNTIME`` if set, else default_runtime_dir()
    (never the repository, never the figure's folder)."""
    override = os.environ.get("PYFIGURES_LIVE_RUNTIME")
    path = Path(override) if override else default_runtime_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def descriptor_path() -> Path:
    """The connection.json to read: in runtime_dir(), else in the default
    folder. A client registered with 0.2.24 or older passes the old AppData
    folder in PYFIGURES_LIVE_RUNTIME while the window now writes the default
    one."""
    first = runtime_dir() / "connection.json"
    if first.is_file() or os.environ.get("PYFIGURES_LIVE_RUNTIME") is None:
        return first
    legacy = legacy_runtime_dir()
    if legacy is not None and Path(os.environ["PYFIGURES_LIVE_RUNTIME"]) != legacy:
        return first                     # a folder of its own (tests, replays): only that one
    fallback = default_runtime_dir() / "connection.json"
    return fallback if fallback.is_file() else first


def sidecar_available() -> bool:
    if not ai_features_enabled():
        return False
    try:
        import qtpy_ai_sidecar  # noqa: F401
    except Exception:
        return False
    return True


def bundled_app_kind():
    """'standard', 'no_ai', 'mcp' or 'web_chat': what pyfigures.spec wrote into this
    standalone app (pyfigures/app_kind.txt). None when not an app, or one
    built before 0.2.8: the executable's name then tells."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        return (Path(sys._MEIPASS) / "pyfigures" / "app_kind.txt").read_text(encoding="utf-8").strip() or None
    except (OSError, AttributeError, TypeError):
        return None


def is_no_ai_app(executable) -> bool:
    """The 'PyFigures NoAI' standalone app: by what the build wrote into
    it (a renamed executable stays what it is), else by its name."""
    if executable == sys.executable:
        kind = bundled_app_kind()
        if kind:
            return kind == "no_ai"
    name = os.path.basename(executable).lower().replace(" ", "").replace("-", "").replace("_", "")
    return "noai" in name


def is_mcp_app(executable=None) -> bool:
    """The 'PyFigures MCP Edition' standalone app (pyfigures.spec with PYFIGURES_MCP_APP=1,
    user 2026-11-24): the AI is an outside app (Mistral Vibe, Claude, Hermes...) reaching the
    open figure through MCP. No chat at start-up; the figure is shared at start-up and the
    first launch offers to register PyFigures with those apps. Not the console twin
    'PyFigures MCP.exe' by name alone: by what the build wrote, else 'MCP Edition'."""
    executable = sys.executable if executable is None else executable
    if executable == sys.executable and getattr(sys, "frozen", False):
        kind = bundled_app_kind()
        if kind:
            return kind == "mcp"
    name = os.path.basename(executable).lower().replace(" ", "").replace("-", "").replace("_", "")
    return "mcpedition" in name


def ai_features_enabled() -> bool:
    """False in the no-AI install (``pip install pyfigures-noai``: no chat
    sidebar package, and the chat / MCP entries hidden) or with
    PYFIGURES_NO_AI=1."""
    if os.environ.get("PYFIGURES_NO_AI") == "1":
        return False
    if getattr(sys, "frozen", False):
        # the "PyFigures NoAI" app (pyfigures.spec with PYFIGURES_NO_AI=1)
        return not is_no_ai_app(sys.executable)
    import importlib.metadata as md
    try:
        md.distribution("pyfigures-noai")
    except md.PackageNotFoundError:
        return True
    return False
