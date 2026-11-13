"""Moving ROIs by numbers (2026-11-13): "move the smallest inset in b by 100px to the
right" — the chat searched for a move tool eight times and stopped. move_annotations
shifts ROIs, lines and free texts in one call; insets say they only change corner."""
import json

import numpy as np
from PIL import Image

from pyfigures.mcp_server import (create_figure, add_image, add_roi_rect, add_roi_ellipse, add_roi_polygon,
                                  add_roi_line, add_zoom_callout, get_annotations, move_annotations)


def _figure(tmp_path):
    p = str(tmp_path / 'f.pyf')
    create_figure(p, mode='groups', num_groups=1)
    Image.fromarray(np.full((200, 300), 128, np.uint8)).save(tmp_path / 'a.png')
    add_image(p, [0], str(tmp_path / 'a.png'))
    add_roi_rect(p, [0], 0, x=10, y=20, width=30, height=40)
    add_roi_ellipse(p, [0], 0, x=50, y=20, width=30, height=30)
    add_roi_polygon(p, [0], 0, points=[[100, 10], [120, 10], [110, 30]])
    add_roi_line(p, [0], 0, x1=10, y1=150, x2=60, y2=160, arrow=True)
    return p


def _by_type(p):
    return {a['type']: a for a in json.loads(get_annotations(p)) if a.get('type') != 'TAText2D'}


import pytest


@pytest.mark.parametrize('query', ['move the smallest inset in b by 100px to the right',
                                   'shift the ROI up by 20 pixels', 'move_inset',
                                   'Move the ROI of the smallest inset in b by 100 px to the right'])
def test_the_chat_finds_move_annotations(query):
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    tools = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools
    names = [t['name'] for t in tools['find_pyfigures_tools'].fn(query=query)['tools']]
    assert 'move_annotations' in names[:2], names[:5]


def test_shift_everything_then_one_by_index(tmp_path):
    p = _figure(tmp_path)
    out = move_annotations(p, [0], 0, dx=100)
    assert out.startswith('Moved 4 annotation(s) by (100, 0)')
    a = _by_type(p)
    assert (a['Rectangle2D']['x'], a['Rectangle2D']['y']) == (110, 20)
    assert a['Ellipse2D']['x'] == 150 and a['Line2D']['x1'] == 110 and a['Line2D']['x2'] == 160
    assert a['Polygon2D']['points'][0] == [200, 10]
    ellipse = a['Ellipse2D']['annotation_index']
    move_annotations(p, [0], 0, dy=-5, annotation_indexes=[ellipse])
    assert _by_type(p)['Ellipse2D']['y'] == 15 and _by_type(p)['Rectangle2D']['y'] == 20


def test_put_one_at_a_point_and_bad_arguments(tmp_path):
    p = _figure(tmp_path)
    rect = _by_type(p)['Rectangle2D']['annotation_index']
    assert move_annotations(p, [0], 0, to_x=200, to_y=100, annotation_indexes=[rect]).startswith('Moved 1')
    assert (_by_type(p)['Rectangle2D']['x'], _by_type(p)['Rectangle2D']['y']) == (200, 100)
    assert move_annotations(p, [0], 0, to_x=5).startswith('ERROR')
    assert move_annotations(p, [0], 0, dx=1, shapes=['star']).startswith('ERROR')
    assert move_annotations(p, [0], 0, dx=1, annotation_indexes=[99]).startswith('ERROR')
    assert move_annotations(p, [0], 0, dx=1, shapes=['line']).startswith('Moved 1')


def test_an_inset_says_it_only_changes_corner(tmp_path):
    p = _figure(tmp_path)
    add_zoom_callout(p, [0], 0, source_x=150, source_y=100, source_w=40, source_h=30,
                     parent_width=300, parent_height=200)
    inset = next(a['annotation_index'] for a in json.loads(get_annotations(p)) if 'inset' in str(a.get('type')))
    out = move_annotations(p, [0], 0, dx=100, annotation_indexes=[inset])
    assert out.startswith('Moved 0') and 'placement' in out
