"""User chat 2026-11-05: "swap channels in e: 3-->1, 1-->2, 2-->3" stored
channels=[3, 1, 2], read it back and reported a swap. channels is the show/hide
list, so every channel stayed on and nothing changed; it is refused now."""
import numpy as np


def _figure(tmp_path):
    from batoolset.img import Img
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="groups", num_groups=1)
    p = str(tmp_path / "rgb.tif")
    Img(np.zeros((20, 30, 3), np.uint8), dimensions="hwc").save(p)
    add_image(pyf, [0], p)
    return pyf


def test_a_channel_order_is_refused_with_the_lut_route(tmp_path):
    from pyfigures.mcp_server import set_image_property, get_image_property
    pyf = _figure(tmp_path)
    before = get_image_property(pyf, [0], 0, "channels")
    for value in ("[3, 1, 2]", [3, 1, 2], "3,1,2"):
        out = set_image_property(pyf, [0], 0, "channels", value)
        assert out.startswith("ERROR") and "set_lut" in out and "not a channel order" in out
    assert get_image_property(pyf, [0], 0, "channels") == before


def test_show_hide_flags_are_still_accepted(tmp_path):
    from pyfigures.mcp_server import set_image_property
    pyf = _figure(tmp_path)
    out = set_image_property(pyf, [0], 0, "channels", "[False, True, False]")
    assert "ERROR" not in out and "False, True, False" in out
    assert "ERROR" not in set_image_property(pyf, [0], 0, "channels", "None")
