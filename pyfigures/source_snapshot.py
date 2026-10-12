"""Detect source files that changed after a figure was last saved.

PyFigures re-reads its images / CSVs from disk every time a figure is opened, so
a figure silently follows its sources: re-process an image or edit a CSV and the
"same" figure now looks different — possibly no longer matching what was
submitted. When a figure is saved, a snapshot of every source file (size,
modification time and, up to 256 MB, a SHA-256 of the content) is written beside
it as ``<figure>.sources.json``; on the next open the files are compared with
that snapshot.

A file whose modification time changed but whose content hash is identical
(copied, touched, synced) is NOT reported. No .pyf format change: figures
without a snapshot simply have nothing to compare against.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET

__all__ = ["figure_sources", "snapshot_path", "compare", "record", "compare_and_record"]

_HASH_LIMIT = 256 * 1024 * 1024
_VERSION = 1
# absolute paths written as string literals in panel scripts (merge channels,
# data-plot CSVs, kymograph / orthogonal-view stacks, user scripts)
_SCRIPT_PATH_RE = re.compile(r"""(?<![A-Za-z0-9_])([rR]?)(['"])((?:[A-Za-z]:[\\/]|/|\\\\)[^'"\n]+?)\2""")


def _script_literal(prefix, quote, body):
    """The path a string literal in a script denotes: a raw literal as
    written, a normal one unescaped the way Python reads it — so a UNC path
    keeps its leading double backslash."""
    if prefix:
        return body
    try:
        v = ast.literal_eval(quote + body + quote)
        return v if isinstance(v, str) else body
    except (ValueError, SyntaxError):
        return body


def snapshot_path(pyf_path: str) -> str:
    return os.path.splitext(pyf_path)[0] + ".sources.json"


def _decode(text):
    if text is None:
        return None
    t = text.strip()
    while len(t) >= 4 and t.startswith('""') and t.endswith('""'):
        t = t[2:-2]
    return t


def figure_sources(root_or_path) -> list[str]:
    """Absolute paths of every existing file the figure reads."""
    resolver = None
    if isinstance(root_or_path, str):
        root = ET.parse(root_or_path).getroot()
        # a figure moved with its data (other folder / disk / OS) still finds
        # its sources the way the loader does
        from pyfigures.path_resolution import PathResolver
        resolver = PathResolver(root_or_path)
    else:
        root = root_or_path
    found = []
    for img in root.iter("Image2D"):
        fn = _decode(img.findtext("filename"))
        if fn and fn not in ("None", "@template@"):
            names = [fn]
            if fn.startswith("[") and fn.endswith("]"):
                try:
                    names = [n for n in ast.literal_eval(fn) if isinstance(n, str)]
                except (ValueError, SyntaxError):
                    names = []
            found.extend(names)
        script = _decode(img.findtext("custom_loading_script"))
        if script and script != "None":
            found.extend(_script_literal(*m.groups()) for m in _SCRIPT_PATH_RE.finditer(script))
    out, seen = [], set()
    for p in found:
        if not isinstance(p, str):
            continue
        # filenames are stored verbatim: never collapse backslashes (UNC paths)
        if not os.path.isfile(p) and resolver is not None:
            p = resolver.resolve(p) or p
        if not os.path.isfile(p):
            continue
        key = os.path.normcase(os.path.abspath(p))
        if key not in seen:
            seen.add(key)
            out.append(os.path.abspath(p))
    return sorted(out, key=lambda s: os.path.normcase(s))


def _sha256(path):
    try:
        if os.path.getsize(path) > _HASH_LIMIT:
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def _read(pyf_path):
    p = snapshot_path(pyf_path)
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("files"), dict):
        return None
    return data


def _entry(path, previous=None):
    st = os.stat(path)
    if previous and previous.get("size") == st.st_size \
            and previous.get("mtime_ns") == st.st_mtime_ns and "sha256" in previous:
        digest = previous["sha256"]          # unchanged on disk: reuse the hash
    else:
        digest = _sha256(path)
    return {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": digest}


def compare(pyf_path: str, sources: list[str] | None = None) -> dict:
    """Compare the figure's current sources with its snapshot::

        {"recorded": bool, "saved": iso-time or None,
         "changed": [paths], "missing": [paths], "added": [paths], "unchanged": n}

    "missing" = recorded but no longer found; "added" = read now but not in
    the snapshot (a new panel, not a change)."""
    snap = _read(pyf_path)
    if sources is None:
        sources = figure_sources(pyf_path)
    res = {"recorded": snap is not None, "saved": snap.get("saved") if snap else None,
           "changed": [], "missing": [], "added": [], "unchanged": 0}
    if snap is None:
        return res
    rec = {os.path.normcase(k): (k, v) for k, v in snap["files"].items()}
    current = {os.path.normcase(p): p for p in sources}
    for key, p in current.items():
        if key not in rec:
            res["added"].append(p)
            continue
        old = rec[key][1]
        try:
            st = os.stat(p)
        except OSError:
            res["missing"].append(p)
            continue
        if st.st_size == old.get("size") and st.st_mtime_ns == old.get("mtime_ns"):
            res["unchanged"] += 1
            continue
        if st.st_size == old.get("size") and old.get("sha256") \
                and _sha256(p) == old["sha256"]:
            res["unchanged"] += 1           # touched / copied, same content
            continue
        res["changed"].append(p)
    for key, (p, _) in rec.items():
        if key not in current and not os.path.isfile(p):
            res["missing"].append(p)
    return res


def record(pyf_path: str, sources: list[str] | None = None) -> int:
    """Write the snapshot for the figure's current sources; returns the number
    of files recorded. Hashes of unchanged files are reused (fast re-saves)."""
    if sources is None:
        sources = figure_sources(pyf_path)
    old = (_read(pyf_path) or {}).get("files", {})
    old_n = {os.path.normcase(k): v for k, v in old.items()}
    files = {}
    for p in sources:
        try:
            files[p] = _entry(p, old_n.get(os.path.normcase(p)))
        except OSError:
            continue
    data = {"version": _VERSION, "figure": os.path.basename(pyf_path),
            "saved": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": files}
    tmp = snapshot_path(pyf_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, snapshot_path(pyf_path))
    return len(files)


def compare_and_record(pyf_path: str, root=None) -> dict:
    """compare() then record() — used on save: returns what changed since the
    previous save (so the caller can warn) and makes the current files the new
    reference."""
    sources = figure_sources(root if root is not None else pyf_path)
    res = compare(pyf_path, sources)
    record(pyf_path, sources)
    return res


def describe(res: dict, limit: int = 12) -> str:
    """Human-readable summary of a compare() result ('' if nothing to report)."""
    lines = []
    for key, title in (("changed", "changed"), ("missing", "missing")):
        items = res.get(key) or []
        if items:
            lines.append(f"{len(items)} source file(s) {title} since the figure was saved"
                         + (f" ({res['saved']})" if res.get("saved") else "") + ":")
            lines += [f"  {p}" for p in items[:limit]]
            if len(items) > limit:
                lines.append(f"  … and {len(items) - limit} more")
    return "\n".join(lines)
