"""A chat session with Mistral Large 4 (2026-11-16) on nine Fiji sample
images, kept as human requests:
  "build a figure with 6-9 images from <folder>", "add scale bars to all",
  "g bar no see...", "segment white stuff in the mouth in h",
  "draw a hat on the top of the head in i using ROIs".
All five worked; two were slow:
- "add scale bars to all" (4 min, 12 model steps): set_scale_bar_all without a
  length refused ("no image has a scale bar yet"), so the model added the
  nine bars one call at a time, and CT.dcm / Blend_Final.IPL were refused
  as "width unknown" (only TIFF and PIL formats were read for a size), and
  CT.dcm's 597 µm pixel size was ignored (a format whitelist).
- "segment the white stuff" (5 min): detect_objects had no region, so the
  model cropped panel h six times to aim it, then put the crop back.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
import tifffile

import pyfigures.mcp_server as M


def _tif(path, shape=(200, 300), um_per_px=None):
    a = np.zeros(shape, np.uint8)
    a[40:80, 50:90] = 200
    if um_per_px:
        tifffile.imwrite(path, a, imagej=True, resolution=(1 / um_per_px, 1 / um_per_px),
                         metadata={"unit": "um"})
    else:
        tifffile.imwrite(path, a)
    return str(path)


def _figure(tmp_path, files):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for f in files:
        M.add_image(pyf, [0], f)
    return pyf


def _bars(pyf):
    out = []
    for i in range(3):
        raw = M.get_scale_bar(pyf, [0], i)
        out.append(None if raw.startswith(("No", "ERROR")) else json.loads(raw))
    return out


def test_add_scale_bars_to_all_without_a_length_is_one_call(tmp_path):
    files = [_tif(tmp_path / "cal.tif", um_per_px=0.1),            # 300 px = 30 µm wide
             _tif(tmp_path / "plain.tif"),                          # no pixel size
             _tif(tmp_path / "wide.tif", (100, 1000), um_per_px=2)]  # 2 mm wide
    pyf = _figure(tmp_path, files)
    reply = M.set_scale_bar_all(pyf)
    assert reply.startswith("Scale bar added to 3 image(s)"), reply
    assert "cal.tif 5 µm" in reply and "plain.tif 50 px" in reply and "wide.tif 300 µm" in reply, reply
    assert "NOT CALIBRATED" in reply and "plain.tif" in reply.split("NOT CALIBRATED")[1]
    assert all(b is not None for b in _bars(pyf))
    # once there are bars, no length restyles them and adds none
    reply = M.set_scale_bar_all(pyf, bar_color="black")
    assert reply.startswith("3 existing scale bar(s) restyled"), reply


def test_restyling_bars_does_not_add_bars_where_there_are_none(tmp_path):
    pyf = _figure(tmp_path, [_tif(tmp_path / "a.tif", um_per_px=0.1), _tif(tmp_path / "b.tif")])
    M.set_scale_bar(pyf, [0], 0, 5)
    reply = M.set_scale_bar_all(pyf, bar_color="black")
    assert reply.startswith("1 existing scale bar(s) restyled"), reply
    assert M.get_scale_bar(pyf, [0], 1).startswith("No")


def _fake_dcm(tmp_path, monkeypatch, vx):
    """A file only the image reader (stack_info) can read: its size and pixel
    size come from there, whatever its format."""
    path = tmp_path / "CT.dcm"
    path.write_bytes(b"\0" * 64)
    import pyfigures.stack_info as S
    real = S.stack_info

    def fake(p, series=None):
        if str(p).lower().endswith(".dcm"):
            return {"sizes": {"h": 495, "w": 888}, "order": "hw", "vx": vx}
        return real(p, series)
    monkeypatch.setattr(S, "stack_info", fake)
    return str(path)


def test_any_format_gives_its_width_and_pixel_size(tmp_path, monkeypatch):
    from pyfigures.mcp_tools.core import _file_pixel_size, _raw_size_from_file
    path = _fake_dcm(tmp_path, monkeypatch, 596.847)
    assert _raw_size_from_file(path) == (888, 495)
    assert _file_pixel_size(path) == pytest.approx(596.847)


def test_a_ct_scan_bar_without_a_length_is_in_cm(tmp_path, monkeypatch):
    path = _fake_dcm(tmp_path, monkeypatch, 596.847)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _load, _save
    # add_image would open the fake file: an Image2D entry pointing at it is enough
    M.add_image(pyf, [0], _tif(tmp_path / "x.tif"))
    tree, root = _load(pyf)
    for el in root.iter("filename"):
        el.text = path
    _save(tree, pyf)
    reply = M.set_scale_bar(pyf, [0], 0)
    assert "10 cm" in reply and "width is unknown" not in reply, reply
    assert ET is not None


def _mouth(tmp_path):
    """Two bright blobs inside a bright ring (teeth in a skull): the ring is
    larger than a quarter of a small search box, the blobs are what is asked."""
    a = np.full((300, 400), 20, np.uint8)
    yy, xx = np.mgrid[:300, :400]
    ring = (np.hypot(yy - 150, xx - 200) > 120) & (np.hypot(yy - 150, xx - 200) < 135)
    a[ring] = 180
    a[110:135, 150:180] = 250
    a[110:135, 220:250] = 250
    path = tmp_path / "head.tif"
    tifffile.imwrite(path, a)
    return str(path)


def test_objects_in_one_part_of_a_panel_without_cropping_it(tmp_path):
    pyf = _figure(tmp_path, [_mouth(tmp_path)])
    found = json.loads(M.detect_objects(pyf, [0], 0, polarity="bright", padding=0,
                                        region=[130, 95, 270, 150]))
    boxes = [(b["x"], b["y"], b["width"], b["height"]) for b in found["boxes"]]
    assert found["added"] == 2 and len(boxes) == 2, found
    assert boxes[0][0] in range(148, 153) and boxes[1][0] in range(218, 223), boxes
    # the panel is not cropped
    t = M.get_image_transform(pyf, [0], 0) if hasattr(M, "get_image_transform") else ""
    assert "crop_left=1" not in str(t)


def test_an_object_cut_by_the_region_is_kept_one_cut_by_the_image_edge_is_not():
    from pyfigures.object_detection import detect
    a = np.zeros((100, 100), np.float32)
    a[40:60, 30:50] = 1.0                       # crosses x = 40, the region's left side
    a[0:20, 70:90] = 1.0                        # touches the image's top edge
    objects, _info = detect(a, (40, 0, 100, 100), polarity="bright", split_touching=False,
                            edge=(0, 0, 100, 100))
    assert [(o["x"], o["y"]) for o in objects] == [(40, 40)], objects


def test_the_chat_is_told_to_add_all_bars_in_one_call_and_to_aim_detection_with_a_region():
    import inspect
    from pyfigures.assistant import categorized_mcp as C
    src = inspect.getsource(C)
    assert "no bar_width_in_units (each image gets its own round length)" in src
    assert "never crop the panel to aim it" in src
    assert "ONE call" in (M.set_scale_bar_all.__doc__ or "")
    assert "region" in (M.detect_objects.__doc__ or "")


def test_the_hat_on_the_head(tmp_path):
    """The last request: a hat drawn with ROIs (brim, crown, stem, pom-pom),
    the calls the model made, on a 256 px head."""
    pyf = _figure(tmp_path, [_tif(tmp_path / "t1-head.tif", (256, 256), um_per_px=1.5)])
    for reply in (M.add_roi_ellipse(pyf, [0], 0, 88, 60, 112, 14, color="red"),
                  M.add_roi_ellipse(pyf, [0], 0, 100, 38, 88, 26, color="red"),
                  M.add_roi_line(pyf, [0], 0, 144, 38, 144, 22, color="red"),
                  M.add_roi_ellipse(pyf, [0], 0, 138, 16, 12, 8, color="red")):
        assert "ERROR" not in reply, reply
    shapes = [a["type"] for a in json.loads(M.get_annotations(pyf))]
    assert shapes.count("Ellipse2D") == 3 and shapes.count("Line2D") == 1, shapes
    # the pom-pom is small but not a slip of the mouse for the audit
    assert json.loads(M.audit_figure(pyf))["panels_with_tiny_rois"] == []
