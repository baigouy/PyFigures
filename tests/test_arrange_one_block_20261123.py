"""Chat 2026-11-23 (Mistral Large 4): "starting from f, make each row contain at most 3 images" on
a 51-frame time-series montage (one block: a column of 9 rows). arrange_live_images could only
re-lay the whole figure, its group_path was refused, the model searched seven times, undid an
earlier edit and gave up. arrange_rows now takes group_path: only that block is re-wrapped."""
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _figure(tmp_path):
    import tifffile
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for i in range(3):
        tif = str(tmp_path / f"top{i}.tif")
        tifffile.imwrite(tif, np.full((40, 40), 30 * i + 20, np.uint8))
        M.add_image(pyf, [0], tif)
    stack = str(tmp_path / "movie.tif")
    tifffile.imwrite(stack, (np.random.rand(10, 32, 32) * 255).astype(np.uint8), imagej=True,
                     metadata={"axes": "TYX"})
    (M.add_stack_montage(pyf, stack, axis="t", frames="all", columns=6))
    return pyf


def _rows(pyf, gi):
    from pyfigures.mcp_tools import structure as tools
    from pyfigures.mcp_tools.core import _top_groups
    root = ET.fromstring(tools.get_xml(pyf))
    group = _top_groups(root)[gi]
    return [len([c for c in g.find("content") if c.tag == "Image2D"])
            for g in group.find("content") if g.tag == "Group"]


def test_only_the_montage_is_rewrapped(tmp_path):
    from pyfigures.assistant.existing_tools import arrange_rows
    from pyfigures.mcp_tools import structure as tools
    from pyfigures.mcp_tools.core import _top_groups
    pyf = _figure(tmp_path)
    tops = len(_top_groups(ET.fromstring(tools.get_xml(pyf))))
    montage = tops - 1
    first_row = ET.tostring(_top_groups(ET.fromstring(tools.get_xml(pyf)))[0])
    result = arrange_rows(pyf, 3, 512, 3, group_path=[montage])
    assert result["images_per_row"] == [3, 3, 3, 3] and result["image_count"] == 12   # 10 frames + 2 empty slots
    assert _rows(pyf, montage) == [3, 3, 3, 3]
    root = ET.fromstring(tools.get_xml(pyf))
    assert len(_top_groups(root)) == tops                          # the rest of the figure is untouched
    assert len([c for c in _top_groups(root)[0].find("content") if c.tag == "Image2D"]) == 3
    ids = [g.findtext("ID") for g in root.iter("Group")]
    assert len(ids) == len(set(ids))


def test_a_wrong_block_changes_nothing(tmp_path):
    from pyfigures.assistant.existing_tools import arrange_rows
    from pyfigures.mcp_tools import structure as tools
    pyf = _figure(tmp_path)
    before = tools.get_xml(pyf)
    with pytest.raises(ValueError, match="Nothing was changed"):
        arrange_rows(pyf, 3, 512, 3, group_path=[42])
    with pytest.raises(ValueError, match="Nothing was changed"):
        arrange_rows(pyf, 3, 512, 3, row_counts=[3, 3], group_path=[1])
    assert tools.get_xml(pyf) == before


def test_the_live_tool_and_its_rule_name_group_path():
    import inspect
    from pyfigures.assistant import categorized_mcp, live_mcp
    assert "group_path" in inspect.signature(live_mcp.arrange_live_images).parameters
    assert "group_path=[its index]" in categorized_mcp.request_rules("starting from f make each row contain at most 3 images")
