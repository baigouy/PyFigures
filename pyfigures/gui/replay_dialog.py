"""Tools > Replay a chat…: the operations a chat model ran, one by one, on the open figure
(pyfigures.assistant.chat_replay). For debugging the chat's operations: what each did
then and does now, with its arguments editable before running it again. Save as
procedure… keeps the ones that changed the figure, to run on other figures
(Tools > Run a procedure…)."""
from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
                            QHeaderView, QLabel, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
                            QTableWidget, QTableWidgetItem, QVBoxLayout)

from pyfigures.assistant import chat_replay as R

_GREY, _RED, _GREEN = QColor(140, 140, 140), QColor(200, 40, 40), QColor(30, 140, 60)


def run_in_thread(fn):
    """fn() on a worker thread while Qt keeps running (the live session answers on the
    Qt thread). Its result, or raises its error."""
    box = {}

    def work():
        try:
            box['out'] = fn()
        except Exception as e:
            box['error'] = e
    t = threading.Thread(target=work, daemon=True)
    t.start()
    app = QApplication.instance()
    while t.is_alive():
        app.processEvents()
        t.join(0.02)
    if 'error' in box:
        raise box['error']
    return box.get('out')


def ensure_shared(window):
    """The window's figure shared with the live session (the chat does it too)."""
    from pyfigures.assistant import launch
    if not launch.is_sharing(window):
        launch.start_live_session(window)


def document_of(window):
    path = getattr(window, 'current_file', None)
    if not path:
        return None, None
    p = Path(str(path))
    return str(p.parent), p.stem


class ReplayDialog(QDialog):
    COLUMNS = ('#', 'Request', 'Operation', 'Then', 'Now')

    def __init__(self, window, source=None):
        super().__init__(window)
        self.window = window
        self.setWindowTitle('Replay a chat')
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.resize(1000, 640)
        self.all_steps, self.steps, self.source = [], [], None
        self.now = {}                 # id(step) -> (ok, text)
        self.snapshot = None
        self.runner = None

        top = QHBoxLayout()
        self.chats = QComboBox(self)
        for p in R.recent_chats():
            self.chats.addItem(p.name, str(p))
        self.chats.activated.connect(lambda _i: self.load(self.chats.currentData()))
        top.addWidget(QLabel('Chat:', self))
        top.addWidget(self.chats, 1)
        browse = QPushButton('Open a log, debug zip or procedure…', self)
        browse.clicked.connect(self.browse)
        top.addWidget(browse)
        self.show_reads = QCheckBox('Show reads and failed calls', self)
        self.show_reads.toggled.connect(lambda _c: self.fill())
        top.addWidget(self.show_reads)

        self.table = QTableWidget(0, len(self.COLUMNS), self)
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.show_step)

        detail = QFrame(self)
        d = QVBoxLayout(detail)
        d.setContentsMargins(0, 0, 0, 0)
        d.addWidget(QLabel('Arguments (edit them, then Run this step):', detail))
        self.arguments = QPlainTextEdit(detail)
        d.addWidget(self.arguments, 1)
        d.addWidget(QLabel('Result in the chat:', detail))
        self.then = QPlainTextEdit(detail)
        self.then.setReadOnly(True)
        d.addWidget(self.then, 1)
        d.addWidget(QLabel('Result now:', detail))
        self.result = QPlainTextEdit(detail)
        self.result.setReadOnly(True)
        d.addWidget(self.result, 1)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self.table)
        split.addWidget(detail)
        split.setSizes([620, 380])

        buttons = QHBoxLayout()
        for text, slot, tip in (
                ('Run this step ▶', self.run_selected, 'Run the selected step (with the arguments as edited) and select the next'),
                ('Run up to here', self.run_to_selected, 'Run every step not run yet, up to the selected one'),
                ('Run all', self.run_all, 'Run every step not run yet'),
                ('Reset the figure', self.reset, 'Put the figure back as it was before the first step run here'),
                ('Save as procedure…', self.save_procedure,
                 'Save the steps that changed the figure, to run them on other figures (Tools > Run a procedure…)')):
            b = QPushButton(text, self)
            b.setToolTip(tip)
            b.clicked.connect(lambda _c=False, s=slot: s())
            buttons.addWidget(b)
        self.status = QLabel('', self)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(split, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        start = source or (self.chats.itemData(0) if self.chats.count() else None)
        if start:
            self.load(start)

    # -- loading -------------------------------------------------------------------------
    def add_sources(self, paths):
        """List *paths* (procedures of a dropped zip) first in the chat box."""
        for k, p in enumerate(paths):
            self.chats.insertItem(k, Path(p).name, str(p))
        if paths:
            self.chats.setCurrentIndex(0)

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Chat log, debug zip or procedure', str(R.chats_folder()),
                                              'Chats and procedures (*.jsonl *.zip *.json);;All files (*)')
        if path:
            self.load(path)

    def load(self, path):
        path = str(path)
        try:
            if path.lower().endswith('.json'):
                self.all_steps = R.load_procedure(path)
            else:
                self.all_steps = R.load_steps(path)
        except Exception as e:
            QMessageBox.warning(self, 'Replay a chat', f'Cannot read {Path(path).name}: {e}')
            return False
        self.source, self.now = path, {}
        self.setWindowTitle('Replay: ' + Path(path).name)
        self.fill()
        return True

    def fill(self):
        keep_all = self.show_reads.isChecked() or str(self.source or '').lower().endswith('.json')
        self.steps = self.all_steps if keep_all else R.procedure_steps(self.all_steps)
        self.table.setRowCount(len(self.steps))
        for row, step in enumerate(self.steps):
            note = ' (read)' if step.reads_only else ' (undone later)' if step.turn_undone else ''
            cells = (str(row + 1), step.request, step.describe() + note,
                     'failed' if step.recorded_error else 'ok', '')
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if step.reads_only or step.turn_undone:
                    item.setForeground(_GREY)
                if col == 3:
                    item.setForeground(_RED if step.recorded_error else _GREEN)
                self.table.setItem(row, col, item)
            self._mark(row)
        self.status.setText(f'{len(self.steps)} step(s) of {len(self.all_steps)} recorded; '
                            'run them one by one or all at once. Edits made by hand during the chat '
                            'were not recorded.')
        if self.steps:
            self.table.selectRow(0)

    def _mark(self, row):
        state = self.now.get(id(self.steps[row]))
        item = self.table.item(row, 4)
        if state is None:
            item.setText('')
            return
        ok, text = state
        item.setText('ok' if ok else 'failed')
        item.setForeground(_GREEN if ok else _RED)
        item.setToolTip(text[:500])

    def show_step(self):
        row = self.current_row()
        if row is None:
            return
        step = self.steps[row]
        shown = dict(step.arguments)
        if step.batch:
            shown = {'arguments': shown, 'batch': step.batch}
        self.arguments.setPlainText(json.dumps(shown, indent=2, ensure_ascii=False))
        self.then.setPlainText(step.recorded_result or ('(not recorded)' if self.source and not
                                                         self.source.endswith('.json') else ''))
        state = self.now.get(id(step))
        self.result.setPlainText(state[1] if state else '')

    def current_row(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return rows[0].row() if rows else None

    # -- running ------------------------------------------------------------------------
    def _ready(self):
        if self.runner is None:
            ensure_shared(self.window)
            self.runner = R.Runner(document_of(self.window))
        if self.snapshot is None:
            self.snapshot = str(Path(tempfile.mkdtemp(prefix='pyfigures_replay_')) / 'before.pyf')
            self.window._save_state_to_file(self.snapshot)

    def _edited(self, step):
        """The step with the arguments as edited in the box (bad JSON: unchanged, said)."""
        try:
            value = json.loads(self.arguments.toPlainText() or '{}')
        except ValueError as e:
            raise ValueError(f'the arguments are not valid JSON: {e}')
        if step.batch and isinstance(value, dict) and 'batch' in value:
            step.arguments, step.batch = dict(value.get('arguments') or {}), value['batch']
        elif isinstance(value, dict):
            step.arguments = value
        return step

    def run_step(self, row, edited=False):
        """Run the step at *row* on the open figure. True when it worked."""
        step = self.steps[row]
        try:
            self._ready()
            if edited:
                self._edited(step)
            out = run_in_thread(lambda: self.runner.run(step))
            self.now[id(step)] = (True, R.result_text(out))
        except Exception as e:
            self.now[id(step)] = (False, f'{type(e).__name__}: {e}')
        self._mark(row)
        if self.current_row() == row:
            self.show_step()
        return self.now[id(step)][0]

    def run_selected(self):
        row = self.current_row()
        if row is None:
            return
        self.run_step(row, edited=True)
        if row + 1 < len(self.steps):
            self.table.selectRow(row + 1)

    def run_to_selected(self):
        row = self.current_row()
        self._run_range(0 if row is None else row)

    def run_all(self):
        self._run_range(len(self.steps) - 1)

    def _run_range(self, last):
        done = failed = 0
        for row in range(last + 1):
            if id(self.steps[row]) in self.now:
                continue
            if self.run_step(row):
                done += 1
            else:
                failed += 1
        self.status.setText(f'{done} step(s) run' + (f', {failed} failed (see Now)' if failed else '') + '.')
        if last + 1 < len(self.steps):
            self.table.selectRow(last + 1)

    def reset(self):
        if self.snapshot is None:
            self.status.setText('Nothing was run yet.')
            return
        self.window.reload_state(self.snapshot, append=False)
        self.now = {}
        for row in range(len(self.steps)):
            self._mark(row)
        self.show_step()
        self.status.setText('The figure is back as it was before the first step run here.')

    def save_procedure(self, path=None):
        steps = R.procedure_steps(self.all_steps) if not str(self.source).endswith('.json') else self.all_steps
        if not steps:
            QMessageBox.information(self, 'Save as procedure', 'This chat changed nothing in the figure.')
            return None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, 'Save the steps as a procedure', '',
                                                  'PyFigures procedure (*.json)')
            if not path:
                return None
        R.save_procedure(steps, path, source=None if str(self.source).endswith('.json') else self.source)
        self.status.setText(f'{len(steps)} step(s) saved to {path}.')
        return path


def run_procedure_on_window(window, path, stop_on_error=True):
    """Tools > Run a procedure…: every step on the open figure, at once. Returns
    (done, total, [(step number, error)])."""
    steps = R.load_procedure(path)
    ensure_shared(window)
    runner = R.Runner(document_of(window))
    done, failed = 0, []
    for number, step in enumerate(steps, 1):
        try:
            run_in_thread(lambda s=step: runner.run(s))
            done += 1
        except Exception as e:
            failed.append((number, f'{step.tool}: {e}'))
            if stop_on_error:
                break
    return done, len(steps), failed
