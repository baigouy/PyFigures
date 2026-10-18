"""The MCP server answers over the real stdio transport, including tools that
start child processes.

On Windows, a child process that inherits the server's stdin (the JSON-RPC
pipe) can block while the server's reader has a read pending on that pipe:
the call then hangs until the client sends another message. Tools that render
(render_preview, export_figure) or import libraries that spawn helpers timed
out this way in real MCP clients, although the same functions worked when
called directly from Python.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")

SAMPLE = Path(__file__).resolve().parent.parent / "pyfigures" / "samples"


def _server_params(cwd):
    from mcp import StdioServerParameters
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_API"] = "pyqt6"
    env["PYTHONPATH"] = os.pathsep.join(p for p in [str(Path(__file__).resolve().parent.parent),
                                                     env.get("PYTHONPATH", "")] if p)
    return StdioServerParameters(command=sys.executable, args=["-m", "pyfigures.mcp_server"],
                                 env=env, cwd=str(cwd))


async def _session_run(cwd, calls, timeout=120):
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client
    results = []
    async with stdio_client(_server_params(cwd)) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), 60)
            for name, args in calls:
                res = await asyncio.wait_for(session.call_tool(name, args), timeout)
                results.append(res)
    return results


def _text(res):
    return " ".join(getattr(c, "text", "") or "" for c in res.content)


def _sample_image(tmp_path):
    import numpy as np
    from PIL import Image
    path = tmp_path / "img.png"
    arr = (np.arange(64 * 64).reshape(64, 64) % 256).astype("uint8")
    Image.fromarray(arr).save(path)
    return path


def test_child_process_tools_answer_over_stdio(tmp_path):
    img = _sample_image(tmp_path)
    pyf = tmp_path / "fig.pyf"
    out = tmp_path / "fig.png"
    calls = [
        ("create_figure", {"pyf_path": str(pyf)}),
        ("add_image", {"pyf_path": str(pyf), "group_path": [], "filename": str(img)}),
        ("add_image", {"pyf_path": str(pyf), "group_path": [], "filename": str(img)}),
        ("render_preview", {"pyf_path": str(pyf)}),
        ("export_figure", {"pyf_path": str(pyf), "out_path": str(out)}),
        ("describe_figure", {"pyf_path": str(pyf)}),
    ]
    results = asyncio.run(_session_run(tmp_path, calls, timeout=90))
    for res in results[:3]:
        assert not res.isError, _text(res)
    assert any(getattr(c, "type", "") == "image" for c in results[3].content), _text(results[3])
    assert out.exists(), _text(results[4])
    assert "img" in _text(results[5])


def test_refused_request_is_a_protocol_error(tmp_path):
    """A tool that refuses a request ("ERROR: ...") is reported with
    isError=true, so a client cannot take it for a completed edit."""
    pyf = tmp_path / "fig.pyf"
    calls = [
        ("create_figure", {"pyf_path": str(pyf)}),
        ("set_spacing", {"pyf_path": str(pyf), "group_path": [7], "spacing": 3}),
    ]
    results = asyncio.run(_session_run(tmp_path, calls, timeout=90))
    assert not results[0].isError
    assert results[1].isError
    assert "ERROR" in _text(results[1])


def test_stray_output_and_children_stay_off_the_protocol_pipes(tmp_path):
    """After the switch, print() and child processes write to stderr, children
    read stdin from the null device, and only the protocol stream reaches the
    real stdout."""
    import subprocess
    script = tmp_path / "probe.py"
    script.write_text(
        "import subprocess, sys\n"
        "from pyfigures.mcp_server import _private_stdio\n"
        "proto_in, proto_out = _private_stdio()\n"
        "print('stray print')\n"
        "r = subprocess.run([sys.executable, '-c', 'import sys; print(repr(sys.stdin.read()))'],\n"
        "                   timeout=30)\n"
        "proto_out.write('PROTO ' + proto_in.readline())\n",
        encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    proc = subprocess.run([sys.executable, str(script)], input="hello\n", capture_output=True,
                          text=True, env=env, timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "PROTO hello\n"
    assert "stray print" in proc.stderr
    assert "''" in proc.stderr
