"""PyFigures MCP tools — Folder-to-figure workflows: scan, create from folder, draft figure, auto-configure images.

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
    _figure_font,
    _restyle_letters,
    _apply_scalebar_to_img,
    _child_text,
    _decode,
    _iter_panel_elements,
    _load,
    _new_tatext2d,
    _save,
    _scale_bar_legend_html,
    _set_child_text,
    _top_groups,
)
from .structure import (
    add_image,
    create_figure,
    resize_figure,
)
from .content import (
    _DATA_PLOT_KINDS,
    add_data_plot,
)
from .overlays import (
    set_figure_caption,
)

# ===========================================================================
# Folder-to-figure workflow
# ===========================================================================

_IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".tif", ".tiff", ".lif", ".czi", ".nd2", ".ims",
    ".oib", ".oif", ".jpg", ".jpeg", ".png", ".bmp",
})

_FLUORESCENCE_LUTS: dict[int, list[str]] = {
    1: ["GRAY"],
    2: ["GREEN", "RED"],
    3: ["BLUE", "GREEN", "RED"],
    4: ["BLUE", "GREEN", "RED", "CYAN"],
    5: ["BLUE", "GREEN", "RED", "CYAN", "MAGENTA"],
}
_FLUOR_CYCLE = ["BLUE", "GREEN", "RED", "CYAN", "MAGENTA", "YELLOW", "ORANGE", "PURPLE"]


def _luts_for_preset(preset: str, n_channels: int) -> list[str] | None:
    """Return a LUT list for *n_channels* under *preset*, or None to skip."""
    if preset == "none":
        return None
    if preset == "gray":
        return ["GRAY"] * n_channels
    if preset == "rgb":
        base = ["RED", "GREEN", "BLUE"]
        return (base + ["DEFAULT"] * max(0, n_channels - 3))[:n_channels]
    # fluorescence (default)
    if n_channels in _FLUORESCENCE_LUTS:
        return _FLUORESCENCE_LUTS[n_channels]
    return [_FLUOR_CYCLE[i % len(_FLUOR_CYCLE)] for i in range(n_channels)]


def _try_read_image_info(filepath: str) -> dict:
    """Try to read channel count and pixel size from an image file.

    Returns a dict with any of: channels (int), px_to_unit (float), unit (str).
    Returns {} on failure or for unsupported formats.  Only .tif/.tiff files
    are currently supported (requires tifffile, which is already a dependency).
    """
    if not os.path.isfile(filepath):
        return {}
    if Path(filepath).suffix.lower() not in (".tif", ".tiff"):
        return {}
    try:
        import tifffile  # already a project dependency
        with tifffile.TiffFile(filepath) as tif:
            info: dict = {}
            ij = tif.imagej_metadata or {}
            # Channel count: prefer ImageJ metadata, then series axes, then heuristic
            if "channels" in ij:
                info["channels"] = max(1, int(ij["channels"]))
            elif tif.series:
                axes = tif.series[0].axes.upper()
                shape = tif.series[0].shape
                if "C" in axes:
                    info["channels"] = shape[axes.index("C")]
                elif len(shape) == 2:
                    info["channels"] = 1
                elif len(shape) >= 3:
                    # Heuristic: small leading dim is likely channels
                    info["channels"] = shape[0] if 1 <= shape[0] <= 6 else 1
            # Pixel size: ImageJ unit string + XResolution TIFF tag
            unit_str = ij.get("unit", "")
            if unit_str and tif.pages:
                page = tif.pages[0]
                xr = page.tags.get("XResolution")
                if xr is not None:
                    val = xr.value
                    if isinstance(val, tuple) and len(val) == 2 and val[0] and val[1]:
                        px_per_unit = val[0] / val[1]
                        if px_per_unit > 0:
                            info["px_to_unit"] = 1.0 / px_per_unit
                            info["unit"] = (
                                unit_str
                                .replace("micron", "µm")
                                .replace("um", "µm")
                                .replace("Âµm", "µm")  # encoding artefact sometimes seen
                            )
            return info
    except Exception:
        return {}


def _collect_image_files(
    folder: str,
    pattern: str = "*",
    recursive: bool = False,
) -> list[str]:
    """Return naturally sorted image files in *folder* matching *pattern*.

    When *pattern* is the catch-all ``"*"``, files are further filtered to
    known image extensions.  Provide an explicit pattern like ``"*.tif"`` to
    bypass that extension filter.
    *recursive*: when True, also descend into immediate sub-directories.
    """
    try:
        from natsort import natsorted  # already a project dependency
    except ImportError:
        natsorted = sorted  # type: ignore[assignment]

    folder = os.path.normpath(folder)
    if not os.path.isdir(folder):
        return []

    catch_all = pattern.strip() in ("*", "**", "")
    files: list[str] = []

    walker = os.walk(folder) if recursive else [(folder, [], os.listdir(folder))]
    for dirpath, _dirs, filenames in walker:
        for name in filenames:
            fpath = os.path.join(dirpath, name)
            if not os.path.isfile(fpath):
                continue
            if not fnmatch.fnmatch(name.lower(), pattern.lower()):
                continue
            if catch_all and Path(name).suffix.lower() not in _IMAGE_EXTENSIONS:
                continue
            files.append(fpath)
    return natsorted(files)


def _auto_grid(n: int) -> tuple[int, int]:
    """Return (num_cols, num_rows) for *n* images in a near-square landscape grid."""
    if n <= 1:
        return (1, 1)
    base = max(1, round(math.sqrt(n)))
    best: tuple[int, int] = (n, 1)
    best_score: float = float("inf")
    for cols in range(max(1, base - 2), min(n, base + 3) + 1):
        rows = math.ceil(n / cols)
        empty = cols * rows - n
        aspect = cols / max(1, rows)
        # Penalise wasted slots heavily; prefer aspect ratio ≈ 1.5 (landscape)
        score = empty * 10.0 + abs(aspect - 1.5)
        if score < best_score:
            best_score = score
            best = (cols, rows)
    return best


@mcp.tool()
def scan_folder(folder: str, pattern: str = "*") -> str:
    """Scan a folder for image files and return layout suggestions as JSON.

    The returned object contains:

    - ``files``: naturally sorted list of matched image paths
    - ``count``: number of matched files
    - ``subfolders``: dict mapping sub-folder name → file list (only when image
      files exist directly inside immediate sub-directories)
    - ``layout_suggestions``: list of layout objects ready for
      ``create_figure_from_folder``, each with ``name``, ``layout``,
      ``num_cols``, ``num_rows`` (and ``groups`` for the subfolder suggestion)

    *pattern*: shell glob to filter filenames.  Default ``"*"`` restricts to
    known image extensions (.tif, .tiff, .lif, .czi, .nd2, .jpg, .png, …).
    Use ``"*.tif"`` or ``"MAX_*.tif"`` for tighter control.

    **Typical workflow**::

        scan_folder("/data/exp1")          # preview files and pick a layout
        create_figure_from_folder(
            "/data/exp1/fig.pyf", "/data/exp1",
            layout="grid", num_cols=3)
        auto_configure_images("/data/exp1/fig.pyf")
    """
    if not os.path.isdir(folder):
        return json.dumps({"error": f"Folder not found: {folder}"}, ensure_ascii=False)

    files = _collect_image_files(folder, pattern)
    n = len(files)

    # Detect immediate sub-directories that contain matching image files
    subfolders: dict[str, list[str]] = {}
    try:
        for entry in sorted(os.listdir(folder)):
            sub_path = os.path.join(folder, entry)
            if os.path.isdir(sub_path):
                sub_files = _collect_image_files(sub_path, pattern)
                if sub_files:
                    subfolders[entry] = sub_files
    except OSError:
        pass

    suggestions: list[dict] = []
    if n > 0:
        seen: set[tuple[int, int]] = set()

        def _add(name: str, layout: str, cols: int, rows: int,
                 extra: dict | None = None) -> None:
            key = (cols, rows)
            if layout == "grid" and key in seen:
                return
            seen.add(key)
            entry: dict = {"name": name, "layout": layout,
                           "num_cols": cols, "num_rows": rows}
            if extra:
                entry.update(extra)
            suggestions.append(entry)

        auto_c, auto_r = _auto_grid(n)
        if auto_c > 1 and auto_r > 1:
            _add(f"{auto_c}×{auto_r} grid (auto)", "grid", auto_c, auto_r)
        _add(f"Single row of {n}", "row", n, 1)
        _add(f"Single column of {n}", "column", 1, n)

        base = max(1, round(math.sqrt(n)))
        for c in range(max(1, base - 2), min(n, base + 4) + 1):
            r = math.ceil(n / c)
            if c > 1 and r > 1:
                _add(f"{c}×{r} grid", "grid", c, r)

        if subfolders:
            suggestions.append({
                "name": f"Grouped by subfolder ({len(subfolders)} group(s))",
                "layout": "subfolder",
                "num_cols": None,
                "num_rows": None,
                "groups": {k: len(v) for k, v in subfolders.items()},
            })

    return json.dumps(
        {"folder": folder, "count": n, "files": files,
         "subfolders": subfolders, "layout_suggestions": suggestions},
        ensure_ascii=False, indent=2,
    )


@mcp.tool()
def create_figure_from_folder(
    pyf_path: str,
    folder: str,
    pattern: str = "*",
    layout: str = "auto",
    num_cols: int | None = None,
    num_rows: int | None = None,
    group_by: str = "none",
    spacing: float = 3.0,
    label_from_filename: bool = True,
) -> str:
    """Create a .pyf figure populated with all image files from a folder.

    Scans *folder*, lays the files out in the requested grid, and saves a
    ready-to-open .pyf.  Follow up with ``auto_configure_images()`` to set LUTs
    and scale bars, or use ``scan_folder()`` first to preview the layout options.

    *pyf_path*: output path (e.g. ``"/data/exp1/fig.pyf"``).
    *folder*:   directory to scan.
    *pattern*:  shell glob filter (default ``"*"`` = all image formats).

    *layout*:
      - ``"auto"``   — near-square landscape grid (default)
      - ``"row"``    — single horizontal row
      - ``"column"`` — single vertical column
      - ``"grid"``   — explicit grid; use *num_cols* and/or *num_rows*

    *num_cols* / *num_rows*: fix one or both grid dimensions (``layout="grid"``).
      Providing just one computes the other automatically.

    *group_by*:
      - ``"none"``      — distribute files evenly across rows (default)
      - ``"subfolder"`` — one group per immediate sub-folder
      - ``"prefix"``    — group by the filename prefix before the first ``_`` or ``-``

    *spacing*: pixel gap between images and groups (default 3).
    *label_from_filename*: label each image with its file stem (default True).
    """
    if not os.path.isdir(folder):
        return f"ERROR: Folder not found: {folder}"

    # For subfolder grouping, images may live entirely in sub-directories;
    # defer the "no files" check until after we've scanned those sub-dirs.
    files = _collect_image_files(folder, pattern)
    if not files and group_by != "subfolder":
        return f"ERROR: No image files found in {folder!r} (pattern={pattern!r})."

    n = len(files)
    spacing_int = max(0, int(spacing))

    # ---- Determine groups of files ----------------------------------------
    groups: list[tuple[str, list[str]]] = []  # (label, file_paths)
    inner_orientation = "X"  # images within each group; overridden for "column"

    if group_by == "subfolder":
        # Scan immediate sub-directories for image files
        try:
            for entry in sorted(os.listdir(folder)):
                sub_path = os.path.join(folder, entry)
                if os.path.isdir(sub_path):
                    sub_files = _collect_image_files(sub_path, pattern)
                    if sub_files:
                        groups.append((entry, sub_files))
        except OSError:
            pass
        # Also include top-level files (if any)
        if files:
            groups.append(("", files))
        if not groups:
            return (
                f"ERROR: No image files found in {folder!r} or its immediate "
                f"sub-directories (pattern={pattern!r})."
            )

    elif group_by == "prefix":
        prefix_map: dict[str, list[str]] = {}
        for f in files:
            stem = Path(f).stem
            prefix = re.split(r"[_\-\s]", stem)[0]
            prefix_map.setdefault(prefix, []).append(f)
        for prefix, pf in prefix_map.items():
            groups.append((prefix, pf))

    else:  # group_by == "none" — distribute into rows
        layout_l = layout.lower().strip()
        if layout_l == "row":
            # One group, images side-by-side
            groups = [("", files)]
        elif layout_l == "column":
            # One group, images stacked vertically
            groups = [("", files)]
            inner_orientation = "Y"
        else:
            # "grid" or "auto": multiple groups (rows) of images side-by-side
            if layout_l == "grid":
                if num_cols is not None and num_rows is not None:
                    num_cols_eff, num_rows_eff = num_cols, num_rows
                elif num_cols is not None:
                    num_cols_eff = num_cols
                    num_rows_eff = math.ceil(n / num_cols_eff)
                elif num_rows is not None:
                    num_rows_eff = num_rows
                    num_cols_eff = math.ceil(n / num_rows_eff)
                else:
                    num_cols_eff, num_rows_eff = _auto_grid(n)
            else:  # auto
                num_cols_eff, num_rows_eff = _auto_grid(n)

            for row_idx in range(num_rows_eff):
                row_files = files[row_idx * num_cols_eff: (row_idx + 1) * num_cols_eff]
                if row_files:
                    groups.append(("", row_files))

    if not groups:
        return "ERROR: Could not determine group layout (no image files found)."

    # ---- Build the figure -------------------------------------------------
    result = create_figure(
        pyf_path,
        mode="groups",
        num_groups=len(groups),
        orientation=inner_orientation,
        spacing=spacing_int,
    )
    if result.startswith("ERROR"):
        return result

    total_added = 0
    skipped = []
    for g_idx, (_lbl, group_files) in enumerate(groups):
        for img_path in group_files:
            lbl = Path(img_path).stem if label_from_filename else ""
            res = add_image(pyf_path, [g_idx], img_path, label=lbl)
            if res.startswith("ERROR"):
                skipped.append(f"{Path(img_path).name} ({res[len('ERROR: '):].split(' (')[0]})")
            else:
                total_added += 1

    # ---- Summary ----------------------------------------------------------
    lines = [
        f"Created {pyf_path}",
        f"  {len(groups)} group(s), {total_added} image(s) from {folder}",
    ]
    if skipped:
        lines.append(f"WARNING: {len(skipped)} file(s) skipped: " + "; ".join(skipped[:10])
                     + (" …" if len(skipped) > 10 else ""))
    if group_by != "none":
        lines.append(f"  Grouped by: {group_by}")
        for lbl, gf in groups:
            lines.append(f"    {lbl or '(root)'}: {len(gf)} image(s)")
    else:
        cols_first = len(groups[0][1]) if groups else 0
        lines.append(
            f"  Grid: {len(groups)} row(s) × up to {cols_first} image(s) per row"
        )
    lines.append("\nNext: call auto_configure_images() to set LUTs and scale bars.")
    return "\n".join(lines)


def _caption_stub(pyf_path: str) -> str:
    """'Figure. (A) wt; (B) ko; (C) data plot. [Describe …]' for the panels of
    a figure, in panel order (used by draft_figure and recipes)."""
    import string
    from .stacks import SERIES_MARK
    from .export import _panel_label_texts
    _, root = _load(pyf_path)
    letters = string.ascii_uppercase
    parent = {c: p for p in root.iter() for c in p}
    # one entry per lettered panel: a montage / channel split is ONE panel
    # (lettered on its first frame) — the stub listed every frame, (A)-(F) for
    # a figure lettered A-C; text panels carry no letter
    entries: list[list] = []
    series_entry: dict = {}
    for img in _iter_panel_elements(root):
        if _child_text(img, "isText") is True:
            continue
        fn = _decode(img.findtext("filename"))
        base = (os.path.splitext(os.path.basename(str(fn)))[0]
                if fn and fn not in ("None", "@template@") else "data plot")
        if str(_decode(img.findtext("user_comments")) or "").startswith(SERIES_MARK):
            key = parent.get(img)
            names = [t for t in _panel_label_texts(img) if not (len(t) <= 2 and t.isalpha() and t.isupper())]
            if key in series_entry:
                series_entry[key][1].extend(names)
                continue
            series_entry[key] = [base, list(names)]
            entries.append(series_entry[key])
        else:
            entries.append([base, []])
    parts = []
    for idx, (base, names) in enumerate(entries):
        L = letters[idx] if idx < 26 else f"P{idx}"
        parts.append(f"({L}) {base}" + (f" ({', '.join(names)})" if names else ""))
    return ("Figure. " + "; ".join(parts)
            + ". [Describe the experiment, scale bars and statistics here.]")


def _finalize_draft(pyf_path, letter_panels, placement, px_to_unit, sb_units,
                    sb_unit, sb_color=0xFFFFFF):
    """One XML pass over a drafted figure: add a scale bar to each raster
    micrograph (if pixel size given) and a sequential A/B/C corner letter to each
    panel that lacks one. Returns (n_lettered, n_scale_bars)."""
    import string
    tree, root = _load(pyf_path)
    letters = string.ascii_uppercase
    lettered = bars = i = 0
    for img in _iter_panel_elements(root):
        fn = _decode(img.findtext("filename"))
        script = img.findtext("custom_loading_script")
        is_raster = (bool(fn and fn not in ("None", "@template@"))
                     and (not script or script.strip() in ("", "None")))
        annots = img.find("annotations")
        if annots is None:
            annots = ET.SubElement(img, "annotations")
        if px_to_unit and sb_units and is_raster:
            _apply_scalebar_to_img(img, float(sb_units),
                                   f"{sb_units:g} {sb_unit}".strip(),
                                   "bottom right", sb_color, float(px_to_unit))
            bars += 1
        # a montage / channel split is ONE figure panel: letter its first member only
        comment = _decode(img.findtext("user_comments")) or ""
        series_tail = comment.startswith("[series ") and not comment.startswith("[series 1/")
        # a LUT calibration bar belongs to the panel next to it: no letter of its own
        is_colour_bar = bool(script) and "ColorbarBase(" in (_decode(script) or "")
        if letter_panels and not series_tail and not is_colour_bar:
            has_letter = any(a.findtext("is_letter") in ("True", "b'True'")
                             for a in annots.iter("TAText2D"))
            if not has_letter and i < len(letters):
                # visible on its panel even when exported headless (the GUI's
                # auto-lettering recolours letters on screen, export does not):
                # black on white data-plot charts, white on image data
                is_chart = bool(script) and "from staplot import api" in (_decode(script) or "")
                ta = _new_tatext2d(letters[i], placement, is_letter=True,
                                   color=None if is_chart else 0xFFFFFF)
                # first, so pack2 keeps the letter in the corner and stacks
                # any label sharing that corner (e.g. "WT") below it
                annots.insert(0, ta)
                lettered += 1
        if not series_tail:
            i += 1
    if lettered:
        font = _figure_font(root)           # new letters in the figure's own font
        if font:
            _restyle_letters(root, **font)
    _save(tree, pyf_path)
    return lettered, bars


@mcp.tool()
def draft_figure(
    folder: str,
    out_pyf: str,
    pattern: str = "*",
    plot_kind: str = "bar",
    group_by: str = "none",
    journal: str | None = None,
    column: str = "single",
    px_to_unit: float | None = None,
    scale_bar_units: float | None = None,
    scale_bar_unit: str = "µm",
    letter_panels: bool = True,
    caption: bool = True,
) -> str:
    """**Draft a complete multi-panel figure from a folder of results, in one
    call** — the fastest path from data to a first-pass figure.

    Point it at a folder of images (and/or CSVs) and it assembles a ready-to-open
    ``.pyf``: it lays the images out in a grid, turns each CSV into a data-plot
    panel (with automatic significance tests), adds scale bars to the micrographs,
    letters every panel A/B/C…, sizes the figure to a journal column, and drafts a
    caption stub. Open the result and fine-tune — it does the tedious assembly so
    you start from a real draft, not a blank canvas.

    This is an orchestration over the individual tools (create_figure_from_folder,
    add_data_plot, set_scale_bar, resize_figure, set_figure_caption); call those
    directly for finer control.

    *folder*: directory of source files. *out_pyf*: output figure path.
    *pattern*: glob to filter images (CSVs are always included).
    *plot_kind*: chart type for CSV panels ("bar"/"box"/"violin"/"scatter"/"grouped").
    *group_by*: image grouping — "none" | "subfolder" | "prefix".
    *journal* / *column*: size to a journal preset (e.g. journal="nature",
      column="double"); omit to leave native size.
    *px_to_unit* + *scale_bar_units*: pixel size (units/px) and bar length to add a
      scale bar to each micrograph (e.g. px_to_unit=0.1, scale_bar_units=10).
    *scale_bar_unit*: physical unit label (default "µm").
    *letter_panels*: add A/B/C… corner letters (default True).
    *caption*: draft a caption stub listing the panels (default True).

    Returns JSON summarising what was assembled + suggested next steps.

    Example — draft a Nature double-column figure from a results folder::

        draft_figure("/data/exp1", "/data/exp1/Figure1.pyf",
                     journal="nature", column="double",
                     px_to_unit=0.1, scale_bar_units=10)
    """
    if not os.path.isdir(folder):
        return f"ERROR: no such folder: {folder}"
    if not out_pyf.lower().endswith(".pyf"):
        return "ERROR: out_pyf must end in .pyf."
    if plot_kind not in _DATA_PLOT_KINDS:
        return f"ERROR: plot_kind must be one of {_DATA_PLOT_KINDS}."
    out_pyf = os.path.abspath(out_pyf)

    images = _collect_image_files(folder, pattern)
    if group_by == "subfolder":
        # images may live only in the condition sub-folders (one row each);
        # counting the top level alone drafted a figure with no images at all
        for entry in sorted(os.listdir(folder)):
            sub_path = os.path.join(folder, entry)
            if os.path.isdir(sub_path):
                images += _collect_image_files(sub_path, pattern)
    csvs = sorted([str(p) for ext in ("*.csv", "*.tsv") for p in Path(folder).glob(ext)])
    if not images and not csvs:
        return f"ERROR: no image or CSV files found in {folder!r}."

    steps = []
    if images:
        r = create_figure_from_folder(out_pyf, folder, pattern=pattern,
                                      group_by=group_by,
                                      label_from_filename=(not letter_panels))
        if isinstance(r, str) and r.startswith("ERROR"):
            return r
        steps.append(f"laid out {len(images)} image(s)")
    else:
        create_figure(out_pyf, mode="canvas")

    n_plots = 0
    for c in csvs:
        rr = add_data_plot(out_pyf, [], c, kind=plot_kind, annotate_stats=True)
        if not (isinstance(rr, str) and rr.startswith("ERROR")):
            n_plots += 1
    if n_plots:
        steps.append(f"added {n_plots} data-plot panel(s) ({plot_kind})")

    lettered, bars = _finalize_draft(out_pyf, letter_panels, "top left",
                                     px_to_unit, scale_bar_units, scale_bar_unit)
    if bars:
        steps.append(f"added scale bars to {bars} micrograph(s)")
    if lettered:
        steps.append(f"lettered {lettered} panel(s)")

    if journal:
        rj = resize_figure(out_pyf, journal=journal, column=column)
        if not (isinstance(rj, str) and rj.startswith("ERROR")):
            steps.append(f"sized to {journal} {column}-column")

    if caption:
        set_figure_caption(out_pyf, _caption_stub(out_pyf), title="Figure")
        steps.append("drafted a caption stub")

    return json.dumps({
        "output": out_pyf,
        "n_images": len(images),
        "n_data_plots": n_plots,
        "panels_lettered": lettered,
        "scale_bars": bars,
        "journal": f"{journal} ({column})" if journal else None,
        "steps": steps,
        "next_steps": [
            "Open in PyFigures and drag panels to fine-tune the layout.",
            "Refine the caption stub (File -> Figure caption / legend).",
            "Run QC: check_resolution, check_scale_consistency, audit_figure.",
        ],
        "summary": (f"Drafted '{os.path.basename(out_pyf)}' with "
                    f"{len(images) + n_plots} panel(s): " + ", ".join(steps) + "."),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def auto_configure_images(
    pyf_path: str,
    lut_preset: str = "fluorescence",
    read_metadata: bool = True,
    set_scale_bar_from_metadata: bool = True,
    scale_bar_width: float = 10.0,
    unit: str = "µm",
    bar_placement: str = "bottom right",
    first_image_only: bool = False,
) -> str:
    """Auto-configure LUTs and scale bars for all images in a figure.

    Reads each image file's metadata to detect channel count and pixel size,
    then applies display settings in a single pass and saves the figure.

    **LUT presets** (*lut_preset*)

    - ``"fluorescence"`` (default) — biologically conventional colours:
        1 ch → GRAY,  2 ch → GREEN + RED,
        3 ch → BLUE + GREEN + RED,  4 ch → BLUE + GREEN + RED + CYAN
    - ``"rgb"``  — RED + GREEN + BLUE
    - ``"gray"`` — all channels in GRAY
    - ``"none"`` — skip LUT assignment

    **Scale bar**

    When *set_scale_bar_from_metadata* is True (default) and a pixel size can
    be extracted from the file (ImageJ TIFF metadata), a scale bar of
    *scale_bar_width* ``*unit*`` is added at *bar_placement*.

    *read_metadata*: False → skip file I/O (apply preset defaults only).
    *first_image_only*: True → configure only the first image per group.
    """
    if lut_preset not in ("fluorescence", "rgb", "gray", "none"):
        return "ERROR: lut_preset must be 'fluorescence', 'rgb', 'gray', or 'none'."

    tree, root = _load(pyf_path)

    # ---- Collect all content images (mirrors list_images traversal) --------
    all_images: list[tuple[ET.Element, list[int], int]] = []

    for ii, img in enumerate(c for c in root if c.tag == "Image2D"):
        all_images.append((img, [], ii))

    def _walk(grp: ET.Element, path: list[int]) -> None:
        content = grp.find("content")
        if content is None:
            return
        sub_g = img_i = 0
        for child in content:
            if child.tag == "Image2D":
                if child.findtext("isText", "False") != "True":  # skip side-labels
                    all_images.append((child, path, img_i))
                img_i += 1
            elif child.tag == "Group":
                if child.findtext("isText", "False") in ("False", ""):
                    _walk(child, path + [sub_g])
                sub_g += 1

    for gi, grp in enumerate(_top_groups(root)):
        if grp.findtext("isText", "False") in ("False", ""):
            _walk(grp, [gi])

    if not all_images:
        return "No configurable images found in the figure."

    # ---- Optionally restrict to first image per group ---------------------
    if first_image_only:
        seen_groups: set[tuple[int, ...]] = set()
        filtered: list[tuple[ET.Element, list[int], int]] = []
        for img, gp, ii in all_images:
            key = tuple(gp)
            if ii == 0 or key not in seen_groups:
                filtered.append((img, gp, ii))
                seen_groups.add(key)
        all_images = filtered

    # ---- Apply settings ---------------------------------------------------
    changed: list[str] = []
    unchanged: list[str] = []

    for img, group_path, img_idx in all_images:
        loc = ("canvas" if not group_path else f"group{group_path}") + f"[{img_idx}]"
        filename_raw = _decode(img.findtext("filename"))
        filepath = str(filename_raw) if filename_raw else ""

        info: dict = _try_read_image_info(filepath) if (read_metadata and filepath) else {}
        n_ch = info.get("channels", 1)
        img_changed: list[str] = []

        # LUT
        if lut_preset != "none":
            luts = _luts_for_preset(lut_preset, n_ch)
            if luts:
                _set_child_text(img, "LUTs", repr(luts))
                img_changed.append(f"LUTs={luts}")

        # Scale bar
        if set_scale_bar_from_metadata and "px_to_unit" in info:
            px_to_unit = info["px_to_unit"]
            unit_str = info.get("unit", unit)
            text = f"{scale_bar_width}{unit_str}"
            legend_html = _scale_bar_legend_html(text, 16777215)  # white
            action = _apply_scalebar_to_img(
                img, scale_bar_width, legend_html, bar_placement, 16777215, px_to_unit
            )
            img_changed.append(
                f"scale bar {action} ({text}, px_to_unit={px_to_unit:.5g})"
            )

        if img_changed:
            changed.append(f"  {loc}: {', '.join(img_changed)}")
        else:
            unchanged.append(loc)

    _save(tree, pyf_path)

    if not changed:
        sample = ", ".join(unchanged[:8]) + (" …" if len(unchanged) > 8 else "")
        return (
            f"Processed {len(all_images)} image(s) — no changes applied.\n"
            f"  Images: {sample}\n"
            "  Hint: metadata not readable (non-TIFF or missing ImageJ pixel-size tags)."
        )
    lines = [f"Configured {len(changed)} image(s):"] + changed
    if unchanged:
        sample = ", ".join(unchanged[:5]) + (" …" if len(unchanged) > 5 else "")
        lines.append(
            f"  ({len(unchanged)} image(s) unchanged — no metadata: {sample})"
        )
    return "\n".join(lines)


def _saved_style_names():
    try:
        from ..journal_styles import list_styles
        return [s["use_as"] for s in list_styles()]
    except Exception:
        return []


@mcp.tool()
def recipe_reference() -> str:
    """The recipe grammar: an annotated example plus EVERY accepted key, per
    panel kind, with the journal names and export formats — read this before
    writing a recipe for build_figure_from_recipe. Generated from the recipe
    code itself, so it is always complete and current (the long-form guide with
    explanations is docs/RECIPES.md)."""
    from .. import recipe as R
    from .core import _JOURNAL_ALIASES, _JOURNAL_PRESETS
    ref = {
        "overview": R.__doc__.strip(),
        "top_level_keys": sorted(R._TOP_KEYS),
        "panel_kinds": "a panel is a bare file name (an image) or a mapping whose kind key "
                       "holds the source: " + ", ".join(R._PANEL_KINDS),
        "keys_per_panel_kind": {k: sorted(v) for k, v in R._KIND_KEYS.items()},
        "defaults_keys": sorted(R._DEFAULT_KEYS),
        "row_mapping_keys": sorted(R._ROW_KEYS),
        "sub_keys": {
            "crop": sorted(R._CROP_KEYS), "scale_bar": sorted(R._SCALE_BAR_KEYS),
            "arrows[]": sorted(R._ARROW_KEYS), "kymograph": sorted(R._KYMO_KEYS),
            "orthogonal": sorted(R._ORTHO_KEYS), "text[]": sorted(R._TEXT_KEYS),
            "corner_labels": list(R._CORNERS), "rois[]": sorted(R._ROI_KEYS),
            "inset": sorted(R._INSET_KEYS), "zoom": sorted(R._ZOOM_KEYS),
            "brackets[]": sorted(R._BRACKET_KEYS), "font": sorted(R._FONT_KEYS),
            "auto_configure": sorted(R._AUTO_KEYS), "exports[] (mapping form)": sorted(R._EXPORT_KEYS),
        },
        "roi_values": {k: f"{n} numbers" for k, n in R._ROI_ARITY.items()},
        "flip": sorted(R._FLIPS),
        "exports": sorted(R._EXPORTS),
        "checks": {k: sorted(v) for k, v in R._CHECKS.items()},
        "journals": {k: v for k, v in sorted(_JOURNAL_PRESETS.items())},
        "journal_aliases": dict(sorted(_JOURNAL_ALIASES.items())),
        "saved_journal_styles": _saved_style_names(),
        "column": "one of the columns the journal has (see journals: widths in mm), e.g. "
                  "single, 1.5, double, triple; also '2 columns', 'full width'. A journal "
                  "that is missing: import its pasted guidelines (prepare_journal_style_import).",
        "notes": [
            "Paths are relative to the recipe file.",
            "px_to_unit is the pixel size (units per pixel), e.g. 0.1 for 0.1 um/pixel; "
            "never invent it: ask the user or read it from the image metadata "
            "(auto_configure: true).",
            "Give either journal (+ column) or one explicit width, not both.",
            "Build with build_figure_from_recipe(recipe_path, recipe_text=...), then check "
            "the result with render_preview; to change the figure, edit the recipe and build again.",
        ],
    }
    return json.dumps(ref, ensure_ascii=False, indent=1)


@mcp.tool()
def build_figure_from_recipe(recipe_path: str, recipe_text: str | None = None) -> str:
    """Build a figure from a declarative **recipe** (YAML or JSON) — the
    reproducible, git-diffable description of a figure. Often the simplest way
    to make a whole figure: call recipe_reference() FIRST for every accepted
    key, write the recipe, build it in one call, check render_preview, then
    edit the recipe and build again.

    *recipe_path*: the recipe file (.yaml/.yml/.json). With *recipe_text* (the
    recipe itself, YAML or JSON), the text is checked, written to recipe_path
    (so you need no file-writing tool and the figure stays reproducible) and
    built; relative paths in it are relative to recipe_path's folder.
    Invalid recipes are refused before anything is built.

    The recipe lists rows of panels (``image`` / ``glob`` / ``plot`` / ``montage``
    / ``split`` / ``merge`` / ``colorbar`` / ``script``) with LUTs, crops,
    rotation/flip, channels, display range, scale bars, text, corner labels,
    ROIs (rect, square, ellipse, circle, line, polygon, point markers), arrows, brackets, insets, zoom callouts, kymographs, orthogonal views
    and data-plot options; rows can be columns with their own spacing, label row
    and side label; plus lettering, journal or explicit width, fonts, min font
    size, typography tidy, metadata auto-configuration, alt text, style copied
    from another figure, caption and exports (pdf/png/svg/tif/latex/print/
    video/source_data/review/caption/ledger/colorblind/pptx/illustrator); ``properties`` sets any
    stored panel field. ``checks`` (integrity, scale, scale_bars, labels,
    resolution, journal) run before the exports — a failure returns an ERROR
    naming the failed checks (the .pyf is saved, nothing exported).
    ``consolidate`` bundles the source files; ``template`` + ``fill`` builds from
    a template's slots instead of rows. Every key: docs/RECIPES.md. Building only
    orchestrates the existing tools. Re-running it after
    the data changed rebuilds the figure and re-runs the statistics — also from
    the command line: ``python -m pyfigures.recipe build fig1.yaml``.

    Minimal example (paths relative to the recipe file)::

        output: Figure1.pyf
        journal: nature
        column: double
        defaults: {px_to_unit: 0.1, scale_bar: {units: 10, unit: um}}
        rows:
          - - {image: wt.tif, lut: red}
            - {image: ko.tif, lut: red}
          - - {glob: "reps/rep*.tif"}
          - - {plot: counts.csv, kind: box, ylabel: "cells / field"}

    Returns JSON {output, rows, panels, images, plots, stack_series,
    other_panels, lettered, journal, size, caption, exports, checks, consolidated,
    template, warnings, summary},
    or an ERROR string (missing file, unknown key,
    invalid value) — nothing is half-built silently.
    """
    from ..recipe import build_figure_from_recipe as _build, RecipeError, save_recipe_text
    try:
        if recipe_text:
            recipe_path = save_recipe_text(recipe_text, recipe_path)
        return json.dumps(_build(recipe_path), ensure_ascii=False, indent=2)
    except RecipeError as e:
        return f"ERROR: {e}"
