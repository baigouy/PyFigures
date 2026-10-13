"""Build a PyFigures figure from a declarative *recipe* (YAML or JSON).

A recipe is the reproducible, git-diffable description of a figure: which images
and CSV data go in which row, with LUTs, crops, scale bars, plots, lettering,
journal size and caption. Building it only orchestrates existing PyFigures tools
(create_figure, add_group, add_image, set_lut, transform_image, set_scale_bar,
add_data_plot, resize_figure, set_figure_caption, ...) — no separate layout engine.

Example (``fig1.yaml``)::

    output: figures/Figure1.pyf        # relative to this recipe file
    journal: nature                    # optional -> resize_figure
    column: double
    letter_panels: true                # default true -> A, B, C...
    caption: "WT vs KO gut, 63x."      # optional; omitted -> auto stub
    background: white                  # optional: colour of the gaps between panels
    label_background: black            # optional: box behind letters / labels
    defaults:                          # applied where a panel doesn't override
      px_to_unit: 0.1                  # um per pixel
      scale_bar: {units: 10, unit: "um"}
    rows:                              # each row = one horizontal group
      - - {image: wt.tif, lut: red}
        - {image: ko.tif}
      - - {glob: "reps/rep*.tif", lut: gray}   # one panel per match (sorted)
      - - {plot: counts.csv, kind: box, ylabel: "cells / field"}
      - [a.tif, b.tif]                 # bare names = images without options

The complete reference is docs/RECIPES.md.

A stack is ONE panel by default (``projection: max`` for a Z stack). Showing
several views of it is opt-in::

      - - {montage: embryo.tif, axis: t, frames: 5}       # time-lapse row + stamps
      - - {split: cells.tif, names: [DAPI, GFP, RFP]}     # channels + merge
      - - image: embryo.tif
          projection: max
          arrows: [{at: [120, 150], from: s}]             # tip exactly on (120,150)
          kymograph: {line: [40, 150, 200, 150], width: 3}
      - - {image: zstack.tif, orthogonal: {at: [200, 180], z: 12}}

An image panel can also carry text, corner labels, ROIs, insets, zoom
callouts and significance brackets; other panel kinds are ``merge:`` (separate
channel files overlaid), ``colorbar:`` (a LUT calibration bar) and ``script:``
(a Python-generated panel, only with ``allow_scripts: true``). A row can be a
mapping with its own orientation, spacing, label row and side label, and the
recipe can size the figure (journal or explicit width), set fonts, tidy text,
read pixel sizes from metadata, write alt text, copy another figure's style
and export it (``exports: [pdf, png, ledger, ...]``). ``checks: [integrity,
scale, ...]`` stop the build before the exports when one fails;
``consolidate: true`` bundles the source files; ``template`` + ``fill`` fills a
template's slots instead of building rows; ``properties`` sets any stored
panel field.

Shortcut: a flat ``panels: [...]`` list with ``columns: N`` is chunked into rows.

Command line (e.g. as a Makefile target, so the figure rebuilds — and its
statistics re-run — whenever the data or the recipe changes)::

    python -m pyfigures.recipe build fig1.yaml

Errors (missing file, unknown key, a tool refusing a value) raise RecipeError,
and the CLI exits with status 1, so pipelines fail loudly.
"""
from __future__ import annotations

import glob as _glob
import html
import json
import os
import re
import sys

__all__ = ["RecipeError", "RecipeChecksFailed", "load_recipe", "build_figure_from_recipe",
           "main"]


class RecipeError(ValueError):
    """Invalid recipe or a build step that failed."""


class RecipeChecksFailed(RecipeError):
    """The figure was built and saved (``output``) but some `checks` failed,
    so it was not exported."""

    def __init__(self, message, output, checks):
        super().__init__(message)
        self.output = output
        self.checks = checks


_TOP_KEYS = {"output", "journal", "column", "letter_panels", "caption", "title",
             "defaults", "rows", "panels", "columns", "spacing", "label_background",
             "background",
             # sizing, typography and finishing
             "width_mm", "width_cm", "width_in", "width_px", "dpi", "font", "min_font_pt",
             "tidy_text", "letter_placement", "auto_configure", "alt_text",
             "copy_style_from", "copy_style_aspects", "exports", "allow_scripts",
             # checks, bundling, templates
             "checks", "consolidate", "template", "fill"}
_IMAGE_KEYS = {"lut", "crop", "scale_bar", "px_to_unit", "label", "projection",
               "arrows", "kymograph", "orthogonal",
               "rotate", "flip", "channels", "z_range", "display_range", "text",
               "corner_labels", "rois", "inset", "zoom", "brackets", "properties"}
_PLOT_KEYS = {"kind", "error", "ylabel", "xlabel", "title", "stats_mode",
              "annotate_stats", "only_significant", "label"}
# a stack shown as several panels is opt-in: `montage:` / `split:` panels
_MONTAGE_KEYS = {"axis", "frames", "columns", "projection", "channel", "lut",
                 "interval", "unit", "stamps", "stamp_format", "stamp_placement",
                 "stamp_color", "time_zero", "series"}
_SPLIT_KEYS = {"names", "colors", "gray", "merge", "merge_label", "projection", "frame",
               "series", "label_placement"}
_MERGE_KEYS = {"colors", "mode", "label", "label_placement", "normalization"}
_COLORBAR_KEYS = {"vmin", "vmax", "label", "orientation", "ticks", "tick_labels",
                  "panel_label"}
_SCRIPT_KEYS = {"label"}
# a montage / split / merge also takes a scale bar (on its LAST panel only)
_SERIES_BAR_KEYS = {"scale_bar", "px_to_unit"}
# panel-local extras that make no sense repeated on every glob match
_SINGLE_PANEL_ONLY = {"label", "arrows", "kymograph", "orthogonal", "text", "corner_labels",
                      "rois", "inset", "zoom", "brackets"}
_PANEL_KINDS = ("image", "glob", "plot", "montage", "split", "merge", "colorbar", "script")
_KIND_KEYS = {"image": _IMAGE_KEYS, "glob": _IMAGE_KEYS - _SINGLE_PANEL_ONLY,
              "plot": _PLOT_KEYS, "montage": _MONTAGE_KEYS | _SERIES_BAR_KEYS,
              "split": _SPLIT_KEYS | _SERIES_BAR_KEYS,
              "merge": _MERGE_KEYS | _SERIES_BAR_KEYS,
              "colorbar": _COLORBAR_KEYS, "script": _SCRIPT_KEYS}
_DEFAULT_KEYS = (_IMAGE_KEYS | _PLOT_KEYS) - _SINGLE_PANEL_ONLY - {"title"}
_ROW_KEYS = {"panels", "orientation", "spacing", "labels", "labels_position",
             "labels_orientation", "side_label", "side_label_position"}
_CROP_KEYS = {"left", "right", "top", "bottom"}
_SCALE_BAR_KEYS = {"units", "unit", "color", "placement", "label"}
_ARROW_KEYS = {"at", "from", "length", "color", "stroke", "head", "both_ends", "label"}
_KYMO_KEYS = {"line", "width", "channel", "projection", "frame_height", "cmap", "mark_line",
              "line_color", "label"}
_ORTHO_KEYS = {"at", "z", "time_point", "channel", "colors", "z_scale", "gap", "background",
               "crosshair", "crosshair_color", "label"}
_TEXT_KEYS = {"text", "placement"}
_CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")
_ROI_SHAPES = ("rect", "ellipse", "line", "polygon", "circle", "square", "point", "points")
_ROI_KEYS = set(_ROI_SHAPES) | {"color", "fill", "stroke", "opacity", "arrow", "both_ends",
                                "style", "size"}
# number of values per shape ([x, y] lists for polygon / points)
_ROI_ARITY = {"rect": 4, "ellipse": 4, "line": 4, "circle": 3, "square": 3, "point": 2}
_INSET_KEYS = {"image", "placement", "size", "border", "border_color"}
_ZOOM_KEYS = {"box", "corner", "size", "color", "line_color", "stroke", "connectors", "border",
              "image"}
_BRACKET_KEYS = {"x1", "x2", "y", "label", "tick", "color", "stroke", "font_pt", "label_gap",
                 "whiskers"}
_FONT_KEYS = {"family", "size", "italic"}
_AUTO_KEYS = {"lut_preset", "scale_bar_width", "unit", "placement", "first_image_only"}
_FLIPS = {"h": (True, False), "v": (False, True), "hv": (True, True), "both": (True, True)}
# export name -> (default file suffix, kind)
_EXPORTS = {"png": (".png", "figure"), "jpg": (".jpg", "figure"), "jpeg": (".jpg", "figure"),
            "tif": (".tif", "figure"), "tiff": (".tif", "figure"), "svg": (".svg", "figure"),
            "pdf": (".pdf", "figure"), "latex": ("_latex.pdf", "latex"),
            "print": ("_print.tif", "print"), "video": (".mp4", "video"),
            "source_data": ("_source_data", "source_data"), "review": ("_review.html", "review"),
            "caption": ("_caption.txt", "caption"), "ledger": ("_ledger.json", "ledger"),
            "colorblind": ("_colorblind.png", "colorblind"),
            "pptx": (".pptx", "pptx"), "illustrator": (".jsx", "illustrator"),
            "jsx": (".jsx", "illustrator")}
_EXPORT_KEYS = {"format", "path", "dpi", "color_mode", "frame_mode", "with_caption",
                "cvd_type"}
# checks: name -> the options it takes (besides `check` and `fail`)
_CHECKS = {"integrity": {"hamming_threshold", "min_clones"},
           "scale": {"tolerance"},
           "scale_bars": set(),
           "labels": set(),
           "resolution": {"min_dpi"},
           "journal": {"min_font_pt", "min_dpi", "require_sans_serif"}}
_PROPERTY_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# fields `properties` may not touch: the file (use `image`), code (a script would
# bypass allow_scripts), and what the layout computes itself
_MANAGED_PROPERTIES = {"filename", "custom_loading_script", "_proxy_stale", "_raw_svg_bytes",
                       "annotations_count", "x", "y", "width", "height", "scale", "isSet",
                       "immutable", "dimensions"}


# ---------------------------------------------------------------------------
# loading + validation
# ---------------------------------------------------------------------------
def load_recipe(path: str) -> dict:
    """Read a recipe file (.yaml/.yml needs PyYAML; .json needs nothing)."""
    if not os.path.isfile(path):
        raise RecipeError(f"recipe not found: {path}")
    text = open(path, encoding="utf-8").read()
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            raise RecipeError("YAML recipes need PyYAML (pip install pyyaml); "
                              "or write the recipe as .json") from None
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise RecipeError(f"invalid YAML in {path}: {e}") from None
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RecipeError(f"invalid JSON in {path}: {e}") from None
    if not isinstance(data, dict):
        raise RecipeError("a recipe must be a mapping (key: value) at the top level")
    return data


def _panel_kind(panel, where):
    if not isinstance(panel, dict):
        raise RecipeError(f"{where}: a panel must be a mapping, got {panel!r}")
    kinds = [k for k in _PANEL_KINDS if k in panel]
    if len(kinds) != 1:
        raise RecipeError(f"{where}: a panel needs exactly one of "
                          + " / ".join(_PANEL_KINDS))
    kind = kinds[0]
    unknown = set(panel) - {kind} - _KIND_KEYS[kind]
    if unknown:
        raise RecipeError(f"{where}: unknown key(s) for a {kind} panel: {sorted(unknown)} "
                          f"(allowed: {sorted(_KIND_KEYS[kind])})")
    return kind


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _bool_key(recipe, key, default):
    """A real true/false only: bool("false") is True, so a quoted 'false' must
    not silently mean yes."""
    v = recipe.get(key, default)
    if not isinstance(v, bool):
        raise RecipeError(f"'{key}' must be true or false (unquoted), got {v!r}")
    return v


def _check_crop(crop, where):
    if not isinstance(crop, dict) or set(crop) - _CROP_KEYS:
        raise RecipeError(f"{where}: crop must be a mapping with keys {sorted(_CROP_KEYS)}")
    for k, v in crop.items():
        if not _is_int(v) or v < 0:
            raise RecipeError(f"{where}: crop.{k} must be a non-negative integer (pixels)")


def _check_scale_bar(sb, where):
    if not isinstance(sb, dict) or "units" not in sb or set(sb) - _SCALE_BAR_KEYS:
        raise RecipeError(f"{where}: scale_bar must be a mapping with 'units' "
                          f"(allowed keys: {sorted(_SCALE_BAR_KEYS)})")


def _check_mapping(value, allowed, required, where, name):
    if not isinstance(value, dict) or set(value) - allowed or not set(required) <= set(value):
        raise RecipeError(f"{where}: {name} must be a mapping with "
                          + (f"{sorted(required)} and " if required else "")
                          + f"optional keys {sorted(set(allowed) - set(required))}")


def _check_point(v, n, where, name):
    if not (isinstance(v, (list, tuple)) and len(v) == n and all(_is_num(x) for x in v)):
        raise RecipeError(f"{where}: {name} must be a list of {n} numbers (image pixels)")


def _as_list(v):
    return v if isinstance(v, list) else [v]


def _check_extras(opts, where, base):
    """The per-panel extras of an image panel (validated before anything is
    built, so a typo never leaves a half-built figure)."""
    arrows = opts.get("arrows")
    if arrows is not None:
        if not isinstance(arrows, list):
            raise RecipeError(f"{where}: arrows must be a list")
        for k, a in enumerate(arrows):
            _check_mapping(a, _ARROW_KEYS, {"at"}, where, f"arrow {k + 1}")
            _check_point(a["at"], 2, where, f"arrow {k + 1} 'at'")
    if "kymograph" in opts:
        _check_mapping(opts["kymograph"], _KYMO_KEYS, {"line"}, where, "kymograph")
        _check_point(opts["kymograph"]["line"], 4, where, "kymograph 'line'")
    if "orthogonal" in opts:
        _check_mapping(opts["orthogonal"], _ORTHO_KEYS, {"at"}, where, "orthogonal")
        _check_point(opts["orthogonal"]["at"], 2, where, "orthogonal 'at'")
    if "rotate" in opts and not _is_num(opts["rotate"]):
        raise RecipeError(f"{where}: rotate must be a number of degrees")
    if "flip" in opts and opts["flip"] not in _FLIPS:
        raise RecipeError(f"{where}: flip must be one of {sorted(_FLIPS)}")
    if "channels" in opts and not (isinstance(opts["channels"], list) and opts["channels"]
                                   and all(isinstance(c, bool) for c in opts["channels"])):
        raise RecipeError(f"{where}: channels must be a list of true/false, one per channel")
    if "z_range" in opts:
        z = opts["z_range"]
        if not (isinstance(z, list) and len(z) == 2 and all(_is_int(v) and v >= 0 for v in z)
                and z[0] < z[1]):
            raise RecipeError(f"{where}: z_range must be [first, last) slice numbers, first < last")
    if "display_range" in opts:
        d = opts["display_range"]
        if not (isinstance(d, list) and len(d) == 2 and all(_is_num(v) for v in d) and d[0] < d[1]):
            raise RecipeError(f"{where}: display_range must be [min, max] with min < max")
    if "text" in opts:
        for k, t in enumerate(_as_list(opts["text"])):
            if not isinstance(t, str):
                _check_mapping(t, _TEXT_KEYS, {"text"}, where, f"text {k + 1}")
    if "corner_labels" in opts:
        cl = opts["corner_labels"]
        if not isinstance(cl, dict) or not cl or set(cl) - set(_CORNERS):
            raise RecipeError(f"{where}: corner_labels must map some of {list(_CORNERS)} "
                              "to a label or a list of labels")
    if "rois" in opts:
        if not isinstance(opts["rois"], list):
            raise RecipeError(f"{where}: rois must be a list")
        for k, roi in enumerate(opts["rois"]):
            name = f"roi {k + 1}"
            if not isinstance(roi, dict) or set(roi) - _ROI_KEYS:
                raise RecipeError(f"{where}: {name} must be a mapping with one of "
                                  f"{list(_ROI_SHAPES)} (optional {sorted(_ROI_KEYS - set(_ROI_SHAPES))})")
            shapes = [s for s in _ROI_SHAPES if s in roi]
            if len(shapes) != 1:
                raise RecipeError(f"{where}: {name} needs exactly one of {list(_ROI_SHAPES)}")
            shape = shapes[0]
            if shape in ("polygon", "points"):
                pts = roi[shape]
                least = 2 if shape == "polygon" else 1
                if not (isinstance(pts, list) and len(pts) >= least):
                    raise RecipeError(f"{where}: {name} {shape} needs a list of [x, y] points")
                for p in pts:
                    _check_point(p, 2, where, f"{name} {shape} point")
            else:
                _check_point(roi[shape], _ROI_ARITY[shape], where, f"{name} {shape}")
            if "size" in roi and not (_is_num(roi["size"]) and roi["size"] > 0):
                raise RecipeError(f"{where}: {name} size must be a positive number")
    for key, allowed, required in (("inset", _INSET_KEYS, {"image"}), ("zoom", _ZOOM_KEYS, {"box"})):
        if key in opts:
            for k, item in enumerate(_as_list(opts[key])):
                _check_mapping(item, allowed, required, where, f"{key} {k + 1}")
                if key == "zoom":
                    _check_point(item["box"], 4, where, f"zoom {k + 1} 'box'")
                if "image" in item and not os.path.isfile(_resolve(base, item["image"])):
                    raise RecipeError(f"{where}: {key} image not found: {_resolve(base, item['image'])}")
    if "brackets" in opts:
        if not isinstance(opts["brackets"], list):
            raise RecipeError(f"{where}: brackets must be a list")
        for k, b in enumerate(opts["brackets"]):
            _check_mapping(b, _BRACKET_KEYS, {"x1", "x2", "y"}, where, f"bracket {k + 1}")
            if not all(_is_num(b[c]) for c in ("x1", "x2", "y")):
                raise RecipeError(f"{where}: bracket {k + 1} x1 / x2 / y must be numbers")
    if "properties" in opts:
        props = opts["properties"]
        if not isinstance(props, dict) or not props:
            raise RecipeError(f"{where}: properties must map property names to values")
        for name, value in props.items():
            if not isinstance(name, str) or not _PROPERTY_NAME.match(name):
                raise RecipeError(f"{where}: property name {name!r} is not valid")
            if name in _MANAGED_PROPERTIES:
                raise RecipeError(f"{where}: property {name} can't be set from a recipe "
                                  "(the file goes in 'image'; code needs a script panel)")
            if value is not None and not isinstance(value, (str, int, float, bool, list)):
                raise RecipeError(f"{where}: property {name} must be a text, number, "
                                  "true/false, a list or null")


def _resolve(base_dir, p):
    p = os.path.expanduser(str(p))
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(base_dir, p))


def _rows_of(recipe):
    """The rows as [(row_options, [panel, ...]), ...]."""
    has_rows, has_panels = "rows" in recipe, "panels" in recipe
    if has_rows == has_panels:
        raise RecipeError("a recipe needs either 'rows' or 'panels' (not both)")
    if has_rows:
        rows = recipe["rows"]
        if not isinstance(rows, list) or not rows:
            raise RecipeError("'rows' must be a non-empty list of rows")
        if "columns" in recipe:
            raise RecipeError("'columns' only applies to a flat 'panels' list")
        out = []
        for r, row in enumerate(rows):
            if isinstance(row, dict):
                bad = set(row) - _ROW_KEYS
                if bad or "panels" not in row:
                    raise RecipeError(f"row {r + 1}: a row mapping needs 'panels' and may have "
                                      f"{sorted(_ROW_KEYS - {'panels'})}"
                                      + (f" (unknown: {sorted(bad)})" if bad else ""))
                panels = row["panels"]
                opts = {k: v for k, v in row.items() if k != "panels"}
            else:
                panels, opts = row, {}
            if not isinstance(panels, list) or not panels:
                raise RecipeError(f"row {r + 1}: needs a non-empty list of panels")
            out.append((opts, panels))
        return out
    panels = recipe["panels"]
    if not isinstance(panels, list) or not panels:
        raise RecipeError("'panels' must be a non-empty list")
    cols = recipe.get("columns", len(panels))
    if not _is_int(cols) or cols < 1:
        raise RecipeError("'columns' must be a positive integer")
    return [({}, panels[i:i + cols]) for i in range(0, len(panels), cols)]


def _check_row_opts(opts, n_panels, where):
    if "orientation" in opts and opts["orientation"] not in ("X", "Y", "row", "column"):
        raise RecipeError(f"{where}: orientation must be X (row) or Y (column)")
    if "spacing" in opts and (not _is_int(opts["spacing"]) or opts["spacing"] < 0):
        raise RecipeError(f"{where}: spacing must be a non-negative integer (pixels)")
    if "labels" in opts:
        labels = opts["labels"]
        if isinstance(labels, list):
            if not all(isinstance(x, str) for x in labels):
                raise RecipeError(f"{where}: labels must be text")
        elif not isinstance(labels, str):
            raise RecipeError(f"{where}: labels must be a text or a list of texts")
    if opts.get("labels_position", "above") not in ("above", "below"):
        raise RecipeError(f"{where}: labels_position must be above or below")
    if opts.get("labels_orientation", "horizontal") not in ("horizontal", "vertical",
                                                             "vertical_flipped"):
        raise RecipeError(f"{where}: labels_orientation must be horizontal, vertical "
                          "or vertical_flipped")
    if "side_label" in opts and not isinstance(opts["side_label"], str):
        raise RecipeError(f"{where}: side_label must be a text")
    if opts.get("side_label_position", "left") not in ("left", "right", "top", "bottom"):
        raise RecipeError(f"{where}: side_label_position must be left, right, top or bottom")


def _check_top(recipe, base):
    """Figure-level finishing keys."""
    widths = [k for k in ("width_mm", "width_cm", "width_in", "width_px") if k in recipe]
    if len(widths) > 1:
        raise RecipeError(f"give one figure width, not {widths}")
    if widths and recipe.get("journal"):
        raise RecipeError("give either 'journal' or an explicit width, not both")
    for k in widths:
        v = recipe[k]
        if not _is_num(v) or v <= 0 or (k == "width_px" and not _is_int(v)):
            raise RecipeError(f"'{k}' must be a positive number")
    if "dpi" in recipe and (not _is_int(recipe["dpi"]) or recipe["dpi"] < 10):
        raise RecipeError("'dpi' must be an integer (dots per inch)")
    if "font" in recipe:
        f = recipe["font"]
        if isinstance(f, str):
            pass
        elif not isinstance(f, dict) or set(f) - _FONT_KEYS or not f:
            raise RecipeError(f"'font' must be a family name or a mapping with {sorted(_FONT_KEYS)}")
    if "min_font_pt" in recipe and (not _is_num(recipe["min_font_pt"]) or recipe["min_font_pt"] <= 0):
        raise RecipeError("'min_font_pt' must be a positive number of points")
    if "auto_configure" in recipe:
        a = recipe["auto_configure"]
        if not isinstance(a, bool) and (not isinstance(a, dict) or set(a) - _AUTO_KEYS):
            raise RecipeError(f"'auto_configure' must be true/false or a mapping with {sorted(_AUTO_KEYS)}")
    if "alt_text" in recipe and not isinstance(recipe["alt_text"], str):
        raise RecipeError("'alt_text' must be 'auto' or the alt text itself")
    if "copy_style_from" in recipe:
        src = _resolve(base, recipe["copy_style_from"])
        if not os.path.isfile(src):
            raise RecipeError(f"copy_style_from: file not found: {src}")
    if "copy_style_aspects" in recipe:
        asp = recipe["copy_style_aspects"]
        ok = {"fonts", "letters", "scale_bars", "spacing", "plots"}
        if not isinstance(asp, list) or not asp or set(asp) - ok:
            raise RecipeError(f"'copy_style_aspects' must be a list of {sorted(ok)}")
    if "exports" in recipe:
        exps = recipe["exports"]
        if not isinstance(exps, list):
            raise RecipeError("'exports' must be a list (e.g. [pdf, png])")
        for e in exps:
            fmt = e if isinstance(e, str) else (e.get("format") if isinstance(e, dict) else None)
            if isinstance(e, dict) and set(e) - _EXPORT_KEYS:
                raise RecipeError(f"export {e!r}: allowed keys are {sorted(_EXPORT_KEYS)}")
            if fmt not in _EXPORTS:
                raise RecipeError(f"export {e!r}: format must be one of {sorted(_EXPORTS)}")
    if "checks" in recipe:
        checks = recipe["checks"]
        if not isinstance(checks, list) or not checks:
            raise RecipeError(f"'checks' must be a list of {sorted(_CHECKS)}")
        for c in checks:
            name = c if isinstance(c, str) else (c.get("check") if isinstance(c, dict) else None)
            if name not in _CHECKS:
                raise RecipeError(f"check {c!r}: must be one of {sorted(_CHECKS)}")
            if isinstance(c, dict):
                bad = set(c) - _CHECKS[name] - {"check", "fail"}
                if bad:
                    raise RecipeError(f"check {name}: unknown option(s) {sorted(bad)} (allowed: "
                                      f"{sorted(_CHECKS[name] | {'fail'})})")
            if name in ("resolution", "journal") and not (
                    recipe.get("journal") or any(k in recipe for k in
                                                 ("width_mm", "width_cm", "width_in"))):
                raise RecipeError(f"check {name} needs the figure's print size: give "
                                  "'journal' or width_mm / width_cm / width_in")
    if "consolidate" in recipe:
        c = recipe["consolidate"]
        if not isinstance(c, bool) and not (isinstance(c, str) and c.lower().endswith(".pyf")):
            raise RecipeError("'consolidate' must be true or the .pyf to write the bundle to")
    if "template" in recipe:
        src = _resolve(base, recipe["template"])
        if not src.lower().endswith(".pyf") or not os.path.isfile(src):
            raise RecipeError(f"template: .pyf not found: {src}")
        if "rows" in recipe or "panels" in recipe:
            raise RecipeError("a template recipe fills the template's slots: give 'fill', "
                              "not 'rows' / 'panels'")
        if not isinstance(recipe.get("fill"), list) or not recipe["fill"]:
            raise RecipeError("'template' needs 'fill': the image files for its slots, in order")
    elif "fill" in recipe:
        raise RecipeError("'fill' only goes with 'template'")
    letter = recipe.get("letter_placement", "top left")
    if letter not in ("top left", "top right", "bottom left", "bottom right"):
        raise RecipeError("'letter_placement' must be a corner such as 'top left'")


def _plan(recipe: dict, recipe_path: str) -> dict:
    """Validate the recipe and expand it into a concrete build plan (resolved
    paths, globs expanded, defaults merged). Raises RecipeError."""
    base = os.path.dirname(os.path.abspath(recipe_path))
    unknown = set(recipe) - _TOP_KEYS
    if unknown:
        raise RecipeError(f"unknown top-level key(s): {sorted(unknown)} "
                          f"(allowed: {sorted(_TOP_KEYS)})")
    if "output" not in recipe:
        raise RecipeError("'output' (the .pyf to write) is required")
    output = _resolve(base, recipe["output"])
    if not output.lower().endswith(".pyf"):
        raise RecipeError("'output' must end in .pyf")

    from pyfigures.mcp_tools.core import _label_background_text
    for key in ("label_background", "background"):
        if recipe.get(key) is not None:
            try:
                _label_background_text(recipe[key])
            except ValueError as e:
                raise RecipeError(f"{key}: {e}") from None

    spacing = recipe.get("spacing", 3)
    if not _is_int(spacing) or spacing < 0:
        raise RecipeError(f"'spacing' must be a non-negative integer (pixels), got {spacing!r}")
    # a template carries its own letters: only re-letter when asked
    letter_panels = _bool_key(recipe, "letter_panels", "template" not in recipe)
    allow_scripts = _bool_key(recipe, "allow_scripts", False)
    tidy = _bool_key(recipe, "tidy_text", False)
    _check_top(recipe, base)

    defaults = recipe.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise RecipeError("'defaults' must be a mapping")
    bad = set(defaults) - _DEFAULT_KEYS
    if bad:
        raise RecipeError(f"unknown key(s) in defaults: {sorted(bad)}")

    fill = []
    for k, f in enumerate(recipe.get("fill") or []):
        if not isinstance(f, str):
            raise RecipeError(f"fill {k + 1}: must be an image file or a glob")
        if any(ch in f for ch in "*?["):
            matches = sorted(m for m in _glob.glob(_resolve(base, f)) if os.path.isfile(m))
            if not matches:
                raise RecipeError(f"fill {k + 1}: glob {f!r} matched no files")
            fill.extend(matches)
        else:
            p = _resolve(base, f)
            if not os.path.isfile(p):
                raise RecipeError(f"fill {k + 1}: file not found: {p}")
            fill.append(p)

    plan_rows = []
    for r, (row_opts, row) in enumerate(_rows_of(recipe) if "template" not in recipe else []):
        _check_row_opts(row_opts, len(row), f"row {r + 1}")
        plan_row = []
        for c, panel in enumerate(row):
            where = f"row {r + 1}, panel {c + 1}"
            if isinstance(panel, str):
                panel = {"image": panel}          # `- [wt.tif, ko.tif]` shorthand
            kind = _panel_kind(panel, where)
            merged = {k: v for k, v in defaults.items() if k in _KIND_KEYS[kind]}
            merged.update({k: v for k, v in panel.items() if k != kind})
            if "crop" in merged:
                _check_crop(merged["crop"], where)
            if "scale_bar" in merged:
                _check_scale_bar(merged["scale_bar"], where)
            if kind in ("image", "glob"):
                _check_extras(merged, where, base)
            if kind == "script":
                if not allow_scripts:
                    raise RecipeError(f"{where}: script panels run Python code — add "
                                      "'allow_scripts: true' to the recipe if you trust it")
                if not isinstance(panel["script"], str) or not panel["script"].strip():
                    raise RecipeError(f"{where}: script must be the Python code (text)")
                plan_row.append((kind, panel["script"], merged))
                continue
            if kind == "colorbar":
                plan_row.append((kind, str(panel["colorbar"]), merged))
                continue
            if kind in ("split", "merge") and isinstance(panel[kind], list):
                files = [_resolve(base, f) for f in panel[kind]]
                missing = [f for f in files if not os.path.isfile(f)]
                if missing:
                    raise RecipeError(f"{where}: file(s) not found: {', '.join(missing)}")
                if kind == "merge" and len(files) < 2:
                    raise RecipeError(f"{where}: a merge needs at least two channel files")
                plan_row.append((kind, files, merged))
                continue
            if kind == "merge":
                raise RecipeError(f"{where}: merge must be a list of channel files")
            if kind == "glob":
                matches = sorted(_glob.glob(_resolve(base, panel["glob"])))
                matches = [m for m in matches if os.path.isfile(m)]
                if not matches:
                    raise RecipeError(f"{where}: glob {panel['glob']!r} matched no files")
                for m in matches:
                    plan_row.append(("image", m, dict(merged)))
                continue
            path = _resolve(base, panel[kind])
            if not os.path.isfile(path):
                raise RecipeError(f"{where}: file not found: {path}")
            plan_row.append((kind, path, merged))
        if "labels" in row_opts and isinstance(row_opts["labels"], list) \
                and len(row_opts["labels"]) != len(plan_row):
            raise RecipeError(f"row {r + 1}: {len(row_opts['labels'])} labels for "
                              f"{len(plan_row)} panels (give one per panel, or one text)")
        plan_rows.append((row_opts, plan_row))

    font = recipe.get("font")
    if isinstance(font, str):
        font = {"family": font}
    return {
        "output": output,
        "base": base,
        "rows": plan_rows,
        "journal": recipe.get("journal"),
        # YAML reads `column: 1.5` / `2` as numbers
        "column": (f"{recipe['column']:g}" if isinstance(recipe.get("column"), (int, float))
                   else recipe.get("column", "single")),
        "width": {k: recipe[k] for k in ("width_mm", "width_cm", "width_in", "width_px")
                  if k in recipe},
        "dpi": recipe.get("dpi", 300),
        "letter_panels": letter_panels,
        "letter_placement": recipe.get("letter_placement", "top left"),
        "caption": recipe.get("caption"),
        "title": recipe.get("title", "Figure"),
        "spacing": spacing,
        "label_background": recipe.get("label_background"),
        "background": recipe.get("background"),
        "font": font,
        "min_font_pt": recipe.get("min_font_pt"),
        "tidy_text": tidy,
        "auto_configure": recipe.get("auto_configure", False),
        "alt_text": recipe.get("alt_text"),
        "copy_style_from": (_resolve(base, recipe["copy_style_from"])
                            if "copy_style_from" in recipe else None),
        "copy_style_aspects": recipe.get("copy_style_aspects"),
        "exports": recipe.get("exports") or [],
        "checks": recipe.get("checks") or [],
        "consolidate": recipe.get("consolidate", False),
        "template": _resolve(base, recipe["template"]) if "template" in recipe else None,
        "fill": fill,
    }


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _check(result, step):
    """Fail loudly on an ERROR from a tool; return any WARNING lines."""
    if isinstance(result, str) and result.startswith("ERROR"):
        raise RecipeError(f"{step}: {result}")
    if isinstance(result, str):
        return [ln[len("WARNING: "):] for ln in result.splitlines()
                if ln.startswith("WARNING: ")]
    return []


_HTML_TAG = re.compile(r"<\s*/?\s*[A-Za-z][^>]*>")


def _label_html(label: str) -> str:
    """Plain labels become white rich text (black vanishes on micrographs);
    real HTML is kept as written; a plain '<' / '&' is escaped, not parsed."""
    if _HTML_TAG.search(label):
        return label
    return f"<font color=#ffffff>{html.escape(label, quote=False)}</font>"


def _last_series_panel(pyf, group_path):
    """(group_path, image_index) of the last panel of the montage / split
    group at *group_path* (a multi-row montage nests one group per row)."""
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _navigate_group
    grp, err = _navigate_group(ET.parse(pyf).getroot(), group_path)
    if err:
        raise RecipeError(err)
    path = list(group_path)
    while True:
        content = list(grp.find("content"))
        imgs = [c for c in content if c.tag == "Image2D"]
        if imgs:
            return path, len(imgs) - 1
        subs = [c for c in content if c.tag == "Group"]
        if not subs:
            raise RecipeError(f"group {group_path} has no panels")
        path.append(len(subs) - 1)
        grp = subs[-1]


def _image_size(path):
    """(width, height) in pixels of the image file (zoom callouts need it)."""
    from pyfigures.stack_info import stack_info
    info = stack_info(path)
    return info["sizes"]["w"], info["sizes"]["h"]


def _apply_image_settings(M, out, gp, i, path, opts, base, step, scale_bar):
    """Everything an image panel asks for, on the panel at (gp, i)."""
    w = []
    cfg = {}
    if opts.get("projection"):
        cfg["projection"] = opts["projection"]
    if "channels" in opts:
        cfg["channels"] = list(opts["channels"])
    if "z_range" in opts:
        cfg["projection_z_start"], cfg["projection_z_end"] = opts["z_range"]
    if "display_range" in opts:
        lo, hi = opts["display_range"]
        cfg["normalization"] = json.dumps({"range": "custom", "min_value": lo, "max_value": hi})
    if cfg:
        w += _check(M.configure_image(out, gp, i, **cfg), step + " display")
    lut = opts.get("lut")
    if lut:
        luts = [str(x).upper() if x else None for x in lut] \
            if isinstance(lut, list) else [str(lut).upper()]
        w += _check(M.set_lut(out, gp, i, luts), step + " lut")
    tf = {}
    crop = opts.get("crop")
    if crop:
        tf.update({f"crop_{k}": v for k, v in crop.items()})
    if "rotate" in opts:
        tf["rotation"] = float(opts["rotate"])
    if "flip" in opts:
        tf["flip_h"], tf["flip_v"] = _FLIPS[opts["flip"]]
    if tf:
        w += _check(M.transform_image(out, gp, i, **tf), step + " crop / rotation")
    sb = opts.get("scale_bar")
    if sb:
        w += scale_bar(gp, i, sb, opts.get("px_to_unit"), step)
    for k, t in enumerate(_as_list(opts.get("text") or [])):
        t = {"text": t} if isinstance(t, str) else t
        w += _check(M.add_annotation(out, gp, i, _label_html(str(t["text"])),
                                     placement=t.get("placement", "bottom left")),
                    step + f" text {k + 1}")
    if opts.get("corner_labels"):
        corners = {c: [_label_html(str(x)) for x in _as_list(v)]
                   for c, v in opts["corner_labels"].items()}
        w += _check(M.add_corner_labels(out, gp, i, **corners), step + " corner labels")
    for k, roi in enumerate(opts.get("rois") or []):
        style = {"color": roi.get("color", "yellow"), "stroke": roi.get("stroke", 2.0),
                 "opacity": roi.get("opacity", 1.0)}
        name = step + f" roi {k + 1}"
        if "rect" in roi or "ellipse" in roi:
            shape = "rect" if "rect" in roi else "ellipse"
            x, y, rw, rh = roi[shape]
            fn = M.add_roi_rect if shape == "rect" else M.add_roi_ellipse
            w += _check(fn(out, gp, i, x, y, rw, rh, fill_color=roi.get("fill"), **style), name)
        elif "circle" in roi or "square" in roi:
            # centred shapes: circle [cx, cy, radius], square [cx, cy, side]
            shape = "circle" if "circle" in roi else "square"
            cx, cy, s = roi[shape]
            half = s if shape == "circle" else s / 2.0
            fn = M.add_roi_ellipse if shape == "circle" else M.add_roi_rect
            w += _check(fn(out, gp, i, cx - half, cy - half, 2 * half, 2 * half,
                           fill_color=roi.get("fill"), **style), name)
        elif "point" in roi or "points" in roi:
            # markers: filled discs of diameter `size` (6 px) centred on each point
            pts = [roi["point"]] if "point" in roi else roi["points"]
            d = float(roi.get("size", 6))
            fill = roi.get("fill", style["color"])
            for x, y in pts:
                w += _check(M.add_roi_ellipse(out, gp, i, x - d / 2.0, y - d / 2.0, d, d,
                                              fill_color=fill, **style), name)
        elif "line" in roi:
            x1, y1, x2, y2 = roi["line"]
            w += _check(M.add_roi_line(out, gp, i, x1, y1, x2, y2, arrow=bool(roi.get("arrow")),
                                       arrow_at_both_ends=bool(roi.get("both_ends")), **style), name)
        else:
            w += _check(M.add_roi_polygon(out, gp, i, [list(p) for p in roi["polygon"]],
                                          fill_color=roi.get("fill"),
                                          style=roi.get("style", "polygon"), **style), name)
    for k, a in enumerate(opts.get("arrows") or []):
        kw = {"from_direction": a.get("from", "top left")}
        kw.update({key: a[key] for key in ("length", "color", "stroke", "head",
                                           "both_ends", "label") if key in a})
        w += _check(M.add_arrow(out, gp, i, a["at"][0], a["at"][1], **kw), step + f" arrow {k + 1}")
    for k, b in enumerate(opts.get("brackets") or []):
        kw = {key: b[key] for key in ("label", "tick", "color", "stroke", "font_pt", "label_gap")
              if key in b}
        if "whiskers" in b:
            kw["whiskers_point"] = b["whiskers"]
        w += _check(M.add_significance_bracket(out, gp, i, b["x1"], b["x2"], b["y"], **kw),
                    step + f" bracket {k + 1}")
    for k, ins in enumerate(_as_list(opts.get("inset") or [])):
        kw = {"placement": ins.get("placement", "top right"),
              "size_fraction": ins.get("size", 0.25),
              "border_size": ins.get("border", 3),
              "border_color": ins.get("border_color", "white")}
        w += _check(M.add_inset(out, gp, i, _resolve(base, ins["image"]), **kw),
                    step + f" inset {k + 1}")
    zooms = _as_list(opts.get("zoom") or [])
    if zooms:
        pw, ph = _image_size(path)
        for k, z in enumerate(zooms):
            x, y, zw, zh = z["box"]
            kw = {"inset_corner": z.get("corner", "top right"),
                  "inset_fraction": z.get("size", 0.4),
                  "box_color": z.get("color", "yellow"),
                  "line_color": z.get("line_color", z.get("color", "yellow")),
                  "stroke": z.get("stroke", 1.5),
                  "connectors": z.get("connectors", 2),
                  "inset_border": z.get("border", 2)}
            if "image" in z:
                kw["inset_filename"] = _resolve(base, z["image"])
            w += _check(M.add_zoom_callout(out, gp, i, x, y, zw, zh, pw, ph, **kw),
                        step + f" zoom {k + 1}")
    # escape hatch, applied last so it wins: any stored property by name
    # (a typo would otherwise add a field nothing reads)
    props = opts.get("properties") or {}
    known = set(json.loads(_ok(M.list_image_properties(out, gp, i), step))) if props else set()
    for name, value in props.items():
        if name not in known or name in _MANAGED_PROPERTIES:
            raise RecipeError(f"{step}: property {name!r} can't be set from a recipe "
                              f"(settable: {sorted(known - _MANAGED_PROPERTIES)})")
        text = value if isinstance(value, str) else repr(value)
        w += _check(M.set_image_property(out, gp, i, name, text), step + f" property {name}")
    return w


def _add_derived_panels(M, out, gp, i, opts, step):
    """Kymograph / orthogonal views of the image at (gp, i): new panels right
    after it. Returns (warnings, number of panels added)."""
    w = []
    added = 0
    if "kymograph" in opts:
        ky = dict(opts["kymograph"])
        x1, y1, x2, y2 = ky.pop("line")
        if "width" in ky:
            ky["line_width"] = ky.pop("width")
        w += _check(M.add_kymograph(out, gp, i, x1, y1, x2, y2, **ky), step + " kymograph")
        added += 1
    if "orthogonal" in opts:
        ov = dict(opts["orthogonal"])
        x, y = ov.pop("at")
        w += _check(M.add_orthogonal_views(out, gp, i, int(x), int(y), **ov),
                    step + " orthogonal views")
        added += 1
    return w, added


def _export(M, out, spec, base):
    """One entry of 'exports'; returns (path, warnings)."""
    if isinstance(spec, str):
        spec = {"format": spec}
    fmt = spec["format"]
    suffix, kind = _EXPORTS[fmt]
    stem = os.path.splitext(out)[0]
    target = _resolve(base, spec["path"]) if "path" in spec else stem + suffix
    if os.path.dirname(target):
        os.makedirs(os.path.dirname(target), exist_ok=True)
    dpi = spec.get("dpi", 300)
    step = f"export {fmt}"
    if kind == "figure":
        res = M.export_figure(out, target, dpi=dpi)
    elif kind == "latex":
        res = M.export_latex(out, target, with_caption=bool(spec.get("with_caption", False)))
    elif kind == "print":
        res = M.export_print_ready(out, target, color_mode=spec.get("color_mode", "cmyk"), dpi=dpi)
    elif kind == "video":
        res = M.export_video(out, target, frame_mode=spec.get("frame_mode", "freeze"))
    elif kind == "source_data":
        res = M.export_source_data(out, target, dpi=dpi)
    elif kind == "review":
        res = M.export_review(out, target, dpi=spec.get("dpi", 150))
    elif kind == "ledger":
        res = M.export_adjustment_ledger(out)
        _check(res, step)
        with open(target, "w", encoding="utf-8") as f:
            f.write(res)
    elif kind == "pptx":
        res = M.export_pptx(out, target)
    elif kind == "illustrator":
        res = M.export_illustrator_script(out, target)
    elif kind == "colorblind":
        cvd = spec.get("cvd_type", "deuteranopia")
        try:
            M.simulate_color_blindness(out, cvd_type=cvd, out_path=target,
                                       dpi=spec.get("dpi", 150))
            res = ""
        except Exception as e:                  # the tool raises on a bad cvd_type
            res = f"ERROR: {e}"
    else:
        res = M.export_caption(out, target)
    warnings = _check(res, step)
    if not os.path.exists(target):
        raise RecipeError(f"{step}: nothing was written to {target} ({res})")
    return target, warnings


def _run_check(M, out, spec, plan):
    """One entry of 'checks'; returns (name, passed, message)."""
    if isinstance(spec, str):
        spec = {"check": spec}
    name = spec["check"]
    opts = {k: v for k, v in spec.items() if k not in ("check", "fail")}
    size = {"journal": plan["journal"], "column": plan["column"]} if plan["journal"] else \
        {k: v for k, v in plan["width"].items() if k != "width_px"}
    if name == "integrity":
        r = json.loads(_ok(M.check_image_integrity(out, **opts), "check integrity"))
        bad = r["flag_count"] or r["load_errors"]
        msg = r["summary"] + (f" ({len(r['load_errors'])} panel(s) could not be read)"
                              if r["load_errors"] else "")
        return name, not bad, msg
    if name == "scale":
        r = json.loads(_ok(M.check_scale_consistency(out, **opts), "check scale"))
        return name, r["inconsistent_count"] == 0, r["summary"]
    if name in ("scale_bars", "labels"):
        r = json.loads(_ok(M.audit_figure(out), f"check {name}"))
        key = "panels_missing_scale_bar" if name == "scale_bars" else "panels_missing_label"
        missing = r[key]
        what = "scale bar" if name == "scale_bars" else "label"
        if not missing:
            return name, True, f"every image panel has a {what}"
        where = ", ".join(f"group {m['group_path']} image {m['image_index']} "
                          f"({os.path.basename(str(m['filename']))})" for m in missing)
        return name, False, f"{len(missing)} panel(s) without a {what}: {where}"
    if name == "resolution":
        r = _ok(M.check_resolution(out, **size, **opts), "check resolution")
        return name, "[FAIL]" not in r, r.strip().splitlines()[-1]
    kw = dict(size, dpi=plan["dpi"])
    if plan["min_font_pt"] is not None:
        kw["min_font_pt"] = float(plan["min_font_pt"])
    kw.update(opts)
    r = _ok(M.check_journal_compliance(out, **kw), "check journal")
    fails = [ln.strip() for ln in r.splitlines() if "[FAIL]" in ln]
    return name, not fails, "; ".join(fails) or r.strip().splitlines()[0]


def _ok(result, step):
    """The result of a read-only tool, or RecipeError if it refused."""
    if isinstance(result, str) and result.startswith("ERROR"):
        raise RecipeError(f"{step}: {result}")
    return result


def _fill_template(M, out, template, files):
    """Copy *template* to *out* and put *files* in its slots, in order;
    returns (n_filled, warnings)."""
    import shutil
    shutil.copyfile(template, out)
    # drop the sidecars of a previous build (as create_figure does)
    for ext in (".caption.json", ".stats.json", ".alttext.json", ".sources.json"):
        if os.path.isfile(os.path.splitext(out)[0] + ext):
            os.remove(os.path.splitext(out)[0] + ext)
    slots = [s for s in json.loads(M.list_images(out)) if s["is_template"]]
    if len(files) > len(slots):
        raise RecipeError(f"fill: {len(files)} file(s) for {len(slots)} template slot(s)")
    w = []
    for k, (slot, f) in enumerate(zip(slots, files)):
        w += _check(M.fill_template(out, slot["group_path"], slot["image_index"], f),
                    f"fill {k + 1} ({os.path.basename(f)})")
    if len(files) < len(slots):
        w.append(f"{len(slots) - len(files)} template slot(s) left empty")
    return len(files), w


def build_figure_from_recipe(recipe_path: str) -> dict:
    """Build the figure described by *recipe_path*; returns a summary dict.
    Raises RecipeError on any invalid input or failed step."""
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.workflow import _finalize_draft, _caption_stub
    plan = _plan(load_recipe(recipe_path), recipe_path)
    out = plan["output"]
    base = plan["base"]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    warnings: list[str] = []

    def scale_bar(group_path, index, sb, px, step):
        return _check(M.set_scale_bar(
            out, group_path, index, float(sb["units"]),
            label=sb.get("label"),
            unit=sb.get("unit", "µm"),
            placement=sb.get("placement", "bottom right"),
            bar_color=sb.get("color", "white"),
            label_color=sb.get("color", "white"),
            px_to_unit=px), step + " scale bar")

    # create_figure also drops the statistics record / alt text of a previous
    # build, so Methods text never lists tests of panels no longer in the recipe
    n_images = n_plots = n_series = n_other = 0
    if plan["template"]:
        n_images, w = _fill_template(M, out, plan["template"], plan["fill"])
        warnings += w
    else:
        warnings += _check(M.create_figure(out, spacing=plan["spacing"]), "create_figure")
    image_tasks = []          # (row, group_path, image_index, path, opts, step)

    # pass 1: every panel, in order
    for r, (row_opts, row) in enumerate(plan["rows"]):
        orientation = {"row": "X", "column": "Y"}.get(row_opts.get("orientation"),
                                                      row_opts.get("orientation", "X"))
        row_spacing = row_opts.get("spacing", plan["spacing"])
        warnings += _check(M.add_group(out, orientation=orientation, spacing=row_spacing),
                           f"row {r + 1}")
        gp = [r]
        i = -1                      # index of the row's last Image2D panel
        n_sub = 0                   # montage / split groups nested in this row
        for c, (kind, path, opts) in enumerate(row):
            if isinstance(path, str) and kind not in ("script", "colorbar"):
                name = os.path.basename(path)
            elif isinstance(path, list):
                name = f"{len(path)} channel files"
            else:
                name = kind
            step = f"row {r + 1}, panel {c + 1} ({name})"
            if kind == "plot":
                kw = {k: opts[k] for k in ("kind", "error", "ylabel", "xlabel", "title",
                                           "stats_mode", "annotate_stats",
                                           "only_significant", "label") if k in opts}
                warnings += _check(M.add_data_plot(out, gp, path, **kw), step)
                n_plots += 1
                i += 1
                continue
            if kind == "montage":
                kw = {k: opts[k] for k in _MONTAGE_KEYS if k in opts}
                warnings += _check(M.add_stack_montage(out, path, parent_group_path=gp,
                                                       spacing=row_spacing, **kw), step)
                if opts.get("scale_bar"):
                    sp, si = _last_series_panel(out, gp + [n_sub])
                    warnings += scale_bar(sp, si, opts["scale_bar"], opts.get("px_to_unit"), step)
                n_sub += 1
                n_series += 1
                continue
            if kind == "split":
                kw = {k: opts[k] for k in ("names", "colors", "gray", "merge_label",
                                           "projection", "frame", "series",
                                           "label_placement") if k in opts}
                if "merge" in opts:
                    kw["include_merge"] = bool(opts["merge"])
                src = {"channel_files": path} if isinstance(path, list) else {"stack_path": path}
                warnings += _check(M.add_channel_split(out, parent_group_path=gp,
                                                       spacing=row_spacing, **src, **kw), step)
                if opts.get("scale_bar"):
                    sp, si = _last_series_panel(out, gp + [n_sub])
                    warnings += scale_bar(sp, si, opts["scale_bar"], opts.get("px_to_unit"), step)
                n_sub += 1
                n_series += 1
                continue
            if kind == "merge":
                kw = {k: opts[k] for k in ("colors", "mode", "label_placement", "normalization")
                      if k in opts}
                if opts.get("label"):
                    kw["label"] = _label_html(str(opts["label"]))
                warnings += _check(M.add_channel_merge(out, gp, path, **kw), step)
                i += 1
                if opts.get("scale_bar"):
                    warnings += scale_bar(gp, i, opts["scale_bar"], opts.get("px_to_unit"), step)
                n_other += 1
                continue
            if kind == "colorbar":
                kw = {k: opts[k] for k in ("vmin", "vmax", "label", "orientation", "ticks",
                                           "tick_labels", "panel_label") if k in opts}
                warnings += _check(M.add_lut_calibration_bar(out, gp, lut=path.upper(), **kw), step)
                i += 1
                n_other += 1
                continue
            if kind == "script":
                label = _label_html(str(opts["label"])) if opts.get("label") else ""
                warnings += _check(M.add_scripted_image(out, gp, path, label=label), step)
                i += 1
                n_other += 1
                continue
            label = opts.get("label") or ""
            if label:
                label = _label_html(str(label))
            warnings += _check(M.add_image(out, gp, path, label=label), step)
            n_images += 1
            i += 1
            image_tasks.append((r, gp, i, path, opts, step))
            # kymograph / orthogonal views go right after their source panel
            w, added = _add_derived_panels(M, out, gp, i, opts, step)
            warnings += w
            i += added

    # pass 2: pixel size / LUTs from the files' metadata — before the explicit
    # per-panel settings, so those always win
    auto = plan["auto_configure"]
    if auto:
        a = auto if isinstance(auto, dict) else {}
        warnings += _check(M.auto_configure_images(
            out, lut_preset=a.get("lut_preset", "fluorescence"),
            scale_bar_width=a.get("scale_bar_width", 10.0), unit=a.get("unit", "µm"),
            bar_placement=a.get("placement", "bottom right"),
            first_image_only=bool(a.get("first_image_only", False))), "auto_configure")

    # pass 3: per-panel settings (none of them adds or moves a panel)
    for r, gp, i, path, opts, step in image_tasks:
        warnings += _apply_image_settings(M, out, gp, i, path, opts, base, step, scale_bar)

    lettered = 0
    if plan["letter_panels"]:
        lettered, _ = _finalize_draft(out, True, plan["letter_placement"], None, None, "")

    # side labels and label rows add panels / groups: last row first, so the
    # indices of the rows still to do never shift
    for r in reversed(range(len(plan["rows"]))):
        row_opts = plan["rows"][r][0]
        if row_opts.get("side_label"):
            warnings += _check(M.add_side_label(
                out, [r], _label_html(row_opts["side_label"]),
                position=row_opts.get("side_label_position", "left")), f"row {r + 1} side label")
        if "labels" in row_opts:
            labels = row_opts["labels"]
            labels = [_label_html(x) for x in labels] if isinstance(labels, list) else _label_html(labels)
            warnings += _check(M.add_label_row(
                out, [r], labels, position=row_opts.get("labels_position", "above"),
                text_orientation=row_opts.get("labels_orientation", "horizontal")),
                f"row {r + 1} labels")

    if plan["label_background"] is not None:
        warnings += _check(M.set_label_background(out, plan["label_background"]),
                           "label background")
    if plan["background"] is not None:
        warnings += _check(M.set_figure_properties(out, page_background=plan["background"]),
                           "figure background")
    if plan["copy_style_from"]:
        warnings += _check(M.copy_style(plan["copy_style_from"], out,
                                        aspects=plan["copy_style_aspects"]), "copy_style_from")
    if plan["font"]:
        f = plan["font"]
        warnings += _check(M.set_figure_properties(out, font_family=f.get("family"),
                                                   font_size=f.get("size"),
                                                   font_italic=f.get("italic")), "font")
    if plan["tidy_text"]:
        warnings += _check(M.tidy_text(out), "tidy_text")
    if plan["journal"]:
        warnings += _check(M.resize_figure(out, journal=plan["journal"], column=plan["column"],
                                           dpi=plan["dpi"]), "journal resize")
    elif plan["width"]:
        warnings += _check(M.resize_figure(out, dpi=plan["dpi"], **plan["width"]), "resize")
    if plan["min_font_pt"] is not None:
        warnings += _check(M.enforce_min_font_size(out, min_pt=float(plan["min_font_pt"])),
                           "min_font_pt")
    caption = plan["caption"] if plan["caption"] is not None else _caption_stub(out)
    warnings += _check(M.set_figure_caption(out, caption, title=plan["title"]), "caption")
    if plan["alt_text"]:
        if plan["alt_text"].strip().lower() == "auto":
            warnings += _check(M.generate_alt_text(out, save=True), "alt_text")
        else:
            warnings += _check(M.set_alt_text(out, plan["alt_text"]), "alt_text")

    # checks: before the exports, so a failing figure is never exported
    checks, failed = {}, []
    for spec in plan["checks"]:
        name, passed, msg = _run_check(M, out, spec, plan)
        checks[name] = ("ok: " if passed else "FAILED: ") + msg
        if not passed:
            if isinstance(spec, dict) and spec.get("fail") is False:
                warnings.append(f"check {name}: {msg}")
            else:
                failed.append(f"{name}: {msg}")
    if failed:
        raise RecipeChecksFailed(f"{len(failed)} check(s) failed (the figure was saved to "
                                 f"{out}, not exported):\n- " + "\n- ".join(failed),
                                 out, checks)

    exported = []
    for spec in plan["exports"]:
        target, w = _export(M, out, spec, base)
        warnings += w
        exported.append(target)

    bundle = None
    if plan["consolidate"]:
        dest = out if plan["consolidate"] is True else _resolve(base, plan["consolidate"])
        if os.path.dirname(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
        r = json.loads(_ok(M.consolidate_figure(out, dest), "consolidate"))
        bundle = r["files_folder"]

    n_rows = len(plan["rows"])
    width_desc = (f"{plan['journal']} ({plan['column']})" if plan["journal"] else
                  (", ".join(f"{k}={v}" for k, v in plan["width"].items()) or None))
    return {
        "output": out,
        "rows": n_rows,
        "panels": n_images + n_plots + n_series + n_other,
        "images": n_images,
        "plots": n_plots,
        "stack_series": n_series,
        "other_panels": n_other,
        "lettered": lettered,
        "journal": f"{plan['journal']} ({plan['column']})" if plan["journal"] else None,
        "size": width_desc,
        "caption": "explicit" if plan["caption"] is not None else "auto stub",
        "exports": exported,
        "checks": checks,
        "consolidated": bundle,
        "template": plan["template"],
        "warnings": warnings,
        "summary": (f"Built {os.path.basename(out)}: {n_rows} row(s), "
                    f"{n_images} image(s), {n_plots} data plot(s)"
                    + (f", {n_series} montage/channel split(s)" if n_series else "")
                    + (f", {n_other} merge/colour bar/script panel(s)" if n_other else "")
                    + (f", sized for {plan['journal']}" if plan["journal"] else "")
                    + (f", {len(exported)} export(s)" if exported else "")
                    + (f", {len(checks)} check(s) passed" if checks and not
                       any(v.startswith("FAILED") for v in checks.values()) else
                       (f", {len(checks)} check(s) run" if checks else ""))
                    + (", files bundled" if bundle else "") + "."),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m pyfigures.recipe",
                                 description="Build PyFigures figures from recipes.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the .pyf described by a recipe")
    b.add_argument("recipe", nargs="+", help="recipe file(s) (.yaml / .yml / .json)")
    b.add_argument("--render", metavar="EXT",
                   help="also export each built figure next to it (e.g. png, pdf, svg)")
    args = ap.parse_args(argv)

    status = 0
    for rp in args.recipe:
        try:
            res = build_figure_from_recipe(rp)
            if args.render:
                from pyfigures.mcp_server import export_figure
                target = os.path.splitext(res["output"])[0] + "." + args.render.lstrip(".")
                rendered = export_figure(res["output"], target)
                res["rendered"] = rendered
                if not isinstance(rendered, str) or rendered.startswith("ERROR") \
                        or not os.path.isfile(target):
                    raise RecipeError(f"render to {target} failed: {rendered}")
            print(json.dumps(res, ensure_ascii=True, indent=2))
        except RecipeError as e:
            print(f"ERROR in {rp}: {e}", file=sys.stderr)
            status = 1
        except Exception as e:          # a bug, not a bad recipe: still go on with the others
            print(f"ERROR in {rp}: unexpected {type(e).__name__}: {e}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
