#!/usr/bin/env python3
"""PyFigures MCP server — tools for reading and editing .pyf figure files.

No Qt / GUI dependency: all tools operate on the XML directly.

Run standalone (stdio transport, used by Claude Code):
    python -m pyfigures.mcp_server

Register with Claude Code — add to ~/.claude/settings.json:
    {
      "mcpServers": {
        "pyfigures": {
          "command": "python",
          "args": ["-m", "pyfigures.mcp_server"]
        }
      }
    }
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
from .mcp_tools import stacks, upkeep

_TOOL_MODULES = (app, core, structure, content, annotations, overlays, workflow, qc, export, poster,
                 stacks, upkeep,)
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


if __name__ == "__main__":
    run_stdio()
