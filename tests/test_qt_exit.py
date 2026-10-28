"""pyfigures.qt_exit: a script that used PyFigures in-process ends with the exit
code it asked for, without going through Qt's teardown (which crashed with
0xC0000005 after check_journal_compliance and another tool, 2026-10-28)."""
import os
import subprocess
import sys

import pytest

PRELUDE = (
    "import atexit\n"
    "from pyfigures.mcp_tools.core import _ensure_qapp\n"
    "_ensure_qapp()\n"
    "atexit.register(lambda: print('LATER-HANDLER-RAN', flush=True))\n"
)


def _run(body):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API="pyqt6")
    env.pop("PYFIGURES_QT_TEARDOWN", None)
    return subprocess.run([sys.executable, "-c", PRELUDE + body], capture_output=True, text=True,
                          env=env, timeout=300, stdin=subprocess.DEVNULL)


@pytest.mark.parametrize("body, code", [
    ("print('ok')\n", 0),
    ("import sys\nsys.exit(3)\n", 3),
    ("raise SystemExit(4)\n", 4),
    ("raise ValueError('boom')\n", 1),
    ("import sys\nsys.exit('bad input')\n", 1),
    ("try:\n    raise SystemExit(5)\nexcept SystemExit:\n    pass\nimport sys\nsys.exit(0)\n", 0),
])
def test_exit_code_is_kept(body, code):
    r = _run(body)
    assert r.returncode == code, r.stderr[-2000:]
    assert "LATER-HANDLER-RAN" in r.stdout          # handlers registered afterwards still run


def test_guard_is_off_under_pytest():
    from pyfigures import qt_exit
    qt_exit.skip_qt_teardown()
    assert not qt_exit._installed
