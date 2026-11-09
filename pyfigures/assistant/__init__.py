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


def runtime_dir() -> Path:
    """Connection descriptor, recovery copies and transaction workspaces:
    ``PYFIGURES_LIVE_RUNTIME`` if set, else the user's app-data folder
    (never the repository, never the figure's folder)."""
    override = os.environ.get("PYFIGURES_LIVE_RUNTIME")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        path = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "PyFigures" / "assistant"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "PyFigures" / "assistant"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "PyFigures" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def descriptor_path() -> Path:
    return runtime_dir() / "connection.json"


def sidecar_available() -> bool:
    if not ai_features_enabled():
        return False
    try:
        import qtpy_ai_sidecar  # noqa: F401
    except Exception:
        return False
    return True


def is_no_ai_app(executable) -> bool:
    """The 'PyFigures NoAI' standalone app, told apart by its name."""
    name = os.path.basename(executable).lower().replace(" ", "").replace("-", "").replace("_", "")
    return "noai" in name


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
