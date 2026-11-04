"""Optional extras installed on the user's request: PyMuPDF, which keeps PDF
panels as vectors (without it a PDF page is embedded as a 600-dpi image,
see batoolset/drawings/shapes/image2d.py).

PyMuPDF is AGPL v3 (Artifex). PyFigures never ships it: it is downloaded
from PyPI only when the user agrees, so PyFigures does not distribute it and
the standalone apps stay GPL v3 only (docs/LICENSING.md).

- From pip: ``pip install pymupdf`` in the running Python.
- In a standalone app (no pip inside): the wheel for this platform and
  Python is downloaded from PyPI, its SHA-256 checked against PyPI's, and
  unpacked into a per-user folder (EXTRAS_DIR) that enable_extras() puts on
  the import path at start-up.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import subprocess
import sys
import zipfile

PYMUPDF_LICENSE = "AGPL v3 (Artifex Software)"
PYPI_JSON = "https://pypi.org/pypi/{name}/json"


def extras_dir() -> str:
    """Per-user folder for extras installed by a standalone app."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    tag = f"py{sys.version_info[0]}{sys.version_info[1]}"
    return os.path.join(base, "PyFigures", "extras", tag)


def enable_extras() -> None:
    """Put EXTRAS_DIR on the import path (standalone apps only: a pip
    install has its own site-packages)."""
    if not getattr(sys, "frozen", False):
        return
    d = extras_dir()
    if os.path.isdir(d) and d not in sys.path:
        sys.path.append(d)
        importlib.invalidate_caches()


def has_pymupdf() -> bool:
    importlib.invalidate_caches()
    try:
        import fitz  # noqa: F401
    except Exception:
        return False
    return True


def pdf_vector_note() -> str:
    """What a PDF panel becomes without PyMuPDF, for MCP and recipe replies."""
    return ("PDF pages are embedded as 600-dpi images: PyMuPDF keeps them as vectors "
            f"(pip install pymupdf — {PYMUPDF_LICENSE}; ask the user before installing it, "
            "or let them accept the offer in the PyFigures window)")


def install_pymupdf(timeout=900) -> tuple[bool, str]:
    """Install PyMuPDF; returns (ok, message)."""
    if getattr(sys, "frozen", False):
        try:
            _install_wheels("pymupdf", extras_dir(), timeout)
        except Exception as e:
            return False, str(e)
        enable_extras()
    else:
        try:
            proc = subprocess.run([sys.executable, "-m", "pip", "install", "pymupdf"],
                                  capture_output=True, text=True, timeout=timeout)
        except Exception as e:
            return False, str(e)
        if proc.returncode != 0:
            return False, (proc.stderr or proc.stdout or "pip failed").strip()[-1500:]
    if not has_pymupdf():
        return False, "PyMuPDF was installed but cannot be imported"
    return True, "PyMuPDF installed: PDF panels are now vectors."


# --------------------------------------------------------------------------
# standalone apps: wheels straight from PyPI
# --------------------------------------------------------------------------
def _supported_tags() -> list[str]:
    """Wheel tags this interpreter accepts, best first."""
    try:
        from packaging.tags import sys_tags
        return [str(t) for t in sys_tags()]
    except Exception:
        pass
    import platform
    py = f"cp{sys.version_info[0]}{sys.version_info[1]}"
    machine = platform.machine().lower()
    if sys.platform == "win32":
        plats = ["win_amd64" if machine in ("amd64", "x86_64") else "win_arm64"]
    elif sys.platform == "darwin":
        arch = "arm64" if machine == "arm64" else "x86_64"
        plats = [f"macosx_{major}_{minor}_{p}" for major in range(16, 10, -1) for minor in (0,)
                 for p in (arch, "universal2")] + [f"macosx_10_{m}_{p}" for m in range(15, 8, -1)
                                                    for p in ("x86_64", "universal2", "intel")]
    else:
        plats = [f"manylinux_2_{m}_{machine}" for m in range(40, 16, -1)] + [f"manylinux2014_{machine}"]
    tags = [f"{py}-{py}-{p}" for p in plats]
    for minor in range(sys.version_info[1], 7, -1):
        tags += [f"cp3{minor}-abi3-{p}" for p in plats]
    return tags + ["py3-none-any"]


def _wheel_tags(filename: str) -> set[str]:
    parts = filename[:-4].split("-")
    pys, abis, plats = parts[-3], parts[-2], parts[-1]
    return {f"{a}-{b}-{c}" for a in pys.split(".") for b in abis.split(".") for c in plats.split(".")}


def _pick_wheel(files: list[dict], tags: list[str]) -> dict | None:
    rank = {t: i for i, t in enumerate(tags)}
    best = None
    for f in files:
        name = f.get("filename", "")
        if not name.endswith(".whl") or f.get("yanked"):
            continue
        score = min((rank[t] for t in _wheel_tags(name) if t in rank), default=None)
        if score is not None and (best is None or score < best[0]):
            best = (score, f)
    return best[1] if best else None


def ssl_context():
    """HTTPS context with certifi's CA bundle (shipped with requests, and in
    the standalone apps). Python's default context reads the Windows
    certificate store, and one malformed certificate there makes every
    download fail ("[ASN1: NOT_ENOUGH_DATA]") — pip has its own bundle, so
    it kept working while the in-app install did not."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _fetch(url: str, timeout) -> bytes:
    from urllib.request import urlopen
    with urlopen(url, timeout=timeout, context=ssl_context()) as r:
        return r.read()


def _install_wheels(name: str, dest: str, timeout, _seen=None) -> None:
    """Download *name*'s wheel for this platform (and its required wheels)
    from PyPI into *dest*, after checking each file's SHA-256."""
    seen = _seen if _seen is not None else set()
    if name.lower() in seen:
        return
    seen.add(name.lower())
    info = json.loads(_fetch(PYPI_JSON.format(name=name), timeout))
    wheel = _pick_wheel(info.get("urls") or [], _supported_tags())
    if wheel is None:
        raise RuntimeError(f"no {name} wheel on PyPI for this platform "
                           f"({sys.platform}, Python {sys.version_info[0]}.{sys.version_info[1]})")
    data = _fetch(wheel["url"], timeout)
    want = (wheel.get("digests") or {}).get("sha256")
    if not want or hashlib.sha256(data).hexdigest() != want:
        raise RuntimeError(f"{wheel['filename']}: checksum does not match PyPI's — not installed")
    os.makedirs(dest, exist_ok=True)
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = os.path.realpath(dest)
        for member in z.namelist():
            target = os.path.realpath(os.path.join(dest, member))
            if not target.startswith(root + os.sep):
                raise RuntimeError(f"{wheel['filename']}: unsafe path {member!r}")
        z.extractall(dest)
    for req in info.get("info", {}).get("requires_dist") or []:
        if ";" in req:                        # extras and platform-specific: skipped
            continue
        dep = req.split()[0].split("[")[0]
        for ch in "<>=!~(":
            dep = dep.split(ch)[0]
        if dep:
            _install_wheels(dep, dest, timeout, seen)
