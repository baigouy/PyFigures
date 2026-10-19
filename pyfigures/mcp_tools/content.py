"""PyFigures MCP tools — Generated panel content: channel merges, data plots, flip/rotate transforms, LUTs, image configuration.

Split out of pyfigures/mcp_server.py (which re-exports every name and
remains the server entry point: ``python -m pyfigures.mcp_server``).
"""
from __future__ import annotations

import fnmatch
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from textwrap import indent
from mcp.server.fastmcp import FastMCP, Image
from .app import (
    mcp,
)
from .core import (
    _append_image,
    _append_stats_entry,
    _child_text,
    _channel_count_from_file,
    _color_to_int,
    _crop_fit_error,
    _raw_size_from_file,
    _encode_str,
    _first_filename,
    _get_container,
    _load,
    _new_image2d,
    _new_tatext2d,
    _save,
    _set_child_text,
)

_DEFAULT_MERGE_COLORS = {
    1: ["gray"],
    2: ["green", "magenta"],          # colour-blind-safe default pair
    3: ["red", "green", "blue"],
    4: ["red", "green", "blue", "gray"],
}


_MERGE_MARKER = "# pyfigures:channel_merge"
_MERGE_NORMALIZATIONS = ("per_channel", "none")


def _make_channel_merge_script(files: list[str], colors_rgb: list[tuple],
                               mode: str, normalization: str = "per_channel") -> str:
    """Return a custom_loading_script that loads each channel file, tints it with
    its RGB colour and combines them into one composite (additive or max).

    *normalization*: "per_channel" linearly stretches each channel to its own
    min..max (brightest pixel = full colour); "none" keeps raw intensities,
    scaled only by the file's bit depth (uint8 /255, uint16 /65535). The choice
    is written in a marker comment so export_adjustment_ledger can disclose it."""
    files_lit = "[" + ", ".join(repr(f) for f in files) + "]"
    colors_lit = "[" + ", ".join(repr(tuple(float(v) for v in c)) for c in colors_rgb) + "]"
    # NB: no nested def()s — PyFigures exec's scripts with split globals/locals,
    # so a nested function cannot see top-level imports (name 'np' not defined).
    return f"""\
{_MERGE_MARKER} mode={mode} normalization={normalization}
import numpy as np
_files = {files_lit}
_colors = {colors_lit}
_mode = {mode!r}
_norm = {normalization!r}

_grays = []
for _p in _files:
    try:
        import tifffile as _tf
        _a = _tf.imread(_p)
    except Exception:
        from PIL import Image as _PI
        _a = np.array(_PI.open(_p))
    _a = np.asarray(_a)
    _full = float(np.iinfo(_a.dtype).max) if np.issubdtype(_a.dtype, np.integer) else 1.0
    _a = _a.astype(np.float64)
    if _a.ndim >= 3 and _a.shape[-1] in (2, 3, 4):
        _a = _a[..., :3].mean(axis=-1)
    while _a.ndim > 2:
        _a = _a.max(axis=0)
    if _norm == "none":
        _grays.append(np.clip(_a / _full, 0.0, 1.0))
    else:
        _mn, _mx = float(_a.min()), float(_a.max())
        _grays.append((_a - _mn) / (_mx - _mn) if _mx > _mn else np.zeros_like(_a))

_H, _W = _grays[0].shape
comp = np.zeros((_H, _W, 3), dtype=np.float64)
for _g, _c in zip(_grays, _colors):
    if _g.shape != (_H, _W):
        _ys = np.linspace(0, _g.shape[0] - 1, _H).astype(np.int64)
        _xs = np.linspace(0, _g.shape[1] - 1, _W).astype(np.int64)
        _g = _g[_ys][:, _xs]
    _t = np.stack([_g * _c[0], _g * _c[1], _g * _c[2]], axis=-1)
    comp = np.maximum(comp, _t) if _mode == "max" else comp + _t
comp = np.clip(comp, 0.0, 1.0)

# figure shaped exactly like the image (1 figure px per image px), no margin:
# a default 4:3 figure made square images come out stretched
fig = plt.figure(figsize=(_W / 100.0, _H / 100.0), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.imshow(comp, interpolation='none', aspect='equal')
ax.axis('off')
fig._pyfigures_pad_inches = 0
fig._pyfigures_image_panel = True
self.img = fig
"""


def _parse_channel_merge_script(script) -> dict | None:
    """If *script* is exactly a channel-merge script produced by
    _make_channel_merge_script, return {files, colors, mode, normalization};
    otherwise None. The script is regenerated from its parsed parameters and
    compared byte-for-byte, so a hand-edited script is NOT recognised (and the
    adjustment ledger then flags it as a custom script)."""
    import ast
    if not isinstance(script, str) or not script.startswith(_MERGE_MARKER):
        return None
    try:
        m = re.search(r"^_files = (.*)$", script, re.M)
        c = re.search(r"^_colors = (.*)$", script, re.M)
        md = re.search(r"^_mode = (.*)$", script, re.M)
        nm = re.search(r"^_norm = (.*)$", script, re.M)
        files = ast.literal_eval(m.group(1))
        colors = ast.literal_eval(c.group(1))
        mode = ast.literal_eval(md.group(1))
        norm = ast.literal_eval(nm.group(1))
    except Exception:
        return None
    if _make_channel_merge_script(files, colors, mode, norm) != script:
        return None
    return {"files": list(files), "colors": list(colors), "mode": mode,
            "normalization": norm}


@mcp.tool()
def add_channel_merge(
    pyf_path: str,
    group_path: list[int],
    channel_files: list[str],
    colors: list[str] | None = None,
    mode: str = "sum",
    label: str | None = None,
    label_placement: str = "top left",
    normalization: str = "per_channel",
) -> str:
    """Add a multi-channel *merge / composite* panel — the microscopy staple of
    overlaying several single-channel images (e.g. DAPI + GFP + RFP) into one
    pseudo-coloured RGB image.

    Each channel file is tinted with its colour and combined. The panel is a
    scripted Image2D, so it re-renders from the source files whenever the figure
    is opened (no baked-in bitmap).

    *normalization*: "per_channel" (default) linearly stretches each channel to
    its own min..max — a brightness/contrast adjustment that
    export_adjustment_ledger discloses; "none" keeps raw intensities (scaled
    only by bit depth), e.g. to compare intensities across merges.

    *channel_files*: absolute paths to the single-channel images (2-4 typical).
    *colors*: one colour per channel (name/#rrggbb/int). Default is colour-blind
    friendlier: 1→gray, 2→green+magenta, 3→red+green+blue.
    *mode*: "sum" (additive, clipped — classic fluorescence merge) or "max"
    (per-pixel maximum — avoids saturation where channels overlap).
    *label*: optional panel label (e.g. "Merge").

    Example — GFP (green) + RFP (magenta) merge::

        add_channel_merge("fig.pyf", [0], ["/d/gfp.tif", "/d/rfp.tif"],
                          colors=["green", "magenta"], label="Merge")
    """
    if mode not in ("sum", "max"):
        return (f"ERROR: mode must be 'sum' (additive blend) or 'max' (brightest channel "
                f"wins), not {mode!r}; channel colours go in 'colors'.")
    if normalization not in _MERGE_NORMALIZATIONS:
        return "ERROR: normalization must be 'per_channel' or 'none'."
    if not channel_files or len(channel_files) < 1:
        return "ERROR: provide at least one channel file."
    from pyfigures.path_resolution import source_exists
    missing = [f for f in channel_files if not source_exists(f)]
    if missing:
        return "ERROR: channel file(s) not found: " + ", ".join(missing)

    n = len(channel_files)
    if colors is None:
        colors = _DEFAULT_MERGE_COLORS.get(n, ["red", "green", "blue", "gray"] * n)[:n]
    if len(colors) != n:
        return f"ERROR: got {len(colors)} colors for {n} channels — counts must match."
    try:
        colors_rgb = []
        for c in colors:
            ci = _color_to_int(c)
            colors_rgb.append(((ci >> 16 & 0xFF) / 255., (ci >> 8 & 0xFF) / 255.,
                               (ci & 0xFF) / 255.))
    except ValueError as e:
        return f"ERROR: {e}"

    script = _make_channel_merge_script([os.path.abspath(f) for f in channel_files],
                                        colors_rgb, mode, normalization)

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__channel_merge__")
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    if label:
        # white: a merge is a dark fluorescence image (default text is black)
        img.find("annotations").append(_new_tatext2d(label, label_placement,
                                                     color=0xFFFFFF))
    _append_image(container, img, is_root=(not group_path))
    _save(tree, pyf_path, recompute=True)

    idx = len([c for c in container if c.tag == "Image2D"]) - 1
    loc = "canvas" if not group_path else f"group {group_path}"
    pairs = ", ".join(f"{os.path.basename(f)}→{c}" for f, c in zip(channel_files, colors))
    # a merge of one RGB file three times (a local model's way of asking for a
    # magenta/green merge) shows nothing useful: say so
    warnings = []
    if len({os.path.abspath(f) for f in channel_files}) < n:
        warnings.append("the same file is used for several channels")
    multi = [os.path.basename(f) for f in channel_files if (_channel_count_from_file(f) or 1) > 1]
    if multi:
        warnings.append(f"{', '.join(multi)} already has several colour channels (a merge "
                        f"expects one single-channel image per channel); to show or recolour "
                        f"the channels of one image use add_channel_split (recipe: split: with "
                        f"colors / merge: true)")
    sizes = {os.path.basename(f): _raw_size_from_file(f) for f in channel_files}
    known = {s for s in sizes.values() if s}
    if len(known) > 1:
        warnings.append("the channel files differ in size ("
                        + ", ".join(f"{k} {s[0]}×{s[1]}" for k, s in sizes.items() if s)
                        + "): they are stretched to the first one's size, so the channels "
                        "are probably not aligned")
    # on lines of their own, so recipes (and the GUI) report them
    warning = "".join(f"\nWARNING: {w}." for w in warnings)
    return (
        f"Channel-merge panel added as index {idx} in {loc} ({n} channels, {mode}): "
        f"{pairs}. Reopen the figure in PyFigures to render it.{warning}"
    )


_DATA_PLOT_KINDS = ("bar", "box", "violin", "scatter", "grouped")


def _make_data_plot_script(csv_path: str, kind: str, error: str, annotate: bool,
                           only_significant: bool, title: str, ylabel: str,
                           xlabel: str, stats_mode: str = "auto", latex: bool = False) -> str:
    """Return a custom_loading_script that renders a data-plot panel from a CSV
    via staplot's UI-free api. Soft dependency: if staplot is not importable the
    panel shows an install hint instead of crashing the figure. The panel is
    *live* — editing the CSV and reopening re-renders (and re-runs the stats).

    NB: no nested def()s — PyFigures exec's scripts with split globals/locals, so
    a nested function cannot see top-level imports (name 'np' not defined)."""
    builder = "grouped_table_from_csv" if kind == "grouped" else "table_from_csv"
    return f"""\
import numpy as np
_csv = {csv_path!r}
try:
    from staplot import api as _api
except Exception as _e:
    fig, ax = plt.subplots(figsize=(4.0, 2.2))
    ax.axis('off')
    ax.text(0.5, 0.5,
            'Data-plot panel needs the "staplot" package.\\n'
            'Install it (pip install staplot) and reopen.\\n\\n' + repr(_e),
            ha='center', va='center', fontsize=8, wrap=True)
    self.img = fig
else:
    import matplotlib as _mpl
    _rc = {{}}
    if {bool(latex)!r}:
        # every text typeset by LaTeX (when installed): the plot keeps its settings,
        # applied again whenever it is rendered (Image2D._toBuffer)
        try:
            from batoolset.latex_tools import matplotlib_rc as _latex_rc
            _rc = _latex_rc()
        except Exception:
            _rc = {{}}
    _tbl = _api.{builder}(_csv)
    with _mpl.rc_context(_rc):
        fig, _rec = _api.plot(_tbl, kind={kind!r}, error={error!r},
                              annotate={bool(annotate)!r},
                              only_significant={bool(only_significant)!r},
                              stats_mode={stats_mode!r},
                              title={title!r}, ylabel={ylabel!r}, xlabel={xlabel!r})
    fig._pyf_rc = _rc
    self.img = fig
"""


def _csv_number_count(path: str) -> int:
    """How many finite numbers a CSV holds (0 for an empty file or a header
    alone: the plot would be an empty frame)."""
    import csv
    n = 0
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            for row in csv.reader(f, dialect):
                for cell in row:
                    try:
                        v = float(cell)
                    except ValueError:
                        continue
                    if math.isfinite(v):
                        n += 1
    except OSError:
        return 0
    return n


@mcp.tool()
def add_data_plot(
    pyf_path: str,
    group_path: list[int],
    csv_path: str,
    kind: str = "bar",
    error: str = "sem",
    annotate_stats: bool = True,
    only_significant: bool = True,
    label: str | None = None,
    label_placement: str = "top left",
    title: str = "",
    ylabel: str = "",
    xlabel: str = "",
    stats_mode: str = "auto",
    latex: bool = False,
) -> str:
    """Add a **data-plot panel** rendered from a CSV of measurements — a real
    statistical chart (bar / box / violin / scatter / grouped bar) as a figure
    panel, with automatic significance brackets.

    This turns PyFigures into a complete figure tool: instead of pasting a chart
    exported from elsewhere, drop a CSV and get a publication-styled plot that
    stays **live** — edit the CSV, reopen the figure, and the plot (and its
    statistics) re-render. Rendering + stats are provided by the ``staplot``
    package (a soft dependency); if it isn't installed the panel shows an install
    hint instead of failing.

    *csv_path*: a CSV of the data.
      - bar/box/violin/scatter: **wide** (one column per group, rows = replicates)
        or **long** (2 columns: group label, value).
      - grouped: **long** with 3 columns: factor_a, factor_b, value.
    *kind*: "bar" | "box" | "violin" | "scatter" | "grouped".
    *error*: error-bar type for bar/grouped — "sem" | "sd" | "ci95" | "none".
    *annotate_stats*: for bar/box/violin, compare the groups (Welch t / Mann-
      Whitney for 2 groups; ANOVA+Tukey / Kruskal+Dunn for >2, chosen by a
      normality check) and draw brackets. The chosen test and every p-value are
      recorded in a ``<figure>.stats.json`` sidecar for the Methods section
      (surfaced by export_adjustment_ledger).
    *only_significant*: draw brackets only for p<0.05 pairs (default) — keeps the
      panel uncluttered; all comparisons are still stored in the sidecar.
    *label*: optional panel corner label (e.g. "D").
    *title* / *ylabel* / *xlabel*: axis text.
    *stats_mode*: "auto" (choose parametric vs non-parametric by a normality
      check — default), "parametric", or "nonparametric". Applies to bar/box/
      violin group comparisons; scatter always uses correlation and grouped uses
      two-way ANOVA.
    *latex*: typeset all the plot's text (axis labels, ticks, title) with the
      computer's LaTeX (TeX Live / MiKTeX / MacTeX): full LaTeX in labels, e.g.
      ``ylabel="$D$ (\\si{\\micro\\metre\\squared\\per\\second})"``, sans-serif to
      match the figure. Ignored without a LaTeX installation.

    For *kind="scatter"* the correlation (r, R^2, p) of the first two columns is
    shown in the legend and recorded; for *kind="grouped"* a two-way ANOVA (main
    effects + interaction) is printed under the axes and recorded.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.

    Example — box plot of three conditions with auto-stats::

        add_data_plot("fig.pyf", [0], "counts.csv", kind="box",
                      ylabel="cells / field", label="D")
    """
    kind = kind.lower()
    if kind not in _DATA_PLOT_KINDS:
        return f"ERROR: kind must be one of {_DATA_PLOT_KINDS}."
    if error not in ("sem", "sd", "ci95", "none"):
        return "ERROR: error must be 'sem', 'sd', 'ci95' or 'none'."
    if stats_mode not in ("auto", "parametric", "nonparametric"):
        return (f"ERROR: stats_mode must be 'auto', 'parametric' or 'nonparametric', not "
                f"{stats_mode!r}: the test itself is chosen from the data (t-test / ANOVA "
                f"are 'parametric', Mann-Whitney / Kruskal-Wallis 'nonparametric').")
    if not os.path.isfile(csv_path):
        return f"ERROR: no such CSV file: {csv_path}"
    csv_abs = os.path.abspath(csv_path)
    if not _csv_number_count(csv_abs):
        return (f"ERROR: {csv_path} holds no numbers to plot (empty, or a header without "
                f"values); nothing was added.")

    script = _make_data_plot_script(csv_abs, kind, error, annotate_stats,
                                    only_significant, title, ylabel, xlabel,
                                    stats_mode, latex=latex)

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__data_plot__")
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    if label:
        img.find("annotations").append(_new_tatext2d(label, label_placement))
    _append_image(container, img, is_root=(not group_path))
    _save(tree, pyf_path, recompute=True)
    idx = len([c for c in container if c.tag == "Image2D"]) - 1

    # record stats provenance at add time (soft dep). Group comparisons
    # (bar/box/violin) get pairwise tests; grouped gets two-way ANOVA; scatter
    # gets a correlation.
    stats_note = ""
    stats_warnings: list[str] = []
    if annotate_stats:
        rec = None
        _mode = {"auto": None, "parametric": True, "nonparametric": False}[stats_mode]
        try:
            from staplot import api as _api
            if kind in ("bar", "box", "violin"):
                rec = _api.auto_test(_api.table_from_csv(csv_abs),
                                     only_significant=only_significant,
                                     parametric=_mode)
            elif kind == "grouped":
                rec = _api.two_way_test(_api.grouped_table_from_csv(csv_abs))
            elif kind == "scatter":
                rec = _api.correlation_test(_api.table_from_csv(csv_abs))
        except Exception as e:
            stats_note = f" (stats provenance skipped: {type(e).__name__})"
        if rec and "error" not in rec:
            entry = {"source": "data_plot", "panel_label": label,
                     "csv": csv_abs, "kind": kind, "test": rec.get("test")}
            if kind in ("bar", "box", "violin"):
                entry.update(omnibus=rec.get("omnibus"),
                             correction=rec.get("correction"),
                             normality=rec.get("normality"),
                             comparisons=rec.get("comparisons"))
                if rec.get("warnings"):
                    entry["warnings"] = rec["warnings"]
                nsig = len(rec.get("sig_pairs", []))
                stats_note = f" — {rec.get('test')}, {nsig} significant pair(s) bracketed"
                stats_warnings = list(rec.get("warnings", []))
            elif kind == "grouped":
                entry.update(effects=rec.get("effects"))
                stats_note = f" — {rec.get('test')} recorded"
            elif kind == "scatter":
                entry.update(r=rec.get("r"), r2=rec.get("r2"), p=rec.get("p"),
                             n=rec.get("n"), x=rec.get("x"), y=rec.get("y"))
                stats_note = (f" — {rec.get('test')} r={rec.get('r'):.3g}, "
                              f"p={rec.get('p'):.3g}")
            _append_stats_entry(pyf_path, entry)

    loc = "canvas" if not group_path else f"group {group_path}"
    suffix = f' with label "{label}"' if label else ""
    return (
        f"Data-plot panel ({kind}) added as index {idx} in {loc}{suffix} from "
        f"{os.path.basename(csv_abs)}{stats_note}. Reopen the figure in PyFigures "
        f"to render it."
        + "".join(f"\nNOTE: {w}" for w in stats_warnings)
    )


def _make_flip_script(flip_h: bool, flip_v: bool) -> str:
    """Return a custom_loading_script that loads file_path and flips the image."""
    ops = []
    if flip_h:
        ops.append("arr = arr[:, ::-1]")   # mirror left-right
    if flip_v:
        ops.append("arr = arr[::-1, :]")   # mirror top-bottom
    ops_code = "\n".join(ops)
    return f"""\
try:
    import tifffile as _tf
    arr = _tf.imread(file_path)
except Exception:
    from PIL import Image as _PI
    arr = np.array(_PI.open(file_path))
# normalise to HWC for display
if arr.ndim == 2:
    arr = arr[:, :, np.newaxis].repeat(3, axis=2)
elif arr.ndim == 3 and arr.shape[0] <= 4 and arr.shape[2] > 4:
    arr = np.moveaxis(arr, 0, -1)   # CHW -> HWC
arr = arr[..., :3]                  # drop alpha if present
# flip
{ops_code}
# scale to uint8 for display
if arr.dtype != np.uint8:
    _lo, _hi = arr.min(), arr.max()
    if _hi > _lo:
        arr = ((arr - _lo) / (_hi - _lo) * 255).astype(np.uint8)
    else:
        arr = arr.astype(np.uint8)
# figure shaped exactly like the image, no margin (a default 4:3 figure
# stretched non-4:3 images)
fig = plt.figure(figsize=(arr.shape[1] / 100.0, arr.shape[0] / 100.0), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.imshow(arr, interpolation='none', aspect='equal')
ax.axis('off')
fig._pyfigures_pad_inches = 0
fig._pyfigures_image_panel = True
self.img = fig
"""


@mcp.tool()
def transform_image(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    rotation: float | None = None,
    flip_h: bool | None = None,
    flip_v: bool | None = None,
    crop_left: int | None = None,
    crop_right: int | None = None,
    crop_top: int | None = None,
    crop_bottom: int | None = None,
    opacity: float | None = None,
    fill_color: str | None = None,
) -> str:
    """Apply geometric transforms and opacity to an image panel.

    All parameters are optional — only the ones you supply are changed.
    Call with multiple parameters to apply several transforms at once.

    *rotation*: clockwise rotation in **degrees** (e.g. 90, -90, 45, 180).
                ``None`` or ``0`` means no rotation (clears any existing rotation).
    *flip_h*:   horizontal mirror (left ↔ right).  True to enable, False to clear.
    *flip_v*:   vertical mirror   (top ↔ bottom).  True to enable, False to clear.
                Flip is implemented via a custom loading script so it works for
                any image type (TIFF, PNG, JPG, …).  If you also set a manual
                script with set_script(), flip will be overwritten — set flip first.
    *crop_left / crop_right / crop_top / crop_bottom*: pixels to remove from
                each edge of the raw image (applied before rotation).
    *opacity*:  0.0 (invisible) – 1.0 (fully opaque, default).
    *fill_color*: background behind rotated/transparent edges.
                  Name ("black", "white"), #rrggbb hex, or integer.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Examples::

        # Rotate 90° clockwise
        transform_image("fig.pyf", [0], 0, rotation=90)

        # Mirror horizontally
        transform_image("fig.pyf", [0], 1, flip_h=True)

        # Flip both axes (equivalent to 180° rotation)
        transform_image("fig.pyf", [0], 2, flip_h=True, flip_v=True)

        # Crop 20 px from each side, rotate 45°, white background
        transform_image("fig.pyf", [0], 3,
                        crop_left=20, crop_right=20,
                        crop_top=20, crop_bottom=20,
                        rotation=45, fill_color="white")

        # Semi-transparent
        transform_image("fig.pyf", [0], 4, opacity=0.5)
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    if opacity is not None and not (0.0 <= opacity <= 1.0):
        return "ERROR: opacity must be between 0.0 and 1.0."

    img = imgs[image_index]
    changed = []

    # --- native PyFigures fields ---
    if rotation is not None:
        _set_child_text(img, "theta", str(float(rotation)) if rotation != 0 else "None")
        changed.append(f"rotation={rotation}°")
    if crop_left is not None:
        _set_child_text(img, "crop_left", str(int(crop_left)))
        changed.append(f"crop_left={crop_left}")
    if crop_right is not None:
        _set_child_text(img, "crop_right", str(int(crop_right)))
        changed.append(f"crop_right={crop_right}")
    if crop_top is not None:
        _set_child_text(img, "crop_top", str(int(crop_top)))
        changed.append(f"crop_top={crop_top}")
    if crop_bottom is not None:
        _set_child_text(img, "crop_bottom", str(int(crop_bottom)))
        changed.append(f"crop_bottom={crop_bottom}")
    if any(c is not None and c < 0 for c in (crop_left, crop_right, crop_top, crop_bottom)):
        return "ERROR: crop values are pixels removed from each side and cannot be negative."
    crop_err = _crop_fit_error(img)
    if crop_err:
        return f"ERROR: {crop_err} Nothing was changed."
    if opacity is not None:
        _set_child_text(img, "opacity", str(float(opacity)))
        changed.append(f"opacity={opacity}")
    if fill_color is not None:
        try:
            fc_int = _color_to_int(fill_color)
        except ValueError as e:
            return f"ERROR: {e}"
        _set_child_text(img, "fill_color", str(fc_int))
        changed.append(f"fill_color={fill_color}")

    # --- flip: implemented via custom_loading_script ---
    if flip_h is not None or flip_v is not None:
        # Read current flip state from existing script if present, else default False
        existing = _child_text(img, "custom_loading_script")
        cur_h = existing is not None and "arr[:, ::-1]" in (existing or "")
        cur_v = existing is not None and "arr[::-1, :]" in (existing or "")
        new_h = flip_h if flip_h is not None else cur_h
        new_v = flip_v if flip_v is not None else cur_v
        if new_h or new_v:
            script = _make_flip_script(new_h, new_v)
            _set_child_text(img, "custom_loading_script", _encode_str(script))
            axes = []
            if new_h: axes.append("horizontal")
            if new_v: axes.append("vertical")
            changed.append(f"flip={'+'.join(axes)}")
        else:
            # Both cleared — remove flip script (unless it was a custom script)
            if existing is not None and "self.img = fig" in existing and "tifffile" in existing:
                _set_child_text(img, "custom_loading_script", "None")
            changed.append("flip=cleared")

    if not changed:
        return "Nothing changed — supply at least one transform parameter."
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: {', '.join(changed)}."


def _canonical_lut_names(luts):
    """Map requested LUT names to the exact keys PyFigures knows (case-
    insensitive). Returns (names_or_None_list, error_messages)."""
    import difflib
    try:
        from batoolset.luts.lut_minimal_test import list_available_luts
        known = list(list_available_luts())
    except Exception:
        # LUT table unavailable: keep the old behaviour rather than block edits
        return [l.upper() if isinstance(l, str) else None for l in luts], []
    by_lower = {k.lower(): k for k in known}
    out, errors = [], []
    for l in luts:
        if not isinstance(l, str) or l.strip() in ("", "None", "null"):
            out.append(None)
            continue
        key = by_lower.get(l.strip().lower())
        if key is None:
            close = difflib.get_close_matches(l.strip().upper(), [k.upper() for k in known], n=3)
            hint = f" — did you mean {', '.join(by_lower[c.lower()] for c in close)}?" if close else ""
            errors.append(f"unknown LUT {l!r}{hint}")
        out.append(key)
    return out, errors


@mcp.tool()
def set_lut(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    luts: list[str | None],
    normalization: str | None = None,
) -> str:
    """Set the colour look-up table (LUT) for each channel of an image.

    *luts*: list of LUT names, one entry per channel in the image.
            Use ``null`` / ``None`` to leave a channel at its current LUT.
            Single-channel images: ``["GREEN"]``.
            Three-channel RGB: ``["RED", "GREEN", "BLUE"]``.
            Mixed (ch0 red, ch1 default): ``["RED", null]``.

    Available LUT names (case-insensitive):
      Standard:  DEFAULT, GRAY, RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA,
                 ORANGE, PURPLE, AFM_HOT, RED_HOT, GREEN_HOT, BLUE_HOT,
                 OCEAN, HI_LO, DNA, RAINBOW_1, RAINBOW_2, RAINBOW_3,
                 RAINBOW_LIGHT, BLUE_WHITE_RED, GREEN_FIRE_BLUE, …
      Matplotlib: MATPLOTLIB_viridis, MATPLOTLIB_plasma, MATPLOTLIB_inferno,
                  MATPLOTLIB_magma, MATPLOTLIB_jet, MATPLOTLIB_hot,
                  MATPLOTLIB_coolwarm, MATPLOTLIB_gray, and all others
                  from matplotlib (append _r for the reversed version).

    *normalization*: optional JSON-like dict string controlling intensity range.
      Common forms::

        # Auto-scale each channel independently to its own min/max
        '{"per_channel": true}'

        # Auto-scale to the current display range (per-frame min/max)
        '{"range": "display"}'

        # Fixed range for a 16-bit image (e.g. 100–4000 out of 0–65535)
        '{"range": "custom", "min_value": 100, "max_value": 4000}'

        # Remove top 1% hot-spots before scaling
        '{"ignore_hot_spots": 0.01}'

        # Per-channel + hot-spot removal combined
        '{"per_channel": true, "ignore_hot_spots": 0.01}'

      Pass ``null`` to clear normalization (revert to default auto-scaling).

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Examples::

        # Show a fluorescence image with green LUT
        set_lut("fig.pyf", [0], 0, ["GREEN"])

        # Two-channel image: red actin + green tubulin
        set_lut("fig.pyf", [0], 1, ["RED", "GREEN"])

        # Viridis colormap with auto per-channel normalisation
        set_lut("fig.pyf", [0], 2, ["MATPLOTLIB_viridis"],
                normalization='{"per_channel": true}')
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    img = imgs[image_index]
    changed = []

    # Resolve each name case-insensitively to its real key. (Blindly upper-casing
    # broke mixed-case names — "MATPLOTLIB_viridis" became a non-existent
    # "MATPLOTLIB_VIRIDIS" — and unknown names were stored silently.)
    luts_encoded, unknown = _canonical_lut_names(luts)
    if unknown:
        return "ERROR: " + "; ".join(unknown)
    _set_child_text(img, "LUTs", repr(luts_encoded))
    changed.append(f"LUTs={luts_encoded}")
    from .stacks import _sync_split_colours
    synced = _sync_split_colours(container, img, luts_encoded)
    if synced:
        changed.append("channel split matched: " + ", ".join(synced))
    warning = ""
    n_channels = _channel_count_from_file(_first_filename(img))
    if n_channels and n_channels > 1 and len(luts) == 1:
        # 'lut: red' on an RGB image changed nothing visible (a local model
        # expected it to show one channel)
        warning = (f"\nWARNING: the image has {n_channels} channels and one LUT colours "
                   f"only the first (RED on an RGB image changes nothing); to show the "
                   f"channels separately use "
                   f"add_channel_split (recipe: split:), or give one LUT per channel.")

    if normalization is not None:
        # Store as the raw string — PyFigures evals it via ast.literal_eval
        _set_child_text(img, "normalization", normalization)
        changed.append(f"normalization={normalization}")
    elif normalization is None and len(luts) > 0:
        pass  # leave existing normalization untouched unless explicitly cleared

    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: {', '.join(changed)}.{warning}"


@mcp.tool()
def configure_image(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    channels: list[bool] | None = None,
    projection: str | None = None,
    projection_z_start: int | None = None,
    projection_z_end: int | None = None,
    serie_to_open: int | None = None,
    normalization: str | None = None,
    clear_normalization: bool = False,
) -> str:
    """Configure display settings for an image: active channels, Z-projection,
    multi-series index, and intensity normalisation.

    Pass only the parameters you want to change — unspecified parameters are
    left at their current values.

    **channels**
      List of booleans, one per channel, indicating which channels are shown.
      ``[True, False, True]`` shows channels 0 and 2, hides channel 1.
      ``null`` (omit) leaves the current selection unchanged.

    **projection**
      Z-projection mode for 3-D / Z-stack images:
        - ``"max"``  — maximum intensity projection
        - ``"min"``  — minimum intensity projection
        - ``"avg"``  — average intensity projection
        - ``"none"`` — no projection (show a single Z slice)
        - ``null``   — leave current setting unchanged

    **projection_z_start** / **projection_z_end**
      First / last (exclusive) Z slice included in the projection.
      Both ``null`` = use all slices.  Pass ``-1`` to reset to *all slices*.

    **serie_to_open**
      0-based series index for multi-series files (.lif, .czi, …).
      Pass ``-1`` to clear (revert to the default first series).
      ``null`` leaves the current series unchanged.

    **normalization**
      JSON-like dict string.  Common forms::

        # Auto-scale each channel to its own min/max
        '{"per_channel": true}'

        # Auto-scale to the per-frame display range
        '{"range": "display"}'

        # Fixed 16-bit window
        '{"range": "custom", "min_value": 200, "max_value": 3500}'

        # Remove hot-spots (top 1%) before scaling
        '{"ignore_hot_spots": 0.01}'

      ``null`` leaves normalization unchanged (use *clear_normalization* to remove it).

    **clear_normalization**
      Set to ``true`` to remove any existing normalization setting (revert to
      PyFigures auto-scaling).  Overrides the *normalization* parameter.

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.

    Examples::

        # Show channels 0 and 2 of a 3-channel image
        configure_image("fig.pyf", [0], 1, channels=[True, False, True])

        # Max-intensity projection across all Z slices
        configure_image("fig.pyf", [0], 0, projection="max")

        # Max projection, slices 5–20 only
        configure_image("fig.pyf", [0], 0, projection="max",
                        projection_z_start=5, projection_z_end=20)

        # Open series 2 of a .lif file
        configure_image("fig.pyf", [0], 0, serie_to_open=2)

        # Per-channel auto-normalisation
        configure_image("fig.pyf", [0], 0,
                        normalization='{"per_channel": true}')
    """
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if image_index >= len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    img = imgs[image_index]
    changed: list[str] = []

    # channels — list of booleans
    if channels is not None:
        bools = [bool(c) for c in channels]
        _set_child_text(img, "channels", repr(bools))
        changed.append(f"channels={bools}")

    # projection
    if projection is not None:
        p = projection.strip().lower()
        if p in ("none", ""):
            _set_child_text(img, "projection", "None")
            changed.append("projection=cleared")
        elif p in ("max", "min", "avg"):
            _set_child_text(img, "projection", p)
            changed.append(f"projection={p}")
        else:
            return (
                f"ERROR: projection must be 'max', 'min', 'avg', or 'none'. Got {projection!r}."
            )

    # projection_z_start / projection_z_end
    if projection_z_start is not None:
        if projection_z_start < 0:
            _set_child_text(img, "projection_z_start", "None")
            changed.append("projection_z_start=cleared")
        else:
            _set_child_text(img, "projection_z_start", str(projection_z_start))
            changed.append(f"projection_z_start={projection_z_start}")

    if projection_z_end is not None:
        if projection_z_end < 0:
            _set_child_text(img, "projection_z_end", "None")
            changed.append("projection_z_end=cleared")
        else:
            _set_child_text(img, "projection_z_end", str(projection_z_end))
            changed.append(f"projection_z_end={projection_z_end}")

    # serie_to_open
    if serie_to_open is not None:
        if serie_to_open < 0:
            _set_child_text(img, "serie_to_open", "None")
            changed.append("serie_to_open=cleared")
        else:
            _set_child_text(img, "serie_to_open", str(serie_to_open))
            changed.append(f"serie_to_open={serie_to_open}")

    # normalization
    if clear_normalization:
        _set_child_text(img, "normalization", "None")
        changed.append("normalization=cleared")
    elif normalization is not None:
        _set_child_text(img, "normalization", normalization)
        changed.append(f"normalization={normalization}")

    if not changed:
        return "Nothing changed — no parameters were specified."

    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: {', '.join(changed)}."
