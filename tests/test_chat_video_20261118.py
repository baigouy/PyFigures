"""A demo video from a chat that already happened (user, 2026-11-18: videos made after the
fact from chats whose result turned out interesting, no new model call, only the requests
chosen): pyfigures.assistant.chat_video, Tools > Make a demo video from a chat…, the chat
sidebar's Procedures menu, python -m pyfigures.assistant.chat_video.

Synthetic chat logs only (never a real one)."""
from __future__ import annotations

import json
import os
import shutil

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from test_assistant_live import _figure, gui, runtime  # noqa: E402,F401  (fixtures)
from pyfigures.assistant import chat_video as V  # noqa: E402

pytestmark = pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="chat replay: local only")

UI = {"spacing": 3, "width": 512, "automatic": True, "first": "a", "background": None}


def _ev(kind, value, **extra):
    return json.dumps({'time': '2026-11-18T10:00:00+00:00', 'kind': kind, 'value': value, **extra})


def _use(tool, arguments, batch=None):
    value = {'tool_name': tool, 'arguments': arguments}
    if batch:
        value['batch'] = batch
    return _ev('tool_call', {'name': 'use_pyfigures_tool', 'arguments': value})


OK = _ev('tool_result', {'is_error': False, 'content': '{"result": "done"}'})
BOTH = [{'panel_ref': 'a'}, {'panel_ref': 'b'}]


def _snapshot(tmp_path, name):
    """A copy of the figure as the chat saves it before a request (.pyf + .ui.json)."""
    folder = tmp_path / 'actions' / name
    folder.mkdir(parents=True)
    pyf = folder / 'before.pyf'
    shutil.copyfile(_figure(tmp_path), pyf)
    (folder / 'before.ui.json').write_text(json.dumps(UI), encoding='utf-8')
    return str(pyf)


def _chat(tmp_path, befores=(True, True, False, False), empty_start=False):
    """Four requests: rotate, black backgrounds (with an intermediate message), an export,
    then letters red. befores: which requests have the copy saved before them."""
    copies = [_snapshot(tmp_path, f'r{k}') if keep else str(tmp_path / f'gone{k}' / 'before.pyf')
              for k, keep in enumerate(befores, 1)]

    def action(k, request):
        return _ev('action', {'id': f'id{k}', 'request': request, 'status': 'applied', 'before': copies[k - 1],
                              'controls': ['undo']})
    summary = {'empty': True, 'answer': 'empty'} if empty_start else {'empty': False, 'answer': '2 panels a, b'}
    lines = [
        _ev('user', 'rotate all images by 25 degrees'),
        _ev('request_settings', {'provider': 'mistral', 'model': 'mistral-large-4'}),
        _ev('host_context', {'figure_summary': summary, 'document': {'file': None}}),
        _ev('tool_call', {'name': 'find_pyfigures_tools', 'arguments': {'query': 'rotate'}}), OK,
        _use('transform_image', {'rotation': 25}, BOTH), OK,
        _ev('assistant', 'Done: **a** and **b** are rotated by 25°.'),
        action(1, 'rotate all images by 25 degrees'),
        _ev('user', 'make all bgs of panels black'),
        _ev('assistant', 'I will set the fill colour of both panels.'),
        _use('set_image_property', {'property_name': 'fill_color', 'value': '0'}, BOTH), OK,
        _ev('assistant', 'Done: both backgrounds are black.'),
        action(2, 'make all bgs of panels black'),
        _ev('user', 'save it as a ppt'),
        _use('export_pptx', {'out_path': str(tmp_path / 'must_not_exist.pptx')}), OK,
        _ev('assistant', 'Saved.'),
        action(3, 'save it as a ppt'),
        _ev('user', 'make the letters red'),
        _use('edit_panel_letters', {'action': 'style', 'color': 'red', 'scope': 'all'}), OK,
        _ev('assistant', 'The letters are red.'),
        action(4, 'make the letters red'),
    ]
    path = tmp_path / 'chat.jsonl'
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


def test_the_requests_of_a_chat_and_where_the_film_starts(tmp_path):
    requests = V.requests_of(_chat(tmp_path))
    assert [r.number for r in requests] == [1, 2, 3, 4]
    assert requests[1].text == 'make all bgs of panels black' and requests[1].edits == 1
    assert requests[0].model == 'mistral-large-4' and requests[0].label().startswith('1. rotate all')
    # the copy saved just before the request
    start = V.start_state(requests, 2)
    assert start['kind'] == 'snapshot' and start['path'] == requests[1].before and start['replay'] == []
    # its copy is gone: an earlier one, then the requests in between replayed silently
    start = V.start_state(requests, 4)
    assert start['path'] == requests[1].before and start['replay'] == [2, 3]
    with pytest.raises(ValueError, match='not in this chat'):
        V.start_state(requests, 5)


def test_no_copy_left(tmp_path):
    # the chat started on an empty figure: from it, everything before replayed
    requests = V.requests_of(_chat(tmp_path, befores=(False,) * 4, empty_start=True))
    assert V.start_state(requests, 3) == {'kind': 'empty', 'path': None, 'replay': [1, 2],
                                          'note': 'the empty figure the chat started on, then requests 1–2 '
                                                  'replayed silently'}
    (tmp_path / 'other').mkdir()
    requests = V.requests_of(_chat(tmp_path / 'other', befores=(False,) * 4))
    with pytest.raises(ValueError, match='No copy of the figure'):
        V.start_state(requests, 2)


def test_an_export_is_never_run_again():
    from pyfigures.assistant.chat_replay import Step
    assert V.writes_files(Step('', 1, 'export_pptx', {'out_path': 'x.pptx'}))
    assert V.writes_files(Step('', 1, 'set_image_property', {}, [{'panel_ref': 'a', 'out_path': 'x'}]))
    assert not V.writes_files(Step('', 1, 'transform_image', {'rotation': 25}, BOTH))


class _Picture:
    """Stands for a grabbed QImage: save(path, 'PNG')."""

    def __init__(self, colour, size=(301, 181)):
        from PIL import Image
        self.image = Image.new('RGB', size, colour)

    def save(self, path, fmt):
        self.image.save(path)
        return True


def test_the_reel_and_its_mp4_and_gif(tmp_path):
    import av
    reel = V.Reel(tmp_path / 'frames')
    reel.add(_Picture((200, 30, 30)), 1.0)
    reel.add(_Picture((30, 30, 200)), 0.5)
    reel.hold(1.5)
    assert reel.frames == 30 and reel.seconds == 3.0 and len(reel.shots) == 2
    assert len(reel.timeline(V.GIF_FPS)) == 24 and reel.timeline()[9:11] == ['00000.png', '00001.png']
    mp4 = V.encode_mp4(reel, tmp_path / 'demo.mp4')
    with av.open(mp4) as c:
        s = c.streams.video[0]
        assert (s.codec_context.name, s.codec_context.pix_fmt) == ('h264', 'yuv420p')
        assert (s.codec_context.width, s.codec_context.height) == (1280, 770)
        assert sum(1 for _ in c.decode(video=0)) == 30
    head = open(mp4, 'rb').read(4096)
    assert head.find(b'moov') != -1 and (head.find(b'mdat') == -1 or head.find(b'moov') < head.find(b'mdat'))
    gif = V.encode_gif(reel, tmp_path / 'demo.gif')
    from PIL import Image
    with Image.open(gif) as g:
        assert g.size == (960, 578) and g.n_frames >= 2
    with av.open(gif) as c:
        assert sum(1 for _ in c.decode(video=0)) == 24
    assert V.output_path(tmp_path / 'demo.mp4', 'gif') == tmp_path / 'demo.gif'


def test_a_long_film_is_shortened_to_the_limit(tmp_path):
    """'it will be slow' (user, 2026-11-18): a film longer than max_seconds has its held
    pictures shortened alike; the typing (one frame each) and the final pause stay."""
    reel = V.Reel(tmp_path / 'frames')
    for k in range(10):
        reel.add(_Picture((k * 20, 0, 0)), 0.1)            # typing
    for k in range(10):
        reel.add(_Picture((0, k * 20, 0)), 5.0)            # steps and answers: 50 s
    reel.hold(3.0)                                         # the result
    assert reel.seconds == 54.0
    assert not reel.fit(60) and reel.seconds == 54.0
    assert reel.fit(20, final_seconds=3.0)
    assert abs(reel.seconds - 20) <= 0.5
    assert [n for _, n in reel.shots[:10]] == [1] * 10 and reel.shots[-1][1] >= 30
    assert len({n for _, n in reel.shots[10:-1]}) == 1     # shortened alike


def test_film_a_range_of_a_chat(qapp, gui, runtime, tmp_path):  # noqa: F811
    """Requests 2-3 only: the figure starts as before request 2 (not rotated), only those
    requests are typed, their edits happen on screen, the export is not run again."""
    from pyfigures.assistant.partner_gui import panels
    chat = _chat(tmp_path)
    seen = {}

    def restored(window):
        seen['start'] = [(p.theta or 0, p.fill_color) for _, _, p in panels(window.paint.EZFIG_panel.shapes_to_draw)]
    options = V.Options(step_seconds=0.3, final_seconds=0.5, formats=())
    film = V.Film(chat, 2, 3, tmp_path / 'demo.mp4', options, work_dir=tmp_path / 'work', on_restored=restored)
    close = film._close

    def closing():
        seen['end'] = [p.fill_color for _, _, p in panels(film.window.paint.EZFIG_panel.shapes_to_draw)]
        close()
    film._close = closing
    report = film.run()
    assert report['requests'] == [2, 3] and report['typed'] == ['make all bgs of panels black', 'save it as a ppt']
    assert report['start']['kind'] == 'snapshot' and report['start_panels'] == 2
    # as before request 2 (the copy saved then: not rotated, backgrounds not black yet)
    assert len(seen['start']) == 2 and all(t == 0 and fill != 0 for t, fill in seen['start'])
    assert report['failed_now'] == [] and len(report['not_rerun']) == 1
    assert not (tmp_path / 'must_not_exist.pptx').exists()
    assert report['frames'] >= 20 and len(os.listdir(tmp_path / 'work' / 'frames')) == report['shots']
    assert seen['end'] == [0, 0]                 # the edit was made on screen
    # nothing written to the user's chats: the film's sidebar logged into the work folder
    assert film.dock.engine.journal.path.parent == tmp_path / 'work'


def test_film_starts_after_replaying_silently(qapp, gui, runtime, tmp_path):  # noqa: F811
    """Request 4's copy is gone: request 2's copy, requests 2 and 3 replayed silently (the
    export left out), then request 4 filmed."""
    from pyfigures.assistant.partner_gui import panels
    seen = {}

    def restored(window):
        seen['fill'] = [p.fill_color for _, _, p in panels(window.paint.EZFIG_panel.shapes_to_draw)]
    report = V.Film(_chat(tmp_path), 4, 4, None, V.Options(step_seconds=0.2, final_seconds=0.2, formats=()),
                    work_dir=tmp_path / 'work', on_restored=restored).run()
    assert report['start']['replay'] == [2, 3] and report['typed'] == ['make the letters red']
    assert seen['fill'] == [0, 0]
    assert not (tmp_path / 'must_not_exist.pptx').exists()


def test_the_dialog_lists_the_requests_and_makes_the_video(qapp, qtbot, gui, tmp_path):  # noqa: F811
    """Tools > Make a demo video from a chat…: first / last request, where the film starts,
    then the video made by a process of its own."""
    import av
    chat = _chat(tmp_path)
    g = gui()
    dialog = g.chat_video_action(str(chat))
    try:
        assert dialog.first.count() == dialog.last.count() == 4
        dialog.first.setCurrentIndex(2)
        dialog.last.setCurrentIndex(0)
        assert not dialog.make.isEnabled() and 'before the first' in dialog.start_note.text()
        dialog.first.setCurrentIndex(1)
        dialog.last.setCurrentIndex(2)
        assert dialog.make.isEnabled() and 'before request 2: the copy saved just before it' in dialog.start_note.text()
        assert dialog.out.text().endswith('chat_requests_2-3.mp4')
        dialog.out.setText(str(tmp_path / 'videos' / 'demo.mp4'))
        dialog.step.setValue(0.2)
        dialog.final.setValue(0.5)
        dialog.intermediate.setChecked(False)
        dialog.format.setCurrentIndex(1)                     # MP4 only
        _program, args = dialog.command()
        assert args[-11:] == ['-o', str(tmp_path / 'videos' / 'demo.mp4'), '--format', 'mp4', '--step', '0.2',
                              '--final', '0.5', '--max', '60', '--no-intermediate']
        dialog.start()
        qtbot.waitUntil(lambda: dialog.process is None, timeout=240000)
        assert dialog.outputs == [str(tmp_path / 'videos' / 'demo.mp4')], dialog.log.toPlainText()
        with av.open(dialog.outputs[0]) as c:
            assert c.streams.video[0].codec_context.width == 1280
        assert dialog.open_folder.isEnabled() and not (tmp_path / 'must_not_exist.pptx').exists()
    finally:
        dialog.close()


def test_mcp_make_chat_video(tmp_path):
    from PIL import Image
    from pyfigures.mcp_server import make_chat_video
    chat = _chat(tmp_path)
    assert 'choose requests from 1 to 4' in make_chat_video(str(chat), str(tmp_path / 'v.gif'), 3, 2)
    assert make_chat_video(str(chat), str(tmp_path / 'v.gif'), video_format='webm').startswith('ERROR')
    text = make_chat_video(str(chat), str(tmp_path / 'v.gif'), 1, 1, video_format='gif', step_seconds=0.2,
                           final_seconds=0.3, intermediate_messages=False)
    assert text.startswith('Filmed requests 1–1') and 'the copy saved just before it' in text, text
    with Image.open(tmp_path / 'v.gif') as g:
        assert g.size[0] == 960 and g.n_frames > 3


def test_cli_lists_the_requests(tmp_path, capsys):
    assert V.main([str(_chat(tmp_path)), '--list']) == 0
    out = capsys.readouterr().out.splitlines()
    assert len(out) == 4 and out[0].startswith('1. rotate all images') and 'copy of the figure' in out[0]
    assert 'copy of the figure' not in out[3]


def test_video_command():
    exe, args = V.video_command('c.jsonl', 2, 3, 'd.mp4', V.Options(intermediate=False))
    assert args[:2] == ['-m', 'pyfigures.assistant.chat_video']
    assert args[2:] == ['c.jsonl', '--from', '2', '--to', '3', '-o', 'd.mp4', '--format', 'both',
                        '--step', '1', '--final', '3', '--max', '60', '--no-intermediate']
