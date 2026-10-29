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


@pytest.mark.parametrize("last_line", ["raise SystemExit(main())", "import sys\nsys.exit(main())"])
def test_code_kept_when_the_exit_was_looked_up_before_the_guard_was_armed(last_line):
    """SystemExit / sys.exit is looked up before main() runs: when main() armed
    the guard, the poster helper and the recipe CLI ended with 0 after an error."""
    body = ("import pyfigures\n"
            "def main():\n"
            "    from pyfigures.mcp_tools.core import _ensure_qapp\n"
            "    _ensure_qapp()\n"
            "    return 3\n" + last_line + "\n")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API="pyqt6")
    env.pop("PYFIGURES_QT_TEARDOWN", None)
    r = subprocess.run([sys.executable, "-c", body], capture_output=True, text=True,
                       env=env, timeout=300, stdin=subprocess.DEVNULL)
    assert r.returncode == 3, r.stderr[-2000:]


def test_poster_helper_reports_an_error_with_a_non_zero_code(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API="pyqt6")
    env.pop("PYFIGURES_QT_TEARDOWN", None)
    poster = str(tmp_path / "p.pyfposter")
    run = [sys.executable, "-m", "pyfigures.poster.poster_headless"]
    assert subprocess.run(run + ["create", poster], capture_output=True, env=env,
                          timeout=300, stdin=subprocess.DEVNULL).returncode == 0
    r = subprocess.run(run + ["align-shapes", poster, "--mode", "left", "--indices", "x"],
                       capture_output=True, text=True, env=env, timeout=300,
                       stdin=subprocess.DEVNULL)
    assert r.returncode == 1 and "ERROR" in r.stderr


def test_guard_is_off_under_pytest():
    from pyfigures import qt_exit
    qt_exit.skip_qt_teardown()
    assert not qt_exit._installed
