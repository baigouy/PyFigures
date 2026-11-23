"""User 2026-11-23: "can this be made simpler" (Hermes edited a file, not the figure open in the
window) / "can the MCP also directly guide a third party app to set up the MCP for live
interaction with the GUI". Register adds both servers ('pyfigures' for files, 'pyfigures-live'
for the open window), in every client's format, and removes both; the file server tells a
client how to reach the open window (live_window_setup)."""
import json
import os

import pytest

from pyfigures import mcp_control as C


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setattr(C, "_home", lambda: str(h))
    monkeypatch.setenv("APPDATA", str(h / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(h / "AppData" / "Local"))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return h


def test_json_clients_get_both_and_lose_both(home):
    C.register("claude_code", python="py.exe")
    servers = json.loads((home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"]
    assert servers["pyfigures"]["args"] == ["-m", "pyfigures.mcp_server"]
    assert servers["pyfigures-live"]["args"] == ["-m", "pyfigures.assistant.live_mcp"]
    assert servers["pyfigures-live"]["type"] == "stdio" and "PYFIGURES_LIVE_RUNTIME" in servers["pyfigures-live"]["env"]
    assert "already" in C.register("claude_code", python="py.exe")
    C.unregister("claude_code")
    servers = json.loads((home / ".claude.json").read_text(encoding="utf-8"))["mcpServers"]
    assert "pyfigures" not in servers and "pyfigures-live" not in servers


def test_codex_gets_both_as_toml_tables(home):
    C.register("codex", python="py.exe")
    path = C.client_config_path("codex")
    data = C._toml_load(open(path, encoding="utf-8").read())
    assert set(data["mcp_servers"]) == {"pyfigures", "pyfigures-live"}
    assert data["mcp_servers"]["pyfigures-live"]["env"]["PYFIGURES_MCP_SURFACE"] == "categories"
    assert "already" in C.register("codex", python="py.exe")
    C.unregister("codex")
    assert not (C._toml_load(open(path, encoding="utf-8").read()).get("mcp_servers") or {})


def test_the_file_server_tells_how_to_reach_the_open_window(tmp_path, monkeypatch):
    monkeypatch.setenv("PYFIGURES_LIVE_RUNTIME", str(tmp_path))       # no window sharing here
    from pyfigures.mcp_tools.guidance import live_window_setup
    from pyfigures.mcp_tools.category_surface import INSTRUCTIONS
    out = json.loads(live_window_setup())
    assert out["window_sharing_now"] is False and out["server_name"] == "pyfigures-live"
    assert "pyfigures-live" in out["mcpServers_json"] and "mcp_servers:" in out["hermes_yaml"]
    assert any("chat panel" in s for s in out["steps"])
    assert "live_window_setup" in INSTRUCTIONS


def test_the_dialog_puts_the_open_window_first(home, qapp):
    from qtpy.QtWidgets import QLabel
    from pyfigures.gui.mcp_server_dialog import McpServerDialog
    dlg = McpServerDialog()
    texts = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert "pyfigures-live" in texts and "the figure open in this window" in texts
    assert dlg.share_button.text() == "Share this window\x27s figure" and not dlg.share_button.isEnabled()
    assert dlg.share_state.text() == "Not shared yet."
    dlg.deleteLater()
