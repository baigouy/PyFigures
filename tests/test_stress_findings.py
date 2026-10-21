"""Bugs found by the stress test of 2026-10-18 (extreme figures built through
recipes, the MCP server and the GUI): each one, fixed."""
from __future__ import annotations

import io
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

import numpy as np
import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def _png(path, h=64, w=64, value=None):
    from PIL import Image
    arr = np.full((h, w), 120, np.uint8) if value is None else value
    Image.fromarray(arr).save(path)
    return str(path)


def _recipe(tmp_path, text):
    from pyfigures.recipe import build_figure_from_recipe
    p = tmp_path / "r.yaml"
    p.write_text(text, encoding="utf-8")
    return build_figure_from_recipe(str(p))


def test_failed_recipe_leaves_no_half_built_figure(tmp_path, qapp):
    from pyfigures.recipe import RecipeError
    _png(tmp_path / "a.png")
    with pytest.raises(RecipeError) as e:
        _recipe(tmp_path, "output: f.pyf\nrows:\n  - [a.png, {image: a.png, lut: NOPE}]\n")
    assert not (tmp_path / "f.pyf").exists()
    assert not (tmp_path / "f.sources.json").exists()
    assert "ERROR" not in str(e.value)                  # one prefix, added by the caller
    # a previous figure is put back as it was
    _recipe(tmp_path, "output: f.pyf\nrows:\n  - [a.png]\n")
    good = (tmp_path / "f.pyf").read_bytes()
    with pytest.raises(RecipeError):
        _recipe(tmp_path, "output: f.pyf\nrows:\n  - [a.png, {image: a.png, lut: NOPE}]\n")
    assert (tmp_path / "f.pyf").read_bytes() == good


def test_failed_checks_still_keep_the_figure(tmp_path, qapp):
    from pyfigures.recipe import RecipeChecksFailed
    _png(tmp_path / "a.png")
    with pytest.raises(RecipeChecksFailed):
        _recipe(tmp_path, "output: f.pyf\nchecks: [integrity]\nrows:\n  - [a.png, a.png]\n")
    assert (tmp_path / "f.pyf").exists()


def test_files_that_are_not_images_are_refused(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    (tmp_path / "text.png").write_text("hello")
    (tmp_path / "empty.tif").write_bytes(b"")
    for bad in ("text.png", "empty.tif"):
        res = M.add_image(pyf, [0], str(tmp_path / bad))
        assert res.startswith("ERROR") and bad in res
    assert M.add_image(pyf, [0], str(tmp_path)).startswith("ERROR")        # a folder
    assert "Added" in M.add_image(pyf, [0], _png(tmp_path / "ok.png"))
    assert M.set_image_filename(pyf, [0], 0, str(tmp_path / "text.png")).startswith("ERROR")


def test_scale_bar_needs_positive_sizes(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(tmp_path / "a.png", 400, 400))
    assert M.set_scale_bar(pyf, [0], 0, 10, px_to_unit=-1).startswith("ERROR")
    assert M.set_scale_bar(pyf, [0], 0, 10, px_to_unit=0).startswith("ERROR")
    assert M.set_scale_bar(pyf, [0], 0, -3, px_to_unit=0.1).startswith("ERROR")
    assert not M.set_scale_bar(pyf, [0], 0, 10, px_to_unit=0.1).startswith("ERROR")


def test_plot_of_a_csv_without_numbers_is_refused(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    (tmp_path / "empty.csv").write_text("")
    (tmp_path / "header.csv").write_text("A,B\n")
    (tmp_path / "ok.csv").write_text("A;B\n1;2\n3;4\n")
    for name in ("empty.csv", "header.csv"):
        assert M.add_data_plot(pyf, [0], str(tmp_path / name)).startswith("ERROR")
    from pyfigures.mcp_tools.content import _csv_number_count
    assert _csv_number_count(str(tmp_path / "ok.csv")) == 4


def test_orientation_words(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    for word, expected in (("vertical", "Y"), ("column", "Y"), ("horizontal", "X"), ("row", "X")):
        assert not M.set_orientation(pyf, [0], word).startswith("ERROR")
        assert f'""{expected}""' in open(pyf, encoding="utf-8").read()
    assert M.set_orientation(pyf, [0], "diagonal").startswith("ERROR")
    _png(tmp_path / "a.png")
    _recipe(tmp_path, "output: g.pyf\nrows:\n  - {panels: [a.png, a.png], orientation: vertical}\n")


def test_squeezed_panels_and_extra_frames_are_reported(tmp_path, qapp):
    import tifffile
    stack = tmp_path / "t.tif"
    tifffile.imwrite(stack, np.zeros((40, 32, 32), np.uint8), imagej=True, metadata={"axes": "TYX"})
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    res = M.add_stack_montage(pyf, str(stack), axis="t", frames=500, spacing=20, columns=40)
    assert "40 are shown" in res
    assert "less than" in res and "too narrow" in res


def test_pptx_of_a_figure_under_one_inch(tmp_path, qapp):
    pptx = pytest.importorskip("pptx")
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(tmp_path / "strip.png", 4, 400))
    out = str(tmp_path / "f.pptx")
    res = M.export_pptx(pyf, out)
    assert not res.startswith("ERROR"), res
    prs = pptx.Presentation(out)
    assert prs.slide_height >= 914400


def test_preview_is_flattened_on_white(tmp_path, qapp):
    from PIL import Image
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_equation(pyf, [0], r"\alpha = \beta")
    im = Image.open(io.BytesIO(M.render_preview(pyf).data))
    assert im.mode == "RGB"
    assert np.asarray(im).max() == 255                     # white page, black formula


def test_nan_and_inf_pixels_do_not_black_out_the_image(qapp):
    from batoolset.drawings.shapes.image2d import _normalize_to_uint8
    a = np.linspace(0, 1, 100, dtype=np.float32).reshape(10, 10)
    a[0, 0] = np.nan
    a[0, 1] = np.inf
    a[0, 2] = -np.inf
    out = _normalize_to_uint8(a, np.nanmin(a), np.nanmax(a))     # -inf, inf
    assert out[9, 9] == 255 and out[1, 0] < out[9, 9]
    out = _normalize_to_uint8(a, np.nan, np.nan)
    assert out.max() == 255


def test_cmyk_jpeg_is_read_as_rgb(tmp_path):
    from PIL import Image
    from batoolset.img import Img
    rgb = np.zeros((20, 30, 3), np.uint8)
    rgb[:, :10] = (255, 0, 0)
    p = str(tmp_path / "c.jpg")
    Image.fromarray(rgb).convert("CMYK").save(p, quality=100)
    img = Img(p)
    assert img.shape == (20, 30, 3)
    assert np.asarray(img)[5, 5, 0] > 200 and np.asarray(img)[5, 25].max() < 60


def test_figure_font_reaches_the_letters(tmp_path, qapp):
    _png(tmp_path / "a.png")
    _recipe(tmp_path, "output: f.pyf\nfont: {family: Arial, size: 30}\nrows:\n  - [a.png, a.png]\n")
    text = open(tmp_path / "f.pyf", encoding="utf-8").read()
    assert text.count("font-size:30pt") == 2 and "Arial" in text
    res = M.set_figure_properties(str(tmp_path / "f.pyf"), font_family="NoSuchFontAtAll")
    assert "not installed" in res


def test_new_letters_use_the_figure_font(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(tmp_path / "a.png"))
    M.set_figure_properties(pyf, font_size=22)
    from pyfigures.mcp_tools.workflow import _finalize_draft
    assert _finalize_draft(pyf, True, "top left", None, None, "µm")[0] == 1
    assert "font-size:22pt" in open(pyf, encoding="utf-8").read()


def test_failing_panel_script_is_reported(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    res = M.add_scripted_image(pyf, [0], "raise RuntimeError('boom')")
    assert "panel script failed" in res and "boom" in res


def test_bad_arguments_are_refused(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    a = _png(tmp_path / "a.png")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], a)
    assert M.add_image(pyf, [-1], a).startswith("ERROR")              # not "the last group"
    missing = M.add_image(pyf, [0], str(tmp_path / "missing.png"))     # allowed, but said
    assert "Added" in missing and "does not exist" in missing
    assert M.set_spacing(pyf, [0], -5).startswith("ERROR")
    assert M.add_annotation(pyf, [0], 0, "x", placement="middle of nowhere").startswith("ERROR")
    assert not M.add_annotation(pyf, [0], 0, "x", placement="bottom-right").startswith("ERROR")
    assert M.create_figure(str(tmp_path / "x.txt")).startswith("ERROR")
    assert M.create_figure(str(tmp_path / "g.pyf"), num_groups=-2).startswith("ERROR")


def test_empty_sub_groups_keep_their_place_and_layout(tmp_path, qapp):
    import xml.etree.ElementTree as ET
    pyf = str(tmp_path / "f.pyf")
    a = _png(tmp_path / "a.png")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], a)
    res = M.add_group(pyf, orientation="Y", parent_group_path=[0])
    assert "WARNING" not in res                                  # nothing visible changed
    M.add_image(pyf, [0, 0], a)
    M.add_image(pyf, [0, 0], a)
    root = ET.parse(pyf).getroot()
    scales = [float(s.text) for s in root.iter("scale") if s.text not in (None, "None")]
    assert scales and all(0.1 < s < 10 for s in scales)
    assert len(list(root.iter("Image2D"))) == 3


def test_figure_with_no_room_still_opens_whole(tmp_path, qapp):
    """Very deep nesting: the layout divides by zero. The loader used to drop
    the whole group (the figure opened empty and the next save lost it)."""
    from batoolset.drawings.shapes.group import Group
    from batoolset.serializations.tools import deserialize_to_dict, create_object
    pyf = str(tmp_path / "deep.pyf")
    a = _png(tmp_path / "a.png")
    M.create_figure(pyf, num_groups=1)
    path = [0]
    for level in range(13):
        M.add_image(pyf, path, a)
        M.add_group(pyf, orientation="Y" if level % 2 == 0 else "X", parent_group_path=path)
        path = path + [0]
    M.add_image(pyf, path, a)
    objs = create_object("list", deserialize_to_dict(open(pyf, encoding="utf-8").read()))
    assert [o for o in objs if isinstance(o, Group)]
    res = M.set_size(pyf, 100)
    assert res.startswith("ERROR") or "Laid out" in res
    assert open(pyf, encoding="utf-8").read().count("<Image2D>") == 14


def test_side_label_in_a_row_without_spacing(tmp_path, qapp):
    """The label cell started 512 px wide: it took the whole row and, with
    spacing 0, the layout divided by zero."""
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf)
    M.add_group(pyf, orientation="X", spacing=0)
    M.add_image(pyf, [0], _png(tmp_path / "a.png"))
    M.add_image(pyf, [0], _png(tmp_path / "b.png"))
    res = M.add_side_label(pyf, [0], "WT")
    assert "WARNING" not in res, res


def test_no_room_and_non_ascii_errors_are_clear(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(tmp_path / "a.png"))
    M.add_image(pyf, [0], _png(tmp_path / "b.png"))
    M.set_size(pyf, 4)
    res = M.export_figure(pyf, str(tmp_path / "f.png"), 72)
    assert res.startswith("ERROR") and "no room" in res and "—" in res        # UTF-8 read back
    assert "no room" in M.export_pptx(pyf, str(tmp_path / "f.pptx"))


def test_label_rows_and_side_labels_show_on_the_page(tmp_path, qapp):
    """They were white text on the (white) page: invisible."""
    _png(tmp_path / "a.png")
    _recipe(tmp_path, "output: f.pyf\nrows:\n  - {panels: [a.png, a.png], side_label: WT, "
                      "labels: [one, two]}\n")
    text = open(tmp_path / "f.pyf", encoding="utf-8").read()
    import re

    def white(label, t):
        return re.search(r"#ffffff[^<]{0,12}&gt;" + label + "&lt;", t) is not None
    assert "WT" in text and "one" in text
    assert not white("WT", text) and not white("one", text)
    _recipe(tmp_path, "output: g.pyf\nbackground: black\nrows:\n  - {panels: [a.png], side_label: KO}\n")
    assert white("KO", open(tmp_path / "g.pyf", encoding="utf-8").read())


def test_undo_right_after_an_edit_keeps_redo(tmp_path, qapp, monkeypatch):
    """The spacing spinner records its undo checkpoint 0.8 s later: an Undo
    pressed sooner was followed by that checkpoint, which re-applied the edit
    and wiped Redo."""
    import time
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], _png(tmp_path / "a.png"))
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    g.activate_or_reset_undo_redo()
    g.save_state(show_popup=False)
    start = g.paint.EZFIG_panel.space
    g.main_space_spinner.setValue(start + 7)        # timer pending, no checkpoint yet
    g.undo()
    for _ in range(30):                              # let any late timer fire
        qapp.processEvents()
        time.sleep(0.05)
    assert g.paint.EZFIG_panel.space == start
    g.redo()
    assert g.paint.EZFIG_panel.space == start + 7
    g._dirty = False


def test_merge_of_different_sizes_and_rois_outside_warn(tmp_path, qapp):
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    a = _png(tmp_path / "a.png", 64, 64)
    b = _png(tmp_path / "b.png", 30, 50)
    res = M.add_channel_merge(pyf, [0], [a, b])
    assert "\nWARNING: " in res and "differ in size" in res
    M.add_image(pyf, [0], a)
    assert "outside" in M.add_roi_rect(pyf, [0], 1, 500, 500, 10, 10)
    assert "outside" not in M.add_roi_rect(pyf, [0], 1, 10, 10, 10, 10)
    assert M.add_roi_rect(pyf, [0], 1, 10, 10, -5, 10).startswith("ERROR")
    assert "outside" in M.add_roi_line(pyf, [0], 1, -50, -50, -10, -10)
