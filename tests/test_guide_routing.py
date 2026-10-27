"""Free-text requests reach the right Show me how guide: a one-panel scale bar
never gets the all-panels guide, and PDF/SVG questions get the vector export
guide rather than PowerPoint (both misled a local model through the MCP help)."""
import pytest

from pyfigures.guides import find_guide


@pytest.mark.parametrize("query,guide", [
    ("scale bar on all panels", "add_scale_bars"),
    ("give every panel a scale bar", "add_scale_bars"),
    ("add a scale bar to this panel", "scale_bar_one_panel"),
    ("How can I choose between PDF and SVG when exporting a figure?", "export_vector"),
    ("export PDF SVG", "export_vector"),
    ("export to powerpoint", "export_pptx"),
    ("export as svg", "export_vector"),
    ("How do I export the original source data alongside a finished figure?", "export_source_data"),
    ("How do I replace a picture while keeping its existing annotations?", "replace_image"),
    ("reconnect missing images", "remap_images"),
    ("How do I calibrate a scale bar when I know the pixel size?", "set_pixel_size"),
    ("set the pixel size", "set_pixel_size"),
])
def test_request_reaches_its_guide(query, guide):
    assert find_guide(query)[0] == guide


@pytest.mark.parametrize("query", ["scale bar", "Give a a 10 micrometre scale bar",
                                   "scale bar um", "10 µm scale bar", "scale bar calibration"])
def test_bare_scale_bar_request_does_not_pick_the_all_panels_guide(query):
    gid, candidates = find_guide(query)
    assert gid != "add_scale_bars" and {"add_scale_bars", "scale_bar_one_panel"} <= set(candidates)
