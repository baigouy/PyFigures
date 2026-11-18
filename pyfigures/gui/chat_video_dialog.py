"""Tools > Make a demo video from a chat… (also in the chat sidebar's Procedures menu): pick
a chat log, its first and last request to film, the pacing and the format; the video is
made off-screen by ``python -m pyfigures.assistant.chat_video`` in a process of its own
(pyfigures.assistant.chat_video), without calling the model."""
from __future__ import annotations

import json
import os
from pathlib import Path

from qtpy.QtCore import QProcess, QProcessEnvironment, QUrl
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
                            QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout)

from pyfigures.assistant import chat_video as V

FORMATS = [('MP4 and GIF', ('mp4', 'gif')), ('MP4', ('mp4',)), ('GIF', ('gif',))]


def videos_folder() -> Path:
    home = Path.home()
    return home / 'Videos' if (home / 'Videos').is_dir() else home


class ChatVideoDialog(QDialog):
    def __init__(self, parent=None, chat=None):
        super().__init__(parent)
        self.setWindowTitle('Make a demo video from a chat')
        self.requests, self.process, self.outputs, self._output = [], None, [], ''
        root = QVBoxLayout(self)
        intro = QLabel('Films part of a chat that already happened, off-screen: each request typed in the chat, '
                       'the edits the model made then shown one by one on the figure, its answers as they '
                       'appeared. The model is not asked again. The images the chat used must still exist; '
                       'edits made by hand between requests are not shown.')
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        row = QHBoxLayout()
        self.chat = QLineEdit()
        self.chat.editingFinished.connect(lambda: self.load(self.chat.text()))
        choose = QPushButton('Choose…')
        choose.clicked.connect(self.choose_chat)
        row.addWidget(self.chat, 1)
        row.addWidget(choose)
        form.addRow('Chat log', row)
        self.first, self.last = QComboBox(), QComboBox()
        for box in (self.first, self.last):
            box.setMinimumContentsLength(40)
            box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            box.currentIndexChanged.connect(self.range_changed)
        form.addRow('First request', self.first)
        form.addRow('Last request', self.last)
        self.start_note = QLabel()
        self.start_note.setWordWrap(True)
        form.addRow('Starts from', self.start_note)
        self.step = QDoubleSpinBox()
        self.step.setRange(0.2, 5.0)
        self.step.setSingleStep(0.1)
        self.step.setValue(1.0)
        self.step.setSuffix(' s per step')
        form.addRow('Pacing', self.step)
        self.final = QDoubleSpinBox()
        self.final.setRange(0.0, 15.0)
        self.final.setValue(3.0)
        self.final.setSuffix(' s')
        form.addRow('Pause on the result', self.final)
        self.max_seconds = QDoubleSpinBox()
        self.max_seconds.setRange(0.0, 600.0)
        self.max_seconds.setDecimals(0)
        self.max_seconds.setValue(60.0)
        self.max_seconds.setSuffix(' s')
        self.max_seconds.setSpecialValueText('no limit')
        self.max_seconds.setToolTip('A longer film has its steps and answers shortened alike '
                                    '(the typing and the final pause are kept)')
        form.addRow('At most', self.max_seconds)
        self.intermediate = QCheckBox("Show the model's intermediate messages (not only its last answer)")
        self.intermediate.setChecked(True)
        form.addRow('', self.intermediate)
        self.format = QComboBox()
        for label, _ in FORMATS:
            self.format.addItem(label)
        form.addRow('Format', self.format)
        row = QHBoxLayout()
        self.out = QLineEdit()
        browse = QPushButton('Browse…')
        browse.clicked.connect(self.choose_output)
        row.addWidget(self.out, 1)
        row.addWidget(browse)
        form.addRow('Save as', row)
        root.addLayout(form)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setPlaceholderText('Progress')
        root.addWidget(self.log, 1)
        buttons = QHBoxLayout()
        self.open_folder = QPushButton('Show the video')
        self.open_folder.setEnabled(False)
        self.open_folder.clicked.connect(self.show_video)
        self.make = QPushButton('Make the video')
        self.make.setDefault(True)
        self.make.clicked.connect(self.start)
        close = QPushButton('Close')
        close.clicked.connect(self.close)
        buttons.addWidget(self.open_folder)
        buttons.addStretch(1)
        buttons.addWidget(self.make)
        buttons.addWidget(close)
        root.addLayout(buttons)
        self.resize(720, 560)
        if chat is None:
            from pyfigures.assistant.chat_replay import recent_chats
            recent = recent_chats(1)
            chat = recent[0] if recent else None
        if chat:
            self.load(str(chat))

    # the chat and its range -----------------------------------------------------------
    def choose_chat(self):
        from pyfigures.assistant.chat_replay import chats_folder
        start = self.chat.text() or str(chats_folder())
        path, _ = QFileDialog.getOpenFileName(self, 'Chat to film', start, 'Chat logs (*.jsonl *.zip)')
        if path:
            self.load(path)

    def load(self, path):
        self.chat.setText(str(path))
        self.requests = []
        for box in (self.first, self.last):
            box.blockSignals(True)
            box.clear()
        try:
            self.requests = V.requests_of(path) if path and Path(path).is_file() else []
        except Exception as exc:
            self.start_note.setText(f'<span style="color:#b3261e">Cannot read this chat: {exc}</span>')
        for r in self.requests:
            self.first.addItem(r.label(), r.number)
            self.last.addItem(r.label(), r.number)
        self.first.setCurrentIndex(0)
        self.last.setCurrentIndex(len(self.requests) - 1)
        for box in (self.first, self.last):
            box.blockSignals(False)
        self.range_changed()

    def selection(self):
        return self.first.currentData(), self.last.currentData()

    def range_changed(self, *args):
        first, last = self.selection()
        ok = bool(self.requests) and first is not None and last is not None and first <= last
        note = ''
        if self.requests and first is not None and last is not None and first > last:
            note = '<span style="color:#b3261e">The last request comes before the first one.</span>'
        elif ok:
            try:
                note = 'The figure as it was before request {}: {}.'.format(first, V.start_state(self.requests, first)['note'])
            except ValueError as exc:
                note, ok = f'<span style="color:#b3261e">{exc}</span>', False
        elif not self.requests and not self.start_note.text():
            note = 'Choose a chat log.'
        if note:
            self.start_note.setText(note)
        self.make.setEnabled(ok and self.process is None)
        if ok and self.chat.text():
            self.out.setText(str(videos_folder() / f'{Path(self.chat.text()).stem}_requests_{first}-{last}.mp4'))

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save the video as', self.out.text() or str(videos_folder()),
                                              'Video (*.mp4 *.gif)')
        if path:
            self.out.setText(path)

    def options(self) -> V.Options:
        return V.Options(step_seconds=self.step.value(), final_seconds=self.final.value(),
                         intermediate=self.intermediate.isChecked(), formats=FORMATS[self.format.currentIndex()][1],
                         max_seconds=self.max_seconds.value())

    # making it ------------------------------------------------------------------------
    def command(self):
        first, last = self.selection()
        return V.video_command(self.chat.text(), first, last, self.out.text(), self.options())

    def start(self):
        program, arguments = self.command()
        Path(self.out.text()).parent.mkdir(parents=True, exist_ok=True)
        self.log.clear()
        self.outputs, self._output = [], ''
        self.open_folder.setEnabled(False)
        process = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert('PYTHONIOENCODING', 'utf-8')
        env.insert('QT_QPA_PLATFORM', 'offscreen')
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read)
        process.finished.connect(self._finished)
        self.process = process
        self.make.setEnabled(False)
        self.log.appendPlainText('Filming off-screen…')
        process.start(program, arguments)

    def _read(self):
        text = bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace')
        self._output += text
        for line in text.splitlines():
            if line.startswith('PROGRESS '):
                self.log.appendPlainText(line[len('PROGRESS '):])

    def _finished(self, code, _status=None):
        self._read()
        report = None
        for line in self._output.splitlines():
            if line.startswith('REPORT '):
                try:
                    report = json.loads(line[len('REPORT '):])
                except ValueError:
                    report = None
        self.process = None
        if code == 0 and report:
            self.outputs = report.get('outputs') or []
            self.log.appendPlainText(f"Done: {report.get('seconds')} s of video"
                                     + (f" (shortened from {report.get('filmed_seconds')} s)."
                                        if report.get('shortened') else '.'))
            for path in self.outputs:
                self.log.appendPlainText(path)
            if report.get('failed_now'):
                self.log.appendPlainText(f"{len(report['failed_now'])} operation(s) failed now (shown as not done):")
                for f in report['failed_now'][:5]:
                    self.log.appendPlainText(f"  request: {f['request'][:60]} · {f['error'][:150]}")
            if report.get('skipped'):
                self.log.appendPlainText(f"Requests undone in the chat, not filmed: {report['skipped']}")
            self.open_folder.setEnabled(bool(self.outputs))
        else:
            tail = '\n'.join(line for line in self._output.splitlines()[-15:] if not line.startswith('PROGRESS '))
            self.log.appendPlainText('The video could not be made:\n' + tail)
        self.range_changed()

    def show_video(self):
        if self.outputs:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self.outputs[0])))

    def closeEvent(self, event):
        if self.process is not None:
            self.process.kill()
            self.process.waitForFinished(3000)
            self.process = None
        super().closeEvent(event)


def open_dialog(parent=None, chat=None):
    """The dialog, shown (non-modal); returned."""
    dialog = ChatVideoDialog(parent, chat)
    dialog.show()
    return dialog
