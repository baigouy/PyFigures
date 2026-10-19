"""Start, stop and register the PyFigures MCP server.

Two ways for an MCP client to reach the server:

* **Registered (stdio, on demand)** — the usual way. The client (Claude
  Desktop, Claude Code, LM Studio) starts ``python -m pyfigures.mcp_server``
  itself when it needs the tools and stops it when it quits; nothing runs in
  between, nothing has to be started at login. ``register`` / ``unregister``
  add or remove the entry in the client's configuration file (the previous
  file is kept in ``~/.pyfigures/backups``); the client must be restarted.
  Claude Code and the Code side of Claude Desktop share ``~/.claude.json``;
  a server switched off there (or with MCP Commander) shows as such.
* **HTTP server (started by hand)** — for clients that connect to a URL.
  ``start_http`` runs the server in the background at
  ``http://127.0.0.1:<port>/mcp`` until ``stop_http``, which stops it with
  every process it started (renderers, LaTeX, ffmpeg).

Used by the GUI (Tools > MCP server…), the MCP tool mcp_server_info and the
command line::

    python -m pyfigures.mcp_control status
    python -m pyfigures.mcp_control start [--port 8765]
    python -m pyfigures.mcp_control stop
    python -m pyfigures.mcp_control register lm_studio      # or claude_code, codex, …
    python -m pyfigures.mcp_control unregister lm_studio
    python -m pyfigures.mcp_control snippet --format json|codex|hermes|url|http

Registered directly: Claude Code / Claude Desktop, LM Studio, Codex (OpenAI's
app and CLI, ~/.codex/config.toml), AnythingLLM Desktop, Cursor, Gemini CLI.
Any other client: paste a snippet (the ``mcpServers`` JSON most of them read,
Hermes Agent's YAML) or give it the HTTP server's URL.
"""
from __future__ import annotations

import datetime
import json
import os
import shutil
import socket
import subprocess
import sys
import time

SERVER_NAME = "pyfigures"
DEFAULT_PORT = 8765
CLIENTS = {
    "claude_code": "Claude Code / Claude Desktop (Code)",     # both read ~/.claude.json
    "claude_desktop": "Claude Desktop (Chat)",
    "lm_studio": "LM Studio",
    "codex": "Codex (OpenAI app / CLI)",                      # ~/.codex/config.toml
    "anythingllm": "AnythingLLM Desktop",
    "cursor": "Cursor",
    "gemini_cli": "Gemini CLI",
}
# Clients configured by hand (config_snippet): Hermes Agent (YAML, often in
# WSL, where the Windows Python is started through /mnt/c/…), and clients that
# connect to a URL (the HTTP server). ChatGPT on the web or in its desktop app
# only reaches servers on the public internet, not one on this computer.


def _home() -> str:
    return os.path.expanduser("~")


def state_path() -> str:
    """Where the running HTTP server is recorded (pid, port)."""
    return os.path.join(_home(), ".pyfigures", "mcp_http.json")


def client_config_path(client: str) -> str:
    """The configuration file in which *client* lists its MCP servers."""
    if client == "claude_desktop":
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.join(_home(), "AppData", "Roaming")
            return os.path.join(base, "Claude", "claude_desktop_config.json")
        if sys.platform == "darwin":
            return os.path.join(_home(), "Library", "Application Support", "Claude",
                                "claude_desktop_config.json")
        return os.path.join(_home(), ".config", "Claude", "claude_desktop_config.json")
    if client == "claude_code":
        return os.path.join(_home(), ".claude.json")          # user scope
    if client == "lm_studio":
        return os.path.join(_home(), ".lmstudio", "mcp.json")
    if client == "codex":
        return os.path.join(os.environ.get("CODEX_HOME") or os.path.join(_home(), ".codex"),
                            "config.toml")
    if client == "anythingllm":
        if sys.platform == "win32":
            base = os.environ.get("APPDATA") or os.path.join(_home(), "AppData", "Roaming")
        elif sys.platform == "darwin":
            base = os.path.join(_home(), "Library", "Application Support")
        else:
            base = os.path.join(_home(), ".config")
        return os.path.join(base, "anythingllm-desktop", "storage", "plugins",
                            "anythingllm_mcp_servers.json")
    if client == "cursor":
        return os.path.join(_home(), ".cursor", "mcp.json")
    if client == "gemini_cli":
        return os.path.join(_home(), ".gemini", "settings.json")
    raise ValueError(f"unknown client {client!r}; one of {', '.join(CLIENTS)}")


def _wsl_path(path: str) -> str:
    """C:\\a\\b.exe -> /mnt/c/a/b.exe"""
    return "/mnt/" + path[0].lower() + path[2:].replace("\\", "/")


def server_entry(python: str | None = None) -> dict:
    """The stdio entry a client needs to start the server."""
    return {"command": python or sys.executable, "args": ["-m", "pyfigures.mcp_server"]}


def config_snippet(python: str | None = None, fmt: str = "json") -> str:
    """What to paste into a client's configuration by hand: the ``mcpServers``
    JSON most clients read (fmt="json"), the TOML table of OpenAI's Codex
    (fmt="codex", ~/.codex/config.toml), the YAML of Hermes Agent
    (fmt="hermes", ~/.hermes/config.yaml) or the URL of the HTTP server
    (fmt="url", for clients that connect to a URL)."""
    entry = server_entry(python)
    args = ", ".join(json.dumps(a) for a in entry["args"])
    if fmt == "codex":
        return (f"[mcp_servers.{SERVER_NAME}]\n"
                f"command = {json.dumps(entry['command'])}\n"
                f"args = [{args}]\n")
    if fmt == "hermes":
        command = entry["command"]
        note = ""
        if sys.platform == "win32" and len(command) > 2 and command[1] == ":":
            note = ("# Hermes in WSL starts the Windows Python through /mnt/"
                    f"{command[0].lower()}/…:\n")
        return (f"{note}mcp_servers:\n"
                f"  {SERVER_NAME}:\n"
                f"    command: {json.dumps(_wsl_path(command) if note else command)}\n"
                f"    args: [{args}]\n")
    if fmt == "url":
        return http_url()
    if fmt == "http":
        return http_snippets_text()
    return json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2)


def http_url(port: int | None = None) -> str:
    """The HTTP server's address: the running one, else the one *port* (the
    default port) would give."""
    st = http_status()
    if st["running"] and port in (None, st.get("port")):
        return st["url"]
    return f"http://127.0.0.1:{port or DEFAULT_PORT}/mcp"


def http_snippets(url: str | None = None) -> list[dict]:
    """What to paste into each kind of client to reach the HTTP server at
    *url*: [{title, text, where}]. The plain address comes first (any client
    that asks for a server URL)."""
    url = url or http_url()
    def as_json(entry):
        return json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2)
    return [
        {"title": "Address", "text": url,
         "where": "Any client that asks for an MCP server URL (streamable HTTP)."},
        {"title": "Claude Code", "text": f"claude mcp add --transport http {SERVER_NAME} {url}",
         "where": "Run in a terminal."},
        {"title": "JSON with a URL", "text": as_json({"url": url}),
         "where": "Cursor (~/.cursor/mcp.json), LM Studio (~/.lmstudio/mcp.json) and most "
                  "clients that read an 'mcpServers' JSON."},
        {"title": "AnythingLLM", "text": as_json({"type": "streamable", "url": url}),
         "where": "anythingllm_mcp_servers.json in AnythingLLM's storage/plugins folder."},
        {"title": "Gemini CLI", "text": as_json({"httpUrl": url}),
         "where": "~/.gemini/settings.json"},
        {"title": "Codex", "text": f"[mcp_servers.{SERVER_NAME}]\nurl = {json.dumps(url)}\n",
         "where": "~/.codex/config.toml (OpenAI's Codex app and CLI)."},
        {"title": "Hermes Agent", "text": f"mcp_servers:\n  {SERVER_NAME}:\n    url: {json.dumps(url)}\n",
         "where": "~/.hermes/config.yaml. From WSL, 127.0.0.1 reaches Windows only with "
                  "WSL's mirrored networking."},
        {"title": "Clients that only start programs",
         "text": as_json({"command": "npx", "args": ["-y", "mcp-remote", url]}),
         "where": "A bridge for clients without URL support (needs Node.js)."},
    ]


def http_snippets_text(url: str | None = None) -> str:
    """http_snippets as plain text (command line, MCP tool)."""
    blocks = []
    for s in http_snippets(url):
        blocks.append(f"── {s['title']} — {s['where']}\n{s['text'].rstrip()}")
    return "\n\n".join(blocks)


# ── registration with MCP clients ─────────────────────────────────────

def _read_json(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        return {}
    if not text.strip():
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object")
    return data


def backup_dir() -> str:
    return os.path.join(_home(), ".pyfigures", "backups")


def _write_text(path: str, text: str, parse) -> str | None:
    """Write *text* to *path* atomically after a timestamped backup of the old
    file (returned). *parse* must read the new text back, or nothing is
    written."""
    parse(text)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    backup = None
    if os.path.isfile(path):
        os.makedirs(backup_dir(), exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = os.path.join(backup_dir(), f"{os.path.basename(path)}.{stamp}.bak")
        n = 1
        while os.path.exists(backup):      # Windows' clock: same stamp for quick edits
            n += 1
            backup = os.path.join(backup_dir(), f"{os.path.basename(path)}.{stamp}-{n}.bak")
        shutil.copyfile(path, backup)
    tmp = path + f".pyfigures_tmp_{os.getpid()}"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)
    return backup


def _write_json(path: str, data: dict) -> str | None:
    return _write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", json.loads)


# Codex (the app and the CLI) lists its servers as TOML tables in
# ~/.codex/config.toml. The file is edited as text, so its comments and
# layout are kept: only the [mcp_servers.pyfigures] table (and its
# sub-tables, e.g. .env) is added or removed.

def _toml_load(text: str) -> dict:
    try:
        import tomllib
    except ImportError:                      # Python 3.10
        try:
            import tomli as tomllib
        except ImportError:
            raise ValueError("reading TOML needs Python 3.11 or the 'tomli' package") from None
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"not valid TOML: {e}") from None


def _read_toml(path: str) -> tuple[str, dict]:
    try:
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
    except FileNotFoundError:
        return "", {}
    return text, _toml_load(text)


def _without_toml_table(text: str, table: str) -> str:
    out = []
    skipping = False
    for line in text.splitlines(keepends=True):
        s = line.strip()
        if s.startswith("["):
            name = s.strip("[]").strip()
            skipping = name == table or name.startswith(table + ".")
        if not skipping:
            out.append(line)
    return "".join(out).rstrip() + ("\n" if out else "")


def _commander_stash() -> dict:
    """Servers MCP Commander switched off for LM Studio (it moves them to a
    file of its own, LM Studio having no 'disabled' list)."""
    path = os.path.join(_home(), ".claude", "mcp_commander_local_disabled.json")
    try:
        data = _read_json(path)
    except (ValueError, OSError):
        return {}
    stash = data.get("lmstudio")
    return stash if isinstance(stash, dict) else {}


def registration(client: str) -> dict:
    """{client, name, path, exists, registered, disabled, entry, error}."""
    path = client_config_path(client)
    info = {"client": client, "name": CLIENTS[client], "path": path,
            "exists": os.path.isfile(path), "registered": False, "disabled": False,
            "entry": None, "error": None}
    try:
        if client == "codex":
            data = _read_toml(path)[1]
        else:
            data = _read_json(path)
    except (ValueError, OSError) as e:
        info["error"] = f"{type(e).__name__}: {e}"
        return info
    if client == "codex":
        entry = (data.get("mcp_servers") or {}).get(SERVER_NAME)
        if entry is not None:
            info["entry"] = entry
            info["disabled" if entry.get("enabled") is False else "registered"] = True
        return info
    entry = (data.get("mcpServers") or {}).get(SERVER_NAME)
    if entry is not None:
        info["registered"] = True
        info["entry"] = entry
    # switched off (Claude's own switch, MCP Commander): the entry is moved aside
    elif SERVER_NAME in (data.get("_mcpServersDisabled") or {}):
        info["disabled"] = True
        info["entry"] = data["_mcpServersDisabled"][SERVER_NAME]
    elif client == "lm_studio" and SERVER_NAME in _commander_stash():
        info["disabled"] = True
        info["entry"] = _commander_stash()[SERVER_NAME]
    return info


def registrations() -> list[dict]:
    return [registration(c) for c in CLIENTS]


def register(client: str, python: str | None = None) -> str:
    """Add the server to *client*'s configuration (stdio, started on demand by
    the client). Every other entry of the file is kept."""
    path = client_config_path(client)
    if client == "codex":
        return _register_codex(path, python)
    try:
        data = _read_json(path)
    except (ValueError, OSError) as e:
        return f"ERROR: cannot read {path} ({e}); nothing was changed."
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        return f"ERROR: 'mcpServers' in {path} is not an object; nothing was changed."
    entry = server_entry(python)
    if client == "claude_code":
        entry = {"type": "stdio", **entry, "env": {}}
    if servers.get(SERVER_NAME) == entry:
        return f"{CLIENTS[client]} already starts the PyFigures MCP server ({path})."
    servers[SERVER_NAME] = entry
    disabled = data.get("_mcpServersDisabled")
    if isinstance(disabled, dict):
        disabled.pop(SERVER_NAME, None)
    backup = _write_json(path, data)
    return (f"Registered with {CLIENTS[client]} ({path}): it starts the server when it needs "
            f"the tools. Restart {CLIENTS[client]} to load it."
            + (f" Previous file kept as {backup}." if backup else ""))


def _register_codex(path: str, python: str | None) -> str:
    try:
        text, data = _read_toml(path)
    except (ValueError, OSError) as e:
        return f"ERROR: cannot read {path} ({e}); nothing was changed."
    entry = server_entry(python)
    current = (data.get("mcp_servers") or {}).get(SERVER_NAME)
    if current is not None and {k: current.get(k) for k in entry} == entry \
            and current.get("enabled", True):
        return f"{CLIENTS['codex']} already starts the PyFigures MCP server ({path})."
    text = _without_toml_table(text, f"mcp_servers.{SERVER_NAME}")
    text = (text + "\n" if text else "") + config_snippet(python, fmt="codex")
    backup = _write_text(path, text, _toml_load)
    return (f"Registered with {CLIENTS['codex']} ({path}): it starts the server when it needs "
            f"the tools. Restart Codex to load it."
            + (f" Previous file kept as {backup}." if backup else ""))


def unregister(client: str) -> str:
    path = client_config_path(client)
    if client == "codex":
        try:
            text, data = _read_toml(path)
        except (ValueError, OSError) as e:
            return f"ERROR: cannot read {path} ({e}); nothing was changed."
        if SERVER_NAME not in (data.get("mcp_servers") or {}):
            return f"{CLIENTS[client]} does not list the PyFigures MCP server ({path})."
        backup = _write_text(path, _without_toml_table(text, f"mcp_servers.{SERVER_NAME}"),
                             _toml_load)
        return (f"Removed from {CLIENTS[client]} ({path}). Restart Codex to apply."
                + (f" Previous file kept as {backup}." if backup else ""))
    try:
        data = _read_json(path)
    except (ValueError, OSError) as e:
        return f"ERROR: cannot read {path} ({e}); nothing was changed."
    found = False
    for key in ("mcpServers", "_mcpServersDisabled"):
        servers = data.get(key)
        if isinstance(servers, dict) and SERVER_NAME in servers:
            del servers[SERVER_NAME]
            found = True
    if not found:
        if client == "lm_studio" and SERVER_NAME in _commander_stash():
            return ("LM Studio's entry was switched off with MCP Commander, which keeps it; "
                    "remove it there.")
        return f"{CLIENTS[client]} does not list the PyFigures MCP server ({path})."
    backup = _write_json(path, data)
    return (f"Removed from {CLIENTS[client]} ({path}). Restart {CLIENTS[client]} to apply."
            + (f" Previous file kept as {backup}." if backup else ""))


# ── the HTTP server ───────────────────────────────────────────────────

def _pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except ImportError:
        pass
    except Exception:
        return False
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                             capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return f'"{pid}"' in out.stdout
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _read_state() -> dict:
    try:
        with open(state_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def http_status() -> dict:
    """{running, pid, host, port, url, started}; a stale record is removed."""
    st = _read_state()
    pid = st.get("pid")
    if pid and _pid_alive(pid):
        st["running"] = True
        st["listening"] = _port_open(st.get("host", "127.0.0.1"), st.get("port", DEFAULT_PORT))
        return st
    if st:
        try:
            os.remove(state_path())
        except OSError:
            pass
    return {"running": False}


def kill_tree(pid: int, timeout: float = 10) -> None:
    """Stop *pid* and every process it started."""
    try:
        import psutil
        try:
            parent = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        procs = parent.children(recursive=True) + [parent]
        for p in procs:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(procs, timeout=timeout)
        return
    except ImportError:
        pass
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                       stdin=subprocess.DEVNULL)
    else:
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            pass
    end = time.time() + timeout
    while _pid_alive(pid) and time.time() < end:
        time.sleep(0.1)


def start_http(port: int = DEFAULT_PORT, host: str = "127.0.0.1", python: str | None = None,
               wait: float = 60, log_path: str | None = None) -> str:
    """Run the server over HTTP in the background (until stop_http)."""
    st = http_status()
    if st["running"]:
        return f"The PyFigures MCP server is already running at {st['url']} (pid {st['pid']})."
    if _port_open(host, port):
        return f"ERROR: port {port} is already in use; choose another port."
    os.makedirs(os.path.dirname(state_path()), exist_ok=True)
    log_path = log_path or os.path.join(os.path.dirname(state_path()), "mcp_http.log")
    cmd = [python or sys.executable, "-m", "pyfigures.mcp_server",
           "--transport", "http", "--host", host, "--port", str(port)]
    env = dict(os.environ)
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = os.pathsep.join(p for p in [pkg_root, env.get("PYTHONPATH", "")] if p)
    kw = {}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kw["start_new_session"] = True
    log = open(log_path, "w", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                env=env, **kw)
    finally:
        log.close()
    url = f"http://{host}:{port}/mcp"
    state = {"pid": proc.pid, "host": host, "port": port, "url": url,
             "started": datetime.datetime.now().isoformat(timespec="seconds"),
             "log": log_path}
    with open(state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
    end = time.time() + wait
    while time.time() < end:
        if proc.poll() is not None:
            try:
                os.remove(state_path())
            except OSError:
                pass
            with open(log_path, encoding="utf-8", errors="replace") as f:
                tail = f.read()[-800:]
            return f"ERROR: the server stopped at once (exit code {proc.returncode}):\n{tail}"
        if _port_open(host, port):
            return f"The PyFigures MCP server is running at {url} (pid {proc.pid})."
        time.sleep(0.2)
    return (f"WARNING: the server was started (pid {proc.pid}) but does not answer at {url} "
            f"yet; see {log_path}.")


def stop_http() -> str:
    st = http_status()
    if not st["running"]:
        return "The PyFigures MCP HTTP server is not running."
    kill_tree(st["pid"])
    try:
        os.remove(state_path())
    except OSError:
        pass
    if _pid_alive(st["pid"]):
        return f"ERROR: the server (pid {st['pid']}) could not be stopped."
    return f"Stopped the PyFigures MCP server (pid {st['pid']}) and the processes it started."


def describe() -> str:
    """Plain-text status: registrations and the HTTP server."""
    lines = ["Registered MCP clients (they start the server themselves when needed):"]
    for r in registrations():
        if r["error"]:
            state = "configuration unreadable: " + r["error"]
        elif r["registered"]:
            state = "registered"
        elif r["disabled"]:
            state = "registered but switched off"
        else:
            state = "not registered"
        lines.append(f"  {r['name']}: {state} ({r['path']})")
    st = http_status()
    if st["running"]:
        lines.append(f"HTTP server: running at {st['url']} (pid {st['pid']}, since {st['started']})"
                     + ("" if st.get("listening") else " — not answering"))
        lines.append("")
        lines.append("What to paste into a client to use it:")
        lines.append(http_snippets_text(st["url"]))
    else:
        lines.append("HTTP server: not running")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m pyfigures.mcp_control",
                                 description="Start, stop and register the PyFigures MCP server.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status", help="registrations and HTTP server state")
    p = sub.add_parser("start", help="run the HTTP server in the background")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="127.0.0.1")
    sub.add_parser("stop", help="stop the HTTP server and its processes")
    for name in ("register", "unregister"):
        p = sub.add_parser(name, help=f"{name} the server with an MCP client")
        p.add_argument("client", choices=list(CLIENTS))
    p = sub.add_parser("snippet", help="print what to paste into a client configuration")
    p.add_argument("--format", choices=["json", "codex", "hermes", "url", "http"], default="json",
                   help="http: everything to paste for the HTTP server, client by client")
    a = ap.parse_args(argv)
    if a.cmd == "start":
        res = start_http(a.port, a.host)
        if http_status()["running"]:
            res += "\n\nWhat to paste into a client to use it:\n" + http_snippets_text()
    elif a.cmd == "stop":
        res = stop_http()
    elif a.cmd == "register":
        res = register(a.client)
    elif a.cmd == "unregister":
        res = unregister(a.client)
    elif a.cmd == "snippet":
        res = config_snippet(fmt=a.format)
    else:
        res = describe()
    print(res)
    return 1 if res.startswith("ERROR") else 0


if __name__ == "__main__":
    sys.exit(main())
