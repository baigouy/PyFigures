"""User 2026-11-23: Hermes Agent said GUI_OFFLINE while the window was shared. PyFigures had been
started from the Claude desktop app (a Microsoft Store app), and Windows redirected its AppData
writes into Claude's private copy, so the connection.json Hermes looked for was not there. The
runtime folder is now ~/.pyfigures/live on Windows, and a client registered before (old AppData
folder in PYFIGURES_LIVE_RUNTIME) still finds the window."""
import json
import sys
from pathlib import Path

import pytest

import pyfigures.assistant as A

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows Store app redirection")


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    monkeypatch.delenv("PYFIGURES_LIVE_RUNTIME", raising=False)
    return tmp_path / "home"


def test_the_runtime_folder_is_not_under_appdata(home):
    assert A.runtime_dir() == home / ".pyfigures" / "live"
    assert A.legacy_runtime_dir() not in A.runtime_dir().parents
    assert A.descriptor_path() == home / ".pyfigures" / "live" / "connection.json"


def test_an_old_registration_still_finds_the_window(home, monkeypatch):
    legacy = A.legacy_runtime_dir()
    monkeypatch.setenv("PYFIGURES_LIVE_RUNTIME", str(legacy))
    assert A.descriptor_path() == legacy / "connection.json"          # nothing shared yet
    new = A.default_runtime_dir()
    new.mkdir(parents=True)
    (new / "connection.json").write_text(json.dumps({"url": "http://127.0.0.1:9", "token": "t"}))
    assert A.descriptor_path() == new / "connection.json"


def test_a_folder_of_its_own_is_never_left(home, monkeypatch, tmp_path):
    """Tests and replays share in a temporary folder: never the user's open window."""
    new = A.default_runtime_dir()
    new.mkdir(parents=True)
    (new / "connection.json").write_text("{}")
    monkeypatch.setenv("PYFIGURES_LIVE_RUNTIME", str(tmp_path / "own"))
    assert A.descriptor_path() == tmp_path / "own" / "connection.json"


def test_new_registrations_point_at_the_new_folder(home):
    from pyfigures.assistant.launch import mcp_server_entry
    assert mcp_server_entry()["env"]["PYFIGURES_LIVE_RUNTIME"] == str(home / ".pyfigures" / "live")
