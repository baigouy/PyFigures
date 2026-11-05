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
from ..flip import legacy_state as legacy_flip_state
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
    if not channel_files or len(channel_files) < 2:
        # one file "merged" drew a blank panel; one image in a colour is a LUT
        return ("ERROR: a merge needs at least two channel files; to show one image "
                "in a colour use add_image then set_lut.")
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
                           xlabel: str, stats_mode: str = "auto", latex: bool = False,
                           colors: list | None = None) -> str:
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
                              colors={list(colors) if colors else None!r},
                              title={title!r}, ylabel={ylabel!r}, xlabel={xlabel!r},
                              show_title={bool(title)!r})
    fig._pyf_rc = _rc
    # out of pyplot's list of open figures (every plot panel stayed there:
    # "More than 20 figures have been opened"); the panel draws it with savefig
    from matplotlib.backends.backend_agg import FigureCanvasAgg as _Agg
    import matplotlib.pyplot as _plt
    _Agg(fig)                    # its own canvas, so closing frees only pyplot's
    _plt.close(fig)
    self.img = fig
"""


def _plot_colours(colors) -> tuple[list | None, str]:
    """(matplotlib colours, error) for a plot's group colours: the figure's
    colour words (magenta, green…) take the tints the images use, anything
    else must be a colour matplotlib knows (#rrggbb, 'tab:blue'…)."""
    if not colors:
        return None, ""
    if isinstance(colors, str):
        colors = [colors]
    from .stacks import _COLOR_HEX
    from matplotlib.colors import is_color_like
    out = []
    for c in colors:
        name = str(c).strip().lower()
        if name in _COLOR_HEX:
            out.append(f"#{_COLOR_HEX[name]:06x}" if name not in ("gray", "grey", "white")
                       else "#999999")
        elif is_color_like(str(c).strip()):
            out.append(str(c).strip())
        else:
            return None, (f"unknown colour {c!r}: use a name (magenta, green, red, blue, cyan, "
                          f"yellow, gray) or #rrggbb")
    return out, ""


def _csv_number_count(path: str) -> int:
    """How many finite numbers a CSV holds (0 for an empty file or a header
    alone: the plot would be an empty frame)."""
    import csv
    try:
        from staplot.api import csv_format
    except ImportError:                 # soft dependency: the panel itself says it is missing
        def csv_format(_sample):
            return ",", "."
    n = 0
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            sep, decimal = csv_format(f.read(4096))       # the reader the plot uses
            f.seek(0)
            for row in csv.reader(f, delimiter=sep):
                for cell in row:
                    try:
                        v = float(cell.replace(",", ".") if decimal == "," else cell)
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
    colors: list[str] | None = None,
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
    *title* / *ylabel* / *xlabel*: axis text. No title unless *title* is given
      (journals rarely want titles on figure panels; a talk slide may).
    *stats_mode*: "auto" (choose parametric vs non-parametric by a normality
      check — default), "parametric", or "nonparametric". Applies to bar/box/
      violin group comparisons; scatter always uses correlation and grouped uses
      two-way ANOVA.
    *latex*: typeset all the plot's text (axis labels, ticks, title) with the
      computer's LaTeX (TeX Live / MiKTeX / MacTeX): full LaTeX in labels, e.g.
      ``ylabel="$D$ (\\si{\\micro\\metre\\squared\\per\\second})"``, sans-serif to
      match the figure. Ignored without a LaTeX installation.
    *colors*: one colour per group, in the CSV's order (names such as magenta /
      green or #rrggbb); groups beyond the list keep the default palette.
      set_figure_colors recolours plots and images together.

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
    if kind == "grouped":
        try:
            from staplot import api as _api
            _api.grouped_table_from_csv(csv_abs)
        except ImportError:
            pass                        # the panel says staplot is missing
        except ValueError as e:
            return f"ERROR: {e}; nothing was added."

    plot_colors, bad = _plot_colours(colors)
    if bad:
        return f"ERROR: {bad}"
    script = _make_data_plot_script(csv_abs, kind, error, annotate_stats,
                                    only_significant, title, ylabel, xlabel,
                                    stats_mode, latex=latex, colors=plot_colors)

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


def _flip_state(img) -> tuple[bool, bool]:
    """(flip_h, flip_v) of an Image2D element: its properties, or an old flip script."""
    legacy = legacy_flip_state(_child_text(img, "custom_loading_script"))
    if legacy is not None:
        return legacy
    return tuple(str(_child_text(img, tag)).strip().lower() == "true" for tag in ("flip_h", "flip_v"))


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
                A flip is a drawing property like the rotation: the image's
                pixels, channels and pixel size stay the original.
    *crop_left / crop_right / crop_top / crop_bottom*: pixels to remove from
                each edge of the raw image (applied before rotation). To crop
                to something in the image, first look at the whole source with
                its pixel rulers (preview_panel live, preview_panel_source on a
                file) and crop once; never uncrop just to look.
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
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    if opacity is not None and not (0.0 <= opacity <= 1.0):
        return "ERROR: opacity must be between 0.0 and 1.0."
    if rotation is not None and not math.isfinite(float(rotation)):
        return f"ERROR: rotation must be a number of degrees (got {rotation})."

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

    # --- flip: native Image2D drawing properties (the pixels stay the original) ---
    if flip_h is not None or flip_v is not None:
        cur_h, cur_v = _flip_state(img)
        # a flip written by an older version as a loading script becomes the properties
        if legacy_flip_state(_child_text(img, "custom_loading_script")) is not None:
            _set_child_text(img, "custom_loading_script", "None")
        new_h = bool(flip_h) if flip_h is not None else cur_h
        new_v = bool(flip_v) if flip_v is not None else cur_v
        _set_child_text(img, "flip_h", str(new_h))
        _set_child_text(img, "flip_v", str(new_v))
        axes = [name for name, on in (("horizontal", new_h), ("vertical", new_v)) if on]
        changed.append(f"flip={'+'.join(axes)}" if axes else "flip=cleared")

    if not changed:
        return "Nothing changed — supply at least one transform parameter."
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: {', '.join(changed)}."


_FIJI_LUT_NEAREST = {
    "FIRE": ["MATPLOTLIB_INFERNO", "AFM_HOT", "MATPLOTLIB_GNUPLOT2"],
    "ICE": ["MATPLOTLIB_OCEAN_R", "CYAN_HOT"],
    "16_COLORS": ["MATPLOTLIB_NIPY_SPECTRAL", "RAINBOW_1"],
    "16 COLORS": ["MATPLOTLIB_NIPY_SPECTRAL", "RAINBOW_1"],
    "GREYS": ["GRAY"],
    "GRAYS": ["GRAY"],
    "SPECTRUM": ["MATPLOTLIB_HSV", "HSV"],
    "THERMAL": ["MATPLOTLIB_INFERNO", "MATPLOTLIB_HOT"],
}


_INVERT_WORDS = r"(?:inverted|inverse|invert|reversed|reverse|negative)"


def _lut_alias(name, by_lower):
    """The exact key for a LUT name as people and models write it: "viridis"
    (MATPLOTLIB_viridis), and inversions — "inverted gray", "GRAY_r",
    "reversed viridis", "viridis_inverted" (GRAY_INVERTED, MATPLOTLIB_viridis_r;
    "invert the gradient" asked for MATPLOTLIB_viridis_r, 2026-11-03)."""
    s = re.sub(r"[\s\-]+", "_", name.strip().lower())
    for candidate in (s, "matplotlib_" + s):
        if candidate in by_lower:
            return by_lower[candidate]
    base = re.sub(rf"^{_INVERT_WORDS}_|_(?:{_INVERT_WORDS}|r)$", "", s)
    if base == s:
        return None
    base = base[len("matplotlib_"):] if base.startswith("matplotlib_") else base
    for candidate in (base + "_inverted", "matplotlib_" + base + "_r"):
        if candidate in by_lower:
            return by_lower[candidate]
    return None


_LUT_CLEAR = {"none", "default", "no lut", "nolut", "original", "reset", "acquisition"}


def _canonical_lut_names(luts):
    """Map requested LUT names to the exact keys PyFigures knows (case-
    insensitive, with the aliases of _lut_alias). Returns
    (names_or_None_list, error_messages)."""
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
        key = by_lower.get(l.strip().lower()) or _lut_alias(l, by_lower)
        if key is None:
            close = difflib.get_close_matches(l.strip().upper(), [k.upper() for k in known], n=3)
            # Fiji LUT names with no PyFigures twin: point to the nearest look
            close = _FIJI_LUT_NEAREST.get(l.strip().upper(), close)
            hint = f" — did you mean {', '.join(by_lower[c.lower()] for c in close)}?" if close else ""
            errors.append(f"unknown LUT {l!r}{hint}")
        out.append(key)
    return out, errors


@mcp.tool()
def list_luts(query: str | None = None) -> str:
    """List the colour look-up tables (LUTs) that set_lut accepts.

    *query*: optional part of a name (case-insensitive), e.g. "green", "fire"
    or "viridis", to list only matching LUTs. Also answers "is there a
    magenta-hot LUT?": list_luts("magenta_hot") → lut_check.available.

    Returns JSON with: luts (exact names, filtered by *query*) and their
    count; standard (the plain PyFigures LUTs) and matplotlib_count when no
    query is given; with a query, lut_check: whether that exact name exists,
    its exact key, and close matches to offer when it does not. Names are
    case-insensitive in set_lut. Inverted LUTs (Fiji's Invert LUT; "negative",
    "reversed"): <NAME>_INVERTED for the PyFigures LUTs (GRAY_INVERTED: dark
    signal on white), MATPLOTLIB_<name>_r for matplotlib maps; set_lut also
    accepts "inverted gray" or "viridis_r".
    """
    import difflib
    try:
        from batoolset.luts.lut_minimal_test import list_available_luts
        known = list(list_available_luts())
    except Exception as e:
        return f"ERROR: LUT table unavailable ({type(e).__name__}: {e})"
    query = str(query).strip() if query else None
    if not query:
        standard = [k for k in known if not k.startswith("MATPLOTLIB_") and not k.endswith("_INVERTED")]
        return json.dumps({"query": None, "count": len(known), "standard": standard,
                           "inverted": "<NAME>_INVERTED for each standard LUT (GRAY_INVERTED: dark "
                                       "on white); MATPLOTLIB_<name>_r for matplotlib maps",
                           "matplotlib_count": len(known) - len(standard),
                           "matplotlib_examples": [k for k in known if k.startswith("MATPLOTLIB_")
                                                   and not k.endswith("_r")][:12],
                           "luts": known}, ensure_ascii=False, indent=2)
    q = query.lower().replace(" ", "_").replace("-", "_")
    hits = [k for k in known if q in k.lower()]
    by_lower = {k.lower(): k for k in known}
    exact = by_lower.get(q) or by_lower.get("matplotlib_" + q)
    close = [] if exact else [by_lower[c] for c in difflib.get_close_matches(
        q, list(by_lower), n=5, cutoff=0.6)]
    return json.dumps({"query": query, "count": len(hits), "luts": hits,
                       "lut_check": {"name": query, "available": bool(exact), "exact_key": exact,
                                     "close_matches": close or hits[:5]}},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def list_colors(query: str | None = None) -> str:
    """List the colour names PyFigures accepts, as list_fonts does for fonts.

    Two kinds, because they apply to different things:
    - channel_colors: the colours of image CHANNELS (set_figure_colors,
      channel splits) — gray, red, green, blue, cyan, magenta, yellow…;
    - drawing_colors: outlines, text, arrows, ROIs, scale bars, borders —
      these names, or any #rrggbb.

    *query*: a colour name ("magenta", "orange") to check: color_check says
    whether it works for channels, for drawings, and close names to offer.

    When the user names colours without saying what they are for and the
    figure has both channels and coloured drawings (ROIs, arrows, text), ask
    which they mean instead of guessing.
    """
    import difflib
    from .core import _NAMED_COLORS
    from .stacks import _COLOR_LUTS
    channels, drawings = sorted(_COLOR_LUTS), sorted(_NAMED_COLORS)
    if not query or not str(query).strip():
        return json.dumps({"channel_colors": channels, "drawing_colors": drawings,
                           "drawing_colors_also": "#rrggbb hex"}, ensure_ascii=False, indent=2)
    q = str(query).strip().lower()
    return json.dumps({"query": query, "color_check": {
        "for_channels": q in _COLOR_LUTS, "for_drawings": q in _NAMED_COLORS or bool(re.fullmatch(r"#?[0-9a-f]{6}", q)),
        "close_matches": difflib.get_close_matches(q, sorted(set(channels) | set(drawings)), n=5, cutoff=0.6)}},
        ensure_ascii=False, indent=2)


@mcp.tool()
def set_lut(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    luts: list[str | None] | str,
    normalization: str | None = None,
) -> str:
    """Set the colour look-up table (LUT) for each channel of an image.

    *luts*: list of LUT names, one entry per channel in the image.
            Use ``null`` / ``None`` to leave a channel at its current LUT.
            Single-channel images: ``["GREEN"]``.
            Three-channel RGB: ``["RED", "GREEN", "BLUE"]``.
            Mixed (ch0 red, ch1 unchanged): ``["RED", null]``.
            ``"NONE"`` (also ``"DEFAULT"``) removes the LUT: the channel is drawn
            with the LUT stored in the image file (e.g. the channel colours of an
            LSM / CZI), or in gray when the file has none, as before any LUT was set.
            This is what "remove / reset / clear the LUT(s)" means.

    Available LUT names (case-insensitive; list_luts lists them all and
    checks whether a name exists):
      Standard:  DEFAULT, GRAY, RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA,
                 ORANGE, PURPLE, AFM_HOT, RED_HOT, GREEN_HOT, BLUE_HOT,
                 OCEAN, HI_LO, DNA, RAINBOW_1, RAINBOW_2, RAINBOW_3,
                 RAINBOW_LIGHT, BLUE_WHITE_RED, GREEN_FIRE_BLUE, …
      Matplotlib: MATPLOTLIB_viridis, MATPLOTLIB_plasma, MATPLOTLIB_inferno,
                  MATPLOTLIB_magma, MATPLOTLIB_jet, MATPLOTLIB_hot,
                  MATPLOTLIB_coolwarm, MATPLOTLIB_gray, and all others
                  from matplotlib (append _r for the reversed version).
      Inverted (Fiji's Invert LUT; "invert", "negative", "reversed"):
                  append _INVERTED to a standard LUT — GRAY_INVERTED shows a
                  dark signal on white, GREEN_INVERTED, FIRE-like HOT LUTs… —
                  and _r to a matplotlib map. "inverted gray" and "viridis_r"
                  are accepted too.

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
    if isinstance(luts, str):
        # one LUT for a one-channel image, as models often send it ("GREEN")
        luts = [luts]
    # "NONE" / "DEFAULT" remove the LUT (the image's own colours). DEFAULT used to
    # be stored as a palette name and drew the DNA rainbow (2026-11-05)
    cleared = {i for i, l in enumerate(luts) if isinstance(l, str) and l.strip().lower() in _LUT_CLEAR}
    luts = [None if i in cleared else l for i, l in enumerate(luts)]
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    img = imgs[image_index]
    changed = []
    refusal = _plot_script_refusal(img)
    if refusal:
        return refusal

    # Resolve each name case-insensitively to its real key. (Blindly upper-casing
    # broke mixed-case names — "MATPLOTLIB_viridis" became a non-existent
    # "MATPLOTLIB_VIRIDIS" — and unknown names were stored silently.)
    luts_encoded, unknown = _canonical_lut_names(luts)
    if unknown:
        return "ERROR: " + "; ".join(unknown) + " (list_luts lists every LUT name)"
    n_file = _channel_count_from_file(_first_filename(img))
    if n_file and len(luts) > n_file:
        # the extra LUTs were stored for channels that do not exist
        return (f"ERROR: {len(luts)} LUTs for an image with {n_file} channel"
                f"{'s' if n_file > 1 else ''}: give at most one LUT per channel.")
    # null keeps that channel's current LUT, as documented (a model asking for
    # [null, "YELLOW", null] used to wipe channels 1 and 3)
    import ast
    try:
        current = ast.literal_eval(_child_text(img, "LUTs") or "None") or []
    except (ValueError, SyntaxError):
        current = []
    luts_encoded = [None if i in cleared else current[i] if new is None and i < len(current) else new
                    for i, new in enumerate(luts_encoded)]
    kept = []
    if n_file and 1 < len(luts_encoded) < n_file:
        # ["MAGENTA", "GREEN"] on a 3-channel merge stored a list one short and
        # channel 3 was drawn in a default colour (Mistral Large 4, Figure 3
        # trial, 2026-11-03): the channels not given keep their LUT, and it is said
        for i in range(len(luts_encoded), n_file):
            luts_encoded.append(current[i] if i < len(current) else None)
            kept.append(f"channel {i + 1} ({current[i] if i < len(current) and current[i] else 'its default'})")
    if not any(luts_encoded):
        luts_encoded = None                      # no LUT left: the image's own colours
    _set_child_text(img, "LUTs", repr(luts_encoded))
    changed.append(f"LUTs={luts_encoded}" if luts_encoded else "LUTs removed (the image's own colours)")
    from .stacks import _sync_split_colours
    synced = _sync_split_colours(container, img, luts_encoded or [])
    if synced:
        changed.append("channel split matched: " + ", ".join(synced))
    warning = ""
    n_channels = _channel_count_from_file(_first_filename(img))
    if n_channels and n_channels > 1 and len(luts) == 1 and not cleared:
        # 'lut: red' on an RGB image changed nothing visible (a local model
        # expected it to show one channel)
        warning = (f"\nWARNING: the image has {n_channels} channels and one LUT colours "
                   f"only the first (RED on an RGB image changes nothing); to show the "
                   f"channels separately use "
                   f"add_channel_split (recipe: split:), or give each channel its own LUT. "
                   f"Never give the SAME LUT to several channels (e.g. GRAY on all): they add up "
                   f"in one colour and can no longer be told apart; ask the user first.")
    dup = None
    if luts_encoded:
        from .export import shared_channel_luts
        dup = shared_channel_luts(img)
    if dup:
        warning += (f"\nWARNING: channels {', '.join(map(str, dup['channels']))} now all use "
                    f"{dup['lut']}: they add up in one colour and cannot be told apart. "
                    f"Tell the user; undo unless they asked for exactly this.")
    if kept:
        shown = [True] * len(luts) + [False] * (n_channels - len(luts))
        warning += (f"\nNOTE: {len(luts)} LUTs for {n_channels} channels: "
                    f"{', '.join(kept)} kept {'its' if len(kept) == 1 else 'their'} LUT and "
                    f"{'is' if len(kept) == 1 else 'are'} still shown. To show only the "
                    f"{len(luts)} coloured channels, hide the others with configure_image "
                    f"(channels={shown}).")

    if normalization is not None:
        from .core import _normalization_to_store
        stored, bad = _normalization_to_store(normalization)
        if bad:
            return f"ERROR: {bad}. Nothing was changed."
        # a Python literal: PyFigures reads it with ast.literal_eval
        _set_child_text(img, "normalization", stored)
        changed.append(f"normalization={normalization}")
    elif normalization is None and len(luts) > 0:
        pass  # leave existing normalization untouched unless explicitly cleared

    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: {', '.join(changed)}.{warning}"


def _plot_script_refusal(img) -> str | None:
    """A panel drawn by a plotting script (a matplotlib figure, a data plot)
    has no channels: a LUT stored on it changes nothing visible ("invert the
    gradient in b" on a script-drawn viridis gradient, 2026-11-03)."""
    from .core import _decode
    script = _decode(_child_text(img, "custom_loading_script"))
    if not isinstance(script, str) or script.strip() in ("", "None") or script.startswith(_MERGE_MARKER) \
            or legacy_flip_state(script) is not None:
        return None
    if re.search(r"\bplt\.|subplots\(|Figure\(|staplot", script):
        return ("ERROR: this panel is drawn by a plotting script, so it has no image channels and "
                "a LUT would change nothing. Change the colour map in its script instead "
                "(get_script, then set_script; e.g. cmap='viridis' -> cmap='viridis_r' to invert it). "
                "Nothing was changed.")
    return None


@mcp.tool()
def invert_lut(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    channels: list[int] | None = None,
) -> str:
    """Invert the LUT (colour look-up table) of an image's channels, as Fiji's
    Invert LUT: dark becomes light. Use for "invert the colours", "negative",
    "white background, dark signal", "reverse the colour map" when no new LUT
    is named. Calling it again restores the original.

    The current LUT is swapped for its inverted twin, stored by name so the
    saved figure keeps it: GRAY <-> GRAY_INVERTED, GREEN <-> GREEN_INVERTED,
    MATPLOTLIB_viridis <-> MATPLOTLIB_viridis_r. A one-channel image still on
    its acquisition colour becomes GRAY_INVERTED. preview_luts shows the result.

    *channels*: 0-based channel indices to invert; None inverts every channel.
    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.
    *image_index*: 0-based index among Image2D elements at that location.
    """
    import ast
    from batoolset.luts.lut_minimal_test import invert_lut_name, list_available_luts
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    refusal = _plot_script_refusal(img)
    if refusal:
        return refusal
    try:
        current = list(ast.literal_eval(_child_text(img, "LUTs") or "None") or [])
    except (ValueError, SyntaxError):
        current = []
    n_file = _channel_count_from_file(_first_filename(img)) or max(len(current), 1)
    current += [None] * (n_file - len(current))
    wanted = list(range(n_file)) if channels is None else channels
    bad = [c for c in wanted if not isinstance(c, int) or not 0 <= c < n_file]
    if bad:
        return f"ERROR: channel {bad[0]} does not exist (the image has {n_file}). Nothing was changed."
    available = list_available_luts()
    new, done = list(current), []
    for c in wanted:
        lut = current[c]
        if lut in (None, "DEFAULT"):
            if n_file != 1:
                return (f"ERROR: channel {c} shows its acquisition colour, which has no inverted twin. "
                        f"Which LUT should it get (e.g. GRAY_INVERTED, GREEN_INVERTED)? Nothing was changed.")
            lut = "GRAY"
        twin = invert_lut_name(lut, available)
        if twin is None:
            return f"ERROR: the LUT {lut} of channel {c} cannot be inverted. Nothing was changed."
        new[c] = twin
        done.append(f"channel {c}: {current[c] or 'acquisition colour'} -> {twin}")
    _set_child_text(img, "LUTs", repr(new))
    from .stacks import _sync_split_colours
    _sync_split_colours(container, img, new)
    _save(tree, pyf_path)
    loc = "canvas" if not group_path else f"group {group_path}"
    return f"Image {image_index} in {loc}: LUT inverted — " + "; ".join(done) + f". LUTs={new}."


@mcp.tool()
def preview_luts(luts: list[str] | str) -> Image:
    """Show colour ramps of LUTs (colour look-up tables) as an image, darkest
    value on the left, so the user can compare them before choosing — e.g.
    preview_luts(["GRAY", "GRAY_INVERTED", "MATPLOTLIB_viridis", "MAGENTA_HOT"]).
    Accepts the same names as set_lut (case-insensitive; "inverted gray",
    "viridis_r"). At most 24 LUTs. Read-only: changes no figure.
    """
    import numpy as np
    from batoolset.luts.lut_minimal_test import list_available_luts, PaletteCreator
    if isinstance(luts, str):
        luts = [luts]
    names, errors = _canonical_lut_names(list(luts)[:24])
    if errors:
        raise ValueError("; ".join(errors) + " (list_luts lists every LUT name)")
    names = [n for n in names if n]
    if not names:
        raise ValueError("Name at least one LUT to preview (list_luts lists them).")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    available, creator = list_available_luts(), PaletteCreator()
    fig = Figure(figsize=(6, 0.42 * len(names) + 0.2), dpi=110)
    FigureCanvasAgg(fig)
    for i, name in enumerate(names):
        ramp = np.asarray(creator.create3(available[name]), dtype=np.uint8)[:256, :3]
        ax = fig.add_axes([0.36, 1 - (i + 1) / len(names) + 0.12 / len(names), 0.6, 0.76 / len(names)])
        ax.imshow(ramp[np.newaxis], aspect="auto", interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(-0.02, 0.5, name, transform=ax.transAxes, ha="right", va="center", fontsize=8)
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return Image(data=buf.getvalue(), format="png")


# Okabe & Ito colour-blind-safe palette (black left out: it is the text colour)
OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]


def _plot_group_count(script: str) -> int | None:
    """How many groups (colours) the data plot of *script* draws, or None."""
    m = re.search(r"^_csv = (.+)$", script, re.M)
    kind = re.search(r"kind=('[a-z]+')", script)
    if not m:
        return None
    try:
        import ast
        from staplot import api as _api
        csv = ast.literal_eval(m.group(1))
        if kind and ast.literal_eval(kind.group(1)) == "grouped":
            import csv as _csvmod
            with open(csv, newline="", encoding="utf-8-sig") as f:
                rows = list(_csvmod.reader(f))[1:]
            return len({r[1] for r in rows if len(r) >= 3}) or None
        return len(_api.table_from_csv(csv).columns) or None
    except Exception:
        return None


def _looks_like_photograph(path) -> bool:
    """An RGB colour photograph (bright field, histology, gel scan): bright
    background, so its channels are not fluorescence channels to recolour."""
    try:
        from PIL import Image
        with Image.open(str(path)) as im:
            if im.mode not in ("RGB", "RGBA"):
                return False
            im.thumbnail((256, 256))
            import numpy as np
            g = np.asarray(im.convert("L"), dtype=float)
        return float(np.median(g)) > 0.5 * 255
    except Exception:
        return False


_PLOT_CALL = re.compile(r"(_api\.plot\(_tbl,)")
_PLOT_COLORS = re.compile(r"colors=(None|\[[^\]]*\]),\s*")


def _recolour_plot_script(script: str, plot_colors: list) -> str:
    """The data-plot script with its group colours set (old scripts have no
    colors= argument: it is added)."""
    if _PLOT_COLORS.search(script):
        return _PLOT_COLORS.sub(lambda m: f"colors={plot_colors!r}, ", script, count=1)
    return _PLOT_CALL.sub(lambda m: f"{m.group(1)} colors={plot_colors!r},", script, count=1)


@mcp.tool()
def set_figure_colors(pyf_path: str, colors: list[str], single_channel: str = "gray") -> str:
    """Recolour the WHOLE figure in one call — "use magenta and green",
    "make it colour-blind friendly". Channel i of every multi-channel image
    (merges, fluorescence RGB micrographs, channel splits: their
    single-channel panels and labels follow) takes ``colors[i]``; channels
    beyond the list keep their colour.

    - Single-channel panels outside a split: gray (``single_channel="gray"``,
      the default — one channel reads best in gray) or ``"keep"``.
    - RGB colour photographs (bright field, histology: bright background) are
      left as they are.
    - Data plots: a plot with exactly ``len(colors)`` groups takes those
      colours; any other plot takes the colour-blind-safe Okabe–Ito palette
      (magenta/green only make sense for two groups).

    *colors*: colour names in channel order — gray, red, green, blue, cyan,
    magenta, yellow. Example: a red/green/blue figure → ``["magenta",
    "green"]`` gives magenta/green/blue images and magenta/green two-group
    plots. ``["colorblind"]`` ("make it colour-blind friendly"): magenta/green
    channels and the Okabe–Ito palette for every plot.
    """
    if single_channel not in ("gray", "grey", "keep"):
        return "ERROR: single_channel must be 'gray' or 'keep'."
    from .stacks import _COLOR_LUTS, _DEFAULT_SPLIT_COLORS, _SPLIT_RE, _sync_split_colours
    import ast
    if isinstance(colors, str):
        colors = [c.strip() for c in re.split(r"[,\s]+", colors) if c.strip()]
    names = [str(c).strip().lower() for c in colors or []]
    colorblind = names in (["colorblind"], ["colourblind"], ["colour-blind"], ["color-blind"])
    if colorblind:
        names = ["magenta", "green"]          # red/green channels → magenta/green
    bad = [c for c in names if c not in _COLOR_LUTS]
    if not names or bad:
        return (f"ERROR: colors must be a list of colour names ({', '.join(sorted(_COLOR_LUTS))})"
                + (f"; unknown: {bad}" if bad else "") + ". Nothing was changed.")
    plot_colors, err = _plot_colours(names)
    if err:
        return f"ERROR: {err}"
    luts = [_COLOR_LUTS[c] for c in names]
    rgb = []
    for c in names:
        ci = _color_to_int(c if c not in ("grey", "gray") else "white")
        rgb.append(((ci >> 16 & 0xFF) / 255., (ci >> 8 & 0xFF) / 255., (ci & 0xFF) / 255.))

    tree, root = _load(pyf_path)
    done = {"images": 0, "merges": 0, "plots": 0}
    synced: list[str] = []
    left: list[str] = []
    gray: list[str] = []
    photos: list[str] = []
    palette_plots: list[str] = []
    # channels beyond the list keep their colour: "use magenta and green" on a
    # 3-channel image kept a third colour in every model run (Figure 3 trials)
    kept_extra: list[str] = []

    def _note_extra(name, cur):
        if len(cur) > len(names):
            kept = ", ".join(f"channel {i + 1} {_lut_name(c)}" for i, c in enumerate(cur)
                             if i >= len(names))
            kept_extra.append(f"{name or 'merge'} ({len(cur)} channels: {kept})")

    def visit(container):
        for img in [c for c in container if c.tag == "Image2D"]:
            script = _decode_text(_child_text(img, "custom_loading_script"))
            name = os.path.basename(str(_first_filename(img) or ""))
            if "from staplot import api" in script:
                n_groups = _plot_group_count(script)
                if n_groups == len(plot_colors) and not colorblind:
                    chosen = plot_colors
                else:
                    chosen = OKABE_ITO[:n_groups] if n_groups else list(OKABE_ITO)
                    palette_plots.append(f"{n_groups or '?'} groups")
                _set_child_text(img, "custom_loading_script",
                                _encode_str(_recolour_plot_script(script, chosen)))
                done["plots"] += 1
                continue
            if script.startswith(_MERGE_MARKER):
                m = re.search(r"^_colors = (\[.*\])$", script, re.M)
                if m:
                    cur = [tuple(c) for c in ast.literal_eval(m.group(1))]
                    new = [rgb[i] if i < len(rgb) else c for i, c in enumerate(cur)]
                    _note_extra(name, cur)
                    lit = "[" + ", ".join(repr(tuple(float(v) for v in c)) for c in new) + "]"
                    script = script[:m.start(1)] + lit + script[m.end(1):]
                    _set_child_text(img, "custom_loading_script", _encode_str(script))
                    done["merges"] += 1
                    # the merge of a split from separate channel files: its singles follow
                    synced.extend(_sync_split_colours(
                        container, img, [luts[i] if i < len(luts) else None
                                         for i in range(len(cur))]))
                continue
            if script.strip():
                continue                                   # other generated panels
            comment = str(_decode_text(_child_text(img, "user_comments"))).strip('"')
            s = _SPLIT_RE.match(comment)
            if s and s.group(4) != "merge":
                continue                                   # follows its merge below
            n = _channel_count_from_file(_first_filename(img)) or 0
            try:
                cur = ast.literal_eval(_child_text(img, "LUTs") or "None")
            except (ValueError, SyntaxError):
                cur = None
            if isinstance(cur, list) and len(cur) >= 2:
                n = max(n, len(cur))
            if n < 2:
                if single_channel == "keep":
                    if name:
                        left.append(name)
                    continue
                active = [x for x in (cur if isinstance(cur, list) else []) if x is not None]
                if active and str(active[0]).upper() != "GRAY":
                    _set_child_text(img, "LUTs", repr(["GRAY"]))
                    gray.append(name)
                continue
            if not isinstance(cur, list) and n == 3 and _looks_like_photograph(_first_filename(img)):
                photos.append(name)                        # a colour photograph, not channels
                continue
            if not isinstance(cur, list) or len(cur) != n:
                cur = [_COLOR_LUTS[c] for c in _DEFAULT_SPLIT_COLORS.get(n, ["red", "green",
                                                                            "blue"])][:n]
                cur += ["GRAY"] * (n - len(cur))
            new = [luts[i] if i < len(luts) and cur[i] is not None else cur[i] for i in range(n)]
            _note_extra(name, cur)
            _set_child_text(img, "LUTs", repr(new))
            synced.extend(_sync_split_colours(container, img, new))
            done["images"] += 1
        for g in [c for c in container if c.tag == "Group"]:
            content = g.find("content")
            if content is not None:
                visit(content)

    visit(root)
    if not any(done.values()) and not gray:
        return ("Nothing to recolour: no multi-channel image, merge or data plot."
                + (f" Left as they are: {', '.join(left + photos)}." if left or photos else ""))
    _save(tree, pyf_path)
    parts = [f"{done['images']} multi-channel image(s)", f"{done['merges']} channel merge(s)",
             f"{done['plots']} data plot(s)"]
    return (f"Figure colours set to {', '.join(names)} (channel order): "
            + ", ".join(parts)
            + (f"; channel splits matched: {', '.join(synced)}" if synced else "")
            + (f". Single-channel panels set to gray (single_channel='keep' keeps their LUT): "
               f"{', '.join(gray)}" if gray else "")
            + ((f". Plots use the colour-blind-safe Okabe-Ito palette" if colorblind else
                f". Plots with another number of groups ({', '.join(palette_plots)}) use the "
                f"colour-blind-safe Okabe-Ito palette instead") if palette_plots else "")
            + (f". Colour photographs left as they are: {', '.join(photos)}" if photos else "")
            + (f". Left as they are (single channel): {', '.join(left)}" if left else "") + "."
            + (f"\nWARNING: {len(names)} colour(s) for more channels: "
               + "; ".join(dict.fromkeys(kept_extra))
               + f" kept their colour. Tell the user which colour those channels have now, or "
               f"ask: for two colours on three channels, give every channel one, e.g. "
               f"[{', '.join(names[:2])}, {names[0]}] or [{', '.join(names[:2])}, gray]."
               if kept_extra else ""))


def _lut_name(c) -> str:
    """'MAGENTA' → 'magenta'; a merge colour (r, g, b) in 0..1 → its name."""
    if isinstance(c, (tuple, list)) and len(c) == 3:
        rgb = tuple(round(float(v)) for v in c)
        return {(1, 0, 0): "red", (0, 1, 0): "green", (0, 0, 1): "blue", (1, 0, 1): "magenta",
                (0, 1, 1): "cyan", (1, 1, 0): "yellow", (1, 1, 1): "gray"}.get(rgb, str(c))
    return str(c).lower()


def _decode_text(value) -> str:
    from .core import _decode
    v = _decode(value)
    return "" if v in (None, "None") else str(v)


def _configure_image_error(img, channels, z_start, z_end, series, normalization) -> str | None:
    """Why configure_image's values do not fit the panel's file, or None.
    Each of these used to be stored as given: a reversed or out-of-range Z
    range, a channel list of the wrong length or with every channel off, a
    series the file does not have, a normalization the renderer can't read."""
    from .core import _channel_count_from_file, _first_filename, _normalization_error
    if normalization is not None:
        bad = _normalization_error(normalization)
        if bad:
            return f"{bad}."
    fn = _first_filename(img)
    if channels is not None:
        if not any(bool(c) for c in channels):
            return "channels must show at least one channel (all were False)."
        n_ch = _channel_count_from_file(fn)
        if n_ch and len(channels) != n_ch:
            return f"channels has {len(channels)} value(s) but the file has {n_ch} channel(s)."
    if series is not None and series > 0 and isinstance(fn, str) and os.path.isfile(fn):
        # the reader falls back to the first series without a word
        n_series = None
        low = fn.lower()
        if low.endswith((".tif", ".tiff")):
            try:
                import tifffile
                with tifffile.TiffFile(fn) as t:
                    n_series = len(t.series)
            except Exception:
                pass
        elif low.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")):
            n_series = 1
        if n_series is not None and series >= n_series:
            return f"serie_to_open {series} does not exist: the file has {n_series} series (0-based)."
    starts = [v for v in (z_start, z_end) if v is not None and v >= 0]
    if not starts and (series is None or series < 0):
        return None
    if z_start is not None and z_end is not None and z_start >= 0 and z_end >= 0 \
            and z_start >= z_end:
        return (f"projection_z_start ({z_start}) must be below projection_z_end ({z_end}, "
                f"exclusive).")
    from pyfigures.stack_info import StackInfoError, stack_info
    try:
        info = stack_info(fn, series=series if series is not None and series >= 0 else None)
    except StackInfoError as e:
        if series is not None and series >= 0 and isinstance(fn, str) and os.path.isfile(fn):
            return f"series {series} cannot be opened: {e}."
        return None                      # unreadable here: leave the checks to the renderer
    n_z = info["sizes"].get("d")
    if starts and n_z:
        if z_start is not None and z_start >= n_z:
            return f"projection_z_start {z_start} is past the last slice (the file has {n_z} Z slices)."
        if z_end is not None and z_end > n_z:
            return f"projection_z_end {z_end} is past the end (the file has {n_z} Z slices, end is exclusive)."
    elif starts and not n_z:
        return "the file has no Z axis: projection_z_start/end do not apply."
    return None


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
    if not 0 <= image_index < len(imgs):
        return f"ERROR: image_index {image_index} out of range ({len(imgs)} images)."

    img = imgs[image_index]
    changed: list[str] = []
    bad = _configure_image_error(img, channels, projection_z_start, projection_z_end,
                                 serie_to_open, None if clear_normalization else normalization)
    if bad:
        return f"ERROR: {bad} Nothing was changed."
    if normalization is not None and not clear_normalization:
        from .core import _normalization_to_store
        normalization = _normalization_to_store(normalization)[0]

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
