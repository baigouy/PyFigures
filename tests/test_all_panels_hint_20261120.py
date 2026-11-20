"""Replay 2026-11-20: "make all bars about 10-15 percent of the image width" — Qwen 27B sent
set_scale_bar with no panel four times; the error only said to supply panel_ref. It now
names the tool that does every panel in one call."""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_a_panel_tool_without_a_panel_names_the_all_panels_tool():
    from mcp.server.fastmcp import FastMCP
    from pyfigures.assistant.original_registry import register_all
    server = FastMCP("test")
    register_all(server, lambda *a, **k: None)
    tools = server._tool_manager._tools
    with pytest.raises(ValueError, match="set_scale_bar_all"):
        tools["set_scale_bar"].fn(bar_width_in_units=40, unit="um")
    with pytest.raises(ValueError) as e:                     # no *_all sibling: no hint
        tools["remove_scale_bar"].fn()
    assert "_all" not in str(e.value)
