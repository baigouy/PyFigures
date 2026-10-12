"""
Regression tests for the Qt-safe global exception handler.

Under PyQt6, an unhandled exception propagating out of a slot/timer/event makes Qt
call qFatal()/abort() (0xC0000409 on Windows) — but ONLY while the default
sys.excepthook is installed. install_global_exception_handler() swaps in a
non-default hook so the app logs the error and keeps running instead of dying.
"""
import sys

import pytest

from batoolset.GUI.exception_handler import (
    install_global_exception_handler,
    global_excepthook,
)


@pytest.fixture
def restore_excepthook():
    original = sys.excepthook
    installed = getattr(sys, '_batoolset_excepthook_installed', False)
    yield
    sys.excepthook = original
    if installed:
        sys._batoolset_excepthook_installed = True
    else:
        try:
            del sys._batoolset_excepthook_installed
        except AttributeError:
            pass


def test_installs_non_default_hook(restore_excepthook):
    sys.excepthook = sys.__excepthook__
    if hasattr(sys, '_batoolset_excepthook_installed'):
        del sys._batoolset_excepthook_installed
    install_global_exception_handler()
    # a NON-default hook is exactly what stops PyQt6 from calling qFatal()
    assert sys.excepthook is global_excepthook
    assert sys.excepthook is not sys.__excepthook__


def test_idempotent(restore_excepthook):
    install_global_exception_handler()
    install_global_exception_handler()
    assert sys.excepthook is global_excepthook


def test_hook_does_not_raise(monkeypatch):
    # the hook must swallow everything (it runs where nothing else can catch it)
    shown = {}
    monkeypatch.setattr(
        'batoolset.GUI.exception_handler._show_dialog',
        lambda short, details: shown.update(short=short, details=details))
    try:
        raise UnicodeEncodeError('charmap', 'x', 0, 1, 'boom')
    except UnicodeEncodeError:
        exctype, value, tb = sys.exc_info()
    global_excepthook(exctype, value, tb)   # must not raise
    assert 'UnicodeEncodeError' in shown['short']


def test_keyboard_interrupt_delegated(monkeypatch):
    # Ctrl+C must keep normal behaviour, not pop a dialog
    called = {}
    monkeypatch.setattr(
        'batoolset.GUI.exception_handler._original_excepthook',
        lambda et, v, tb: called.update(delegated=True))
    monkeypatch.setattr(
        'batoolset.GUI.exception_handler._show_dialog',
        lambda *a: called.update(dialog=True))
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        exctype, value, tb = sys.exc_info()
    global_excepthook(exctype, value, tb)
    assert called.get('delegated') and not called.get('dialog')


def test_slot_exception_does_not_abort(qapp):
    """End-to-end: an exception raised inside a real Qt timer slot must not kill
    the process when the handler is installed."""
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QMessageBox, QApplication
    QMessageBox.exec_ = lambda self: None
    QMessageBox.exec = lambda self: None
    install_global_exception_handler()

    fired = {'n': 0}

    def boom():
        fired['n'] += 1
        raise UnicodeEncodeError('charmap', 'x', 0, 1, 'boom in slot')

    QTimer.singleShot(0, boom)
    for _ in range(20):
        QApplication.processEvents()
    # reached here => the abort was suppressed and we survived the slot exception
    assert fired['n'] == 1
