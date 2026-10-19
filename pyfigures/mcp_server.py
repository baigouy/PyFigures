#!/usr/bin/env python3
"""PyFigures MCP server — tools for reading and editing .pyf figure files.

No Qt / GUI dependency: all tools operate on the XML directly.

Run standalone (stdio transport, used by Claude Code):
    python -m pyfigures.mcp_server

Over HTTP (clients that connect to http://127.0.0.1:8765/mcp):
    python -m pyfigures.mcp_server --transport http --port 8765

Register it with Claude Desktop / Claude Code / LM Studio, or start and stop
the HTTP server: GUI Tools > MCP server…, or python -m pyfigures.mcp_control.
"""

# The tools live in the pyfigures.mcp_tools package, one module per area:
#   app         FastMCP instance + tool decorator
#   core        shared helpers (XML, atomic save + layout recompute, builders)
#   structure   figure / group / image / annotation / size / script tools
#   content     channel merges, data plots, transforms, LUTs
#   annotations ROI shapes, significance brackets, remap / clone / properties
#   overlays    captions, scale bars, insets + callouts, label rows
#   workflow    folder-to-figure, draft figure, auto-configure
#   qc          resolution, scale consistency, fonts, journal compliance
#   export      render / export / audit / review / library / diff / ledger
#   poster      poster designer
#   stacks      stack montages, channel splits, kymographs, orthogonal views
#   upkeep      changed-source detection, copy style between figures, alt text
# Importing a module registers its tools on the shared server. Every name is
# re-exported here so `from pyfigures.mcp_server import <anything>` keeps working.
# NB: monkeypatch helpers in the module that DEFINES them (e.g.
# pyfigures.mcp_tools.core), not here — this module only holds re-exports.

from __future__ import annotations

import os
import sys

from .mcp_tools import app, core, structure, content, annotations, overlays, workflow, qc, export, poster
from .mcp_tools import stacks, upkeep, guidance, journal

_TOOL_MODULES = (app, core, structure, content, annotations, overlays, workflow, qc, export, poster,
                 stacks, upkeep, guidance, journal,)
for _m in _TOOL_MODULES:
    globals().update({_k: _v for _k, _v in vars(_m).items()
                      if not (_k.startswith("__") and _k.endswith("__"))})
del _m


def _private_stdio():
    """Move the JSON-RPC pipes off the standard handles.

    Returns (stdin, stdout) text files on private, non-inheritable copies of
    the real stdin/stdout. Afterwards the standard stdin is the null device and
    the standard stdout is stderr, so a child process (renderer, ffmpeg, LaTeX,
    a library helper) never inherits the protocol pipe — on Windows a child
    holding the stdin pipe blocks while the server's reader waits on it, and
    the tool call hangs — and a stray print() can no longer corrupt the
    protocol stream.
    """
    import io
    sys.stdout.flush()
    fd_in = os.dup(0)
    fd_out = os.dup(1)
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    os.dup2(2, 1)
    proto_in = io.TextIOWrapper(io.FileIO(fd_in, "rb"), encoding="utf-8", newline="")
    proto_out = io.TextIOWrapper(io.FileIO(fd_out, "wb"), encoding="utf-8", newline="",
                                 write_through=True)
    sys.stdin = open(os.devnull, "r", encoding="utf-8")
    sys.stdout = sys.stderr
    return proto_in, proto_out


async def _run_stdio_async(server):
    import anyio
    from mcp.server.stdio import stdio_server
    proto_in, proto_out = _private_stdio()
    async with stdio_server(anyio.wrap_file(proto_in), anyio.wrap_file(proto_out)) as (read, write):
        await server._mcp_server.run(read, write, server._mcp_server.create_initialization_options())


def run_stdio(server=None):
    """Serve the PyFigures tools over stdio (what MCP clients launch)."""
    import anyio
    anyio.run(_run_stdio_async, server or mcp)


def _kill_children():
    """Stop every process this server started (and theirs)."""
    try:
        import psutil
    except ImportError:
        return
    try:
        procs = psutil.Process().children(recursive=True)
    except psutil.Error:
        return
    for p in procs:
        try:
            p.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(procs, timeout=5)


def _children_die_with_me_posix():
    """macOS / Linux: when the client stops the server (MCP clients close
    stdin, then send SIGTERM) or the HTTP server is stopped, the processes it
    started are stopped too. A SIGKILL cannot be caught; stop_http kills the
    whole tree itself."""
    import atexit
    import signal

    def on_signal(signum, frame):
        _kill_children()
        os._exit(128 + signum)

    for sig in (signal.SIGTERM, signal.SIGHUP):
        try:
            signal.signal(sig, on_signal)
        except (ValueError, OSError):          # not the main thread
            return None
    atexit.register(_kill_children)
    return "posix"


def _children_die_with_me():
    """Windows: put the server in a job object closed (and its processes
    killed) when the server ends, so a renderer, LaTeX or ffmpeg started by a
    tool never outlives a server that its client killed. macOS / Linux: the
    same on SIGTERM / SIGHUP / exit (_children_die_with_me_posix). If the
    system refuses, nothing is done."""
    if sys.platform != "win32":
        return _children_die_with_me_posix()
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _IoCounters(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in
                    ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                     "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BasicLimits),
                    ("IoInfo", _IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _ExtendedLimits()
    info.BasicLimitInformation.LimitFlags = 0x2000 | 0x800   # KILL_ON_JOB_CLOSE | BREAKAWAY_OK
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return None
    if not k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()):
        return None
    return job          # kept open for the life of the process


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m pyfigures.mcp_server",
                                 description="The PyFigures MCP server. MCP clients start it "
                                             "over stdio; --transport http serves it at "
                                             "http://HOST:PORT/mcp (see pyfigures.mcp_control).")
    ap.add_argument("--transport", choices=["stdio", "http", "sse"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    global _JOB
    _JOB = _children_die_with_me()
    if a.transport == "stdio":
        run_stdio()
        return
    mcp.settings.host = a.host
    mcp.settings.port = a.port
    mcp.run(transport="streamable-http" if a.transport == "http" else "sse")


_JOB = None

if __name__ == "__main__":
    main()
