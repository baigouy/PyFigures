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
        # what CAN be done: each colour on its own, from the chat and from the GUI
        assert "make channel 1 blue" in out and "Appearance > Set LUT(s)" in out and "Set LUTs" in out
    assert get_image_property(pyf, [0], 0, "channels") == before


def test_state_tells_the_colour_each_channel_shows():
    # "swap channel 1 and 2" after a LUT reset: the chat must know the file's own
    # colours (an LSM's RED, GREEN, BLUE) to permute them
    from types import SimpleNamespace
    from pyfigures.assistant.session import channel_colours, lut_colour_name
    ramp = np.linspace(0, 255, 256)
    zero = np.zeros(256)

    def lut(r, g, b):
        return np.stack([ramp if r else zero, ramp if g else zero, ramp if b else zero], axis=1)   # (256, 3)
    assert [lut_colour_name(lut(*c)) for c in ((1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1))] == \
        ["RED", "GREEN", "BLUE", "MAGENTA", "GRAY"]
    assert lut_colour_name(lut(1, 0, 0).T) == "RED"                                   # (3, 256) too
    img = SimpleNamespace(metadata={"LUTs": [lut(1, 0, 0), lut(0, 1, 0), lut(0, 0, 1)]})
    assert channel_colours(SimpleNamespace(LUTs=None, img=img)) == ["RED", "GREEN", "BLUE"]
    assert channel_colours(SimpleNamespace(LUTs=["magenta", None, None], img=img)) == ["MAGENTA", "GREEN", "BLUE"]
    assert channel_colours(SimpleNamespace(LUTs=None, img=None)) is None


def test_show_hide_flags_are_still_accepted(tmp_path):
    from pyfigures.mcp_server import set_image_property
    pyf = _figure(tmp_path)
    out = set_image_property(pyf, [0], 0, "channels", "[False, True, False]")
    assert "ERROR" not in out and "False, True, False" in out
    assert "ERROR" not in set_image_property(pyf, [0], 0, "channels", "None")
