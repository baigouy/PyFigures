"""Atomic file replacement shared by every PyFigures save path.

A save writes a uniquely named temporary file next to the target, then renames
it over the target with os.replace, so an interrupted save leaves the previous
file intact. On Windows the rename can fail for a moment with
PermissionError (WinError 5/32) while OneDrive, an antivirus scanner, the
search indexer or another PyFigures save holds the target; the rename is then
retried with a bounded backoff (about 3 s in all). If it still fails, the
temporary file is removed, the previous file is left untouched and the error
is raised so the caller can report it.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time

_RETRY_DELAYS = (0.02, 0.05, 0.1, 0.1, 0.2, 0.2, 0.3, 0.4, 0.5, 0.5, 0.6)
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(path: str) -> threading.Lock:
    """One lock per destination: two threads saving the same file take turns."""
    key = os.path.normcase(os.path.abspath(path))
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _locks[key] = lock
        return lock


def replace_with_retry(tmp: str, path: str, delays=_RETRY_DELAYS) -> None:
    """os.replace(tmp, path), retried on PermissionError only (a transient
    sharing/access lock on Windows). Any other error is raised at once."""
    for delay in delays:
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(delay)
    os.replace(tmp, path)


def write_atomic(path, data, *, encoding: str = "utf-8", fsync: bool = False,
                 make_dirs: bool = False) -> None:
    """Write *data* (str or bytes) to *path* atomically. The temporary file has
    a unique name (two concurrent saves never share it) and is removed when the
    save fails, leaving the previous *path* as it was. *make_dirs* creates a
    missing parent folder (otherwise that is an error)."""
    path = os.fspath(path)
    folder = os.path.dirname(os.path.abspath(path)) or "."
    base = os.path.basename(path)
    if make_dirs:
        os.makedirs(folder, exist_ok=True)
    with _lock_for(path):
        fd, tmp = tempfile.mkstemp(prefix=f".~{base}.", suffix=".tmp", dir=folder)
        try:
            if isinstance(data, str):
                with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
                    f.write(data)
                    if fsync:
                        f.flush()
                        os.fsync(f.fileno())
            else:
                with os.fdopen(fd, "wb") as f:
                    f.write(data)
                    if fsync:
                        f.flush()
                        os.fsync(f.fileno())
            replace_with_retry(tmp, path)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
