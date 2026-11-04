import glob
import os
import shutil
import tempfile

import pytest
import matplotlib.pyplot as plt

# Before any test creates a QApplication: tests run on Qt's offscreen platform,
# which on Windows finds NO fonts unless QT_QPA_FONTDIR is set (no-op on Linux
# and macOS, where offscreen uses fontconfig / Core Text).
from pyfigures.offscreen import use_offscreen
use_offscreen()

# Tests click Theme / Tips buttons that persist user preferences (QSettings —
# the registry on Windows): keep them in a throw-away INI file so a test run
# never changes the real user's theme or tip settings.
def _isolate_user_prefs():
    try:
        from pyfigures.gui import user_prefs
        from qtpy.QtCore import QSettings
    except Exception:
        return
    ini = os.path.join(tempfile.mkdtemp(prefix='pyfigures_test_prefs_'), 'prefs.ini')
    user_prefs._s = lambda: QSettings(ini, QSettings.Format.IniFormat)


_isolate_user_prefs()


# The colour-blind assistant samples the REAL screen around the mouse every
# 100 ms (pyautogui + PIL.ImageGrab). Tests open it, so screen access is
# replaced suite-wide by a fixed synthetic patch: no capture of the user's
# desktop, ever, and the same pixels on every machine.
def _no_real_screen_capture():
    import sys
    import types
    fake = types.ModuleType('pyautogui')
    fake.position = lambda: (0, 0)
    sys.modules['pyautogui'] = fake
    try:
        from PIL import Image, ImageGrab

        def _grab(bbox=None, **_kw):
            w, h = ((bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else (64, 48))
            return Image.new('RGB', (max(1, w), max(1, h)), (200, 40, 90))
        ImageGrab.grab = _grab
    except Exception:
        pass


_no_real_screen_capture()


# ---------------------------------------------------------------------------
# Deterministic end of session
# ---------------------------------------------------------------------------
# After every test has passed, the process could still die with an access
# violation (sip / ~QApplication) while Python tore down its objects in an
# arbitrary order — timing-dependent, seen when the machine was busy. So the
# session ends in a fixed order: loader threads joined, windows and matplotlib
# figures closed, Qt's pending deletions processed, Qt's thread pool drained;
# then the process exits with pytest's status WITHOUT the random interpreter
# teardown (as the app itself does with os._exit in pyfigures/__main__.py).
# Set PYFIGURES_TEST_NORMAL_EXIT=1 to get the ordinary teardown (debugging).

def _orderly_qt_shutdown():
    import sys
    if 'qtpy' not in sys.modules:
        return
    from qtpy.QtCore import QCoreApplication, QEvent, QThreadPool
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        stop = getattr(w, '_stop_all_img_loaders', None)
        if stop is not None:
            stop()
        if hasattr(w, '_dirty'):
            w._dirty = False          # no save prompt
        canvas = getattr(w, 'canvas', None)
        if hasattr(canvas, 'mark_saved'):
            canvas.mark_saved()       # poster designer: no save prompt either
        w.close()
    plt.close('all')
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
    QThreadPool.globalInstance().waitForDone(10000)
    import gc
    gc.collect()


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    if os.environ.get('PYFIGURES_TEST_NORMAL_EXIT'):
        return
    status = getattr(config, '_pyfigures_exitstatus', None)
    if status is None:
        return                         # not a normal test session (e.g. --help)
    try:
        _orderly_qt_shutdown()
    finally:
        import sys
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(int(status))


def pytest_sessionfinish(session, exitstatus):
    session.config._pyfigures_exitstatus = exitstatus


# ---------------------------------------------------------------------------
# --clean-tmp  option
# ---------------------------------------------------------------------------

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "gui_e2e: end-to-end GUI layer (real Qt events, saved-state checks); "
        "run alone with  pytest -m gui_e2e  (see docs/GUI_E2E_TESTS.md)")


def pytest_addoption(parser):
    parser.addoption(
        "--clean-tmp",
        action="store_true",
        default=False,
        help="Delete all pytest-generated tmp directories before running tests.",
    )


def pytest_sessionstart(session):
    """Remove stale pytest tmp dirs when --clean-tmp is passed."""
    if not session.config.getoption("--clean-tmp"):
        return
    pattern = os.path.join(tempfile.gettempdir(), "pytest-of-*")
    removed = []
    for d in glob.glob(pattern):
        shutil.rmtree(d, ignore_errors=True)
        removed.append(d)
    if removed:
        print(f"\n[clean-tmp] Removed {len(removed)} directory(ies):")
        for d in removed:
            print(f"  {d}")
    else:
        print("\n[clean-tmp] Nothing to remove.")

# Location of the sample .pyf files. Cross-platform: the Linux box keeps its
# original path; on this Windows machine the folder lives under the Desktop
# test_images tree. First existing candidate wins; PYFIGURES_SAMPLE_DIR overrides.
_SAMPLE_DIR_CANDIDATES = [
    os.environ.get('PYFIGURES_SAMPLE_DIR'),
    '/home/aigouy/Bureau/sample_pyf_pyfigures_files',
    r'C:\Users\aigouy\OneDrive\Desktop\test_images\sample_pyf_pyfigures_files',
]
SAMPLE_DIR = next(
    (d for d in _SAMPLE_DIR_CANDIDATES if d and os.path.isdir(d)),
    _SAMPLE_DIR_CANDIDATES[1],  # fall back to the Linux default if none exist
)


@pytest.fixture(autouse=True)
def poster_render_cache_in_tmp(tmp_path, monkeypatch):
    """The poster designer caches flattened .pyf figures under
    ~/.pyfigures/poster_pyf_renders — tests must not write in the user's home."""
    try:
        from pyfigures.poster import poster_canvas
    except Exception:
        yield
        return
    monkeypatch.setattr(poster_canvas, 'PYF_RENDER_CACHE_DIR', str(tmp_path / 'pyf_renders'))
    yield


def _keep_message_box_titles():
    """QMessageBox ignores its window title on macOS (Apple's guidelines), so
    the GUI tests, which recognise dialogs by title, saw anonymous boxes there.
    The title is set through QWidget.setWindowTitle instead, on every platform
    (so the same code runs on Windows/Linux, where it changes nothing)."""
    try:
        from qtpy.QtWidgets import QMessageBox, QWidget
    except Exception:
        return
    if getattr(QMessageBox, "_tests_keep_titles", False):
        return
    QMessageBox._tests_keep_titles = True
    Button = QMessageBox.StandardButton
    original_init = QMessageBox.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        title = kwargs.get("title", args[1] if len(args) > 1 else None)
        if isinstance(title, str):
            QWidget.setWindowTitle(self, title)

    def setWindowTitle(self, title):
        QWidget.setWindowTitle(self, title)

    def static(icon, default_buttons):
        # Qt's static helpers set the title in C++ (ignored on macOS): same
        # behaviour rebuilt in Python, returning the clicked standard button
        def show(parent, title, text, buttons=default_buttons, defaultButton=Button.NoButton):
            box = QMessageBox(icon, title, text, buttons, parent)
            box.setDefaultButton(defaultButton)
            if box.exec() == -1:
                return Button.Cancel
            clicked = box.clickedButton()
            return box.standardButton(clicked) if clicked is not None else Button.NoButton
        show._suite_dialog_patch = True       # ensure_real_dialogs keeps it (gui_e2e_harness)
        return staticmethod(show)

    Icon = QMessageBox.Icon
    QMessageBox.__init__ = __init__
    QMessageBox.setWindowTitle = setWindowTitle
    QMessageBox.information = static(Icon.Information, Button.Ok)
    QMessageBox.warning = static(Icon.Warning, Button.Ok)
    QMessageBox.critical = static(Icon.Critical, Button.Ok)
    QMessageBox.question = static(Icon.Question, Button.Yes | Button.No)


_keep_message_box_titles()


@pytest.fixture(autouse=True)
def no_tinytex_download(monkeypatch):
    """No real TinyTeX download or tlmgr run: a GUI test answering Yes to
    'Install LaTeX?' downloaded TinyTeX on the CI runners, half-installed it
    (packages failed) and later LaTeX tests found a broken latex. Tests that
    exercise the installer patch these two with their own fakes."""
    try:
        from batoolset import tex_install
    except Exception:
        yield
        return

    def _refuse(*_a, **_k):
        raise RuntimeError("no TinyTeX download in the test suite")
    monkeypatch.setattr(tex_install, "_download", _refuse)
    monkeypatch.setattr(tex_install, "_run", _refuse)
    yield


@pytest.fixture(autouse=True)
def no_fiji_jvm_in_the_test_process(monkeypatch):
    """No Fiji fallback reader inside the test process: it starts a Java VM
    that raises access violations on purpose and stays loaded, after which Qt
    crashed at random places later in the run. Files only Fiji reads are
    tested in a child process (test_fiji_formats.py)."""
    try:
        from batoolset import image_reader
    except Exception:
        yield
        return
    monkeypatch.setattr(image_reader, '_ij_reader_available', False, raising=False)
    try:
        from batoolset.IJ import ij_reader     # importing it starts no JVM
    except Exception:
        yield
        return

    def _no_jvm(*_a, **_k):
        raise RuntimeError('Fiji is not used inside the test process')
    # series counting (get_series_info) reaches the JVM without init_ij
    # the JVM start itself (init_ij's singleton logic stays testable)
    monkeypatch.setattr(ij_reader, '_init_ij_unlocked', _no_jvm)
    monkeypatch.setattr(ij_reader, '_java_imports', _no_jvm)
    yield


@pytest.fixture(autouse=True)
def close_matplotlib_figures():
    yield
    plt.close('all')


@pytest.fixture(autouse=True)
def join_gui_loader_threads():
    """Tests leave EZFIG_GUI windows open; their .pyf / image loader QThreads
    must be finished before the process exits — a QThread destroyed while
    running is an access violation at interpreter shutdown (timing-dependent:
    it showed up when the machine was busy)."""
    yield
    import sys
    if 'qtpy' not in sys.modules:
        return
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        return
    for w in app.topLevelWidgets():
        stop = getattr(w, '_stop_all_img_loaders', None)
        if stop is not None:
            stop()


def sample_pyf(name):
    return os.path.join(SAMPLE_DIR, name)


# the sample .pyf files live outside the repository (not on CI runners)
needs_sample_dir = pytest.mark.skipif(not os.path.isdir(SAMPLE_DIR),
                                      reason="the sample .pyf files are not on this computer")


@pytest.fixture(scope='session')
def sample_dir():
    if not os.path.isdir(SAMPLE_DIR):
        pytest.skip("the sample .pyf files are not on this computer")
    return SAMPLE_DIR


@pytest.fixture(scope='session')
def all_pyf_files(sample_dir):
    return sorted(
        os.path.join(sample_dir, f)
        for f in os.listdir(sample_dir)
        if f.endswith('.pyf')
    )
