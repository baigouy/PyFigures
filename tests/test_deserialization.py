"""
Tests for .pyf XML deserialization — no Qt required.
These verify that the XML in each sample file can be parsed into a dict
without any Qt dependency.
"""
import os
import pytest
import xml.etree.ElementTree as ET

from batoolset.serializations.tools import deserialize_to_dict
from conftest import SAMPLE_DIR


def _read_pyf(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.mark.parametrize('filename', [
    'test.pyf',
    'another_test.pyf',
    'test_resized_256_not_reloading_deserializing_minimal_test.pyf',
    'test_templates_only.pyf',
    'test_with_comments.pyf',
    'test_with_custom_script.pyf',
    'test_with_labels.pyf',
])
def test_parses_to_dict(filename):
    """Each .pyf file must parse to a non-empty dict without errors."""
    path = os.path.join(SAMPLE_DIR, filename)
    xml_string = _read_pyf(path)
    result = deserialize_to_dict(xml_string)
    assert result is not None
    assert isinstance(result, dict)


def test_root_is_list_element():
    """The XML root element must be <list>."""
    path = os.path.join(SAMPLE_DIR, 'test.pyf')
    xml_string = _read_pyf(path)
    root = ET.fromstring(xml_string)
    assert root.tag == 'list'


def test_with_labels_has_annotations():
    """test_with_labels.pyf must contain at least one TAText2D annotation."""
    path = os.path.join(SAMPLE_DIR, 'test_with_labels.pyf')
    xml_string = _read_pyf(path)
    root = ET.fromstring(xml_string)
    texts = root.findall('.//TAText2D')
    assert len(texts) > 0, 'Expected TAText2D annotation elements'


def test_with_comments_has_comments():
    """test_with_comments.pyf must have at least one non-empty user_comments field."""
    path = os.path.join(SAMPLE_DIR, 'test_with_comments.pyf')
    xml_string = _read_pyf(path)
    root = ET.fromstring(xml_string)
    comments = [el.text for el in root.findall('.//user_comments') if el.text and el.text.strip() not in ('""', "''''", '')]
    assert len(comments) > 0, 'Expected at least one non-empty user_comments'


def test_custom_script_has_script():
    """test_with_custom_script.pyf must have a non-None custom_loading_script."""
    path = os.path.join(SAMPLE_DIR, 'test_with_custom_script.pyf')
    xml_string = _read_pyf(path)
    root = ET.fromstring(xml_string)
    scripts = [el.text for el in root.findall('.//custom_loading_script')
               if el.text and el.text.strip() not in ('None', '')]
    assert len(scripts) > 0, 'Expected at least one custom_loading_script'


def test_templates_only_all_images_are_templates():
    """test_templates_only.pyf: every Image2D must have filename @template@ or be empty."""
    path = os.path.join(SAMPLE_DIR, 'test_templates_only.pyf')
    xml_string = _read_pyf(path)
    root = ET.fromstring(xml_string)
    for img in root.findall('.//Image2D'):
        fn = img.findtext('filename') or ''
        assert '@template@' in fn or fn.strip() in ('', 'None'), \
            f'Unexpected non-template image: {fn}'


def test_all_files_are_valid_xml(all_pyf_files):
    """All .pyf files in the sample directory must be parseable as XML."""
    for path in all_pyf_files:
        try:
            ET.parse(path)
        except ET.ParseError as e:
            pytest.fail(f'{os.path.basename(path)} is not valid XML: {e}')
