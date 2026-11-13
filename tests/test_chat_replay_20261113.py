"""Replaying a chat (user, 2026-11-13: "a tool to replay a conversation for debugging, one
by one ... also useful for users that would like to repeat the exact procedure always with
their figs, in that case all automated"): pyfigures.assistant.chat_replay, Tools > Replay a
chat… / Run a procedure…, MCP list_chat_steps / save_chat_procedure / run_procedure, recipe
procedure:."""
from __future__ import annotations

import json
import os
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import _figure, gui, runtime  # noqa: E402,F401  (fixtures)
from pyfigures.assistant import chat_replay as R  # noqa: E402


def _ev(kind, value):
    return json.dumps({'time': '2026-11-13T13:15:34+00:00', 'kind': kind, 'value': value})


def _use(tool, arguments, batch=None):
    value = {'tool_name': tool, 'arguments': arguments}
    if batch:
        value['batch'] = batch
    return _ev('tool_call', {'name': 'use_pyfigures_tool', 'arguments': value})


OK = _ev('tool_result', {'is_error': False, 'content': '{"result": "done"}'})
FAILED = _ev('tool_result', {'is_error': True, 'content': 'Unknown argument(s): colour'})


def _chat(tmp_path, folder='C:/figs', name='wing'):
    """A chat log as the sidebar writes it: two requests kept, a failed call, reads,
    and a request undone afterwards."""
    both = [{'panel_ref': 'a'}, {'panel_ref': 'b'}]
    lines = [
        _ev('user', 'rotate all images by 25 degrees'),
        _ev('host_context', {'document': {'folder': folder, 'name': name}}),
        _ev('tool_call', {'name': 'find_pyfigures_tools', 'arguments': {'query': 'rotate'}}), OK,
        _use('transform_image', {'rotation': 25}, both), OK,
        _ev('tool_call', {'name': 'inspect_figure', 'arguments': {}}), OK,
        _ev('user', 'make all bgs of panels black'),
        _use('set_image_property', {'property_name': 'fill_color', 'colour': '0'}, both), FAILED,
        _use('set_image_property', {'property_name': 'fill_color', 'value': '0'}, both), OK,
        _ev('user', 'make the letters red'),
        _use('edit_panel_letters', {'action': 'style', 'color': 'red', 'scope': 'all'}), OK,
        _ev('action', {'id': 'x', 'request': 'make the letters red', 'status': 'undone'}),
        _ev('user', 'save it as a ppt with the same name'),
        _use('export_pptx', {'out_path': f'{folder}/{name}.pptx'}), OK,
    ]
    path = tmp_path / 'chat.jsonl'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def test_the_steps_of_a_chat(tmp_path):
    steps = R.load_steps(_chat(tmp_path))
    assert [s.tool for s in steps] == ['find_pyfigures_tools', 'transform_image', 'inspect_figure',
                                       'set_image_property', 'set_image_property', 'edit_panel_letters',
                                       'export_pptx']
    assert [s.reads_only for s in steps][:3] == [True, False, True]
    assert steps[3].recorded_error and not steps[4].recorded_error and steps[5].turn_undone
    assert steps[1].request == 'rotate all images by 25 degrees' and steps[1].batch[1] == {'panel_ref': 'b'}
    kept = R.procedure_steps(steps)
    assert [s.tool for s in kept] == ['transform_image', 'set_image_property', 'export_pptx']


def test_an_edit_the_chat_undid_is_left_out(tmp_path):
    """'skip steps that failed or were undone' (2026-11-13): undo_redo in the chat drops
    the edit before it; a redo puts it back; a new edit ends the redo history."""
    undo = _ev('tool_call', {'name': 'undo_redo', 'arguments': {'action': 'undo'}})
    redo = _ev('tool_call', {'name': 'undo_redo', 'arguments': {'action': 'redo'}})
    lines = [_ev('user', 'rotate a'), _use('transform_image', {'panel_ref': 'a', 'rotation': 10}), OK,
             _ev('user', 'make b black'), _use('set_image_property', {'panel_ref': 'b', 'value': '0'}), OK,
             _ev('user', 'undo that'), undo, OK,
             _ev('user', 'rotate c'), _use('transform_image', {'panel_ref': 'c', 'rotation': 5}), OK,
             _ev('user', 'undo, then redo'), undo, OK, redo, OK]
    path = tmp_path / 'undo.jsonl'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    kept = R.procedure_steps(R.load_steps(path))
    assert [s.arguments['panel_ref'] for s in kept] == ['a', 'c']


def test_a_debug_zip_is_read_like_a_log(tmp_path):
    z = tmp_path / 'sidecar-debug.zip'
    with zipfile.ZipFile(z, 'w') as out:
        out.writestr('events.jsonl', _chat(tmp_path).read_text(encoding='utf-8'))
    assert len(R.procedure_steps(R.load_steps(z))) == 3
    bad = tmp_path / 'other.zip'
    with zipfile.ZipFile(bad, 'w') as out:
        out.writestr('x.txt', 'x')
    with pytest.raises(ValueError, match='events.jsonl'):
        R.load_steps(bad)


def test_a_procedure_names_the_figure_it_runs_on(tmp_path):
    chat = _chat(tmp_path)
    proc = tmp_path / 'steps.json'
    R.save_procedure(R.procedure_steps(R.load_steps(chat)), proc, source=chat)
    data = json.loads(proc.read_text(encoding='utf-8'))
    # the chat sidecar's format: one MCP call per step (its Procedures menu runs it too)
    assert data['procedure'] == 1 and data['application'] == 'PyFigures' and len(data['steps']) == 3
    assert data['steps'][2]['call'] == 'use_pyfigures_tool'
    assert data['steps'][2]['arguments']['arguments']['out_path'] == '{folder}/{name}.pptx'
    # a procedure in the first PyFigures layout ("tool", "batch") still runs
    old = tmp_path / 'old.json'
    old.write_text(json.dumps({'pyfigures_procedure': 1, 'steps': [
        {'request': 'r', 'tool': 'transform_image', 'arguments': {'rotation': 25}, 'batch': [{'panel_ref': 'a'}]}]}),
        encoding='utf-8')
    assert R.load_procedure(old)[0].batch == [{'panel_ref': 'a'}]
    again = R.load_procedure(proc)
    assert again[0].batch == [{'panel_ref': 'a'}, {'panel_ref': 'b'}]
    assert R._fill(again[2].arguments, 'D:/other', 'kidney') == {'out_path': 'D:/other/kidney.pptx'}
    (tmp_path / 'bad.json').write_text('{"name": 1}', encoding='utf-8')
    with pytest.raises(ValueError, match='not a PyFigures procedure'):
        R.load_procedure(tmp_path / 'bad.json')


def _rotate_and_black(tmp_path):
    proc = tmp_path / 'rotate_black.json'
    chat = _chat(tmp_path)
    steps = [s for s in R.procedure_steps(R.load_steps(chat)) if s.tool != 'export_pptx']
    R.save_procedure(steps, proc, source=chat)
    return proc


def _live_window(qapp, gui, tmp_path):  # noqa: F811
    from pyfigures.assistant import launch
    from pyfigures.assistant.partner_gui import panels
    g = gui(shareable=True)
    g.reload_state(_figure(tmp_path), append=False)
    launch.start_live_session(g)
    return g, lambda: [p for _, _, p in panels(g.paint.EZFIG_panel.shapes_to_draw)]


def test_run_a_procedure_on_the_open_figure(qapp, gui, runtime, tmp_path):  # noqa: F811
    g, panels = _live_window(qapp, gui, tmp_path)
    done, total, failed = g.run_procedure_action(str(_rotate_and_black(tmp_path)))
    assert (done, total, failed) == (2, 2, [])
    assert [(p.theta, p.fill_color) for p in panels()] == [(25, 0), (25, 0)]


def test_the_dialog_steps_through_a_chat_and_resets(qapp, gui, runtime, tmp_path):  # noqa: F811
    g, panels = _live_window(qapp, gui, tmp_path)
    dialog = g.replay_chat_action(str(_chat(tmp_path)))
    try:
        assert dialog.table.rowCount() == 3                      # the steps that changed the figure
        from qtpy.QtWidgets import QHeaderView
        header = dialog.table.horizontalHeader()                 # every column can be resized by hand
        assert all(header.sectionResizeMode(c) == QHeaderView.ResizeMode.Interactive for c in range(5))
        dialog.table.selectRow(0)
        dialog.run_selected()                                    # rotate, then the next row is selected
        assert [p.theta for p in panels()] == [25, 25] and dialog.current_row() == 1
        assert dialog.table.item(0, 4).text() == 'ok'
        # debugging: change the arguments of the next step before running it
        shown = json.loads(dialog.arguments.toPlainText())
        shown['arguments']['value'] = '255'
        dialog.arguments.setPlainText(json.dumps(shown))
        dialog.run_selected()
        assert [p.fill_color for p in panels()] == [255, 255]
        dialog.show_reads.setChecked(True)                       # reads and failed calls too
        assert dialog.table.rowCount() == 7
        dialog.reset()
        assert [p.theta or 0 for p in panels()] == [0, 0]
        dialog.show_reads.setChecked(False)
        assert dialog.save_procedure(str(tmp_path / 'saved.json'))
        assert len(R.load_procedure(tmp_path / 'saved.json')) == 3
    finally:
        dialog.close()


def test_drag_and_drop_a_procedure_a_chat_or_a_zip(qapp, gui, runtime, tmp_path):  # noqa: F811
    """'can you also add it to DND': dropped procedures run or open the replay."""
    g, panels = _live_window(qapp, gui, tmp_path)
    proc = _rotate_and_black(tmp_path)
    chat = _chat(tmp_path)
    junk = tmp_path / 'notes.json'
    junk.write_text('{"a": 1}', encoding='utf-8')
    assert g._replayable(str(proc)) and g._replayable(str(chat)) and not g._replayable(str(junk))
    assert g.replay_drop(str(proc), answer='cancel') is None
    assert g.replay_drop(str(proc), answer='run') == (2, 2, [])
    assert [p.theta for p in panels()] == [25, 25]
    dialog = g.replay_drop(str(chat))                   # a chat log: the step-by-step dialog
    assert dialog.table.rowCount() == 3
    dialog.close()
    many = tmp_path / 'procedures.zip'
    with zipfile.ZipFile(many, 'w') as z:
        z.write(proc, 'a_rotate.json')
        z.write(proc, 'b_again.json')
        z.writestr('README.txt', 'index')
    assert g._replayable(str(many))
    dialog = g.replay_drop(str(many))
    assert [dialog.chats.itemText(k) for k in range(2)] == ['a_rotate.json', 'b_again.json']
    assert dialog.table.rowCount() == 2
    dialog.close()


def test_save_the_last_chat_and_run_it_from_the_chat(qapp, gui, runtime, tmp_path, monkeypatch):  # noqa: F811
    """'allow to do the procedure stuff directly': Tools > Save the last chat as a
    procedure… in one step, and the live chat's run_procedure_here on the open figure."""
    from pyfigures.assistant import live_mcp
    from pyfigures.gui.replay_dialog import run_in_thread
    chat = _chat(tmp_path)
    monkeypatch.setattr(R, 'recent_chats', lambda limit=30: [chat])
    g, panels = _live_window(qapp, gui, tmp_path)
    saved = g.save_last_chat_procedure_action(str(tmp_path / 'last.json'))
    assert [s.tool for s in R.load_procedure(saved)] == ['transform_image', 'set_image_property', 'export_pptx']
    out = run_in_thread(lambda: live_mcp.run_procedure_here(str(_rotate_and_black(tmp_path))))
    assert (out['done'], out['total'], out['failed']) == (2, 2, [])
    assert [(p.theta, p.fill_color) for p in panels()] == [(25, 0), (25, 0)]
    with pytest.raises(ValueError, match='Cannot read'):
        live_mcp.run_procedure_here(str(tmp_path / 'missing.json'))


def test_mcp_and_recipe_run_a_procedure_on_files(qapp, runtime, tmp_path):  # noqa: F811
    from pyfigures.mcp_server import run_procedure, list_chat_steps, save_chat_procedure
    chat = _chat(tmp_path)
    assert '3 step(s) of 7' in list_chat_steps(str(chat))
    assert save_chat_procedure(str(tmp_path / 's.json'), chat_path=str(chat)).startswith('Saved 3')
    figure = _figure(tmp_path)
    out = run_procedure(str(_rotate_and_black(tmp_path)), figure)
    assert out.startswith('2 of 2 step(s) done'), out
    import xml.etree.ElementTree as ET
    imgs = [e for e in ET.parse(figure).getroot().iter('Image2D') if e.findtext('filename')]
    assert [float(e.findtext('theta')) for e in imgs] == [25.0, 25.0]
    assert run_procedure(str(tmp_path / 's.json'), str(tmp_path / 'nope.pyf')).startswith('ERROR')


def test_cli_lists_the_steps(tmp_path, capsys):
    assert R.main(['steps', str(_chat(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert 'transform_image' in out and 'find_pyfigures_tools' not in out
