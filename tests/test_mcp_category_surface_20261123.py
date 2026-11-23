"""`python -m pyfigures.mcp_server --tools categories`: the file server lists three tools
(categories, search, run) instead of all of them with their full descriptions (~85k
tokens for 210 tools, user 2026-11-23: "grouping them into categories would cut that").
Every operation stays reachable through use_pyfigures_tool, over the real stdio transport.
"""
from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from test_mcp_stdio_protocol import _sample_image, _server_params  # noqa: E402


def _params(cwd, mode):
    p = _server_params(cwd)
    return p.model_copy(update={"args": p.args + ["--tools", mode]})


async def _listing(cwd, mode):
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    async with stdio_client(_params(cwd, mode)) as (read, write):
        async with ClientSession(read, write) as session:
            init = await asyncio.wait_for(session.initialize(), 60)
            tools = (await session.list_tools()).tools
            return init.instructions or "", tools


async def _run(cwd, calls):
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    out = []
    async with stdio_client(_params(cwd, "categories")) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 60)
            for name, args in calls:
                out.append(await asyncio.wait_for(session.call_tool(name, args), 120))
    return out


def _size(instructions, tools):
    return len(instructions) + sum(len(json.dumps(t.model_dump(mode="json"))) for t in tools)


def _text(res):
    return " ".join(getattr(c, "text", "") or "" for c in res.content)


def test_the_category_listing_is_small_and_the_full_one_unchanged(tmp_path):
    instr, tools = asyncio.run(_listing(tmp_path, "categories"))
    assert sorted(t.name for t in tools) == ["find_pyfigures_tools", "list_pyfigures_categories",
                                             "use_pyfigures_tool"]
    full_instr, full = asyncio.run(_listing(tmp_path, "all"))
    assert len(full) > 150
    small, big = _size(instr, tools), _size(full_instr, full)
    assert small < 4000 and small * 50 < big, (small, big)


def test_search_then_run_reaches_every_operation(tmp_path):
    img = _sample_image(tmp_path)
    pyf = str(tmp_path / "fig.pyf")
    use = "use_pyfigures_tool"
    res = asyncio.run(_run(tmp_path, [
        ("list_pyfigures_categories", {}),
        ("find_pyfigures_tools", {"query": "add a scale bar to one image"}),
        ("find_pyfigures_tools", {"query": "set_scale_bar_all"}),
        (use, {"tool_name": "create_figure", "arguments": {"pyf_path": pyf}}),
        (use, {"tool_name": "add_image", "arguments": {"pyf_path": pyf, "group_path": [], "filename": str(img)}}),
        (use, {"tool_name": "describe_figure", "arguments": {"pyf_path": pyf}}),
        (use, {"tool_name": "render_preview", "arguments": {"pyf_path": pyf}}),
        (use, {"tool_name": "set_scale_barr", "arguments": {}}),
        (use, {"tool_name": "set_scale_bar", "arguments": {"pyf_path": pyf}}),
    ]))
    cats = json.loads(_text(res[0]))
    assert "scale_bars" in cats and "native_gui" not in cats       # live-GUI-only areas are not offered
    assert sum(c["operations"] for c in cats.values()) > 150
    found = json.loads(_text(res[1]))
    assert "set_scale_bar" in [t["name"] for t in found["tools"]]
    assert "pyf_path" in found["tools"][0]["arguments_schema"]["properties"]
    assert json.loads(_text(res[2]))["tools"][0]["name"] == "set_scale_bar_all"   # named exactly: first
    assert not res[3].isError and not res[4].isError
    assert "img.png" in _text(res[5])
    assert any(getattr(c, "type", "") == "image" for c in res[6].content)          # images pass through
    assert res[7].isError and "set_scale_bar" in _text(res[7])                    # a typo names the close ones
    assert res[8].isError and "image_index" in _text(res[8])                      # a missing argument: the schema
    assert all("Nothing was changed" in _text(r) for r in res[7:])
