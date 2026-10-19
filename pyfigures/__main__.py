# all seems now ok and working well maybe do advanced tests so that I can do this even better

from batoolset.settings.global_settings import set_UI
set_UI()
from qtpy.QtWidgets import QApplication, QMessageBox, QProgressDialog
import sys
from pyfigures.gui.pfgui import EZFIG_GUI
import os
# os.environ['QT_FONT_DPI'] = '144'
# os.environ['QT_LOGGING_RULES'] = 'qt.qpa.wayland*=false' # --> silences wayland bugs but still crashes

def run_pyfigures():
    """
    Runs the PyFigures GUI.

    This function sets the UI and initializes the QApplication.
    The EPySeg PyFigures window is created and shown.
    The application event loop is started and the program exits
    when the GUI window is closed.
    """

    try:
        import batoolset.IJ.ij_reader as ij_reader  # availability check — no JVM started yet
        _use_ij_reader = True
    except ImportError:
        ij_reader = None
        _use_ij_reader = False

    # Initialize the QApplication
    app = QApplication(sys.argv)
    from pyfigures.icons import set_app_identity
    set_app_identity('pyfigures')

    # Install a Qt-safe global exception hook: without it, any unhandled exception
    # raised inside a slot/timer/event makes PyQt6 abort the whole app with
    # 0xC0000409. With it, the error is logged and shown, and the app keeps running.
    from batoolset.GUI.exception_handler import install_global_exception_handler
    install_global_exception_handler()

    from pyfigures.gui.theme import apply_theme, load_saved_theme
    apply_theme(load_saved_theme())

    if False:
        # just a trick to override the default cursor...
        from qtpy.QtGui import QCursor, QPixmap
        # Load a custom cursor image
        cursor_image = QPixmap("/home/aigouy/Téléchargements/cursor-mini.png")
        # Create a custom cursor object with the cursor image
        custom_cursor = QCursor(cursor_image)
        # Set the custom cursor globally for the application
        QApplication.setOverrideCursor(custom_cursor)

    if True:  # TODO -> set this to true at some point
        if _use_ij_reader:
            from qtpy.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                        QLabel, QPushButton, QFrame)
            from qtpy.QtCore import Qt, QTimer
            import threading

            import queue as _queue
            import io as _io
            import re as _re
            import time as _time

            _ANSI_RE = _re.compile(r'\x1b\[[0-9;]*[mGKHF]')

            class _QueueWriter(_io.TextIOBase):
                """Tees stdout/stderr to the original stream and a queue for the dialog."""
                def __init__(self, original, q):
                    self._original = original
                    self._q = q
                def write(self, text):
                    self._original.write(text)
                    self._original.flush()
                    clean = _ANSI_RE.sub('', text).replace('\r', '').strip()
                    if clean:
                        self._q.put(clean)
                    return len(text)
                def flush(self):
                    self._original.flush()

            class FijiInitDialog(QDialog):
                """Progress dialog for Fiji initialisation with Skip and Quit options."""

                def __init__(self, log_queue, parent=None):
                    super().__init__(parent)
                    from qtpy.QtWidgets import QTextEdit
                    self._programmatic_close = False
                    self._log_queue = log_queue
                    self.setWindowTitle('Fiji initialisation')
                    self.setWindowFlags(
                        Qt.Window |
                        Qt.WindowStaysOnTopHint |
                        Qt.WindowTitleHint
                    )
                    self.setFixedSize(560, 420)
                    self.user_skipped = False
                    self.user_quit    = False

                    layout = QVBoxLayout()
                    layout.setSpacing(12)
                    layout.setContentsMargins(20, 20, 20, 20)

                    title = QLabel('Fiji (ImageJ) — First Time Setup')
                    title.setStyleSheet('font-size: 14pt; font-weight: bold;')
                    layout.addWidget(title)

                    line = QFrame()
                    line.setFrameShape(QFrame.HLine)
                    line.setFrameShadow(QFrame.Sunken)
                    layout.addWidget(line)

                    msg = QLabel(
                        'Fiji is being downloaded and initialised for the first time.<br>'
                        'This requires a one-time download of approximately <b>200MB</b>.<br><br>'
                        '<b style="color:red;">⚠ This can take up to 10 minutes</b> depending on your '
                        'internet speed — hundreds of dependencies must be resolved.<br>'
                        'Subsequent launches will be <b>instant</b> — this only happens once.'
                    )
                    msg.setWordWrap(True)
                    msg.setStyleSheet('font-size: 10pt;')
                    layout.addWidget(msg)

                    auto_close = QLabel(
                        '<html>&#9432;&nbsp; This window will close automatically once initialisation is complete.'
                    )
                    auto_close.setWordWrap(True)
                    auto_close.setStyleSheet('font-size: 10pt; color: red; font-style: italic;')
                    layout.addWidget(auto_close)

                    self._spinner_label = QLabel('Please wait...')
                    self._spinner_label.setAlignment(Qt.AlignCenter)
                    self._spinner_label.setStyleSheet('font-size: 10pt; color: grey;')
                    layout.addWidget(self._spinner_label)

                    self._log_view = QTextEdit()
                    self._log_view.setReadOnly(True)
                    self._log_view.setFixedHeight(100)
                    self._log_view.setStyleSheet('font-size: 8pt; font-family: monospace; background: #1e1e1e; color: #d4d4d4;')
                    layout.addWidget(self._log_view)

                    layout.addSpacing(4)

                    line2 = QFrame()
                    line2.setFrameShape(QFrame.HLine)
                    line2.setFrameShadow(QFrame.Sunken)
                    layout.addWidget(line2)

                    options_label = QLabel('Or choose an option below:')
                    options_label.setStyleSheet('font-size: 9pt; color: grey;')
                    layout.addWidget(options_label)

                    btn_layout = QHBoxLayout()
                    btn_skip = QPushButton('Skip (use legacy reader)')
                    btn_quit = QPushButton('Quit')
                    btn_skip.setMinimumWidth(160)
                    btn_quit.setMinimumWidth(80)
                    btn_quit.setStyleSheet('color: red;')
                    btn_layout.addWidget(btn_skip)
                    btn_layout.addStretch()
                    btn_layout.addWidget(btn_quit)
                    layout.addLayout(btn_layout)

                    self.setLayout(layout)

                    btn_skip.clicked.connect(self._on_skip)
                    btn_quit.clicked.connect(self._on_quit)

                    self._spinner_states = ['Please wait .  ', 'Please wait .. ', 'Please wait ...']
                    self._spinner_idx = 0
                    self._timer = QTimer()
                    self._timer.timeout.connect(self._tick)
                    self._timer.start(400)

                def _tick(self):
                    self._spinner_label.setText(
                        self._spinner_states[self._spinner_idx % len(self._spinner_states)])
                    self._spinner_idx += 1
                    # drain the log queue and append to the log view
                    try:
                        while True:
                            line = self._log_queue.get_nowait()
                            self._log_view.append(line)
                            self._log_view.verticalScrollBar().setValue(
                                self._log_view.verticalScrollBar().maximum())
                    except _queue.Empty:
                        pass

                def _on_skip(self):
                    self.user_skipped = True
                    self._timer.stop()
                    self.accept()

                def _on_quit(self):
                    self.user_quit = True
                    self._timer.stop()
                    self.reject()

                def closeEvent(self, event):
                    if not self._programmatic_close:
                        self.user_skipped = True
                    self._timer.stop()
                    event.accept()

            if not ij_reader._is_fiji_cached():
                # Fiji not cached — show dialog and wait for download
                log_queue = _queue.Queue()
                dialog = FijiInitDialog(log_queue=log_queue, parent=app.activeWindow())
                dialog.show()
                app.processEvents()

                done  = threading.Event()
                error = [None]

                def _run():
                    import sys as _sys
                    import logging as _logging
                    _orig_out = _sys.stdout
                    _orig_err = _sys.stderr
                    try:
                        _sys.stdout = _QueueWriter(_orig_out, log_queue)
                        _sys.stderr = _QueueWriter(_orig_err, log_queue)

                        # Forward jgo/imagej/scyjava log records to the dialog queue
                        class _QHandler(_logging.Handler):
                            def emit(self, record):
                                print(f'[{record.name.split(".")[-1]}] {record.getMessage()}')

                        _qh = _QHandler(_logging.DEBUG)
                        _patched_loggers = []
                        for _name in ('jgo', 'imagej', 'scyjava', 'cjdk'):
                            _lg = _logging.getLogger(_name)
                            _prev_level = _lg.level
                            _lg.setLevel(_logging.DEBUG)
                            _lg.addHandler(_qh)
                            _patched_loggers.append((_lg, _qh, _prev_level))

                        try:
                            ij_reader.init_ij()
                        except Exception as e:
                            error[0] = str(e)
                        finally:
                            for _lg, _qh, _prev in _patched_loggers:
                                _lg.removeHandler(_qh)
                                _lg.setLevel(_prev)
                    finally:
                        _sys.stdout = _orig_out
                        _sys.stderr = _orig_err
                        done.set()

                threading.Thread(target=_run, daemon=True).start()

                while not done.is_set() and dialog.isVisible():
                    app.processEvents()
                    _time.sleep(0.05)

                dialog._programmatic_close = True
                dialog.close()
                app.processEvents()

                if dialog.user_quit:
                    sys.exit(0)

                if error[0]:
                    QMessageBox.critical(None, 'Fiji init failed',
                                         f'Could not initialise Fiji:\n\n{error[0]}')
                elif not dialog.user_skipped:
                    print('Fiji loaded successfully.')

            else:
                # Fiji already cached — init silently in background
                def _init_fiji_cached():
                    try:
                        ij_reader.init_ij()
                        print('Fiji loaded successfully.')
                    except Exception:
                        pass
                threading.Thread(target=_init_fiji_cached, daemon=True).start()

    # Only NOW create the main window — Fiji is fully ready (or skipped)
    w = EZFIG_GUI()
    w.show()
    w.open_guide_mailbox()      # MCP show_me_how / `python -m pyfigures.guides show …`

    # Run the event loop; it returns once the last window is closed.
    exit_code = app.exec_() if hasattr(app, 'exec_') else app.exec()
    # Force-terminate: the ImageJ/JVM background threads are non-daemon and would
    # otherwise keep the interpreter alive after the window closes. closeEvent has
    # already run its cleanup by this point.
    os._exit(exit_code)


def requested_tool(argv, executable):
    """'album' or 'poster' when that designer should open instead of the
    figure editor: `--album`/`--poster` on the command line, or, in the
    standalone app, the 'PyFigures Album' / 'PyFigures Poster' executables
    (copies of PyFigures built by pyfigures.spec, told apart only by their
    name). None otherwise."""
    if '--album' in argv:
        return 'album'
    if '--poster' in argv:
        return 'poster'
    name = os.path.basename(executable).lower()
    for tool in ('album', 'poster'):
        if tool in name:
            return tool
    return None


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        # build check: PyFigures --self-test report.json (see pyfigures/self_test.py)
        from pyfigures.self_test import run as run_self_test
        args = sys.argv[sys.argv.index('--self-test') + 1:]
        code = run_self_test(args[0] if args else 'pyfigures_self_test.json')
        sys.stdout.flush()
        os._exit(code)
    tool = requested_tool(sys.argv[1:], sys.executable if getattr(sys, 'frozen', False) else '')
    if tool is not None:
        from pyfigures.poster.__main__ import run_poster_designer
        run_poster_designer(album=tool == 'album')
    else:
        # Run the PyFigures GUI
        run_pyfigures()