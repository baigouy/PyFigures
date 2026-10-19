"""Atomic saves (pyfigures/atomic_io.py): the intermittent WinError 5 seen by
the 2026-10-19 re-audit (poster saves, figure3.sources.json.tmp) came from a
transient lock on the target and, for the source snapshot, a fixed shared
temporary name."""
from __future__ import annotations

import os
import threading

import pytest

from pyfigures import atomic_io


def _no_temp_left(folder):
    return [n for n in os.listdir(folder) if n.endswith(".tmp")] == []


def test_transient_permission_error_is_retried(tmp_path, monkeypatch):
    target = tmp_path / "f.pyf"
    target.write_text("old", encoding="utf-8")
    real = os.replace
    fails = {"n": 3}

    def flaky(src, dst):
        if fails["n"]:
            fails["n"] -= 1
            raise PermissionError(5, "Access is denied")
        return real(src, dst)

    monkeypatch.setattr(atomic_io.os, "replace", flaky)
    atomic_io.write_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "new"
    assert _no_temp_left(tmp_path)


def test_persistent_failure_keeps_the_old_file_and_raises(tmp_path, monkeypatch):
    target = tmp_path / "f.pyf"
    target.write_text("old", encoding="utf-8")

    def locked(src, dst):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(atomic_io.os, "replace", locked)
    monkeypatch.setattr(atomic_io, "_RETRY_DELAYS", (0.0, 0.0))
    with pytest.raises(PermissionError):
        atomic_io.write_atomic(target, "new", )
    assert target.read_text(encoding="utf-8") == "old"
    assert _no_temp_left(tmp_path)


def test_other_errors_are_not_retried(tmp_path, monkeypatch):
    calls = []

    def missing(src, dst):
        calls.append(1)
        raise FileNotFoundError(dst)

    monkeypatch.setattr(atomic_io.os, "replace", missing)
    with pytest.raises(FileNotFoundError):
        atomic_io.write_atomic(tmp_path / "f.pyf", b"x")
    assert len(calls) == 1


def test_concurrent_saves_of_one_file_never_collide(tmp_path):
    target = tmp_path / "f.sources.json"
    errors = []

    def save(i):
        try:
            for _ in range(20):
                atomic_io.write_atomic(target, f"writer {i}")
        except Exception as e:      # noqa: BLE001 - collected for the assert
            errors.append(e)

    threads = [threading.Thread(target=save, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert target.read_text(encoding="utf-8").startswith("writer ")
    assert _no_temp_left(tmp_path)


def test_source_snapshot_uses_the_atomic_writer(tmp_path, monkeypatch):
    from pyfigures import source_snapshot
    seen = []
    real = atomic_io.write_atomic

    def spy(path, data, **kw):
        seen.append(os.path.basename(os.fspath(path)))
        return real(path, data, **kw)

    monkeypatch.setattr(atomic_io, "write_atomic", spy)
    pyf = tmp_path / "fig.pyf"
    pyf.write_text("<root/>", encoding="utf-8")
    source_snapshot.record(str(pyf), sources=[])
    assert seen == ["fig.sources.json"]
    assert _no_temp_left(tmp_path)
