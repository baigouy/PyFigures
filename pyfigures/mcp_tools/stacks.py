"""PyFigures MCP tools — panels made from image stacks: frame montages (opt-in),
channel-split rows, kymographs and orthogonal (XZ/YZ) views.

By default a stack added with add_image shows ONE image (first frame / chosen
projection); these tools are for when a figure needs several views of it.

Montage and channel-split panels are plain Image2D panels that select their
frame / channel natively (``dimensions`` / ``channels`` fields, no script), so
they stay editable in the GUI and are not flagged as custom scripts. Kymographs
and orthogonal views are computed, so they are scripted panels that re-render
from the source stack whenever the figure is opened.
"""
from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET

from .app import mcp, _warn
from .core import (
    _append_image,
    _child_text,
    _color_to_int,
    _decode,
    _encode_str,
    _first_filename,
    _get_container,
    _load,
    _navigate_group,
    _new_group_elem,
    _new_image2d,
    _new_roi_line,
    _new_tatext2d,
    _next_group_id,
    _save,
    _set_child_text,
    _top_groups,
)
from .content import _canonical_lut_names, _make_channel_merge_script

SERIES_MARK = "[series "          # user_comments prefix of montage / split members

# colour name -> PyFigures LUT key, for tinting a channel natively
_COLOR_LUTS = {"gray": "GRAY", "grey": "GRAY", "white": "GRAY", "red": "RED",
               "green": "GREEN", "blue": "BLUE", "cyan": "CYAN",
               "magenta": "MAGENTA", "yellow": "YELLOW"}
_COLOR_HEX = {"gray": 0xFFFFFF, "grey": 0xFFFFFF, "white": 0xFFFFFF, "red": 0xFF4040,
              "green": 0x40FF40, "blue": 0x5A8CFF, "cyan": 0x00FFFF,
              "magenta": 0xFF40FF, "yellow": 0xFFFF00}
_DEFAULT_SPLIT_COLORS = {1: ["gray"], 2: ["green", "magenta"],
                         3: ["red", "green", "blue"], 4: ["red", "green", "blue", "gray"]}



# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _stack(path, series=None):
    from pyfigures.stack_info import stack_info, StackInfoError
    try:
        return stack_info(path, series), None
    except StackInfoError as e:
        return None, str(e)


def _insert_group(root, grp, parent_group_path):
    """Insert *grp* as a new top-level group (after the last one) or inside the
    group at *parent_group_path*; returns (path, error)."""
    if parent_group_path is None:
        n = len(_top_groups(root))
        last = -1
        for i, child in enumerate(root):
            if child.tag == "Group":
                last = i
        root.insert(last + 1, grp)
        return [n], ""
    parent, err = _navigate_group(root, parent_group_path)
    if err:
        return None, err
    content = parent.find("content")
    if content is None:
        content = ET.SubElement(parent, "content")
    idx = len([c for c in content if c.tag == "Group"])
    content.append(grp)
    return list(parent_group_path) + [idx], ""


def _stack_panel(info, values, projection=None, channels=None, luts=None,
                 series=None, comment=""):
    """Image2D showing one plane of a stack natively."""
    img = _new_image2d(info["path"])
    order = info["order"]
    lead = order[:order.index("h")]
    if lead:
        _set_child_text(img, "dimensions",
                        repr({"order": order, "values": [int(v) for v in values]}))
    if projection:
        _set_child_text(img, "projection", projection)
    if channels is not None:
        _set_child_text(img, "channels", repr([bool(c) for c in channels]))
    if luts is not None:
        _set_child_text(img, "LUTs", repr(list(luts)))
    if series is not None:
        _set_child_text(img, "serie_to_open", str(int(series)))
    if info.get("vx"):
        _set_child_text(img, "px_to_unit_conversion_factor", repr(float(info["vx"])))
    if comment:
        _set_child_text(img, "user_comments", _encode_str(comment))
    return img


def _plane_values(info, fixed: dict, projection):
    """Index for every dimension before h/w: *fixed* {letter: index}, others 0
    (the projected axis is skipped by Image2D when a projection is set)."""
    order = info["order"]
    return [int(fixed.get(L, 0)) for L in order[:order.index("h")]]


def _projection_for(info, axis_shown, projection):
    """Z projection applies only when the stack has a Z axis that is not the
    one being shown frame by frame (and Z is the axis right before h/w, which
    is where Image2D projects)."""
    order = info["order"]
    if not projection or str(projection).lower() == "none":
        return None
    p = str(projection).lower()
    if p not in ("max", "min", "avg"):
        raise ValueError("projection must be 'max', 'min', 'avg' or 'none'")
    if "d" not in order or axis_shown == "d":
        return None
    if order[order.index("h") - 1] != "d":
        return None
    return p


def _lut_list(lut, n_channels):
    """LUTs field for a panel: one name for every channel, or a per-channel list."""
    if lut is None:
        return None
    luts = lut if isinstance(lut, list) else [lut] * max(1, n_channels)
    names, errs = _canonical_lut_names(luts)
    if errs:
        raise ValueError("; ".join(errs))
    return names


# ---------------------------------------------------------------------------
# 1. frame montage (opt-in)
# ---------------------------------------------------------------------------
@mcp.tool()
def add_stack_montage(
    pyf_path: str,
    stack_path: str,
    axis: str = "t",
    frames: list[int] | str | int | None = None,
    columns: int | None = None,
    parent_group_path: list[int] | None = None,
    projection: str | None = "max",
    channel: int | None = None,
    lut: str | list[str] | None = None,
    interval: float | None = None,
    unit: str | None = None,
    stamps: bool = True,
    stamp_format: str | None = None,
    time_zero: int | None = None,
    stamp_placement: str = "top right",
    stamp_color: str | int = "white",
    series: int | None = None,
    spacing: int = 3,
) -> str:
    """Show several frames of ONE stack side by side — a time-lapse or Z-series
    montage with time / depth stamps ("0 min, 2 min, 4 min…").

    Opt-in: add_image shows a stack as a single image; use this only when the
    figure should show the frames.

    *axis*: "t" (time) or "z" (depth).
    *frames*: which frames — None = 6 evenly spaced frames incl. first and last;
      an int N = N evenly spaced frames; "all"; "start:stop:step" (stop
      exclusive, "::5" = every 5th frame); or a list [0, 5, 10].
    *columns*: wrap into several rows of this many panels (default one row).
    *parent_group_path*: None = add as a new top-level row (or block of rows);
      [i] = nest inside that group.
    *projection*: for a time montage of a 3-D stack, how each time point's Z
      stack is shown ("max", "min", "avg", or "none" = first slice).
    *channel*: show only this channel (0-based) of a multi-channel stack.
    *lut*: LUT for the panels (e.g. "GRAY", "MATPLOTLIB_magma"), or a list per
      channel.
    *interval* / *unit*: time (or Z step) per frame; default from the file
      (ImageJ finterval/tunit, LSM, OME; Z step = voxel depth). Without either,
      stamps read "frame 1, frame 2…".
    *stamps*: add the stamps; *stamp_format* e.g. "t = {value:g} {unit}";
      *stamp_placement* default "top right" (the panel letter takes top left).
    *time_zero*: frame whose stamp is 0 (default: the first frame shown).

    Example — 5 time points of a 3-D time-lapse, max-projected, 2 min apart::

        add_stack_montage("fig.pyf", "/d/embryo.tif", axis="t", frames=5)
    """
    from pyfigures.stack_info import parse_frames, format_stamp
    axis_l = {"t": "t", "time": "t", "z": "d", "d": "d", "depth": "d"}.get(str(axis).lower())
    if axis_l is None:
        return "ERROR: axis must be 't' or 'z'."
    info, err = _stack(stack_path, series)
    if err:
        return f"ERROR: {err}"
    order, sizes = info["order"], info["sizes"]
    if axis_l not in order[:order.index("h")]:
        have = ", ".join(f"{k}={v}" for k, v in sizes.items() if k not in "hw")
        return (f"ERROR: {os.path.basename(stack_path)} has no "
                f"{'time' if axis_l == 't' else 'Z'} axis (dimensions: "
                f"{order}{'; ' + have if have else ''}).")
    n = sizes[axis_l]
    try:
        idx = parse_frames(frames if not isinstance(frames, str) or frames.strip() else None, n)
        proj = _projection_for(info, axis_l, projection)
        nch = sizes.get("c", 1)
        chans = None
        if channel is not None:
            if "c" not in order or not 0 <= channel < nch:
                return f"ERROR: channel {channel} out of range (stack has {nch} channel(s))."
            chans = [i == channel for i in range(nch)]
        luts = _lut_list(lut, nch)
        scol = _color_to_int(stamp_color)
    except ValueError as e:
        return f"ERROR: {e}"
    if columns is not None and columns < 1:
        return "ERROR: columns must be >= 1."

    # stamps: value per frame
    if axis_l == "t":
        step = interval if interval is not None else info.get("interval")
        s_unit = unit if unit is not None else info.get("time_unit")
    else:
        step = interval if interval is not None else info.get("vz")
        s_unit = unit if unit is not None else info.get("space_unit")
    t0 = idx[0] if time_zero is None else int(time_zero)

    def stamp(f):
        if step is None:
            return f"frame {f + 1}" if axis_l == "t" else f"z {f + 1}"
        return format_stamp((f - t0) * float(step), s_unit, stamp_format)

    tree, root = _load(pyf_path)
    per_row = columns if columns else len(idx)
    rows = [idx[i:i + per_row] for i in range(0, len(idx), per_row)]
    gid = _next_group_id(root)
    if len(rows) == 1:
        outer = _new_group_elem("X", spacing, gid)
        targets = [outer]
    else:
        outer = _new_group_elem("Y", spacing, gid)
        targets = []
        for r in range(len(rows)):
            sub = _new_group_elem("X", spacing, gid + 1 + r)
            outer.find("content").append(sub)
            targets.append(sub)
    path, err = _insert_group(root, outer, parent_group_path)
    if err:
        return f"ERROR: {err}"
    k = 0
    base = os.path.basename(stack_path)
    for grp, row in zip(targets, rows):
        for f in row:
            k += 1
            img = _stack_panel(
                info, _plane_values(info, {axis_l: f}, proj), proj, chans, luts, series,
                comment=f"{SERIES_MARK}{k}/{len(idx)}] montage of {base}, "
                        f"{'t' if axis_l == 't' else 'z'}={f}")
            if stamps:
                img.find("annotations").append(
                    _new_tatext2d(stamp(f), stamp_placement, is_letter=False, color=scol))
            grp.find("content").append(img)
    _save(tree, pyf_path, recompute=True)
    stamps_note = ""
    if stamps:
        stamps_note = (f"; stamps {stamp(idx[0])} … {stamp(idx[-1])}" if step is not None else
                       "; no frame interval in the file — stamps are frame numbers "
                       "(pass interval= and unit= for times)")
    return (f"Montage of {len(idx)} {'time points' if axis_l == 't' else 'Z slices'} "
            f"of {base} added at group {path} ({len(rows)} row(s))"
            + (f", Z {proj}-projected" if proj else "") + stamps_note + ".")


# ---------------------------------------------------------------------------
# 2. channel split row
# ---------------------------------------------------------------------------
@mcp.tool()
def add_channel_split(
    pyf_path: str,
    stack_path: str | None = None,
    channel_files: list[str] | None = None,
    names: list[str] | None = None,
    colors: list[str] | None = None,
    gray: bool = True,
    include_merge: bool = True,
    merge_label: str = "Merge",
    parent_group_path: list[int] | None = None,
    projection: str | None = "max",
    frame: int = 0,
    series: int | None = None,
    spacing: int = 3,
    label_placement: str = "top right",
) -> str:
    """The classic channel-split row: each channel on its own panel, then the
    merge, with the channel names on the panels.

    Give EITHER *stack_path* (one multi-channel image/stack) OR *channel_files*
    (one single-channel image per channel).

    *names*: channel names for the labels (default "Ch1", "Ch2"…); the merge
      gets *merge_label* ("" = none).
    *colors*: channel colours used in the merge (gray/red/green/blue/cyan/
      magenta/yellow); default green+magenta for 2 channels, RGB for 3.
    *gray*: True (default) shows each single channel in grayscale with its name
      written in the channel colour — the most legible and colour-blind safe;
      False tints each single-channel panel in its colour.
    *include_merge*: add the merge panel at the end.
    *projection* / *frame*: for 3-D / time stacks, the Z projection and the
      time point shown (same for every panel so they match).

    Example::

        add_channel_split("fig.pyf", stack_path="/d/cells.tif",
                          names=["DAPI", "GFP", "RFP"], colors=["blue", "green", "magenta"])
    """
    if bool(stack_path) == bool(channel_files):
        return "ERROR: give either stack_path or channel_files (not both)."
    base_comment = os.path.basename(stack_path) if stack_path else "channel files"
    info = None
    if stack_path:
        info, err = _stack(stack_path, series)
        if err:
            return f"ERROR: {err}"
        n = info["sizes"].get("c", 1)
        if "c" not in info["order"] or n < 2:
            return (f"ERROR: {os.path.basename(stack_path)} has a single channel "
                    f"(dimensions {info['order']}); give channel_files instead.")
        nt = info["sizes"].get("t", 1)
        if not 0 <= int(frame) < nt:
            return f"ERROR: frame {frame} out of range (the stack has {nt} time point(s): 0..{nt - 1})."
    else:
        from pyfigures.path_resolution import source_exists
        missing = [f for f in channel_files if not source_exists(f)]
        if missing:
            return "ERROR: channel file(s) not found: " + ", ".join(missing)
        n = len(channel_files)
        if n < 2:
            return "ERROR: a channel split needs at least 2 channels."
    names = list(names) if names else [f"Ch{i + 1}" for i in range(n)]
    colors = [str(c).lower() for c in colors] if colors else \
        _DEFAULT_SPLIT_COLORS.get(n, (["red", "green", "blue", "gray", "cyan", "magenta", "yellow"] * 2)[:n])
    if len(names) != n or len(colors) != n:
        return f"ERROR: {n} channels but {len(names)} names / {len(colors)} colours."
    bad = [c for c in colors if c not in _COLOR_LUTS]
    if bad:
        return f"ERROR: unsupported colour(s) {bad}; use {sorted(set(_COLOR_LUTS) - {'grey', 'white'})}."

    tree, root = _load(pyf_path)
    grp = _new_group_elem("X", spacing, _next_group_id(root))
    path, err = _insert_group(root, grp, parent_group_path)
    if err:
        return f"ERROR: {err}"
    content = grp.find("content")
    total = n + (1 if include_merge else 0)
    try:
        proj = _projection_for(info, None, projection) if info else None
    except ValueError as e:
        return f"ERROR: {e}"
    for i in range(n):
        lut = "GRAY" if gray else _COLOR_LUTS[colors[i]]
        # label: channel colour on gray panels (reads as a legend), white on tinted
        lab_col = _COLOR_HEX[colors[i]] if gray else 0xFFFFFF
        comment = f"{SERIES_MARK}{i + 1}/{total}] channel split of {base_comment}: {names[i]}"
        if info:
            fixed = {"t": frame} if "t" in info["order"] else {}
            img = _stack_panel(info, _plane_values(info, fixed, proj), proj,
                               [j == i for j in range(n)],
                               [lut if j == i else None for j in range(n)], series, comment)
        else:
            img = _new_image2d(os.path.abspath(channel_files[i]))
            _set_child_text(img, "LUTs", repr([lut]))
            _set_child_text(img, "user_comments", _encode_str(comment))
        if names[i]:
            img.find("annotations").append(
                _new_tatext2d(names[i], label_placement, is_letter=False, color=lab_col))
        content.append(img)
    if include_merge:
        comment = f"{SERIES_MARK}{total}/{total}] channel split of {base_comment}: merge"
        if info:
            fixed = {"t": frame} if "t" in info["order"] else {}
            img = _stack_panel(info, _plane_values(info, fixed, proj), proj,
                               [True] * n, [_COLOR_LUTS[c] for c in colors], series, comment)
        else:
            rgb = []
            for c in colors:
                ci = _COLOR_HEX[c] if c not in ("gray", "grey", "white") else 0xFFFFFF
                if c in ("red", "green", "blue", "magenta", "cyan", "yellow"):
                    ci = {"red": 0xFF0000, "green": 0x00FF00, "blue": 0x0000FF,
                          "magenta": 0xFF00FF, "cyan": 0x00FFFF, "yellow": 0xFFFF00}[c]
                rgb.append(((ci >> 16 & 255) / 255., (ci >> 8 & 255) / 255., (ci & 255) / 255.))
            script = _make_channel_merge_script([os.path.abspath(f) for f in channel_files],
                                                rgb, "sum", "per_channel")
            img = _new_image2d("__channel_merge__")
            img.find("filename").text = "None"
            _set_child_text(img, "custom_loading_script", _encode_str(script))
            _set_child_text(img, "user_comments", _encode_str(comment))
        if merge_label:
            img.find("annotations").append(
                _new_tatext2d(merge_label, label_placement, is_letter=False, color=0xFFFFFF))
        content.append(img)
    _save(tree, pyf_path, recompute=True)
    return (f"Channel split of {base_comment} added at group {path}: "
            + ", ".join(f"{nm} ({c})" for nm, c in zip(names, colors))
            + (" + merge" if include_merge else "")
            + (", grayscale singles" if gray else ", tinted singles")
            + (f", Z {proj}-projected" if proj else "") + ".")


# ---------------------------------------------------------------------------
# panel lookup shared by kymograph / orthogonal views
# ---------------------------------------------------------------------------
def _source_panel(root, group_path, image_index):
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return None, None, err
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return None, None, f"image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    fn = _first_filename(img)
    from pyfigures.path_resolution import source_exists
    if not fn or not source_exists(fn):
        return None, None, "the source panel has no readable image file."
    ser = _child_text(img, "serie_to_open")
    try:
        ser = int(ser) if ser not in (None, "", "None") else None
    except ValueError:
        ser = None
    return img, (fn, ser), ""


def _target_container(root, group_path, target_group_path):
    gp = group_path if target_group_path is None else target_group_path
    return _get_container(root, gp, refuse_label_rows=True), gp


# ---------------------------------------------------------------------------
# 3a. kymograph
# ---------------------------------------------------------------------------
_KYMO_MARK = "# pyfigures:kymograph"


def _make_kymograph_script(path, series, order, line, width, channel, zproj,
                           frame_h, cmap):
    return f"""\
{_KYMO_MARK}
import numpy as np
_path = {path!r}
_series = {series!r}
_order = {order!r}
_line = {tuple(float(v) for v in line)!r}
_width = {int(width)!r}
_channel = {channel!r}
_zproj = {zproj!r}
_frame_h = {int(frame_h)!r}
_cmap = {cmap!r}

_a = Img(_path) if _series is None else Img(_path, serie_to_open=_series)
# reduce in the file's own dtype: a float64 copy of a whole 4-D stack can be
# many GB; only the (T, H, W) result is converted
_a = np.asarray(_a)
if 'c' in _order:
    _a = np.take(_a, _channel or 0, axis=_order.index('c'))
    _order = _order.replace('c', '')
if 'd' in _order:
    _ax = _order.index('d')
    _a = _a.mean(axis=_ax, dtype=np.float64) if _zproj == 'avg' else (_a.min(axis=_ax) if _zproj == 'min' else _a.max(axis=_ax))
    _order = _order.replace('d', '')
_a = _a.astype(np.float64, copy=False)
if _order != 'thw':
    raise ValueError('kymograph needs a time stack, got dimensions ' + _order)
_T, _H, _W = _a.shape
_ax1, _ay1, _ax2, _ay2 = _line
_len = float(np.hypot(_ax2 - _ax1, _ay2 - _ay1))
_n = max(2, int(round(_len)) + 1)
_s = np.linspace(0.0, 1.0, _n)
# panel coordinates put pixel i's centre at i + 0.5
_px = _ax1 + (_ax2 - _ax1) * _s - 0.5
_py = _ay1 + (_ay2 - _ay1) * _s - 0.5
_nx = -(_ay2 - _ay1) / _len if _len > 0 else 0.0
_ny = (_ax2 - _ax1) / _len if _len > 0 else 0.0
_kymo = np.zeros((_T, _n), dtype=np.float64)
_offs = np.arange(_width) - (_width - 1) / 2.0
for _o in _offs:
    _xs = np.clip(_px + _nx * _o, 0, _W - 1)
    _ys = np.clip(_py + _ny * _o, 0, _H - 1)
    _x0 = np.floor(_xs).astype(np.int64)
    _y0 = np.floor(_ys).astype(np.int64)
    _xb = np.minimum(_x0 + 1, _W - 1)
    _yb = np.minimum(_y0 + 1, _H - 1)
    _fx = _xs - _x0
    _fy = _ys - _y0
    _kymo += (_a[:, _y0, _x0] * (1 - _fx) * (1 - _fy) + _a[:, _y0, _xb] * _fx * (1 - _fy)
              + _a[:, _yb, _x0] * (1 - _fx) * _fy + _a[:, _yb, _xb] * _fx * _fy)
_kymo /= len(_offs)
_kymo = np.repeat(_kymo, _frame_h, axis=0)
_lo, _hi = float(_kymo.min()), float(_kymo.max())
_kymo = (_kymo - _lo) / (_hi - _lo) if _hi > _lo else np.zeros_like(_kymo)
_KH, _KW = _kymo.shape
fig = plt.figure(figsize=(_KW / 100.0, _KH / 100.0), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.imshow(_kymo, cmap=_cmap, vmin=0, vmax=1, interpolation='none', aspect='auto')
ax.axis('off')
fig._pyfigures_pad_inches = 0
fig._pyfigures_image_panel = True
self.img = fig
"""


@mcp.tool()
def add_kymograph(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    line_width: int = 3,
    channel: int | None = None,
    projection: str = "max",
    frame_height: int | None = None,
    cmap: str = "gray",
    mark_line: bool = True,
    line_color: str | int = "yellow",
    label: str | None = None,
    target_group_path: list[int] | None = None,
) -> str:
    """Kymograph (position along a line vs time) from the time stack shown in a
    panel: time runs downwards, one row block per frame.

    (*x1*, *y1*) → (*x2*, *y2*): the line, in the source image's pixels.
    *line_width*: pixels averaged across the line (odd numbers centre on it).
    *channel*: channel to use for multi-channel stacks (default 0).
    *projection*: how a 3-D stack's Z is collapsed per time point (max/avg/min).
    *frame_height*: rows per frame (default: enough for the kymograph to be
      about half as tall as wide). Frames are repeated, not interpolated.
    *mark_line*: draw the sampled line on the source panel.
    *target_group_path*: where the kymograph panel goes (default: the source
      panel's group, appended).

    The kymograph's horizontal pixel size is the source's, so a scale bar on it
    measures distance along the line. Time per frame is in the return message.
    """
    tree, root = _load(pyf_path)
    src, pair, err = _source_panel(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    fn, ser = pair
    info, err = _stack(fn, ser)
    if err:
        return f"ERROR: {err}"
    if info["sizes"].get("t", 1) < 2:
        return (f"ERROR: {os.path.basename(fn)} is not a time series "
                f"(dimensions {info['order']}).")
    W, H = info["sizes"]["w"], info["sizes"]["h"]
    for v, lim, nm in ((x1, W, "x1"), (x2, W, "x2"), (y1, H, "y1"), (y2, H, "y2")):
        if not 0 <= v <= lim:
            return f"ERROR: {nm}={v} is outside the image ({W} x {H} px)."
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 2:
        return "ERROR: the line is too short."
    nch = info["sizes"].get("c", 1)
    if channel is not None and not 0 <= channel < nch:
        return f"ERROR: channel {channel} out of range ({nch} channel(s))."
    if projection not in ("max", "avg", "min"):
        return "ERROR: projection must be 'max', 'avg' or 'min'."
    T = info["sizes"]["t"]
    fh = frame_height or max(1, int(round(0.5 * (length + 1) / T)))
    script = _make_kymograph_script(info["path"], ser, info["order"], (x1, y1, x2, y2),
                                    max(1, int(line_width)), channel, projection, fh, cmap)
    (container, err), gp = _target_container(root, group_path, target_group_path)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__kymograph__")
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    _set_child_text(img, "user_comments", _encode_str(
        f"kymograph of {os.path.basename(fn)} along ({x1:g},{y1:g})-({x2:g},{y2:g}), "
        f"width {line_width} px, {fh} row(s)/frame"))
    if info.get("vx"):
        _set_child_text(img, "px_to_unit_conversion_factor", repr(float(info["vx"])))
    # known output size, so the layout is right before the first render
    _set_child_text(img, "width", repr(float(int(round(length)) + 1)))
    _set_child_text(img, "height", repr(float(T * fh)))
    if label:
        img.find("annotations").append(_new_tatext2d(label, "top left", color=0xFFFFFF))
    if mark_line:
        src.find("annotations").append(
            _new_roi_line(x1, y1, x2, y2, _color_to_int(line_color), 1.0, 1.0, False, False))
    _append_image(container, img, is_root=(not gp))
    _save(tree, pyf_path, recompute=True)
    interval, tunit = info.get("interval"), info.get("time_unit")
    tnote = (f"{T} frames × {interval:g} {tunit} = {(T - 1) * interval:g} {tunit} top to bottom"
             if interval else f"{T} frames top to bottom (no frame interval in the file)")
    return (f"Kymograph added to group {gp}: {int(round(length)) + 1} px along the line "
            f"× {T} frames ({fh} row(s) per frame); {tnote}.")


# ---------------------------------------------------------------------------
# 3b. orthogonal views
# ---------------------------------------------------------------------------
_ORTHO_MARK = "# pyfigures:orthogonal_views"


def _make_ortho_script(path, series, order, x, y, z, t, channel, colors, zscale,
                       gap, background):
    return f"""\
{_ORTHO_MARK}
import numpy as np
_path = {path!r}
_series = {series!r}
_order = {order!r}
_x, _y, _z, _t = {int(x)!r}, {int(y)!r}, {z!r}, {int(t)!r}
_channel = {channel!r}
_colors = {colors!r}
_zs = {float(zscale)!r}
_gap = {int(gap)!r}
_bg = {tuple(float(v) for v in background)!r}

_a = Img(_path) if _series is None else Img(_path, serie_to_open=_series)
# pick the time point / channel first, in the file's dtype: never a float64
# copy of the whole time-lapse
_a = np.asarray(_a)
if 't' in _order:
    _a = np.take(_a, _t, axis=_order.index('t'))
    _order = _order.replace('t', '')
if 'c' not in _order:
    _a = _a[..., np.newaxis]
    _order = _order + 'c'
if _channel is not None:
    _a = np.take(_a, [_channel], axis=_order.index('c'))
_a = _a.astype(np.float64)
if _order != 'dhwc':
    raise ValueError('orthogonal views need a Z stack, got dimensions ' + _order)
_Z, _H, _W, _C = _a.shape
# one intensity window per channel for all three views, so they match
_lo = _a.reshape(-1, _C).min(axis=0)
_hi = _a.reshape(-1, _C).max(axis=0)
_a = (_a - _lo) / np.where(_hi > _lo, _hi - _lo, 1.0)
_xy = _a[_z] if _z is not None else _a.max(axis=0)
_xz = _a[:, _y, :, :]
_yz = np.transpose(_a[:, :, _x, :], (1, 0, 2))
_Zp = max(1, int(round(_Z * _zs)))
_zi = np.minimum((np.arange(_Zp) / _zs).astype(np.int64), _Z - 1)
_xz = _xz[_zi]
_yz = _yz[:, _zi]
_rgb = np.zeros((_H + _gap + _Zp, _W + _gap + _Zp, 3), dtype=np.float64)
_rgb[...] = _bg
if _C == 1:
    _tint = [(1.0, 1.0, 1.0)]
else:
    _tint = _colors
for _k in range(_C):
    _c = np.asarray(_tint[_k], dtype=np.float64)
    for _img, _r0, _c0 in ((_xy, 0, 0), (_xz, _H + _gap, 0), (_yz, 0, _W + _gap)):
        _h, _w = _img.shape[:2]
        _blk = _rgb[_r0:_r0 + _h, _c0:_c0 + _w]
        if _k == 0:
            _blk[...] = 0.0
        _blk += _img[..., _k, np.newaxis] * _c
_rgb = np.clip(_rgb, 0.0, 1.0)
_RH, _RW = _rgb.shape[:2]
fig = plt.figure(figsize=(_RW / 100.0, _RH / 100.0), dpi=100)
ax = fig.add_axes([0, 0, 1, 1])
ax.imshow(_rgb, interpolation='none', aspect='equal')
ax.axis('off')
fig._pyfigures_pad_inches = 0
fig._pyfigures_image_panel = True
self.img = fig
"""


@mcp.tool()
def add_orthogonal_views(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    x: int,
    y: int,
    z: int | None = None,
    time_point: int = 0,
    channel: int | None = None,
    colors: list[str] | None = None,
    z_scale: float | None = None,
    gap: int = 4,
    background: str | int = "white",
    crosshair: bool = True,
    crosshair_color: str | int = "yellow",
    label: str | None = None,
    target_group_path: list[int] | None = None,
) -> str:
    """Orthogonal views of the Z stack shown in a panel, in the classic layout:
    XY top-left, YZ to its right, XZ below, cut through voxel (*x*, *y*).

    *z*: the XY slice shown (default: maximum projection); also marks the
      slice in the side views.
    *time_point*: frame used for a time series.
    *channel*: one channel (grayscale); default all channels, tinted with
      *colors* (default green+magenta / RGB).
    *z_scale*: Z step / pixel size, so the side views have true proportions —
      read from the file's voxel size when omitted.
    *crosshair*: thin lines marking the cut position (editable annotations).

    The composite keeps the source's XY pixel size, so a scale bar on it is
    correct for all three views.
    """
    tree, root = _load(pyf_path)
    src, pair, err = _source_panel(root, group_path, image_index)
    if err:
        return f"ERROR: {err}"
    fn, ser = pair
    info, err = _stack(fn, ser)
    if err:
        return f"ERROR: {err}"
    sz = info["sizes"]
    if sz.get("d", 1) < 2:
        return f"ERROR: {os.path.basename(fn)} is not a Z stack (dimensions {info['order']})."
    W, H, Z = sz["w"], sz["h"], sz["d"]
    if not (0 <= x < W and 0 <= y < H):
        return f"ERROR: ({x}, {y}) is outside the image ({W} x {H} px)."
    if z is not None and not 0 <= z < Z:
        return f"ERROR: z={z} out of range (0..{Z - 1})."
    if not 0 <= time_point < sz.get("t", 1):
        return f"ERROR: time_point {time_point} out of range."
    nch = sz.get("c", 1)
    if channel is not None and not 0 <= channel < nch:
        return f"ERROR: channel {channel} out of range ({nch} channel(s))."
    if z_scale is None:
        if info.get("vz") and info.get("vx"):
            z_scale = info["vz"] / info["vx"]
        else:
            return ("ERROR: the file has no voxel depth — pass z_scale "
                    "(Z step divided by the pixel size).")
    if z_scale <= 0:
        return "ERROR: z_scale must be > 0."
    k = 1 if channel is not None else nch
    cols = [str(c).lower() for c in colors] if colors else \
        _DEFAULT_SPLIT_COLORS.get(k, ["red", "green", "blue", "gray"] * 2)[:k]
    if len(cols) < k:
        return f"ERROR: need {k} colours."
    full = {"gray": 0xFFFFFF, "grey": 0xFFFFFF, "white": 0xFFFFFF, "red": 0xFF0000,
            "green": 0x00FF00, "blue": 0x0000FF, "cyan": 0x00FFFF,
            "magenta": 0xFF00FF, "yellow": 0xFFFF00}
    try:
        tints = [((full[c] >> 16 & 255) / 255., (full[c] >> 8 & 255) / 255.,
                  (full[c] & 255) / 255.) if c in full else None for c in cols]
        if None in tints:
            raise ValueError(f"unsupported colour in {cols}")
        bgi = _color_to_int(background)
    except (ValueError, KeyError) as e:
        return f"ERROR: {e}"
    bg = ((bgi >> 16 & 255) / 255., (bgi >> 8 & 255) / 255., (bgi & 255) / 255.)
    Zp = max(1, int(round(Z * z_scale)))
    script = _make_ortho_script(info["path"], ser, info["order"], x, y, z, time_point,
                                channel, tints, z_scale, gap, bg)
    (container, err), gp = _target_container(root, group_path, target_group_path)
    if err:
        return f"ERROR: {err}"
    img = _new_image2d("__orthogonal_views__")
    img.find("filename").text = "None"
    _set_child_text(img, "custom_loading_script", _encode_str(script))
    _set_child_text(img, "user_comments", _encode_str(
        f"orthogonal views of {os.path.basename(fn)} at x={x}, y={y}"
        + (f", z={z}" if z is not None else " (XY = max projection)")
        + f", Z scaled ×{z_scale:.3g}"))
    if info.get("vx"):
        _set_child_text(img, "px_to_unit_conversion_factor", repr(float(info["vx"])))
    RW, RH = W + gap + Zp, H + gap + Zp
    _set_child_text(img, "width", repr(float(RW)))
    _set_child_text(img, "height", repr(float(RH)))
    annots = img.find("annotations")
    if crosshair:
        c = _color_to_int(crosshair_color)
        cx, cy = x + 0.5, y + 0.5
        yz0, xz0 = W + gap, H + gap
        segs = [(cx, 0, cx, H), (0, cy, W, cy),                 # XY
                (cx, xz0, cx, RH),                              # XZ: x position
                (yz0, cy, RW, cy)]                              # YZ: y position
        if z is not None:
            zc = (z + 0.5) * z_scale
            segs += [(0, xz0 + zc, W, xz0 + zc), (yz0 + zc, 0, yz0 + zc, H)]
        for s in segs:
            line = _new_roi_line(*s, c, 0.65, 0.8, False, False)
            annots.append(line)
    if label:
        annots.append(_new_tatext2d(label, "top left", color=0xFFFFFF))
    _append_image(container, img, is_root=(not gp))
    _save(tree, pyf_path, recompute=True)
    return (f"Orthogonal views added to group {gp}: XY {W}×{H}, side views {Zp} px deep "
            f"(Z ×{z_scale:.3g}); cut at x={x}, y={y}"
            + (f", z={z}" if z is not None else ", XY = max projection") + ".")
