"""Chat finding 2026-11-05 (Mistral Large 4 in the sidecar): "make 4 rows instead
of 3" on 9 images, then "yep 3-2-2-2", used all 32 tool steps and failed:

- arrange_live_images only knew equal rows (columns) -> row_counts=[3, 2, 2, 2],
  also Edit > Arrange all images in rows… ("3-2-2-2"),
- move_image refused (the move changed the letters) and told the model to use
  ungroup_all_images, which the chat refuses as an unrequested removal -> the
  error now points to row_counts,
- tool searches by exact name came back with unrelated how-to guides first, and
  limit=20 was an error -> named tools first without guides, limit clamped.
"""
from __future__ import annotations

import uuid

import numpy as np
import pytest

from test_assistant_live import runtime, gui  # noqa: F401  (fixtures)

NAMES = list("abcdefghi")


def _nine_in_three_rows(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "nine.pyf")
    create_figure(pyf, mode="groups", num_groups=3)
    for i, name in enumerate(NAMES):
        p = str(tmp_path / f"{name}.tif")
        Img((np.full((40, 50), 20 * i + 10)).astype(np.uint8), dimensions="hw").save(p)
        add_image(pyf, [i // 3], p)
    return pyf


def _rows(pyf):
    from pyfigures.mcp_tools.core import _load, layout_rows
    return layout_rows(_load(pyf, resolve=False)[1])


def _expected(counts):
    rows, start = [], 0
    for r, n in enumerate(counts):
        rows.append(f"row {r + 1}: " + " | ".join(f"{x}.tif" for x in NAMES[start:start + n]))
        start += n
    return rows


@pytest.mark.parametrize("value, expected", [
    (3, (3, None)), ("3", (3, None)), ([3, 2, 2, 2], (3, [3, 2, 2, 2])), ("3-2-2-2", (3, [3, 2, 2, 2])),
    ("3,2,2,2", (3, [3, 2, 2, 2])), ("2 3 4", (4, [2, 3, 4])), ([4], (4, None)), ("3x3", (3, [3, 3]))])
def test_images_per_row_are_parsed(value, expected):
    from pyfigures.assistant.existing_tools import parse_row_counts
    assert parse_row_counts(value) == expected


@pytest.mark.parametrize("bad", ["", "three", "3-x", True, 2.5, [3, "2"]])
def test_bad_images_per_row_are_refused(bad):
    from pyfigures.assistant.existing_tools import parse_row_counts
    with pytest.raises(ValueError):
        parse_row_counts(bad)


def test_uneven_rows_keep_reading_order_on_a_file(tmp_path):
    from pyfigures.assistant.existing_tools import arrange_rows
    pyf = _nine_in_three_rows(tmp_path)
    assert _rows(pyf) == _expected([3, 3, 3])
    result = arrange_rows(pyf, 4, 1200, 3, [3, 2, 2, 2])
    assert result["images_per_row"] == [3, 2, 2, 2] and result["rows"] == 4
    assert _rows(pyf) == _expected([3, 2, 2, 2])
    arrange_rows(pyf, 2, 1200, 3)                                 # equal rows still work
    assert _rows(pyf) == _expected([2, 2, 2, 2, 1])


def test_a_split_that_does_not_add_up_changes_nothing(tmp_path):
    from pyfigures.assistant.existing_tools import arrange_rows
    pyf = _nine_in_three_rows(tmp_path)
    before = open(pyf, "rb").read()
    with pytest.raises(ValueError, match=r"places 8 images but the figure has 9"):
        arrange_rows(pyf, 3, 1200, 3, [3, 2, 2, 1])
    assert open(pyf, "rb").read() == before


def test_the_chat_request_3_2_2_2_is_one_undoable_live_call(qapp, gui, runtime, tmp_path):
    """What the model should have done: one arrange_live_images call."""
    from pyfigures.assistant import launch
    g = gui(shareable=True)
    g.reload_state(_nine_in_three_rows(tmp_path), append=False)
    session = launch.start_live_session(g)

    def cmd(operation, **arguments):
        s = session.snapshot()
        return session.execute(dict(operation=operation, arguments=arguments, request_id=str(uuid.uuid4()),
                                    session_id=s["session_id"], expected_revision=s["revision"]))

    def live_rows():
        out = str(tmp_path / "live.pyf")
        g._save_state_to_file(out)
        return _rows(out)

    out = cmd("arrange_rows", row_counts=[3, 2, 2, 2])
    assert out["operation_result"]["images_per_row"] == [3, 2, 2, 2]
    assert live_rows() == _expected([3, 2, 2, 2])
    cmd("undo")
    assert live_rows() == _expected([3, 3, 3])


def test_gui_arrange_all_images_in_rows(qapp, gui, runtime, tmp_path, monkeypatch):
    from qtpy.QtWidgets import QMessageBox
    g = gui()
    g.reload_state(_nine_in_three_rows(tmp_path), append=False)
    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(a[2]))

    def rows():
        out = str(tmp_path / "gui.pyf")
        g._save_state_to_file(out)
        return _rows(out)

    assert g.arrange_images_in_rows("3-2-2-2")["images_per_row"] == [3, 2, 2, 2]
    assert rows() == _expected([3, 2, 2, 2])
    g.undo()
    assert rows() == _expected([3, 3, 3])
    assert g.arrange_images_in_rows("5-5") is None and "has 9" in warned[-1]   # refused, explained
    assert rows() == _expected([3, 3, 3])


def test_live_tool_documents_row_counts():
    from pyfigures.assistant import live_mcp
    tool = live_mcp.mcp._tool_manager._tools["arrange_live_images"]
    assert "row_counts" in tool.parameters["properties"] and "3, 2, 2, 2" in tool.description


def test_move_refusal_points_to_row_counts_not_ungroup():
    from pyfigures.assistant.figure_state import movement_changes
    letter = lambda t: {"text": t}
    before = {"panels": [{"panel_id": "p1", "filename": "a.tif", "letters": [letter("a")]},
                         {"panel_id": "p2", "filename": "b.tif", "letters": [letter("b")]}]}
    after = {"panels": [{"panel_id": "p1", "filename": "a.tif", "letters": [letter("b")]},
                        {"panel_id": "p2", "filename": "b.tif", "letters": [letter("a")]}]}
    with pytest.raises(ValueError) as err:
        movement_changes(before, after)
    assert "row_counts" in str(err.value) and "ungroup_all_images" not in str(err.value)


def test_searching_a_tool_by_name_returns_it_first_without_guides():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    find = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools["find_pyfigures_tools"].fn
    for query in ("move_image", "move_image arguments schema src dst group path image index",
                  "arrange_live_images exact arguments schema columns"):
        out = find(query=query)
        assert out["tools"][0]["name"] == query.split()[0], query
        assert "arguments_schema" in out["tools"][0] and not out.get("manual_guides"), query
    out = find(query="arrange layout rows columns grid", category="layout", limit=20)   # was an error
    assert 1 <= len(out["tools"]) <= 12
