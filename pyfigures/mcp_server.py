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

from .mcp_tools import app, core, structure, content, annotations, overlays, workflow, qc, export, poster
from .mcp_tools import stacks, upkeep

_TOOL_MODULES = (app, core, structure, content, annotations, overlays, workflow, qc, export, poster,
                 stacks, upkeep,)
for _m in _TOOL_MODULES:
    globals().update({_k: _v for _k, _v in vars(_m).items()
                      if not (_k.startswith("__") and _k.endswith("__"))})
del _m

if __name__ == "__main__":
    mcp.run()
