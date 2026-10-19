"""PyFigures MCP tools — "Show me how": guide the user through an operation in
the running GUI instead of doing it (registry + mailbox: pyfigures/guides.py).

Three modes, kept distinct:
* do it      — the ordinary editing tools (each guide names its tool: do_it_tool);
* show me how — show_me_how opens highlighted, closable steps in the open
  PyFigures window; the user clicks. It never edits the figure;
* explain    — explain_how returns the same authored steps as text.
"""
from __future__ import annotations

import json

from .app import mcp
from .. import guides as _guides


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


@mcp.tool()
def list_how_to_guides() -> str:
    """List the "show me how" guides (id, title, summary, and the tool that does
    the same operation directly). Use show_me_how(<id>) when the user wants to
    learn / do it themselves in the PyFigures window, explain_how for text only.
    Nothing is executed."""
    return _dump(_guides.list_guides())


@mcp.tool()
def show_me_how(operation: str, pyf_path: str = "") -> str:
    """Open a short guide in the user's open PyFigures window that highlights the
    real menus and controls for one operation, in a floating closable bubble.
    The USER performs the clicks; this tool does not change the figure
    (operation_executed is always false).

    *operation*: a guide id from list_how_to_guides (e.g. "split_channels",
    "crop_image", "set_lut", "zoom_inset", "add_scale_bars") or the user's words
    ("how do I crop?"); an ambiguous request returns candidates instead.
    *pyf_path*: when several PyFigures windows are open, the one showing this
    figure gets the guide.

    status: guidance_shown (visible now) | completed (the user did it) |
    gui_unavailable (no window open: steps_as_text is returned; tell the user
    to open PyFigures, never pretend the guide is on screen) | target_unavailable
    | unknown_operation | ambiguous. Follow with guidance_status to see whether
    the user finished."""
    return _dump(_guides.show(operation, pyf_path or None))


@mcp.tool()
def guidance_status(pyf_path: str = "") -> str:
    """The open guide's state in the PyFigures window: guidance_shown (with the
    current step), completed (the user's result was detected), cancelled,
    guidance_closed or no_guide. Read-only."""
    return _dump(_guides.status(pyf_path or None))


@mcp.tool()
def close_guidance(pyf_path: str = "") -> str:
    """Close the guide in the PyFigures window. The figure is not changed."""
    return _dump(_guides.close(pyf_path or None))


@mcp.tool()
def explain_how(operation: str) -> str:
    """Explain mode: the authored steps of a guide as text (menus to use, what
    to set), without needing the GUI. Also names do_it_tool, the MCP tool that
    performs the operation directly."""
    return _dump(_guides.explain(operation))
