"""One call for many items (user, 2026-11-13: "a bit slow ... how to improve repetitive
tasks"): the chat made 26 add_roi_polygon then 26 set_roi_properties calls, one model
step (~4 s) each, and hit the 32-step limit. use_pyfigures_tool now takes batch=[...],
and a repeated single call is told to batch the rest."""
import asyncio
import json

import pytest
from mcp.server.fastmcp import FastMCP

from pyfigures.assistant.categorized_mcp import build_server
from test_assistant_live import gui, runtime  # noqa: F401  (fixtures)


@pytest.fixture
def dispatcher():
    calls = []
    full = FastMCP('fake')

    @full.tool()
    def delete_last_rows(count: int, label: str = '') -> dict:      # a name the chat exposes
        if count < 0:
            raise ValueError('count must be positive')
        if count == 99:
            return 'ERROR: no row 99'
        calls.append((count, label))
        return {'result': f'deleted {count}', 'document_changed': True}

    @full.tool()
    def preview_panel(panel_ref: str) -> str:
        return 'image'

    @full.tool()
    def remove_annotation(annotation_index: int) -> str:
        calls.append(('removed', annotation_index))
        return 'ok'

    tools = build_server(full, lambda *a, **k: {})._tool_manager._tools
    run = tools['use_pyfigures_tool'].fn
    return (lambda **kw: asyncio.run(run(**kw))), calls, tools['use_pyfigures_tool']


def test_one_call_runs_every_item_with_the_shared_fields(dispatcher):
    run, calls, _ = dispatcher
    out = run(tool_name='delete_last_rows', arguments={'label': 'x'},
              batch=[{'count': 1}, {'count': 2}, {'count': 3}])
    assert calls == [(1, 'x'), (2, 'x'), (3, 'x')]
    assert out['batch_done'] == 3 and out['document_changed'] and not out['errors']
    assert '3 of 3' in out['result']


def test_failed_items_are_listed_and_the_others_still_run(dispatcher):
    run, calls, _ = dispatcher
    out = run(tool_name='delete_last_rows', arguments={},
              batch=[{'count': 1}, {'count': -1}, {'count': 99}, {'count': 4}])
    assert [c for c, _ in calls] == [1, 4]
    assert out['batch_done'] == 2 and [e['item'] for e in out['errors']] == [2, 3]
    assert 'do not redo' in out['result']


def test_bad_batches_are_refused(dispatcher):
    run, calls, _ = dispatcher
    with pytest.raises(ValueError):
        run(tool_name='delete_last_rows', arguments={}, batch=['count=1'])
    with pytest.raises(ValueError, match='once'):
        run(tool_name='preview_panel', arguments={}, batch=[{'panel_ref': 'a'}, {'panel_ref': 'b'}])
    with pytest.raises(ValueError, match='at most'):
        run(tool_name='delete_last_rows', arguments={}, batch=[{'count': 1}] * 401)
    assert calls == []


def test_a_repeated_single_call_is_told_to_batch(dispatcher):
    run, _, _ = dispatcher
    first = run(tool_name='delete_last_rows', arguments={'count': 1})
    assert 'tip' not in first
    second = run(tool_name='delete_last_rows', arguments={'count': 2})
    assert 'batch' in second['tip'] and '#2' in second['tip']
    # reading the same thing twice is not repetitive work
    run(tool_name='preview_panel', arguments={'panel_ref': 'a'})
    assert 'TIP' not in run(tool_name='preview_panel', arguments={'panel_ref': 'a'})


def test_a_live_batch_edits_the_open_figure_with_one_reload(qapp, gui, runtime, tmp_path):  # noqa: F811
    """26 ROIs added then recoloured: one figure reload per batch, not one per ROI."""
    import os
    import threading
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from test_human_requests_20261112 import _live
    from pyfigures.assistant import live_mcp
    g, run, _ = _live(qapp, gui, tmp_path)
    tools = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools
    dispatch = tools['use_pyfigures_tool'].fn
    reloads = []
    real = g.reload_state
    g.reload_state = lambda *a, **k: (reloads.append(1), real(*a, **k))[1]

    def call(**kw):
        box = {}
        t = threading.Thread(target=lambda: box.update(out=asyncio.run(dispatch(**kw))))
        t.start()
        while t.is_alive():
            qapp.processEvents()
            t.join(0.02)
        return box['out']

    out = call(tool_name='add_roi_polygon', arguments={'panel_ref': 'a', 'color': 'yellow'},
               batch=[{'points': [[i, 2], [i + 3, 8], [i - 3, 8]]} for i in range(4, 40, 5)]
               + [{'points': 'not points'}])
    assert out['batch_done'] == 8 and len(out['errors']) == 1, out
    assert len(reloads) == 1
    rois = [a for a in json.loads(run('get_annotations')['tool_result']) if a.get('type') == 'Polygon2D']
    assert len(rois) == 8
    out = call(tool_name='set_roi_properties', arguments={'panel_ref': 'a', 'color': 'red'},
               batch=[{'annotation_index': r['annotation_index']} for r in rois])
    assert out['batch_done'] == 8 and not out['errors'] and len(reloads) == 2, out
    colours = {a['color'] for a in json.loads(run('get_annotations')['tool_result']) if a.get('type') == 'Polygon2D'}
    assert len(colours) == 1 and colours != {r['color'] for r in rois}
    assert g.undo_stack            # one undoable step
    # the user's chat (2026-11-13): a background colour for three panels in one call
    # failed with "'str' object has no attribute 'get'"
    out = call(tool_name='set_image_property', arguments={'property_name': 'fill_color', 'value': '16777215'},
               batch=[{'panel_ref': 'a'}, {'panel_ref': 'b'}])
    assert out['batch_done'] == 2 and not out['errors'], out


def test_removals_by_index_go_from_the_highest(dispatcher):
    """Removing index 3 first shifted the later ones (the chat's 2026-11-13 log)."""
    run, calls, _ = dispatcher
    run(tool_name='remove_annotation', arguments={}, batch=[{'annotation_index': i} for i in (3, 41, 8)])
    assert calls == [('removed', 41), ('removed', 8), ('removed', 3)]


def test_the_document_names_its_file():
    from pyfigures.assistant.session import document_info
    info = document_info('C:/figs/wing_figure.pyf', dirty=True)
    assert info['name'] == 'wing_figure' and info['folder'].endswith('figs') and not info['saved']
    assert 'wing_figure.pptx' in info['note']
    assert document_info(None, False)['name'] is None


def test_the_schema_offers_batch(dispatcher):
    _, _, tool = dispatcher
    assert 'batch' in tool.parameters['properties']
    assert 'ONE call' in tool.description
