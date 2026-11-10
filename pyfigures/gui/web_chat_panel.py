"""Tools → Chat in a web page…: an online chat page (Mistral Le Chat / Emmy,
ChatGPT, Claude, Gemini or any address) docked beside the figure.

The user logs in on the page as in a browser (the login is kept), clicks
"Start" to put PyFigures' instructions and the figure into the chat box,
adds a request and presses Send. The model's answers end with a
PYFIGURES-CALLS block (pyfigures.assistant.web_chat); the panel finds it in
the page text, shows it with Apply / Dismiss, runs it on the figure and puts
the results into the chat box for the next Send. A request typed in the
panel is sent from there (with the instructions the first time); with
"Automatic" ticked (off by default) every operation is applied and the
results are sent too, by a real Enter key press or the page's send button,
up to MAX_ROUNDS rounds per request.

Without Qt WebEngine (PyQt6-WebEngine not installed, or imported too late)
the same panel works through the clipboard: the chat opens in the usual
browser, prompts and results are copied, replies are pasted back.
"""
from __future__ import annotations

import json
import os
import re
import sys

from qtpy.QtCore import QObject, QSettings, Qt, QTimer, QUrl, Signal
from qtpy.QtGui import QDesktopServices, QImage
from qtpy.QtCore import QEvent
from qtpy.QtGui import QKeyEvent
from qtpy.QtWidgets import (QApplication, QCheckBox, QComboBox, QDockWidget, QFrame, QHBoxLayout,
                            QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from pyfigures.assistant import web_chat

SCAN_MS = 1500
MAX_ROUNDS = 20         # automatic apply-and-send rounds in a row, then it waits for a click
IDLE_SCANS = 4          # page unchanged this many scans (~6 s): the automatic run is over
MAX_UNSETTLED = 8       # scans a new block waits for the page to stop changing (the model still writes)
SEND_TRIES = 4          # looks for the page's send button (off while a picture uploads or an answer is written)
MAX_LOG_BYTES = 1_000_000

# The text is still in the chat box after Enter (a site that sends with a
# button only): click the page's send button. A button named Send (label,
# tooltip, test id) anywhere, else the submit button of the chat box's own
# form; never one named Stop/Cancel; the nearest to the box when several.
_SEND_BUTTON_JS = r"""
(function(start){
  function visible(e){var r=e.getBoundingClientRect();return r.width>0&&r.height>0;}
  var boxes=Array.prototype.slice.call(document.querySelectorAll('textarea,[contenteditable="true"],[contenteditable=""],[contenteditable="plaintext-only"]')).filter(visible);
  var full=boxes.filter(function(b){return (b.value||b.innerText||'').indexOf(start)>=0;});
  if(!full.length) return 'sent';
  var box=full[full.length-1], form=box.closest('form');
  function label(b){return ((b.getAttribute('aria-label')||'')+' '+(b.title||'')+' '+(b.getAttribute('data-testid')||'')).toLowerCase();}
  var all=Array.prototype.slice.call(document.querySelectorAll('button,[role="button"]')).filter(function(b){
    return visible(b)&&!b.disabled&&b.getAttribute('aria-disabled')!=='true'&&!/stop|cancel|annul|arr[eê]t|interr/.test(label(b));});
  var named=all.filter(function(b){return /send|envoy|submit|soumettre/.test(label(b));});
  var mine=form?all.filter(function(b){return b.type==='submit'&&form.contains(b);}):[];
  var buttons=named.length?named:mine;
  if(!buttons.length) return 'no button';
  var r=box.getBoundingClientRect();
  function far(b){var q=b.getBoundingClientRect();return Math.abs(q.left+q.width/2-r.right)+Math.abs(q.top+q.height/2-r.bottom);}
  buttons.sort(function(a,b){return far(a)-far(b);});
  buttons[0].click();
  return 'clicked';
})(%s)
"""

# Forget my login: what the page itself keeps (cookies and the cache go through the profile)
_CLEAR_STORAGE_JS = "try{localStorage.clear();sessionStorage.clear();}catch(e){}; true"


def web_engine():
    """(QWebEngineView, QWebEnginePage, QWebEngineProfile) or the reason
    they cannot be used."""
    try:
        from qtpy.QtWebEngineWidgets import QWebEngineView
        from qtpy.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    except Exception as exc:      # missing, or imported after the QApplication without shared contexts
        command = web_engine_command()
        if command is None:
            return (f'{type(exc).__name__}: {exc}. This app does not contain Qt WebEngine: download the '
                    '"PyFigures Web Chat" app (same page as this one) to show the chat inside PyFigures.')
        older = web_engine_command(older=True)
        return (f'{type(exc).__name__}: {exc}. To show the chat inside PyFigures: {command}, then restart '
                'PyFigures.' + (f' If pip finds no such version (Qt WebEngine comes out after PyQt6): {older}.'
                                if older else ''))
    return QWebEngineView, QWebEnginePage, QWebEngineProfile


def web_engine_command(older=False):
    """The pip command that installs Qt WebEngine for this PyQt6 (with
    *older*: PyQt6 and its WebEngine one version back, for a PyQt6 whose
    WebEngine is not out yet). None in a standalone app: nothing can be
    installed into it."""
    if getattr(sys, 'frozen', False):
        return None
    try:
        from qtpy.QtCore import PYQT_VERSION_STR
        major, minor = PYQT_VERSION_STR.split('.')[:2]
    except Exception:
        return None if older else 'pip install PyQt6-WebEngine'
    if older:
        if int(minor) < 1:
            return None
        return f'pip install "PyQt6=={major}.{int(minor) - 1}.*" "PyQt6-WebEngine=={major}.{int(minor) - 1}.*"'
    return f'pip install "PyQt6-WebEngine=={major}.{minor}.*"'


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

WARNING = ('<b>Experimental, not recommended: a last resort.</b> Prefer the chat sidebar (Tools → Chat sidebar, '
           'with an API key or a local model): it works far better. Use this only if really nothing else is '
           'possible, and first make sure it respects the <b>terms of service</b> '
           'of the chat site and your institution\'s rules: PyFigures types into the page and, with Automatic, '
           'sends messages for you.')

# presets taken out of the list: a saved choice of one is not brought back
_DROPPED_PRESETS = frozenset({'https://chat.mistral.ai/login?return_to=%2Fcode'})

# The page has a chat box (not a sign-in page: those use <input>s)
_HAS_BOX_JS = r"""
(function(){
  function visible(e){var r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden';}
  return Array.prototype.slice.call(document.querySelectorAll('textarea,[contenteditable="true"],[contenteditable=""],[contenteditable="plaintext-only"]')).some(visible);
})()
"""


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
        self.seen = {}               # block text -> how many times the page showed it
        self.pending = []            # blocks waiting for Apply / Dismiss
        self.busy = False
        self.last_image = None       # PNG bytes of the last preview
        self.baseline_next_scan = True
        self.started = False         # the page's conversation has the instructions
        self.rounds_left = 0         # automatic rounds left before a pause (refilled when the chat is idle)
        self.last_text = None        # the page text at the last scan, and since when it is unchanged
        self.unchanged_scans = 0
        self.stopped = False         # Stop clicked: no automatic run until the user resumes it
        self.unsettled_scans = 0     # scans a new block has waited for the page to stop changing
        self.signature_seen = False  # the page showed the instructions of this conversation
        self.signature_missing = 0   # …and for how many scans it no longer does
        self.relay = _Relay(self)
        self.relay.arrived.connect(lambda callback, value: callback(value))
        self.settings = QSettings('PyFigures', 'web_chat')

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.warning = QLabel(WARNING, self)
        self.warning.setWordWrap(True)
        self.warning.setTextFormat(Qt.TextFormat.RichText)
        self.warning.setStyleSheet('QLabel { background: #fff3cd; color: #664d03; border: 1px solid #e0b100; '
                                   'border-radius: 3px; padding: 4px; }')
        layout.addWidget(self.warning)
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
        if last in _DROPPED_PRESETS:
            last = web_chat.PRESETS[0][1]
        index = self.address.findData(last)
        if index < 0:
            self.address.addItem(last, last)
            index = self.address.findData(last)
        self.address.setCurrentIndex(index)
        self.address.activated.connect(lambda _i: self.go())
        self.address.lineEdit().returnPressed.connect(self.go)
        top.addWidget(self.address, 1)
        layout.addLayout(top)

        engine = web_engine() if use_web else 'Clipboard mode chosen.'
        self.view = None
        if isinstance(engine, tuple):
            self._make_view(*engine)
            layout.addWidget(self.view, 1)
            for label, tip, action in (('←', 'Back to the previous page', self.view.back),
                                       ('⟳', 'Load the page again', self.view.reload)):
                button = QPushButton(label, self)
                button.setToolTip(tip)
                button.setMaximumWidth(32)
                button.clicked.connect(lambda _c=False, action=action: action())
                top.addWidget(button)
        else:
            note = QLabel('The chat cannot be shown inside PyFigures here (' + engine + ')\n\n'
                          'Clipboard mode: choose the chat page above (it opens in your browser), click "Start" and paste '
                          '(Ctrl+V) into the chat; copy the model\'s answer and click "Read a copied reply".', self)
            note.setWordWrap(True)
            note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(note, 1)
            command = web_engine_command() if use_web else None
            if command:
                copy = QPushButton('Copy the install command', self)
                copy.setToolTip(command)
                copy.clicked.connect(lambda _c=False: (QApplication.clipboard().setText(command),
                                                       copy.setText('Copied')))
                layout.addWidget(copy)
        self.new_button = QPushButton('New conversation', self)
        self.new_button.setToolTip('Open the chat page again for a fresh conversation: the next request gives it '
                                   'the instructions and the figure again')
        self.new_button.clicked.connect(lambda _c=False: self.go())
        top.addWidget(self.new_button)
        self.forget_button = QPushButton('Forget my login…', self)
        self.forget_button.setToolTip('Delete the cookies and cached pages PyFigures keeps for the chat sites: '
                                      'you will have to sign in again')
        self.forget_button.clicked.connect(lambda _c=False: self.forget_login())
        self.forget_button.setVisible(self.view is not None)
        top.addWidget(self.forget_button)

        buttons = QHBoxLayout()
        self.start_button = QPushButton('Start: give the chat the figure', self)
        self.start_button.setToolTip('Put PyFigures\' instructions, its operations and the figure as it is now into '
                                     'the chat box. Add your request after it and press Send on the page.')
        self.start_button.clicked.connect(lambda _c=False: self.start())
        buttons.addWidget(self.start_button)
        paste = QPushButton('Read a copied reply', self)
        paste.setToolTip('Look for PyFigures operations in an answer copied to the clipboard (clipboard mode)')
        paste.clicked.connect(lambda _c=False: self.read_text(QApplication.clipboard().text(), page=False))
        buttons.addWidget(paste)
        layout.addLayout(buttons)

        ask = QHBoxLayout()
        self.ask_edit = QLineEdit(self)
        self.ask_edit.setPlaceholderText('Your request, e.g. "make channel 2 yellow in a"')
        self.ask_edit.setToolTip('Sent to the chat from here; the first one also gives it the instructions and '
                                 'the figure (no need to click Start)')
        self.ask_edit.returnPressed.connect(self.ask)
        ask.addWidget(self.ask_edit, 1)
        self.ask_button = QPushButton('Send', self)
        self.ask_button.clicked.connect(lambda _c=False: self.ask())
        ask.addWidget(self.ask_button)
        layout.addLayout(ask)

        self.automatic = QCheckBox(f'Automatic: apply every operation and send the results (up to {MAX_ROUNDS} '
                                   'rounds per request)', self)
        self.automatic.setToolTip('PyFigures presses Send on the page for you and applies what the model asks '
                                  'for without asking (Ctrl+Z undoes each change). Stop pauses it.')
        self.automatic.setChecked(self.settings.value('automatic', False, type=bool))
        self.automatic.toggled.connect(self._automatic_toggled)
        if self.automatic.isChecked():
            self.rounds_left = MAX_ROUNDS
        layout.addWidget(self.automatic)
        self.auto_lookups = QCheckBox('Run look-ups without asking (they change nothing)', self)
        self.auto_lookups.setChecked(self.settings.value('auto_lookups', True, type=bool))
        self.auto_lookups.toggled.connect(lambda on: self.settings.setValue('auto_lookups', on))
        layout.addWidget(self.auto_lookups)
        self.attach_previews = QCheckBox('Paste figure previews into the chat with the results', self)
        self.attach_previews.setToolTip('When the model asks for a preview of the figure, the picture is pasted '
                                        'into the chat box after the results (through the clipboard), so that the '
                                        'model sees it. Needs a chat site and a model that take pictures.')
        self.attach_previews.setChecked(self.settings.value('attach_previews', True, type=bool))
        self.attach_previews.toggled.connect(lambda on: self.settings.setValue('attach_previews', on))
        self.attach_previews.setVisible(self.view is not None)
        layout.addWidget(self.attach_previews)

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
        self.stop_button = QPushButton('Stop', self)
        self.stop_button.setToolTip('Stop the automatic rounds and drop the operations waiting here')
        self.stop_button.clicked.connect(lambda _c=False: self.stop())
        for b in (self.apply_button, self.dismiss_button, self.stop_button, self.preview_button):
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
        # plain Chrome to the sites: some refuse or change pages for "QtWebEngine/…"
        self.profile.setHttpUserAgent(re.sub(r'\s*QtWebEngine/\S+', '', self.profile.httpUserAgent()))
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
        self._paste_action = QWebEnginePage.WebAction.Paste

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
        if QUrl(url).scheme() not in ('http', 'https'):
            # a local file or a script is not a chat page (and what a page shows is run as requests)
            self.say('Only web addresses (https://…) can be opened here.')
            return
        self.settings.setValue('url', url)
        urls = [u for u in self._remembered() if u != url]
        if url not in dict(web_chat.PRESETS).values():
            self.settings.setValue('urls', json.dumps([url] + urls[:9]))
        self.started = False         # a new page: a new conversation
        self.signature_seen, self.signature_missing = False, 0
        if self.view is not None:
            self.baseline_next_scan = True
            self.view.setUrl(QUrl(url))
        else:
            QDesktopServices.openUrl(QUrl(url))

    def forget_login(self):
        """Forget my login…: the cookies, cache and visited links of the
        chat profile, and what the page shown keeps for itself."""
        if self.view is None:
            return
        answer = QMessageBox.question(self, 'Forget my login',
                                      'Delete the cookies and cached pages PyFigures keeps for the chat sites?\n\n'
                                      'You will have to sign in again. Your conversations stay on the chat site.')
        if answer != QMessageBox.StandardButton.Yes:
            return

        def cleared(_result=None):
            self.profile.cookieStore().deleteAllCookies()
            self.profile.clearHttpCache()
            self.profile.clearAllVisitedLinks()
            self.go()
            self.say('Login forgotten: sign in again on the page.')
        self.view.page().runJavaScript(_CLEAR_STORAGE_JS, 0, cleared)

    def write_to_chat(self, text, what, send=False, image=None):
        """Put *text* into the chat box (on the clipboard instead when there
        is no page, or its box was not found); with *send*, press Send for
        the user. *image* (PNG bytes of a preview) is pasted after the text
        when the user allows it."""
        if self.view is None:
            QApplication.clipboard().setText(text)
            self.say(f'{what} copied: paste it into the chat (Ctrl+V) and press Send.')
            return

        def written(how):
            if how not in ('textarea', 'editable'):
                QApplication.clipboard().setText(text)
                self.say(f'{what} could not be typed into this page: click in its message box and paste (Ctrl+V); '
                         'it is on the clipboard.')
                return
            pasted = image is not None and self.attach_previews.isChecked() and self.paste_image(image)
            if send:
                self.say(f'{what} sent; waiting for the answer…')
                # a pasted picture is uploaded first: Send is off meanwhile
                QTimer.singleShot(2500 if pasted else 250, lambda: self.press_send(text))
            else:
                self.say(f'{what} is in the chat box' + (' with the preview' if pasted else '')
                         + ': press Send on the page.')
        self.view.page().runJavaScript(_INSERT_JS % json.dumps(text), 0, written)

    def paste_image(self, png):
        """Paste a preview into the page's chat box (focused by the text
        just written), as Ctrl+V would. True when it was tried."""
        action = getattr(self, '_paste_action', None)
        picture = QImage.fromData(png, 'PNG')
        if action is None or picture.isNull():
            return False
        QApplication.clipboard().setImage(picture)
        self.view.setFocus()
        self.view.page().triggerAction(action)
        return True

    def press_send(self, text, tries=SEND_TRIES):
        """A real Enter in the page's box (what sends on most chat sites);
        when the text is still there a moment later, its send button (looked
        for a few times: it is off while a picture uploads)."""
        self.view.setFocus()
        target = self.view.focusProxy() or self.view
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.postEvent(target, QKeyEvent(kind, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, '\r'))
        start = text.strip()[:40]

        def check(left):
            def clicked(how):
                if how != 'no button':
                    return
                if left > 1:
                    QTimer.singleShot(1500, lambda: check(left - 1))
                else:
                    self.say('Could not press Send on this page: press it yourself.')
            self.view.page().runJavaScript(_SEND_BUTTON_JS % json.dumps(start), 0, clicked)
        QTimer.singleShot(1500, lambda: check(tries))

    # ---- reading answers --------------------------------------------------------
    def scan(self):
        if self.view is None or not self.isVisible():
            return
        baseline = self.baseline_next_scan
        self.baseline_next_scan = False
        def got(text):
            if not isinstance(text, str):
                return
            self._idle_check(text)
            new_conversation = self._conversation_check(text)
            # a block is run once the page stopped changing: the model may still be writing after it,
            # and the sites refuse a message sent meanwhile
            settled = self.unchanged_scans >= 1 or self.unsettled_scans >= MAX_UNSETTLED
            self.read_text(text, baseline or new_conversation, settled=settled)
            self._auto_start()
        self.view.page().runJavaScript(_TEXT_JS, 0, got)

    def _conversation_check(self, text):
        """True when a new conversation was started on the page itself (its
        own "New chat": no page load): the instructions PyFigures sent were
        on the page and are gone. The next request gives them again, and
        the blocks now shown are not replayed."""
        if not self.started or self.busy:
            self.signature_missing = 0
            return False
        if web_chat.SIGNATURE in text:
            self.signature_seen, self.signature_missing = True, 0
            return False
        if not self.signature_seen:
            return False
        self.signature_missing += 1
        if self.signature_missing < 2:
            return False
        self.started = False
        self.signature_seen, self.signature_missing = False, 0
        self.log('new conversation', 'the instructions are no longer on the page')
        return True

    def _auto_start(self):
        """Automatic mode: once the chat page is there (signed in, its box
        shown, the page settled), Start runs and is sent by itself, once per
        conversation."""
        if (self.view is None or self.started or self.busy or self.stopped or not self.automatic.isChecked()
                or self.unchanged_scans < 1):
            return

        def has_box(found):
            if found is True and not (self.started or self.busy or self.stopped) and self.automatic.isChecked():
                self.log('auto start', self.url())
                self.start(send=True)
        self.view.page().runJavaScript(_HAS_BOX_JS, 0, has_box)

    def _automatic_toggled(self, on):
        self.settings.setValue('automatic', on)
        self.rounds_left = MAX_ROUNDS if on else 0
        self.stopped = False
        if on:
            self._next()        # what waits for Apply now runs
        else:
            self._refresh()

    def _idle_check(self, text):
        """A conversation that stopped changing (the model answered without
        operations) ends the automatic run: the next message, typed on the
        page or in the panel, gets MAX_ROUNDS again. Only a model looping
        on operations hits the limit."""
        if text == self.last_text:
            self.unchanged_scans += 1
        else:
            self.last_text, self.unchanged_scans = text, 0
        if (self.automatic.isChecked() and not self.stopped and self.unchanged_scans >= IDLE_SCANS and not self.busy
                and not self.pending and self.rounds_left < MAX_ROUNDS):
            self.rounds_left = MAX_ROUNDS

    def read_text(self, text, baseline=False, page=True, settled=True):
        """New PYFIGURES-CALLS blocks in *text*. A page is read again and
        again, so a block is new when it appears MORE times than before (the
        model may rightly ask for the same operations twice: counting
        distinct texts skipped the repeat). With *baseline*, the blocks of a
        page just opened (or of a new conversation) are only counted, from
        zero: an old conversation is not replayed, and what an earlier one
        asked for can be asked again. A copied reply (*page* False) is new
        as a whole. Not *settled* (the page still changes): new blocks wait
        for the next scan."""
        if not isinstance(text, str):
            return
        new, counts = [], {}
        for block in web_chat.parse_blocks(text):
            counts[block.key] = counts.get(block.key, 0) + 1
            if page and (baseline or counts[block.key] <= self.seen.get(block.key, 0)):
                continue
            new.append(block)
        if page and baseline:
            self.seen = counts
            self.unsettled_scans = 0
            return
        if page and new and not settled:
            self.unsettled_scans += 1
            return
        self.unsettled_scans = 0
        if page:
            # never down: a long conversation whose page drops old messages, then shows
            # them again, must not replay them
            for key, count in counts.items():
                self.seen[key] = max(count, self.seen.get(key, 0))
        for block in new:
            self.log('found', block.describe())
            self.pending.append(block)
        if new:
            self._next()
        elif self.view is None:
            self.say('No PyFigures operations in the copied text.')

    def _next(self):
        """Look-ups run by themselves (when allowed); anything else waits
        for Apply."""
        if self.busy or not self.pending:
            self._refresh()
            return
        block = self.pending[0]
        # saving, exporting, running a script, naming a file: a click, even in automatic mode
        # (what the page shows is not always the model's own words)
        guarded = block.error is None and block.writes_files
        if self._automatic() and not guarded:
            self.rounds_left -= 1
            self.apply()          # an unreadable block: apply sends the correction
            return
        if block.error is None and block.read_only and not guarded and self.auto_lookups.isChecked():
            self.apply()
            return
        self._refresh()
        if guarded and self.automatic.isChecked():
            self.say('These operations write or read files on your computer: Apply to allow them, or Dismiss.')
            return
        if self.automatic.isChecked() and self.rounds_left <= 0:
            self.say(f'Paused after {MAX_ROUNDS} automatic rounds: Apply to go on, or Stop.')
            return
        if block.error:
            self.say('The model\'s last request could not be read. Dismiss sends it a correction.')
        else:
            self.say('The model asks for the operations above: Apply or Dismiss.')

    # ---- acting -----------------------------------------------------------------
    def _run(self, function, done, *args):
        self.busy = True
        self._refresh()
        web_chat.run_async(function, lambda value: self.relay.arrived.emit(done, value), *args)

    def _automatic(self):
        return self.automatic.isChecked() and self.rounds_left > 0

    def start(self, request=None, send=None):
        """The instructions and the figure into the chat box (sent, with
        *request* after them, when the request comes from the panel; sent
        alone with *send*, the automatic start)."""
        if self.busy:
            return
        send = bool(request) if send is None else send
        self.started = True          # not twice while the figure is read
        self.signature_seen, self.signature_missing = False, 0
        self.say('Reading the figure…')

        def done(value):
            self.busy = False
            if isinstance(value, Exception):
                self.started = False
                self.say(f'Could not read the figure: {value}')
            else:
                self.write_to_chat(value, 'The instructions and the figure' + (' with your request' if request else ''),
                                   send=send)
            self._next()
        self._run(self.runner.first_prompt, done, request)

    def ask(self):
        """The request typed in the panel, sent to the chat (with the
        instructions the first time); in automatic mode the rounds that
        follow need no click."""
        request = self.ask_edit.text().strip()
        if not request or self.busy:
            return
        self.ask_edit.clear()
        self.rounds_left = MAX_ROUNDS
        self.stopped = False
        if not self.started:
            self.start(request)
        else:
            self.write_to_chat(request, 'Your request', send=True)

    def stop(self):
        # paused until the next request from the panel, or until Automatic is ticked again
        self.rounds_left = 0
        self.stopped = True
        self.pending.clear()
        self._refresh()
        self.say('Stopped. Nothing more runs by itself until you send a request from the panel or tick '
                 'Automatic again.')

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
            # Stop may have emptied the list meanwhile: the operations ran all the same,
            # and the chat is told (popping blindly raised, and the results were lost)
            if self.pending and self.pending[0] is block:
                self.pending.pop(0)
            if isinstance(value, Exception):
                outcomes, images = [(block.calls[0], False, str(value))], []
            else:
                outcomes, images = value
            if images:
                self.last_image = images[-1]
            # sent by itself in automatic mode (the last round's results wait for the user)
            message = web_chat.results_message(outcomes)
            self.log('results', message)
            self.write_to_chat(message, 'The results', send=self._automatic(),
                               image=images[-1] if images else None)
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
        self.write_to_chat(text, 'The message', send=bool(block.error) and self._automatic())
        self._next()

    def copy_preview(self):
        if self.last_image:
            QApplication.clipboard().setImage(QImage.fromData(self.last_image, 'PNG'))
            self.say('The preview is on the clipboard: paste it into the chat (Ctrl+V) if the page takes images.')

    def say(self, text):
        self.status.setText(text)
        self.log('status', text)

    def log(self, kind, text):
        """What the panel did, in web_chat.log of the live folder (no page
        text, no credentials: blocks found, statuses, results), to explain a
        run that went wrong. Past MAX_LOG_BYTES it starts again, the
        old one kept as web_chat.log.1."""
        try:
            import time
            from pyfigures.assistant import runtime_dir
            path = runtime_dir() / 'web_chat.log'
            if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
                os.replace(path, path.with_name('web_chat.log.1'))
            with open(path, 'a', encoding='utf-8') as f:
                f.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {kind}: {text[:2000]}\n')
        except OSError:
            pass

    def _refresh(self):
        block = self.pending[0] if self.pending else None
        self.request_box.setPlainText(block.describe() if block else '')
        if len(self.pending) > 1:
            self.request_box.appendPlainText(f'(+{len(self.pending) - 1} more waiting)')
        self.apply_button.setEnabled(bool(block) and block.error is None and not self.busy)
        self.dismiss_button.setEnabled(bool(block) and not self.busy)
        self.start_button.setEnabled(not self.busy)
        self.ask_button.setEnabled(not self.busy)
        self.stop_button.setEnabled(bool(self.pending) or self.rounds_left > 0)
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
