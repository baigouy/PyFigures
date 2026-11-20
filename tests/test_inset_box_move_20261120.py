"""Replay 2026-11-20 (Qwen, turn 225): "the region is more to the left" -> the model removed
the inset's box and its leader lines one by one to redraw them (14 calls, the inset left
orphaned). Removing the box an inset shows is refused with the one call that moves it."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_remove_annotation_is_still_a_tool_and_the_helper_is_not():
    """The guard's helper was first added under remove_annotation's @mcp.tool(), which
    turned the helper into a tool and dropped remove_annotation from the server."""
    import asyncio
    from pyfigures import mcp_server as M
    names = {t.name for t in asyncio.run(M.mcp.list_tools())}
    assert "remove_annotation" in names
    assert not any(n.startswith("_") for n in names)


def test_the_box_an_inset_shows_is_moved_not_removed(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import (create_figure, add_image, add_zoom_callout, remove_annotation,
                                      get_annotations, move_annotations)
    png = tmp_path / "cells.png"
    Image.new("L", (200, 150), 80).save(png)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    add_image(pyf, [], str(png))
    out = add_zoom_callout(pyf, [], 0, source_x=40, source_y=30, source_w=40, source_h=40,
                           parent_width=200, parent_height=150)
    assert "ERROR" not in out, out
    import json
    anns = json.loads(get_annotations(pyf))
    box = next(a["annotation_index"] for a in anns if a.get("type") == "Rectangle2D")
    refused = remove_annotation(pyf, [], 0, box)
    assert refused.startswith("ERROR") and "move_annotations" in refused and "Nothing was removed" in refused
    assert "ERROR" not in move_annotations(pyf, [], 0, dx=-20, annotation_indexes=[box])
