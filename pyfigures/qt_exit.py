"""Skip Qt's teardown when a process that loaded PyFigures in-process exits.

A Python script that calls PyFigures functions (the MCP tool functions, the
headless renderers) gets a QApplication inside its own process. When such a
script ends, Python destroys modules and Qt objects in no particular order and
Qt's own shutdown can then crash after all the work is done: an access
violation with no Python frame, and exit code 139 / 0xC0000005 instead of 0, so
a pipeline sees a failure. Deleting or keeping the QApplication does not help
(verified 2026-10-28 on check_journal_compliance followed by another tool).

skip_qt_teardown() ends the process with os._exit once every atexit handler
registered after it has run, after flushing logging and the standard streams,
with the exit code the script asked for: sys.exit(n) / raise SystemExit(n)
give n, an uncaught exception gives 1, a normal end 0. The operating system
frees memory, handles and windows itself; files written by PyFigures are
already closed when its functions return.

The code is recorded from the moment the pyfigures package is imported
(install_recorder, called by pyfigures/__init__.py), not only once the guard
is armed: in ``raise SystemExit(main())`` or ``sys.exit(main())`` Python looks
up SystemExit / sys.exit BEFORE main() runs, and when main() was what armed the
guard, a failing run of the poster helper or the recipe CLI ended with 0.

It does nothing under pytest (pytest's exit status comes from SystemExit
handling and its own atexit hooks) or when PYFIGURES_QT_TEARDOWN=1.
"""
import atexit
import builtins
import os
import sys

_installed = False
_code = [0]


def _as_code(code):
    if code is None:
        return 0
    if isinstance(code, bool):
        return int(code)
    if isinstance(code, int):
        return code
    try:                              # sys.exit("message"): Python prints it, status 1
        sys.stderr.write(f"{code}\n")
    except Exception:
        pass
    return 1


class _RecordedSystemExit(builtins.SystemExit):
    """`raise SystemExit(n)` in Python code records n (an exception class is
    looked up in builtins when it is raised)."""

    def __init__(self, *args):
        super().__init__(*args)
        _code[0] = args[0] if args else None


def _exit_now():
    code = _as_code(_code[0])
    try:
        import logging
        logging.shutdown()
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(code)


_recording = False


def _disabled():
    return "pytest" in sys.modules or os.environ.get("PYFIGURES_QT_TEARDOWN") == "1"


def install_recorder():
    """Record the exit code a script asks for (sys.exit, raise SystemExit, an
    uncaught exception). Inert on its own: nothing changes how the process
    ends until skip_qt_teardown() arms the guard."""
    global _recording
    if _recording or _disabled():
        return
    _recording = True

    real_exit = sys.exit

    def exit(code=None):
        _code[0] = code
        real_exit(code)

    sys.exit = exit
    builtins.SystemExit = _RecordedSystemExit

    previous_hook = sys.excepthook

    def excepthook(kind, value, tb):      # never called for SystemExit
        _code[0] = 1
        previous_hook(kind, value, tb)

    sys.excepthook = excepthook


def skip_qt_teardown():
    """Install the exit guard once (see the module docstring)."""
    global _installed
    if _installed or _disabled():
        return
    _installed = True
    install_recorder()
    # atexit runs handlers last-registered-first: handlers registered after this
    # one (by the script or later imports) still run before the process ends
    atexit.register(_exit_now)
