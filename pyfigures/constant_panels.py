"""Panels and channels holding a single value everywhere (all black, all
white, a constant negative): an RGB file with content in two channels gave a
black panel for the third when split. Shared by the channel splits (GUI and
MCP), which leave such channels out, and by QC, which lists such panels.
"""
from __future__ import annotations

import os

import numpy as np


def constant_free_channels(data) -> list:
    """Indices of the channels (last axis) of *data* that are not one value
    everywhere (over every plane of a stack). All of them when every channel
    is constant (nothing to choose from)."""
    arr = np.asarray(data)
    n = arr.shape[-1]
    flat = arr.reshape(-1, n)
    kept = [c for c in range(n) if flat[:, c].min() != flat[:, c].max()]
    return kept or list(range(n))


def constant_value(data):
    """The single value of *data*, or None when it has more than one."""
    arr = np.asarray(data)
    if arr.size == 0:
        return None
    lo = arr.min()
    return lo.item() if lo == arr.max() else None


def _channels_shown(img_el):
    """The channel mask of a panel (None: all channels)."""
    import ast
    from pyfigures.mcp_tools.core import _decode
    text = _decode(img_el.findtext("channels"))
    if not isinstance(text, str):
        return list(text) if isinstance(text, (list, tuple)) else None
    if not text or text in ("None", ""):
        return None
    try:
        mask = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return None
    return list(mask) if isinstance(mask, (list, tuple)) else None


def constant_panel_value(path, channels=None, cache=None):
    """The single value shown by a panel of image *path* (restricted to the
    channels with a True in *channels*), or None when it is not constant or
    cannot be read. Stacks count as constant only when every plane is."""
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    key = path
    if cache is not None and key in cache:
        data = cache[key]
    else:
        try:
            from batoolset.img import Img
            data = np.asarray(Img(path))
        except Exception:
            data = None
        if cache is not None:
            cache[key] = data
    if data is None:
        return None
    try:
        from batoolset.img import guess_dimensions
        dims = guess_dimensions(data) or ""
    except Exception:
        dims = ""
    if channels and dims.endswith("c") and len(channels) == data.shape[-1]:
        sel = [i for i, on in enumerate(channels) if on]
        if sel:
            data = data[..., sel]
    return constant_value(data)
