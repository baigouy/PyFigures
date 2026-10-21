#!/usr/bin/env python3
"""Image-integrity analysis for a PyFigures figure, run in a subprocess.

Scientific figure integrity checks that journals and readers increasingly
demand, computed straight from the panels' source pixels:

  * exact file reuse       - the same image file dropped into two panels
  * cross-panel duplication - one panel is a duplicate of another, possibly
                              flipped / rotated / contrast-inverted (a common
                              way reused blots/micrographs are disguised)
  * within-panel cloning    - a region copy-pasted elsewhere in the same panel
                              (classic copy-move retouching)

It is deliberately Qt-free (pure ElementTree + numpy + batoolset image loading)
and writes its JSON report to an explicit output file -- never to stdout, which
can be polluted by Fiji/JVM initialisation when a panel is a .zvi/.lif/etc.

    python -m pyfigures.gui.integrity_ops <fig.pyf> <report.json> [--max-dim N]
        [--hamming-threshold H] [--block B] [--min-clones C]

numpy note: this avoids matmul (np.dot/@/np.linalg) on purpose - it can crash
under numpy 2.4 BLAS on Windows. Only reductions/comparisons are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np


# --------------------------------------------------------------------------- #
# figure parsing (no Qt)
# --------------------------------------------------------------------------- #
def _decode(text):
    """Undo the light obfuscation PyFigures applies to some XML text fields."""
    if text is None:
        return None
    t = text.strip()
    # strings are saved as ""value"" (the file name of every panel)
    if t.startswith('""') and t.endswith('""') and len(t) >= 4:
        return t[2:-2]
    if t.startswith("b'") or t.startswith('b"'):
        try:
            import ast
            raw = ast.literal_eval(t)
            if isinstance(raw, (bytes, bytearray)):
                return raw.decode("utf-8", "replace")
        except Exception:
            pass
    return t


def _iter_image_elements(root):
    for img in root.iter("Image2D"):
        yield img


def collect_panels(pyf_path):
    """Return a list of dicts {index, label, file} for every real (non-template)
    image panel in the figure, with filenames resolved to absolute paths."""
    tree = ET.parse(pyf_path)
    root = tree.getroot()
    base = os.path.dirname(os.path.abspath(pyf_path))
    panels = []
    idx = 0
    for img in _iter_image_elements(root):
        fn_el = img.find("filename")
        fn = _decode(fn_el.text) if fn_el is not None else None
        if not fn or fn in ("@template@", "None"):
            # "None": a data plot (drawn by its script) or an empty padding panel,
            # not an image file ("file not found" was reported for them)
            continue
        # letter label if the panel carries one (first is_letter annotation)
        label = None
        annots = img.find("annotations")
        if annots is not None:
            for a in annots.iter("TAText2D"):
                il = a.find("is_letter")
                tx = a.find("text")
                if il is not None and (il.text or "").strip() in ("True", "b'True'") \
                        and tx is not None and tx.text:
                    label = _decode(tx.text)
                    break
        path = fn if os.path.isabs(fn) else os.path.join(base, fn)
        panels.append({"index": idx, "label": label, "file": path,
                       "exists": os.path.isfile(path)})
        idx += 1
    return panels


# --------------------------------------------------------------------------- #
# pixel loading / normalisation
# --------------------------------------------------------------------------- #
def _to_gray2d(arr):
    """Reduce an arbitrary-rank image array to a single 2-D float32 plane:
    stacks are max-projected, colour channels averaged."""
    a = np.asarray(arr)
    if a.ndim <= 1:
        return None
    # collapse a trailing colour axis (3 or 4) by averaging
    if a.ndim >= 3 and a.shape[-1] in (2, 3, 4):
        a = a.mean(axis=-1)
    # max-project any remaining leading axes (z / t stacks)
    while a.ndim > 2:
        a = a.max(axis=0)
    return a.astype(np.float32, copy=False)


def _normalize(g):
    g = g.astype(np.float32, copy=False)
    mn = float(g.min())
    mx = float(g.max())
    if mx <= mn:
        return np.zeros_like(g)
    return (g - mn) / (mx - mn)


def _resize(g, w, h):
    """Nearest/area resize without cv2 matmul; uses cv2 if present else striding."""
    try:
        import cv2
        interp = cv2.INTER_AREA if (g.shape[1] > w or g.shape[0] > h) else cv2.INTER_LINEAR
        return cv2.resize(g, (w, h), interpolation=interp)
    except Exception:
        ys = (np.linspace(0, g.shape[0] - 1, h)).astype(np.int64)
        xs = (np.linspace(0, g.shape[1] - 1, w)).astype(np.int64)
        return g[ys][:, xs]


def load_gray(path, max_dim):
    """Load an image file to a normalised 2-D float32 array capped at max_dim."""
    from batoolset.img import Img
    arr = Img(path)
    g = _to_gray2d(arr)
    if g is None or g.size == 0:
        raise ValueError("could not reduce image to a 2-D plane")
    h, w = g.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        g = _resize(g, max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return _normalize(g), (int(h), int(w))


# --------------------------------------------------------------------------- #
# perceptual hashing (dHash) + oriented variants
# --------------------------------------------------------------------------- #
def _dhash(g, hash_size=8):
    """64-bit difference hash: resize to (hash_size+1 x hash_size), compare
    horizontally-adjacent pixels. Robust to brightness/contrast and scaling."""
    small = _resize(g, hash_size + 1, hash_size)
    diff = small[:, 1:] > small[:, :-1]
    bits = 0
    for v in diff.flatten():
        bits = (bits << 1) | int(bool(v))
    return bits


_VARIANTS = ["identity", "fliplr", "flipud", "rot90", "rot180", "rot270", "invert"]


def _variant(g, name):
    if name == "identity":
        return g
    if name == "fliplr":
        return np.fliplr(g)
    if name == "flipud":
        return np.flipud(g)
    if name == "rot90":
        return np.rot90(g, 1)
    if name == "rot180":
        return np.rot90(g, 2)
    if name == "rot270":
        return np.rot90(g, 3)
    if name == "invert":
        return 1.0 - g
    return g


def variant_hashes(g):
    return {name: _dhash(_variant(g, name)) for name in _VARIANTS}


def _hamming(a, b):
    return bin(a ^ b).count("1")


# --------------------------------------------------------------------------- #
# within-panel copy-move (block hashing)
# --------------------------------------------------------------------------- #
def within_panel_clones(g, block=24, min_std=0.04, min_clones=3, max_report=8,
                        search_max=384, min_corr=0.99, max_checks=200000):
    """Find non-adjacent, textured regions whose signature is identical - the
    fingerprint of copy-move retouching. Uses stride-1 sliding windows (so a
    pasted region is caught at *any* offset, not just grid-aligned ones) with a
    cheap 8x8 signature, fully vectorised. A signature only says two blocks have
    the same light/dark pattern (any two similar edges do), so each candidate
    pair is then confirmed on the pixels themselves: the two blocks' Pearson
    correlation must be >= *min_corr*.
    Returns (count, sample_pairs)."""
    g = np.ascontiguousarray(g, dtype=np.float32)
    h, w = g.shape[:2]
    if max(h, w) > search_max:          # bound cost on large panels
        g = _resize(g, max(1, int(round(w * search_max / max(h, w)))),
                    max(1, int(round(h * search_max / max(h, w)))))
        g = np.ascontiguousarray(g, dtype=np.float32)
        h, w = g.shape[:2]
    if h < block * 2 or w < block * 2:
        return 0, []

    from numpy.lib.stride_tricks import sliding_window_view
    win = sliding_window_view(g, (block, block))         # (H-B+1, W-B+1, B, B)
    ph, pw = win.shape[0], win.shape[1]
    sub = win[:, :, ::max(1, block // 8), ::max(1, block // 8)]
    sub = sub[:, :, :8, :8]                              # 8x8 per-block thumbnail
    means = sub.mean(axis=(2, 3), keepdims=True)
    bits = (sub > means).reshape(ph, pw, 64)
    packed = np.packbits(bits, axis=2)                   # (ph, pw, 8) uint8 signature
    stds = win.std(axis=(2, 3))

    flat = packed.reshape(-1, packed.shape[2])
    textured = stds.reshape(-1) >= min_std
    keep = np.nonzero(textured)[0]
    if keep.size < 2:
        return 0, []
    sigs = np.ascontiguousarray(flat[keep])
    sv = sigs.view(np.dtype((np.void, sigs.dtype.itemsize * sigs.shape[1]))).reshape(-1)
    _uniq, inv, counts = np.unique(sv, return_inverse=True, return_counts=True)

    pairs = []
    checks = 0
    inv = inv.reshape(-1)
    for grp in np.nonzero(counts > 1)[0]:
        members = keep[np.nonzero(inv == grp)[0]]
        pts = [(int(m % pw), int(m // pw)) for m in members]   # (x, y)
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                (x1, y1), (x2, y2) = pts[i], pts[j]
                if abs(x1 - x2) < block and abs(y1 - y2) < block:
                    continue                                    # overlapping - not a clone
                checks += 1
                if checks > max_checks:                         # safety cap on cost
                    break
                # a copy stays near-perfectly correlated with its source even
                # after the panel was resampled; similar textures (fibres,
                # edges) share the signature but correlate far less (~0.9)
                a = win[y1, x1].ravel() - win[y1, x1].mean()
                b = win[y2, x2].ravel() - win[y2, x2].mean()
                den = float(np.sqrt(float(np.einsum('i,i->', a, a)) * float(np.einsum('i,i->', b, b))))
                if den <= 0 or float(np.einsum('i,i->', a, b)) / den < min_corr:
                    continue                                    # same pattern, different pixels
                pairs.append(((x1, y1), (x2, y2)))
                if len(pairs) > 5000:                           # safety cap
                    break
            if checks > max_checks or len(pairs) > 5000:
                break
        if checks > max_checks or len(pairs) > 5000:
            break
    if len(pairs) < min_clones:
        return 0, []
    return len(pairs), pairs[:max_report]


# --------------------------------------------------------------------------- #
# main analysis
# --------------------------------------------------------------------------- #
def analyze(pyf_path, max_dim=512, hamming_threshold=6, block=24, min_clones=3):
    panels = collect_panels(pyf_path)
    grays = {}
    hashes = {}
    file_sha = {}
    load_errors = []
    for p in panels:
        i = p["index"]
        if not p["exists"]:
            load_errors.append({"index": i, "file": p["file"], "error": "file not found"})
            continue
        try:
            with open(p["file"], "rb") as fh:
                file_sha[i] = hashlib.sha1(fh.read()).hexdigest()
        except Exception:
            file_sha[i] = None
        try:
            g, shape = load_gray(p["file"], max_dim)
            grays[i] = g
            hashes[i] = variant_hashes(g)
            p["shape"] = shape
        except Exception as e:
            load_errors.append({"index": i, "file": p["file"],
                                "error": f"{type(e).__name__}: {e}"})

    idxs = sorted(grays.keys())

    # exact file reuse (identical bytes) -- distinct from perceptual duplication
    exact = []
    for a_i in range(len(idxs)):
        for b_i in range(a_i + 1, len(idxs)):
            i, j = idxs[a_i], idxs[b_i]
            si, sj = file_sha.get(i), file_sha.get(j)
            same_path = os.path.normcase(panels[i]["file"]) == os.path.normcase(panels[j]["file"])
            if same_path or (si is not None and si == sj):
                exact.append({"a": i, "b": j,
                              "a_label": panels[i]["label"], "b_label": panels[j]["label"],
                              "a_file": os.path.basename(panels[i]["file"]),
                              "b_file": os.path.basename(panels[j]["file"]),
                              "reason": "same file path" if same_path else "identical file bytes"})

    exact_pairs = {(e["a"], e["b"]) for e in exact}

    # cross-panel perceptual duplication (best over oriented variants)
    cross = []
    for a_i in range(len(idxs)):
        for b_i in range(a_i + 1, len(idxs)):
            i, j = idxs[a_i], idxs[b_i]
            if (i, j) in exact_pairs:
                continue  # already reported as an exact reuse
            hi = hashes[i]["identity"]
            best_sim = -1.0
            best_tf = None
            for tf in _VARIANTS:
                d = _hamming(hi, hashes[j][tf])
                sim = 1.0 - d / 64.0
                if sim > best_sim:
                    best_sim, best_tf = sim, tf
                    best_d = d
            if best_d <= hamming_threshold:
                cross.append({
                    "a": i, "b": j,
                    "a_label": panels[i]["label"], "b_label": panels[j]["label"],
                    "a_file": os.path.basename(panels[i]["file"]),
                    "b_file": os.path.basename(panels[j]["file"]),
                    "similarity": round(best_sim, 4),
                    "hamming": int(best_d),
                    "transform": "same orientation" if best_tf == "identity" else best_tf,
                })
    cross.sort(key=lambda c: -c["similarity"])

    # within-panel copy-move
    clones = []
    for i in idxs:
        cnt, samples = within_panel_clones(grays[i], block=block, min_clones=min_clones)
        if cnt:
            clones.append({"panel": i, "label": panels[i]["label"],
                           "file": os.path.basename(panels[i]["file"]),
                           "clone_block_pairs": cnt,
                           "example_regions": [{"from": list(a), "to": list(b),
                                                "block": block} for a, b in samples]})

    flag_count = len(exact) + len(cross) + len(clones)
    parts = []
    if exact:
        parts.append(f"{len(exact)} exact file reuse")
    if cross:
        parts.append(f"{len(cross)} cross-panel duplicate(s)")
    if clones:
        parts.append(f"{len(clones)} panel(s) with internal cloning")
    if load_errors:
        parts.append(f"{len(load_errors)} panel(s) could not be analysed")
    summary = ("No integrity issues detected across "
               f"{len(idxs)} analysed panel(s)." if flag_count == 0
               else "Potential issues: " + "; ".join(parts) +
                    ". Review flagged panels; a match may be legitimate "
                    "(e.g. an intentional inset or loading control).")

    return {
        "panels_analyzed": len(idxs),
        "panels_total": len(panels),
        "exact_file_duplicates": exact,
        "cross_panel_duplicates": cross,
        "within_panel_clones": clones,
        "load_errors": load_errors,
        "flag_count": flag_count,
        "settings": {"max_dim": max_dim, "hamming_threshold": hamming_threshold,
                     "block": block, "min_clones": min_clones},
        "summary": summary,
    }


def _main(argv=None):
    ap = argparse.ArgumentParser(description="PyFigures image-integrity analysis.")
    ap.add_argument("pyf_path")
    ap.add_argument("out_json")
    ap.add_argument("--max-dim", type=int, default=512)
    ap.add_argument("--hamming-threshold", type=int, default=6)
    ap.add_argument("--block", type=int, default=24)
    ap.add_argument("--min-clones", type=int, default=3)
    args = ap.parse_args(argv)
    if not os.path.isfile(args.pyf_path):
        sys.stderr.write(f"ERROR: no such .pyf file: {args.pyf_path}\n")
        return 1
    try:
        report = analyze(args.pyf_path, max_dim=args.max_dim,
                         hamming_threshold=args.hamming_threshold,
                         block=args.block, min_clones=args.min_clones)
    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        return 1
    with open(args.out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
