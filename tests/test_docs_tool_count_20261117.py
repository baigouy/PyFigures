"""The MCP guide states how many tools the server exposes: keep it true.

2026-11-17: the guide said 175 while the server had 193 (found when checking the
manuscript, which quotes the number).
"""
import asyncio
import os
import re


def test_the_guide_states_the_real_number_of_tools():
    import pyfigures.mcp_server as M
    count = len(asyncio.run(M.mcp.list_tools()))
    guide = os.path.join(os.path.dirname(__file__), "..", "docs", "MCP_SERVER.md")
    with open(guide, encoding="utf-8") as f:
        stated = int(re.search(r"exposes \*\*(\d+) tools\*\*", f.read()).group(1))
    assert stated == count, f"docs/MCP_SERVER.md says {stated} tools, the server has {count}"
