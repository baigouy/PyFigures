"""Fiji starts in the background at every launch (user 2026-11-23: keep it). A cached Fiji
downloads nothing, but its start still printed ~6000 debug lines (jgo / scyjava / imagej,
each twice through the app's log handler) while the user dropped images: the window lagged.
The debug log now goes to the console only for a real download. No JVM is started here."""
import logging
import sys
import types

import pytest

R = pytest.importorskip("batoolset.IJ.ij_reader", exc_type=ImportError)
# the real start-up (conftest swaps it for one that refuses); imagej.init is faked below
_REAL_INIT = R._init_ij_unlocked


@pytest.fixture
def fake_init(monkeypatch):
    seen = {}

    def init(*a, **k):
        lg = logging.getLogger("jgo")
        seen["level"] = lg.level
        seen["handlers"] = list(lg.handlers)
        lg.debug("Resolving RELEASE for sc.fiji:fiji")
        return "gateway"
    monkeypatch.setitem(sys.modules, "imagej", types.SimpleNamespace(init=init))
    for name in ("_cleanup_duplicate_jgo_fiji_envs", "_use_conda_java", "silence_java_logging"):
        monkeypatch.setattr(R, name, lambda: None)
    monkeypatch.setattr(R, "_on_fiji_init_callback", None)
    return seen


def test_a_cached_fiji_starts_without_its_debug_log(fake_init, monkeypatch, capsys):
    monkeypatch.setattr(R, "_is_fiji_cached", lambda: True)
    before = list(logging.getLogger("jgo").handlers)
    assert _REAL_INIT() == "gateway"
    assert fake_init["handlers"] == before and fake_init["level"] != logging.DEBUG
    assert "Resolving RELEASE" not in capsys.readouterr().out


def test_a_download_still_shows_its_progress(fake_init, monkeypatch, capsys):
    monkeypatch.setattr(R, "_is_fiji_cached", lambda: False)
    before = list(logging.getLogger("jgo").handlers)
    _REAL_INIT()
    assert fake_init["level"] == logging.DEBUG
    assert "[jgo] Resolving RELEASE" in capsys.readouterr().out
    assert logging.getLogger("jgo").handlers == before   # detached afterwards
