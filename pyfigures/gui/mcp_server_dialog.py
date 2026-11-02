"""Tools > MCP server…: register the PyFigures MCP server with MCP clients,
and start / stop it over HTTP (pyfigures/mcp_control.py)."""
from batoolset.settings.global_settings import set_UI
set_UI()
import json
import threading

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QGuiApplication, QFontDatabase
from qtpy.QtWidgets import (QDialog, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                            QPushButton, QSpinBox, QCheckBox, QMessageBox, QGroupBox)

from pyfigures import mcp_control as C
from pyfigures.gui import user_prefs


class McpServerDialog(QDialog):
    """Registration with Claude Desktop / Claude Code / LM Studio (they start
    the server themselves over stdio when they need it) and an HTTP server
    started and stopped here."""
    _finished = Signal(str)          # a start/stop done in a worker thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PyFigures MCP server")
        self._busy = False
        self.last_message = ""
        lay = QVBoxLayout(self)

        # the setup took too much guessing (LM Studio: where the entry goes,
        # the plug icon in the chat, which document is edited)
        howto = QLabel(
            "<b>How to use it</b><ol style='margin-top:2px'>"
            "<li><b>Register</b> your client below (it merges one 'pyfigures' entry into its "
            "configuration, keeping every other server; a backup is kept), then restart the "
            "client.</li>"
            "<li><b>LM Studio</b>: in a chat, click the <b>plug / hammer icon</b> under the message "
            "box and switch <b>mcp/pyfigures</b> on. Pick a model that can call tools; tool "
            "descriptions use part of the context, so give it 32k tokens or more.</li>"
            "<li>The MCP server works on <b>saved .pyf files</b>: give the model the file's path "
            "(File → Save first). Reopen the file here to see its changes.</li></ol>")
        howto.setWordWrap(True)
        howto.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(howto)

        reg_box = QGroupBox("MCP clients (they start the server when they need it, "
                            "and stop it when they quit)")
        grid = QGridLayout(reg_box)
        self._reg_labels = {}
        self._reg_buttons = {}
        for row, client in enumerate(C.CLIENTS):
            grid.addWidget(QLabel(C.CLIENTS[client]), row, 0)
            state = QLabel()
            grid.addWidget(state, row, 1)
            button = QPushButton()
            button.clicked.connect(lambda _=False, c=client: self.toggle_registration(c))
            grid.addWidget(button, row, 2)
            self._reg_labels[client] = state
            self._reg_buttons[client] = button
        copies = QFrame()
        cl = QHBoxLayout(copies)
        cl.setContentsMargins(0, 0, 0, 0)
        for label, fmt, tip in (("Copy JSON", "json", "The 'mcpServers' entry most MCP clients read "
                                                     "(Windsurf, Cline…). Add its 'pyfigures' entry "
                                                     "INSIDE the file's existing \"mcpServers\" "
                                                     "object: do not replace the other servers."),
                                ("Copy Hermes YAML", "hermes", "For Hermes Agent: paste into "
                                                               "~/.hermes/config.yaml (in WSL "
                                                               "if Hermes runs there).")):
            b = QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fmt: self.copy_snippet(f))
            cl.addWidget(b)
        grid.addWidget(copies, len(C.CLIENTS), 0, 1, 3)
        lay.addWidget(reg_box)

        http_box = QGroupBox("HTTP server (for clients that connect to a URL)")
        h = QVBoxLayout(http_box)
        line = QFrame()
        hl = QHBoxLayout(line)
        hl.setContentsMargins(0, 0, 0, 0)
        self.start_stop = QPushButton()
        self.start_stop.setMinimumHeight(36)
        font = self.start_stop.font()
        font.setBold(True)
        self.start_stop.setFont(font)
        self.start_stop.clicked.connect(self.toggle_http)
        hl.addWidget(self.start_stop, 1)
        hl.addWidget(QLabel("Port"))
        self.port = QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(user_prefs.load_mcp_http_port())
        hl.addWidget(self.port)
        h.addWidget(line)
        self.http_state = QLabel()
        self.http_state.setWordWrap(True)
        h.addWidget(self.http_state)
        # what to paste into each kind of client, shown while the server runs
        self.http_snippets = QFrame()
        sg = QGridLayout(self.http_snippets)
        sg.setContentsMargins(0, 0, 0, 0)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._snippet_texts = []
        for row, s in enumerate(C.http_snippets()):
            title = QLabel(f"<b>{s['title']}</b>")
            title.setToolTip(s["where"])
            sg.addWidget(title, row, 0, Qt.AlignmentFlag.AlignTop)
            text = QLabel()
            text.setFont(mono)
            text.setToolTip(s["where"])
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            sg.addWidget(text, row, 1)
            b = QPushButton("Copy")
            b.setToolTip(s["where"])
            b.clicked.connect(lambda _=False, i=row: self.copy_http_snippet(i))
            sg.addWidget(b, row, 2, Qt.AlignmentFlag.AlignTop)
            self._snippet_texts.append(text)
        sg.setColumnStretch(1, 1)
        h.addWidget(self.http_snippets)
        self.autostart = QCheckBox("Start the HTTP server when PyFigures opens "
                                   "(it stops when PyFigures closes)")
        self.autostart.setChecked(user_prefs.load_mcp_http_autostart())
        self.autostart.toggled.connect(user_prefs.save_mcp_http_autostart)
        h.addWidget(self.autostart)
        lay.addWidget(http_box)

        self.message = QLabel()
        self.message.setWordWrap(True)
        lay.addWidget(self.message)
        self.model_warning = QLabel("⚠ " + C.MODEL_WARNING)
        self.model_warning.setWordWrap(True)
        self.model_warning.setStyleSheet("color: #a15c00;")
        lay.addWidget(self.model_warning)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        lay.addWidget(close)
        self._finished.connect(self._on_finished)
        self.refresh()

    # ── state ────────────────────────────────────────────────────────
    def refresh(self):
        for r in C.registrations():
            if r["error"]:
                text = "configuration unreadable"
            elif r["registered"]:
                text = "registered"
            elif r["disabled"]:
                text = "registered, switched off"
            else:
                text = "not registered"
            self._reg_labels[r["client"]].setText(text)
            self._reg_labels[r["client"]].setToolTip(r["path"] + ("\n" + r["error"] if r["error"] else ""))
            self._reg_buttons[r["client"]].setText("Remove" if (r["registered"] or r["disabled"])
                                                   else "Register")
            self._reg_buttons[r["client"]].setEnabled(not r["error"])
        st = C.http_status()
        if st["running"]:
            self.http_state.setText(f"Running at <b>{st['url']}</b> (pid {st['pid']}). "
                                    "Paste one of these into the client:")
            self.start_stop.setText("Stop the HTTP server")
            self.port.setEnabled(False)
            for text, s in zip(self._snippet_texts, C.http_snippets(st["url"])):
                shown = s["text"].rstrip()
                if shown.startswith("{"):         # JSON on one line here; copied indented
                    shown = json.dumps(json.loads(shown))
                text.setText(shown)
        else:
            self.http_state.setText("Not running. Start it to get the address and what to "
                                    "paste into each client.")
            self.start_stop.setText("Start the HTTP server")
            self.port.setEnabled(True)
        self.http_snippets.setVisible(st["running"])
        self.start_stop.setEnabled(not self._busy)

    def _say(self, text):
        self.last_message = text
        self.message.setText(text)

    # ── actions ──────────────────────────────────────────────────────
    def toggle_registration(self, client, confirm=True):
        r = C.registration(client)
        removing = r["registered"] or r["disabled"]
        if confirm:
            verb = "Remove the PyFigures MCP server from" if removing else "Register the PyFigures MCP server with"
            answer = QMessageBox.question(
                self, "MCP client configuration",
                f"{verb} {C.CLIENTS[client]}?\n\nThis edits {r['path']} "
                f"(a backup is kept beside it). Restart {C.CLIENTS[client]} afterwards.")
            if answer != QMessageBox.StandardButton.Yes:
                return None
        res = C.unregister(client) if removing else C.register(client)
        self._say(res)
        self.refresh()
        return res

    def copy_snippet(self, fmt="json"):
        QGuiApplication.clipboard().setText(C.config_snippet(fmt=fmt))
        self._say("Copied. Paste it into the MCP client's configuration.")

    def copy_http_snippet(self, index):
        s = C.http_snippets()[index]
        QGuiApplication.clipboard().setText(s["text"])
        self._say(f"Copied ({s['title']}). {s['where']}")

    def toggle_http(self, wait=False):
        if self._busy:
            return
        running = C.http_status()["running"]
        port = self.port.value()
        user_prefs.save_mcp_http_port(port)
        self._busy = True
        self.start_stop.setEnabled(False)
        self._say("Stopping…" if running else "Starting…")

        def work():
            res = C.stop_http() if running else C.start_http(port)
            self._finished.emit(res)

        if wait:
            work()
            return self.last_message
        threading.Thread(target=work, daemon=True).start()
        return None

    def _on_finished(self, res):
        self._busy = False
        self._say(res)
        self.refresh()


_autostart_thread = None


def autostart_http_server():
    """Called when PyFigures opens: start the HTTP server if asked to.
    Returns True when this call started it (so it is stopped at close)."""
    global _autostart_thread
    if not user_prefs.load_mcp_http_autostart():
        return False
    if C.http_status()["running"]:
        return False
    _autostart_thread = threading.Thread(target=C.start_http,
                                         args=(user_prefs.load_mcp_http_port(),), daemon=True)
    _autostart_thread.start()
    return True


def stop_autostarted_http_server():
    """Called at close for a server autostart_http_server started."""
    if _autostart_thread is not None:
        _autostart_thread.join(timeout=60)
    return C.stop_http()
