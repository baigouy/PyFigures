"""Registering PyFigures with Mistral Vibe (user 2026-11-24: installed by the employer; it must
be offered, first in Tools > MCP server…) and the standalone apps starting the saved-file
server themselves (--mcp-server), so registration works there too. The user's real
~/.vibe is never touched: the home folder is a temporary one."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

try:
    import tomllib
except ImportError:                     # Python 3.10: Vibe registration needs tomli there
    tomllib = pytest.importorskip("tomli")

from pyfigures import mcp_control as C

# what Vibe writes itself (tomli_w): an empty inline list before the tables
VIBE_CONFIG = '''active_model = "devstral-2"
mcp_servers = []
enabled_tools = []

[[providers]]
name = "mistral"
api_base = "https://api.mistral.ai/v1"

[providers.extra_headers]
X-Org = "lab"

[tools.bash]
permission = "ask"
'''


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setattr(C, "_home", lambda: str(h))
    monkeypatch.delenv("VIBE_HOME", raising=False)
    monkeypatch.setenv("PYFIGURES_LIVE_RUNTIME", str(tmp_path / "live"))
    return h


def _config(home, text=VIBE_CONFIG):
    path = home / ".vibe" / "config.toml"
    path.parent.mkdir()
    path.write_text(text, encoding="utf-8")
    return path


def _servers(path):
    return {s["name"]: s for s in tomllib.loads(path.read_text(encoding="utf-8")).get("mcp_servers", [])}


def test_vibe_is_offered_first(home, monkeypatch):
    assert next(iter(C.CLIENTS)) == "vibe" and C.CLIENTS["vibe"] == "Mistral Vibe"
    assert C.client_config_path("vibe") == os.path.join(str(home), ".vibe", "config.toml")
    monkeypatch.setenv("VIBE_HOME", str(home / "elsewhere"))
    assert C.client_config_path("vibe") == os.path.join(str(home / "elsewhere"), "config.toml")


def test_register_keeps_the_rest_of_vibes_config(home):
    path = _config(home)
    before = tomllib.loads(VIBE_CONFIG)
    assert C.registration("vibe")["registered"] is False
    msg = C.register("vibe", python=r"C:\Program Files\py\python.exe")
    assert msg.startswith("Registered with Mistral Vibe"), msg
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert {k: v for k, v in data.items() if k != "mcp_servers"} == \
        {k: v for k, v in before.items() if k != "mcp_servers"}
    servers = _servers(path)
    files, live = servers["pyfigures"], servers["pyfigures-live"]
    # a list, not a string: Vibe would shlex-split the backslashes away
    assert files["command"] == [r"C:\Program Files\py\python.exe"]
    assert files["args"] == ["-m", "pyfigures.mcp_server", "--tools", "categories"]
    assert files["transport"] == live["transport"] == "stdio"
    assert files["startup_timeout_sec"] >= 30
    assert live["args"] == ["-m", "pyfigures.assistant.live_mcp"]
    assert live["env"]["PYFIGURES_LIVE_RUNTIME"]
    assert C.registration("vibe")["registered"] is True
    assert "already" in C.register("vibe", python=r"C:\Program Files\py\python.exe")
    assert list(home.joinpath(".pyfigures", "backups").glob("config.toml.*.bak"))


def test_other_servers_kept_and_unregister(home):
    path = _config(home, VIBE_CONFIG.replace(
        "mcp_servers = []\n", "") + '\n[[mcp_servers]]\nname = "fetch"\ntransport = "stdio"\n'
        'command = "uvx"\nargs = ["mcp-server-fetch"]\n\n[mcp_servers.env]\nA = "1"\n')
    C.register("vibe", python="/usr/bin/python3")
    assert set(_servers(path)) == {"fetch", "pyfigures", "pyfigures-live"}
    assert _servers(path)["fetch"]["env"] == {"A": "1"}
    msg = C.unregister("vibe")
    assert msg.startswith("Removed from Mistral Vibe"), msg
    assert set(_servers(path)) == {"fetch"}
    assert tomllib.loads(path.read_text(encoding="utf-8"))["tools"] == {"bash": {"permission": "ask"}}
    assert "does not list" in C.unregister("vibe")


def test_no_config_yet_and_switched_off(home):
    path = home / ".vibe" / "config.toml"
    C.register("vibe", python="/usr/bin/python3")
    assert set(_servers(path)) == {"pyfigures", "pyfigures-live"}
    text = path.read_text(encoding="utf-8").replace('name = "pyfigures"\n',
                                                    'name = "pyfigures"\ndisabled = true\n', 1)
    path.write_text(text, encoding="utf-8")
    assert C.registration("vibe")["disabled"] is True
    C.register("vibe", python="/usr/bin/python3")       # switches it back on
    assert C.registration("vibe")["registered"] is True


def test_a_broken_config_is_left_alone(home):
    path = _config(home, "mcp_servers = [\n")
    assert C.register("vibe", python="/usr/bin/python3").startswith("ERROR")
    assert path.read_text(encoding="utf-8") == "mcp_servers = [\n"
    assert C.registration("vibe")["error"]


def test_standalone_app_starts_the_file_server_itself(monkeypatch, tmp_path):
    """In PyFigures.exe, `-m pyfigures.mcp_server` would open a window: --mcp-server instead,
    through the console twin on Windows (as --live-mcp)."""
    exe = tmp_path / "PyFigures.exe"
    exe.write_bytes(b"")
    (tmp_path / "PyFigures MCP.exe").write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    entry = C.server_entry()
    assert entry["args"] == ["--mcp-server"]
    expected = "PyFigures MCP.exe" if sys.platform == "win32" else "PyFigures.exe"
    assert os.path.basename(entry["command"]) == expected


def test_main_dispatches_mcp_server_flag():
    src = open(os.path.join(os.path.dirname(C.__file__), "__main__.py"), encoding="utf-8").read()
    assert "'--mcp-server' in sys.argv" in src
    assert src.index("'--mcp-server' in sys.argv") < src.rindex("run_pyfigures()")
