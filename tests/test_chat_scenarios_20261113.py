"""Regression table of real chat requests (user, 2026-11-13: "it failed at a task it could
achieve previously, these tasks may be turned into tests so that there is no regression").

Each row is a request a user typed in the PyFigures chat, the operation that does it and,
for the ones that changed the figure, the call the model made and the state it must give.
Two parts can be tested without a language model:
- discovery: the user's own words, searched with find_pyfigures_tools, give that operation
  first (a model often searches with the user's words; when nothing fit it searched again
  and again and gave up);
- execution: the call works on an open figure and reaches the expected state.
Whether a given model picks the right call can only be measured by replaying the requests
against it (costs API calls, not part of this suite).

Add a row whenever a chat log shows a request that failed or that worked and must keep working.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import gui, runtime  # noqa: E402,F401  (fixtures)
from test_panel_editor import fig, ui  # noqa: E402,F401  (fixtures)

# (request as typed, operation found first, chat log it comes from)
DISCOVERY = [
    ('rotate all image by 25 degrees', 'transform_image', '2026-11-13 14:15'),
    ('now make all bgs of panels black', 'set_image_property', '2026-11-13 14:15'),
    ('fit the bg of each panel to the bg of its image', 'set_image_property', '2026-11-13 14:15 (failed: 13 searches)'),
    ('add a bg to panels that roughly have the same color as the general bg of each image', 'set_image_property', '2026-11-13 10:31'),
    ('sample pixel colour at the corner', 'set_image_property', '2026-11-13 14:15 (the model\'s own search)'),
    ('segment nuclei in d', 'detect_objects', '2026-11-13 10:31'),
    ('draw ROIs over every cell in e', 'detect_objects', '2026-11-13'),
    ('segment red blobs in d', 'detect_objects', '2026-11-13 10:31'),
    ('there are super tiny ROIs do remove them', 'remove_rois', '2026-11-13 10:31 (failed: one by one)'),
    ('remove all the ROIs of e', 'remove_rois', '2026-11-13'),
    ('instead of circles make triangles', 'remove_rois', '2026-11-13 10:31'),
    ('make all line strokes 0.65', 'set_roi_properties', '2026-11-13 14:15'),
    ('make all these triangles red', 'set_roi_properties', '2026-11-13 10:31 (26 calls)'),
    ('move the box in b by 100 px to the right', 'move_annotations', '2026-11-13'),
    ('put the left inset in b at the bottom left corner', 'set_inset_property', '2026-11-13 10:31'),
    ('letter b is not visible fix it', 'edit_panel_letters', '2026-11-13 14:15'),
    ('uncrop it', 'transform_image', '2026-11-13'),
    ('save this fig as a ppt', 'export_pptx', '2026-11-13 10:31'),
    ('connect the ROI to the inset', 'connect_roi_to_inset', '2026-11-12'),
    ('join these two boxes with a line', 'add_connector', '2026-11-12'),
    ('crop the burnt in scale bar of e', 'preview_panel', '2026-11-13 (cropped blind)'),
]


@pytest.fixture(scope='module')
def tools():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    return build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools


@pytest.mark.parametrize('request_text, operation, origin', DISCOVERY, ids=[d[0][:40] for d in DISCOVERY])
def test_the_users_words_find_the_operation(tools, request_text, operation, origin):
    found = [t['name'] for t in tools['find_pyfigures_tools'].fn(query=request_text)['tools']]
    assert found and found[0] == operation, f'{request_text!r} ({origin}): {found[:4]}'


# -- execution: the calls the model made (or should make), on an open figure ------------
@pytest.fixture
def live(qapp, gui, runtime, tmp_path):  # noqa: F811
    from test_human_requests_20261112 import _live
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    g, run, _ = _live(qapp, gui, tmp_path)
    dispatch = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools['use_pyfigures_tool'].fn

    def call(tool_name, arguments, batch=None):
        box = {}

        def work():
            try:
                box['out'] = asyncio.run(dispatch(tool_name=tool_name, arguments=arguments, batch=batch))
            except Exception as e:      # shown by the assert below
                box['error'] = e
        t = threading.Thread(target=work)
        t.start()
        while t.is_alive():
            qapp.processEvents()
            t.join(0.02)
        if 'error' in box:
            raise box['error']
        return box['out']

    def panels():
        from pyfigures.assistant.partner_gui import panels as image_panels
        return [p for _, _, p in image_panels(g.paint.EZFIG_panel.shapes_to_draw)]
    return g, call, run, panels


ALL = [{'panel_ref': 'a'}, {'panel_ref': 'b'}]


def test_rotate_all_images_by_25_degrees(live):
    g, call, _, panels = live
    out = call('transform_image', {'rotation': 25}, ALL)
    assert out['batch_done'] == 2 and out.get('verified')
    assert [p.theta for p in panels()] == [25, 25]


def test_black_then_each_images_own_background(live):
    """"now make all bgs of panels black", then "fit the bg to the bg of each image"
    (failed 2026-11-13: no way to read the image's colour)."""
    from pyfigures.panel_source_preview import border_colour
    g, call, _, panels = live
    call('set_image_property', {'property_name': 'fill_color', 'value': '0'}, ALL)
    assert [p.fill_color for p in panels()] == [0, 0]
    out = call('set_image_property', {'property_name': 'fill_color', 'value': 'auto'}, ALL)
    assert out['batch_done'] == 2, out
    assert [p.fill_color for p in panels()] == [border_colour(p) for p in panels()]
    assert all(p.fill_color not in (0, None) for p in panels())      # grey noise images: not black


def test_strokes_of_all_rois_and_the_tiny_ones_removed(live):
    """"make all line strokes 0.65" (one batch) and "there are super tiny ROIs do remove
    them" (one remove_rois with max_size; it removed 2 of 5 one by one, then stopped)."""
    g, call, run, panels = live
    for x, size in ((2, 20), (25, 4), (32, 5)):
        call('add_roi_ellipse', {'panel_ref': 'a', 'x': x, 'y': 2, 'width': size, 'height': size})
    rois = [a for a in json.loads(run('get_annotations')['tool_result']) if a.get('type') == 'Ellipse2D']
    out = call('set_roi_properties', {'panel_ref': 'a', 'stroke': 0.65},
               [{'annotation_index': r['annotation_index']} for r in rois])
    ellipses = lambda: [e for e in panels()[0].annotations if type(e).__name__ == 'Ellipse2D']
    assert out['batch_done'] == 3 and {e.stroke for e in ellipses()} == {0.65}
    call('remove_rois', {'panel_ref': 'a', 'max_size': 6})
    assert [round(e.width()) for e in ellipses()] == [20]


def test_the_chat_state_names_the_open_file(qapp, live, tmp_path):
    """"use the same name as the pyf minus the extension" (2026-11-13: nine searches)."""
    from test_assistant_live import _call
    g, _, _, _ = live
    g.current_file = str(tmp_path / 'wing_figure.pyf')
    document = _call(qapp, 'inspect')['document']
    assert document['name'] == 'wing_figure' and document['file'].endswith('wing_figure.pyf')
    assert document['note'].endswith('wing_figure.pptx')


# -- the same feature in the GUI and in recipes ---------------------------------------------
def test_editor_from_image_button(fig, ui):  # noqa: F811
    """Panel editor → Fill → From image: the panel background in the image's own colour."""
    from test_panel_editor import edit
    from pyfigures.panel_source_preview import border_colour
    img = edit(fig, ui, "rgb", lambda ed: ed.match_image_background())
    # the colour as shown (each channel's display range applied), here (255, 90, 0)
    assert img.fill_color == border_colour(img) and img.fill_color >> 16 == 255


def test_recipe_panel_background(tmp_path):
    import numpy as np
    from PIL import Image
    from pyfigures.recipe import build_figure_from_recipe, RecipeError
    Image.fromarray(np.full((40, 60, 3), (10, 200, 30), np.uint8)).save(tmp_path / 'g.png')

    def build(name, value):
        rp = tmp_path / (name + '.json')
        rp.write_text(json.dumps({'output': name + '.pyf',
                                  'rows': [[{'image': 'g.png', 'rotate': 20, 'panel_background': value}]]}))
        out = build_figure_from_recipe(str(rp))['output']
        import xml.etree.ElementTree as ET
        return next(e.findtext('fill_color') for e in ET.parse(out).getroot().iter('Image2D')
                    if e.findtext('filename'))
    auto = int(build('auto', 'auto'))           # green, as shown: (0, 255, 27)
    assert (auto >> 8) & 255 == 255 and auto >> 16 < 30 and auto & 255 < 60
    assert int(build('white', 'white')) == 0xFFFFFF
    with pytest.raises(RecipeError, match='panel_background'):
        build('bad', [1, 2])
