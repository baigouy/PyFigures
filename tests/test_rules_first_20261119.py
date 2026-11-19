"""2026-11-19 (user): a trick so the chat model gets a topic's rules even when it runs
an operation without searching first. Each topic names its operations: a search that
finds one returns its rules; an edit made before the model had them is held once, its
rules returned, and the same call sent again runs."""
import asyncio
import json


def _server():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    sent = []

    def send(*args, **kwargs):
        sent.append(args)
        raise ValueError("no GUI in this test")          # the edit itself is not what is tested
    return build_server(live_mcp.mcp, send), sent


def _call(server, name, arguments):
    async def go():
        try:
            result = await server.call_tool(name, arguments)
        except Exception as e:                             # the edit reached the (absent) GUI
            return {"ran": str(e)}
        blocks = result[0] if isinstance(result, tuple) else result
        text = "".join(getattr(b, "text", "") for b in blocks)
        try:
            return json.loads(text)
        except ValueError:
            return {"ran": text}
    return asyncio.run(go())


def test_an_edit_without_its_rules_is_held_once():
    server, _ = _server()
    first = _call(server, "use_pyfigures_tool", {"tool_name": "set_scale_bar_all", "arguments": {}})
    assert first.get("not_run") is True and first["rules"].startswith("SCALE BARS:")
    assert "send exactly the same call again" in first["next_step"]
    again = _call(server, "use_pyfigures_tool", {"tool_name": "set_scale_bar_all", "arguments": {}})
    assert "not_run" not in again


def test_a_search_gives_the_rules_of_the_operations_it_finds():
    server, _ = _server()
    found = _call(server, "find_pyfigures_tools", {"query": "exchange panels q and o"})
    assert "SWAPS:" in found["guidance"]
    edit = _call(server, "use_pyfigures_tool", {"tool_name": "swap_live_panels",
                                                 "arguments": {"first": "a", "second": "b"}})
    assert "not_run" not in edit                         # the rules were given by the search


def test_reads_and_unrelated_edits_are_never_held():
    server, _ = _server()
    for name, args in (("list_luts", {"query": "green"}), ("transform_image", {"panel_ref": "a", "rotation": 5})):
        out = _call(server, "use_pyfigures_tool", {"tool_name": name, "arguments": args})
        assert "not_run" not in out, name


def test_the_panel_background_is_its_own_topic():
    server, _ = _server()
    out = _call(server, "use_pyfigures_tool", {"tool_name": "set_image_property",
                                                "arguments": {"panel_ref": "g", "property_name": "fill_color",
                                                              "value": "0"}})
    assert out.get("not_run") and out["rules"].startswith("BACKGROUND:")
    other = _call(server, "use_pyfigures_tool", {"tool_name": "set_image_property",
                                                  "arguments": {"panel_ref": "g", "property_name": "opacity",
                                                                "value": "0.5"}})
    assert "not_run" not in other
