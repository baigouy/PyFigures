"""User 2026-11-23 (file-MCP A/B, Mistral Large, categories mode): "How wide is the figure, in
mm?" failed: get_figure_properties was the first search hit but only said "global font and
default spacing", so the model went on searching and read every panel's width / scale until it
ran out of steps. The size in mm is now in get_figure_properties (first line says so) and in
describe_figure, and the search finds it from the user's words."""
import json
import os

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _figure(tmp_path):
    import tifffile
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for i in range(3):
        tif = str(tmp_path / f"{i}.tif")
        tifffile.imwrite(tif, np.full((60, 80), 40 * i + 20, np.uint8))
        M.add_image(pyf, [0], tif)
    return pyf


def test_the_size_in_mm_is_reported(tmp_path):
    from pyfigures import mcp_server as M
    pyf = _figure(tmp_path)
    M.resize_figure(pyf, width_mm=120)
    size = json.loads(M.get_figure_properties(pyf))["size"]
    assert abs(size["width_mm"] - 120) < 1.5, size
    assert size["height_mm"] > 0 and size["target_width_mm"] == 120
    assert abs(size["width_pt"] - 120 / 25.4 * 72) < 4
    assert "120" in M.describe_figure(pyf).splitlines()[1] and "mm wide" in M.describe_figure(pyf)


def test_the_search_finds_it_from_the_users_words():
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.category_surface import build
    find = build(M.mcp)._tool_manager._tools["find_pyfigures_tools"].fn
    for q in ("How wide is the figure, in mm?", "figure width height size in mm"):
        top = [t["name"] for t in find(query=q, limit=3)["tools"]]
        assert "get_figure_properties" in top, (q, top)
    # whole words, small words ignored, the whole request covered: no regressions on the
    # A/B suite's requests (the old substring search had "in" match "kinds")
    for q, want in (("export pdf", "export_figure"), ("legend outside", "edit_data_plot"),
                    ("add scale bar", "set_scale_bar"), ("crop image left", "transform_image"),
                    ("put ROI around every blob", "detect_objects"), ("spacing between panels", "set_spacing"),
                    ("flip horizontally", "transform_image"), ("list images", "list_images")):
        top = [t["name"] for t in find(query=q, limit=3)["tools"]]
        assert want in top, (q, top)
    assert M.get_figure_properties.__doc__.splitlines()[0].startswith("How wide")
