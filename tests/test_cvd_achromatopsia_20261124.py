"""Achromatopsia in the colour-blindness preview (user 2026-11-24: the manuscript lists it with
protanopia, deuteranopia and tritanopia, and it was missing)."""
import numpy as np
import pytest

from pyfigures import cvd


def test_achromatopsia_is_offered_after_the_dichromacies():
    assert cvd.TYPES == ("protanopia", "deuteranopia", "tritanopia", "achromatopsia")
    # the GUI dialog preselects index 1: still deuteranopia
    assert cvd.TYPES[1] == "deuteranopia"
    for alias in ("achromat", "grey", "gray", "grayscale", "Monochromacy"):
        assert cvd.resolve_type(alias) == "achromatopsia"
    with pytest.raises(ValueError, match="achromatopsia"):
        cvd.resolve_type("nope")


def test_achromatopsia_turns_every_colour_into_its_grey():
    rgb = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255], [0, 0, 0],
                     [255, 0, 255]]], np.uint8)
    out = cvd.simulate_array(rgb, "achromatopsia")
    assert out.shape == rgb.shape and out.dtype == np.uint8
    assert (out[..., 0] == out[..., 1]).all() and (out[..., 1] == out[..., 2]).all()
    assert out[0, :, 0].tolist() == [54, 182, 18, 255, 0, 73]     # Rec. 709 luminance
    # magenta and green, the colour-blind-safe pair, stay apart in grey
    assert abs(int(out[0, 5, 0]) - int(out[0, 1, 0])) > 100


def test_alpha_kept():
    rgba = np.zeros((2, 2, 4), np.uint8)
    rgba[..., 1] = 200
    rgba[..., 3] = 77
    out = cvd.simulate_array(rgba, "grey")
    assert out.shape == (2, 2, 4) and (out[..., 3] == 77).all()


def test_mcp_tool_and_review_brief_know_it():
    from pyfigures.mcp_tools import export
    assert "achromatopsia" in export.simulate_color_blindness.__doc__ or \
        "achromatopsia" in (getattr(export.simulate_color_blindness, "description", "") or "")
    src = open(export.__file__, encoding="utf-8").read()
    assert '"tritanopia", "achromatopsia"]' in src
