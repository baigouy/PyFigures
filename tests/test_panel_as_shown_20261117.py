"""preview_panel(view="figure"): the panel as drawn, overlays on or off, described.

Chat log 2026-11-17: asked "scale bar in i does not read well fix it", the model
looked with preview_panel, which only showed the plain source pixels: it could
not see the scale bar, its text or the letter as drawn. The user: it "should be
offered to see image with or without labels letters and ROIs", and "for non
visual models could a description of each panel help". The figure view draws
the panel as in the figure and measures each overlay (place, colour, colour
behind it, contrast ratio).
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

M = pytest.importorskip("pyfigures.mcp_server")


@pytest.fixture
def fig(tmp_path):
    import tifffile
    a = np.zeros((120, 160), np.uint8)
    a[30:90, 40:120] = 220
    img = str(tmp_path / "img.tif")
    tifffile.imwrite(img, a, imagej=True, resolution=(1 / 0.5, 1 / 0.5), metadata={"unit": "um"})
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], img)
    assert not M.set_scale_bar(pyf, [0], 0, bar_width_in_units=20).startswith("ERROR")
    assert not M.add_roi_rect(pyf, [0], 0, 40, 30, 80, 60).startswith("ERROR")
    return pyf


def _png(image):
    from PIL import Image as PILImage
    return np.asarray(PILImage.open(image.path).convert("RGB"))


def test_figure_view_draws_and_describes_each_overlay(fig):
    text, image = M.preview_panel_source(fig, [0], 0, view="figure")
    assert "AS SHOWN IN THE FIGURE" in text
    assert "Drawn: 1 scale bar, 1 ROI/arrow" in text
    bar = next(line for line in text.splitlines() if line.startswith("- scale bar"))
    assert "20 µm" in bar and "bottom right" in bar and "white" in bar and "black" in bar
    assert "reads well" in bar and "21.0:1" in bar
    roi = next(line for line in text.splitlines() if line.startswith("- rectangle ROI"))
    assert "yellow" in roi and "hard to see" in roi              # on the white object's edge
    rgb = _png(image)
    assert rgb.max() == 255 and (rgb.sum(-1) == 0).mean() > 0.5   # the image itself, not blank


def test_overlays_can_be_left_out_of_the_preview_only(fig):
    with_all = _png(M.preview_panel_source(fig, [0], 0, view="figure")[1])
    text, image = M.preview_panel_source(fig, [0], 0, view="figure", rois=False, scale_bar=False)
    assert "Drawn: none" in text and "Left out of this preview only: 1 scale bar, 1 ROI/arrow" in text
    plain = _png(image)
    assert plain.shape == with_all.shape and (plain != with_all).any()
    yellow = (plain[..., 0] > 150) & (plain[..., 1] > 150) & (plain[..., 2] < 100)
    assert not yellow.any()                                       # no ROI drawn
    # the figure itself is unchanged
    again = M.preview_panel_source(fig, [0], 0, view="figure")[0]
    assert "Drawn: 1 scale bar, 1 ROI/arrow" in again


def test_poor_contrast_is_said_in_words(fig):
    M.set_scale_bar(fig, [0], 0, bar_color=0x101010, label_color=0x101010)
    text = M.preview_panel_source(fig, [0], 0, view="figure")[0]
    bar = next(line for line in text.splitlines() if line.startswith("- scale bar"))
    assert "not visible here" in bar or "POOR" in bar


def test_region_and_source_view_unchanged(fig):
    text = M.preview_panel_source(fig, [0], 0, view="figure", region=[100, 100, 160, 120])[0]
    assert "source pixels [100, 100, 160, 120]" in text and "scale bar" in text
    src = M.preview_panel_source(fig, [0], 0)[0]
    assert "AS SHOWN" not in src
    with pytest.raises(ValueError):
        M.preview_panel_source(fig, [0], 0, view="pretty")


def test_roi_replies_name_the_colour(fig):
    # a text-only model set color=255 and told the user "bright red": 255 is blue
    import json
    out = json.loads(M.set_roi_properties(fig, [0], 0, 1, color=255))
    assert out["now"]["color_name"] == "blue (#0000ff)"
    out = json.loads(M.set_roi_properties(fig, [0], 0, 1, color="red"))
    assert out["now"]["color_name"].startswith("red")


def test_export_mode_leaves_nothing_saved_behind(fig):
    # exit_export_mode set _export_original_renderer to None instead of removing it:
    # it was saved with the figure, so every export or preview changed the document
    from batoolset.serializations.tools import element_to_dict, create_object, object_to_xml
    from pyfigures.mcp_tools.core import _load, _get_container, _ensure_qapp
    _ensure_qapp()
    _t, root = _load(fig)
    el = [c for c in _get_container(root, [0])[0] if c.tag == "Image2D"][0]
    props = element_to_dict(el)
    panel = create_object("Image2D", props.get("Image2D", props))
    before = object_to_xml([panel], is_list=True)
    panel.enter_export_mode()
    panel.exit_export_mode()
    after = object_to_xml([panel], is_list=True)
    assert "_export_original_renderer" not in after and after == before


def _panel(fig):
    from batoolset.serializations.tools import element_to_dict, create_object
    from pyfigures.mcp_tools.core import _load, _get_container, _ensure_qapp
    _ensure_qapp()
    _t, root = _load(fig)
    el = [c for c in _get_container(root, [0])[0] if c.tag == "Image2D"][0]
    props = element_to_dict(el)
    return create_object("Image2D", props.get("Image2D", props))


def test_inspect_figure_lists_only_what_is_hard_to_see(fig):
    # a 9B text-only model always called inspect_figure, never the figure view
    from pyfigures.panel_source_preview import overlay_contrast
    out = overlay_contrast(_panel(fig))
    assert out["read_well"] == 1                                   # the white-on-black scale bar
    assert len(out["problems"]) == 1 and out["problems"][0].startswith("rectangle ROI")
    M.set_scale_bar(fig, [0], 0, bar_color=0x101010, label_color=0x101010)
    out = overlay_contrast(_panel(fig))
    assert out["read_well"] == 0
    assert any(p.startswith("scale bar") and ("POOR" in p or "not visible" in p) for p in out["problems"])


def test_inspect_figure_carries_the_verdicts():
    from pyfigures.assistant import categorized_mcp, session
    src = inspect.getsource(categorized_mcp)
    assert "call_live('overlay_contrast')" in src and "'hard_to_see'" in src
    # the sidecar's "Model vision: Off" keeps the verdicts from the model too
    assert "os.environ.get('QTPY_AI_SIDECAR_VISION') == 'none'" in src
    assert "op == 'overlay_contrast'" in inspect.getsource(session)


def test_live_tool_and_guidance_offer_the_figure_view():
    from pyfigures.assistant import live_mcp, categorized_mcp
    sig = inspect.signature(live_mcp.preview_panel)
    for p in ("view", "letters", "texts", "scale_bar", "rois", "insets"):
        assert p in sig.parameters
    doc = inspect.getdoc(live_mcp.preview_panel)
    assert "view='figure'" in doc and "scale bar" in doc
    src = inspect.getsource(categorized_mcp)
    assert 'preview_panel(panel_ref, view="figure")' in src
    assert "Never say what a panel looks like without it" in src
