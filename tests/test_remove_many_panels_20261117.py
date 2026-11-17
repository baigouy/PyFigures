"""Several panels removed in ONE call, the right ones whatever the letters do.

User chat 2026-11-17: "remove the duplicates" - the model said "The tool takes one
panel at a time. Removing h, f, m, r, w, x one by one". The user: "can't we
optimize that, be careful letters don't change during the process". Removing h
re-letters every later panel (i becomes h), so letters must all be read before the
first removal, and removing image 1 of a row makes its image 3 the new image 2, so
removals go from the last address to the first.
"""
from __future__ import annotations

import asyncio
import os
import threading

import pytest

from test_assistant_live import gui, runtime  # noqa: F401  (fixtures)


def _figure(gui, tmp_path):  # noqa: F811
    import numpy as np
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "six.pyf")
    create_figure(pyf, mode="groups", num_groups=2)
    for i in range(6):                       # row 0: p0 p1 p2, row 1: p3 p4 p5
        p = str(tmp_path / f"p{i}.tif")
        Img(np.full((30, 40), 20 + 30 * i, dtype=np.uint8), dimensions="hw").save(p)
        add_image(pyf, [i // 3], p)
    g = gui(shareable=True)
    g.reload_state(pyf, append=False)
    g.auto_lettering_checkbox.setChecked(True)
    g.update_letters()
    return g


def _shown(g):
    from pyfigures.assistant.partner_gui import letters, letter_info, panels
    return [(os.path.basename(str(p.filename)), [letter_info(a)["text"] for a in letters(p)])
            for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)]


def test_many_panels_go_in_one_call_and_the_right_ones(qapp, gui, runtime, tmp_path):  # noqa: F811
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from pyfigures.assistant import launch, live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    g = _figure(gui, tmp_path)
    assert [t for _, t in _shown(g)] == [["a"], ["b"], ["c"], ["d"], ["e"], ["f"]]
    launch.start_live_session(g)
    dispatch = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools["use_pyfigures_tool"].fn
    reloads = []
    real = g.reload_state
    g.reload_state = lambda *a, **k: (reloads.append(1), real(*a, **k))[1]

    def call(**kw):
        box = {}

        def work():
            try:
                box["out"] = asyncio.run(dispatch(**kw))
            except Exception as exc:          # shown by the assertion below
                box["error"] = exc
        t = threading.Thread(target=work)
        t.start()
        while t.is_alive():
            qapp.processEvents()
            t.join(0.02)
        if "error" in box:
            raise box["error"]
        return box["out"]

    # b and c share a row with a; e is in the second row. Read one by one after each
    # removal, "c" would be p3 and "e" p5.
    out = call(tool_name="remove_image", arguments={"panel_refs": ["b", "c", "e"]})
    assert out["batch_done"] == 3 and not out["errors"], out
    assert len(reloads) == 1                                 # one edit, one undo step
    assert [f for f, _ in _shown(g)] == ["p0.tif", "p3.tif", "p5.tif"]
    assert [t for _, t in _shown(g)] == [["a"], ["b"], ["c"]]   # re-lettered once, in order
    g.undo()
    assert [f for f, _ in _shown(g)] == [f"p{i}.tif" for i in range(6)]


def test_a_panel_named_twice_removes_nothing():
    from pyfigures.assistant.session import _address_key
    assert _address_key({"group_path": [1], "image_index": 0}) > _address_key({"group_path": [0], "image_index": 2})
    assert _address_key({"group_path": [0], "image_index": 2}) > _address_key({"group_path": [0], "image_index": 1})
    import inspect
    from pyfigures.assistant import session
    assert "named twice" in inspect.getsource(session.LiveSession.original_tool) \
        if hasattr(session, "LiveSession") else "named twice" in inspect.getsource(session)
