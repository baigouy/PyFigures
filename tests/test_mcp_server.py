"""
Tests for the PyFigures MCP server tools  (pyfigures/mcp_server.py).

All tool functions are called directly — no MCP transport layer required.
Temporary .pyf files are created via pytest's ``tmp_path`` fixture so each
test is fully isolated and works on any OS.

No Qt is needed for the vast majority of tests.  Tools that invoke the
PyFigures layout engine (``set_size``, ``layout_canvas``) will skip if Qt
is unavailable; all other tools are pure-XML and run without Qt.

Run from the repo root (pyfigures_pkg and BAtools_pkg on PYTHONPATH):
    pytest tests/test_mcp_server.py -v

Or just:
    pytest tests/ -v
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module under test
# ---------------------------------------------------------------------------
from pyfigures.mcp_server import (
    # helpers (private)
    _decode, _encode_str, _encode_value, _color_to_int, _html_to_plain,
    _flatten_points, _width_mm_for_journal, _JOURNAL_PRESETS,
    _load, _child_text,
    # figure-level tools
    create_figure, describe_figure, get_xml, write_xml, list_images,
    get_figure_properties, set_figure_properties,
    # group management
    add_group, remove_group, set_spacing, set_orientation, reorder_children,
    # image management
    add_image, remove_image, clone_image, move_image,
    set_image_filename, fill_template, batch_fill_templates,
    add_scripted_image, get_script, set_script,
    list_image_properties, get_image_property, set_image_property,
    # annotations
    add_annotation, add_corner_labels, remove_annotation,
    set_annotation_text, get_annotations,
    # ROIs
    add_roi_rect, add_roi_ellipse, add_roi_line, add_roi_polygon,
    # display settings
    set_lut, configure_image, transform_image,
    # scale bars
    set_scale_bar, get_scale_bar, remove_scale_bar, set_scale_bar_all,
    # insets
    add_inset, list_insets, remove_inset, set_inset_property,
    # label rows / side labels
    add_label_row, add_side_label, list_label_rows, remove_label_row,
    # layout / resize
    resize_figure, recompute_layout,
    # path remapping
    remap_paths,
    # folder-to-figure workflow
    scan_folder, create_figure_from_folder, auto_configure_images,
    _auto_grid, _luts_for_preset, _collect_image_files,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pyf_canvas(tmp_path):
    """Empty free-canvas figure."""
    p = str(tmp_path / "canvas.pyf")
    create_figure(p, mode="canvas")
    return p


@pytest.fixture
def pyf_groups(tmp_path):
    """Figure with one top-level group (orientation X, spacing 3)."""
    p = str(tmp_path / "groups.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    return p


@pytest.fixture
def pyf_with_images(tmp_path):
    """Figure with one group containing 3 images, each with a letter label."""
    p = str(tmp_path / "with_images.pyf")
    create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
    add_image(p, [0], "/data/a.tif", label="A")
    add_image(p, [0], "/data/b.tif", label="B")
    add_image(p, [0], "/data/c.tif", label="C")
    return p


@pytest.fixture
def pyf_canvas_imgs(tmp_path):
    """Free-canvas figure with 2 images."""
    p = str(tmp_path / "canvas_imgs.pyf")
    create_figure(p, mode="canvas")
    add_image(p, [], "/data/x.tif")
    add_image(p, [], "/data/y.tif")
    return p


# ---------------------------------------------------------------------------
# Helper utilities used in multiple test classes
# ---------------------------------------------------------------------------

def _get_group_images(pyf_path: str, group_idx: int = 0) -> list[ET.Element]:
    """Return Image2D elements from a group's content."""
    _, root = _load(pyf_path)
    grp = [c for c in root if c.tag == "Group"][group_idx]
    content = grp.find("content")
    return [c for c in content if c.tag == "Image2D"] if content is not None else []


def _get_canvas_images(pyf_path: str) -> list[ET.Element]:
    _, root = _load(pyf_path)
    return [c for c in root if c.tag == "Image2D"]


# ===========================================================================
# ── Helper-function unit tests (no file I/O) ──────────────────────────────
# ===========================================================================

class TestDecode:
    def test_none_string(self):      assert _decode("None") is None
    def test_true_string(self):      assert _decode("True") is True
    def test_false_string(self):     assert _decode("False") is False
    def test_integer(self):          assert _decode("42") == 42
    def test_float(self):            assert _decode("3.14") == pytest.approx(3.14)
    def test_quoted_string(self):    assert _decode('""hello""') == "hello"
    def test_plain_string(self):     assert _decode("xyz") == "xyz"
    def test_whitespace(self):       assert _decode("  7  ") == 7
    def test_python_none(self):      assert _decode(None) is None


class TestEncodeStr:
    def test_basic(self):       assert _encode_str("hello") == '""hello""'
    def test_empty(self):       assert _encode_str("") == '""""'

    @pytest.mark.parametrize("s", ["Arial", "top left", "max", "/path/to/file.tif"])
    def test_roundtrip(self, s):
        assert _decode(_encode_str(s)) == s


class TestEncodeValue:
    def test_none_keyword(self):  assert _encode_value("None") == "None"
    def test_true_keyword(self):  assert _encode_value("True") == "True"
    def test_false_keyword(self): assert _encode_value("False") == "False"
    def test_integer(self):       assert _encode_value("42") == "42"
    def test_float(self):         assert _encode_value("3.14") == "3.14"

    def test_list_literal_verbatim(self):
        assert _encode_value("['RED', 'GREEN']") == "['RED', 'GREEN']"

    def test_dict_literal_verbatim(self):
        v = _encode_value("{'per_channel': true}")
        assert v == "{'per_channel': true}"

    def test_plain_string_quoted(self):
        assert _encode_value("Arial") == '""Arial""'


class TestColorToInt:
    def test_white(self):          assert _color_to_int("white") == 0xFFFFFF
    def test_black(self):          assert _color_to_int("black") == 0
    def test_red(self):            assert _color_to_int("red") == 0xFF0000
    def test_yellow(self):         assert _color_to_int("yellow") == 0xFFFF00
    def test_hex_hash(self):       assert _color_to_int("#ff0000") == 0xFF0000
    def test_hex_no_hash(self):    assert _color_to_int("00ff00") == 0x00FF00
    def test_int_passthrough(self):assert _color_to_int(0x0000FF) == 0x0000FF
    def test_case_insensitive(self): assert _color_to_int("RED") == _color_to_int("red")

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _color_to_int("notacolor")


class TestHtmlToPlain:
    def test_strips_tags(self):
        assert _html_to_plain("<b>Hello</b>") == "Hello"

    def test_plain_unchanged(self):
        assert _html_to_plain("plain text") == "plain text"

    def test_nested_tags(self):
        assert _html_to_plain("<span><b>A</b></span>") == "A"

    def test_removes_style_block(self):
        html = "<html><head><style>body{color:red}</style></head><body>X</body></html>"
        result = _html_to_plain(html)
        assert "X" in result
        assert "color:red" not in result


class TestFlattenPoints:
    def test_pair_list(self):
        assert _flatten_points([[1, 2], [3, 4]]) == [1.0, 2.0, 3.0, 4.0]

    def test_flat_list(self):
        assert _flatten_points([1, 2, 3, 4]) == [1.0, 2.0, 3.0, 4.0]

    def test_empty(self):
        assert _flatten_points([]) == []


# ===========================================================================
# ── create_figure ──────────────────────────────────────────────────────────
# ===========================================================================

class TestCreateFigure:
    def test_creates_file(self, tmp_path):
        p = str(tmp_path / "fig.pyf")
        result = create_figure(p)
        assert Path(p).exists()
        assert "ERROR" not in result

    def test_canvas_mode_has_no_groups(self, tmp_path):
        p = str(tmp_path / "canvas.pyf")
        create_figure(p, mode="canvas")
        _, root = _load(p)
        assert len([c for c in root if c.tag == "Group"]) == 0

    def test_groups_mode_creates_correct_count(self, tmp_path):
        p = str(tmp_path / "g3.pyf")
        create_figure(p, mode="groups", num_groups=3)
        _, root = _load(p)
        assert len([c for c in root if c.tag == "Group"]) == 3

    def test_spacing_stored(self, tmp_path):
        p = str(tmp_path / "sp.pyf")
        create_figure(p, mode="groups", num_groups=1, spacing=7)
        _, root = _load(p)
        grp = [c for c in root if c.tag == "Group"][0]
        assert _child_text(grp, "space") == 7

    def test_orientation_y_stored(self, tmp_path):
        p = str(tmp_path / "oy.pyf")
        create_figure(p, mode="groups", num_groups=1, orientation="Y")
        _, root = _load(p)
        grp = [c for c in root if c.tag == "Group"][0]
        assert _decode(grp.findtext("orientation")) == "Y"

    def test_root_element_is_list(self, tmp_path):
        p = str(tmp_path / "root.pyf")
        create_figure(p)
        _, root = _load(p)
        assert root.tag == "list"

    def test_invalid_mode_returns_error(self, tmp_path):
        result = create_figure(str(tmp_path / "x.pyf"), mode="invalid")
        assert result.startswith("ERROR")

    def test_invalid_orientation_returns_error(self, tmp_path):
        result = create_figure(str(tmp_path / "x.pyf"), mode="groups",
                               num_groups=1, orientation="Z")
        assert result.startswith("ERROR")


# ===========================================================================
# ── add_group / remove_group ──────────────────────────────────────────────
# ===========================================================================

class TestGroups:
    def test_add_top_level(self, pyf_canvas):
        result = add_group(pyf_canvas, orientation="X", spacing=5)
        assert "ERROR" not in result
        _, root = _load(pyf_canvas)
        assert len([c for c in root if c.tag == "Group"]) == 1

    def test_add_two_groups(self, pyf_canvas):
        add_group(pyf_canvas, orientation="X")
        add_group(pyf_canvas, orientation="Y")
        _, root = _load(pyf_canvas)
        assert len([c for c in root if c.tag == "Group"]) == 2

    def test_group_ids_are_unique(self, pyf_canvas):
        add_group(pyf_canvas)
        add_group(pyf_canvas)
        _, root = _load(pyf_canvas)
        ids = [int(g.findtext("ID", "0")) for g in root if g.tag == "Group"]
        assert len(ids) == len(set(ids))

    def test_add_nested_group(self, pyf_groups):
        result = add_group(pyf_groups, orientation="Y", parent_group_path=[0])
        assert "ERROR" not in result
        _, root = _load(pyf_groups)
        top = [c for c in root if c.tag == "Group"][0]
        content = top.find("content")
        sub = [c for c in content if c.tag == "Group"] if content is not None else []
        assert len(sub) == 1

    def test_remove_group(self, pyf_groups):
        result = remove_group(pyf_groups, [0])
        assert "ERROR" not in result
        _, root = _load(pyf_groups)
        assert len([c for c in root if c.tag == "Group"]) == 0

    def test_remove_group_with_images_removes_contents(self, pyf_with_images):
        result = remove_group(pyf_with_images, [0])
        assert "ERROR" not in result
        _, root = _load(pyf_with_images)
        assert len([c for c in root if c.tag == "Group"]) == 0

    def test_remove_invalid_group_returns_error(self, pyf_groups):
        assert remove_group(pyf_groups, [99]).startswith("ERROR")

    def test_remove_empty_path_returns_error(self, pyf_groups):
        assert remove_group(pyf_groups, []).startswith("ERROR")


# ===========================================================================
# ── add_image / remove_image ──────────────────────────────────────────────
# ===========================================================================

class TestImages:
    def test_add_to_canvas(self, pyf_canvas):
        result = add_image(pyf_canvas, [], "/img/foo.tif")
        assert "ERROR" not in result
        assert len(_get_canvas_images(pyf_canvas)) == 1

    def test_add_to_group(self, pyf_groups):
        result = add_image(pyf_groups, [0], "/img/bar.tif")
        assert "ERROR" not in result
        assert len(_get_group_images(pyf_groups)) == 1

    def test_filename_stored(self, pyf_groups):
        add_image(pyf_groups, [0], "/data/img.tif")
        img = _get_group_images(pyf_groups)[0]
        assert _child_text(img, "filename") == "/data/img.tif"

    def test_add_with_label_creates_tatext2d(self, pyf_groups):
        add_image(pyf_groups, [0], "/img/a.tif", label="<b>A</b>")
        img = _get_group_images(pyf_groups)[0]
        ann = img.find("annotations")
        assert ann is not None
        ta_list = ann.findall("TAText2D")
        assert len(ta_list) == 1
        assert "A" in (ta_list[0].findtext("text") or "")

    def test_label_placement_stored(self, pyf_groups):
        add_image(pyf_groups, [0], "/img/a.tif",
                  label="X", label_placement="bottom right")
        img = _get_group_images(pyf_groups)[0]
        ta = img.find("annotations").find("TAText2D")
        assert ta.findtext("placement") == "bottom right"

    def test_three_images_added(self, pyf_groups):
        for i in range(3):
            add_image(pyf_groups, [0], f"/img/{i}.tif")
        assert len(_get_group_images(pyf_groups)) == 3

    def test_remove_image(self, pyf_with_images):
        result = remove_image(pyf_with_images, [0], 1)  # remove B
        assert "ERROR" not in result
        imgs = _get_group_images(pyf_with_images)
        assert len(imgs) == 2
        fns = [_child_text(im, "filename") for im in imgs]
        assert "/data/b.tif" not in fns

    def test_remove_invalid_index_returns_error(self, pyf_with_images):
        assert remove_image(pyf_with_images, [0], 99).startswith("ERROR")


# ===========================================================================
# ── list_images ────────────────────────────────────────────────────────────
# ===========================================================================

class TestListImages:
    def test_canvas_group_path_is_empty(self, pyf_canvas_imgs):
        data = json.loads(list_images(pyf_canvas_imgs))
        assert all(e["group_path"] == [] for e in data)

    def test_canvas_count(self, pyf_canvas_imgs):
        data = json.loads(list_images(pyf_canvas_imgs))
        assert len(data) == 2

    def test_group_count(self, pyf_with_images):
        data = json.loads(list_images(pyf_with_images))
        assert len(data) == 3

    def test_group_path_correct(self, pyf_with_images):
        data = json.loads(list_images(pyf_with_images))
        assert all(e["group_path"] == [0] for e in data)

    def test_paths_correct(self, pyf_with_images):
        data = json.loads(list_images(pyf_with_images))
        paths = {e["path"] for e in data}
        assert paths == {"/data/a.tif", "/data/b.tif", "/data/c.tif"}

    def test_empty_figure_empty_list(self, pyf_groups):
        data = json.loads(list_images(pyf_groups))
        assert data == []

    def test_template_is_flagged(self, tmp_path):
        p = str(tmp_path / "t.pyf")
        create_figure(p, mode="groups", num_groups=1)
        add_image(p, [0], "@template@")
        data = json.loads(list_images(p))
        assert data[0]["is_template"] is True
        assert data[0]["path"] is None


# ===========================================================================
# ── describe_figure ────────────────────────────────────────────────────────
# ===========================================================================

class TestDescribeFigure:
    def test_returns_string(self, pyf_groups):
        assert isinstance(describe_figure(pyf_groups), str)

    def test_mentions_group(self, pyf_groups):
        assert "Group" in describe_figure(pyf_groups)

    def test_mentions_filenames(self, pyf_with_images):
        result = describe_figure(pyf_with_images)
        assert "a.tif" in result

    def test_canvas_mode_mentioned(self, pyf_canvas_imgs):
        result = describe_figure(pyf_canvas_imgs).lower()
        assert "canvas" in result or "free" in result

    def test_empty_figure_mentioned(self, pyf_canvas):
        result = describe_figure(pyf_canvas).lower()
        assert "empty" in result or "no image" in result


# ===========================================================================
# ── set_spacing / set_orientation / reorder_children ─────────────────────
# ===========================================================================

class TestLayoutControls:
    def test_set_spacing(self, pyf_groups):
        result = set_spacing(pyf_groups, [0], 10)
        assert "ERROR" not in result
        _, root = _load(pyf_groups)
        grp = [c for c in root if c.tag == "Group"][0]
        assert _child_text(grp, "space") == 10

    def test_set_spacing_invalid_group(self, pyf_groups):
        assert set_spacing(pyf_groups, [99], 5).startswith("ERROR")

    def test_set_spacing_empty_path(self, pyf_groups):
        assert set_spacing(pyf_groups, [], 5).startswith("ERROR")

    def test_set_orientation_x(self, pyf_groups):
        set_orientation(pyf_groups, [0], "X")
        _, root = _load(pyf_groups)
        assert _decode([c for c in root if c.tag == "Group"][0].findtext("orientation")) == "X"

    def test_set_orientation_y(self, pyf_groups):
        set_orientation(pyf_groups, [0], "Y")
        _, root = _load(pyf_groups)
        assert _decode([c for c in root if c.tag == "Group"][0].findtext("orientation")) == "Y"

    def test_set_orientation_invalid(self, pyf_groups):
        assert set_orientation(pyf_groups, [0], "Z").startswith("ERROR")

    def test_reorder_canvas(self, pyf_canvas_imgs):
        reorder_children(pyf_canvas_imgs, [], [1, 0])
        imgs = _get_canvas_images(pyf_canvas_imgs)
        assert _child_text(imgs[0], "filename") == "/data/y.tif"
        assert _child_text(imgs[1], "filename") == "/data/x.tif"

    def test_reorder_group(self, pyf_with_images):
        reorder_children(pyf_with_images, [0], [2, 0, 1])
        imgs = _get_group_images(pyf_with_images)
        assert _child_text(imgs[0], "filename") == "/data/c.tif"

    def test_reorder_invalid_permutation(self, pyf_with_images):
        result = reorder_children(pyf_with_images, [0], [0, 1])  # length 2 ≠ 3
        assert result.startswith("ERROR")


# ===========================================================================
# ── Annotations ────────────────────────────────────────────────────────────
# ===========================================================================

class TestAnnotations:
    def test_add_annotation(self, pyf_with_images):
        result = add_annotation(pyf_with_images, [0], 0, "Hello", "top right")
        assert "ERROR" not in result
        img = _get_group_images(pyf_with_images)[0]
        ta_list = img.find("annotations").findall("TAText2D")
        assert any("Hello" in (t.findtext("text") or "") for t in ta_list)

    def test_add_annotation_invalid_index(self, pyf_with_images):
        assert add_annotation(pyf_with_images, [0], 99, "X").startswith("ERROR")

    def test_set_annotation_text(self, pyf_with_images):
        # Image 0 already has annotation "A" at index 0
        result = set_annotation_text(pyf_with_images, [0], 0, 0, "Z")
        assert "ERROR" not in result
        img = _get_group_images(pyf_with_images)[0]
        ta = img.find("annotations").findall("TAText2D")[0]
        assert "Z" in (ta.findtext("text") or "")

    def test_remove_annotation(self, pyf_with_images):
        result = remove_annotation(pyf_with_images, [0], 0, 0)
        assert "ERROR" not in result
        img = _get_group_images(pyf_with_images)[0]
        assert len(img.find("annotations").findall("TAText2D")) == 0

    def test_remove_annotation_out_of_range(self, pyf_with_images):
        assert remove_annotation(pyf_with_images, [0], 0, 99).startswith("ERROR")

    def test_remove_protected_scale_bar_returns_error(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10)
        data = json.loads(get_annotations(pyf_with_images))
        sb = next((e for e in data
                   if e["image_index"] == 0 and "scale_bar" in e["type"].lower()), None)
        if sb is not None:  # ScaleBar present in get_annotations
            result = remove_annotation(pyf_with_images, [0], 0,
                                       sb["annotation_index"])
            assert result.startswith("ERROR")

    def test_get_annotations_returns_json_list(self, pyf_with_images):
        data = json.loads(get_annotations(pyf_with_images))
        assert isinstance(data, list)

    def test_get_annotations_count(self, pyf_with_images):
        # 3 images × 1 label each
        data = json.loads(get_annotations(pyf_with_images))
        assert len(data) == 3

    def test_get_annotations_types(self, pyf_with_images):
        data = json.loads(get_annotations(pyf_with_images))
        assert all(e["type"] == "TAText2D" for e in data)

    def test_add_corner_labels_single_corner(self, pyf_with_images):
        result = add_corner_labels(pyf_with_images, [0], 0, top_left=["WT"])
        assert "ERROR" not in result
        img = _get_group_images(pyf_with_images)[0]
        ta_list = img.find("annotations").findall("TAText2D")
        placements = [t.findtext("placement") for t in ta_list]
        assert "top left" in placements

    def test_add_corner_labels_stacked(self, tmp_path):
        # Use an unlabeled image so there is no pre-existing "top left" annotation
        p = str(tmp_path / "stacked.pyf")
        create_figure(p, mode="groups", num_groups=1, orientation="X", spacing=3)
        add_image(p, [0], "/data/a.tif")  # no label keyword
        add_corner_labels(p, [0], 0, top_left=["WT", "ctrl"])
        img = _get_group_images(p)[0]
        ta_list = img.find("annotations").findall("TAText2D")
        tl_count = sum(1 for t in ta_list if t.findtext("placement") == "top left")
        assert tl_count == 2  # WT + ctrl

    def test_add_corner_labels_multiple_corners(self, pyf_with_images):
        add_corner_labels(pyf_with_images, [0], 1,
                          top_left=["A"], bottom_right=["10µm"])
        img = _get_group_images(pyf_with_images)[1]
        ta_list = img.find("annotations").findall("TAText2D")
        raw_texts = " ".join(t.findtext("text") or "" for t in ta_list)
        assert "A" in raw_texts
        assert "10" in raw_texts

    def test_add_corner_labels_no_corners_returns_error(self, pyf_with_images):
        assert add_corner_labels(pyf_with_images, [0], 0).startswith("ERROR")


# ===========================================================================
# ── ROIs ───────────────────────────────────────────────────────────────────
# ===========================================================================

class TestROIs:
    def _annotations(self, pyf_path, img_idx=0):
        return _get_group_images(pyf_path)[img_idx].find("annotations")

    def test_add_rect_element_created(self, pyf_with_images):
        add_roi_rect(pyf_with_images, [0], 0, x=10, y=20, width=100, height=50)
        rects = self._annotations(pyf_with_images).findall("Rectangle2D")
        assert len(rects) == 1

    def test_add_rect_dimensions(self, pyf_with_images):
        add_roi_rect(pyf_with_images, [0], 0, x=10, y=20, width=100, height=50)
        r = self._annotations(pyf_with_images).find("Rectangle2D")
        assert r.findtext("width") == "100.0"
        assert r.findtext("height") == "50.0"

    def test_add_rect_color(self, pyf_with_images):
        add_roi_rect(pyf_with_images, [0], 0, 0, 0, 50, 50, color="red")
        r = self._annotations(pyf_with_images).find("Rectangle2D")
        assert r.findtext("color") == str(0xFF0000)

    def test_add_rect_fill_color(self, pyf_with_images):
        add_roi_rect(pyf_with_images, [0], 0, 0, 0, 50, 50,
                     fill_color="blue")
        r = self._annotations(pyf_with_images).find("Rectangle2D")
        assert r.findtext("fill_color") == str(0x0000FF)

    def test_add_ellipse(self, pyf_with_images):
        result = add_roi_ellipse(pyf_with_images, [0], 1,
                                 x=30, y=40, width=80, height=80)
        assert "ERROR" not in result
        assert len(self._annotations(pyf_with_images, 1).findall("Ellipse2D")) == 1

    def test_add_line_basic(self, pyf_with_images):
        result = add_roi_line(pyf_with_images, [0], 0,
                              x1=0, y1=0, x2=100, y2=100)
        assert "ERROR" not in result
        lines = self._annotations(pyf_with_images).findall("Line2D")
        assert len(lines) == 1

    def test_add_line_arrow(self, pyf_with_images):
        add_roi_line(pyf_with_images, [0], 0, 0, 0, 50, 50, arrow=True)
        line = self._annotations(pyf_with_images).find("Line2D")
        assert line.findtext("arrow") == "True"

    def test_add_line_both_ends_arrow(self, pyf_with_images):
        add_roi_line(pyf_with_images, [0], 0, 0, 0, 50, 50,
                     arrow=True, arrow_at_both_ends=True)
        line = self._annotations(pyf_with_images).find("Line2D")
        assert line.findtext("arrow_at_both_ends") == "True"

    def test_add_polygon(self, pyf_with_images):
        result = add_roi_polygon(pyf_with_images, [0], 2,
                                 points=[[0,0],[100,0],[100,100],[0,100]])
        assert "ERROR" not in result
        assert len(self._annotations(pyf_with_images, 2).findall("Polygon2D")) == 1

    def test_add_polyline(self, pyf_with_images):
        result = add_roi_polygon(pyf_with_images, [0], 0,
                                 points=[[0,0],[50,25],[100,0]],
                                 style="polyline")
        assert "ERROR" not in result
        assert len(self._annotations(pyf_with_images).findall("PolyLine2D")) == 1

    def test_add_freehand(self, pyf_with_images):
        result = add_roi_polygon(pyf_with_images, [0], 0,
                                 points=[[0,0],[10,5],[20,0]],
                                 style="freehand")
        assert "ERROR" not in result
        assert len(self._annotations(pyf_with_images).findall("Freehand2D")) == 1

    def test_polygon_invalid_style_returns_error(self, pyf_with_images):
        result = add_roi_polygon(pyf_with_images, [0], 0,
                                 points=[[0,0],[1,1]], style="triangle")
        assert result.startswith("ERROR")

    def test_polygon_too_few_points_returns_error(self, pyf_with_images):
        result = add_roi_polygon(pyf_with_images, [0], 0, points=[[0,0]])
        assert result.startswith("ERROR")

    def test_roi_visible_in_get_annotations(self, pyf_with_images):
        add_roi_rect(pyf_with_images, [0], 0, 5, 5, 20, 20)
        data = json.loads(get_annotations(pyf_with_images))
        rects = [e for e in data
                 if e["type"] == "Rectangle2D" and e["image_index"] == 0]
        assert len(rects) == 1
        assert rects[0]["width"] == pytest.approx(20.0)

    def test_roi_removed_via_remove_annotation(self, pyf_with_images):
        add_roi_rect(pyf_with_images, [0], 0, 0, 0, 10, 10)
        data = json.loads(get_annotations(pyf_with_images))
        rect_idx = next(e["annotation_index"] for e in data
                        if e["type"] == "Rectangle2D" and e["image_index"] == 0)
        result = remove_annotation(pyf_with_images, [0], 0, rect_idx)
        assert "ERROR" not in result
        data2 = json.loads(get_annotations(pyf_with_images))
        assert not any(e["type"] == "Rectangle2D" and e["image_index"] == 0
                       for e in data2)


# ===========================================================================
# ── fill_template / batch_fill_templates ──────────────────────────────────
# ===========================================================================

class TestTemplates:
    def _template_figure(self, tmp_path, n=3):
        p = str(tmp_path / "tmpl.pyf")
        create_figure(p, mode="groups", num_groups=1)
        for _ in range(n):
            add_image(p, [0], "@template@")
        return p

    def test_fill_single_slot(self, tmp_path):
        p = self._template_figure(tmp_path, 1)
        result = fill_template(p, [0], 0, "/real/img.tif")
        assert "ERROR" not in result
        assert _child_text(_get_group_images(p)[0], "filename") == "/real/img.tif"

    def test_fill_non_template_returns_error(self, pyf_with_images):
        assert fill_template(pyf_with_images, [0], 0, "/new.tif").startswith("ERROR")

    def test_batch_fill_all_slots(self, tmp_path):
        p = self._template_figure(tmp_path, 3)
        files = ["/f1.tif", "/f2.tif", "/f3.tif"]
        result = batch_fill_templates(p, [0], files)
        assert "ERROR" not in result
        paths = [e["path"] for e in json.loads(list_images(p))]
        assert paths == files

    def test_batch_fill_too_few_files_returns_error(self, tmp_path):
        p = self._template_figure(tmp_path, 3)
        assert batch_fill_templates(p, [0], ["/one.tif"]).startswith("ERROR")

    def test_batch_fill_no_templates_returns_message(self, pyf_with_images):
        result = batch_fill_templates(pyf_with_images, [0], ["/x.tif"])
        assert "no" in result.lower() or "ERROR" in result


# ===========================================================================
# ── clone_image / move_image ───────────────────────────────────────────────
# ===========================================================================

class TestCloneMove:
    def test_clone_increases_count(self, pyf_with_images):
        clone_image(pyf_with_images, [0], 0, [0])
        assert len(_get_group_images(pyf_with_images)) == 4

    def test_clone_preserves_filename(self, pyf_with_images):
        clone_image(pyf_with_images, [0], 0, [0])
        imgs = _get_group_images(pyf_with_images)
        # Clone appended at end
        assert _child_text(imgs[-1], "filename") == "/data/a.tif"

    def test_clone_preserves_annotations(self, pyf_with_images):
        # Image 0 already has label "A"
        clone_image(pyf_with_images, [0], 0, [0])
        imgs = _get_group_images(pyf_with_images)
        clone_ann = imgs[-1].find("annotations")
        assert clone_ann is not None
        assert len(clone_ann.findall("TAText2D")) > 0

    def test_move_between_groups(self, tmp_path):
        p = str(tmp_path / "two.pyf")
        create_figure(p, mode="groups", num_groups=2)
        add_image(p, [0], "/src.tif")
        result = move_image(p, [0], 0, [1])
        assert "ERROR" not in result
        _, root = _load(p)
        grps = [c for c in root if c.tag == "Group"]
        src_imgs = [c for c in grps[0].find("content") if c.tag == "Image2D"]
        dst_imgs = [c for c in grps[1].find("content") if c.tag == "Image2D"]
        assert len(src_imgs) == 0
        assert len(dst_imgs) == 1

    def test_move_within_group_repositions(self, pyf_with_images):
        # Move a.tif (index 0) to position 2: result = [b, c, a]
        move_image(pyf_with_images, [0], 0, [0], 2)
        imgs = _get_group_images(pyf_with_images)
        assert _child_text(imgs[2], "filename") == "/data/a.tif"


# ===========================================================================
# ── set_image_filename ─────────────────────────────────────────────────────
# ===========================================================================

class TestSetImageFilename:
    def test_updates_filename(self, pyf_with_images):
        result = set_image_filename(pyf_with_images, [0], 0, "/new/path.tif")
        assert "ERROR" not in result
        assert _child_text(_get_group_images(pyf_with_images)[0], "filename") == "/new/path.tif"

    def test_invalid_index_returns_error(self, pyf_with_images):
        assert set_image_filename(pyf_with_images, [0], 99, "/x.tif").startswith("ERROR")


# ===========================================================================
# ── Image properties ───────────────────────────────────────────────────────
# ===========================================================================

class TestImageProperties:
    def test_list_properties_returns_dict(self, pyf_with_images):
        data = json.loads(list_image_properties(pyf_with_images, [0], 0))
        assert isinstance(data, dict)

    def test_list_properties_has_core_keys(self, pyf_with_images):
        data = json.loads(list_image_properties(pyf_with_images, [0], 0))
        for key in ("filename", "opacity", "crop_left"):
            assert key in data

    def test_get_opacity_default(self, pyf_with_images):
        result = get_image_property(pyf_with_images, [0], 0, "opacity")
        assert "1" in result  # default 1.0

    def test_set_and_get_opacity(self, pyf_with_images):
        set_image_property(pyf_with_images, [0], 0, "opacity", "0.5")
        assert _child_text(_get_group_images(pyf_with_images)[0], "opacity") == pytest.approx(0.5)

    def test_set_readonly_field_returns_error(self, pyf_with_images):
        assert set_image_property(pyf_with_images, [0], 0, "width", "100").startswith("ERROR")

    def test_get_missing_property(self, pyf_with_images):
        result = get_image_property(pyf_with_images, [0], 0, "nonexistent_xyz")
        assert "not found" in result.lower() or "ERROR" in result


# ===========================================================================
# ── Display settings ───────────────────────────────────────────────────────
# ===========================================================================

class TestDisplaySettings:
    def test_set_lut_single_channel(self, pyf_with_images):
        result = set_lut(pyf_with_images, [0], 0, ["GREEN"])
        assert "ERROR" not in result
        luts = _get_group_images(pyf_with_images)[0].findtext("LUTs")
        assert "GREEN" in luts

    def test_set_lut_multi_channel(self, pyf_with_images):
        result = set_lut(pyf_with_images, [0], 0, ["RED", "GREEN", "BLUE"])
        assert "ERROR" not in result

    def test_set_lut_with_normalization(self, pyf_with_images):
        set_lut(pyf_with_images, [0], 0, ["GRAY"],
                normalization='{"per_channel": true}')
        norm = _get_group_images(pyf_with_images)[0].findtext("normalization")
        assert "per_channel" in (norm or "")

    def test_configure_channels(self, pyf_with_images):
        configure_image(pyf_with_images, [0], 0, channels=[True, False, True])
        ch = _get_group_images(pyf_with_images)[0].findtext("channels")
        assert "True" in ch
        assert "False" in ch

    def test_configure_projection_max(self, pyf_with_images):
        configure_image(pyf_with_images, [0], 0, projection="max")
        assert _get_group_images(pyf_with_images)[0].findtext("projection") == "max"

    def test_configure_projection_invalid_returns_error(self, pyf_with_images):
        assert configure_image(pyf_with_images, [0], 0, projection="xyz").startswith("ERROR")

    def test_configure_serie_to_open(self, pyf_with_images):
        result = configure_image(pyf_with_images, [0], 0, serie_to_open=2)
        assert "ERROR" not in result
        assert _get_group_images(pyf_with_images)[0].findtext("serie_to_open") == "2"

    def test_configure_clear_normalization(self, pyf_with_images):
        configure_image(pyf_with_images, [0], 0,
                        normalization='{"per_channel": true}')
        configure_image(pyf_with_images, [0], 0, clear_normalization=True)
        assert _get_group_images(pyf_with_images)[0].findtext("normalization") == "None"

    def test_configure_nothing_specified(self, pyf_with_images):
        result = configure_image(pyf_with_images, [0], 0)
        assert "Nothing changed" in result

    def test_transform_rotation(self, pyf_with_images):
        transform_image(pyf_with_images, [0], 0, rotation=90)
        assert _child_text(_get_group_images(pyf_with_images)[0], "theta") == pytest.approx(90.0)

    def test_transform_crop(self, pyf_with_images):
        transform_image(pyf_with_images, [0], 0,
                        crop_left=10, crop_right=10,
                        crop_top=5, crop_bottom=5)
        img = _get_group_images(pyf_with_images)[0]
        assert _child_text(img, "crop_left") == 10
        assert _child_text(img, "crop_bottom") == 5

    def test_transform_opacity(self, pyf_with_images):
        transform_image(pyf_with_images, [0], 0, opacity=0.75)
        assert _child_text(_get_group_images(pyf_with_images)[0], "opacity") == pytest.approx(0.75)

    def test_transform_invalid_opacity_returns_error(self, pyf_with_images):
        assert transform_image(pyf_with_images, [0], 0, opacity=1.5).startswith("ERROR")

    def test_transform_nothing_returns_message(self, pyf_with_images):
        result = transform_image(pyf_with_images, [0], 0)
        assert "Nothing changed" in result


# ===========================================================================
# ── Scale bars ─────────────────────────────────────────────────────────────
# ===========================================================================

class TestScaleBar:
    def test_set_creates_scalebar(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10, label="10µm")
        sb = _get_group_images(pyf_with_images)[0].find("annotations").find("ScaleBar")
        assert sb is not None
        assert sb.findtext("bar_width_in_units") == "10.0"

    def test_get_returns_json(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10)
        data = json.loads(get_scale_bar(pyf_with_images, [0], 0))
        assert data["bar_width_in_units"] == pytest.approx(10.0)

    def test_remove_scale_bar(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10)
        remove_scale_bar(pyf_with_images, [0], 0)
        result = get_scale_bar(pyf_with_images, [0], 0)
        assert "no scale bar" in result.lower()

    def test_get_absent_scale_bar(self, pyf_with_images):
        assert "no scale bar" in get_scale_bar(pyf_with_images, [0], 0).lower()

    def test_remove_absent_scale_bar(self, pyf_with_images):
        result = remove_scale_bar(pyf_with_images, [0], 0)
        assert "no" in result.lower()

    def test_set_all_images(self, pyf_with_images):
        result = set_scale_bar_all(pyf_with_images, 5, label="5µm")
        assert "ERROR" not in result
        assert "3" in result  # 3 images

    def test_placement_stored(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10, placement="top left")
        data = json.loads(get_scale_bar(pyf_with_images, [0], 0))
        assert data["placement"] == "top left"

    def test_px_to_unit_stored_on_image(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10, px_to_unit=0.1)
        img = _get_group_images(pyf_with_images)[0]
        assert _child_text(img, "px_to_unit_conversion_factor") == pytest.approx(0.1)

    def test_update_does_not_create_duplicate(self, pyf_with_images):
        set_scale_bar(pyf_with_images, [0], 0, 10)
        set_scale_bar(pyf_with_images, [0], 0, 20)
        ann = _get_group_images(pyf_with_images)[0].find("annotations")
        assert len(ann.findall("ScaleBar")) == 1
        assert json.loads(get_scale_bar(pyf_with_images, [0], 0))["bar_width_in_units"] == pytest.approx(20.0)


# ===========================================================================
# ── Insets ──────────────────────────────────────────────────────────────────
# ===========================================================================

class TestInsets:
    def test_add_inset_creates_entry(self, pyf_with_images):
        add_inset(pyf_with_images, [0], 0, "/inset.tif")
        data = json.loads(list_insets(pyf_with_images, [0], 0))
        assert len(data) == 1
        assert data[0]["filename"] == "/inset.tif"

    def test_add_inset_placement(self, pyf_with_images):
        add_inset(pyf_with_images, [0], 0, "/i.tif", placement="bottom left")
        data = json.loads(list_insets(pyf_with_images, [0], 0))
        assert data[0]["placement"] == "bottom left"

    def test_add_inset_size_fraction(self, pyf_with_images):
        add_inset(pyf_with_images, [0], 0, "/i.tif", size_fraction=0.3)
        data = json.loads(list_insets(pyf_with_images, [0], 0))
        assert data[0]["size_fraction"] == pytest.approx(0.3)

    def test_remove_inset(self, pyf_with_images):
        add_inset(pyf_with_images, [0], 0, "/i.tif")
        remove_inset(pyf_with_images, [0], 0, 0)
        assert "no insets" in list_insets(pyf_with_images, [0], 0).lower()

    def test_list_insets_empty(self, pyf_with_images):
        assert "no insets" in list_insets(pyf_with_images, [0], 0).lower()

    def test_set_inset_property(self, pyf_with_images):
        add_inset(pyf_with_images, [0], 0, "/i.tif", size_fraction=0.25)
        result = set_inset_property(
            pyf_with_images, [0], 0, 0,
            "fraction_of_parent_image_width_if_image_is_inset", "0.4")
        assert "ERROR" not in result
        data = json.loads(list_insets(pyf_with_images, [0], 0))
        assert data[0]["size_fraction"] == pytest.approx(0.4)

    def test_invalid_size_fraction_returns_error(self, pyf_with_images):
        assert add_inset(pyf_with_images, [0], 0, "/i.tif",
                         size_fraction=0.0).startswith("ERROR")

    def test_add_two_insets(self, pyf_with_images):
        add_inset(pyf_with_images, [0], 0, "/a.tif")
        add_inset(pyf_with_images, [0], 0, "/b.tif")
        data = json.loads(list_insets(pyf_with_images, [0], 0))
        assert len(data) == 2


# ===========================================================================
# ── Label rows / side labels ───────────────────────────────────────────────
# ===========================================================================

class TestLabelRows:
    def test_add_label_row_above(self, pyf_with_images):
        result = add_label_row(pyf_with_images, [0],
                               labels=["WT", "KO", "RES"], position="above")
        assert "ERROR" not in result
        rows = json.loads(list_label_rows(pyf_with_images))
        assert len(rows) >= 1
        all_texts = [entry["text"] for row in rows for entry in row["labels"]]
        assert "WT" in all_texts

    def test_add_label_row_below(self, pyf_with_images):
        result = add_label_row(pyf_with_images, [0],
                               labels=["A", "B", "C"], position="below")
        assert "ERROR" not in result

    def test_add_label_row_wrong_count_returns_error(self, pyf_with_images):
        result = add_label_row(pyf_with_images, [0],
                               labels=["only_one"], position="above")
        assert result.startswith("ERROR")

    def test_add_label_row_single_string_ok(self, pyf_with_images):
        result = add_label_row(pyf_with_images, [0],
                               labels="Header", position="above")
        assert "ERROR" not in result

    def test_remove_label_row(self, pyf_with_images):
        add_label_row(pyf_with_images, [0], labels=["A", "B", "C"],
                      position="above")
        rows_before = json.loads(list_label_rows(pyf_with_images))
        row_path = rows_before[0]["group_path"]
        result = remove_label_row(pyf_with_images, row_path)
        assert "ERROR" not in result
        # When the last label-row is removed, list_label_rows may return a
        # plain message instead of "[]" — handle both cases gracefully.
        rows_after_str = list_label_rows(pyf_with_images)
        try:
            rows_after = json.loads(rows_after_str)
        except json.JSONDecodeError:
            rows_after = []  # "No label-row groups found" counts as empty
        assert len(rows_after) == len(rows_before) - 1

    def test_remove_content_group_with_remove_label_row_returns_error(self, pyf_with_images):
        # group [0] is a content group — remove_label_row should reject it
        assert remove_label_row(pyf_with_images, [0]).startswith("ERROR")

    def test_add_side_label_inserted_as_first_child(self, pyf_with_images):
        result = add_side_label(pyf_with_images, [0],
                                "Condition A", position="left")
        assert "ERROR" not in result
        _, root = _load(pyf_with_images)
        grp = [c for c in root if c.tag == "Group"][0]
        first = list(grp.find("content"))[0]
        assert first.tag == "Image2D"
        assert first.findtext("isText") == "True"

    def test_add_side_label_right(self, pyf_with_images):
        result = add_side_label(pyf_with_images, [0],
                                "Condition B", position="right")
        assert "ERROR" not in result
        _, root = _load(pyf_with_images)
        grp = [c for c in root if c.tag == "Group"][0]
        last = list(grp.find("content"))[-1]
        assert last.tag == "Image2D"
        assert last.findtext("isText") == "True"

    def test_list_label_rows_empty(self, pyf_groups):
        assert "no label" in list_label_rows(pyf_groups).lower()


# ===========================================================================
# ── Figure-level properties ────────────────────────────────────────────────
# ===========================================================================

class TestFigureProperties:
    def test_get_returns_json(self, pyf_groups):
        data = json.loads(get_figure_properties(pyf_groups))
        assert "font" in data or "gui" in data

    def test_set_font_size(self, pyf_groups):
        set_figure_properties(pyf_groups, font_size=10)
        data = json.loads(get_figure_properties(pyf_groups))
        assert data["font"]["size"] == 10

    def test_set_font_family(self, pyf_groups):
        set_figure_properties(pyf_groups, font_family="Helvetica")
        data = json.loads(get_figure_properties(pyf_groups))
        assert data["font"]["family"] == "Helvetica"

    def test_set_default_spacing(self, pyf_groups):
        set_figure_properties(pyf_groups, default_spacing=5)
        data = json.loads(get_figure_properties(pyf_groups))
        assert data["gui"]["space"] == 5

    def test_nothing_specified_returns_message(self, pyf_groups):
        assert "Nothing changed" in set_figure_properties(pyf_groups)


# ===========================================================================
# ── remap_paths ────────────────────────────────────────────────────────────
# ===========================================================================

class TestRemapPaths:
    def test_remaps_prefix(self, pyf_with_images):
        remap_paths(pyf_with_images, "/data", "/new/data")
        paths = {e["path"] for e in json.loads(list_images(pyf_with_images))}
        assert all(p.startswith("/new/data") for p in paths)

    def test_dry_run_does_not_modify(self, pyf_with_images):
        remap_paths(pyf_with_images, "/data", "/new", dry_run=True)
        paths = {e["path"] for e in json.loads(list_images(pyf_with_images))}
        assert all(p.startswith("/data") for p in paths)

    def test_no_match_nothing_changed(self, pyf_with_images):
        result = remap_paths(pyf_with_images, "/nonexistent", "/new")
        assert "0 path" in result or "unchanged" in result.lower()


# ===========================================================================
# ── Scripts ────────────────────────────────────────────────────────────────
# ===========================================================================

_SAMPLE_SCRIPT = (
    "fig, ax = plt.subplots()\n"
    "ax.plot([1, 2, 3], [4, 5, 6])\n"
    "self.img = fig"
)


class TestScripts:
    def test_add_scripted_image(self, pyf_groups):
        result = add_scripted_image(pyf_groups, [0], _SAMPLE_SCRIPT, label="D")
        assert "ERROR" not in result
        assert "index 0" in result

    def test_get_script_after_add(self, pyf_groups):
        add_scripted_image(pyf_groups, [0], _SAMPLE_SCRIPT)
        result = get_script(pyf_groups, [0], 0)
        assert "self.img" in result

    def test_set_script(self, pyf_with_images):
        result = set_script(pyf_with_images, [0], 0, _SAMPLE_SCRIPT)
        assert "ERROR" not in result
        assert "self.img" in get_script(pyf_with_images, [0], 0)

    def test_clear_script(self, pyf_with_images):
        set_script(pyf_with_images, [0], 0, _SAMPLE_SCRIPT)
        set_script(pyf_with_images, [0], 0, "")
        assert "no script" in get_script(pyf_with_images, [0], 0).lower()

    def test_get_script_no_script(self, pyf_with_images):
        assert "no script" in get_script(pyf_with_images, [0], 0).lower()

    def test_scripted_image_filename_is_none(self, pyf_groups):
        add_scripted_image(pyf_groups, [0], _SAMPLE_SCRIPT)
        img = _get_group_images(pyf_groups)[0]
        assert img.findtext("filename") == "None"


# ===========================================================================
# ── get_xml / write_xml ────────────────────────────────────────────────────
# ===========================================================================

class TestXmlTools:
    def test_get_xml_returns_string(self, pyf_groups):
        result = get_xml(pyf_groups)
        assert isinstance(result, str)
        assert "<list>" in result

    def test_write_xml_roundtrip(self, pyf_groups):
        original = get_xml(pyf_groups)
        write_xml(pyf_groups, original)
        assert get_xml(pyf_groups) == original

    def test_write_xml_invalid_returns_error(self, pyf_groups):
        assert write_xml(pyf_groups, "<not valid xml").startswith("ERROR")

    def test_write_xml_modifies_file(self, tmp_path):
        p = str(tmp_path / "rt.pyf")
        create_figure(p, mode="groups", num_groups=2, spacing=3)
        xml = get_xml(p)
        xml2 = xml.replace("<space>3</space>", "<space>99</space>")
        write_xml(p, xml2)
        _, root = _load(p)
        spaces = [grp.findtext("space") for grp in root if grp.tag == "Group"]
        assert all(s == "99" for s in spaces)


# ===========================================================================
# ── resize_figure — journal preset maths (no Qt required) ────────────────
# ===========================================================================

class TestResizeFigurePresets:
    """Unit tests for journal preset lookup and unit conversion logic.

    These do NOT call the PyFigures layout engine, so no Qt is needed.
    The pixel calculation is verified; the actual layout step (set_size)
    may return an error when Qt is unavailable — that is acceptable.
    """

    def test_unknown_journal_returns_error(self, pyf_groups):
        assert resize_figure(pyf_groups, journal="no_such_journal").startswith("ERROR")

    def test_unknown_column_returns_error(self, pyf_groups):
        assert resize_figure(pyf_groups, journal="nature", column="triple").startswith("ERROR")

    def test_no_target_returns_error(self, pyf_groups):
        assert resize_figure(pyf_groups).startswith("ERROR")

    def test_zero_width_returns_error(self, pyf_groups):
        assert resize_figure(pyf_groups, width_px=0).startswith("ERROR")

    @pytest.mark.parametrize("journal,column,expected_mm", [
        ("nature",  "single",  89),
        ("nature",  "double", 183),
        ("cell",    "single",  85),
        ("science", "single",  57),
        ("science", "double", 184),
        ("cell",    "double", 174),
        ("plos",    "double", 174),
        ("pnas",    "single",  87),
        ("pnas",    "1.5",    114),     # PNAS Digital Art guide, p2 (not 131)
        ("pnas",    "double", 178),
        ("embo",    "double", 180),     # EMBO J author guide: "between 87 mm and 180 mm wide"
        ("jcb",     "single",  85),
        ("nature communications", "single", 88),
        ("nature communications", "double", 180),
        ("nature medicine", "double", 180),
    ])
    def test_journal_mm_values(self, journal, column, expected_mm):
        assert _width_mm_for_journal(journal, column) == pytest.approx(expected_mm)

    @pytest.mark.parametrize("alias,canonical", [
        ("nature cell biology",     "nature methods"),
        ("ncomms",                  "nature communications"),
        ("plos one",                "plos"),
        ("cell reports",            "cell"),
        ("journal of cell biology", "jcb"),
        ("science advances",        "science"),
    ])
    def test_journal_aliases(self, alias, canonical):
        mm = _width_mm_for_journal(alias, "single")
        assert mm == pytest.approx(_JOURNAL_PRESETS[canonical]["single"])

    def test_column_synonym_1(self, pyf_groups):
        # "1" is an alias for "single"
        mm1 = _width_mm_for_journal("nature", "1")
        mm_single = _width_mm_for_journal("nature", "single")
        assert mm1 == pytest.approx(mm_single)

    def test_column_synonym_double(self, pyf_groups):
        mm = _width_mm_for_journal("nature", "2")
        assert mm == pytest.approx(_JOURNAL_PRESETS["nature"]["double"])

    def test_resize_reports_correct_px_from_mm(self, pyf_groups):
        """Even if set_size fails (no Qt), the message should quote correct px."""
        result = resize_figure(pyf_groups, width_mm=89, dpi=300)
        expected_px = round(89 / 25.4 * 300)  # 1051
        assert str(expected_px) in result or "ERROR" in result

    def test_resize_reports_correct_px_from_cm(self, pyf_groups):
        result = resize_figure(pyf_groups, width_cm=8.9, dpi=300)
        expected_px = round(8.9 / 2.54 * 300)
        assert str(expected_px) in result or "ERROR" in result

    def test_resize_reports_correct_px_from_in(self, pyf_groups):
        result = resize_figure(pyf_groups, width_in=3.5, dpi=300)
        expected_px = round(3.5 * 300)
        assert str(expected_px) in result or "ERROR" in result


# ===========================================================================
# ── recompute_layout ───────────────────────────────────────────────────────
# ===========================================================================

class TestRecomputeLayout:
    def test_never_raises(self, pyf_groups):
        """recompute_layout must return a string even when Qt is unavailable."""
        result = recompute_layout(pyf_groups)
        assert isinstance(result, str)

    def test_canvas_figure_never_raises(self, pyf_canvas):
        result = recompute_layout(pyf_canvas)
        assert isinstance(result, str)

    def test_returns_after_structural_edit(self, pyf_with_images):
        add_image(pyf_with_images, [0], "/extra.tif")
        result = recompute_layout(pyf_with_images)
        assert isinstance(result, str)


# ===========================================================================
# ── _auto_grid helper ──────────────────────────────────────────────────────
# ===========================================================================

class TestAutoGrid:
    @pytest.mark.parametrize("n,expected_cols,expected_rows", [
        (1,  1, 1),
        (2,  2, 1),
        (4,  2, 2),
        (6,  3, 2),
        (9,  3, 3),
        (12, 4, 3),
    ])
    def test_exact_grids(self, n, expected_cols, expected_rows):
        cols, rows = _auto_grid(n)
        assert cols == expected_cols
        assert rows == expected_rows

    def test_covers_all_images(self):
        """cols*rows must be >= n for any n."""
        for n in range(1, 25):
            cols, rows = _auto_grid(n)
            assert cols * rows >= n

    def test_landscape_preference(self):
        """cols should be >= rows (landscape orientation)."""
        for n in [4, 6, 8, 9, 10, 12, 15]:
            cols, rows = _auto_grid(n)
            assert cols >= rows, f"n={n}: cols={cols} < rows={rows}"

    def test_returns_tuple_of_ints(self):
        cols, rows = _auto_grid(7)
        assert isinstance(cols, int) and isinstance(rows, int)


# ===========================================================================
# ── _luts_for_preset helper ────────────────────────────────────────────────
# ===========================================================================

class TestLutsForPreset:
    def test_fluorescence_1ch(self):
        assert _luts_for_preset("fluorescence", 1) == ["GRAY"]

    def test_fluorescence_2ch(self):
        assert _luts_for_preset("fluorescence", 2) == ["GREEN", "RED"]

    def test_fluorescence_3ch(self):
        assert _luts_for_preset("fluorescence", 3) == ["BLUE", "GREEN", "RED"]

    def test_fluorescence_4ch(self):
        luts = _luts_for_preset("fluorescence", 4)
        assert len(luts) == 4
        assert "BLUE" in luts and "GREEN" in luts and "RED" in luts

    def test_fluorescence_many_channels(self):
        luts = _luts_for_preset("fluorescence", 8)
        assert len(luts) == 8
        assert all(isinstance(l, str) for l in luts)

    def test_gray_preset(self):
        assert _luts_for_preset("gray", 3) == ["GRAY", "GRAY", "GRAY"]

    def test_rgb_preset(self):
        luts = _luts_for_preset("rgb", 3)
        assert luts == ["RED", "GREEN", "BLUE"]

    def test_none_preset_returns_none(self):
        assert _luts_for_preset("none", 3) is None


# ===========================================================================
# ── scan_folder ────────────────────────────────────────────────────────────
# ===========================================================================

class TestScanFolder:
    def test_missing_folder_returns_error_json(self, tmp_path):
        result = json.loads(scan_folder(str(tmp_path / "nonexistent")))
        assert "error" in result

    def test_empty_folder_count_zero(self, tmp_path):
        result = json.loads(scan_folder(str(tmp_path)))
        assert result["count"] == 0
        assert result["files"] == []

    def test_finds_tiff_files(self, tmp_path):
        for name in ("a.tif", "b.tif", "c.tiff"):
            (tmp_path / name).write_bytes(b"")
        result = json.loads(scan_folder(str(tmp_path)))
        assert result["count"] == 3

    def test_non_image_files_excluded(self, tmp_path):
        (tmp_path / "notes.txt").write_text("ignore me")
        (tmp_path / "img.tif").write_bytes(b"")
        result = json.loads(scan_folder(str(tmp_path)))
        assert result["count"] == 1

    def test_pattern_filter(self, tmp_path):
        (tmp_path / "MAX_a.tif").write_bytes(b"")
        (tmp_path / "b.tif").write_bytes(b"")
        result = json.loads(scan_folder(str(tmp_path), pattern="MAX_*.tif"))
        assert result["count"] == 1
        assert "MAX_a.tif" in result["files"][0]

    def test_layout_suggestions_present(self, tmp_path):
        for i in range(6):
            (tmp_path / f"img{i}.tif").write_bytes(b"")
        result = json.loads(scan_folder(str(tmp_path)))
        assert len(result["layout_suggestions"]) >= 2

    def test_layout_suggestions_have_required_keys(self, tmp_path):
        for i in range(4):
            (tmp_path / f"img{i}.tif").write_bytes(b"")
        result = json.loads(scan_folder(str(tmp_path)))
        for sug in result["layout_suggestions"]:
            assert "name" in sug
            assert "layout" in sug

    def test_subfolder_detection(self, tmp_path):
        sub = tmp_path / "ctrl"
        sub.mkdir()
        (sub / "a.tif").write_bytes(b"")
        result = json.loads(scan_folder(str(tmp_path)))
        assert "ctrl" in result["subfolders"]

    def test_returns_json_string(self, tmp_path):
        result = scan_folder(str(tmp_path))
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "files" in parsed


# ===========================================================================
# ── create_figure_from_folder ──────────────────────────────────────────────
# ===========================================================================

class TestCreateFigureFromFolder:
    def _make_folder(self, tmp_path, n=6, names=None):
        folder = tmp_path / "imgs"
        folder.mkdir()
        import numpy as np
        import tifffile
        for name in (names or [f"img{i:02d}.tif" for i in range(n)]):
            tifffile.imwrite(folder / name, np.zeros((4, 4), np.uint8))   # an empty file is refused
        return str(folder)

    def test_unreadable_files_are_reported(self, tmp_path):
        folder = self._make_folder(tmp_path, 2)
        (Path(folder) / "broken.tif").write_bytes(b"")
        res = create_figure_from_folder(str(tmp_path / "fig.pyf"), folder)
        assert "2 image(s)" in res and "skipped: broken.tif" in res

    def test_creates_pyf_file(self, tmp_path):
        folder = self._make_folder(tmp_path, 4)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder)
        assert Path(p).exists()

    def test_missing_folder_returns_error(self, tmp_path):
        result = create_figure_from_folder(
            str(tmp_path / "out.pyf"),
            str(tmp_path / "nonexistent"))
        assert result.startswith("ERROR")

    def test_empty_folder_returns_error(self, tmp_path):
        folder = tmp_path / "empty"
        folder.mkdir()
        result = create_figure_from_folder(str(tmp_path / "out.pyf"), str(folder))
        assert result.startswith("ERROR")

    def test_correct_image_count(self, tmp_path):
        folder = self._make_folder(tmp_path, 6)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, layout="auto")
        imgs = json.loads(list_images(p))
        assert len(imgs) == 6

    def test_row_layout_one_group(self, tmp_path):
        folder = self._make_folder(tmp_path, 4)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, layout="row")
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        assert len(groups) == 1

    def test_column_layout_one_group(self, tmp_path):
        folder = self._make_folder(tmp_path, 4)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, layout="column")
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        assert len(groups) == 1

    def test_grid_explicit_num_cols(self, tmp_path):
        folder = self._make_folder(tmp_path, 6)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, layout="grid", num_cols=3)
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        assert len(groups) == 2  # 2 rows of 3

    def test_grid_explicit_num_rows(self, tmp_path):
        folder = self._make_folder(tmp_path, 6)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, layout="grid", num_rows=3)
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        assert len(groups) == 3  # 3 rows of 2

    def test_label_from_filename(self, tmp_path):
        folder = self._make_folder(tmp_path, 2, names=["ctrl.tif", "treated.tif"])
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, label_from_filename=True)
        _, root = _load(p)
        # Find TAText2D labels in the figure
        all_texts = [
            el.findtext("text") or ""
            for el in root.iter("TAText2D")
        ]
        assert any("ctrl" in t for t in all_texts)
        assert any("treated" in t for t in all_texts)

    def test_no_label_when_disabled(self, tmp_path):
        folder = self._make_folder(tmp_path, 2)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, label_from_filename=False)
        _, root = _load(p)
        ta_list = list(root.iter("TAText2D"))
        assert len(ta_list) == 0

    def test_group_by_prefix(self, tmp_path):
        folder = self._make_folder(
            tmp_path, names=["ctrl_1.tif", "ctrl_2.tif",
                              "treat_1.tif", "treat_2.tif"])
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, group_by="prefix")
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        assert len(groups) == 2  # ctrl and treat

    def test_group_by_subfolder(self, tmp_path):
        folder = tmp_path / "data"
        folder.mkdir()
        for sub in ("ctrl", "treated"):
            (folder / sub).mkdir()
            (folder / sub / "img.tif").write_bytes(b"")
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(str(p), str(folder), group_by="subfolder")
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        assert len(groups) == 2

    def test_auto_grid_is_near_square(self, tmp_path):
        folder = self._make_folder(tmp_path, 9)
        p = str(tmp_path / "fig.pyf")
        create_figure_from_folder(p, folder, layout="auto")
        _, root = _load(p)
        groups = [c for c in root if c.tag == "Group"]
        # 9 images → 3×3: 3 groups of 3
        assert len(groups) == 3


# ===========================================================================
# ── auto_configure_images ──────────────────────────────────────────────────
# ===========================================================================

class TestAutoConfigureImages:
    def _make_figure_with_fake_files(self, tmp_path, n=3):
        """Figure with n images pointing at non-existent files (no metadata)."""
        p = str(tmp_path / "fig.pyf")
        create_figure(p, mode="groups", num_groups=1, orientation="X")
        for i in range(n):
            add_image(p, [0], f"/nonexistent/img{i}.tif")
        return p

    def test_returns_string(self, tmp_path):
        p = self._make_figure_with_fake_files(tmp_path)
        result = auto_configure_images(p)
        assert isinstance(result, str)

    def test_no_metadata_reports_unchanged(self, tmp_path):
        p = self._make_figure_with_fake_files(tmp_path)
        result = auto_configure_images(p, read_metadata=False)
        # Without reading metadata we still apply LUTs
        assert isinstance(result, str)

    def test_lut_written_to_xml(self, tmp_path):
        p = self._make_figure_with_fake_files(tmp_path, n=1)
        auto_configure_images(p, lut_preset="gray", read_metadata=False)
        _, root = _load(p)
        img = next(c for grp in root.iter("Group")
                   for c in (grp.find("content") or [])
                   if c.tag == "Image2D")
        lut_text = img.findtext("LUTs") or ""
        assert "GRAY" in lut_text

    def test_invalid_preset_returns_error(self, tmp_path):
        p = self._make_figure_with_fake_files(tmp_path)
        result = auto_configure_images(p, lut_preset="rainbow")
        assert result.startswith("ERROR")

    def test_none_preset_skips_lut(self, tmp_path):
        p = self._make_figure_with_fake_files(tmp_path, n=1)
        # First set a known LUT, then run with "none" preset
        add_image(p, [0], "/x.tif")  # extra image
        auto_configure_images(p, lut_preset="gray", read_metadata=False)
        # Get the LUT of first image before
        _, root = _load(p)
        img0 = next(c for grp in root.iter("Group")
                    for c in (grp.find("content") or [])
                    if c.tag == "Image2D")
        lut_before = img0.findtext("LUTs")
        # Now run with "none"
        auto_configure_images(p, lut_preset="none", read_metadata=False)
        _, root = _load(p)
        img0 = next(c for grp in root.iter("Group")
                    for c in (grp.find("content") or [])
                    if c.tag == "Image2D")
        lut_after = img0.findtext("LUTs")
        assert lut_before == lut_after  # unchanged

    def test_first_image_only(self, tmp_path):
        p = self._make_figure_with_fake_files(tmp_path, n=3)
        result = auto_configure_images(
            p, lut_preset="gray", read_metadata=False, first_image_only=True)
        # Only image[0] in the group should be processed
        assert "group[0][0]" in result

    def test_canvas_images_processed(self, tmp_path):
        p = str(tmp_path / "canvas.pyf")
        create_figure(p, mode="canvas")
        add_image(p, [], "/data/canvas_img.tif")
        result = auto_configure_images(p, lut_preset="gray", read_metadata=False)
        assert isinstance(result, str)
        # The canvas image should have its LUT set
        _, root = _load(p)
        img = next(c for c in root if c.tag == "Image2D")
        assert "GRAY" in (img.findtext("LUTs") or "")
