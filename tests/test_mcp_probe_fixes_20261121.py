"""What a session driven through the MCP server found (2026-11-21, user: "test the MCP
yourself and try requests ... fix all things you find"): links lost on a layout update,
plots drawn into their old frame after an edit, no letters drawn, a broken axis silently
leaving out a right axis, statistics sentences that did not say which plot."""
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("staplot")


@pytest.fixture
def figure(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import create_figure, add_image
    rng = np.random.default_rng(3)
    png = tmp_path / "cells.png"
    Image.fromarray((rng.random((300, 400)) * 255).astype(np.uint8)).save(png)
    rows = ["day,genotype,area"]
    for day, s in ((1, 1.0), (7, 1.6)):
        for g, m in (("WT", 100), ("KO", 130)):
            rows += [f"{day},{g},{m * s + v:.1f}" for v in rng.normal(0, 8, 8)]
    csv = tmp_path / "area.csv"
    csv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, num_groups=2)
    add_image(pyf, [0], str(png))
    return pyf, str(csv)


def _links(pyf):
    from pyfigures.mcp_tools.core import _load, _child_text
    _t, root = _load(pyf)
    img = next(iter(root.iter("Image2D")))
    return {a.tag: (_child_text(a, "link_id"), _child_text(a, "follows_roi")) for a in img.find("annotations")}


def test_a_data_plot_keeps_the_box_inset_links_of_the_figure(figure):
    """add_data_plot's layout update re-saved every panel without their link fields: the
    inset no longer followed its box, and the box could be removed under it."""
    from pyfigures.mcp_server import (add_zoom_callout, set_scale_bar, add_data_plot, move_annotations,
                                      remove_annotation)
    pyf, csv = figure
    set_scale_bar(pyf, [0], 0, bar_width_in_units=10, unit="µm", px_to_unit=0.2)
    add_zoom_callout(pyf, [0], 0, source_x=100, source_y=80, source_w=60, source_h=60,
                     parent_width=400, parent_height=300)
    box_id = _links(pyf)["Rectangle2D"][0]
    assert box_id and _links(pyf)["Image2D"][1] == box_id
    assert "ERROR" not in add_data_plot(pyf, [1], csv, kind="box", columns=["genotype", "area"])
    assert _links(pyf)["Rectangle2D"][0] == box_id and _links(pyf)["Image2D"][1] == box_id
    move_annotations(pyf, [0], 0, dx=-40, dy=0, annotation_indexes=[1])
    refused = remove_annotation(pyf, [0], 0, 1)
    assert refused.startswith("ERROR") and "Nothing was removed" in refused


def test_an_edited_plot_is_measured_again(figure):
    """Its stored size was kept: a violin / broken axis / layer drawn into the old frame
    lost its x labels at the bottom."""
    from pyfigures.mcp_server import add_data_plot, edit_data_plot
    from pyfigures.mcp_tools.core import _load, _child_text
    pyf, csv = figure
    add_data_plot(pyf, [1], csv, kind="box", columns=["genotype", "area"], where="day == 1")

    def size():
        _t, root = _load(pyf)
        plot = [i for i in root.iter("Image2D") if "_api" in str(_child_text(i, "custom_loading_script"))][0]
        return _child_text(plot, "width"), _child_text(plot, "height")
    before = size()
    assert "ERROR" not in edit_data_plot(pyf, [1], 0, ybreak=[115, 125])
    after = size()
    assert after != before and all(isinstance(v, (int, float)) and v > 0 for v in after)


def test_a_broken_axis_refuses_what_it_cannot_draw(figure):
    from pyfigures.mcp_server import add_data_plot, edit_data_plot
    pyf, csv = figure
    add_data_plot(pyf, [1], csv, kind="box", columns=["genotype", "area"], where="day == 1")
    edit_data_plot(pyf, [1], 0, ybreak=[115, 125])
    out = edit_data_plot(pyf, [1], 0, y2={"csv": csv, "columns": ["genotype", "area"]})
    assert out.startswith("ERROR") and "broken y axis" in out
    assert edit_data_plot(pyf, [1], 0, invert_y=True).startswith("ERROR")


def test_letters_on_a_figure_that_had_none(figure):
    """set_panel_letter_layout("panel") answered "one in each panel" and none was drawn:
    lettering on alone draws nothing, the letters are texts the panels carry."""
    from pyfigures.mcp_server import set_panel_letter_layout, add_image
    from pyfigures.mcp_tools.core import _load, _child_text
    pyf, _csv = figure
    _t, root = _load(pyf)
    add_image(pyf, [0], _child_text(next(iter(root.iter("Image2D"))), "filename"))
    out = set_panel_letter_layout(pyf, "panel")
    assert "2 panel(s) lettered" in out, out
    _t, root = _load(pyf)
    assert sum(1 for t in root.iter("TAText2D") if str(_child_text(t, "is_letter")) == "True") == 2
    assert "lettered" not in set_panel_letter_layout(pyf, "panel")        # never twice


def test_column_titles_take_no_letter_and_a_turned_panel_gets_a_readable_one(figure):
    """A row of column titles took A-D (the images began at E); a rotated panel's letter
    was white on the white page corner."""
    from pyfigures.mcp_server import add_image, add_label_row, transform_image, set_panel_letter_layout
    from pyfigures.mcp_tools.core import _load, _child_text
    pyf, _csv = figure
    _t, root = _load(pyf)
    add_image(pyf, [0], _child_text(next(iter(root.iter("Image2D"))), "filename"))
    transform_image(pyf, [0], 1, rotation=15)
    add_label_row(pyf, [0], ["WT", "KO"], position="above")
    assert "2 panel(s) lettered" in set_panel_letter_layout(pyf, "panel")
    _t, root = _load(pyf)
    letters = {}
    for img in root.iter("Image2D"):
        for t in img.iter("TAText2D"):
            if str(_child_text(t, "is_letter")) == "True":
                letters[_child_text(img, "theta") or 0] = str(_child_text(t, "text"))
    assert len(letters) == 2
    turned = next(v for k, v in letters.items() if float(k or 0) == 15)
    assert "#000000" in turned or "black" in turned.lower(), turned        # dark on the page


def test_texts_with_no_font_beside_named_ones_are_reported(figure):
    import json
    from pyfigures.mcp_server import add_label_row, set_scale_bar, check_text_consistency
    pyf, _csv = figure
    set_scale_bar(pyf, [0], 0, bar_width_in_units=10, unit="µm", px_to_unit=0.2)
    add_label_row(pyf, [0], ["WT"], position="above")
    report = json.loads(check_text_consistency(pyf))
    fonts = [i for i in report["issues"] if i["property"] == "font"]
    if any(t["font"] in ("Sans Serif", "MS Shell Dlg 2") for t in report["kinds"].get("other texts", {}).values()
           if isinstance(t, dict) and "font" in t):
        assert fonts and "restyle_texts" in fonts[-1]["fix"] and not report["consistent"]


def test_statistics_say_which_plot_and_the_figure_says_what_a_plot_is(figure):
    from pyfigures.mcp_server import add_data_plot, caption_statistics, describe_figure
    pyf, csv = figure
    add_data_plot(pyf, [1], csv, kind="box", columns=["genotype", "area"], facet="day", facet_panels=True)
    text = caption_statistics(pyf)
    assert "(day = 1)" in text and "(day = 7)" in text, text
    desc = describe_figure(pyf)
    assert "data plot (box, area.csv)" in desc and "<no file>" not in desc
