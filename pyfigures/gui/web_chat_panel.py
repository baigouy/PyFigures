"""Tools → Chat in a web page…: an online chat page (Mistral Le Chat / Emmy,
ChatGPT, Claude, Gemini or any address) docked beside the figure.

The user logs in on the page as in a browser (the login is kept), clicks
"Start" to put PyFigures' instructions and the figure into the chat box,
adds a request and presses Send. The model's answers end with a
PYFIGURES-CALLS block (pyfigures.assistant.web_chat); the panel finds it in
the page text, shows it with Apply / Dismiss, runs it on the figure and puts
the results into the chat box for the next Send. Nothing is ever sent by
PyFigures: the user presses the page's Send button every time.

Without Qt WebEngine (PyQt6-WebEngine not installed, or imported too late)
the same panel works through the clipboard: the chat opens in the usual
browser, prompts and results are copied, replies are pasted back.
"""
from __future__ import annotations

import json
import os

from qtpy.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from qtpy.QtGui import QDesktopServices, QImage
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDockWidget, QFrame, QHBoxLayout,
                            QLabel, QPlainTextEdit, QPushButton, QVBoxLayout)

from pyfigures.assistant import web_chat

SCAN_MS = 1500


def web_engine():
    """(QWebEngineView, QWebEnginePage, QWebEngineProfile) or the reason
    they cannot be used."""
    try:
        from qtpy.QtWebEngineWidgets import QWebEngineView
        from qtpy.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    except Exception as exc:      # missing, or imported after the QApplication without shared contexts
        try:
            from qtpy.QtCore import PYQT_VERSION_STR
            major_minor = '.'.join(PYQT_VERSION_STR.split('.')[:2])
            hint = f'pip install "PyQt6-WebEngine=={major_minor}.*"'
        except Exception:
            hint = 'pip install PyQt6-WebEngine'
        return f'{type(exc).__name__}: {exc}. To show the chat inside PyFigures: {hint}, then restart PyFigures.'
    return QWebEngineView, QWebEnginePage, QWebEngineProfile


# Writes into the chat box of any site: the focused box, else the lowest
# visible textarea / contenteditable (ChatGPT, Claude, Le Chat use
# ProseMirror: execCommand('insertText') is what their editors listen to).
_INSERT_JS = r"""
(function(text){
  function visible(e){var r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';}
  function box(e){return e&&(e.tagName==='TEXTAREA'||e.isContentEditable)&&visible(e);}
  var el=document.activeElement;
  if(!box(el)){
    var c=Array.prototype.slice.call(document.querySelectorAll('textarea,[contenteditable="true"],[contenteditable=""],[contenteditable="plaintext-only"]')).filter(visible);
    c.sort(function(a,b){return b.getBoundingClientRect().bottom-a.getBoundingClientRect().bottom;});
    el=c[0];
  }
  if(!el) return 'none';
  el.focus();
  if(el.tagName==='TEXTAREA'){
    var setter=Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
    setter.call(el,(el.value?el.value+'\n\n':'')+text);
    el.dispatchEvent(new Event('input',{bubbles:true}));
    return 'textarea';
  }
  var sel=window.getSelection();sel.selectAllChildren(el);sel.collapseToEnd();
  if(el.textContent.trim()) document.execCommand('insertText',false,'\n\n');
  return document.execCommand('insertText',false,text)?'editable':'failed';
})(%s)
"""

_TEXT_JS = "document.body ? document.body.innerText : ''"


class _Relay(QObject):
    """Hands a worker thread's result to the Qt thread."""
    arrived = Signal(object, object)


class WebChatPanel(QFrame):
    """The panel inside the dock (QFrame: a bare QWidget container crashes
    PySide2)."""

    def __init__(self, window, parent=None, use_web=True):
        super().__init__(parent)
        self.window = window
        self.runner = web_chat.ToolRunner()
        self.seen = set()            # blocks already shown, run or dismissed
        self.pending = []            # blocks waiting for Apply / Dismiss
        self.busy = False
        self.last_image = None       # PNG bytes of the last preview
        self.baseline_next_scan = True
        self.relay = _Relay(self)
        self.relay.arrived.connect(lambda callback, value: callback(value))
        self.settings = QSettings('PyFigures', 'web_chat')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        top = QHBoxLayout()
        self.address = QComboBox(self)
        self.address.setEditable(True)
        self.address.setToolTip('The chat page: a preset, or type the address of yours (e.g. Emmy) and press Enter. '
                                'Addresses you use are remembered.')
        for name, url in web_chat.PRESETS:
            self.address.addItem(f'{name} — {url}', url)
        for url in self._remembered():
            if self.address.findData(url) < 0:
                self.address.addItem(url, url)
        last = self.settings.value('url', web_chat.PRESETS[0][1])
        index = self.address.findData(last)
        if index < 0:
            self.address.addItem(last, last)
            index = self.address.findData(last)
        self.address.setCurrentIndex(index)
        self.address.activated.connect(lambda _i: self.go())
        self.address.lineEdit().returnPressed.connect(self.go)
        top.addWidget(self.address, 1)
        external = QPushButton('Open in my browser', self)
        external.setToolTip('Open the chat page in your usual browser (then use the clipboard buttons)')
        external.clicked.connect(lambda _c=False: QDesktopServices.openUrl(QUrl(self.url())))
        top.addWidget(external)
        layout.addLayout(top)

        engine = web_engine() if use_web else 'Clipboard mode chosen.'
        self.view = None
        if isinstance(engine, tuple):
            self._make_view(*engine)
            layout.addWidget(self.view, 1)
        else:
            note = QLabel('The chat cannot be shown inside PyFigures here (' + engine + ')\n\n'
                          'Clipboard mode: open the chat in your browser, click "Start" and paste '
                          '(Ctrl+V) into the chat; copy the model\'s answer and click "Read a copied reply".', self)
            note.setWordWrap(True)
            note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(note, 1)

        buttons = QHBoxLayout()
        self.start_button = QPushButton('Start: give the chat the figure', self)
        self.start_button.setToolTip('Put PyFigures\' instructions, its operations and the figure as it is now into '
                                     'the chat box. Add your request after it and press Send on the page.')
        self.start_button.clicked.connect(lambda _c=False: self.start())
        buttons.addWidget(self.start_button)
        paste = QPushButton('Read a copied reply', self)
        paste.setToolTip('Look for PyFigures operations in an answer copied to the clipboard (clipboard mode)')
        paste.clicked.connect(lambda _c=False: self.read_text(QApplication.clipboard().text(), baseline=False))
        buttons.addWidget(paste)
        layout.addLayout(buttons)

        self.auto_lookups = QCheckBox('Run look-ups without asking (they change nothing)', self)
        self.auto_lookups.setChecked(self.settings.value('auto_lookups', True, type=bool))
        self.auto_lookups.toggled.connect(lambda on: self.settings.setValue('auto_lookups', on))
        layout.addWidget(self.auto_lookups)

        self.request_box = QPlainTextEdit(self)
        self.request_box.setReadOnly(True)
        self.request_box.setPlaceholderText('Operations the model asks for appear here.')
        self.request_box.setMaximumHeight(110)
        layout.addWidget(self.request_box)
        actions = QHBoxLayout()
        self.apply_button = QPushButton('Apply', self)
        self.apply_button.setToolTip('Run these operations on the figure (one undo step each) and put the results '
                                     'into the chat box')
        self.apply_button.clicked.connect(lambda _c=False: self.apply())
        self.dismiss_button = QPushButton('Dismiss', self)
        self.dismiss_button.setToolTip('Do not run them; tell the chat so in its box')
        self.dismiss_button.clicked.connect(lambda _c=False: self.dismiss())
        self.preview_button = QPushButton('Copy the last preview', self)
        self.preview_button.setToolTip('Copy the last figure preview to the clipboard, to paste it into the chat')
        self.preview_button.clicked.connect(lambda _c=False: self.copy_preview())
        for b in (self.apply_button, self.dismiss_button, self.preview_button):
            actions.addWidget(b)
        layout.addLayout(actions)
        self.status = QLabel('', self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self._refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scan)
        if self.view is not None:
            self.timer.start(SCAN_MS)
            self.go()

    # ---- the page ---------------------------------------------------------------
    def _make_view(self, QWebEngineView, QWebEnginePage, QWebEngineProfile):
        # a named profile keeps cookies on disk: the login survives restarts
        self.profile = QWebEngineProfile('pyfigures-web-chat', self)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.popups = []
        panel = self

        class Page(QWebEnginePage):
            def createWindow(self, _type):
                # sign-in pop-ups open in a window of their own, same profile
                view = QWebEngineView()
                page = Page(panel.profile, view)
                view.setPage(page)
                view.resize(520, 680)
                view.setWindowTitle('Sign in')
                page.windowCloseRequested.connect(view.close)
                panel.popups = [v for v in panel.popups if v.isVisible()] + [view]
                view.show()
                return page

        self.view = QWebEngineView(self)
        self.view.setPage(Page(self.profile, self.view))
        self.view.loadFinished.connect(lambda _ok: setattr(self, 'baseline_next_scan', True))

    def url(self):
        text = self.address.currentText().strip()
        data = self.address.currentData()
        if data and text.endswith(data):
            return data
        if text and '://' not in text:
            text = 'https://' + text
        return text

    def _remembered(self):
        try:
            return [u for u in json.loads(self.settings.value('urls', '[]')) if isinstance(u, str)]
        except ValueError:
            return []

    def go(self):
        url = self.url()
        if not url:
            return
        self.settings.setValue('url', url)
        urls = [u for u in self._remembered() if u != url]
        if url not in dict(web_chat.PRESETS).values():
            self.settings.setValue('urls', json.dumps([url] + urls[:9]))
        if self.view is not None:
            self.baseline_next_scan = True
            self.view.setUrl(QUrl(url))
        else:
            QDesktopServices.openUrl(QUrl(url))

    def write_to_chat(self, text, what):
        """Put *text* into the chat box (and on the clipboard, in case the
        page's box was not found); the user presses Send."""
        QApplication.clipboard().setText(text)
        if self.view is None:
            self.say(f'{what} copied: paste it into the chat (Ctrl+V) and press Send.')
            return

        def written(how):
            if how in ('textarea', 'editable'):
                self.say(f'{what} is in the chat box: press Send on the page.')
            else:
                self.say(f'{what} could not be typed into this page: click in its message box and paste (Ctrl+V); '
                         'it is on the clipboard.')
        self.view.page().runJavaScript(_INSERT_JS % json.dumps(text), 0, written)

    # ---- reading answers --------------------------------------------------------
    def scan(self):
        if self.view is None or not self.isVisible():
            return
        baseline = self.baseline_next_scan
        self.baseline_next_scan = False
        self.view.page().runJavaScript(_TEXT_JS, 0, lambda text: self.read_text(text, baseline))

    def read_text(self, text, baseline=False):
        """New PYFIGURES-CALLS blocks in *text*. With *baseline*, the ones
        already on a page just opened are only remembered (an old
        conversation is not replayed)."""
        if not isinstance(text, str):
            return
        found = 0
        for block in web_chat.parse_blocks(text):
            if block.key in self.seen:
                continue
            self.seen.add(block.key)
            if baseline:
                continue
            found += 1
            self.pending.append(block)
        if found:
            self._next()
        elif not baseline and self.view is None:
            self.say('No PyFigures operations in the copied text.')

    def _next(self):
        """Look-ups run by themselves (when allowed); anything else waits
        for Apply."""
        if self.busy or not self.pending:
            self._refresh()
            return
        block = self.pending[0]
        if block.error is None and block.read_only and self.auto_lookups.isChecked():
            self.apply()
            return
        self._refresh()
        if block.error:
            self.say('The model\'s last request could not be read. Dismiss sends it a correction.')
        else:
            self.say('The model asks for the operations above: Apply or Dismiss.')

    # ---- acting -----------------------------------------------------------------
    def _run(self, function, done, *args):
        self.busy = True
        self._refresh()
        web_chat.run_async(function, lambda value: self.relay.arrived.emit(done, value), *args)

    def start(self):
        if self.busy:
            return
        self.say('Reading the figure…')
        if self.view is not None:
            self.baseline_next_scan = True

        def done(value):
            self.busy = False
            if isinstance(value, Exception):
                self.say(f'Could not read the figure: {value}')
            else:
                self.write_to_chat(value, 'The instructions and the figure')
            self._next()
        self._run(self.runner.first_prompt, done)

    def apply(self):
        if self.busy or not self.pending:
            return
        block = self.pending[0]
        if block.error:
            self.dismiss()
            return
        self.say('Running: ' + '; '.join(web_chat.describe_call(c).split(' ', 1)[0] for c in block.calls) + '…')

        def done(value):
            self.busy = False
            self.pending.pop(0)
            if isinstance(value, Exception):
                outcomes, images = [(block.calls[0], False, str(value))], []
            else:
                outcomes, images = value
            if images:
                self.last_image = images[-1]
            self.write_to_chat(web_chat.results_message(outcomes), 'The results')
            self._next()
        self._run(self.runner.run_block, done, block)

    def dismiss(self):
        if self.busy or not self.pending:
            return
        block = self.pending.pop(0)
        if block.error:
            text = (f'{web_chat.RESULTS}: your last block could not be read ({block.error}). Write it again: the '
                    f'marker lines alone on their lines, a JSON list of {{"tool": …, "arguments": {{…}}}} between them.')
        else:
            text = f'{web_chat.RESULTS}: I did not run these operations. Ask me before trying something else.'
        self.write_to_chat(text, 'The message')
        self._next()

    def copy_preview(self):
        if self.last_image:
            QApplication.clipboard().setImage(QImage.fromData(self.last_image, 'PNG'))
            self.say('The preview is on the clipboard: paste it into the chat (Ctrl+V) if the page takes images.')

    def say(self, text):
        self.status.setText(text)

    def _refresh(self):
        block = self.pending[0] if self.pending else None
        self.request_box.setPlainText(block.describe() if block else '')
        if len(self.pending) > 1:
            self.request_box.appendPlainText(f'(+{len(self.pending) - 1} more waiting)')
        self.apply_button.setEnabled(bool(block) and block.error is None and not self.busy)
        self.dismiss_button.setEnabled(bool(block) and not self.busy)
        self.start_button.setEnabled(not self.busy)
        self.preview_button.setEnabled(self.last_image is not None)


def attach(window, use_web=True):
    """Dock the web chat on *window* (already sharing its figure); the
    existing dock is shown again."""
    dock = getattr(window, 'web_chat_dock', None)
    if dock is not None:
        dock.show()
        dock.raise_()
        return dock
    dock = QDockWidget('Chat in a web page', window)
    dock.setObjectName('web_chat_dock')
    dock.setWidget(WebChatPanel(window, dock, use_web=use_web))
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    window.web_chat_dock = dock
    dock.show()
    return dock
