"""2026-11-19 (user, live app): "rotate all images by 25 degrees clockwise" turned the
cropped panels into a larger, different region ("crops got messed up by the
rotation, I don't see why the crop size should change"). A crop is counted on the
rotated image (the panel editor crops what it shows), so a new angle now converts
it: the window keeps its size and its centre on the image, which turns under it.
Also: plots keep only a hair of white around them (they sat further from their
neighbours than the panel spacing), and a path whose backslashes became control
characters is refused instead of writing an unreadable figure file."""
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyfigures.mcp_tools.core import crops_for_new_rotation, _rotated_size

CROP = {"left": 17, "right": 176, "top": 77, "bottom": 27}       # the user's crop of a 229 x 140 image
SIZE = (229, 140)


def _window(size, theta, crop):
    w, h = _rotated_size(size[0], size[1], theta)
    return w - crop["left"] - crop["right"], h - crop["top"] - crop["bottom"]


@pytest.mark.parametrize("theta1", [25, 90, -40, 180])
def test_the_window_keeps_its_size(theta1):
    new = crops_for_new_rotation(SIZE, 0, CROP, theta1)
    assert _window(SIZE, theta1, new) == pytest.approx(_window(SIZE, 0, CROP), abs=1.5)


def test_turning_back_gives_the_crop_back():
    there = crops_for_new_rotation(SIZE, 0, CROP, 25)
    back = crops_for_new_rotation(SIZE, 25, there, 0)
    assert all(abs(back[k] - CROP[k]) <= 1 for k in CROP), back


def test_the_same_angle_changes_nothing():
    assert crops_for_new_rotation(SIZE, 25, CROP, 25) == CROP


def _figure(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_group, add_image
    src = str(tmp_path / "img.png")
    Image.fromarray((np.random.default_rng(0).random((140, 229)) * 255).astype(np.uint8)).save(src)
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    add_group(pyf, "X")
    add_image(pyf, [0], src)
    return pyf


def _crop(pyf):
    img = ET.parse(pyf).getroot().find(".//Image2D")
    return {k: int(float(img.findtext(f"crop_{k}") or 0)) for k in CROP}, img.findtext("theta")


def test_rotating_a_cropped_panel_keeps_its_window(tmp_path):
    from pyfigures.mcp_server import transform_image
    pyf = _figure(tmp_path)
    transform_image(pyf, [0], 0, **{f"crop_{k}": v for k, v in CROP.items()})
    msg = transform_image(pyf, [0], 0, rotation=25)
    assert "ERROR" not in msg and "same region stays visible" in msg
    crop, theta = _crop(pyf)
    assert float(theta) == 25
    assert _window(SIZE, 25, crop) == pytest.approx(_window(SIZE, 0, CROP), abs=1.5)


def test_set_image_property_theta_does_the_same(tmp_path):
    from pyfigures.mcp_server import transform_image, set_image_property
    pyf = _figure(tmp_path)
    transform_image(pyf, [0], 0, **{f"crop_{k}": v for k, v in CROP.items()})
    msg = set_image_property(pyf, [0], 0, "theta", "25")
    assert "ERROR" not in msg and "same region stays visible" in msg
    assert _window(SIZE, 25, _crop(pyf)[0]) == pytest.approx(_window(SIZE, 0, CROP), abs=1.5)


def test_a_crop_and_a_rotation_given_together_are_kept_as_given(tmp_path):
    """The panel editor's way: rotate, then crop the blank corners off the rotated image."""
    from pyfigures.mcp_server import transform_image
    pyf = _figure(tmp_path)
    transform_image(pyf, [0], 0, rotation=25, crop_left=40, crop_right=40, crop_top=40, crop_bottom=40)
    assert _crop(pyf)[0] == {"left": 40, "right": 40, "top": 40, "bottom": 40}


def test_an_uncropped_panel_just_turns(tmp_path):
    from pyfigures.mcp_server import transform_image
    pyf = _figure(tmp_path)
    msg = transform_image(pyf, [0], 0, rotation=25)
    assert "same region" not in msg and _crop(pyf)[0] == {k: 0 for k in CROP}


def test_a_path_with_control_characters_is_refused(tmp_path):
    from pyfigures.mcp_server import create_figure, add_group, add_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    add_group(pyf, "X")
    msg = add_image(pyf, [0], "C:\\Users\\me\\Desktop\test_images\blobs.gif")    # \t and \b, not escaped
    assert msg.startswith("ERROR") and "forward slashes" in msg
    ET.parse(pyf)                                                               # still readable


def test_plots_keep_only_a_hair_of_white_around_them():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from batoolset.matplolibs.tools import figure_pad_inches
    fig = plt.figure()
    assert figure_pad_inches(fig) <= 0.02          # was matplotlib's 0.1 inch
    fig._pyfigures_pad_inches = 0
    assert figure_pad_inches(fig) == 0
    plt.close(fig)
