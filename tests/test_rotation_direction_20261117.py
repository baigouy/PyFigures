"""A positive rotation turns the image clockwise, and the reply says the direction.

User, 2026-11-17: "rotate n by 25 degrees clockwise" -> the model sent rotation=-25
(the maths convention) and reported "rotated 25° clockwise (rotation = -25°)". In
PyFigures a positive angle is clockwise as seen; the frequent-operations line of the
chat dispatcher did not say so, and the reply ("rotation=-25.0°") gave no direction.
"""
from __future__ import annotations

import os

import numpy as np
import pytest


def _figure(tmp_path):
    import tifffile
    import pyfigures.mcp_server as M
    a = np.zeros((200, 200), np.uint8)
    a[95:105, 100:200] = 255            # a bar from the centre to the right edge
    tif = str(tmp_path / "bar.tif")
    tifffile.imwrite(tif, a)
    pyf = str(tmp_path / "rot.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], tif)
    return M, pyf


def test_the_reply_names_the_direction(tmp_path):
    M, pyf = _figure(tmp_path)
    assert "clockwise 25° as seen" in M.transform_image(pyf, [0], 0, rotation=25)
    reply = M.transform_image(pyf, [0], 0, rotation=-25)
    assert "counter-clockwise 25° as seen" in reply and "(clockwise" not in reply
    assert "upright" in M.transform_image(pyf, [0], 0, rotation=0)


def test_the_chat_is_told_positive_is_clockwise():
    import inspect
    from pyfigures.assistant import categorized_mcp
    source = inspect.getsource(categorized_mcp)
    assert "POSITIVE = CLOCKWISE" in source and '"25° clockwise" = 25' in source


def test_a_positive_angle_turns_the_image_clockwise(tmp_path):
    # on screen (y down) clockwise takes the bar's right end DOWN
    M, pyf = _figure(tmp_path)
    M.transform_image(pyf, [0], 0, rotation=30, fill_color="black")
    _text, image = M.preview_panel_source(pyf, [0], 0, view="figure")
    from PIL import Image
    px = np.asarray(Image.open(image.path).convert("L")).astype(int)
    h, w = px.shape
    right = px[:, int(w * 0.75):]                       # the bar's outer part
    rows = np.nonzero((right > 128).any(1))[0]
    assert len(rows) and rows.mean() > h / 2 + 3, (rows.mean(), h)
