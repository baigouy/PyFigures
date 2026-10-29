"""Call history and undo for figures edited through the MCP server.

Every MCP tool call that names a figure is appended to
``<figure>.history/log.jsonl`` beside it: the tool, its arguments, whether it
succeeded, the start of its reply and whether it changed the figure. A call
that changed the figure also keeps the figure as it was BEFORE the call (the
.pyf and its sidecars, in ``<figure>.history/NNNN/``), so it can be undone.

Undo is refused when the figure was changed after the call by something else
(the GUI, another program): restoring would silently drop that work. The
snapshots are stored as ``*.snap`` files so that folder scans never take them
for figures.

Used by the MCP server (every call; tools list_history / undo_last), the GUI
(File > MCP call history…) and the command line::

    python -m pyfigures.history figure.pyf            # list the calls
    python -m pyfigures.history figure.pyf --undo 2   # undo the last 2 changes
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil
import sys

SIDECAR_EXTS = (".caption.json", ".stats.json", ".alttext.json", ".sources.json",
                ".target.json")
MAX_SNAPSHOTS = 100          # older before-states are pruned (the log is kept)
_MAX_ARG_CHARS = 4000        # long arguments (an inline recipe) are cut in the log


def history_dir(pyf_path: str) -> str:
    return os.path.splitext(os.path.abspath(pyf_path))[0] + ".history"


def _log_path(pyf_path: str) -> str:
    return os.path.join(history_dir(pyf_path), "log.jsonl")


def _state_files(pyf_path: str) -> list[str]:
    stem = os.path.splitext(os.path.abspath(pyf_path))[0]
    return [os.path.abspath(pyf_path)] + [stem + ext for ext in SIDECAR_EXTS]


def capture(pyf_path: str) -> dict:
    """The figure's current state: {path: bytes or None (absent)}."""
    state = {}
    for p in _state_files(pyf_path):
        try:
            with open(p, "rb") as f:
                state[p] = f.read()
        except OSError:
            state[p] = None
    return state


def restore(state: dict) -> None:
    """Put back a state from capture(): files rewritten, files absent then
    removed."""
    for path, data in state.items():
        if data is None:
            if os.path.isfile(path):
                os.remove(path)
        else:
            from .atomic_io import write_atomic
            write_atomic(path, data)


def _digest(state: dict) -> str:
    """One fingerprint of the figure and its sidecars (a caption typed in the
    GUI changes only its sidecar)."""
    h = hashlib.sha256()
    for path in sorted(state):
        data = state[path]
        h.update(os.path.basename(path).encode("utf-8"))
        h.update(b"\0" if data is None else b"\1" + hashlib.sha256(data).digest())
    return h.hexdigest()


def _short(value):
    if isinstance(value, str) and len(value) > _MAX_ARG_CHARS:
        return value[:_MAX_ARG_CHARS] + f"… [{len(value)} characters]"
    if isinstance(value, (list, tuple)):
        return [_short(v) for v in value]
    if isinstance(value, dict):
        return {k: _short(v) for k, v in value.items()}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return repr(value)


def entries(pyf_path: str) -> list[dict]:
    """Every logged call for the figure, oldest first."""
    try:
        with open(_log_path(pyf_path), encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
    except OSError:
        return []


def _append(pyf_path: str, entry: dict) -> None:
    os.makedirs(history_dir(pyf_path), exist_ok=True)
    with open(_log_path(pyf_path), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _write_snapshot(pyf_path: str, n: int, before: dict) -> None:
    folder = os.path.join(history_dir(pyf_path), f"{n:04d}")
    os.makedirs(folder, exist_ok=True)
    manifest = {}
    for path, data in before.items():
        name = os.path.basename(path) + ".snap"
        manifest[os.path.basename(path)] = name if data is not None else None
        if data is not None:
            with open(os.path.join(folder, name), "wb") as f:
                f.write(data)
    with open(os.path.join(folder, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    _prune(pyf_path)


def _prune(pyf_path: str) -> None:
    root = history_dir(pyf_path)
    snaps = sorted(d for d in os.listdir(root) if d.isdigit() and os.path.isdir(os.path.join(root, d)))
    for d in snaps[:-MAX_SNAPSHOTS]:
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def record(pyf_path: str, tool: str, arguments: dict, result, before: dict,
           kind: str = "call", undoes: int | None = None) -> dict | None:
    """Log one call. *before* is capture() from before the call. Returns the
    entry, or None when the figure neither existed before nor after the call
    (a call on a misspelt path leaves no history folder behind)."""
    after = capture(pyf_path)
    main = os.path.abspath(pyf_path)
    if before.get(main) is None and after.get(main) is None:
        return None
    changed = any(before.get(p) != after.get(p) for p in after)
    text = result if isinstance(result, str) else json.dumps(_short(result), ensure_ascii=False)
    status = "error" if text.lstrip().startswith("ERROR") else (
        "warning" if "WARNING" in text else "ok")
    log = entries(pyf_path)
    n = (log[-1]["n"] + 1) if log else 1
    entry = {
        "n": n,
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "tool": tool,
        "arguments": _short(arguments),
        "status": status,
        "result": text[:600],
        "changed": changed,
        "after_sha256": _digest(after),
    }
    if undoes is not None:
        entry["undoes"] = undoes
    if changed:
        _write_snapshot(pyf_path, n, before)
        entry["snapshot"] = f"{n:04d}"
    _append(pyf_path, entry)
    return entry


def _undoable(log: list[dict]) -> list[dict]:
    """Changing calls not undone yet, oldest first."""
    undone = {e.get("undoes") for e in log if e.get("kind") == "undo"}
    return [e for e in log if e.get("kind") == "call" and e.get("changed")
            and e.get("snapshot") and e["n"] not in undone]


def undo_last(pyf_path: str, steps: int = 1, force: bool = False) -> str:
    """Restore the figure as it was before its last *steps* changing calls
    (each undo is itself logged). Refused, unless *force*, when the figure was
    changed since that call by something that was not logged (the GUI…)."""
    if steps < 1:
        return "ERROR: steps must be 1 or more."
    done = []
    for _ in range(steps):
        log = entries(pyf_path)
        todo = _undoable(log)
        if not todo:
            if done:
                break
            return "ERROR: nothing to undo — no logged change of this figure is left."
        last = todo[-1]
        main = os.path.abspath(pyf_path)
        current = capture(pyf_path)
        if not force and _digest(current) != last.get("after_sha256"):
            msg = (f"the figure was changed after call {last['n']} ({last['tool']}) by something "
                   f"that is not in the log (the GUI or another program); undoing would drop "
                   f"that change. Pass force=True to restore the state before call "
                   f"{last['n']} anyway.")
            return ("ERROR: " + msg) if not done else (
                f"Undid {', '.join(done)}; stopped: {msg}")
        folder = os.path.join(history_dir(pyf_path), last["snapshot"])
        try:
            with open(os.path.join(folder, "manifest.json"), encoding="utf-8") as f:
                manifest = json.load(f)
        except OSError:
            return f"ERROR: the snapshot of call {last['n']} is missing (pruned or deleted)."
        if not force and manifest.get(os.path.basename(main), "") is None:
            # the figure did not exist before that call (create_figure): undoing
            # it deletes the .pyf for good — undo_last(steps=500) did so unasked
            msg = (f"undoing call {last['n']} ({last['tool']}) would delete the figure file "
                   f"itself; pass force=True to delete it.")
            return ("ERROR: " + msg) if not done else (
                f"Undid {', '.join(done)}; stopped: {msg}")
        stem_dir = os.path.dirname(main)
        for base, snap in manifest.items():
            target = os.path.join(stem_dir, base)
            if snap is None:
                if os.path.isfile(target):
                    os.remove(target)
            else:
                from .atomic_io import write_atomic
                with open(os.path.join(folder, snap), "rb") as f:
                    write_atomic(target, f.read())
        record(pyf_path, "undo_last", {"steps": 1, "force": force},
               f"restored the figure as it was before call {last['n']} ({last['tool']})",
               current, kind="undo", undoes=last["n"])
        done.append(f"call {last['n']} ({last['tool']})")
    return f"Undid {', '.join(done)}: the figure is back to its state before them."


def describe(pyf_path: str, last: int = 20) -> str:
    """The last *last* logged calls as text, newest last."""
    log = entries(pyf_path)
    if not log:
        return f"No call history for {os.path.basename(pyf_path)} (only MCP calls are logged)."
    undone = {e.get("undoes") for e in log if e.get("kind") == "undo"}
    lines = [f"{len(log)} logged call(s) for {os.path.basename(pyf_path)}"
             f"{f' (last {last})' if len(log) > last else ''}:"]
    for e in log[-last:]:
        flags = []
        if e.get("changed"):
            flags.append("changed")
        if e["n"] in undone:
            flags.append("undone")
        if e.get("kind") == "undo":
            flags.append(f"undo of {e.get('undoes')}")
        args = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)[:60]}"
                         for k, v in (e.get("arguments") or {}).items() if k != "pyf_path")
        lines.append(f"  {e['n']:>3}  {e['time']}  {e['tool']}({args})  [{e['status']}"
                     f"{'; ' + ', '.join(flags) if flags else ''}]")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m pyfigures.history",
                                 description="List or undo the MCP calls made on a figure.")
    ap.add_argument("figure", help="the .pyf file")
    ap.add_argument("--undo", type=int, nargs="?", const=1, default=0, metavar="N",
                    help="undo the last N changing calls (default 1)")
    ap.add_argument("--force", action="store_true",
                    help="undo even if the figure was changed outside the MCP server since, "
                         "or if undoing its creation deletes the figure file")
    ap.add_argument("--last", type=int, default=20, help="number of calls listed (default 20)")
    a = ap.parse_args(argv)
    if a.undo:
        res = undo_last(a.figure, a.undo, a.force)
        print(res)
        return 1 if res.startswith("ERROR") else 0
    print(describe(a.figure, a.last))
    return 0


if __name__ == "__main__":
    sys.exit(main())
