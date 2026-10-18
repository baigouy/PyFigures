"""Text arguments reach the tools as text over MCP.

FastMCP parses a string argument as JSON unless the parameter is annotated
exactly ``str``: a JSON recipe given as ``recipe_text`` (``str | None``) came
in as a dict and was refused, and a text "null" turned into None."""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _call(name, **args):
    try:
        res = asyncio.run(M.mcp.call_tool(name, args))
    except Exception as e:
        return f"ERROR: {e}"
    content = res[0] if isinstance(res, tuple) else res
    return "\n".join(getattr(c, "text", "") for c in content)


def test_json_recipe_text_is_built(tmp_path, qapp):
    from PIL import Image
    Image.new("L", (64, 48), 120).save(tmp_path / "a.png")
    text = json.dumps({"output": "built.pyf", "rows": [["a.png"]]})
    res = _call("build_figure_from_recipe", recipe_path=str(tmp_path / "r.json"), recipe_text=text)
    assert not res.startswith("ERROR"), res
    assert (tmp_path / "built.pyf").is_file()


def test_text_that_looks_like_json_stays_text(tmp_path, qapp):
    pyf = tmp_path / "f.pyf"
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    for caption in ("null", '{"a": 1}', "[1, 2]"):
        assert not _call("set_figure_caption", pyf_path=str(pyf), caption=caption).startswith("ERROR")
        assert json.loads(_call("get_figure_caption", pyf_path=str(pyf)))["caption"] == caption


def test_lists_given_as_json_text_are_still_parsed(tmp_path, qapp):
    """What the pre-parsing is for: a client sending a list as JSON text."""
    from PIL import Image
    pyf = tmp_path / "f.pyf"
    Image.new("L", (64, 48), 120).save(tmp_path / "a.png")
    _call("create_figure", pyf_path=str(pyf), num_groups=1)
    res = _call("add_image", pyf_path=str(pyf), group_path="[0]", filename=str(tmp_path / "a.png"))
    assert not res.startswith("ERROR"), res
