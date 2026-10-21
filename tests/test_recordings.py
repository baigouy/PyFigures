"""Regression tests made from the user's bug recordings (GUI Help > Debug >
Record a bug; ``python -m pyfigures.gui.bug_recorder make-test``): each
folder of tests/recordings/ is replayed step by step on its starting figure
and its checks must hold. A recording whose bug is not fixed yet has
"status": "open" and is expected to fail (xfail) until its fix lands; it
then becomes "fixed" and an ordinary test.

Only small stand-in images are kept here; raw recordings stay in the user's
own folder (bug_recorder.recordings_dir()), never in the repository."""
from __future__ import annotations

import glob
import json
import os

import pytest

from gui_e2e_harness import e2e_gui, menus  # noqa: F401
import recording_replay as R

pytestmark = pytest.mark.gui_e2e

HERE = os.path.dirname(os.path.abspath(__file__))


def _recordings():
    out = []
    for path in sorted(glob.glob(os.path.join(HERE, "recordings", "*", "recording.json"))):
        with open(path, encoding="utf-8") as f:
            status = json.load(f).get("status", "open")
        marks = [pytest.mark.xfail(reason="bug not fixed yet", strict=False)] if status == "open" else []
        out.append(pytest.param(os.path.dirname(path), id=os.path.basename(os.path.dirname(path)), marks=marks))
    return out or [pytest.param(None, id="none", marks=pytest.mark.skip(reason="no recording yet"))]


@pytest.mark.parametrize("rec_dir", _recordings())
def test_recording(qapp, e2e_gui, menus, tmp_path, monkeypatch, rec_dir):
    d, state, errors = R.replay(qapp, e2e_gui, rec_dir, tmp_path, menus, monkeypatch)
    assert d.get("checks"), "a recording test needs checks (what was expected)"
    failed = R.run_checks(d, state, errors)
    assert not failed, failed
