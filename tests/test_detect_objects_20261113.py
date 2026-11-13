"""Object detection (2026-11-13): "can you draw ROIs over every cell in e" — the chat
model placed two boxes in two minutes by eye from the whole-figure preview, both off
target, then ran out of output tokens. detect_objects thresholds the panel and boxes
every object at once; preview_panel shows the panel's ROIs and can zoom on a region."""
import json
import xml.etree.ElementTree as ET

import numpy as np
import pytest
from PIL import Image

from pyfigures.mcp_server import create_figure, add_image, detect_objects, transform_image, preview_panel_source
from pyfigures.object_detection import detect

CENTRES = [(40, 40), (120, 50), (60, 130), (150, 140)]


def _cells(path, bright=False, touching=False):
    """Dark discs (radius 14) on a light background, a thin dark bar at the bottom."""
    yy, xx = np.mgrid[:200, :200]
    img = np.full((200, 200), 200, np.uint8)
    centres = CENTRES + ([(172, 140)] if touching else [])     # touches (150, 140)
    for cx, cy in centres:
        img[(xx - cx) ** 2 + (yy - cy) ** 2 <= 14 ** 2] = 60
    img[188:190, 20:180] = 40                                   # a burnt-in scale bar
    if bright:
        img = 255 - img
    Image.fromarray(np.stack([img] * 3, -1)).save(path)
    return path


def _figure(tmp_path, **kw):
    p = str(tmp_path / 'cells.pyf')
    create_figure(p, mode='groups', num_groups=1)
    add_image(p, [0], _cells(str(tmp_path / 'cells.png'), **kw))
    return p


def _rois(p):
    img = ET.parse(p).getroot().find('.//Image2D')
    return [a for a in img.find('annotations') if a.tag in ('Rectangle2D', 'Ellipse2D')]


def test_every_cell_gets_one_roi_and_the_scale_bar_none(tmp_path):
    p = _figure(tmp_path)
    out = json.loads(detect_objects(p, [0], 0, padding=0))
    assert out['found'] == out['added'] == 4 and out['polarity'] == 'dark'
    assert not any(b['y'] > 170 for b in out['boxes'])          # no box on the bar
    centres = sorted((b['x'] + b['width'] / 2, b['y'] + b['height'] / 2) for b in out['boxes'])
    assert all(abs(cx - ex) <= 2 and abs(cy - ey) <= 2 for (cx, cy), (ex, ey) in zip(centres, sorted(CENTRES)))
    assert len(_rois(p)) == 4 and out['annotation_indexes'] == [0, 3]


def test_bright_objects_ellipses_dry_run_and_touching(tmp_path):
    p = _figure(tmp_path, bright=True, touching=True)
    out = json.loads(detect_objects(p, [0], 0, dry_run=True))
    assert out['found'] == 5 and out['added'] == 0 and out['polarity'] == 'bright' and not _rois(p)
    assert json.loads(detect_objects(p, [0], 0, dry_run=True, split_touching=False))['found'] == 4
    out = json.loads(detect_objects(p, [0], 0, shape='ellipse', color='cyan'))
    assert out['added'] == 5 and {a.tag for a in _rois(p)} == {'Ellipse2D'}


def test_only_the_visible_part_is_searched(tmp_path):
    p = _figure(tmp_path)
    transform_image(p, [0], 0, crop_right=100)                  # keeps x 0-100
    out = json.loads(detect_objects(p, [0], 0))
    assert out['found'] == 2 and all(b['x'] + b['width'] <= 100 for b in out['boxes'])


def test_nothing_found_and_bad_arguments_are_said(tmp_path):
    p = str(tmp_path / 'flat.pyf')
    create_figure(p, mode='groups', num_groups=1)
    Image.new('RGB', (64, 64), (128, 128, 128)).save(tmp_path / 'flat.png')
    add_image(p, [0], str(tmp_path / 'flat.png'))
    out = json.loads(detect_objects(p, [0], 0))
    assert out['found'] == 0 and 'uniform' in out['note']
    assert detect_objects(p, [0], 0, shape='star').startswith('ERROR')
    assert detect_objects(p, [0], 3).startswith('ERROR')


def test_too_many_objects_are_not_added(tmp_path):
    p = _figure(tmp_path)
    out = json.loads(detect_objects(p, [0], 0, max_objects=2))
    assert out['found'] == 4 and out['added'] == 0 and 'max_objects' in out['note'] and not _rois(p)


def test_detect_on_the_users_embryos_image():
    """The image of the chat (Fiji sample embryos.jpg): about 28 embryos, the bar ignored."""
    import os
    path = 'C:/Users/aigouy/OneDrive/Desktop/test_images/sample_images_FIJI/embryos.jpg'
    if not os.path.isfile(path):
        pytest.skip('sample image not on this computer')
    objects, info = detect(np.asarray(Image.open(path).convert('RGB')))
    assert 24 <= len(objects) <= 32 and info['polarity'] == 'dark'
    assert not any(o['y'] > 1080 and o['width'] > 200 for o in objects)     # no box on the bar


def _recipe(tmp_path, name, detect):
    from pyfigures.recipe import build_figure_from_recipe
    _cells(str(tmp_path / 'cells.png'))
    rp = tmp_path / (name + '.json')
    rp.write_text(json.dumps({'output': name + '.pyf', 'rows': [[{'image': 'cells.png', 'detect_objects': detect}]]}))
    return build_figure_from_recipe(str(rp))['output']


def test_recipe_detect_objects(tmp_path):
    from pyfigures.recipe import RecipeError
    out = _recipe(tmp_path, 'r1', {'shape': 'ellipse', 'color': 'cyan', 'padding': 0})
    assert [a.tag for a in _rois(out)] == ['Ellipse2D'] * 4
    assert len(_rois(_recipe(tmp_path, 'r2', True))) == 4
    with pytest.raises(RecipeError, match='detect_objects'):
        _recipe(tmp_path, 'r3', {'shape': 'star'})
    with pytest.raises(RecipeError, match='unknown'):
        _recipe(tmp_path, 'r4', {'size': 3})


@pytest.mark.parametrize('query', ['draw ROIs over every cell in e', 'how many cells are there in b',
                                   'box each nucleus of panel c'])
def test_the_chat_finds_detect_objects(query):
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    tools = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools
    names = [t['name'] for t in tools['find_pyfigures_tools'].fn(query=query)['tools']]
    assert names[0] == 'detect_objects', names[:5]
    assert 'preview_panel' in tools['preview_figure'].fn.__doc__      # points to the panel's own pixels


def test_preview_panel_draws_the_rois_and_zooms(tmp_path):
    p = _figure(tmp_path)
    detect_objects(p, [0], 0)
    text, image = preview_panel_source(p, [0], 0, brighten=False)
    assert '4 existing ROI(s) are drawn in magenta' in text and 'region=[x0, y0, x1, y1]' in text
    text, image = preview_panel_source(p, [0], 0, region=[20, 20, 70, 70])
    assert text.startswith('Region x 20-70, y 20-70 of the panel source (200x200 px), magnified')
    with pytest.raises(ValueError, match='empty'):
        preview_panel_source(p, [0], 0, region=[300, 300, 400, 400])
