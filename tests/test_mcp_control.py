"""Starting, stopping and registering the MCP server (pyfigures/mcp_control.py):
command line, GUI (Tools > MCP server…) and the read-only MCP tool
mcp_server_info. The user's real client configurations are never touched:
the home folder is a temporary one."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

pytest.importorskip("mcp")
from pyfigures import mcp_control as C


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setattr(C, "_home", lambda: str(h))
    monkeypatch.setenv("APPDATA", str(h / "AppData" / "Roaming"))
    return h


def _free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_register_and_unregister_keep_every_other_entry(home):
    cfg = home / ".claude.json"
    cfg.write_text(json.dumps({"numStartups": 3, "mcpServers": {"other": {"command": "x"}},
                               "_mcpServersDisabled": {"pyfigures": {"command": "old"}}}),
                   encoding="utf-8")
    assert C.registration("claude_code")["disabled"]
    res = C.register("claude_code", python="py.exe")
    assert res.startswith("Registered") and "backups" in res
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["numStartups"] == 3 and "other" in data["mcpServers"]
    assert data["mcpServers"]["pyfigures"]["args"] == ["-m", "pyfigures.mcp_server"]
    assert "pyfigures" not in data["_mcpServersDisabled"]          # switched back on
    assert "already" in C.register("claude_code", python="py.exe")
    assert C.unregister("claude_code").startswith("Removed")
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "pyfigures" not in data["mcpServers"] and "other" in data["mcpServers"]
    assert len(os.listdir(C.backup_dir())) == 2
    # a new file for a client never configured
    assert C.register("lm_studio").startswith("Registered")
    assert C.registration("lm_studio")["registered"]
    assert "does not list" in C.unregister("cursor")


def test_unreadable_configuration_is_never_overwritten(home):
    cfg = home / ".lmstudio" / "mcp.json"
    cfg.parent.mkdir()
    cfg.write_text("{ not json", encoding="utf-8")
    assert C.registration("lm_studio")["error"]
    assert C.register("lm_studio").startswith("ERROR")
    assert cfg.read_text(encoding="utf-8") == "{ not json"


def test_lm_studio_entry_switched_off_by_mcp_commander(home):
    stash = home / ".claude" / "mcp_commander_local_disabled.json"
    stash.parent.mkdir()
    stash.write_text(json.dumps({"lmstudio": {"pyfigures": {"command": "py"}}}), encoding="utf-8")
    assert C.registration("lm_studio")["disabled"]
    assert "MCP Commander" in C.unregister("lm_studio")
    assert "switched off" in C.describe()


def test_quick_edits_keep_every_backup(home, monkeypatch):
    import datetime as dt
    frozen = dt.datetime(2026, 10, 19, 9, 0, 0)

    class Clock(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen
    monkeypatch.setattr(C.datetime, "datetime", Clock)
    cfg = str(home / "a.json")
    for k in range(4):
        C._write_json(cfg, {"k": k})
    assert len(os.listdir(C.backup_dir())) == 3


def test_snippets(home):
    assert json.loads(C.config_snippet("py"))["mcpServers"]["pyfigures"]["command"] == "py"
    toml = C.config_snippet("C:\\py\\python.exe", fmt="codex")
    assert C._toml_load(toml)["mcp_servers"]["pyfigures"]["command"] == "C:\\py\\python.exe"
    import yaml
    hermes = yaml.safe_load(C.config_snippet("C:\\py\\python.exe", fmt="hermes"))
    expected = "/mnt/c/py/python.exe" if sys.platform == "win32" else "C:\\py\\python.exe"
    assert hermes["mcp_servers"]["pyfigures"]["command"] == expected
    assert C.config_snippet(fmt="url").endswith("/mcp")


def test_http_snippets_for_each_kind_of_client(home):
    url = "http://127.0.0.1:9999/mcp"
    s = {x["title"]: x["text"] for x in C.http_snippets(url)}
    assert s["Address"] == url
    assert s["Claude Code"] == f"claude mcp add --transport http pyfigures {url}"
    assert json.loads(s["JSON with a URL"])["mcpServers"]["pyfigures"] == {"url": url}
    assert json.loads(s["AnythingLLM"])["mcpServers"]["pyfigures"]["type"] == "streamable"
    assert json.loads(s["Gemini CLI"])["mcpServers"]["pyfigures"] == {"httpUrl": url}
    assert C._toml_load(s["Codex"])["mcp_servers"]["pyfigures"] == {"url": url}
    import yaml
    assert yaml.safe_load(s["Hermes Agent"])["mcp_servers"]["pyfigures"] == {"url": url}
    assert json.loads(s["Clients that only start programs"])["mcpServers"]["pyfigures"]["args"][-1] == url
    assert C.http_url(9999) == url
    text = C.config_snippet(fmt="http")
    assert "Claude Code" in text and "/mcp" in text


def test_codex_toml_keeps_comments_and_other_tables(home):
    cfg = home / ".codex" / "config.toml"
    cfg.parent.mkdir()
    original = ('# my settings\nmodel = "x"\n\n[mcp_servers.other]\ncommand = "o"\n\n'
                '[mcp_servers.pyfigures]\ncommand = "old"\nargs = []\n\n'
                '[mcp_servers.pyfigures.env]\nA = "1"\n\n[desktop]\nfoo = 1\n')
    cfg.write_text(original, encoding="utf-8")
    assert C.registration("codex")["registered"]
    assert C.register("codex", python="C:\\py\\python.exe").startswith("Registered")
    text = cfg.read_text(encoding="utf-8")
    data = C._toml_load(text)
    assert text.startswith("# my settings")
    assert data["mcp_servers"]["pyfigures"] == {"command": "C:\\py\\python.exe",
                                                "args": ["-m", "pyfigures.mcp_server"]}
    assert data["mcp_servers"]["other"] == {"command": "o"} and data["desktop"] == {"foo": 1}
    assert "already" in C.register("codex", python="C:\\py\\python.exe")
    assert C.unregister("codex").startswith("Removed")
    data = C._toml_load(cfg.read_text(encoding="utf-8"))
    assert "pyfigures" not in data["mcp_servers"] and data["desktop"] == {"foo": 1}
    cfg.write_text("[mcp_servers.pyfigures]\ncommand = 'p'\nenabled = false\n", encoding="utf-8")
    assert C.registration("codex")["disabled"]
    cfg.write_text("not = = toml", encoding="utf-8")
    assert C.register("codex").startswith("ERROR")
    assert cfg.read_text(encoding="utf-8") == "not = = toml"


def test_anythingllm(home):
    cfg = home / "AppData" / "Roaming" / "anythingllm-desktop" / "storage" / "plugins" \
        / "anythingllm_mcp_servers.json"
    if sys.platform != "win32":
        cfg = C.client_config_path("anythingllm")
    assert C.client_config_path("anythingllm") == str(cfg)
    assert C.register("anythingllm").startswith("Registered")
    assert C.registration("anythingllm")["registered"]


def test_http_server_starts_answers_and_stops_with_its_children(home):
    port = _free_port()
    res = C.start_http(port)
    assert "running at" in res, res
    st = C.http_status()
    assert st["running"] and st["listening"]
    assert "already running" in C.start_http(port)

    async def call():
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
        async with streamablehttp_client(st["url"]) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                res = await s.call_tool("mcp_server_info", {})
                return res.content[0].text

    try:
        info = asyncio.run(call())
        assert "tools" in info and "HTTP server" in info
    finally:
        out = C.stop_http()
    assert out.startswith("Stopped"), out
    assert not C._pid_alive(st["pid"])
    assert not C.http_status()["running"]
    assert "not running" in C.stop_http()


def test_command_line(home, capsys):
    assert C.main(["status"]) == 0
    assert "not registered" in capsys.readouterr().out
    assert C.main(["register", "gemini_cli"]) == 0
    assert C.registration("gemini_cli")["registered"]
    assert C.main(["snippet", "--format", "codex"]) == 0
    assert "[mcp_servers.pyfigures]" in capsys.readouterr().out
    assert C.main(["stop"]) == 0


@pytest.mark.skipif(sys.platform != "win32", reason="Windows job object")
def test_processes_a_server_started_end_with_it(tmp_path):
    """A child started by a tool (renderer, LaTeX, ffmpeg) does not outlive a
    server its client killed."""
    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess, sys, time\n"
        "from pyfigures.mcp_server import _children_die_with_me\n"
        "assert _children_die_with_me() is not None\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        f"open(r'{pid_file}', 'w').write(str(p.pid))\n"
        "time.sleep(120)\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([os.path.dirname(os.path.dirname(os.path.abspath(C.__file__))),
                                         env.get("PYTHONPATH", "")])
    server = subprocess.Popen([sys.executable, "-c", script], env=env)
    end = time.time() + 120
    while not pid_file.exists() or not pid_file.read_text():
        assert time.time() < end and server.poll() is None
        time.sleep(0.2)
    child = int(pid_file.read_text())
    assert C._pid_alive(child)
    server.kill()                              # what a client does on quit
    server.wait()
    end = time.time() + 10
    while C._pid_alive(child) and time.time() < end:
        time.sleep(0.2)
    assert not C._pid_alive(child)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
def test_processes_a_server_started_end_with_it_on_sigterm(tmp_path):
    """macOS / Linux: a client stopping the server (SIGTERM) stops its children."""
    import signal
    pid_file = tmp_path / "child.pid"
    script = (
        "import subprocess, sys, time\n"
        "from pyfigures.mcp_server import _children_die_with_me\n"
        "assert _children_die_with_me() == 'posix'\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        f"open(r'{pid_file}', 'w').write(str(p.pid))\n"
        "time.sleep(120)\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([os.path.dirname(os.path.dirname(os.path.abspath(C.__file__))),
                                         env.get("PYTHONPATH", "")])
    server = subprocess.Popen([sys.executable, "-c", script], env=env)
    end = time.time() + 120
    while not pid_file.exists() or not pid_file.read_text():
        assert time.time() < end and server.poll() is None
        time.sleep(0.2)
    child = int(pid_file.read_text())
    assert C._pid_alive(child)
    server.send_signal(signal.SIGTERM)
    server.wait(30)
    end = time.time() + 10
    while C._pid_alive(child) and time.time() < end:
        time.sleep(0.2)
    assert not C._pid_alive(child)


def test_kill_children_stops_the_processes_started():
    script = (
        "import subprocess, sys\n"
        "from pyfigures.mcp_server import _kill_children\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        "_kill_children()\n"
        "print(p.wait(10) is not None)\n")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([os.path.dirname(os.path.dirname(os.path.abspath(C.__file__))),
                                         env.get("PYTHONPATH", "")])
    out = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True,
                         timeout=120)
    assert out.stdout.strip() == "True", out.stderr


def test_gui_dialog_registers_and_starts_the_http_server(home, qapp, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui import mcp_server_dialog as D
    from pyfigures.gui import user_prefs
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    dlg = D.McpServerDialog()
    assert dlg._reg_buttons["lm_studio"].text() == "Register"
    assert dlg.toggle_registration("lm_studio").startswith("Registered")
    assert dlg._reg_buttons["lm_studio"].text() == "Remove"
    assert dlg._reg_labels["lm_studio"].text() == "registered"
    dlg.copy_snippet("codex")
    from qtpy.QtGui import QGuiApplication
    assert "[mcp_servers.pyfigures]" in QGuiApplication.clipboard().text()
    dlg.port.setValue(_free_port())
    try:
        assert "running at" in dlg.toggle_http(wait=True)
        qapp.processEvents()
        assert dlg.start_stop.text() == "Stop the HTTP server"
        url = C.http_status()["url"]
        assert "Running at" in dlg.http_state.text() and url in dlg.http_state.text()
        assert not dlg.http_snippets.isHidden()
        assert dlg._snippet_texts[0].text() == url
        dlg.copy_http_snippet(2)
        assert json.loads(QGuiApplication.clipboard().text())["mcpServers"]["pyfigures"]["url"] == url
    finally:
        assert dlg.toggle_http(wait=True).startswith("Stopped")
    qapp.processEvents()
    assert dlg.start_stop.text() == "Start the HTTP server"
    assert dlg.http_snippets.isHidden()
    # autostart with PyFigures (off by default), stopped at close
    assert D.autostart_http_server() is False
    user_prefs.save_mcp_http_port(_free_port())
    user_prefs.save_mcp_http_autostart(True)
    try:
        assert D.autostart_http_server() is True
        D._autostart_thread.join(60)
        assert C.http_status()["running"]
    finally:
        user_prefs.save_mcp_http_autostart(False)
        assert D.stop_autostarted_http_server().startswith("Stopped")


def test_gui_menu_opens_the_dialog(home, qapp, monkeypatch):
    from pyfigures.gui import mcp_server_dialog as D
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(D.McpServerDialog, "exec_", lambda self: 0)
    g = EZFIG_GUI()
    actions = [a for m in g.menuBar.actions() for a in m.menu().actions()] \
        if hasattr(g.menuBar, "actions") else []
    action = next(a for a in actions if a.text() == "MCP server…")
    action.trigger()
    dlg = g.open_mcp_server_dialog()
    assert isinstance(dlg, D.McpServerDialog)
    assert dlg.model_warning.text().endswith(C.MODEL_WARNING)    # models make mistakes
    # the toolbar's robot opens the chat, first in the toolbar so it is always visible
    opened = []
    monkeypatch.setattr(g, "open_chat_sidebar", lambda: opened.append(1))
    assert g.mainToolBar.actions()[0] is g.chat_toolbar_action
    g.chat_toolbar_action.trigger()
    assert opened == [1]
    # View → Open the chat at start-up is remembered (pyfigures/__main__.py reads it)
    from pyfigures.gui.user_prefs import load_chat_at_start
    was = load_chat_at_start()
    try:
        g.chat_at_start_action.setChecked(True)
        assert load_chat_at_start() is True
        g.chat_at_start_action.setChecked(False)
        assert load_chat_at_start() is False
    finally:
        g.chat_at_start_action.setChecked(was)
    # the dialog says how to use it (LM Studio's plug icon, saved files)
    dlg = D.McpServerDialog(g)
    from qtpy.QtWidgets import QLabel
    text = " ".join(l.text() for l in dlg.findChildren(QLabel))
    assert "plug / hammer icon" in text and "saved .pyf files" in text
    dlg.deleteLater()
