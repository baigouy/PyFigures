"""Colour-vision-deficiency (CVD) simulation — see a figure as a colour-blind
reader would.

Uses the widely-cited Machado, Oliveira & Fernandes (2009) severity-1.0 sRGB
matrices for the three dichromacies. Applied directly to 8-bit sRGB — an
approximation, but the standard quick check for whether a figure's colours stay
distinguishable. Pure numpy, no Qt / matplotlib.
"""
from __future__ import annotations

import numpy as np

# 3x3 matrices, row-major, applied to sRGB [0,1] channel vectors.
CVD_MATRICES = {
    "protanopia": np.array([
        [0.152286, 1.052583, -0.204868],
        [0.114503, 0.786281, 0.099216],
        [-0.003882, -0.048116, 1.051998]]),
    "deuteranopia": np.array([
        [0.367322, 0.860646, -0.227968],
        [0.280085, 0.672501, 0.047413],
        [-0.011820, 0.042940, 0.968881]]),
    "tritanopia": np.array([
        [1.255528, -0.076749, -0.178779],
        [-0.078411, 0.930809, 0.147602],
        [0.004733, 0.691367, 0.303900]]),
}
# Friendly aliases.
_ALIASES = {
    "protan": "protanopia", "protanope": "protanopia", "red": "protanopia",
    "deuteran": "deuteranopia", "deuteranope": "deuteranopia", "green": "deuteranopia",
    "tritan": "tritanopia", "tritanope": "tritanopia", "blue": "tritanopia",
}

TYPES = tuple(CVD_MATRICES)


def resolve_type(cvd_type: str) -> str:
    """Map a user string to a canonical CVD type, or raise ValueError."""
    key = (cvd_type or "").strip().lower()
    key = _ALIASES.get(key, key)
    if key not in CVD_MATRICES:
        raise ValueError(
            f"unknown cvd_type {cvd_type!r}; use one of {', '.join(TYPES)}")
    return key


def simulate_array(rgb: np.ndarray, cvd_type: str) -> np.ndarray:
    """Return an (H,W,3) uint8 RGB array as seen under *cvd_type*.

    Accepts (H,W,3) or (H,W,4) uint8 input; any alpha channel is preserved.
    """
    cvd_type = resolve_type(cvd_type)
    m = CVD_MATRICES[cvd_type].T          # so we can right-multiply row vectors
    a = np.asarray(rgb)
    alpha = None
    if a.ndim == 3 and a.shape[2] == 4:
        alpha = a[..., 3:4]
        a = a[..., :3]
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError("expected an (H,W,3) or (H,W,4) RGB image")
    f = a.astype(np.float32) / 255.0
    out = np.clip(f.reshape(-1, 3) @ m, 0.0, 1.0).reshape(a.shape)
    out = np.rint(out * 255.0).astype(np.uint8)
    if alpha is not None:
        out = np.concatenate([out, alpha.astype(np.uint8)], axis=2)
    return out
