"""Inverted LUTs (Fiji's Invert LUT), LUT previews and colour bars placed next
to their panel. "invert the gradient in b" and "add the corresponding LUT on
the right of b" both failed in the chat on 2026-11-03."""
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_API", "pyqt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _luts(pyf, index=0):
    return [i for i in ET.parse(pyf).getroot().iter("Image2D")][index].findtext("LUTs")


@pytest.fixture
def gray_and_rgb(tmp_path):
    import tifffile
    from pyfigures.mcp_server import create_figure, add_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, num_groups=1)
    tifffile.imwrite(str(tmp_path / "g.tif"), np.tile(np.arange(64, dtype=np.uint8), (64, 1)))
    tifffile.imwrite(str(tmp_path / "c.tif"), np.full((3, 20, 20), 120, np.uint8), metadata={"axes": "CYX"})
    add_image(pyf, [0], str(tmp_path / "g.tif"))
    add_image(pyf, [0], str(tmp_path / "c.tif"))
    return pyf


def test_every_pyfigures_lut_has_an_inverted_twin():
    from batoolset.luts.lut_minimal_test import (list_available_luts, PaletteCreator, invert_lut_name,
                                                 is_inverted_lut)
    luts, creator = list_available_luts(), PaletteCreator()
    gray, inverted = creator.create3(luts["GRAY"]), creator.create3(luts["GRAY_INVERTED"])
    assert list(inverted[0]) == [255, 255, 255] and list(inverted[255]) == [0, 0, 0]
    assert (np.asarray(creator.create3(luts["HI_LO_INVERTED"])) == np.asarray(creator.create3(luts["HI_LO"]))[::-1]).all()
    assert "DEFAULT_INVERTED" not in luts and "PACKING_INVERTED" not in luts
    assert invert_lut_name("GRAY") == "GRAY_INVERTED" and invert_lut_name("GRAY_INVERTED") == "GRAY"
    assert invert_lut_name("MATPLOTLIB_viridis") == "MATPLOTLIB_viridis_r"
    assert invert_lut_name("MATPLOTLIB_viridis_r") == "MATPLOTLIB_viridis"
    assert invert_lut_name("DEFAULT") is None and invert_lut_name("blorple") is None
    assert is_inverted_lut("GREEN_INVERTED") and is_inverted_lut("MATPLOTLIB_jet_r") and not is_inverted_lut("GREEN")
    assert gray is not None


@pytest.mark.parametrize("asked,key", [
    ("inverted gray", "GRAY_INVERTED"), ("negative green", "GREEN_INVERTED"), ("GRAY_INVERTED", "GRAY_INVERTED"),
    ("reversed viridis", "MATPLOTLIB_viridis_r"), ("viridis_inverted", "MATPLOTLIB_viridis_r"),
    ("viridis", "MATPLOTLIB_viridis"), ("MATPLOTLIB_viridis_r", "MATPLOTLIB_viridis_r")])
def test_lut_names_as_people_write_them(asked, key):
    from pyfigures.mcp_tools.content import _canonical_lut_names
    assert _canonical_lut_names([asked]) == ([key], [])


def test_invert_lut_toggles_and_is_stored(gray_and_rgb):
    from pyfigures.mcp_server import invert_lut, set_lut
    out = invert_lut(gray_and_rgb, [0], 0)
    assert "GRAY_INVERTED" in out and _luts(gray_and_rgb) == repr(["GRAY_INVERTED"])
    invert_lut(gray_and_rgb, [0], 0)
    assert _luts(gray_and_rgb) == repr(["GRAY"])                    # inverting again restores it
    # an RGB image on its acquisition colours: which LUT is not guessed
    assert invert_lut(gray_and_rgb, [0], 1).startswith("ERROR")
    set_lut(gray_and_rgb, [0], 1, ["MAGENTA", "GREEN", "MATPLOTLIB_viridis"])
    invert_lut(gray_and_rgb, [0], 1, channels=[0, 2])
    assert _luts(gray_and_rgb, 1) == repr(["MAGENTA_INVERTED", "GREEN", "MATPLOTLIB_viridis_r"])
    assert invert_lut(gray_and_rgb, [0], 1, channels=[5]).startswith("ERROR")


def test_a_plot_script_panel_refuses_a_lut_and_says_why(tmp_path):
    from pyfigures.mcp_server import create_figure, add_scripted_image, set_lut, invert_lut
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, num_groups=1)
    add_scripted_image(pyf, [0], "fig, ax = plt.subplots()\nax.imshow(np.eye(4), cmap='viridis')\nself.img = fig")
    for out in (set_lut(pyf, [0], 0, ["MATPLOTLIB_viridis_r"]), invert_lut(pyf, [0], 0)):
        assert out.startswith("ERROR") and "set_script" in out and "viridis_r" in out


def test_preview_luts_draws_the_ramps():
    from pyfigures.mcp_server import preview_luts
    image = preview_luts(["GRAY", "inverted gray", "MATPLOTLIB_viridis"])
    assert image.data[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(ValueError, match="blorple"):
        preview_luts(["blorple"])


def test_colour_bar_next_to_its_panel_takes_its_lut(gray_and_rgb):
    from pyfigures.mcp_server import add_lut_calibration_bar, set_lut
    set_lut(gray_and_rgb, [0], 0, ["GRAY_INVERTED"])
    out = add_lut_calibration_bar(gray_and_rgb, [0], lut="", image_index=0)
    assert "GRAY_INVERTED colour bar added as index 1" in out and "panel LUT" in out
    imgs = list(ET.parse(gray_and_rgb).getroot().iter("Image2D"))
    assert len(imgs) == 3 and "ColorbarBase" in (imgs[1].findtext("custom_loading_script") or "") + str(
        __import__("pyfigures.mcp_tools.core", fromlist=["_decode"])._decode(imgs[1].findtext("custom_loading_script")))
    # without a panel: appended at the end, GRAY by default, as before
    assert "index 3" in add_lut_calibration_bar(gray_and_rgb, [0])


def test_colour_bar_and_inversion_requests_find_their_tools():
    from pyfigures.guides import find_guide
    assert find_guide("add LUT colorbar next to panel right side show colour table scale")[0] == "colour_bar"
    assert find_guide("add a colour bar")[0] == "colour_bar"
    assert find_guide("add a scale bar to this panel")[0] == "scale_bar_one_panel"
