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
    _append_new_panel,
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
    container, group_path = _append_new_panel(root, container, img, group_path)
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


_DATA_PLOT_KINDS = ("bar", "box", "violin", "scatter", "grouped", "split_violin", "paired", "line")
# the kinds drawn from a two-factor table (factor A, factor B, value)
_TWO_FACTOR_KINDS = ("grouped", "split_violin", "line")


# how a plot reads its table: some columns, some rows, lines skipped above the table
_TABLE_KEYS = ("columns", "where", "skip_rows")
# facets of a data plot (staplot.api.plot_facets): the column, a second one for rows, per row
_FACET_KEYS = ("facet", "facet_row", "facet_ncols")


def _plot_facet(csv_abs: str, values: dict, current: dict, skip_rows=None, where=None) -> tuple[dict, str]:
    """({facet, facet_row, facet_ncols} set, error): *current* with *values* changed ("" /
    0 clears one); each facet column checked on the table."""
    out = {k: current.get(k) for k in _FACET_KEYS if current.get(k) not in (None, "", 0)}
    for k in _FACET_KEYS:
        v = values.get(k)
        if v is None:
            continue
        if v in ("", 0, False, "none"):
            out.pop(k, None)
            if k == "facet":
                out.pop("facet_row", None)
            continue
        if k == "facet_ncols":
            try:
                v = int(v)
            except (TypeError, ValueError):
                return {}, f"facet_ncols must be a number of facets per row, not {v!r}"
            if not 1 <= v <= 12:
                return {}, "facet_ncols must be 1 to 12"
        else:
            try:
                from staplot.api import facet_levels
                v, _levels = facet_levels(csv_abs, str(v), where, skip_rows)
            except ImportError:
                v = str(v)
            except Exception as e:
                return {}, str(e)
        out[k] = v
    if out.get("facet_row") and not out.get("facet"):
        return {}, "facet_row needs a facet (the column of the facets side by side)"
    return out, ""


def _sel(values: dict) -> dict:
    """The table options among *values* that are set (skip_rows=0 is set)."""
    return {k: values[k] for k in _TABLE_KEYS if values.get(k) is not None and values.get(k) not in ("", [])}


def _auto_kind(table: str, columns=None, where=None, skip_rows=None) -> tuple[str | None, str]:
    """(kind, why) for kind="auto": staplot.api.suggest_kind (the plot that shows the
    table best: grouped for two factors, scatter for an x / y series, else bar / box /
    violin by the number of points per group); (None, why) when it cannot tell."""
    try:
        from staplot import api as _api
        pick = getattr(_api, "suggest_kind", None)
        if pick is None:
            return "bar", "staplot too old to choose; bar"
        rec = pick(table, **_sel({"columns": columns, "where": where, "skip_rows": skip_rows}))
        return rec.get("kind"), rec.get("reason", "")
    except ImportError:
        return "bar", "staplot is not installed"
    except Exception as e:
        return None, f"cannot read the table ({e})"


def _make_data_plot_script(csv_path: str, kind: str, error: str, annotate: bool,
                           only_significant: bool, title: str, ylabel: str,
                           xlabel: str, stats_mode: str = "auto", latex: bool = False,
                           colors: list | None = None, aspect: float | None = None,
                           layout: dict | None = None) -> str:
    """Return a custom_loading_script that renders a data-plot panel from a CSV
    via staplot's UI-free api. Soft dependency: if staplot is not importable the
    panel shows an install hint instead of crashing the figure. The panel is
    *live* — editing the CSV and reopening re-renders (and re-runs the stats).

    NB: no nested def()s — PyFigures exec's scripts with split globals/locals, so
    a nested function cannot see top-level imports (name 'np' not defined)."""
    builder = "grouped_table_from_csv" if kind in _TWO_FACTOR_KINDS else "table_from_csv"
    # width / height of the plot (a plot can take any shape, unlike an image), its size,
    # text size, group order, y axis, labels, legend: only what was asked
    layout = dict(layout or {})
    if aspect:
        layout["aspect"] = aspect
    aspect_kw = "".join(f", {k}={layout[k]!r}" for k in PLOT_LAYOUT_KEYS
                        if layout.get(k) not in (None, False, [], ""))
    # an axis label removed: none at all, not staplot's automatic "Value"
    aspect_kw += "".join(f", {k}=False" for k in ("show_ylabel", "show_xlabel", "show_points")
                         if layout.get(k) is False)
    # the columns of a wider (tidy) table the plot uses ("split by sex" from a sheet
    # holding genotype, treatment, sex, day, area)
    cols_kw = f", columns={list(layout['columns'])!r}" if layout.get("columns") else ""
    # only some rows ("only day 14", "only the males"): a pandas query on the table
    cols_kw += f", where={str(layout['where'])!r}" if layout.get("where") else ""
    # lines above the table skipped by hand (else found by staplot)
    cols_kw += f", skip_rows={int(layout['skip_rows'])}" if layout.get("skip_rows") is not None else ""
    # facets: one plot per value of a column ("one plot per day"), each with its statistics
    if layout.get("facet"):
        table_line = "_tbl = None                  # a faceted plot reads its table itself"
        plot_call = (f"_api.plot_facets(_csv, facet={layout['facet']!r}"
                     + (f", facet_row={layout['facet_row']!r}" if layout.get("facet_row") else "")
                     + (f", ncols={int(layout['facet_ncols'])}" if layout.get("facet_ncols") else "")
                     + f"{cols_kw}, kind=")
    else:
        table_line = f"_tbl = _api.{builder}(_csv{cols_kw})"
        plot_call = "_api.plot(_tbl, kind="
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
    {table_line}
    with _mpl.rc_context(_rc):
        fig, _rec = {plot_call}{kind!r}, error={error!r},
                              annotate={bool(annotate)!r},
                              only_significant={bool(only_significant)!r},
                              stats_mode={stats_mode!r},
                              colors={(dict(colors) if isinstance(colors, dict) else list(colors)) if colors else None!r},
                              title={title!r}, ylabel={ylabel!r}, xlabel={xlabel!r},
                              show_title={bool(title)!r}{aspect_kw})
    fig._pyf_rc = _rc
    # out of pyplot's list of open figures (every plot panel stayed there:
    # "More than 20 figures have been opened"); the panel draws it with savefig
    from matplotlib.backends.backend_agg import FigureCanvasAgg as _Agg
    import matplotlib.pyplot as _plt
    _Agg(fig)                    # its own canvas, so closing frees only pyplot's
    _plt.close(fig)
    self.img = fig
"""


# the layout / size settings of a data plot (staplot.api.plot), in the order they are written
PLOT_LAYOUT_KEYS = ("aspect", "width", "height", "font_scale", "order", "ylim", "log_y",
                    "xtick_rotation", "legend", "rename", "violin_inner", "violin_side", "element_colors",
                    "show_n", "show_mean", "p_format", "hlines", "control", "point_style", "normalize",
                    "pairs", "stats_text")
_LAYOUT_LIMITS = {"aspect": (0.2, 6), "width": (0.5, 20), "height": (0.5, 20), "font_scale": (0.3, 4)}


def _plot_skip(skip_rows) -> tuple[int | None, str]:
    """(lines to skip above the table, or None = found automatically; error)."""
    if skip_rows in (None, "", "auto"):
        return None, ""
    try:
        skip = int(skip_rows)
    except (TypeError, ValueError):
        return None, f"skip_rows must be a number of lines (or 'auto'), not {skip_rows!r}"
    if not 0 <= skip <= 10000:
        return None, "skip_rows must be 0 or more"
    return skip, ""


def _plot_where(csv_abs: str, where, skip_rows=None) -> tuple[str | None, str]:
    """(the row filter of a plot, a pandas query, or None; error): checked on the table."""
    if where in (None, "", 0, False):
        return None, ""
    where = str(where).strip()
    try:
        from staplot.api import read_table, select_columns
        select_columns(read_table(csv_abs, skip_rows), None, where)
    except ImportError:
        pass
    except Exception as e:
        return None, str(e)
    return where, ""


def _plot_columns(csv_abs: str, kind: str, columns, skip_rows=None) -> tuple[list | None, str]:
    """(the columns a plot uses, of a wider table, or None for the whole table; error).
    Two-factor kinds take three (factor on x, factor split / coloured, value); the others
    two (group, value) or one value column per group."""
    if columns in (None, "", [], 0, False):
        return None, ""
    cols = [columns] if isinstance(columns, str) else [str(c) for c in columns]
    want = {"grouped": 3, "split_violin": 3, "line": 3}.get(kind)
    if want and len(cols) != want:
        if kind == "line":
            return None, ("a line plot takes 3 columns: the groups (one line each), x (day, dose, time), "
                          "the value (e.g. ['genotype', 'day', 'length'])")
        return None, (f"a {kind} plot takes 3 columns: the factor on x, the factor "
                      f"{'split into the two halves' if kind == 'split_violin' else 'in colour'}, "
                      f"the value (e.g. ['genotype', 'sex', 'area'])")
    if not want and len(cols) < 2 and kind != "scatter":
        return None, ("give 2 columns (the group column, then the value column, e.g. "
                      "['genotype', 'area']) or one column per group")
    try:
        from staplot import api as _api
        from staplot.api import read_table, select_columns
        cols = [str(c) for c in select_columns(read_table(csv_abs, skip_rows), cols).columns]
    except ImportError:
        pass
    except Exception as e:
        return None, str(e)
    return cols, ""


def _plot_layout(kind: str, csv_abs: str, values: dict, current: dict | None = None,
                 columns=None, where=None, skip_rows=None) -> tuple[dict, str]:
    """(layout, error) for a data plot: *current* with the given *values* changed.
    A value of 0 / "" / [] / False clears a setting (back to staplot's default)."""
    out = {k: v for k, v in (current or {}).items()
           if k in PLOT_LAYOUT_KEYS and v not in (None, False, [], "")}
    for key, value in values.items():
        if value is None:
            continue
        if value is False or (not isinstance(value, bool) and value in (0, "", [], {})):
            out.pop(key, None)
            continue
        if key in _LAYOUT_LIMITS:
            try:
                value = float(value)
            except (TypeError, ValueError):
                return {}, f"{key} must be a number, not {value!r}"
            low, high = _LAYOUT_LIMITS[key]
            if not low <= value <= high:
                return {}, (f"{key} must be between {low} and {high}"
                            + (" (inches)" if key in ("width", "height") else ""))
        elif key == "xtick_rotation":
            try:
                value = float(value)
            except (TypeError, ValueError):
                return {}, f"xtick_rotation must be degrees, not {value!r}"
        elif key == "legend":
            value = str(value).strip().lower()
            if value not in ("inside", "outside", "none"):
                return {}, "legend must be 'inside', 'outside' or 'none'"
        elif key == "log_y":
            value = bool(value)
        elif key == "ylim":
            if isinstance(value, (int, float, str)) or len(value) != 2:
                return {}, "ylim must be [low, high] (null for an automatic end), e.g. [0, null]"
            try:
                value = [None if v is None else float(v) for v in value]
            except (TypeError, ValueError):
                return {}, "ylim must be two numbers (or null), e.g. [0, null]"
        elif key == "violin_inner":
            value = str(value).strip().lower()
            if value not in ("lines", "box", "none"):
                return {}, "violin_inner must be 'box' (a mini box plot), 'lines' (the default) or 'none'"
            if value == "lines":
                out.pop(key, None)
                continue
        elif key == "violin_side":
            value = {"half": "left", "true": "left", "full": "both", "whole": "both"}.get(
                str(value).strip().lower(), str(value).strip().lower())
            if value not in ("both", "left", "right"):
                return {}, ("violin_side must be 'left' or 'right' (half violins, the points on the other "
                            "side) or 'both' (whole violins, the default)")
            if value == "both":
                out.pop(key, None)
                continue
        elif key == "rename":
            if not isinstance(value, dict):
                return {}, 'rename must be {"old name": "new name", ...}'
            try:
                from staplot import api as _api
                names = ([c.name for c in _api.table_from_csv(csv_abs, **_sel({"columns": columns, "where": where,
                                                                         "skip_rows": skip_rows})).columns]
                         if kind not in _TWO_FACTOR_KINDS else None)
            except ImportError:
                names = None
            except Exception as e:
                return {}, f"cannot read the groups of {csv_abs}: {e}"
            if names is not None:
                low = {n.lower(): n for n in names}
                missing = [k for k in value if str(k).lower() not in low]
                if missing:
                    return {}, f"no group named {missing}; the groups are {names}"
                value = {low[str(k).lower()]: str(v) for k, v in value.items()}
            # names given before stay, the new ones are added
            value = {**(out.get("rename") or {}), **value}
        elif key in ("show_n", "show_mean", "stats_text"):
            value = bool(value)
            if key == "stats_text" and value and kind not in _TWO_FACTOR_KINDS:
                return {}, "stats_text (the two-way ANOVA written under the axes) applies to grouped, split_violin and line plots"
        elif key == "pairs":
            if kind not in ("bar", "box", "violin", "paired"):
                return {}, "pairs (the brackets drawn) applies to bar, box, violin and paired plots"
            if not isinstance(value, (list, tuple)) or not all(isinstance(p, (list, tuple)) and len(p) == 2
                                                               for p in value):
                return {}, 'pairs must be [["WT", "mutA"], ...]: two group names each'
            try:
                from staplot import api as _api
                names = [c.name for c in _api.table_from_csv(csv_abs, **_sel({"columns": columns, "where": where,
                                                                               "skip_rows": skip_rows})).columns]
            except ImportError:
                names = None
            except Exception as e:
                return {}, f"cannot read the groups of {csv_abs}: {e}"
            if names is not None:
                low = {n.lower(): n for n in names}
                bad = [p for p in value if str(p[0]).lower() not in low or str(p[1]).lower() not in low]
                if bad:
                    return {}, f"no group in {bad}; the groups are {names}"
                value = [[low[str(a).lower()], low[str(b).lower()]] for a, b in value]
        elif key == "point_style":
            value = {"beeswarm": "swarm", "bee swarm": "swarm", "swarmplot": "swarm", "random": "jitter",
                     "column": "line", "aligned": "line", "straight": "line"}.get(str(value).strip().lower(),
                                                                                str(value).strip().lower())
            if value not in ("jitter", "swarm", "line"):
                return {}, "point_style must be 'jitter' (random), 'swarm' (side by side) or 'line' (one column)"
            if value == "jitter":
                out.pop(key, None)
                continue
        elif key in ("control", "normalize"):
            if key == "control" and kind not in ("bar", "box", "violin"):
                return {}, "control (compare every group with one) applies to bar, box and violin plots"
            if key == "normalize" and kind not in ("bar", "box", "violin", "paired"):
                return {}, "normalize (values as % of a group) applies to bar, box, violin and paired plots"
            try:
                from staplot import api as _api
                names = [c.name for c in _api.table_from_csv(csv_abs, **_sel({"columns": columns, "where": where,
                                                                               "skip_rows": skip_rows})).columns]
            except ImportError:
                names = None
            except Exception as e:
                return {}, f"cannot read the groups of {csv_abs}: {e}"
            if names is not None:
                low = {n.lower(): n for n in names}
                if str(value).lower() not in low:
                    return {}, (f"no group named {value!r} to {'compare with' if key == 'control' else 'normalise to'}; "
                                f"the groups are {names}")
                value = low[str(value).lower()]
        elif key == "p_format":
            value = {"numbers": "p", "number": "p", "p-value": "p", "p-values": "p", "p value": "p",
                     "p values": "p", "pvalue": "p", "values": "p", "star": "stars", "asterisks": "stars"}.get(
                str(value).strip().lower(), str(value).strip().lower())
            if value not in ("stars", "p"):
                return {}, "p_format must be 'stars' (*, **, ***) or 'p' (the p-value itself, p = 0.0031)"
            if value == "stars":
                out.pop(key, None)
                continue
        elif key == "hlines":
            items = value if isinstance(value, (list, tuple)) else [value]
            fixed = []
            for item in items:
                spec = dict(item) if isinstance(item, dict) else {"y": item}
                try:
                    spec["y"] = float(spec["y"])
                except (KeyError, TypeError, ValueError):
                    return {}, ('hlines: numbers ([1.0]) or {"y": 100, "label": "control", "color": "grey", '
                                '"style": "--"}')
                fixed.append(spec if len(spec) > 1 else spec["y"])
            value = fixed
        elif key == "element_colors":
            if not isinstance(value, dict):
                return {}, 'element_colors must be {"points": "black", "median": "red", ...}'
            try:
                from staplot.api import PLOT_ELEMENTS
            except ImportError:
                PLOT_ELEMENTS = None
            from matplotlib.colors import to_rgba
            fixed = {}
            for part, colour in value.items():
                part = str(part).strip().lower().replace(" ", "_")
                part = {"point": "points", "dots": "points", "medians": "median", "outline": "edges",
                        "outlines": "edges", "edge": "edges", "bracket": "brackets", "stars": "brackets",
                        "error_bar": "error_bars", "errorbars": "error_bars", "whisker": "whiskers",
                        "regression": "fit", "regression_line": "fit", "line": "fit", "axis": "axes",
                        "outlier": "outliers"}.get(part, part)
                if PLOT_ELEMENTS is not None and part not in PLOT_ELEMENTS:
                    return {}, (f"no plot element {part!r}; the elements are {', '.join(PLOT_ELEMENTS)} "
                                f"(the groups' own colours: colors=[...])")
                if colour in (None, "", 0, False):
                    fixed[part] = None
                    continue
                try:
                    if str(colour).lower() != "none":
                        to_rgba(colour)
                except ValueError:
                    return {}, f"unknown colour {colour!r} for {part}: a name (red, black...) or #rrggbb"
                fixed[part] = str(colour)
            value = {k: v for k, v in {**(out.get("element_colors") or {}), **fixed}.items() if v is not None}
            if not value:
                out.pop(key, None)
                continue
        elif key == "order":
            if kind not in ("bar", "box", "violin", "paired"):
                return {}, "order (the groups' order) applies to bar, box, violin and paired plots"
            value = [str(v) for v in (value if isinstance(value, (list, tuple)) else [value])]
            try:
                from staplot import api as _api
                names = [c.name for c in _api.table_from_csv(csv_abs, **_sel({"columns": columns, "where": where,
                                                                         "skip_rows": skip_rows})).columns]
            except ImportError:
                names = None
            except Exception as e:
                return {}, f"cannot read the groups of {csv_abs}: {e}"
            if names is not None:
                low = {n.lower(): n for n in names}
                missing = [v for v in value if v.lower() not in low]
                if missing:
                    return {}, f"no group named {missing}; the groups are {names}"
                value = [low[v.lower()] for v in value]
        out[key] = value
    return out, ""


# the size of a plot's text and lines on the printed page (the journals' range for figure
# text is 5-8 pt; 7 pt reads well and fits them all), whatever the panel's size
PLOT_TEXT_PT = 7.0
PLOT_LINE_PT = 0.5


def _plot_text_on_page(img, font_pt: float | None = None) -> None:
    """Draw the plot panel *img* with its text at *font_pt* points ON THE PAGE (the
    exported figure): before, its text was set in the plot's own points and shrank or
    grew with the panel (7 pt in one figure, 16 pt in another). User, 2026-11-18:
    "plots should fit the text font recommended by journals by default unless the user
    explicitly asks for a given size"."""
    _set_child_text(img, "publication_style", "True")
    _set_child_text(img, "publication_font_on_page", "True")
    _set_child_text(img, "publication_font_size", f"{float(font_pt or PLOT_TEXT_PT):g}")
    _set_child_text(img, "publication_font_size_from_labels", "False")
    _set_child_text(img, "publication_line_width", f"{PLOT_LINE_PT:g}")


FOLLOW_LABELS = "figure"          # = batoolset.drawings.shapes.image2d.FOLLOW_LABELS
# the words that ask for a plot's text "like the labels" (font_family / font_pt)
_LIKE_LABELS = ("", "auto", "labels", "label", "figure", "default", "like the labels")


def _plot_text_like_labels(img, root, family: bool = True, size: bool = True) -> None:
    """The plot's text in the font (*family*) and at the size (*size*) of the figure's
    labels, the texts other than the panel letters (user, 2026-11-19: "use the same font
    for the graph as the image fonts", "the size of the label font", "label font is
    normally smaller than letter font"). Read again each time the plot is drawn, so the
    plot follows the labels when they change. The size kept in the file is the labels'
    size now, else 7 pt (never the letters' size)."""
    from .core import _other_text_size
    _set_child_text(img, "publication_style", "True")
    _set_child_text(img, "publication_font_on_page", "True")
    if img.find("publication_line_width") is None:
        _set_child_text(img, "publication_line_width", f"{PLOT_LINE_PT:g}")
    if family:
        _set_child_text(img, "publication_font", _encode_str(FOLLOW_LABELS))
    if size:
        _set_child_text(img, "publication_font_size", f"{float(_other_text_size(root) or PLOT_TEXT_PT):g}")
        _set_child_text(img, "publication_font_size_from_labels", "True")


def _plot_colours(colors) -> tuple[list | None, str]:
    """(matplotlib colours, error) for a plot's group colours: the figure's
    colour words (magenta, green…) take the tints the images use, anything
    else must be a colour matplotlib knows (#rrggbb, 'tab:blue'…)."""
    if not colors:
        return None, ""
    if isinstance(colors, str):
        colors = [colors]
    if isinstance(colors, dict):
        # a colour per group by name ({"WT": "black", "mutA": "red"})
        fixed = {}
        for name, c in colors.items():
            one, bad = _plot_colours([c])
            if bad:
                return None, bad
            fixed[str(name)] = one[0]
        return fixed, ""
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


def _check_colour_names(csv_abs: str, kind: str, colors, sel: dict) -> str:
    """'' or why colours given by group name do not fit the table's groups."""
    if not isinstance(colors, dict):
        return ""
    try:
        from staplot import api as _api
        table = (_api.grouped_table_from_csv(csv_abs, **sel) if kind in _TWO_FACTOR_KINDS
                 else _api.table_from_csv(csv_abs, **sel))
        _api._colors_by_name(table, kind, colors)
    except ImportError:
        return ""
    except Exception as e:
        return str(e)
    return ""


def data_plot_stats_entry(csv_abs: str, kind: str, only_significant: bool = True,
                          stats_mode: str = "auto", label=None, columns=None, where=None, skip_rows=None,
                          facet=None, facet_row=None, control=None):
    """(the figure's stats-provenance entry or None, a note for the reply, warnings) of a
    data plot: pairwise tests for bar/box/violin, two-way ANOVA for grouped, a
    correlation for scatter. Shared by add_data_plot and the GUI's dropped tables."""
    rec = None
    note = ""
    _mode = {"auto": None, "parametric": True, "nonparametric": False}.get(stats_mode)
    try:
        from staplot import api as _api
        _ckw = _sel({"columns": columns, "where": where, "skip_rows": skip_rows})
        if facet:
            recs = _api.facet_stats(csv_abs, kind, facet, facet_row, only_significant=only_significant,
                                    stats_mode=stats_mode, **_ckw, **({"control": control} if control else {}))
            entry = {"source": "data_plot", "panel_label": label, "csv": csv_abs, "kind": kind,
                     "facet": facet, "facet_row": facet_row, **_ckw,
                     "facets": {k: {f: r.get(f) for f in ("test", "omnibus", "comparisons", "effects",
                                                         "split_comparisons", "within_x", "r", "p", "error")
                                    if f in r}
                                for k, r in recs.items()}}
            tests = sorted({str(r.get("test")) for r in recs.values() if r.get("test")})
            return entry, f" — {len(recs)} facets, each tested ({', '.join(tests)})", []
        if kind == "paired":
            rec = _api.paired_test(_api.table_from_csv(csv_abs, **_ckw), only_significant=only_significant,
                                   parametric=_mode)
        elif kind in ("bar", "box", "violin"):
            rec = _api.auto_test(_api.table_from_csv(csv_abs, **_ckw), only_significant=only_significant,
                                 **({"control": control} if control else {}),
                                 parametric=_mode)
        elif kind in _TWO_FACTOR_KINDS:
            gt = _api.grouped_table_from_csv(csv_abs, **_ckw)
            rec = _api.two_way_test(gt)
            if kind == "split_violin" and "error" not in rec:
                rec["split_comparisons"] = _api.split_pair_tests(*_api.split_parts(gt), parametric=_mode)
            elif "error" not in rec and hasattr(_api, "within_x_tests"):
                rec["within_x"] = _api.within_x_tests(gt, parametric=_mode, only_significant=only_significant)
        elif kind == "scatter":
            rec = _api.correlation_test(_api.table_from_csv(csv_abs, **_ckw))
    except Exception as e:
        return None, f" (stats provenance skipped: {type(e).__name__})", []
    if not rec or "error" in rec:
        return None, note, []
    entry = {"source": "data_plot", "panel_label": label, "csv": csv_abs, "kind": kind,
             "test": rec.get("test")}
    if columns:
        entry["columns"] = list(columns)
    if where:
        entry["where"] = str(where)
    if skip_rows is not None:
        entry["skip_rows"] = int(skip_rows)
    warnings: list[str] = []
    if kind in ("bar", "box", "violin", "paired"):
        entry.update(omnibus=rec.get("omnibus"), correction=rec.get("correction"),
                     normality=rec.get("normality"), comparisons=rec.get("comparisons"))
        if rec.get("warnings"):
            entry["warnings"] = rec["warnings"]
        note = f" — {rec.get('test')}, {len(rec.get('sig_pairs', []))} significant pair(s) bracketed"
        warnings = list(rec.get("warnings", []))
    elif kind in _TWO_FACTOR_KINDS:
        entry.update(effects=rec.get("effects"))
        note = f" — {rec.get('test')} recorded"
        if rec.get("split_comparisons"):
            entry["split_comparisons"] = rec["split_comparisons"]
            note += ", each pair of halves compared"
        if rec.get("within_x"):
            entry["within_x"] = rec["within_x"]
            note += ", the groups compared at each x level (stars)"
    elif kind == "scatter":
        entry.update(r=rec.get("r"), r2=rec.get("r2"), p=rec.get("p"), n=rec.get("n"),
                     x=rec.get("x"), y=rec.get("y"))
        note = f" — {rec.get('test')} r={rec.get('r'):.3g}, p={rec.get('p'):.3g}"
    return entry, note, warnings


_EXCEL = (".xlsx", ".xlsm", ".xls")


def _is_excel(path: str) -> bool:
    """A workbook by its extension, or by its content when it has none (macOS)."""
    if str(path).lower().endswith(_EXCEL):
        return True
    try:
        from staplot.api import is_excel
    except ImportError:
        return False
    return is_excel(str(path))


def _table_path(path: str, sheet=None) -> tuple[str, str]:
    """(absolute table path, error) for a plot's table: a CSV / TSV / TXT, or an Excel
    workbook whose *sheet* (name or number from 1) is kept as "book.xlsx::Sheet" —
    the form the panel script and staplot read."""
    path = str(path)
    if "::" in path and sheet in (None, ""):
        path, sheet = path.split("::", 1)
    if not os.path.isfile(path):
        return "", f"no such table file: {path}"
    path = os.path.abspath(path)
    from pyfigures.plot_tables import is_sqlite_file
    if is_sqlite_file(path):
        # an SQLite database: *sheet* is a table / view (name or number from 1) or a query
        try:
            from staplot.api import list_sheets, read_table
            names = list_sheets(path)
        except ImportError as e:
            return "", str(e)
        except Exception as e:
            return "", f"cannot read {os.path.basename(path)} ({type(e).__name__}: {e})"
        if not names and sheet in (None, ""):
            return "", f"{os.path.basename(path)} holds no table"
        if sheet in (None, ""):
            return path, ""
        table = f"{path}::{sheet}"
        try:
            read_table(table)
        except Exception as e:
            return "", (f"{e}" if "no table" in str(e) else
                        f"cannot read {sheet!r} from {os.path.basename(path)} ({type(e).__name__}: {e}); "
                        f"its tables are {', '.join(names)}")
        return table, ""
    excel = _is_excel(path)
    if sheet not in (None, "") and not excel:
        return "", (f"sheet applies to Excel files (.xlsx, .xls) and SQLite databases only, not "
                    f"{os.path.basename(path)}")
    if not excel:
        return path, ""
    try:
        from staplot.api import list_sheets
        names = list_sheets(path)
    except ImportError as e:
        return "", str(e)
    except Exception as e:
        return "", f"cannot read {os.path.basename(path)} ({type(e).__name__}: {e})"
    if sheet in (None, ""):
        return path, ""
    sheet = str(sheet)
    if sheet not in names and not (sheet.strip().isdigit() and 1 <= int(sheet) <= len(names)):
        return "", f"no sheet {sheet!r} in {os.path.basename(path)}; its sheets are {', '.join(names)}"
    return f"{path}::{sheet}", ""


def _csv_number_count(path: str, skip_rows=None) -> int:
    """How many finite numbers a CSV holds (0 for an empty file or a header
    alone: the plot would be an empty frame)."""
    import csv
    from pyfigures.plot_tables import is_sqlite_file
    if skip_rows is not None:
        try:
            import pandas as pd
            from staplot.api import read_table
            df = read_table(path, skip_rows)
            return int(sum(pd.to_numeric(df[c], errors="coerce").notna().sum() for c in df.columns))
        except ImportError:
            pass
        except Exception:
            return 0
    if "::" in str(path) or _is_excel(str(path)) or is_sqlite_file(str(path)):
        try:
            import pandas as pd
            from staplot.api import read_table
            df = read_table(path)
            return int(sum(pd.to_numeric(df[c], errors="coerce").notna().sum() for c in df.columns))
        except Exception:
            return 0
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
    kind: str = "auto",
    error: str = "sd",              # SD, as journals prefer (user, 2026-11-18)
    annotate_stats: bool = True,
    only_significant: bool = True,
    label: str | None = None,
    label_placement: str = "top left",
    title: str = "",
    ylabel: str = "",
    xlabel: str = "",
    stats_mode: str = "auto",
    latex: bool = False,
    colors: list[str] | dict[str, str] | None = None,
    sheet: str | None = None,
    aspect: float | None = None,
    width: float | None = None,
    height: float | None = None,
    font_scale: float | None = None,
    order: list[str] | None = None,
    ylim: list[float | None] | None = None,
    log_y: bool | None = None,
    xtick_rotation: float | None = None,
    legend: str | None = None,
    font_pt: float | str | None = None,
    font_family: str | None = None,
    rename: dict[str, str] | None = None,
    show_points: bool | None = None,
    violin_inner: str | None = None,
    violin_side: str | None = None,
    columns: list[str] | None = None,
    where: str | None = None,
    skip_rows: int | str | None = None,
    element_colors: dict[str, str] | None = None,
    facet: str | None = None,
    facet_row: str | None = None,
    facet_ncols: int | None = None,
    show_n: bool | None = None,
    show_mean: bool | None = None,
    p_format: str | None = None,
    hlines: list | None = None,
    control: str | None = None,
    point_style: str | None = None,
    normalize: str | None = None,
    pairs: list[list[str]] | None = None,
    stats_text: bool | None = None,
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

    *csv_path*: a table of the data: CSV, TSV, TXT, an Excel workbook (.xlsx, .xls;
      *sheet* = the sheet's name or number from 1, else the first sheet), or an SQLite
      database (any name; *sheet* = a table or view by name or number from 1, or an
      SQL query "SELECT genotype, area FROM cells WHERE day = 3"; else the first table).
      - bar/box/violin/scatter: **wide** (one column per group, rows = replicates)
        or **long** (2 columns: group label, value).
      - grouped / split_violin: **long** with 3 columns: factor_a, factor_b, value.
    *columns*: the columns to use from a wider (tidy) table, by name: ["genotype",
      "area"] (group, value) for bar / box / violin; ["genotype", "sex", "area"] (factor
      on x, factor split or coloured, value) for split_violin / grouped. describe_table
      lists a table's columns and which are factors.
    *where*: only the rows matching this pandas query, on any column of the table:
      "day == 14", "sex == 'male'", "treatment == 'drug' and area > 100" (backquotes
      around names with spaces: "`cells per field` > 30"). The statistics use those rows.
    *skip_rows*: lines above the table to skip (an instrument's header, a title, notes):
      found automatically by default (the reply says what was skipped); a number skips
      that many, 0 none.
    *element_colors*: the colour of parts of the plot: {"points": "black", "median":
      "red", "edges": "none", "brackets": "#555555", "error_bars", "whiskers", "outliers",
      "inner", "fit", "axes", "background"}; the groups' own colours are *colors*.
    *facet*: one plot per value of this column, side by side, each with its own
      statistics ("one plot per day", "split by treatment": facet="day"), a shared y axis;
      *facet_row*: a second column, one row of facets per value (facet_grid);
      *facet_ncols*: facets per row (default up to 4). The facet columns are not among
      *columns*. The title goes over all the facets.
    Journal details: *show_n* the n of each group under its name; *show_mean* a mean
      marker (box, violin); *p_format* "p" writes the p-values on the brackets instead
      of stars; *hlines* reference lines: [1.0] or [{"y": 100, "label": "control"}].
    *control*: compare every group with this one only ("compare everything to WT"): one-way
      ANOVA + Dunnett's test, or Mann-Whitney against it (Bonferroni); bar, box, violin.
    *point_style*: the individual points "jitter" (default), "swarm" (side by side, never
      overlapping) or "line" (one column).
    *normalize*: a group's name: the values as a % of its mean ("normalise to WT", "% of
      control"); the y label says so unless given.
    *pairs*: brackets only for these pairs ([["WT", "mutA"]]: "only show WT vs mutA"); the
      p-values stay those of the whole test.
    *stats_text*: grouped / split_violin / line: True writes the two-way ANOVA under the
      axes ("show the ANOVA on the plot"); off by default, the plot shows stars only.
    The axis labels come from the table when not given: the value column's name on y
      (a long table, or columns=), the factor on x, the split / colour factor as the
      legend title.
    *kind*: "auto" (default: the plot that shows the data best — grouped for a
      two-factor table, scatter for an x / y series, else by the points per group:
      bar under 5, box 5-19, violin 20 or more) | "bar" | "box" | "violin" |
      "scatter" | "grouped". The reply says which kind auto chose and why.
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
    *aspect*: width / height of the plot (e.g. 1.5 for a wide plot); default: one
      0.9 in-wide column per group, 4 in tall.
    Layout and size (only when asked; edit_data_plot changes them later): *width* /
      *height* in inches (a smaller plot has relatively bigger text once scaled into
      its panel), *font_scale* (1.3 = text 30 % bigger), *order* (group names in the
      order to draw; groups left out are dropped and not tested), *ylim* [low, high]
      (null keeps an end automatic), *log_y*, *xtick_rotation* (degrees, for long
      group names), *legend* "inside" | "outside" | "none" (scatter, grouped), *rename*
      {"mutA": "mutant A"} (the name a group shows; the table is unchanged),
      *show_points* False (no individual points), *violin_inner* "box" | "lines" | "none",
      *violin_side* "left" | "right" (half violins, the points on the other side).
    *kind="split_violin"*: two conditions as the two halves of each violin ("split by
      sex", "half violins per condition"): a two-factor table (e.g. genotype, sex, value)
      where one factor has two levels; a legend names the halves, each pair is tested.
    *font_pt*: the size of the plot's text in the printed figure, in points; only when
      the user asks for a size. Default: the size of the figure's labels (not the
      letters), else 7 pt, whatever the panel's size; the plot follows the labels.
    *font_family*: the plot's font; default the font of the figure's labels (followed).
    *colors*: one colour per group, in the CSV's order (names such as magenta /
      green or #rrggbb); groups beyond the list keep the default palette. Or by name:
      {"WT": "black", "mutA": "red"} (the groups not named keep theirs).
      set_figure_colors recolours plots and images together.

    For *kind="scatter"* the correlation (r, R^2, p) of the first two columns is
    shown in the legend and recorded; for *kind="grouped"* / *"line"* the groups are
    compared at each x level (stars; Tukey / Dunn within the level) and the two-way ANOVA
    (main effects + interaction) is recorded, for the legend text; *stats_text=True*
    also writes it under the axes (off by default: not elegant on a figure).

    *group_path*: [] for free-canvas, [0] for top-level group 0, [0,1] sub-group.

    Example — box plot of three conditions with auto-stats::

        add_data_plot("fig.pyf", [0], "counts.csv", kind="box",
                      ylabel="cells / field", label="D")
    """
    kind = (kind or "auto").lower()
    if kind not in _DATA_PLOT_KINDS + ("auto",):
        return f"ERROR: kind must be 'auto' or one of {_DATA_PLOT_KINDS}."
    if error not in ("sem", "sd", "ci95", "none"):
        return "ERROR: error must be 'sem', 'sd', 'ci95' or 'none'."
    if stats_mode not in ("auto", "parametric", "nonparametric"):
        return (f"ERROR: stats_mode must be 'auto', 'parametric' or 'nonparametric', not "
                f"{stats_mode!r}: the test itself is chosen from the data (t-test / ANOVA "
                f"are 'parametric', Mann-Whitney / Kruskal-Wallis 'nonparametric').")
    csv_path, bad = _table_path(csv_path, sheet)
    if bad:
        return f"ERROR: {bad}"
    csv_abs = csv_path
    skip_rows, bad = _plot_skip(skip_rows)
    if bad:
        return f"ERROR: {bad}; nothing was added."
    if not _csv_number_count(csv_abs, skip_rows):
        return (f"ERROR: {csv_path} holds no numbers to plot (empty, or a header without "
                f"values); nothing was added.")
    auto_note = ""
    if kind == "auto":
        where, bad = _plot_where(csv_abs, where, skip_rows)
        if bad:
            return f"ERROR: {bad}; nothing was added."
        kind, why = _auto_kind(csv_abs, columns, where, skip_rows)
        if not kind:
            return f"ERROR: no plot kind fits this table on its own: {why}. Nothing was added."
        auto_note = f"\nKIND: auto chose {kind}: {why}. Say so; edit_data_plot kind changes it."
    columns, bad = _plot_columns(csv_abs, kind, columns, skip_rows)
    if bad:
        return f"ERROR: {bad}; nothing was added."
    where, bad = _plot_where(csv_abs, where, skip_rows)
    if bad:
        return f"ERROR: {bad}; nothing was added."
    _ckw = _sel({"columns": columns, "where": where, "skip_rows": skip_rows})
    if kind in _TWO_FACTOR_KINDS:
        try:
            from staplot import api as _api
            gt = _api.grouped_table_from_csv(csv_abs, **_ckw)
            if kind == "split_violin":
                _api.split_parts(gt)
        except ImportError:
            pass                        # the panel says staplot is missing
        except (ValueError, AttributeError) as e:
            return f"ERROR: {e}; nothing was added."

    plot_colors, bad = _plot_colours(colors)
    if bad:
        return f"ERROR: {bad}"
    bad = _check_colour_names(csv_abs, kind, plot_colors, _ckw)
    if bad:
        return f"ERROR: {bad}; nothing was added."
    layout, bad = _plot_layout(kind, csv_abs,
                               {"aspect": aspect, "width": width, "height": height, "font_scale": font_scale,
                                "order": order, "ylim": ylim, "log_y": log_y,
                                "xtick_rotation": xtick_rotation, "legend": legend,
                                "rename": rename, "violin_inner": violin_inner,
                                "violin_side": violin_side, "element_colors": element_colors,
                                "show_n": show_n, "show_mean": show_mean, "p_format": p_format,
                                "hlines": hlines, "control": control, "point_style": point_style,
                                "normalize": normalize, "pairs": pairs, "stats_text": stats_text},
                               columns=columns, where=where, skip_rows=skip_rows)
    if bad:
        return f"ERROR: {bad}; nothing was added."
    if show_points is False:
        layout["show_points"] = False
    if columns:
        layout["columns"] = columns
    if where:
        layout["where"] = where
    if skip_rows is not None:
        layout["skip_rows"] = skip_rows
    facets, bad = _plot_facet(csv_abs, {"facet": facet, "facet_row": facet_row, "facet_ncols": facet_ncols},
                              {}, skip_rows, where)
    if bad:
        return f"ERROR: {bad}; nothing was added."
    layout.update(facets)
    script = _make_data_plot_script(csv_abs, kind, error, annotate_stats,
                                    only_significant, title, ylabel, xlabel,
                                    stats_mode, latex=latex, colors=plot_colors, layout=layout)

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__data_plot__")
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    like_labels = font_pt is None or (isinstance(font_pt, str) and font_pt.strip().lower() in _LIKE_LABELS)
    if not like_labels:
        try:
            font_pt = float(font_pt)
        except (TypeError, ValueError):
            return (f"ERROR: font_pt is the plot's text size in points on the page, or \"labels\" (the size "
                    f"of the figure's labels); got {font_pt!r}. Nothing was changed.")
    _plot_text_on_page(img, None if like_labels else font_pt)
    _plot_text_like_labels(img, root, size=like_labels)
    if font_family and font_family.strip().lower() not in _LIKE_LABELS:
        from .core import _warn_missing_font
        _set_child_text(img, "publication_font", _encode_str(font_family.strip()))
        _warn_missing_font(font_family.strip())
    if label:
        img.find("annotations").append(_new_tatext2d(label, label_placement))
    container, group_path = _append_new_panel(root, container, img, group_path)
    _save(tree, pyf_path, recompute=True)
    idx = len([c for c in container if c.tag == "Image2D"]) - 1

    # record stats provenance at add time (soft dep). Group comparisons
    # (bar/box/violin) get pairwise tests; grouped gets two-way ANOVA; scatter
    # gets a correlation.
    stats_note = ""
    stats_warnings: list[str] = []
    if annotate_stats:
        entry, stats_note, stats_warnings = data_plot_stats_entry(csv_abs, kind, only_significant,
                                                                  stats_mode, label, **_ckw,
                                                                  facet=facets.get("facet"),
                                                                  facet_row=facets.get("facet_row"),
                                                                  control=layout.get("control"))
        if entry:
            _append_stats_entry(pyf_path, entry)

    loc = "canvas" if not group_path else f"group {group_path}"
    suffix = f' with label "{label}"' if label else ""
    # say what the plot leaves out of the CSV (empty / NA / text cells): tell the user
    from pyfigures.assistant.plot_info import data_cleaning
    cleaning = data_cleaning({"csv": csv_abs, "kind": kind, **_ckw})
    cleaning_note = (f"\nDATA: {cleaning} Tell the user what was left out."
                     if cleaning and ("no value left out" not in cleaning or "skipped" in cleaning) else "")
    return (
        f"Data-plot panel ({kind}) added as index {idx} in {loc}{suffix} from "
        f"{os.path.basename(csv_abs)}{stats_note}. Reopen the figure in PyFigures "
        f"to render it."
        + "".join(f"\nNOTE: {w}" for w in stats_warnings)
        + cleaning_note + auto_note
    )


@mcp.tool()
def match_display_range(
    pyf_path: str,
    files: list[str] | None = None,
    low_percentile: float = 0.1,
    high_percentile: float = 99.9,
    min_value: float | None = None,
    max_value: float | None = None,
) -> str:
    """Give image panels ONE SHARED display range, so their brightness can honestly be
    compared: "same brightness and contrast so they're comparable", "same display
    settings for WT and mutant", "don't auto-scale each image". The range is computed
    from all the chosen panels' pixels together (low/high percentiles), or given
    (*min_value* / *max_value*), and set identically on each: a pixel value then looks the
    same in every panel. Never use per-channel auto-normalisation for this: it stretches
    each image to its own range and makes them NOT comparable.

    *files*: the source file names (as in panel_references source_file) of the panels to
      match; None = every image panel (plots and drawings are left alone). Match only
      images of the same kind of acquisition (same stain, same settings).
    *low_percentile* / *high_percentile*: the shared range's ends, in percent of all their
      pixels (0.1 and 99.9 by default).
    """
    import numpy as np
    from batoolset.img import Img
    from .core import _decode
    if not 0 <= low_percentile < high_percentile <= 100:
        return "ERROR: need 0 <= low_percentile < high_percentile <= 100. Nothing was changed."
    if (min_value is None) != (max_value is None) or (min_value is not None and min_value >= max_value):
        return "ERROR: give both min_value and max_value (min < max), or neither. Nothing was changed."
    wanted = {os.path.basename(str(f)).lower() for f in files} if files else None
    tree, root = _load(pyf_path)
    chosen = []
    for img in root.iter("Image2D"):
        if (_decode(img.findtext("isText")) or "False") not in ("False", "None"):
            continue
        name = _first_filename(img)
        script = _decode_text(_child_text(img, "custom_loading_script"))
        if not name or str(name) in ("None", "__data_plot__") or (script and script.strip() not in ("", "None")):
            continue
        if str(name).lower().endswith((".svg", ".pdf", ".eps")):
            continue
        if wanted is not None and os.path.basename(str(name)).lower() not in wanted:
            continue
        chosen.append((img, str(name)))
    if wanted is not None:
        found = {os.path.basename(n).lower() for _, n in chosen}
        missing = sorted(wanted - found)
        if missing:
            return f"ERROR: no image panel shows {missing}. Nothing was changed."
    if len(chosen) < 2 and min_value is None:
        return "ERROR: a shared range needs at least two image panels. Nothing was changed."
    dtypes = set()
    if min_value is None:
        samples = []
        rng = np.random.default_rng(0)
        for _, name in chosen:
            try:
                a = np.asarray(Img(name))
            except Exception as e:
                return f"ERROR: could not read {os.path.basename(name)} ({type(e).__name__}). Nothing was changed."
            dtypes.add(str(a.dtype))
            flat = a.reshape(-1)
            if flat.size > 1_000_000:
                flat = flat[rng.integers(0, flat.size, 1_000_000)]
            samples.append(flat.astype(np.float64))
        pooled = np.concatenate(samples)
        min_value, max_value = (float(v) for v in np.percentile(pooled, [low_percentile, high_percentile]))
        if max_value <= min_value:
            return "ERROR: these images are uniform over that range; nothing to stretch. Nothing was changed."
    text = repr({"range": "custom", "min_value": min_value, "max_value": max_value})
    for img, _ in chosen:
        _set_child_text(img, "normalization", text)
    _save(tree, pyf_path)
    names = ", ".join(os.path.basename(n) for _, n in chosen)
    note = (f" NOTE: the images have different pixel types ({', '.join(sorted(dtypes))}): one range rarely "
            f"suits them all; match images of the same acquisition only." if len(dtypes) > 1 else "")
    return (f"One shared display range {min_value:g}–{max_value:g} set on {len(chosen)} panel(s): {names}. "
            f"Equal pixel values now look the same in each.{note}")


def plot_panel_code(script: str) -> str | None:
    """The Python code of a plot panel's script, to read or run outside PyFigures, or None
    when the panel is not a plot (shared by data_plot_code and the GUI's Show plot code)."""
    from pyfigures.assistant.plot_info import parse_data_plot, data_plot_code as _code
    spec = parse_data_plot(script)
    if spec:
        return _code(spec)
    from pyfigures.seaborn_plot import parse as parse_seaborn
    if parse_seaborn(script) is not None:
        return ("# A seaborn plot made by PyFigures; runs on its own (pandas, seaborn, matplotlib).\n"
                "class _Panel:\n    img = None\n\n\nself = _Panel()\n\n" + script.split("\n", 1)[1] +
                '\n\nself.img.savefig("plot.pdf")            # vector; or .png / .svg\n')
    from pyfigures.table_panel import parse as parse_table, table_code
    table = parse_table(script)
    if table is not None:
        return table_code(table)
    return None


@mcp.tool()
def data_plot_code(pyf_path: str, group_path: list[int], image_index: int, out_path: str | None = None) -> str:
    """The **Python code of a plot panel** ("show me the code of this plot", "how was it
    made?", "give me the script so I can redo it"): for a data plot, a script that redraws
    it with staplot and then reads the table with pandas (as the plot reads it: separator,
    decimal comma, Excel sheet, left-out cells) and runs the same test with scipy /
    statsmodels alone, so the statistics can be checked without PyFigures; for a seaborn
    plot, its seaborn code. *out_path*: also save it as a .py file.
    To change the plot, use edit_data_plot / edit_seaborn_plot, not this code."""
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    images = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(images):
        return f"ERROR: image_index {image_index} out of range (0..{len(images) - 1})"
    code = plot_panel_code(_decode_text(_child_text(images[image_index], "custom_loading_script")))
    if code is None:
        return ("ERROR: this panel is not a data plot or a seaborn plot (add_data_plot / add_seaborn_plot); "
                "a script panel's code is read with get_script.")
    if out_path:
        if not out_path.lower().endswith(".py"):
            return "ERROR: out_path must end in .py"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(code)
        return f"Saved to {out_path}.\n\n{code}"
    return code


@mcp.tool()
def list_data_plot_kinds() -> str:
    """The kinds of data plot PyFigures draws from a CSV (add_data_plot, edit_data_plot),
    with what each shows and what each can hold. Read-only. Use it for "what plot types
    are there?", "which plot should I use?", "what can I put inside my violin plot?",
    "what can I change on this plot?"."""
    from pyfigures.assistant.plot_info import PLOT_KINDS
    from pyfigures.seaborn_plot import describe_functions
    return ("Data-plot kinds with statistics (add_data_plot to add one, edit_data_plot to switch an existing plot):\n"
            + "\n".join(f"- {k}: {v}" for k, v in PLOT_KINDS.items())
            + "\nkind='auto' (the default) picks the one that shows the data best and says why."
            + "\n\nWhat each can show (edit_data_plot):"
            + "\n- violin, inside each violin (violin_inner): 'lines' (default: a thin line over the range, a thick "
              "one over the quartiles, a white median dot), 'box' (a mini box plot: quartile box, median line, "
              "whiskers to 1.5 IQR) or 'none' (the shape alone); plus the individual points or not (show_points); "
              "half violins (violin_side='left' or 'right': the half shape, the points on the open side, a "
              "'raincloud')."
            + "\n- split_violin: two conditions (sex, treatment...) as the two halves of each violin, one "
              "violin per level of the other factor, a legend naming the halves above the plot; each pair "
              "of halves tested (t-test or Mann-Whitney) and the two-way ANOVA under the plot. Needs a "
              "two-factor table (factor A, factor B, value) with a two-level factor. Split violins in "
              "facets (e.g. one facet per treatment): add_seaborn_plot function='catplot', kind='violin', "
              "hue='sex', col='treatment', options={'split': true}."
            + "\n- box: median, quartiles, whiskers to 1.5 IQR and outliers; individual points or not (show_points)."
            + "\n- bar: mean with error bars (sd, sem, ci95, none); individual points or not (show_points)."
            + "\n- scatter: the points of each y column against the first column, a regression line with R² "
              "and p; each series its own colour and marker shape; legend inside / outside / none."
            + "\n- paired: repeated measures (one row per subject, one column per condition: before / "
              "after, day 1 / 2 / 3): every subject's values joined by a line, the mean and SD beside them; a "
              "paired t-test or Wilcoxon signed-rank (2 conditions), a repeated-measures ANOVA or Friedman "
              "then paired tests (more)."
            + "\n- line: a time course / dose response: the mean ± error of each group (one line, colour "
              "and marker each) across x (day, dose, time; spaced as numbers when they read as numbers), "
              "points optional (show_points), a two-way ANOVA (group, x, interaction) under it. Columns: "
              "group, x, value (columns=['genotype', 'day', 'length'])."
            + "\n- grouped: bars by two factors with error bars and every point, a two-way ANOVA under them; "
              "legend inside / outside / none."
            + "\n- facets (every kind): facet='day' draws one plot per day side by side, each with its own "
              "statistics and a shared y axis; facet_row='sex' a grid; facet_ncols per row."
            + "\n- colours: colors=[one per group]; element_colors={'points': 'black', 'median': 'red', "
              "'edges': 'none', 'brackets': 'grey', 'error_bars', 'whiskers', 'outliers', 'inner', 'fit', "
              "'axes', 'background'}."
            + "\n- normalised values: normalize='WT' = every value as a % of WT's mean (the y label says "
              "'% of WT'); the tests are unchanged by the scaling."
            + "\n- comparisons against one control only: control='WT' (one-way ANOVA + Dunnett's test, or "
              "Mann-Whitney against it with Bonferroni); bar, box, violin."
            + "\n- journal details (every kind with groups): show_n=True (n under each name), show_mean=True "
              "(a mean marker, box / violin), p_format='p' (p-values written instead of stars), hlines=[1.0] "
              "or [{'y': 100, 'label': 'control'}] (reference lines)."
            + "\n- the table: columns=[...] of a tidy table, where='day == 14' (some rows), skip_rows (lines "
              "above the table, found automatically); axis labels come from the column names."
            + "\nCombinations in one plot: violin + mini box (violin_inner='box'), half violin + points "
              "(violin_side='left'), split violin + mini boxes, violin + range/quartile "
              "lines (the default), violin / box / bar + the individual points (show_points), scatter + "
              "regression line. Other combinations (a bar over a violin, two kinds side by side in one "
              "panel) are not drawn: make two panels, or a seaborn plot."
            + "\n- every kind: group names shown (rename), group order (order), y range (ylim), log y, tilted "
              "names (xtick_rotation), legend place, text size on the page (font_pt), shape and size (aspect, "
              "width, height), axis labels, colours, statistics on / off and which brackets.\n"
            + "\nError bars (bar, grouped): sem, sd, ci95 or none. Statistics: automatic test (parametric "
              "or not from a normality check), or stats_mode='parametric' / 'nonparametric'; brackets for "
              "every tested pair or only the significant ones.\n\n" + describe_functions())



def _read_any_table(csv_path: str, sheet=None, skip_rows=None):
    """(DataFrame, table path, error) of a CSV / TSV / TXT, an Excel sheet or an SQLite
    table / query, read as the plots read it (staplot.api.read_table, pandas)."""
    table, bad = _table_path(csv_path, sheet)
    if bad:
        return None, "", bad
    try:
        from staplot.api import read_table
        df = read_table(table, *(() if skip_rows in (None, "", "auto") else (int(skip_rows),)))
    except ImportError:
        import pandas as pd
        try:
            df = pd.read_csv(table, sep=None, engine="python")
        except Exception as e:
            return None, table, f"cannot read {os.path.basename(table)} ({type(e).__name__}: {e})"
    except Exception as e:
        return None, table, f"cannot read {os.path.basename(table)} ({type(e).__name__}: {e})"
    return df, table, ""


def table_factors(df, max_levels: int = 20) -> list[dict]:
    """The columns of *df* that can split the data into groups (factors): text columns,
    and number columns with few distinct values (day 1 / 2 / 3, a 0 / 1 code), each
    with its levels and their counts and what it can do in a plot."""
    import pandas as pd
    out = []
    n = max(1, len(df))
    for c in df.columns:
        col = df[c].dropna()
        if col.empty:
            continue
        num = pd.to_numeric(col, errors="coerce")
        is_number = num.notna().sum() >= len(col) * 0.8
        levels = col.astype(str).str.strip().value_counts(sort=False)
        k = len(levels)
        if k < 2 or k > max_levels:
            continue
        if is_number and (k > 6 or k > n / 3):
            continue                           # a measurement, not a code
        uses = ["x groups", "hue (colour)", "facets (col / row)"]
        if k == 2:
            uses.insert(1, "split violin halves")
        out.append({"column": str(c), "type": "numbers" if is_number else "text",
                    "levels": {str(a): int(b) for a, b in levels.items()}, "uses": uses})
    return out


@mcp.tool()
def list_factor_columns(csv_path: str, sheet: str | None = None, max_levels: int = 20,
                        skip_rows: int | None = None) -> str:
    """The FACTOR columns of a data table: the ones that can split the data into groups
    (text columns such as genotype, sex, treatment; number columns with few values such
    as day 1 / 2 / 3), each with its levels and their counts and what it can be in a plot:
    x groups, the two halves of a split violin (two levels), hue, facets. Also the number
    columns (the values to plot). Read-only. Use it for "which columns can I split /
    facet / colour by?", "what are the factors of this table?".

    *csv_path*: CSV, TSV, TXT, Excel workbook or SQLite database. *sheet*: an Excel sheet,
      an SQLite table or query. *max_levels*: a column with more levels is not a factor.
    """
    import pandas as pd
    df, table, bad = _read_any_table(csv_path, sheet, skip_rows)
    if bad:
        return f"ERROR: {bad}"
    factors = table_factors(df, max_levels=max_levels)
    names = {f["column"] for f in factors}
    values = [str(c) for c in df.columns if str(c) not in names
              and pd.to_numeric(df[c], errors="coerce").notna().sum() >= max(1, df[c].notna().sum() * 0.8)]
    lines = [f"{os.path.basename(table)}: {len(df)} rows."]
    if not factors:
        lines.append("No factor column (no text column, nor a number column with a few values): a wide "
                     "table, one column per group.")
    else:
        lines.append("Factor columns:")
        for f in factors:
            lv = ", ".join(f"{k} ({v})" for k, v in f["levels"].items())
            lines.append(f"- {f['column']} ({f['type']}, {len(f['levels'])} levels: {lv}): "
                         + ", ".join(f["uses"]))
    if values:
        lines.append("Value columns (numbers): " + ", ".join(values))
    two = [f["column"] for f in factors if len(f["levels"]) == 2]
    many = [f["column"] for f in factors if len(f["levels"]) > 2]
    if factors and values:
        x = (many or [f["column"] for f in factors])[0]
        lines.append("E.g. add_data_plot kind='violin', columns=['%s', '%s']" % (x, values[0]))
        if two:
            other = next((f["column"] for f in factors if f["column"] != two[0]), None)
            if other:
                lines.append(f"     add_data_plot kind='split_violin', columns=['{other}', '{two[0]}', "
                             f"'{values[0]}'] (halves = {two[0]})")
            rest = [f["column"] for f in factors if f["column"] not in (two[0], other)]
            lines.append(f"     add_seaborn_plot function='catplot', kind='violin', x='{other or two[0]}', "
                         f"y='{values[0]}', hue='{two[0]}', options={{'split': true}}"
                         + (f", col='{rest[0]}' (one facet per {rest[0]})" if rest else ""))
    return "\n".join(lines)


@mcp.tool()
def describe_table(csv_path: str, sheet: str | None = None, rows: int = 5,
                   skip_rows: int | None = None) -> str:
    """What a data table holds, read with pandas as the plots read it: its sheets (Excel)
    or tables (SQLite), the number of rows, each column with its type, missing cells,
    range (numbers) or levels and their counts (text), the first *rows* rows, and which
    plots fit it (a column with two levels can split violins; text columns can be
    seaborn hue / col / row facets). Read-only. Use it BEFORE add_data_plot /
    add_seaborn_plot when the column names are not known ("what's in this table?",
    "which columns can I facet by?", "show me the data").

    *csv_path*: CSV, TSV, TXT, an Excel workbook or an SQLite database ("file::sheet" or
      "file::SELECT ..." works too). *sheet*: an Excel sheet, an SQLite table or query.
    *skip_rows*: lines above the table to skip (default: found automatically, and said).
    """
    import numpy as np
    import pandas as pd
    df, table, bad = _read_any_table(csv_path, sheet, skip_rows)
    if bad:
        return f"ERROR: {bad}"
    from pyfigures.plot_tables import split_sheet
    file, part = split_sheet(table)
    lines = [f"Table {os.path.basename(file)}{(' ' + part) if part else ''}: {len(df)} rows, "
             f"{df.shape[1]} columns."]
    skipped = df.attrs.get("skipped_lines") or []
    if skipped:
        lines.append(f"Skipped above the table ({len(skipped)} line(s); skip_rows=0 keeps them): "
                     + " | ".join(str(t)[:60] for t in skipped[:5]))
    try:
        from staplot.api import list_sheets
        others = list_sheets(file)
        if others:
            lines.append(("Sheets: " if _is_excel(file) else "Tables / views: ")
                         + ", ".join(others))
    except Exception:
        pass
    text_cols, two_level, numeric = [], [], []
    lines.append("Columns:")
    for c in df.columns:
        col = df[c]
        missing = int(col.isna().sum())
        miss = f", {missing} missing" if missing else ""
        num = pd.to_numeric(col, errors="coerce")
        if num.notna().sum() and num.notna().sum() >= col.notna().sum() * 0.8:
            numeric.append(str(c))
            levels = num.dropna().unique()
            extra = (f", {len(levels)} distinct values" if len(levels) <= 6 else "")
            lines.append(f"- {c!s}: numbers, {num.min():.4g} to {num.max():.4g}, mean {num.mean():.4g}"
                         f"{extra}{miss}")
        else:
            counts = col.dropna().astype(str).value_counts(sort=False)
            text_cols.append(str(c))
            if len(counts) == 2:
                two_level.append(str(c))
            shown = ", ".join(f"{k} ({v})" for k, v in list(counts.items())[:12])
            more = f", ... {len(counts) - 12} more" if len(counts) > 12 else ""
            lines.append(f"- {c!s}: text, {len(counts)} levels: {shown}{more}{miss}")
    with pd.option_context("display.max_columns", 30, "display.width", 200):
        lines.append(f"First {min(rows, len(df))} rows:\n" + df.head(max(0, int(rows))).to_string(index=False))
    fit = []
    try:
        from staplot.api import suggest_kind
        rec = suggest_kind(table)
        if rec.get("kind"):
            fit.append(f"add_data_plot kind='auto' would draw {rec['kind']} ({rec.get('reason', '')})")
        else:
            fit.append(f"add_data_plot: {rec.get('reason', '')}")
    except Exception:
        pass
    if text_cols and numeric:
        fit.append(f"seaborn (add_seaborn_plot): y = a number column ({', '.join(numeric[:6])}); x, hue, "
                   f"col / row facets = text columns ({', '.join(text_cols[:6])})")
    if two_level and numeric:
        fit.append(f"split violins by {', '.join(two_level)} (two levels): add_seaborn_plot "
                   f"function='violinplot' or 'catplot' kind='violin', hue='{two_level[0]}', "
                   "options={'split': true} (+ col= for facets); or add_data_plot "
                   f"kind='split_violin', columns=[a factor, '{two_level[0]}', a value column] "
                   "(with statistics)")
    if text_cols and numeric and df.shape[1] > 3:
        fit.append("add_data_plot on some columns only: columns=[factor, value] for bar / box / violin "
                   "(e.g. " + repr([text_cols[0], numeric[0]]) + "), [factor, factor, value] for "
                   "grouped / split_violin; list_factor_columns lists the factors")
    factors = table_factors(df)
    if factors:
        lines.append("Factor columns (x groups, hue, facets; two levels = split violin halves): "
                     + "; ".join(f"{f['column']} ({len(f['levels'])} levels)" for f in factors))
    if fit:
        lines.append("Plots that fit:\n" + "\n".join(f"- {f}" for f in fit))
    return "\n".join(lines)


@mcp.tool()
def summarize_table(csv_path: str, value: str | None = None, by: list[str] | str | None = None,
                    where: str | None = None, sheet: str | None = None,
                    skip_rows: int | None = None, out_path: str | None = None) -> str:
    """Numbers of a data table by group, with pandas: n, mean, sd, sem, median, min and
    max of *value* for each combination of the *by* columns ("mean area per genotype and
    sex", "how many cells per day?"). Read-only; nothing is plotted or changed.

    *value*: a number column (None = every number column). *by*: one column or a list
      (None = the whole table). *where*: rows to keep, as a pandas query
      ("day == 3", "treatment == 'drug' and area > 100"; backquote names with spaces:
      "`cells per field` > 30"). *sheet*: an Excel sheet, an SQLite table or query.
    *out_path*: also save the summary there (.csv, .xlsx: one sheet per value), e.g. for
      the source data of a figure; nothing else is written.
    """
    import pandas as pd
    df, table, bad = _read_any_table(csv_path, sheet, skip_rows)
    if bad:
        return f"ERROR: {bad}"
    low = {str(c).lower(): c for c in df.columns}

    def col(name):
        return low.get(str(name).strip().lower())
    if where:
        try:
            df = df.query(str(where), engine="python")
        except Exception as e:
            return (f"ERROR: cannot apply where={where!r} ({type(e).__name__}: {e}); the columns are "
                    f"{', '.join(map(str, df.columns))}")
    groups = [by] if isinstance(by, str) else list(by or [])
    missing = [g for g in groups if col(g) is None]
    if value is not None and col(value) is None:
        missing.append(value)
    if missing:
        return f"ERROR: no column {missing}; the columns are {', '.join(map(str, df.columns))}"
    groups = [col(g) for g in groups]
    if value is not None:
        values = [col(value)]
    else:
        values = [c for c in df.columns if c not in groups
                  and pd.to_numeric(df[c], errors="coerce").notna().sum() >= max(1, df[c].notna().sum() * 0.8)]
    if not values:
        return "ERROR: no column of numbers to summarise."
    out = []
    frames = {}
    for v in values:
        data = df[groups + [v]].copy()
        data[v] = pd.to_numeric(data[v], errors="coerce")
        stats = (data.groupby(groups, dropna=False, sort=False)[v] if groups else data[v])
        res = stats.agg(["count", "mean", "std", "sem", "median", "min", "max"])
        if not groups:
            res = res.to_frame().T
        res = res.rename(columns={"count": "n", "std": "sd"})
        frames[str(v)] = res
        with pd.option_context("display.max_rows", 200, "display.width", 200,
                               "display.float_format", "{:.4g}".format):
            out.append(f"{v}" + (f" by {', '.join(map(str, groups))}" if groups else "") + ":\n" + res.to_string())
    head = f"{os.path.basename(table)}: {len(df)} rows" + (f" where {where}" if where else "") + "."
    saved = ""
    if out_path:
        try:
            out_path = os.path.abspath(str(out_path))
            if out_path.lower().endswith((".xlsx", ".xlsm")):
                with pd.ExcelWriter(out_path, engine="openpyxl") as book:
                    for name, res in frames.items():
                        res.to_excel(book, sheet_name=str(name)[:31] or "summary")
            else:
                pd.concat(frames, names=["value"]).to_csv(out_path)
            saved = f"\nSaved to {out_path}."
        except Exception as e:
            return f"ERROR: cannot save {out_path} ({type(e).__name__}: {e})"
    return head + saved + "\n" + "\n\n".join(out)


_TABLE_PANEL_KEYS = ("columns", "where", "skip_rows", "by", "value", "stats", "decimals", "max_rows",
                     "title", "rename")


@mcp.tool()
def add_table_panel(
    pyf_path: str,
    group_path: list[int],
    csv_path: str,
    sheet: str | None = None,
    columns: list[str] | None = None,
    where: str | None = None,
    skip_rows: int | None = None,
    by: list[str] | str | None = None,
    value: list[str] | str | None = None,
    stats: list[str] | None = None,
    decimals: int = 2,
    max_rows: int | None = None,
    title: str = "",
    rename: dict[str, str] | None = None,
    label: str | None = None,
) -> str:
    """Add a **table panel**: a data table, or a summary of it, drawn as a figure panel
    ("add a table of mean ± SD per genotype", "show the raw values as a table"). It stays
    live: the table is read again when the figure opens, and is copied with it on
    consolidation.

    *csv_path*: CSV, TSV, TXT, Excel (*sheet*) or SQLite (*sheet* = a table or a query).
    The rows shown: *columns* (some columns), *where* (a pandas query: "day == 14"),
      *skip_rows* (lines above the table; found automatically otherwise), *max_rows*
      (default 60; the rest is said under the table).
    A summary instead: *by* (one column or several: one row per group) and *value* (the
      number column(s); default every number column), *stats* among n, mean, sd, sem,
      median, min, max, "mean±sd", "mean±sem", "median [iqr]" (default ["n",
      "mean±sd"]). *decimals*: digits after the point. *rename*: names shown for columns
      or values. *title*: over the table.
    """
    from pyfigures.table_panel import check, make_script
    csv_path, bad = _table_path(csv_path, sheet)
    if bad:
        return f"ERROR: {bad}. Nothing was added."
    spec = {"csv": csv_path}
    for key, val in (("columns", columns), ("where", where), ("skip_rows", skip_rows), ("by", by),
                     ("value", value), ("stats", stats), ("decimals", decimals), ("max_rows", max_rows),
                     ("title", title), ("rename", rename)):
        if val not in (None, "", [], {}):
            spec[key] = val
    if isinstance(spec.get("stats"), str):
        spec["stats"] = [spec["stats"]]
    bad = check(spec)
    if bad:
        return f"ERROR: {bad}. Nothing was added."
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__table_panel__")
    _plot_text_on_page(img)
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(make_script(spec)))
    if label:
        img.find("annotations").append(_new_tatext2d(label, "top left"))
    container, group_path = _append_new_panel(root, container, img, group_path)
    _save(tree, pyf_path, recompute=True)
    idx = len([c for c in container if c.tag == "Image2D"]) - 1
    from pyfigures.table_panel import table_cells
    header, rows, note = table_cells(spec)
    what = (f"a summary by {', '.join(by) if isinstance(by, list) else by}" if by else
            "a summary" if stats else "the table")
    return (f"Table panel ({what}: {len(rows)} row(s), {len(header)} column(s)) of "
            f"{os.path.basename(csv_path)} added as index {idx} in "
            f"{'canvas' if not group_path else f'group {group_path}'}." + (f" {note}." if note else ""))


@mcp.tool()
def edit_table_panel(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    columns: list[str] | None = None,
    where: str | None = None,
    skip_rows: int | None = None,
    by: list[str] | str | None = None,
    value: list[str] | str | None = None,
    stats: list[str] | None = None,
    decimals: int | None = None,
    max_rows: int | None = None,
    title: str | None = None,
    rename: dict[str, str] | None = None,
    remove: list[str] | None = None,
) -> str:
    """Change a table panel (add_table_panel): other columns or rows, a summary by
    other groups, other statistics, decimals, title, names. Only what is given changes;
    *remove*: settings to drop (["by", "stats"] shows the raw rows again)."""
    from pyfigures.table_panel import check, make_script, parse
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    images = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(images):
        return f"ERROR: image_index {image_index} out of range (0..{len(images) - 1}); nothing was changed."
    img = images[image_index]
    spec = parse(_decode_text(_child_text(img, "custom_loading_script")))
    if spec is None:
        return "ERROR: this panel is not a table panel (add_table_panel). Nothing was changed."
    new = dict(spec)
    for key, val in (("columns", columns), ("where", where), ("skip_rows", skip_rows), ("by", by),
                     ("value", value), ("stats", stats), ("decimals", decimals), ("max_rows", max_rows),
                     ("title", title), ("rename", rename)):
        if val is not None:
            if val in ("", [], {}):
                new.pop(key, None)
            else:
                new[key] = [val] if key == "stats" and isinstance(val, str) else val
    for key in remove or []:
        new.pop(str(key), None)
    bad = check(new)
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    _set_child_text(img, "custom_loading_script", _encode_str(make_script(new)))
    _save(tree, pyf_path, recompute=True)
    changed = [f"{k} {spec.get(k)!r} -> {new.get(k)!r}" for k in sorted(set(spec) | set(new)) if spec.get(k) != new.get(k)]
    return ("Table panel changed: " + "; ".join(changed) + ".") if changed else \
        "The table panel already had these settings; nothing was changed."


@mcp.tool()
def add_seaborn_plot(
    pyf_path: str,
    group_path: list[int],
    csv_path: str,
    function: str,
    x: str | None = None,
    y: str | None = None,
    hue: str | None = None,
    col: str | None = None,
    row: str | None = None,
    col_wrap: int | None = None,
    kind: str | None = None,
    style: str | None = None,
    size: str | None = None,
    palette: str | None = None,
    height: float | None = None,
    aspect: float | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    index: str | None = None,
    columns: str | None = None,
    values: str | None = None,
    options: dict | None = None,
    label: str | None = None,
    sheet: str | None = None,
    where: str | None = None,
    skip_rows: int | None = None,
    rename: dict[str, str] | None = None,
    legend: str | None = None,
    xlim: list[float | None] | None = None,
    ylim: list[float | None] | None = None,
) -> str:
    """Add a **seaborn plot** of a CSV or an Excel sheet (.xlsx, .xls; *sheet* = its name
    or number from 1, else the first) — a tidy / long table: one row per observation — as a
    panel: any seaborn plot, with FACETS like ggplot2's facet_wrap / facet_grid. It stays
    live: the CSV is read again when the figure opens. No statistics brackets (use
    add_data_plot for tested group comparisons).

    *function*: relplot, displot, catplot, lmplot, pairplot, jointplot (figure-level), or
      scatterplot, lineplot, histplot, kdeplot, ecdfplot, rugplot, stripplot, swarmplot,
      boxplot, violinplot, boxenplot, pointplot, barplot, countplot, regplot, residplot,
      heatmap, clustermap. list_data_plot_kinds describes them.
    *x*, *y*, *hue*, *style*, *size*: column names mapped as in seaborn.
    *col* / *row*: facet by these columns (one small plot per value), as facet_wrap
      (col + *col_wrap* = how many per row) or facet_grid (col and row); relplot,
      displot, catplot and lmplot only. E.g. box plots per genotype, one facet per day:
      function="catplot", kind="box", x="genotype", y="length", col="day".
    *kind*: the figure-level function's kind ("scatter"/"line"; "hist"/"kde"/"ecdf";
      "strip"/"swarm"/"box"/"violin"/"boxen"/"point"/"bar"/"count").
    *palette*: a seaborn / matplotlib palette name ("colorblind", "deep", "viridis"...), or a
      colour per hue group: {"female": "#d55e00", "male": "#0072b2"} or a list.
    *legend*: "outside" (beside), "top" (above, in one line), "inside" or "none".
    *xlim* / *ylim*: [low, high] of an axis (null for an automatic end).
    Column names unknown? describe_table(csv_path) lists them, their levels and the plots
    that fit. Split (half) violins: function="violinplot" (or catplot kind="violin"),
    hue = a two-level column (e.g. "sex"), options={"split": true}.
    *height* / *aspect*: inches per facet and width / height.
    *index* / *columns* / *values*: heatmap / clustermap of a pivot of the table.
    *options*: any other keyword the seaborn function takes (e.g. {"errorbar": "se"},
      {"bins": 20}, {"dodge": true}).
    *where*: only the rows matching a pandas query ("day == 14", "sex == 'male'").
    *skip_rows*: lines above the table to skip (default: found automatically).
    *rename*: the names shown, of columns (axis labels, legend titles) or of values
      (ticks, legend entries): {"weight_g": "weight (g)", "mutA": "mutant A"}.
    Common requests: a cumulative histogram = function="histplot", options={"cumulative":
      true, "element": "step", "fill": false} (or function="ecdfplot"); split / half
      violins = function="violinplot", hue=<two-level column>, options={"split": true};
      a title = title="..."; facets = col= / row=; log axis = options={"log_scale": true};
      bins = options={"bins": 30}; error bars as SD = options={"errorbar": "sd"}.
    Rows with a missing value in a used column are left out (the reply says how many).
    """
    from pyfigures.seaborn_plot import check, make_script, dropped_rows
    csv_path, bad = _table_path(csv_path, sheet)
    if bad:
        return f"ERROR: {bad}. Nothing was added."
    spec = {"function": str(function).strip().lower(), "csv": csv_path}
    for key, value in (("x", x), ("y", y), ("hue", hue), ("col", col), ("row", row), ("col_wrap", col_wrap),
                       ("kind", kind), ("style", style), ("size", size), ("palette", palette),
                       ("height", height), ("aspect", aspect), ("title", title), ("xlabel", xlabel),
                       ("ylabel", ylabel), ("index", index), ("columns", columns), ("values", values),
                       ("options", options), ("where", where), ("skip_rows", skip_rows), ("rename", rename),
                       ("legend", legend), ("xlim", xlim), ("ylim", ylim)):
        if value not in (None, ""):
            spec[key] = value
    bad = check(spec)
    if bad:
        return f"ERROR: {bad}. Nothing was added."
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__seaborn_plot__")
    _plot_text_on_page(img)
    _plot_text_like_labels(img, root)
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(make_script(spec)))
    if label:
        img.find("annotations").append(_new_tatext2d(label, "top left"))
    container, group_path = _append_new_panel(root, container, img, group_path)
    _save(tree, pyf_path, recompute=True)
    idx = len([c for c in container if c.tag == "Image2D"]) - 1
    facets = (f", faceted by {' and '.join(v for v in (col, row) if v)}" if (col or row) else "")
    rows_note = dropped_rows(spec)
    return (f"Seaborn {spec['function']}{' (' + kind + ')' if kind else ''} of {os.path.basename(csv_path)} added as "
            f"index {idx} in {'canvas' if not group_path else f'group {group_path}'}{facets}."
            + (f"\nDATA: {rows_note}." if rows_note else ""))


@mcp.tool()
def edit_seaborn_plot(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    function: str | None = None,
    x: str | None = None,
    y: str | None = None,
    hue: str | None = None,
    col: str | None = None,
    row: str | None = None,
    col_wrap: int | None = None,
    kind: str | None = None,
    palette: str | None = None,
    height: float | None = None,
    aspect: float | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    options: dict | None = None,
    remove: list[str] | None = None,
    where: str | None = None,
    skip_rows: int | None = None,
    rename: dict[str, str] | None = None,
    legend: str | None = None,
    xlim: list[float | None] | None = None,
    ylim: list[float | None] | None = None,
) -> str:
    """Change a seaborn plot panel (add_seaborn_plot): another function or kind ("make it a
    violin", "a swarm instead"), other columns, facets ("one facet per day": col="day";
    "no facets": remove=["col", "row"]), palette, size or labels. Only what is given
    changes. *remove*: setting names to drop (e.g. ["hue"], ["col", "col_wrap"]).
    *options* replaces the extra seaborn keywords. *where*: only the rows matching a
    pandas query ("day == 14"); remove=["where"] plots every row again. *skip_rows*: lines
    above the table to skip. *rename*: names shown for columns or values ({"weight_g":
    "weight (g)"}), merged with the ones given before.
    A cumulative histogram: function="histplot", options={"cumulative": true, "element":
    "step", "fill": false}; or function="ecdfplot". *palette*: a name, or a colour per hue
    group {"female": "red"}. *legend*: "outside" | "top" | "inside" | "none". *xlim* /
    *ylim*: [low, high]; remove=["ylim"] gives the automatic range back."""
    from pyfigures.seaborn_plot import check, make_script, parse, dropped_rows
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    images = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(images):
        return f"ERROR: image_index {image_index} out of range (0..{len(images) - 1}); nothing was changed."
    img = images[image_index]
    spec = parse(_decode_text(_child_text(img, "custom_loading_script")))
    if spec is None:
        return ("ERROR: this panel is not a seaborn plot (add_seaborn_plot). A data plot with statistics is "
                "changed with edit_data_plot. Nothing was changed.")
    new = dict(spec)
    for key, value in (("function", function), ("x", x), ("y", y), ("hue", hue), ("col", col), ("row", row),
                       ("col_wrap", col_wrap), ("kind", kind), ("palette", palette), ("height", height),
                       ("aspect", aspect), ("title", title), ("xlabel", xlabel), ("ylabel", ylabel),
                       ("options", options), ("where", where), ("skip_rows", skip_rows),
                       ("legend", legend), ("xlim", xlim), ("ylim", ylim)):
        if value is not None:
            new[key] = value.strip().lower() if key == "function" else value
    if rename is not None:
        new["rename"] = {**(spec.get("rename") or {}), **rename} if rename else {}
        if not new["rename"]:
            new.pop("rename")
    for key in remove or []:
        new.pop(str(key), None)
    bad = check(new)
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    _set_child_text(img, "custom_loading_script", _encode_str(make_script(new)))
    _save(tree, pyf_path, recompute=True)
    changed = [f"{k} {spec.get(k)!r} -> {new.get(k)!r}" for k in sorted(set(spec) | set(new)) if spec.get(k) != new.get(k)]
    rows_note = dropped_rows(new)
    return (("Seaborn plot changed: " + "; ".join(changed) + ".") if changed else
            "The plot already had these settings; nothing was changed.") + (f"\nDATA: {rows_note}." if rows_note and changed else "")


@mcp.tool()
def edit_data_plot(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    kind: str | None = None,
    error: str | None = None,
    annotate_stats: bool | None = None,
    only_significant: bool | None = None,
    stats_mode: str | None = None,
    title: str | None = None,
    ylabel: str | None = None,
    xlabel: str | None = None,
    colors: list[str] | dict[str, str] | None = None,
    csv_path: str | None = None,
    sheet: str | None = None,
    aspect: float | None = None,
    width: float | None = None,
    height: float | None = None,
    font_scale: float | None = None,
    order: list[str] | None = None,
    ylim: list[float | None] | None = None,
    log_y: bool | None = None,
    xtick_rotation: float | None = None,
    legend: str | None = None,
    font_pt: float | str | None = None,
    font_family: str | None = None,
    rename: dict[str, str] | None = None,
    show_points: bool | None = None,
    violin_inner: str | None = None,
    violin_side: str | None = None,
    columns: list[str] | None = None,
    where: str | None = None,
    skip_rows: int | str | None = None,
    element_colors: dict[str, str] | None = None,
    facet: str | None = None,
    facet_row: str | None = None,
    facet_ncols: int | None = None,
    show_n: bool | None = None,
    show_mean: bool | None = None,
    p_format: str | None = None,
    hlines: list | None = None,
    control: str | None = None,
    point_style: str | None = None,
    normalize: str | None = None,
    pairs: list[list[str]] | None = None,
    stats_text: bool | None = None,
) -> str:
    """Change an existing **data-plot panel** (one made by add_data_plot from a CSV):
    switch its kind ("make it a violin plot", "a bar plot instead"), its error bars, its
    statistics ("only show the significant comparisons", "no stats", "non-parametric"),
    its axis labels, colours or CSV. Only the arguments given change; the rest is kept.
    The plot is redrawn and its statistics recomputed. Never edit a data plot's script
    with set_script: that breaks it.

    *kind*: bar | box | violin | scatter | grouped (list_data_plot_kinds says what each shows),
      or auto (the one that shows the data best; the reply says which and why).
    *error*: sem | sd | ci95 | none (bar and grouped plots).
    *annotate_stats*: False removes the test and its brackets, True brings them back.
    *only_significant*: True draws brackets only for p < 0.05 pairs, False for every pair.
    *stats_mode*: auto | parametric | nonparametric.
    *title* / *ylabel* / *xlabel*: "" removes one (no label at all on that axis);
      "auto" gives back the automatic one ("Value", the column's name).
    *colors*: one colour per group (names or #rrggbb), or by name {"WT": "black", "mutA": "red"}.
    *aspect*: width / height of the plot ("make the plot wider": 1.5 or 2; "narrower": 0.7).
      A plot, unlike an image, can take any shape: in a row it is as tall as its
      neighbours, so a larger aspect gives it more of the row.
    Text size: *font_pt* = the size of ALL the plot's text in the printed figure, in
      points ("bigger text" 8 or 9, "like the panel letters" their size, "7 pt"). By
      default a plot's text has the size of the figure's labels (not the letters), else
      7 pt, and follows them; "labels" = back to the labels' size.
    *font_family*: the plot's font ("Verdana", "Times New Roman"); "labels" = the font of
      the figure's labels, the default, which follows them.
    Size: *width* / *height* in inches ("make the plot smaller / bigger").
      *font_scale*: relative sizes inside the plot only; for "bigger text" use font_pt.
    Layout: *order*: the groups in this order (names; groups left out are dropped and
      not tested); *ylim*: [low, high], null for an automatic end ("start the y axis at
      0": [0, null]; on a plot "the scale" / "the scale bar" / "the range from 0 to 50"
      is its y axis: [0, 50]); *rename*: {"mutA": "mutant A"} the name a group shows
      (axis, legend, statistics; the table is unchanged; {} gives the table's names back);
      *show_points*: False removes the individual points ("remove the point cloud"),
      True brings them back; *violin_inner*: inside each violin, "box" (a mini box plot:
      "a box plot within the violin"), "lines" (default: range, quartiles, median dot)
      or "none"; *violin_side*: "left" / "right" = half violins ("make it half violins"), the
      points on the open side, "both" = whole violins; kind="split_violin" puts two
      conditions in the two halves (needs a two-factor table); *log_y*; *xtick_rotation*: degrees ANTICLOCKWISE ("the group names overlap": 45; "rotate
      left" / "anticlockwise" = positive, the names rising "/"; "rotate right" /
      "clockwise" = negative, "\\");
      *legend*: "inside" | "outside" | "none".
    0, "" or [] clears a layout setting (back to the default); only what is asked changes.
    *csv_path*: plot another table (CSV, TXT, Excel) with the same settings.
    *columns*: the columns used from a wider (tidy) table: ["genotype", "area"] (bar /
      box / violin), ["genotype", "sex", "area"] (split_violin: x, halves, value; grouped);
      [] uses the whole table again. describe_table lists the columns and the factors.
    *where*: only the rows matching a pandas query ("day == 14", "sex == 'male'"); ""
      plots every row again.
    *skip_rows*: lines above the table to skip (a number; "auto" = found automatically).
    *element_colors*: colours of parts of the plot ({"points": "black", "median": "red",
      "edges": "none", "brackets": "grey", ...}); merged with the ones set before, a part
      set to "" goes back to its default; {} clears them all.
    *facet*: one plot per value of this column ("one plot per day", "split it by
      treatment"), each with its statistics; "" = one plot again. *facet_row*: a second
      column, one row of facets per value. *facet_ncols*: facets per row.
    *show_n*: n under each group's name ("add the n"); *show_mean*: a mean marker;
    *p_format*: "p" = the p-values written on the brackets ("show the p values, not
    stars"), "stars" back; *hlines*: reference lines ([1.0], [{"y": 100, "label":
    "control"}]; [] removes them).
    *control*: compare every group with this one only (Dunnett); "" = every pair again.
    *point_style*: "swarm" (points side by side, a beeswarm), "line" (one column),
      "jitter" (random, the default).
    *normalize*: values as a % of this group's mean ("% of WT"); "" = the raw values.
    *pairs*: brackets only for these pairs ([["WT", "mutA"]]); [] = every significant pair.
    *stats_text*: True = the two-way ANOVA written under the axes; False = stars only (default).
    *sheet*: another sheet of the Excel workbook (name or number from 1), or another
      table / SQL query of an SQLite database.
    *group_path* / *image_index*: the panel, as for the other image tools.
    """
    from pyfigures.assistant.plot_info import parse_data_plot
    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return f"ERROR: {err}"
    images = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(images):
        return f"ERROR: image_index {image_index} out of range (0..{len(images) - 1}); nothing was changed."
    img = images[image_index]
    spec = parse_data_plot(_decode_text(_child_text(img, "custom_loading_script")))
    if spec is None:
        return ("ERROR: this panel is not a data plot made from a CSV (add_data_plot), so it has no plot "
                "settings to change. A panel drawn by a Python script is changed with get_script / "
                "set_script. Nothing was changed.")
    new = dict(spec)
    for axis, value in (("ylabel", ylabel), ("xlabel", xlabel)):
        # "remove the y label": gone, not replaced by the automatic "Value" (user, 2026-11-18:
        # "I did not say replace it by value, I said I want the label of the y axis gone")
        if value is not None:
            gone = str(value).strip() == ""
            new["show_" + axis] = not gone
            if str(value).strip().lower() == "auto":
                ylabel, xlabel = (("", xlabel) if axis == "ylabel" else (ylabel, ""))
    for key, value in (("kind", kind), ("error", error), ("annotate_stats", annotate_stats),
                       ("only_significant", only_significant), ("stats_mode", stats_mode),
                       ("title", title), ("ylabel", ylabel), ("xlabel", xlabel)):
        if value is not None:
            new[key] = value.lower().strip() if key in ("kind", "error", "stats_mode") else value
    auto_note = ""
    if new["kind"] == "auto":
        new["kind"], why = _auto_kind(new["csv"] if csv_path is None and sheet in (None, "") else
                                      _table_path(csv_path if csv_path is not None else new["csv"], sheet)[0],
                                      (columns if columns is not None else spec.get("columns")) or None,
                                      (where if where is not None else spec.get("where")) or None,
                                      _plot_skip(skip_rows if skip_rows is not None else spec.get("skip_rows"))[0])
        if not new["kind"]:
            return f"ERROR: no plot kind fits this table on its own: {why}. Nothing was changed."
        auto_note = f" (auto: {why})"
    if new["kind"] not in _DATA_PLOT_KINDS:
        return f"ERROR: kind must be 'auto' or one of {_DATA_PLOT_KINDS} (list_data_plot_kinds). Nothing was changed."
    if new["error"] not in ("sem", "sd", "ci95", "none"):
        return "ERROR: error must be 'sem', 'sd', 'ci95' or 'none'. Nothing was changed."
    if new["stats_mode"] not in ("auto", "parametric", "nonparametric"):
        return "ERROR: stats_mode must be 'auto', 'parametric' or 'nonparametric'. Nothing was changed."
    if csv_path is not None or sheet not in (None, ""):
        from pyfigures.plot_tables import split_sheet
        table, bad = _table_path(csv_path if csv_path is not None else split_sheet(new["csv"])[0], sheet)
        if bad:
            return f"ERROR: {bad}. Nothing was changed."
        new["csv"] = table
    new["skip_rows"], bad = _plot_skip(skip_rows if skip_rows is not None else spec.get("skip_rows"))
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    new["columns"], bad = _plot_columns(new["csv"], new["kind"],
                                        columns if columns is not None else spec.get("columns"),
                                        new["skip_rows"])
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    new["where"], bad = _plot_where(new["csv"], where if where is not None else spec.get("where"),
                                    new["skip_rows"])
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    if new["kind"] in _TWO_FACTOR_KINDS:
        try:
            from staplot import api as _api
            gt = _api.grouped_table_from_csv(new["csv"], **_sel(new))
            if new["kind"] == "split_violin":
                _api.split_parts(gt)
        except ImportError:
            pass
        except (ValueError, AttributeError) as e:
            return (f"ERROR: a {new['kind']} plot needs a table with two factors and a value column "
                    f"({e}). Nothing was changed.")
    current = {k: spec.get(k) for k in PLOT_LAYOUT_KEYS}
    if new["kind"] not in ("bar", "box", "violin", "split_violin", "paired"):
        current.pop("order", None)              # a group order means nothing for scatter / grouped
    layout, bad = _plot_layout(new["kind"], new["csv"],
                               {"aspect": aspect, "width": width, "height": height, "font_scale": font_scale,
                                "order": order, "ylim": ylim, "log_y": log_y,
                                "xtick_rotation": xtick_rotation, "legend": legend,
                                "rename": rename, "violin_inner": violin_inner,
                                "violin_side": violin_side, "element_colors": element_colors,
                                "show_n": show_n, "show_mean": show_mean, "p_format": p_format,
                                "hlines": hlines, "control": control, "point_style": point_style,
                                "normalize": normalize, "pairs": pairs, "stats_text": stats_text}, current,
                               columns=new["columns"], where=new["where"], skip_rows=new["skip_rows"])
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    layout.update(_sel(new))
    facets, bad = _plot_facet(new["csv"], {"facet": facet, "facet_row": facet_row, "facet_ncols": facet_ncols},
                              spec, new["skip_rows"], new["where"])
    if bad:
        return f"ERROR: {bad}. Nothing was changed."
    for k in _FACET_KEYS:
        new[k] = facets.get(k)
    layout.update(facets)
    for k in PLOT_LAYOUT_KEYS:
        new[k] = layout.get(k)
    if show_points is not None:
        new["show_points"] = bool(show_points)
    for k in ("show_ylabel", "show_xlabel", "show_points"):
        if new.get(k) is False:
            layout[k] = False
    plot_colors = new.get("colors")
    if colors is not None:
        plot_colors, bad = _plot_colours(colors)
        if bad:
            return f"ERROR: {bad}. Nothing was changed."
        bad = _check_colour_names(new["csv"], new["kind"], plot_colors, _sel(new))
        if bad:
            return f"ERROR: {bad}. Nothing was changed."
    script = _make_data_plot_script(new["csv"], new["kind"], new["error"], new["annotate_stats"],
                                    new["only_significant"], new["title"], new["ylabel"], new["xlabel"],
                                    new["stats_mode"], latex=new.get("latex", False), colors=plot_colors,
                                    layout=layout)
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    font_note = []
    if font_family is not None:
        from .core import _decode
        old_family = _decode(_child_text(img, "publication_font") or "") or "?"
        wanted = str(font_family).strip()
        if wanted.lower() in _LIKE_LABELS:
            _plot_text_like_labels(img, root, size=False)
            new_family = "the labels' font"
        else:
            from .core import _warn_missing_font
            _set_child_text(img, "publication_font", _encode_str(wanted))
            _warn_missing_font(wanted)
            new_family = wanted
        if old_family == FOLLOW_LABELS:
            old_family = "the labels' font"
        if old_family != new_family:
            font_note.append(f"font {old_family} -> {new_family}")
    if isinstance(font_pt, str) and font_pt.strip().lower() in _LIKE_LABELS:
        old_pt = _child_text(img, "publication_font_size")
        _plot_text_like_labels(img, root, family=False)
        font_note.append(f"text {old_pt or '?'} pt -> the labels' size "
                         f"({_child_text(img, 'publication_font_size')} pt now)")
        font_pt = None
    if font_pt is not None:
        try:
            font_pt = float(font_pt)
        except (TypeError, ValueError):
            return (f"ERROR: font_pt is the plot's text size in points on the page, or \"labels\" (the size "
                    f"of the figure's labels); got {font_pt!r}. Nothing was changed.")
        if not 3 <= float(font_pt) <= 72:
            return "ERROR: font_pt is the plot's text size in the printed figure, 3 to 72 points. Nothing was changed."
        old_pt = _child_text(img, "publication_font_size")
        on_page = str(_child_text(img, "publication_font_on_page")) == "True"
        followed = str(_child_text(img, "publication_font_size_from_labels")) == "True"
        _plot_text_on_page(img, font_pt)
        if not on_page or followed or str(old_pt) != f"{float(font_pt):g}":
            font_note.append(f"text {old_pt or '?'} pt{'' if on_page else ' (plot points)'}"
                             f"{' (the labels’ size)' if followed else ''} -> {float(font_pt):g} pt on the page")
    _save(tree, pyf_path, recompute=True)
    changed = font_note + [f"{k} {spec.get(k)!r} -> {new.get(k)!r}" for k in
               ("kind", "error", "annotate_stats", "only_significant", "stats_mode", "title", "ylabel", "xlabel", "csv",
                "columns", "where", "skip_rows") + _FACET_KEYS
               + PLOT_LAYOUT_KEYS + ("show_ylabel", "show_xlabel", "show_points")
               if spec.get(k) != new.get(k)]
    if colors is not None:
        changed.append(f"colours -> {plot_colors}")
    if not changed:
        return "The data plot already had these settings; nothing was changed." + auto_note
    return "Data plot changed: " + "; ".join(changed) + auto_note + "."


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

    *rotation*: rotation in **degrees**, POSITIVE = CLOCKWISE as seen (not the
                maths convention): "25° clockwise" is 25, "25° counter-clockwise"
                is -25 (e.g. 90, -90, 45, 180). The absolute angle, not a step.
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
        if all(c is None for c in (crop_left, crop_right, crop_top, crop_bottom)):
            # a cropped image keeps showing the same region, turned (user 2026-11-19)
            from .core import keep_crop_on_rotation
            kept = keep_crop_on_rotation(img, float(rotation))
            if kept:
                changed.append(kept)
        _set_child_text(img, "theta", str(float(rotation)) if rotation != 0 else "None")
        # the direction in words: a model asked for "25° clockwise" sent -25 (maths
        # convention) and reported it as clockwise (chat log 2026-11-17)
        r = float(rotation)
        direction = "upright" if r == 0 else ("clockwise" if r > 0 else "counter-clockwise")
        changed.append(f"rotation={r}° ({direction}" + ("" if r == 0 else f" {abs(r):g}° as seen") + ")")
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
    if luts_encoded is None and not any(current or []) and normalization is None:
        # "LUTs removed" was reported for a panel that had none, and the model then
        # told the user the colour was back when nothing had changed (2026-11-17)
        return (f"NO CHANGE: image {image_index} already has no LUT (it shows the image's own "
                f"colours); nothing was changed. If the panel does not look as the user wants, "
                f"look at it (render_preview) before saying what colour it is.")
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

    *channels*: channel numbers to invert, counted from 1 (1 = the first
      channel, as the GUI shows it); None inverts every channel.
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
    if channels is None:
        wanted = list(range(n_file))
    else:
        from .stacks import _channel_index
        wanted = []
        for ch in (channels if isinstance(channels, (list, tuple)) else [channels]):
            idx, cerr = _channel_index(ch, n_file)
            if cerr:
                return f"ERROR: {cerr}"
            wanted.append(idx)
    available = list_available_luts()
    new, done = list(current), []
    for c in wanted:
        lut = current[c]
        if lut in (None, "DEFAULT"):
            if n_file != 1:
                return (f"ERROR: channel {c + 1} shows its acquisition colour, which has no inverted twin. "
                        f"Which LUT should it get (e.g. GRAY_INVERTED, GREEN_INVERTED)? Nothing was changed.")
            lut = "GRAY"
        twin = invert_lut_name(lut, available)
        if twin is None:
            return f"ERROR: the LUT {lut} of channel {c + 1} cannot be inverted. Nothing was changed."
        new[c] = twin
        done.append(f"channel {c + 1}: {current[c] or 'acquisition colour'} -> {twin}")
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
    kind = re.search(r"kind=('[a-z_]+')", script)
    if not m:
        return None
    try:
        import ast
        from staplot import api as _api
        csv = ast.literal_eval(m.group(1))
        if kind and ast.literal_eval(kind.group(1)) in _TWO_FACTOR_KINDS:
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

        # ONE Z slice ("show slice 7", "the next z"): a projection of that slice alone
        configure_image("fig.pyf", [0], 0, projection="max",
                        projection_z_start=7, projection_z_end=8)

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
