"""2026-11-19 (user): "expose preview_panel directly maybe because seeing could solve a lot
of issues". Behind use_pyfigures_tool, Qwen 27B looked at the whole figure (each panel
small) 92 times and at one panel 25 times in a replay; preview_figure was offered
directly, preview_panel was not."""
import asyncio
import json


def _server(calls):
    from mcp.server.fastmcp import FastMCP
    from pyfigures.assistant.categorized_mcp import build_server
    full = FastMCP("fake")

    @full.tool()
    def preview_panel(panel_ref: str, brighten: bool = True, region: list[float] | None = None,
                      view: str = 'source', letters: bool = True, texts: bool = True, scale_bar: bool = True,
                      rois: bool = True, insets: bool = True) -> list:
        calls.append(dict(panel_ref=panel_ref, view=view, region=region, brighten=brighten, letters=letters))
        return ["described"]

    return build_server(full, lambda *a, **k: {})


def test_preview_panel_is_offered_directly_beside_preview_figure():
    server = _server([])
    tools = server._tool_manager._tools
    assert "preview_panel" in tools and "preview_figure" in tools
    assert len(tools) <= 24                     # the sidecar searches past 24 direct tools
    schema = tools["preview_panel"].parameters["properties"]
    assert set(schema) == {"panel_ref", "view", "region", "brighten"}
    # the first message stays small: one short tool
    size = len(tools["preview_panel"].description) + len(json.dumps(tools["preview_panel"].parameters))
    assert size < 1200, size


def test_the_direct_tool_and_the_wrapped_one_reach_the_same_preview():
    calls = []
    server = _server(calls)
    tools = server._tool_manager._tools
    tools["preview_panel"].fn(panel_ref="b", view="figure", region=[0, 0, 10, 10])
    assert calls[-1] == dict(panel_ref="b", view="figure", region=[0, 0, 10, 10], brighten=True, letters=True)
    run = tools["use_pyfigures_tool"].fn       # every option is still there through the dispatcher
    asyncio.run(run(tool_name="preview_panel", arguments={"panel_ref": "c", "letters": False}))
    assert calls[-1]["panel_ref"] == "c" and calls[-1]["letters"] is False


def test_no_direct_tool_when_the_session_has_no_panel_preview():
    from mcp.server.fastmcp import FastMCP
    from pyfigures.assistant.categorized_mcp import build_server
    server = build_server(FastMCP("empty"), lambda *a, **k: {})
    assert "preview_panel" not in server._tool_manager._tools
