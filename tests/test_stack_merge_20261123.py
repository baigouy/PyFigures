"""User 2026-11-23 (live chat): "split d into its channels" made the two channel panels
(no merge); then "make the split and merge its own row and put the merge at the end" failed:
add_channel_merge only took one file per channel, the model could not add the merge of the
stack and gave up. add_channel_merge(stack_path=...) now adds the stack's merge panel at the
end of a row."""
import os
import xml.etree.ElementTree as ET

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _stack(tmp_path):
    import tifffile
    data = np.zeros((4, 2, 30, 40), np.uint8)          # Z C Y X
    data[:, 0, 5:15, 5:15] = 200
    data[:, 1, 15:25, 20:35] = 150
    p = str(tmp_path / "zc.tif")
    tifffile.imwrite(p, data, imagej=True, metadata={"axes": "ZCYX"})
    return p


def _row_images(pyf, row):
    root = ET.parse(pyf).getroot()
    grp = [g for g in root if g.tag == "Group"][row]
    return [i for i in grp.find("content") if i.tag == "Image2D"]


def test_the_merge_of_a_stack_goes_at_the_end_of_the_split_row(tmp_path):
    from pyfigures import mcp_server as M
    stack = _stack(tmp_path)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], stack)
    out = M.add_channel_split(pyf, stack_path=stack, include_merge=False)
    assert "added at group [1]" in out, out
    assert len(_row_images(pyf, 1)) == 2
    res = M.add_channel_merge(pyf, [1], stack_path=stack, label="Merge")
    assert "the last panel" in res and "green" in res and "magenta" in res, res
    row = _row_images(pyf, 1)
    assert len(row) == 3
    merge = row[-1]
    assert "True" in merge.findtext("channels") and "False" not in merge.findtext("channels")
    assert "GREEN" in merge.findtext("LUTs") and "MAGENTA" in merge.findtext("LUTs")
    assert "Merge" in ET.tostring(merge, encoding="unicode")


def test_errors_say_what_to_give(tmp_path):
    from pyfigures import mcp_server as M
    stack = _stack(tmp_path)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    assert "not both" in M.add_channel_merge(pyf, [0], channel_files=[stack, stack], stack_path=stack)
    assert "2 channels but 3 colours" in M.add_channel_merge(pyf, [0], stack_path=stack,
                                                             colors=["red", "green", "blue"])
