"""Replay a chat: the operations a chat model ran, again, without the model.

Two uses (user, 2026-11-13):
- debugging: step through a recorded chat one operation at a time on the open figure,
  see what each one did then and does now, change its arguments and run it again
  (Tools > Replay a chat…);
- procedures: the operations that changed the figure, saved as a procedure file
  (JSON) and run in one go on any figure, to repeat the same steps on every figure
  (Tools > Run a procedure…, MCP run_procedure, recipe ``procedure:``, or
  ``python -m pyfigures.assistant.chat_replay run steps.json figure.pyf``).

The chat log is the sidecar's journal (one JSON event per line, kept in
<user data>/qtpy-ai-sidecar/PyFigures/chats), or the "sidecar-debug" zip its Debug
export writes. The model's calls are replayed exactly as it made them: panels are
named by their letters (or panel numbers), so a procedure fits figures laid out like
the one it was recorded on. Edits made by hand between the chat's requests were not
recorded and are not replayed.
"""
from __future__ import annotations

import asyncio
import json
import os
import zipfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

PROCEDURE_VERSION = 1
DISPATCHER = 'use_pyfigures_tool'

# Reading chat logs and choosing the steps that stayed is the chat sidecar's
# (qtpy_ai_sidecar.procedures, shared by every application it serves); procedure files
# are plain JSON, read here too, so recipes, the MCP server and the command line run
# them without the sidecar installed.


@dataclass
class Step:
    """One operation of the chat. *tool* is the PyFigures operation (for a
    use_pyfigures_tool call, the operation it named)."""
    request: str
    turn: int
    tool: str
    arguments: dict = field(default_factory=dict)
    batch: list | None = None
    direct: bool = False            # called by its own name, not through use_pyfigures_tool
    recorded_error: bool = False
    recorded_result: str = ''
    reads_only: bool = False
    turn_undone: bool = False
    role: str = 'edit'              # edit, read, undo, redo, skip (the sidecar's PyFigures adapter)

    def call(self):
        """The MCP call it is: (name, arguments)."""
        if self.direct:
            return self.tool, dict(self.arguments)
        return DISPATCHER, {'tool_name': self.tool, 'arguments': dict(self.arguments),
                            **({'batch': self.batch} if self.batch else {})}

    @classmethod
    def from_call(cls, request, turn, name, arguments):
        if name == DISPATCHER:
            return cls(request, turn, str(arguments.get('tool_name', '')), dict(arguments.get('arguments') or {}),
                       arguments.get('batch') or None, False)
        return cls(request, turn, name, dict(arguments or {}), None, True)

    def describe(self) -> str:
        args = {k: v for k, v in self.arguments.items() if k != 'pyf_path'}
        text = self.tool + ' ' + json.dumps(args, ensure_ascii=False)
        if self.batch:
            text += f' × {len(self.batch)}'
        return text


def chats_folder() -> Path:
    """Where the chat sidebar keeps its logs."""
    from platformdirs import user_data_path
    return user_data_path('qtpy-ai-sidecar', appauthor=False) / 'PyFigures' / 'chats'


def recent_chats(limit=30) -> list[Path]:
    folder = chats_folder()
    if not folder.is_dir():
        return []
    return sorted(folder.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def _sidecar():
    """The chat sidecar's procedures module and its PyFigures adapter (it wrote the logs)."""
    try:
        from qtpy_ai_sidecar import procedures
        from qtpy_ai_sidecar.adapters.pyfigures import PyFiguresAdapter
    except ImportError as exc:
        raise ValueError('Reading chat logs needs the chat sidebar package: pip install qtpy-ai-sidecar') from exc
    return procedures, PyFiguresAdapter('unused')


def load_steps(path) -> list[Step]:
    """Every operation of the chat log *path* (or debug zip), in order, with the request
    it answered and what it gave then."""
    P, adapter = _sidecar()
    steps = []
    for g in P.load_steps(path, adapter):
        s = Step.from_call(g.request, g.turn, g.call, g.arguments)
        s.role, s.reads_only = g.role, g.role in ('read', 'skip')
        s.recorded_error, s.recorded_result, s.turn_undone = g.recorded_error, g.recorded_result, g.turn_undone
        steps.append(s)
    return steps


def reads_only(tool: str, arguments: dict | None = None) -> bool:
    P, adapter = _sidecar()
    return adapter.procedure_role(tool, arguments or {}) in ('read', 'skip')


def procedure_steps(steps) -> list[Step]:
    """The steps a procedure keeps: the ones that changed the figure and stayed (not the
    reads, not the failed calls, not a reply undone with its Undo button, not an edit the
    chat undid itself with undo_redo, which a redo puts back)."""
    P, _adapter = _sidecar()
    return P.kept_steps(steps)


def _document(path):
    P, _adapter = _sidecar()
    return P.document_of(path)


def _templated(value, folder, name):
    """A path under the chat's figure folder / with its name: "{folder}", "{name}"."""
    if isinstance(value, str) and folder and name and ('/' in value or '\\' in value):
        norm, base = value.replace('\\', '/'), folder.replace('\\', '/').rstrip('/')
        if norm.lower().startswith(base.lower() + '/'):
            rest = norm[len(base) + 1:]
            stem, dot, ext = rest.rpartition('.')
            if dot and stem == name:
                rest = '{name}.' + ext
            return '{folder}/' + rest
    if isinstance(value, dict):
        return {k: _templated(v, folder, name) for k, v in value.items()}
    if isinstance(value, list):
        return [_templated(v, folder, name) for v in value]
    return value


def save_procedure(steps, out_path, name=None, source=None) -> str:
    """Write *steps* as a procedure file, in the chat sidecar's format (each step one MCP
    call), so its Procedures menu runs it too."""
    folder, figure = _document(source) if source else (None, None)
    data = {'procedure': PROCEDURE_VERSION, 'application': 'PyFigures', 'name': name or Path(out_path).stem,
            'source_chat': str(source) if source else None,
            'note': 'Run with Tools > Run a procedure…, the chat\'s Procedures menu, MCP run_procedure, '
                    'recipe procedure:, or python -m pyfigures.assistant.chat_replay run THIS.json figure.pyf. '
                    'Panels are named by their letters; {folder} / {name} are the folder and name of the '
                    'figure it runs on.',
            'steps': [{'request': s.request, 'call': s.call()[0],
                       'arguments': _templated(s.call()[1], folder, figure)} for s in steps]}
    Path(out_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    return str(out_path)


def load_procedure(path) -> list[Step]:
    """The steps of a procedure file: the sidecar's format ("call" per step) or the first
    PyFigures one ("tool", "arguments", "batch")."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or not isinstance(data.get('steps'), list):
        raise ValueError(f'{Path(path).name} is not a PyFigures procedure (no "steps")')
    steps = []
    for k, s in enumerate(data['steps'], 1):
        if isinstance(s, dict) and s.get('call'):
            steps.append(Step.from_call(s.get('request', ''), k, s['call'], dict(s.get('arguments') or {})))
        elif isinstance(s, dict) and s.get('tool'):
            steps.append(Step(s.get('request', ''), k, s['tool'], dict(s.get('arguments') or {}),
                              s.get('batch') or None, bool(s.get('direct'))))
        else:
            raise ValueError(f'step {k} of {Path(path).name} names no operation ("call")')
    return steps


def procedures_in_zip(path) -> list[Path]:
    """The procedures (.json) of a zip, extracted to a temporary folder, sorted by
    name; [] when it holds none (a zip of procedures, e.g. one per past chat)."""
    import tempfile
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if n.lower().endswith('.json') and not n.endswith('/'))
        if not names:
            return []
        folder = Path(tempfile.mkdtemp(prefix='pyfigures_procedures_'))
        out = []
        for n in names:
            target = folder / Path(n).name           # flat: no path from the zip is trusted
            target.write_bytes(z.read(n))
            try:
                load_procedure(target)
            except ValueError:
                continue
            out.append(target)
        return out


def _fill(value, folder, name):
    if isinstance(value, str):
        return value.replace('{folder}', folder or '.').replace('{name}', name or 'figure')
    if isinstance(value, dict):
        return {k: _fill(v, folder, name) for k, v in value.items()}
    if isinstance(value, list):
        return [_fill(v, folder, name) for v in value]
    return value


REDACTED = '[REDACTED]'


def _current_token(arguments):
    """An annotation edit replayed from a chat log: the log redacts every "token" key, so
    the object's stale-check token (a hash of what the model had inspected, no secret) is
    read again from the object at that index now. Any other arguments are unchanged."""
    if not isinstance(arguments, dict) or arguments.get('token') != REDACTED \
            or not isinstance(arguments.get('annotation_index'), int):
        return arguments
    from .live_mcp import call_live
    index, offset = arguments['annotation_index'], 0
    while offset is not None:
        found = call_live('inspect_annotation_objects', dict(panel_ref=arguments.get('panel_ref'), offset=offset,
                                                             limit=24, include_panel_letters=True))
        if not isinstance(found, dict):
            break
        pool = found.get('editor_draft_objects') if found.get('edit_target') == 'editor_draft' else found.get('objects')
        for obj in pool or []:
            if obj.get('annotation_index') == index and obj.get('token'):
                return {**arguments, 'token': obj['token']}
        offset = found.get('next_offset') if found.get('edit_target') != 'editor_draft' else None
    return arguments


class Runner:
    """Runs steps on the figure shared by the live session (the open window), through
    the same dispatcher the chat uses. Call run() from a thread other than the Qt one:
    the session answers on the Qt thread."""

    def __init__(self, document=None):
        from . import live_mcp
        from .categorized_mcp import build_server
        self.tools = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools
        self.document = document or (None, None)

    def run(self, step: Step):
        """The result of *step* (text or JSON), or raises its error."""
        folder, name = self.document
        arguments = _current_token(_fill(step.arguments, folder, name))
        batch = [_current_token(b) for b in _fill(step.batch, folder, name)] if step.batch else None
        if step.direct:
            tool = self.tools.get(step.tool)
            if tool is None:
                raise ValueError(f'{step.tool} is not an operation of this PyFigures')
            out = tool.fn(**arguments)
        else:
            out = self.tools['use_pyfigures_tool'].fn(tool_name=step.tool, arguments=arguments, batch=batch)
        if asyncio.iscoroutine(out):
            out = asyncio.run(out)
        text = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)
        if text.lstrip().startswith('ERROR'):
            raise ValueError(text)
        return out


def result_text(out, limit=4000) -> str:
    if isinstance(out, str):
        text = out
    elif isinstance(out, list):
        text = '\n'.join(result_text(o, limit) for o in out)
    else:
        text = getattr(out, 'text', None) or json.dumps(out, ensure_ascii=False, default=str, indent=1)
    return text if len(text) <= limit else text[:limit] + '…'


# -- a procedure on a .pyf file (no window open): an off-screen window shares it ------------
def run_procedure_on_file(procedure, pyf_path, out_path=None, stop_on_error=True) -> dict:
    """Open *pyf_path* in an off-screen PyFigures window, run every step of
    *procedure* (a path or a list of Steps), save to *out_path* (default: in place).
    Returns {'done', 'failed': [(step number, error)], 'output'}."""
    import threading
    from batoolset.settings.global_settings import set_UI
    from qtpy.QtWidgets import QApplication
    set_UI()
    app = QApplication.instance() or QApplication([])
    steps = load_procedure(procedure) if isinstance(procedure, (str, Path)) else list(procedure)
    from pyfigures.gui.pfgui import EZFIG_GUI
    from .partner_gui import PartnerGUI
    from . import launch
    import tempfile
    EZFIG_GUI.show_tips = lambda self: None
    window = PartnerGUI()
    window.reload_state(str(pyf_path), append=False)
    window.current_file = str(pyf_path)
    # a runtime folder of its own: a PyFigures window sharing its figure with the chat
    # (same user folder) would refuse a second shared window
    saved_runtime = os.environ.get('PYFIGURES_LIVE_RUNTIME')
    os.environ['PYFIGURES_LIVE_RUNTIME'] = tempfile.mkdtemp(prefix='pyfigures_procedure_')
    launch.start_live_session(window)
    path = Path(pyf_path)
    runner = Runner((str(path.parent), path.stem))
    done, failed = 0, []
    try:
        for number, step in enumerate(steps, 1):
            box = {}

            def work():
                try:
                    box['out'] = runner.run(step)
                except Exception as e:
                    box['error'] = e
            t = threading.Thread(target=work)
            t.start()
            while t.is_alive():
                app.processEvents()
                t.join(0.02)
            if 'error' in box:
                failed.append((number, f'{step.tool}: {box["error"]}'))
                if stop_on_error:
                    break
            else:
                done += 1
        window._save_state_to_file(str(out_path or pyf_path))
    finally:
        launch.stop_live_session(window)
        window.close()
        if saved_runtime is None:
            os.environ.pop('PYFIGURES_LIVE_RUNTIME', None)
        else:
            os.environ['PYFIGURES_LIVE_RUNTIME'] = saved_runtime
    return {'done': done, 'total': len(steps), 'failed': failed, 'output': str(out_path or pyf_path)}


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog='python -m pyfigures.assistant.chat_replay',
                                description='Chat logs as replayable steps and procedures.')
    sub = p.add_subparsers(dest='cmd', required=True)
    ls = sub.add_parser('steps', help='list the steps of a chat log (or debug zip)')
    ls.add_argument('chat')
    ls.add_argument('--all', action='store_true', help='also the reads and failed calls')
    sv = sub.add_parser('save', help='save the steps that changed the figure as a procedure')
    sv.add_argument('chat')
    sv.add_argument('procedure')
    rn = sub.add_parser('run', help='run a procedure on a .pyf file')
    rn.add_argument('procedure')
    rn.add_argument('figure')
    rn.add_argument('--out')
    rn.add_argument('--keep-going', action='store_true', help='go on after a failed step')
    a = p.parse_args(argv)
    if a.cmd == 'steps':
        steps = load_steps(a.chat)
        for k, s in enumerate(steps if a.all else procedure_steps(steps), 1):
            flag = ' (read)' if s.reads_only else ' (failed)' if s.recorded_error else ' (undone)' if s.turn_undone else ''
            print(f'{k:3d}. [{s.turn}] {s.describe()[:150]}{flag}')
        return 0
    if a.cmd == 'save':
        print(save_procedure(procedure_steps(load_steps(a.chat)), a.procedure, source=a.chat))
        return 0
    result = run_procedure_on_file(a.procedure, a.figure, a.out, stop_on_error=not a.keep_going)
    print(json.dumps(result, indent=2))
    return 0 if not result['failed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
