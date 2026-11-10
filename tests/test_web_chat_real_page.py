"""The web chat panel's typing, sending and picture pasting against real Qt
WebEngine pages (local ones), in a process of its own
(web_chat_real_page_check.py). Skipped where Qt WebEngine is not installed
(the CI: it is optional)."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))


def _has_web_engine():
    try:
        return importlib.util.find_spec("PyQt6.QtWebEngineWidgets") is not None
    except (ImportError, ValueError):
        return False


@pytest.mark.skipif(not _has_web_engine(), reason="Qt WebEngine (PyQt6-WebEngine) is not installed")
def test_typing_sending_and_pasting_in_real_pages(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API="pyqt6",
               PYFIGURES_LIVE_RUNTIME=str(tmp_path / "runtime"), PYTHONUTF8="1")
    env["PYTHONPATH"] = os.pathsep.join([os.path.dirname(HERE), env.get("PYTHONPATH", "")])
    done = subprocess.run([sys.executable, os.path.join(HERE, "web_chat_real_page_check.py")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=240)
    line = next((l for l in done.stdout.splitlines() if l.startswith("RESULTS ")), None)
    if line is None and "context" in (done.stderr or "").lower() and "gl" in (done.stderr or "").lower():
        pytest.skip("Qt WebEngine cannot draw here: " + done.stderr[-300:])
    # the exit status is not checked: Qt WebEngine may crash when the process ends
    assert line is not None, done.stdout[-1500:] + done.stderr[-1500:]
    pages = json.loads(line[len("RESULTS "):])
    text = "Hello from PyFigures\nline 2"
    # a real Enter sends where the site listens to it
    assert pages["enter"]["sent"].strip() == text and pages["enter"]["box"] == ""
    # else the button named Send
    assert pages["button"]["sent"].strip() == text
    # an unnamed submit button counts only in the chat box's own form; never Stop, never another form
    assert pages["form"]["sent"].strip() == text and pages["form"]["wrong"] == ""
    # nothing that sends: nothing else is clicked, and the user is told
    assert pages["none"]["sent"] == "" and pages["none"]["wrong"] == ""
    assert pages["none"]["box"].strip() == text and "press it yourself" in pages["none"]["status"]
    # a preview is pasted into the chat box as a picture, after the text
    assert pages["image"]["pasted"].startswith("image/") and "with the preview" in pages["image"]["status"]
