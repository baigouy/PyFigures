"""Copy buttons show that they copied (user 2026-11-24: "nothing changes when I press the
button"): the button says "✓ Copied" for a moment and the copied text blinks. Also: the MCP
Edition app (replaces the web chat app) opens without the chat, shares the figure and offers
registration once."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest
from qtpy.QtWidgets import QApplication, QLabel, QPushButton

from pyfigures.gui.copy_feedback import COPIED_LABEL, FLASH_STYLE, copy_with_feedback


def _wait(ms):
    app = QApplication.instance()
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def test_button_says_copied_and_text_blinks(qapp):
    button, text = QPushButton("Copy"), QLabel("http://127.0.0.1:8765/mcp")
    try:
        assert copy_with_feedback("http://127.0.0.1:8765/mcp", button=button, flash=text)
        _wait(50)
        assert QApplication.clipboard().text() == "http://127.0.0.1:8765/mcp"
        assert button.text() == COPIED_LABEL and FLASH_STYLE in text.styleSheet()
        _wait(1700)
        assert button.text() == "Copy" and FLASH_STYLE not in text.styleSheet()
    finally:
        button.deleteLater()
        text.deleteLater()


def test_mcp_edition_is_told_apart_from_the_console_twin(monkeypatch):
    from pyfigures import assistant as A
    monkeypatch.setattr(A.sys, "frozen", False, raising=False)
    assert A.is_mcp_app("C:/Apps/PyFigures MCP Edition/PyFigures MCP Edition.exe")
    assert not A.is_mcp_app("C:/Apps/PyFigures/PyFigures MCP.exe")      # the stdio twin
    assert not A.is_mcp_app("C:/Apps/PyFigures/PyFigures.exe")
    monkeypatch.setattr(A.sys, "frozen", True, raising=False)
    monkeypatch.setattr(A, "bundled_app_kind", lambda: "mcp")
    assert A.is_mcp_app()                                                # by what the build wrote
    monkeypatch.setattr(A, "bundled_app_kind", lambda: "standard")
    assert not A.is_mcp_app()


def test_mcp_edition_start_up_defaults(monkeypatch):
    from pyfigures import assistant as A
    from pyfigures.gui import user_prefs
    exe = "C:/Apps/PyFigures MCP Edition/PyFigures MCP Edition.exe"
    assert user_prefs.chat_at_start_default(frozen=True, executable=exe) is False
    assert user_prefs.chat_at_start_default(frozen=True, executable="C:/Apps/PyFigures.exe") is True
    store = {}

    class Settings:
        def value(self, key, default=None, type=None):
            return store.get(key, default)

        def setValue(self, key, value):
            store[key] = value
    monkeypatch.setattr(user_prefs, "_s", lambda: Settings())
    monkeypatch.setattr(A, "is_mcp_app", lambda executable=None: True)
    assert user_prefs.load_share_at_start() is True                     # shared until unticked
    assert user_prefs.take_mcp_app_welcome() is True
    assert user_prefs.take_mcp_app_welcome() is False                  # once only
    store["ui/share_at_start"] = False
    assert user_prefs.load_share_at_start() is False                   # the user's choice wins


def test_first_launch_opens_the_registration_dialog_only_when_nothing_is_registered(qapp, monkeypatch):
    from pyfigures import __main__ as M, mcp_control
    from pyfigures.gui import user_prefs
    opened = []

    class Window:
        def open_mcp_server_dialog(self):
            opened.append(True)
    welcome = iter([True, True, False])
    monkeypatch.setattr(user_prefs, "take_mcp_app_welcome", lambda: next(welcome))
    monkeypatch.setattr(mcp_control, "registrations", lambda: [{"registered": False}])
    window = Window()                   # kept: Qt holds the bound method weakly
    assert M.offer_mcp_registration(window) is True
    _wait(700)
    assert opened == [True]
    monkeypatch.setattr(mcp_control, "registrations", lambda: [{"registered": True}])
    assert M.offer_mcp_registration(Window()) is False                 # already registered
    assert M.offer_mcp_registration(Window()) is False                 # not the first launch
    _wait(700)
    assert opened == [True]


def test_ci_builds_the_mcp_edition_not_the_web_chat_app():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, ".github", "workflows", "build.yml"), encoding="utf-8") as f:
        ci = f.read()
    assert "PyFigures MCP Edition" in ci and "check_mcp_server.py" in ci
    assert "web_chat: '1'" not in ci and "PyFigures-WebChat" not in ci
    with open(os.path.join(root, "pyfigures.spec"), encoding="utf-8") as f:
        spec = f.read()
    assert "PYFIGURES_MCP_APP" in spec and "'mcp' if MCP_APP" in spec
