"""Qwen A/B 2026-11-23, "Swap the two rows": the file MCP server had no way to reorder rows;
reorder_children(group_path=[]) reordered only loose canvas images ("permutation of 0..-1" on a
figure made of rows) and Mistral got there by rewriting the XML. [] now reorders the rows."""
import os
import xml.etree.ElementTree as ET

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _rows(pyf):
    root = ET.parse(pyf).getroot()
    return [[os.path.basename(i.findtext("filename")).strip('"') for i in g.iter("Image2D")]
            for g in root if g.tag == "Group"]


def test_swap_the_two_rows(tmp_path):
    import tifffile
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=2)
    for row, names in enumerate((["a.tif", "b.tif"], ["c.tif", "d.tif"])):
        for n in names:
            p = str(tmp_path / n)
            tifffile.imwrite(p, np.full((20, 30), 50, np.uint8))
            M.add_image(pyf, [row], p)
    out = M.reorder_children(pyf, [], [1, 0])
    assert out.startswith("Rows reordered to [1, 0]"), out
    assert _rows(pyf) == [["c.tif", "d.tif"], ["a.tif", "b.tif"]]
    bad = M.reorder_children(pyf, [], [0, 1, 2])
    assert "permutation of 0..1 (the figure has 2 rows)" in bad and "Nothing was changed" in bad
    assert _rows(pyf) == [["c.tif", "d.tif"], ["a.tif", "b.tif"]]          # refused: unchanged
    root = ET.parse(pyf).getroot()
    tags = [c.tag for c in root]
    assert max(i for i, t in enumerate(tags) if t == "Group") < len(tags) - 1 or "Group" not in tags[-1:]


def test_the_search_finds_it_for_swap_rows():
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.category_surface import build
    find = build(M.mcp)._tool_manager._tools["find_pyfigures_tools"].fn
    top = [t["name"] for t in find(query="swap the two rows", limit=3)["tools"]]
    assert "reorder_children" in top, top
