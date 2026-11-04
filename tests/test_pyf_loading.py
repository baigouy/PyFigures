"""
Tests for full .pyf object creation — requires Qt (run with pytest-qt).

Images are loaded in lazy mode (no pixel data fetched) so tests run fast
and don't need the actual image files on disk.

Run with:
    QT_QPA_PLATFORM=offscreen pytest tests/test_pyf_loading.py
"""
import os
import pytest

from batoolset.serializations.tools import deserialize_to_dict, create_object
from batoolset.drawings.shapes.group import Group
from batoolset.drawings.shapes.image2d import Image2D
from conftest import SAMPLE_DIR, needs_sample_dir

pytestmark = needs_sample_dir


def _load_pyf(path):
    """Parse a .pyf file and return the list of deserialized objects (no pixel data)."""
    with open(path, 'r', encoding='utf-8') as f:
        xml_string = f.read()
    properties = deserialize_to_dict(xml_string)
    Image2D._lazy_mode = True
    try:
        objects = create_object(list.__name__, properties)
    finally:
        Image2D._lazy_mode = False
    return objects


@pytest.mark.parametrize('filename', [
    'test.pyf',
    'another_test.pyf',
    'test_resized_256_not_reloading_deserializing_minimal_test.pyf',
    'test_templates_only.pyf',
    'test_with_comments.pyf',
    'test_with_custom_script.pyf',
    'test_with_labels.pyf',
])
def test_loads_without_error(qapp, filename):
    """Each sample .pyf must deserialize into a non-empty list of objects."""
    objects = _load_pyf(os.path.join(SAMPLE_DIR, filename))
    assert isinstance(objects, list)
    assert len(objects) > 0


def test_with_labels_has_annotated_images(qapp):
    """test_with_labels.pyf: images inside groups must have annotations."""
    objects = _load_pyf(os.path.join(SAMPLE_DIR, 'test_with_labels.pyf'))
    images_with_annotations = []
    stack = list(objects)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D) and obj.annotations:
            images_with_annotations.append(obj)
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    assert len(images_with_annotations) > 0, 'Expected images with annotations'


def test_with_labels_annotation_ranges_set_or_none(qapp):
    """TAText2D annotation ranges must be either None or a 2-element list [begin, end]."""
    from batoolset.drawings.shapes.txt2d import TAText2D
    objects = _load_pyf(os.path.join(SAMPLE_DIR, 'test_with_labels.pyf'))
    stack = list(objects)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D) and obj.annotations:
            for ann in obj.annotations:
                if not isinstance(ann, TAText2D):
                    continue
                rng = ann.range
                assert rng is None or (isinstance(rng, list) and len(rng) == 2), \
                    f'Unexpected range format: {rng}'
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)


def test_groups_have_content(qapp):
    """Groups in test.pyf must have at least one content element."""
    objects = _load_pyf(os.path.join(SAMPLE_DIR, 'test.pyf'))
    groups = [o for o in objects if isinstance(o, Group)]
    assert len(groups) > 0, 'Expected at least one Group'
    for g in groups:
        assert g.content, f'Group {g} has empty content'


def test_images_in_lazy_mode_have_no_pixel_data(qapp):
    """Raster images loaded in lazy mode must have img=None (pixel data deferred).
    SVG images are excluded — they load via QSvgRenderer synchronously regardless of lazy mode."""
    objects = _load_pyf(os.path.join(SAMPLE_DIR, 'test.pyf'))
    stack = list(objects)
    while stack:
        obj = stack.pop()
        if type(obj) is Image2D and obj.filename is not None:
            ext = obj.filename.lower().rsplit('.', 1)[-1]
            if ext in ('svg', 'txt'):
                pass  # SVG and matplotlib-figure files load synchronously regardless of lazy mode
            else:
                assert obj.img is None, f'{obj.filename} should not have pixel data in lazy mode'
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)


def test_templates_only_all_images_are_templates(qapp):
    """test_templates_only.pyf: every Image2D must be a template (filename @template@ or None)."""
    objects = _load_pyf(os.path.join(SAMPLE_DIR, 'test_templates_only.pyf'))
    stack = list(objects)
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D):
            assert obj.filename is None or obj.filename == '@template@', \
                f'Unexpected non-template image: {obj.filename}'
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)


def test_resized_minimal_loads(qapp):
    """The minimal resized file must load and contain at least one Image2D."""
    objects = _load_pyf(os.path.join(
        SAMPLE_DIR, 'test_resized_256_not_reloading_deserializing_minimal_test.pyf'))
    stack = list(objects)
    images = []
    while stack:
        obj = stack.pop()
        if isinstance(obj, Image2D):
            images.append(obj)
        if hasattr(obj, 'content') and obj.content:
            stack.extend(obj.content)
    assert len(images) > 0
