"""Removing all ROIs at once (2026-11-13): "I would prefer triangular ROIs" — the chat
model removed 26 ellipses with 26 remove_annotation calls and ran out of steps; it said
itself "No bulk-removal tool exists". remove_rois (MCP), Annotations > Remove ROIs…
and the panel editor's Remove all ROIs button do it in one go."""
import json
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image

from pyfigures.mcp_server import (create_figure, add_image, add_roi_rect, add_roi_ellipse, add_roi_polygon,
                                  add_roi_line, add_annotation, add_connector, add_zoom_callout, remove_rois,
                                  get_annotations)


def _figure(tmp_path, n=2):
    p = str(tmp_path / 'f.pyf')
    create_figure(p, mode='groups', num_groups=1)
    for i in range(n):
        Image.fromarray(np.full((100, 120), 128, np.uint8)).save(tmp_path / f'im{i}.png')
        add_image(p, [0], str(tmp_path / f'im{i}.png'))
    return p


def _tags(p, index=0):
    img = [i for i in ET.parse(p).getroot().iter('Image2D') if i.find('filename') is not None][index]
    return [a.tag for a in img.find('annotations')]


def test_every_area_roi_goes_texts_and_lines_stay(tmp_path):
    p = _figure(tmp_path)
    add_roi_rect(p, [0], 0, x=5, y=5, width=10, height=10)
    add_roi_ellipse(p, [0], 0, x=30, y=5, width=10, height=10)
    add_roi_polygon(p, [0], 0, points=[[50, 5], [60, 5], [55, 15]])
    add_roi_line(p, [0], 0, x1=5, y1=50, x2=40, y2=60, arrow=True)
    add_annotation(p, [0], 0, text='hello')
    out = remove_rois(p, [0], 0)
    assert out.startswith('Removed 3 ROI(s)') and 'Polygon2D' in out
    assert 'Rectangle2D' not in _tags(p) and 'Ellipse2D' not in _tags(p)
    assert 'Line2D' in _tags(p) and 'TAText2D' in _tags(p)
    assert remove_rois(p, [0], 0, shapes=['line']).startswith('Removed 1 ROI(s)')
    assert 'Line2D' not in _tags(p) and 'TAText2D' in _tags(p)
    assert remove_rois(p, [0], 0).startswith('Removed 0 ROI(s)')


@pytest.mark.parametrize('query', ['remove all the ROIs of e', 'remove ellipses bulk delete all annotations',
                                   'clear the boxes in d'])
def test_the_chat_finds_remove_rois(query):
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    tools = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools
    names = [t['name'] for t in tools['find_pyfigures_tools'].fn(query=query)['tools']]
    assert names[0] == 'remove_rois', names[:5]


def test_all_panels_and_bad_arguments(tmp_path):
    p = _figure(tmp_path)
    for i in range(2):
        add_roi_rect(p, [0], i, x=5, y=5, width=10, height=10)
        add_roi_ellipse(p, [0], i, x=30, y=5, width=10, height=10)
    assert remove_rois(p, all_panels=True).startswith('Removed 4 ROI(s) from every panel')
    assert remove_rois(p, [0], 0, shapes=['triangle']).startswith('ERROR')
    assert remove_rois(p).startswith('ERROR')
    assert remove_rois(p, [0], 7).startswith('ERROR')


def test_connectors_go_with_their_shapes_and_the_inset_roi_stays(tmp_path):
    p = _figure(tmp_path, n=1)
    add_roi_rect(p, [0], 0, x=5, y=5, width=10, height=10)
    add_roi_rect(p, [0], 0, x=60, y=40, width=10, height=10)
    rois = [a['annotation_index'] for a in json.loads(get_annotations(p)) if a['type'] == 'Rectangle2D']
    add_connector(p, [0], 0, rois[0], rois[1])
    add_zoom_callout(p, [0], 0, source_x=40, source_y=40, source_w=20, source_h=20,
                     parent_width=120, parent_height=100)
    before = _tags(p)
    out = remove_rois(p, [0], 0)
    after = _tags(p)
    assert 'connector' in out and 'kept' in out                        # the callout's box stays
    assert after.count('Rectangle2D') == 1 and 'Image2D' in after
    assert before.count('Line2D') - after.count('Line2D') == 1         # the connector, not the leaders
    assert remove_rois(p, [0], 0, keep_inset_rois=False).startswith('Removed 1 ROI(s)')
    assert 'Rectangle2D' not in _tags(p) and 'Image2D' in _tags(p)      # the inset itself stays
