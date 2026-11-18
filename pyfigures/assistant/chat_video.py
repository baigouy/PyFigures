"""A demo video from a chat that already happened, without calling the model again.

The user (2026-11-18): live recordings work, but a video made afterwards from a chat whose
result turned out interesting is better: no model call, the result already known, the
pacing set for viewing; and only part of a chat, from a first to a last request.

How it is filmed (off-screen, in a process of its own: the GUI runs
``python -m pyfigures.assistant.chat_video``):

- the figure is put back as it was just before the first chosen request: the copy the
  chat sidebar saved before each request (``before.pyf`` of the request's document
  action, kept in <runtime>/assistant_actions); when that copy is gone, an earlier
  request's copy (or the empty figure the chat started on) with the requests in between
  replayed silently, without filming them;
- a PyFigures window with the chat sidebar docked; each chosen request is typed into the
  message box and sent, the edits the model made then are run again one by one through
  the same operations (chat_replay.Runner), the figure updating on screen, and the
  model's recorded answers appear in the sidebar as they did;
- about a second per step, three seconds on the final result (options), a
  "Replayed from the chat" label on every frame;
- MP4 (H.264, 1280 px wide, crf 22, yuv420p, faststart) and/or GIF (8 frames/s, 960 px
  wide, palettegen/paletteuse with a Bayer dither), written with PyAV.

Limits: the timing is not the real one; the images the chat used must still exist where
they were; edits made by hand between the requests were not recorded and are not shown;
a reply undone with its Undo button is left out (its edits did not stay).

Command line::

    python -m pyfigures.assistant.chat_video CHAT.jsonl --list
    python -m pyfigures.assistant.chat_video CHAT.jsonl --from 2 --to 4 -o demo.mp4 --format both
"""
from __future__ import annotations

import json
import math
import os
import shutil
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

FPS = 10                       # frames per second of the film (and of the MP4)
GIF_FPS = 8
MP4_WIDTH, GIF_WIDTH = 1280, 960
WINDOW_SIZE = (1500, 900)
DOCK_WIDTH = 470
LABEL = 'Replayed from the chat'
RUNS = ('edit', 'undo', 'redo')        # the calls replayed (reads change nothing on screen)
_WRITES = ('export', 'save', 'write_')
_OUT_KEYS = ('out_path', 'output_path', 'out', 'output', 'destination', 'save_path')


def writes_files(step) -> bool:
    """A call that writes files (an export, a save): never run again for a video, it
    would overwrite the files the chat wrote then."""
    args = step.arguments if isinstance(step.arguments, dict) else {}
    return step.tool.startswith(_WRITES) or any(k in args for k in _OUT_KEYS) \
        or any(isinstance(b, dict) and any(k in b for k in _OUT_KEYS) for b in (step.batch or []))


@dataclass
class Request:
    """One request of the chat, numbered from 1 in the order they were sent."""
    number: int
    text: str
    turn: object = None                 # qtpy_ai_sidecar.procedures.Turn
    before: str | None = None           # the figure just before it (.pyf), when saved
    action: dict | None = None          # the chat's document action for it (Undo button)
    model: str = ''
    setup: bool = False
    undone: bool = False
    chat_started_empty: bool | None = None      # the figure at the chat's first request
    chat_document: str | None = None            # its file then, if saved

    @property
    def edits(self) -> int:
        return sum(1 for s in self.turn.calls() if s.role in RUNS and not s.recorded_error) if self.turn else 0

    def label(self, width=70) -> str:
        text = ' '.join(self.text.split())
        text = text if len(text) <= width else text[:width - 1] + '…'
        flag = ' (undone in the chat: not filmed)' if self.undone else ''
        return f'{self.number}. {text}{flag}'


def requests_of(chat) -> list[Request]:
    """The requests of a chat log (or of the sidebar's debug zip), in order, each with
    the copy of the figure saved just before it and the model that answered."""
    from .chat_replay import _sidecar
    P, adapter = _sidecar()
    events = P.read_events(chat)
    turns = P.load_turns(chat, adapter)
    out = [Request(k, t.request, t, setup=t.setup, undone=t.undone) for k, t in enumerate(turns, 1)]
    k, empty_start, document = 0, None, None
    for event in events:
        kind, value = event.get('kind'), event.get('value')
        if kind == 'user':
            k += 1
            continue
        if not 0 < k <= len(out):
            continue
        r = out[k - 1]
        if kind == 'action' and isinstance(value, dict) and value.get('before') and r.before is None:
            r.before, r.action = str(value['before']), value
        elif kind == 'request_settings' and isinstance(value, dict) and not r.model:
            r.model = str(value.get('model') or '')
        elif kind == 'host_context' and isinstance(value, dict) and k == 1 and empty_start is None:
            empty_start = bool((value.get('figure_summary') or {}).get('empty'))
            document = (value.get('document') or {}).get('file')
    for r in out:
        r.chat_started_empty, r.chat_document = empty_start, document
    return out


def start_state(requests, first) -> dict:
    """How to put the figure back as it was just before request *first*:
    {'kind': 'snapshot' | 'empty' | 'document', 'path', 'replay': [request numbers run
    silently first], 'note'}."""
    if not 1 <= first <= len(requests):
        raise ValueError(f'request {first} is not in this chat (1 to {len(requests)})')
    for k in range(first, 0, -1):
        before = requests[k - 1].before
        if before and Path(before).is_file():
            note = ('the copy saved just before it' if k == first else
                    f'the copy saved before request {k}, then requests {k}–{first - 1} replayed silently')
            return {'kind': 'snapshot', 'path': before, 'replay': list(range(k, first)), 'note': note}
    if requests[0].chat_started_empty:
        return {'kind': 'empty', 'path': None, 'replay': list(range(1, first)),
                'note': 'the empty figure the chat started on' + (f', then requests 1–{first - 1} replayed silently'
                                                                    if first > 1 else '')}
    document = requests[0].chat_document
    if document and Path(document).is_file():
        return {'kind': 'document', 'path': document, 'replay': list(range(1, first)),
                'note': f'{Path(document).name} as saved now (no copy of the figure from the chat is left)'
                        + (f', then requests 1–{first - 1} replayed silently' if first > 1 else '')}
    raise ValueError('No copy of the figure from before this request is left (the chat\'s copies are gone and '
                     'the chat did not start on an empty or saved figure): the video cannot start from the '
                     'right figure.')


# -- the frames --------------------------------------------------------------------------
class Reel:
    """The film as distinct pictures (PNG files in *folder*), each shown for a number of
    frames at FPS."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.shots = []                     # [file name, frames]

    def add(self, image, seconds):
        name = f'{len(self.shots):05d}.png'
        if not image.save(str(self.folder / name), 'PNG'):
            raise OSError(f'could not write the frame {self.folder / name}')
        self.shots.append([name, max(1, round(seconds * FPS))])

    def hold(self, seconds):
        if self.shots:
            self.shots[-1][1] += max(0, round(seconds * FPS))

    @property
    def frames(self) -> int:
        return sum(n for _, n in self.shots)

    @property
    def seconds(self) -> float:
        return self.frames / FPS

    def timeline(self, fps=FPS):
        """The picture of each frame at *fps* (file names, repeated while held)."""
        names = [name for name, n in self.shots for _ in range(n)]
        if not names:
            return []
        count = max(1, math.floor(len(names) * fps / FPS))
        return [names[min(len(names) - 1, math.floor(i * FPS / fps))] for i in range(count)]


def _scaled(path, width):
    from PIL import Image
    image = Image.open(path).convert('RGB')
    height = max(2, round(image.height * width / image.width / 2) * 2)
    return image.resize((width, height), Image.LANCZOS)


def encode_mp4(reel, out_path, width=MP4_WIDTH, crf=22):
    """H.264, yuv420p, faststart (plays in browsers and on forums)."""
    import av
    container = av.open(str(out_path), 'w', options={'movflags': '+faststart'})
    try:
        stream = None
        for k, name in enumerate(reel.timeline(FPS)):
            frame = av.VideoFrame.from_image(_scaled(reel.folder / name, width))
            if stream is None:
                stream = container.add_stream('libx264', rate=FPS)
                stream.width, stream.height, stream.pix_fmt = frame.width, frame.height, 'yuv420p'
                stream.options = {'crf': str(crf), 'preset': 'slow'}
            frame = frame.reformat(format='yuv420p')
            frame.pts = k
            for packet in stream.encode(frame):
                container.mux(packet)
        if stream is not None:
            for packet in stream.encode(None):
                container.mux(packet)
    finally:
        container.close()
    return str(out_path)


def _drain(sink):
    import av
    out = []
    while True:
        try:
            out.append(sink.pull())
        except (av.BlockingIOError, av.EOFError):
            return out


def encode_gif(reel, out_path, width=GIF_WIDTH, fps=GIF_FPS):
    """palettegen over the whole film, then paletteuse with a Bayer dither."""
    import av
    names = reel.timeline(fps)
    if not names:
        raise ValueError('no frame to write')
    base = time_base = Fraction(1, fps)
    cache = {}

    def picture(name):
        if name not in cache:
            cache.clear()
            cache[name] = _scaled(reel.folder / name, width)
        return cache[name]

    def frame(name, k):
        f = av.VideoFrame.from_image(picture(name))
        f.pts, f.time_base = k, time_base
        return f

    first = picture(names[0])
    graph = av.filter.Graph()
    source = graph.add_buffer(width=first.width, height=first.height, format='rgb24', time_base=base)
    palettegen = graph.add('palettegen', 'max_colors=192:stats_mode=diff')
    sink = graph.add('buffersink')
    source.link_to(palettegen)
    palettegen.link_to(sink)
    graph.configure()
    previous = None
    for k, name in enumerate(names):
        if name != previous:                # stats_mode=diff: a held picture adds nothing
            source.push(frame(name, k))
            previous = name
    source.push(None)
    palette = _drain(sink)[0]

    graph = av.filter.Graph()
    source = graph.add_buffer(width=first.width, height=first.height, format='rgb24', time_base=base)
    palette_source = graph.add_buffer(width=palette.width, height=palette.height, format=palette.format.name,
                                      time_base=base)
    use = graph.add('paletteuse', 'dither=bayer:bayer_scale=4:diff_mode=rectangle')
    sink = graph.add('buffersink')
    source.link_to(use, 0, 0)
    palette_source.link_to(use, 0, 1)
    use.link_to(sink)
    graph.configure()
    palette.pts, palette.time_base = 0, base
    palette_source.push(palette)
    palette_source.push(None)
    container = av.open(str(out_path), 'w')
    try:
        stream = container.add_stream('gif', rate=fps)
        stream.width, stream.height, stream.pix_fmt = first.width, first.height, 'pal8'
        k = 0
        for k, name in enumerate(names):
            source.push(frame(name, k))
            for out in _drain(sink):
                for packet in stream.encode(out):
                    container.mux(packet)
        source.push(None)
        for out in _drain(sink):
            for packet in stream.encode(out):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    finally:
        container.close()
    return str(out_path)


# -- the filming ------------------------------------------------------------------------
@dataclass
class Options:
    step_seconds: float = 1.0           # each edit, each short message
    final_seconds: float = 3.0          # the result, at the end
    intermediate: bool = True           # the model's messages before its last one
    formats: tuple = ('mp4', 'gif')     # () films only (frames kept in the work folder)
    typing_seconds: float = 2.5         # at most, for a long request


def _wait(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _run_in_thread(app, fn):
    box = {}

    def work():
        try:
            box['out'] = fn()
        except Exception as exc:
            box['error'] = exc
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    while worker.is_alive():
        app.processEvents()
        worker.join(0.02)
    if 'error' in box:
        raise box['error']
    return box.get('out')


def _images_loaded(app, window, timeout=60):
    end = time.monotonic() + timeout
    while time.monotonic() < end and (getattr(window, '_active_img_loaders', None)
                                      or getattr(window, '_lazy_img_queue', None)):
        app.processEvents()
        time.sleep(0.02)


def _label(image, text, area=None):
    """*text* in a dark rounded box at the bottom right of *area* (a QRect of the
    picture: the figure's canvas; the canvas' zoom buttons are at its bottom left)."""
    from qtpy.QtCore import QRectF, Qt
    from qtpy.QtGui import QColor, QFont, QPainter
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont('Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans')
        font.setPixelSize(max(14, image.height() // 42))
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w, h = metrics.horizontalAdvance(text) + 28, metrics.height() + 12
        right, bottom = (area.right(), area.bottom()) if area is not None else (image.width(), image.height())
        box = QRectF(right - w - 28, bottom - h - 28, w, h)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 30, 190))
        painter.drawRoundedRect(box, 9, 9)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)
    finally:
        painter.end()
    return image


class Film:
    """Films requests *first*..*last* of *chat* (numbers from requests_of) off-screen.
    Call run() with a QApplication on the offscreen platform (main() makes one)."""

    def __init__(self, chat, first, last, out_path=None, options=None, work_dir=None, progress=None,
                 on_restored=None):
        self.chat, self.first, self.last = str(chat), int(first), int(last)
        self.on_restored = on_restored          # fn(window) once the starting figure is back
        self.out_path = Path(out_path) if out_path else None
        self.options = options or Options()
        self.work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix='pyfigures_chat_video_'))
        self.progress = progress or (lambda text: None)
        self.requests = requests_of(self.chat)
        if not 1 <= self.first <= self.last <= len(self.requests):
            raise ValueError(f'choose requests from 1 to {len(self.requests)}, the first before the last '
                             f'(got {self.first} to {self.last})')
        self.start = start_state(self.requests, self.first)
        self.report = {'chat': self.chat, 'requests': [], 'skipped': [], 'failed_now': [], 'not_rerun': [],
                       'start': self.start,
                       'outputs': [], 'frames_folder': str(self.work / 'frames')}

    # the window -----------------------------------------------------------------------
    def _open(self):
        from qtpy.QtCore import Qt
        from qtpy.QtWidgets import QApplication
        from pyfigures.gui.pfgui import EZFIG_GUI
        from .partner_gui import PartnerGUI
        from . import launch
        import qtpy_ai_sidecar.credentials as credentials
        from qtpy_ai_sidecar.widgets import ModelPicker
        self.app = QApplication.instance()
        # nothing reaches the model's provider: no model list, no key look-up
        self._patches = [(EZFIG_GUI, 'show_tips', lambda self: None),
                         (ModelPicker, 'load_in_background', lambda self: None),
                         (credentials, 'key_state', lambda config: None)]
        self._saved = [(o, n, o.__dict__.get(n, getattr(o, n, None))) for o, n, _ in self._patches]
        for owner, name, value in self._patches:
            setattr(owner, name, value)
        self._runtime = os.environ.get('PYFIGURES_LIVE_RUNTIME')
        # a runtime folder of its own: never the one of a PyFigures open on this computer
        os.environ['PYFIGURES_LIVE_RUNTIME'] = str(self.work / 'runtime')
        (self.work / 'runtime').mkdir(parents=True, exist_ok=True)
        window = PartnerGUI()
        window._edit_hint_shown = True
        window.show()
        window.resize(*WINDOW_SIZE)
        dock = launch.attach_sidecar(window)
        self.dock, self.window = dock, dock.parent()
        self.window._edit_hint_shown = True
        self.window.show()
        self.window.resize(*WINDOW_SIZE)
        self.window.resizeDocks([dock], [DOCK_WIDTH], Qt.Orientation.Horizontal)
        # anything the chat would write goes to the work folder, never to the user's chats
        dock.engine.journal.path = self.work / 'film_journal.jsonl'
        dock.timer.stop()
        model = next((r.model for r in self.requests[self.first - 1:self.last] if r.model), '')
        if model:
            dock.engine.config.model = model
            dock.model_picker.sync()
        self.session = self.window._live_session
        _wait(self.app, 0.2)

    def _close(self):
        from . import launch
        try:
            launch.stop_live_session(self.window)
            self.dock.closed = True
            self.window._dirty = False
            self.window.close()
        finally:
            for owner, name, value in self._saved:
                setattr(owner, name, value)
            if self._runtime is None:
                os.environ.pop('PYFIGURES_LIVE_RUNTIME', None)
            else:
                os.environ['PYFIGURES_LIVE_RUNTIME'] = self._runtime

    def _restore(self):
        """The figure as it was just before the first request filmed."""
        from .assistant_actions import adopt
        from .chat_replay import procedure_steps
        kind, path = self.start['kind'], self.start['path']
        if kind == 'snapshot' and Path(path).with_suffix('.ui.json').is_file():
            adopt(self.session, Path(path))
        elif kind in ('snapshot', 'document'):
            self.window.reload_state(str(path), append=False)
        _images_loaded(self.app, self.window)
        if self.start['replay']:
            self.progress(f'replaying requests {self.start["replay"][0]}–{self.start["replay"][-1]} silently')
            steps = [s for n in self.start['replay'] for s in self._steps(self.requests[n - 1])]
            for step in procedure_steps(steps):
                if not writes_files(step):
                    self._run(step, silent=True)
        self.report['start_panels'] = self._panel_count()
        if self.on_restored is not None:
            self.on_restored(self.window)
        self._fit()

    def _panel_count(self):
        from .partner_gui import panels
        return len(list(panels(self.window.paint.EZFIG_panel.shapes_to_draw)))

    def _steps(self, request):
        from .chat_replay import Step
        out = []
        for g in request.turn.calls():
            s = Step.from_call(g.request, g.turn, g.call, g.arguments)
            s.role, s.reads_only = g.role, g.role in ('read', 'skip')
            s.recorded_error, s.turn_undone = g.recorded_error, g.turn_undone
            out.append(s)
        return out

    def _run(self, step, silent=False):
        if not hasattr(self, 'runner'):
            from .chat_replay import Runner
            self.runner = Runner()
        try:
            _run_in_thread(self.app, lambda: self.runner.run(step))
        except Exception as exc:
            self.report['failed_now'].append({'request': step.request, 'operation': step.describe()[:200],
                                              'error': str(exc)[:300], 'silent': silent})
        _images_loaded(self.app, self.window)

    def _fit(self):
        try:
            self.window.paint.fit_to_window()
        except Exception:
            pass

    # the pictures ---------------------------------------------------------------------
    def _shot(self, seconds):
        _wait(self.app, 0.05)
        from qtpy.QtCore import QPoint, QRect
        image = self.window.grab().toImage()
        model = next((r.model for r in self.requests[self.first - 1:self.last] if r.model), '')
        canvas = self.window.paint
        area = QRect(canvas.mapTo(self.window, QPoint(0, 0)), canvas.size()) if canvas.isVisible() else None
        self.reel.add(_label(image, LABEL + (f' · {model}' if model else ''), area), seconds)

    def _status(self, text):
        self.dock.activity_text = text
        self.dock.status.setText(text)

    def _type(self, text):
        from qtpy.QtGui import QTextCursor
        frames = max(1, round(self.options.typing_seconds * FPS))
        per_frame = max(2, math.ceil(len(text) / frames))
        for end in list(range(per_frame, len(text), per_frame)) + [len(text)]:
            self.dock.input.setPlainText(text[:end])
            self.dock.input.moveCursor(QTextCursor.MoveOperation.End)
            self._shot(1 / FPS)
        self.reel.hold(0.5)

    def _send(self, text):
        """What the sidebar does when a message is sent, without the model."""
        self.dock.clear_choices()
        self.dock.last_assistant = ''
        self.dock.last_assistant_layout = None
        self.dock.input.clear()
        self.dock.add_message('user', text)
        self.report.setdefault('typed', []).append(text)
        self._done = threading.Event()

        async def waiting():
            import asyncio
            while not self._done.is_set():
                await asyncio.sleep(0.02)
        self.dock.run(waiting)
        self.dock.timer.stop()

    def _finish(self, request):
        self.dock.started = time.monotonic() - request.turn.seconds      # "Finished · 12.3s", as then
        self._done.set()
        end = time.monotonic() + 10
        while self.dock.busy and time.monotonic() < end:
            self.app.processEvents()
            time.sleep(0.01)
        if self.dock.thread is not None:
            self.dock.thread.join(5)

    def _reading(self, text):
        """Time to read a message: a step for a short one, up to four."""
        return self.options.step_seconds * max(1.0, min(4.0, len(text.split()) / 25))

    def _film(self, request):
        o = self.options
        self.progress(f'request {request.number}: {request.label(60)}')
        self._type(request.text)
        self._send(request.text)
        self._status('Thinking…')
        self._shot(o.step_seconds / 2)
        answers = [k for k, (kind, _) in enumerate(request.turn.items) if kind == 'assistant']
        last_answer = answers[-1] if answers else None
        steps = iter(self._steps(request))
        for k, (kind, item) in enumerate(request.turn.items):
            if kind == 'call':
                step = next(steps)
                if writes_files(step):
                    if not step.recorded_error:
                        self._status(step.tool.replace('_', ' ') + ' (not repeated for the video)')
                        self.report['not_rerun'].append(step.describe()[:200])
                elif step.role in RUNS and not step.recorded_error:
                    self._status('Running ' + step.tool.replace('_', ' '))
                    self._run(step)
                    self._fit()
                    self._shot(o.step_seconds)
                elif o.intermediate and step.role == 'read':
                    self._status('Checking: ' + step.tool.replace('_', ' '))
            elif kind == 'assistant' and (k == last_answer or o.intermediate):
                if k == last_answer:
                    continue                    # shown after the turn, with its Undo button
                self.dock.receive('assistant', item)
                self._shot(self._reading(item))
        if last_answer is not None:
            text = request.turn.items[last_answer][1]
            self.dock.receive('assistant', text)
            if request.action and request.action.get('status') == 'applied':
                self.dock.receive('action', request.action)
        self._finish(request)
        self._fit()
        self._shot(self._reading(text) if last_answer is not None else o.step_seconds)
        self.report['requests'].append(request.number)

    def run(self) -> dict:
        self.reel = Reel(self.work / 'frames')
        self._open()
        try:
            self.progress('restoring the figure: ' + self.start['note'])
            self._restore()
            self._shot(self.options.step_seconds)
            for request in self.requests[self.first - 1:self.last]:
                if request.undone:
                    self.report['skipped'].append(request.number)
                    continue
                self._film(request)
            self.reel.hold(self.options.final_seconds)
        finally:
            self._close()
        self.report['frames'], self.report['seconds'] = self.reel.frames, round(self.reel.seconds, 1)
        self.report['shots'] = len(self.reel.shots)
        for fmt in self.options.formats:
            out = output_path(self.out_path or Path(self.chat).with_suffix(''), fmt)
            self.progress(f'writing {out}')
            (encode_mp4 if fmt == 'mp4' else encode_gif)(self.reel, out)
            self.report['outputs'].append(str(out))
        return self.report


def output_path(path, fmt) -> Path:
    path = Path(path)
    return path.with_suffix('.' + fmt) if path.suffix.lower() in ('.mp4', '.gif', '') else \
        path.with_name(path.name + '.' + fmt)


def make_video(chat, first, last, out_path, options=None, work_dir=None, progress=None, keep_frames=False,
               on_restored=None) -> dict:
    """Film requests *first*..*last* of *chat* into *out_path* (.mp4 and/or .gif, from
    options.formats). Needs a QApplication on the offscreen platform."""
    film = Film(chat, first, last, out_path, options, work_dir, progress, on_restored)
    try:
        return film.run()
    finally:
        if not keep_frames and work_dir is None:
            shutil.rmtree(film.work, ignore_errors=True)


def video_command(chat, first, last, out_path, options=None) -> tuple[str, list]:
    """(program, arguments) making the video in a process of its own (the window is
    filmed off-screen there). In a standalone app, PyFigures itself with --chat-video
    (on Windows its console twin, which has a usable stdout for the progress)."""
    o = options or Options()
    fmt = 'both' if set(o.formats) == {'mp4', 'gif'} else (o.formats[0] if o.formats else 'mp4')
    args = [str(chat), '--from', str(first), '--to', str(last), '-o', str(out_path), '--format', fmt,
            '--step', f'{o.step_seconds:g}', '--final', f'{o.final_seconds:g}']
    if not o.intermediate:
        args.append('--no-intermediate')
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        if sys.platform == 'win32':
            twin = os.path.join(os.path.dirname(exe), 'PyFigures MCP.exe')
            if os.path.isfile(twin):
                exe = twin
        return exe, ['--chat-video'] + args
    return sys.executable, ['-m', 'pyfigures.assistant.chat_video'] + args


def main(argv=None) -> int:
    import argparse
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog='python -m pyfigures.assistant.chat_video',
                                description='A demo video (MP4 / GIF) of part of a chat, replayed without the model.')
    p.add_argument('chat', help='chat log (.jsonl) or the chat sidebar\'s debug zip')
    p.add_argument('--list', action='store_true', help='list the requests of the chat and exit')
    p.add_argument('--from', dest='first', type=int, default=1, help='first request filmed (from 1)')
    p.add_argument('--to', dest='last', type=int, help='last request filmed (default: the last one)')
    p.add_argument('-o', '--out', help='output file (.mp4 / .gif; default: next to the chat log)')
    p.add_argument('--format', choices=('mp4', 'gif', 'both'), default=None,
                   help='default: from the -o extension, else both')
    p.add_argument('--step', type=float, default=1.0, help='seconds per step (default 1)')
    p.add_argument('--final', type=float, default=3.0, help='seconds on the final result (default 3)')
    p.add_argument('--no-intermediate', action='store_true', help='only the model\'s last message of each request')
    p.add_argument('--keep-frames', metavar='FOLDER', help='keep the frames (PNG) in FOLDER')
    a = p.parse_args(argv)
    requests = requests_of(a.chat)
    if a.list:
        for r in requests:
            mark = ' [copy of the figure before it]' if r.before and Path(r.before).is_file() else ''
            print(f'{r.label(100)} — {r.edits} edit(s){mark}')
        return 0
    last = a.last or len(requests)
    fmt = a.format or {'.mp4': 'mp4', '.gif': 'gif'}.get(Path(a.out).suffix.lower() if a.out else '', 'both')
    formats = ('mp4', 'gif') if fmt == 'both' else (fmt,)
    options = Options(step_seconds=a.step, final_seconds=a.final, intermediate=not a.no_intermediate,
                      formats=formats)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    if os.environ['QT_QPA_PLATFORM'].split(':')[0] != 'offscreen':
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from pyfigures.offscreen import ensure_offscreen_fonts
    ensure_offscreen_fonts()
    from batoolset.settings.global_settings import set_UI
    set_UI()
    from qtpy.QtGui import QFont
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setFont(QFont('Segoe UI' if sys.platform == 'win32' else 'DejaVu Sans', 9))
    out = a.out or str(Path(a.chat).with_suffix('')) + f'_requests_{a.first}-{last}.mp4'
    report = make_video(a.chat, a.first, last, out, options, work_dir=a.keep_frames,
                        progress=lambda text: print('PROGRESS ' + text, flush=True),
                        keep_frames=bool(a.keep_frames))
    for path in report['outputs']:
        print(f'{path} ({report["seconds"]} s)')
    for failed in report['failed_now']:
        print(f'failed now: {failed["operation"][:100]}: {failed["error"][:150]}')
    # one line for the dialog that started this process (stderr may be mixed in)
    print('REPORT ' + json.dumps(report, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    os._exit(code)          # Qt and the live session's threads: no slow, noisy teardown
