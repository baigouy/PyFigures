"""Find the source files of a figure that was moved to another folder, disk or OS.

A .pyf stores absolute paths (``/home/me/Bureau/exp/a.tif``). When the figure
and its data are copied elsewhere (``C:/Users/me/Desktop/exp/a.tif``) the stored
path no longer exists. Instead of requiring a manual remap, a missing path is
looked up *relative to where the .pyf now is*: the longest trailing part of the
old path (``exp/a.tif``, then ``a.tif`` …) is tried under the .pyf's folder and
its parent folders. The prefix swap that worked (``/home/me/Bureau/`` ->
``C:/Users/me/Desktop/``) is remembered, so the other panels resolve instantly.

Works in both directions (Linux <-> Windows) and needs no change to the file
format — older PyFigures versions read the files exactly as before. Paths inside
panel scripts (channel merges, data plots) are resolved too.

UI-free: used by the GUI loader and the MCP server.
"""
from __future__ import annotations

import ast
import io
import os
import re
import tokenize
import xml.etree.ElementTree as ET

_MAX_ANCESTORS = 6          # how far up from the .pyf folder to look
_SEP_RE = re.compile(r"[\\/]+")


def _parts(path: str) -> list[str]:
    """Path components without the drive / root (works for both OS styles)."""
    p = path.strip()
    p = re.sub(r"^[A-Za-z]:", "", p)          # drop a Windows drive
    return [c for c in _SEP_RE.split(p) if c not in ("", ".")]


def is_remote(path) -> bool:
    """True for an http(s) URL (e.g. an OME-Zarr image on a server)."""
    return isinstance(path, str) and bool(re.match(r"^https?://", path.strip(), re.I))


def source_exists(path) -> bool:
    """True when *path* is an image source PyFigures can read: an existing file,
    a local .zarr store (a folder) or a remote URL (checked when it is read)."""
    if not isinstance(path, str) or not path.strip():
        return False
    if is_remote(path):
        return True
    p = path.split("#", 1)[0]
    if p.rstrip("/\\").lower().endswith(".zarr"):
        return os.path.isdir(p)
    return os.path.isfile(path)


def _looks_absolute(path: str) -> bool:
    return bool(re.match(r"^([A-Za-z]:[\\/]|/|\\\\)", path.strip()))


def _norm(p: str) -> str:
    return p.replace("\\", "/")


class PathResolver:
    """Resolves missing absolute paths for one figure (learns prefix swaps)."""

    def __init__(self, pyf_path: str):
        self.pyf_dir = os.path.dirname(os.path.abspath(pyf_path))
        self.bundle_dir = os.path.splitext(os.path.abspath(pyf_path))[0] + ".files"
        self.ancestors = []
        d = self.pyf_dir
        for _ in range(_MAX_ANCESTORS):
            self.ancestors.append(d)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
        self.learned: list[tuple[str, str]] = []   # (old_prefix, new_prefix)
        self.resolved: dict[str, str] = {}
        self.unresolved: set[str] = set()

    def resolve(self, path: str) -> str | None:
        """New location of *path*, or None if it exists already / can't be found."""
        if not isinstance(path, str) or not path.strip() or not _looks_absolute(path):
            return None
        if path in self.resolved:
            return self.resolved[path]
        if path in self.unresolved or os.path.exists(path):
            return None
        found = self._from_learned(path) or self._search(path)
        if found:
            self.resolved[path] = found
        else:
            self.unresolved.add(path)
        return found

    def _from_learned(self, path):
        np_ = _norm(path)
        for old, new in self.learned:
            if np_.startswith(old):
                cand = new + np_[len(old):]
                if os.path.exists(cand):
                    return cand
        return None

    def _search(self, path):
        parts = _parts(path)
        if not parts:
            return None
        # longest trailing part first; a bare file name only next to the .pyf
        # or in its consolidation bundle (too ambiguous further up)
        for n in range(len(parts), 0, -1):
            tail = parts[-n:]
            bases = self.ancestors if n >= 2 else [self.pyf_dir, self.bundle_dir]
            for base in bases:
                cand = os.path.join(base, *tail)
                if os.path.exists(cand):
                    self._learn(path, cand, n)
                    return _norm(cand)
        return None

    def _learn(self, old_path, new_path, n_tail):
        old_parts = _norm(old_path).split("/")
        new_parts = _norm(new_path).split("/")
        if n_tail >= len(old_parts) or n_tail >= len(new_parts):
            return
        old_prefix = "/".join(old_parts[:-n_tail]) + "/"
        new_prefix = "/".join(new_parts[:-n_tail]) + "/"
        if (old_prefix, new_prefix) not in self.learned:
            self.learned.append((old_prefix, new_prefix))

    # ---- file-name fields and scripts -------------------------------------
    def resolve_filename_field(self, text: str) -> str:
        """Resolve a serialized <filename> value (``""path""`` or a list)."""
        if text is None:
            return text
        raw = text.strip()
        wrapped = raw.startswith('""') and raw.endswith('""') and len(raw) >= 4
        inner = raw[2:-2] if wrapped else raw
        if inner.startswith("[") and inner.endswith("]"):
            try:
                lst = ast.literal_eval(inner)
            except Exception:
                return text
            if not isinstance(lst, list):
                return text
            changed = False
            out = []
            for p in lst:
                new = self.resolve(p) if isinstance(p, str) else None
                out.append(new or p)
                changed = changed or bool(new)
            if not changed:
                return text
            inner_new = repr(out)
        else:
            new = self.resolve(inner)
            if not new:
                return text
            inner_new = new
        return f'""{inner_new}""' if wrapped else inner_new

    def resolve_script(self, script: str) -> str:
        """Rewrite absolute path string literals in a panel script."""
        if not script or script in ("None",):
            return script
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(script).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return script
        lines = script.splitlines(keepends=True)
        offsets = [0]
        for ln in lines:
            offsets.append(offsets[-1] + len(ln))
        edits = []
        for t in toks:
            if t.type != tokenize.STRING:
                continue
            try:
                val = ast.literal_eval(t.string)
            except Exception:
                continue
            if isinstance(val, str):
                new = self.resolve(val)
                if new:
                    a = offsets[t.start[0] - 1] + t.start[1]
                    b = offsets[t.end[0] - 1] + t.end[1]
                    edits.append((a, b, repr(new)))
        for a, b, rep in reversed(edits):
            script = script[:a] + rep + script[b:]
        return script


def resolve_moved_paths_in_tree(root: ET.Element, pyf_path: str) -> dict[str, str]:
    """Resolve missing source paths in a parsed figure in place.
    Returns {old_path: new_path} for every path that was relocated."""
    r = PathResolver(pyf_path)
    for img in root.iter("Image2D"):
        fn = img.find("filename")
        if fn is not None and fn.text:
            fn.text = r.resolve_filename_field(fn.text)
        sc = img.find("custom_loading_script")
        if sc is not None and sc.text and sc.text.strip() not in ("None", ""):
            raw = sc.text
            wrapped = raw.startswith('""') and raw.endswith('""') and len(raw) >= 4
            inner = raw[2:-2] if wrapped else raw
            new_inner = r.resolve_script(inner)
            if new_inner != inner:
                sc.text = f'""{new_inner}""' if wrapped else new_inner
    return dict(r.resolved)


def resolve_moved_paths(xml_string: str, pyf_path: str) -> tuple[str, dict[str, str]]:
    """String-level variant for loaders that work on the raw .pyf text.
    Returns (xml_string, {old: new}); the text is unchanged if nothing moved or
    the XML can't be parsed (malformed files are left to the loader's repair)."""
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError:
        return xml_string, {}
    moved = resolve_moved_paths_in_tree(root, pyf_path)
    if not moved:
        return xml_string, {}
    return ET.tostring(root, encoding="unicode"), moved
