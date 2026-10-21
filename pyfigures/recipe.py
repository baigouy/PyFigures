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

from pyfigures.path_resolution import source_exists

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
             "defaults", "rows", "panels", "columns", "layout", "spacing", "label_background",
             "background",
             # sizing, typography and finishing
             "width_mm", "width_cm", "width_in", "width_px", "dpi", "font", "min_font_pt",
             "fit_height", "max_height_mm", "colors",
             "tidy_text", "letter_placement", "auto_configure", "alt_text",
             "copy_style_from", "copy_style_aspects", "exports", "allow_scripts",
             # checks, bundling, templates
             "checks", "consolidate", "download_remote", "template", "fill"}
_IMAGE_KEYS = {"lut", "crop", "scale_bar", "px_to_unit", "label", "projection",
               "arrows", "kymograph", "orthogonal",
               "rotate", "flip", "channels", "z_range", "display_range", "text",
               "corner_labels", "rois", "inset", "zoom", "brackets", "properties",
               "page"}
_PLOT_KEYS = {"kind", "error", "ylabel", "xlabel", "title", "stats_mode",
              "annotate_stats", "only_significant", "label", "latex", "colors"}
# a stack shown as several panels is opt-in: `montage:` / `split:` panels
_MONTAGE_KEYS = {"axis", "frames", "columns", "projection", "z_range", "z_slice", "channel", "lut",
                 "interval", "unit", "stamps", "stamp_format", "stamp_placement",
                 "stamp_color", "time_zero", "series"}
_SPLIT_KEYS = {"names", "colors", "gray", "merge", "merge_label", "projection", "frame",
               "series", "label_placement"}
_MERGE_KEYS = {"colors", "mode", "label", "label_placement", "normalization"}
_COLORBAR_KEYS = {"vmin", "vmax", "label", "orientation", "ticks", "tick_labels",
                  "panel_label"}
_SCRIPT_KEYS = {"label"}
_EQUATION_KEYS = {"font_size", "color", "fontset", "label", "engine", "preamble", "font"}
_TEX_KEYS = {"label", "preamble"}           # tex: LaTeX code panel
# a montage / split / merge also takes a scale bar, on its last panel (a split:
# the merge) unless scale_bar_panels: all
_SERIES_BAR_KEYS = {"scale_bar", "px_to_unit",
                    # ... and a crop, applied to EVERY panel it makes (e.g. text
                    # burned into the image's bottom rows)
                    "crop",
                    # scale_bar_panels: last | all overrides that default
                    "scale_bar_panels"}
# panel-local extras that make no sense repeated on every glob match
_SINGLE_PANEL_ONLY = {"label", "arrows", "kymograph", "orthogonal", "text", "corner_labels",
                      "rois", "inset", "zoom", "brackets"}
_PANEL_KINDS = ("image", "glob", "plot", "montage", "split", "merge", "colorbar", "script",
                "equation", "tex")
_KIND_KEYS = {"image": _IMAGE_KEYS, "glob": _IMAGE_KEYS - _SINGLE_PANEL_ONLY,
              "plot": _PLOT_KEYS, "montage": _MONTAGE_KEYS | _SERIES_BAR_KEYS,
              "split": _SPLIT_KEYS | _SERIES_BAR_KEYS,
              "merge": _MERGE_KEYS | _SERIES_BAR_KEYS,
              "colorbar": _COLORBAR_KEYS, "script": _SCRIPT_KEYS,
              "equation": _EQUATION_KEYS, "tex": _TEX_KEYS}
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
            "jsx": (".jsx", "illustrator"), "vectorcraft": (".vectorcraft", "vectorcraft"),
            "deckcraft": (".deckcraft", "deckcraft")}
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
def _yaml_hint(text: str) -> str:
    """What to write instead, for YAML slips small models repeated (Qwen3.5 9B
    sent "- [a.png]" followed by "    [b.png]" 30 times against the bare parser
    error)."""
    lines = str(text or "").splitlines()
    for n in range(1, len(lines)):
        prev, line = lines[n - 1], lines[n]
        m = re.match(r"^(\s*)-\s*\[(.*)\]\s*$", prev)
        if m and re.match(r"^\s+\[(.*)\]\s*$", line):
            joined = ", ".join(x.strip() for x in (m.group(2) + "," +
                                                    line.strip()[1:-1]).split(",") if x.strip())
            return (f" — line {n + 1} '{line.strip()}' continues the row of line {n}: the panels "
                    f"of one row go in ONE list, '{m.group(1)}- [{joined}]'; a new row starts "
                    f"with '- '. Or draw the layout: layout: |, then one line per row of panel "
                    f"names.")
    example = ("\n  rows:\n    - - {split: a.tif, names: [A, B]}     # row 1\n"
               "    - - {image: b.tif, zoom: {box: [10, 10, 50, 50], size: 0.4}}   # row 2, panel 1\n"
               "      - {plot: c.csv, kind: box}        # row 2, panel 2\n"
               "(or send the whole recipe as JSON)")
    for n in range(1, len(lines)):
        prev, line = lines[n - 1].rstrip(), lines[n]
        if line.lstrip().startswith(","):
            # Qwen3.5 9B: "  - - {a}\n    , {b}" for 10 builds in a row
            return (f" — line {n + 1} starts with ',': a block list has no commas between items; "
                    f"each panel starts with '- ' (one '- ' per panel, aligned under the first "
                    f"panel of its row) and each new row with '- - ' at the rows level:{example}")
        if re.match(r"^\s*-(\s+-)?\s+\{.*\}\s*$", prev) and re.match(r"^\s+[A-Za-z_]\w*\s*:", line):
            key = line.strip().split(":")[0]
            return (f" — line {n + 1} adds '{key}:' after the panel of line {n} was closed by "
                    f"'}}': put it INSIDE the braces, e.g. "
                    f"{prev.strip().lstrip('- ').rstrip()[:-1].rstrip()}, {line.strip()}}}{example}")
    return (" — check the indentation (two spaces per level) and that each row under rows: "
            "starts with '- ', e.g. rows:\\n  - [a.png, b.png]\\n  - [c.png]")


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
            raise RecipeError(f"invalid YAML in {path}: {e}{_yaml_hint(text)}") from None
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RecipeError(f"invalid JSON in {path}: {e}") from None
    if not isinstance(data, dict):
        raise RecipeError("a recipe must be a mapping (key: value) at the top level")
    return _fix_missing_spaces(data)


_KEY_VALUE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):(\S.*)$")


def _fix_missing_spaces(data):
    """YAML reads ``{bottom:24}`` (no space after the colon) as a key
    'bottom:24' with no value. A missing space is an easy slip (language models
    made it over and over), so such keys become ``bottom: 24``."""
    if isinstance(data, list):
        return [_fix_missing_spaces(v) for v in data]
    if not isinstance(data, dict):
        return data
    fixed = {}
    for k, v in data.items():
        m = _KEY_VALUE.match(k) if isinstance(k, str) and v is None else None
        if m:
            try:
                import yaml
                v = yaml.safe_load(m.group(2))
            except Exception:
                v = m.group(2)
            k = m.group(1)
        fixed[k] = _fix_missing_spaces(v)
    return fixed


def save_recipe_text(text: str, recipe_path: str) -> str:
    """Check that *text* is a valid YAML/JSON recipe mapping, then write it to
    *recipe_path* (.yaml/.yml/.json) so the figure stays reproducible; relative
    paths in the recipe are relative to that file. Returns the absolute path."""
    if not recipe_path.lower().endswith((".yaml", ".yml", ".json")):
        raise RecipeError("the recipe file must end in .yaml, .yml or .json")
    if recipe_path.lower().endswith(".json"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise RecipeError(f"invalid JSON recipe: {e}") from None
    else:
        try:
            import yaml
        except ImportError:
            raise RecipeError("YAML recipes need PyYAML (pip install pyyaml); "
                              "or give the recipe as JSON with a .json file name") from None
        try:
            data = yaml.safe_load(text)       # JSON is valid YAML too
        except yaml.YAMLError as e:
            raise RecipeError(f"invalid YAML recipe: {e}{_yaml_hint(text)}") from None
    if not isinstance(data, dict):
        raise RecipeError("a recipe must be a mapping (key: value) at the top level")
    recipe_path = os.path.abspath(recipe_path)
    os.makedirs(os.path.dirname(recipe_path), exist_ok=True)
    with open(recipe_path, "w", encoding="utf-8") as f:
        f.write(text)
    return recipe_path


def _panel_kind(panel, where):
    if not isinstance(panel, dict):
        raise RecipeError(f"{where}: a panel must be a mapping, got {panel!r}")
    kinds = [k for k in _PANEL_KINDS if k in panel]
    # `merge: true/false` on a split is its option (merged panel or not), not a merge panel
    if "split" in panel and isinstance(panel.get("merge"), bool) and "merge" in kinds:
        kinds.remove("merge")
    if sorted(kinds) == ["image", "split"] and isinstance(panel["image"], str) \
            and (panel["split"] is True or isinstance(panel["split"], dict)
                 and not {"image", "file", "path", "source", "split"} & set(panel["split"])):
        # {image: x.tif, split: {names: [...]}} or {image: x.tif, split: true}:
        # a split of that file, nothing else (Qwen3.5 9B resent it 4 times
        # against the "exactly one of" refusal)
        inner = panel["split"] if isinstance(panel["split"], dict) else {}
        fixed = {"split": panel["image"], **inner,
                 **{k: v for k, v in panel.items() if k not in ("image", "split")}}
        panel.clear()
        panel.update(fixed)
        kinds = ["split"]
    if len(kinds) != 1:
        found = f" (found {' and '.join(kinds)})" if kinds else f" (keys found: {sorted(panel)})"
        hint = ""
        if {"merge", "split"} & set(kinds) or "image" in kinds and "merge" in panel:
            hint = (" — each channel of ONE multi-channel file plus their merge is a single "
                    "panel {split: file.tif, names: [...], merge: true}; merge: [a.tif, b.tif] "
                    "overlays SEPARATE single-channel files")
        raise RecipeError(f"{where}: a panel needs exactly one of "
                          + " / ".join(_PANEL_KINDS) + found + hint)
    kind = kinds[0]
    if isinstance(panel[kind], dict):
        # {split: {image: x.tif, crop: ...}} — options nested inside the source.
        # Unambiguous, and small models looped on it (gpt-oss: 25 refusals in a
        # row), so it is read as the flat panel when every key is valid there.
        inner = dict(panel[kind])
        src_key = next((k for k in ("image", "file", "path", "source", kind) if k in inner), None)
        src = inner.pop(src_key) if src_key else "file.tif"
        if kind == "split" and isinstance(inner.get("lut"), list) and "colors" not in inner:
            inner["colors"] = [str(c).lower() for c in inner.pop("lut")]
        fixed = {kind: src, **inner, **{k: v for k, v in panel.items() if k != kind}}
        if src_key and isinstance(src, (str, list)):
            # flattened even with a wrong key inside, so the error below names
            # that key instead of repeating "flatten it" (gpt-oss looped on a
            # nested split that also held `channels`)
            panel.clear()
            panel.update(fixed)
        else:
            raise RecipeError(f"{where}: '{kind}:' takes the file name; put the other keys beside "
                              f"it, not inside — write {json.dumps(fixed, ensure_ascii=False)}")
    unknown = set(panel) - {kind} - _KIND_KEYS[kind]
    if unknown:
        hint = ""
        if kind == "split" and "channels" in unknown:
            hint = (" — a split already shows every channel plus their merge: remove "
                    "'channels'; give names (and colors) in channel order")
        elif any("split" in str(k) for k in unknown):
            hint = (" — to show each channel of a file, use a split panel: "
                    "{split: file.tif, names: [...]}")
        raise RecipeError(f"{where}: unknown key(s) for a {kind} panel: {sorted(unknown)} "
                          f"(allowed: {sorted(_KIND_KEYS[kind])}; recipe_reference() "
                          f"lists every key){hint}")
    return kind


# names models used for inset / zoom keys (the MCP tools' argument names
# among them) -> the recipe key; renamed only when the recipe key is absent
_INSET_ALIASES = {"filename": "image", "file": "image", "path": "image", "source": "image",
                  "size_fraction": "size", "inset_fraction": "size", "fraction": "size",
                  "corner": "placement"}
_ZOOM_ALIASES = {"size_fraction": "size", "inset_fraction": "size", "fraction": "size",
                 "region": "box", "rect": "box", "placement": "corner"}


def _percent_hint(v):
    """'(a percentage? 40 -> 0.4)' for a fraction given as a percentage."""
    if _is_num(v) and 1 < v <= 100:
        return f" — a percentage? write size: {round(v / 100, 3)}"
    return ""


def _renamed(item, aliases):
    out = dict(item)
    for old, new in aliases.items():
        if old in out and new not in out:
            out[new] = out.pop(old)
    return out


def _inset_as_zoom(item):
    """The zoom an inset without an image was meant to be: models wrote
    ``inset: {at: [x, y], size: [w, h]}`` to magnify a region. None when
    it does not look like one."""
    if not isinstance(item, dict) or "image" in item:
        return None
    box = item.get("box")
    if not (isinstance(box, list) and len(box) == 4):
        at = item.get("at") or item.get("position") or item.get("xy")
        wh = item.get("size") if isinstance(item.get("size"), list) else [item.get("width"), item.get("height")]
        if not (isinstance(at, list) and len(at) == 2 and isinstance(wh, list) and len(wh) == 2
                and all(_is_num(v) for v in at + wh)):
            return None
        box = [at[0], at[1], wh[0], wh[1]]
    size = item.get("size")
    return {"box": box, "size": size if _is_num(size) and 0 < size <= 1 else 0.4}


def _check_not_options_only(panel, previous, where):
    """A panel made only of options (``- {inset: {...}}`` after the image it
    should decorate) is refused with the panel written the right way:
    Qwen3.5 9B kept the separate panel for a dozen builds against the bare
    'needs exactly one of' message."""
    if not isinstance(panel, dict) or not panel or any(k in panel for k in _PANEL_KINDS):
        return
    if not set(panel) <= _KIND_KEYS["image"]:
        return
    opts = dict(panel)
    zoom = _inset_as_zoom(opts.get("inset"))
    if zoom:
        opts.pop("inset")
        opts["zoom"] = zoom
    if isinstance(previous, str):
        previous = {"image": previous}
    if isinstance(previous, dict) and any(k in previous for k in ("image", "glob")):
        fixed = json.dumps({**previous, **opts}, ensure_ascii=False)
        msg = (f"{where} is only options ({', '.join(sorted(panel))}), not a panel: they belong "
               f"INSIDE the image panel they decorate, the one before — write that panel as "
               f"{fixed} and remove this one")
    else:
        msg = (f"{where} is only options ({', '.join(sorted(panel))}), not a panel: put them "
               f"inside an image panel, e.g. {json.dumps({'image': 'file.tif', **opts}, ensure_ascii=False)}")
    if zoom:
        msg += (" (inset: places ANOTHER image in a corner and needs image:; to magnify a region "
                "of this image use zoom: {box: [x, y, width, height], size: 0.4})")
    raise RecipeError(msg)


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


def _check_crop(crop, where, source=None):
    # the error shows what was given and the right form: language models kept
    # resending the same list after a bare "must be a mapping"
    if not isinstance(crop, dict) or set(crop) - _CROP_KEYS:
        raise RecipeError(f"{where}: crop must be a mapping of pixels to remove per side, "
                          f"keys {sorted(_CROP_KEYS)} — e.g. crop: {{bottom: 24}} — got {crop!r}")
    for k, v in crop.items():
        if not _is_int(v) or v < 0:
            raise RecipeError(f"{where}: crop.{k} must be a non-negative integer (pixels), got {v!r}")
    if source:
        # before anything is built (the build used to stop half way at this panel)
        from pyfigures.mcp_tools.core import _raw_size_from_file
        size = _raw_size_from_file(source)
        if size:
            w, h = size
            lr = crop.get("left", 0) + crop.get("right", 0)
            tb = crop.get("top", 0) + crop.get("bottom", 0)
            if lr >= w or tb >= h:
                raise RecipeError(
                    f"{where}: crop {crop!r} removes the whole image ({os.path.basename(source)} is "
                    f"{w} x {h} px; left + right = {lr}, top + bottom = {tb}). Crop values are "
                    f"pixels removed from each side, not coordinates. To show a small region "
                    f"magnified, keep the image and add zoom: {{box: [x, y, width, height]}}.")


def _check_scale_bar(sb, where):
    if not isinstance(sb, dict) or "units" not in sb or set(sb) - _SCALE_BAR_KEYS:
        raise RecipeError(f"{where}: scale_bar must be a mapping with 'units' "
                          f"(allowed keys: {sorted(_SCALE_BAR_KEYS)}) — e.g. "
                          f"scale_bar: {{units: 10, unit: µm}} — got {sb!r}")


def _normalise_panel_opts(opts, where):
    """Accept two natural ways of writing a panel (a local model rewrote the
    recipe dozens of times against these refusals):

    - the pixel size inside the scale bar, ``scale_bar: {units: 10,
      px_to_unit: 0.1}`` = ``px_to_unit: 0.1`` beside it;
    - ``inset_fraction`` (the MCP tool's name) for a zoom's ``size``, which
      must be a fraction of the panel width."""
    sb = opts.get("scale_bar")
    if isinstance(sb, dict) and "px_to_unit" in sb:
        sb = dict(sb)                      # may be shared with 'defaults'
        px = sb.pop("px_to_unit")
        if "px_to_unit" in opts and opts["px_to_unit"] != px:
            raise RecipeError(f"{where}: two pixel sizes, px_to_unit: {opts['px_to_unit']!r} "
                              f"and scale_bar px_to_unit: {px!r}")
        opts["px_to_unit"] = px
        opts["scale_bar"] = sb
    if "inset" in opts:
        insets = []
        for k, item in enumerate(_as_list(opts["inset"])):
            if isinstance(item, dict):
                item = _renamed(item, _INSET_ALIASES)
                zoom = _inset_as_zoom(item)
                if zoom:
                    raise RecipeError(
                        f"{where}: inset {k + 1} has no image: — inset: places ANOTHER image file "
                        f"in a corner ({{image: other.tif, size: 0.3}}); to magnify a region of "
                        f"this image write zoom: {json.dumps(zoom)} (box = x, y, width, height "
                        f"in pixels; size = inset width as a fraction of the panel)")
                if "size" in item and not (_is_num(item["size"]) and 0 < item["size"] <= 1):
                    raise RecipeError(f"{where}: inset {k + 1} size is its width as a fraction of "
                                      f"the panel width (0 < size <= 1, e.g. size: 0.3), got "
                                      f"{item['size']!r}{_percent_hint(item['size'])}")
            insets.append(item)
        opts["inset"] = insets if isinstance(opts["inset"], list) else insets[0]
    if "zoom" in opts:
        zooms = []
        for k, z in enumerate(_as_list(opts["zoom"])):
            if isinstance(z, dict):
                z = _renamed(z, _ZOOM_ALIASES)
                guess = None if "box" in z else _inset_as_zoom(z)
                if guess:
                    # [x, y] could be the corner or the centre: not guessed silently
                    raise RecipeError(
                        f"{where}: zoom {k + 1} needs box: [x, y, width, height] (pixels, x/y = "
                        f"top-left corner) and size (inset width as a fraction of the panel) — "
                        f"e.g. zoom: {json.dumps(guess)}")
            if isinstance(z, dict) and "size" in z and not (_is_num(z["size"]) and 0 < z["size"] <= 1):
                raise RecipeError(f"{where}: zoom {k + 1} size is the inset width as a fraction "
                                  f"of the panel width (0 < size <= 1, e.g. size: 0.4), got {z['size']!r}"
                                  f"{_percent_hint(z['size'])}")
            zooms.append(z)
        opts["zoom"] = zooms if isinstance(opts["zoom"], list) else zooms[0]


def _check_mapping(value, allowed, required, where, name):
    if not isinstance(value, dict) or set(value) - allowed or not set(required) <= set(value):
        problem = ""
        if isinstance(value, dict):
            extra = sorted(set(value) - allowed)
            missing = sorted(set(required) - set(value))
            problem = ((f"; unknown {extra}" if extra else "")
                       + (f"; missing {missing}" if missing else ""))
        raise RecipeError(f"{where}: {name} must be a mapping with "
                          + (f"{sorted(required)} and " if required else "")
                          + f"optional keys {sorted(set(allowed) - set(required))} — got {value!r}"
                          + problem)


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
                if "image" in item and not source_exists(_resolve(base, item["image"])):
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
    from pyfigures.path_resolution import is_remote
    if is_remote(p):
        return str(p).strip()          # a URL (e.g. OME-Zarr on a server) is used as is
    p = os.path.expanduser(str(p))
    return os.path.normpath(p if os.path.isabs(p) else os.path.join(base_dir, p))


_FILE_LIKE = re.compile(r"\.[A-Za-z0-9]{2,5}$")


def _layout_rows(recipe, base=None):
    """A layout formula (pyfigures/layout_formula.py) as (tree, ids, rows):
    one single-panel row per panel id, in reading order; the build then
    arranges these rows into the formula's nested groups. An id that is not
    in panels: is a file name, or the name of exactly ONE file in the recipe's
    folder (a → a.png); several candidates are an error, never a guess."""
    from pyfigures import layout_formula as LF
    if "rows" in recipe:
        raise RecipeError("a recipe needs either 'layout' (with 'panels' as a mapping id: panel) "
                          "or 'rows', not both")
    if "columns" in recipe:
        raise RecipeError("'columns' does not apply to a layout formula")
    if not isinstance(recipe["layout"], str):
        raise RecipeError("'layout' must be a formula text such as \"(a,b,c)/(d,e,f)\" or a "
                          "picture (one line per row of cells)")
    from pyfigures import layout_picture as LP
    try:
        tree = (LP.parse(recipe["layout"]) if LP.is_picture(recipe["layout"])
                else LF.parse(recipe["layout"]))
    except LF.FormulaError as e:
        raise RecipeError(f"layout: {e}") from None
    panels = recipe.get("panels") or {}
    if not isinstance(panels, dict):
        raise RecipeError("with 'layout', 'panels' must be a mapping of panel id to panel "
                          "(e.g. panels: {a: {image: wt.tif, crop: {bottom: 20}}, b: ko.tif}), "
                          "not a list")
    ids = LF.panel_ids(tree)
    seen = set()
    for pid in ids:
        if pid in seen:
            raise RecipeError(f"layout: panel {pid!r} is placed twice — to show the same image "
                              "twice, define two ids with the same source in panels:")
        seen.add(pid)
    unused = [str(k) for k in panels if str(k) not in seen]
    if unused:
        raise RecipeError(f"panels {unused} are not in the layout {recipe['layout']!r} "
                          "(a typo? every panel id must appear in the formula once)")
    rows = []
    for pid in ids:
        if pid in panels:
            rows.append(({}, [panels[pid]]))
        elif _FILE_LIKE.search(pid):
            rows.append(({}, [pid]))                 # a file name used directly
        else:
            cands = []
            if base and os.path.isdir(base):
                cands = sorted(n for n in os.listdir(base)
                               if os.path.splitext(n)[0].lower() == pid.lower()
                               and os.path.isfile(os.path.join(base, n))
                               and not n.lower().endswith((".yaml", ".yml", ".json", ".pyf")))
            if len(cands) == 1:
                rows.append(({}, [cands[0]]))
                continue
            if len(cands) > 1:
                raise RecipeError(f"layout: panel {pid!r} matches several files {cands}: write "
                                  f"the file name in the formula, or define {pid} in panels:")
            raise RecipeError(f"layout: panel {pid!r} is not defined in panels: and no file "
                              f"called {pid}.* is next to the recipe — add it, e.g. "
                              f"panels: {{{pid}: {{image: file.tif}}}}")
    return tree, ids, rows


def _rows_of(recipe):
    """The rows as [(row_options, [panel, ...]), ...]."""
    if "layout" in recipe:
        return _layout_rows(recipe)[2]
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
    if "orientation" in opts:
        from pyfigures.mcp_tools.core import _orientation
        if _orientation(opts["orientation"]) is None:
            raise RecipeError(f"{where}: orientation must be X (a row: side by side) or Y "
                              f"(a column: stacked), not {opts['orientation']!r}")
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
    if recipe.get("journal") is not None:
        # checked before anything is built (`journal: true` used to crash
        # half-way, after the figure was saved)
        from pyfigures.mcp_tools.core import _width_mm_for_journal
        column = recipe.get("column", "single")
        if isinstance(column, (int, float)) and not isinstance(column, bool):
            column = f"{column:g}"
        if not isinstance(recipe["journal"], str) or not isinstance(column, str):
            raise RecipeError("'journal' must be a journal name (e.g. nature) and 'column' "
                              "single, 1.5, double or triple (the sizes that journal gives; "
                              "'half page' = an estimate for a journal giving only a full width)")
        try:
            _width_mm_for_journal(recipe["journal"], column)
        except ValueError as e:
            raise RecipeError(str(e)) from None
    widths = [k for k in ("width_mm", "width_cm", "width_in", "width_px") if k in recipe]
    if len(widths) > 1:
        raise RecipeError(f"give one figure width, not {widths}")
    if widths and recipe.get("journal"):
        raise RecipeError("give either 'journal' or an explicit width, not both")
    for k in widths:
        v = recipe[k]
        if not _is_num(v) or v <= 0 or (k == "width_px" and not _is_int(v)):
            raise RecipeError(f"'{k}' must be a positive number")
    if "colors" in recipe:
        from pyfigures.mcp_tools.stacks import _COLOR_LUTS
        c = recipe["colors"]
        cb = isinstance(c, list) and [str(x).lower().replace("-", "").replace("colour", "color")
                                      for x in c] == ["colorblind"]
        if not cb and (not isinstance(c, list) or not c
                       or any(str(x).lower() not in _COLOR_LUTS for x in c)):
            raise RecipeError(f"'colors' recolours the whole figure: a list of colour names in "
                              f"channel order, from {sorted(_COLOR_LUTS)} — e.g. "
                              f"colors: [magenta, green] — or colors: [colorblind]; got {c!r}")
    if "fit_height" in recipe and recipe["fit_height"] not in (True, False, "shrink", "column",
                                                               "off"):
        raise RecipeError("'fit_height' (a figure taller than the journal's maximum height) "
                          "must be shrink (narrow it until it fits, the default), column (the "
                          "widest journal column it fits in) or off (keep the width)")
    if "max_height_mm" in recipe and (not _is_num(recipe["max_height_mm"])
                                      or recipe["max_height_mm"] <= 0):
        raise RecipeError("'max_height_mm' must be a positive number of millimetres")
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
    if "download_remote" in recipe:
        if not isinstance(recipe["download_remote"], bool):
            raise RecipeError("'download_remote' must be true or false")
        if not recipe.get("consolidate"):
            raise RecipeError("'download_remote' applies to 'consolidate': add consolidate: true")
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
        # a panel key at the top (a local model repeated 'scale_bar:' there 46
        # times): say where it goes rather than only listing what is allowed
        panel_keys = sorted(k for k in unknown if k in _DEFAULT_KEYS)
        hint = ""
        if panel_keys:
            k = panel_keys[0]
            example = json.dumps(recipe[k], ensure_ascii=False, default=str)
            hint = (f" — {panel_keys} {'is a panel key' if len(panel_keys) == 1 else 'are panel keys'}: "
                    f"for every panel put it under 'defaults' (defaults: {{{k}: {example}}}), "
                    f"or on the panels that need it")
        elif any("letter" in str(k) for k in unknown):
            hint = " — panel letters: letter_panels: true (placement: letter_placement)"
        raise RecipeError(f"unknown top-level key(s): {sorted(unknown)}{hint} "
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
        hint = ""
        if any("letter" in str(k) for k in bad):
            hint = " — panel letters are a top-level key: letter_panels: true"
        elif bad & _TOP_KEYS:
            hint = f" — {sorted(bad & _TOP_KEYS)} go at the top of the recipe, not in defaults"
        raise RecipeError(f"unknown key(s) in defaults: {sorted(bad)} "
                          f"(allowed: {sorted(_DEFAULT_KEYS)}){hint}")

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
            if not source_exists(p):
                raise RecipeError(f"fill {k + 1}: file not found: {p}")
            fill.append(p)

    layout_tree, layout_ids, rows_src = None, None, []
    if "layout" in recipe and "template" not in recipe:
        layout_tree, layout_ids, rows_src = _layout_rows(recipe, base)
    elif "template" not in recipe:
        rows_src = _rows_of(recipe)
    plan_rows = []
    for r, (row_opts, row) in enumerate(rows_src):
        _check_row_opts(row_opts, len(row), f"row {r + 1}")
        plan_row = []
        for c, panel in enumerate(row):
            where = (f"layout panel {layout_ids[r]!r}" if layout_ids
                     else f"row {r + 1}, panel {c + 1}")
            if isinstance(panel, str):
                panel = {"image": panel}          # `- [wt.tif, ko.tif]` shorthand
            _check_not_options_only(panel, row[c - 1] if c else None, where)
            kind = _panel_kind(panel, where)
            merged = {k: v for k, v in defaults.items() if k in _KIND_KEYS[kind]}
            merged.update({k: v for k, v in panel.items() if k != kind})
            _normalise_panel_opts(merged, where)
            if "crop" in merged:
                src = panel.get(kind) if kind in ("image", "split", "montage") else None
                _check_crop(merged["crop"], where,
                            _resolve(base, src) if isinstance(src, str) else None)
            if merged.get("scale_bar_panels", "last") not in ("last", "all"):
                raise RecipeError(f"{where}: scale_bar_panels must be 'last' or 'all', "
                                  f"got {merged['scale_bar_panels']!r}")
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
            if kind == "tex":
                if not isinstance(panel["tex"], str) or not panel["tex"].strip():
                    raise RecipeError(f"{where}: tex must be LaTeX code (text)")
                plan_row.append((kind, panel["tex"], merged))
                continue
            if kind == "equation":
                from pyfigures import equations as _eq
                eq = str(panel["equation"])
                engine = merged.get("engine", "mathtext")
                if engine not in _eq.ENGINES:
                    raise RecipeError(f"{where}: engine must be one of {', '.join(_eq.ENGINES)}")
                if engine == "latex" and not _eq.latex_available():
                    from batoolset.tex_install import INSTALL_HINT
                    raise RecipeError(f"{where}: engine: latex needs a LaTeX installation (latex and "
                                      f"dvisvgm from TeX Live, MiKTeX or MacTeX). {INSTALL_HINT}")
                if eq.strip().lower().endswith(".tex"):
                    eq = _resolve(base, eq.strip())
                    if not os.path.isfile(eq):
                        raise RecipeError(f"{where}: .tex file not found: {eq}")
                elif engine == "mathtext":
                    try:
                        _eq.check(eq, merged.get("fontset", "cm"))
                    except ValueError as e:
                        raise RecipeError(f"{where}: {e}") from None
                plan_row.append((kind, eq, merged))
                continue
            if kind in ("split", "merge") and isinstance(panel[kind], list):
                files = [_resolve(base, f) for f in panel[kind]]
                missing = [f for f in files if not source_exists(f)]
                if missing:
                    raise RecipeError(f"{where}: file(s) not found: {', '.join(missing)}")
                if kind == "merge" and len(files) < 2:
                    raise RecipeError(f"{where}: a merge needs at least two channel files")
                plan_row.append((kind, files, merged))
                continue
            if kind == "merge":
                raise RecipeError(
                    f"{where}: merge must be a list of single-channel files, e.g. merge: "
                    "[dapi.tif, gfp.tif]; for each channel of ONE multi-channel file (an RGB "
                    "image, a stack) plus their merge, use {split: file.tif, names: [...], "
                    "merge: true} — a split already adds its merge panel")
            if kind == "glob":
                matches = sorted(_glob.glob(_resolve(base, panel["glob"])))
                matches = [m for m in matches if os.path.isfile(m)]
                if not matches:
                    raise RecipeError(f"{where}: glob {panel['glob']!r} matched no files")
                for m in matches:
                    plan_row.append(("image", m, dict(merged)))
                continue
            path = _resolve(base, panel[kind])
            if not source_exists(path):
                raise RecipeError(f"{where}: file not found: {path}")
            if kind in ("image", "split", "montage") and \
                    os.path.splitext(str(path))[1].lower() in (".csv", ".tsv", ".xlsx", ".xls"):
                # a table read as an image became a black panel (Qwen3 30B)
                raise RecipeError(f"{where}: {os.path.basename(str(path))} is a data table, not "
                                  f"an image — plot it with {{plot: {panel[kind]}, kind: box}} "
                                  "(kind: bar, box, violin, scatter or grouped)")
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
        "layout": layout_tree,
        "layout_ids": layout_ids,
        "journal": recipe.get("journal"),
        # YAML reads `column: 1.5` / `2` as numbers
        "column": (f"{recipe['column']:g}" if isinstance(recipe.get("column"), (int, float))
                   else recipe.get("column", "single")),
        "width": {k: recipe[k] for k in ("width_mm", "width_cm", "width_in", "width_px")
                  if k in recipe},
        "dpi": recipe.get("dpi", 300),
        "fit_height": recipe.get("fit_height", True),
        "max_height_mm": recipe.get("max_height_mm"),
        "letter_panels": letter_panels,
        "letter_placement": recipe.get("letter_placement", "top left"),
        "caption": recipe.get("caption"),
        "title": recipe.get("title", "Figure"),
        "spacing": spacing,
        "label_background": recipe.get("label_background"),
        "background": recipe.get("background"),
        "font": font,
        "min_font_pt": recipe.get("min_font_pt"),
        "colors": recipe.get("colors"),
        "tidy_text": tidy,
        "auto_configure": recipe.get("auto_configure", False),
        "alt_text": recipe.get("alt_text"),
        "copy_style_from": (_resolve(base, recipe["copy_style_from"])
                            if "copy_style_from" in recipe else None),
        "copy_style_aspects": recipe.get("copy_style_aspects"),
        "exports": recipe.get("exports") or [],
        "checks": recipe.get("checks") or [],
        "consolidate": recipe.get("consolidate", False),
        "download_remote": recipe.get("download_remote", False),
        "template": _resolve(base, recipe["template"]) if "template" in recipe else None,
        "fill": fill,
    }


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def _strip_error(text: str) -> str:
    """'ERROR: ERROR: x' -> 'x' (the caller adds its own single prefix)."""
    text = text.strip()
    while text.upper().startswith("ERROR"):
        text = text[5:].lstrip(" :")
    return text


def _check(result, step):
    """Fail loudly on an ERROR from a tool; return any WARNING lines."""
    if isinstance(result, str) and result.startswith("ERROR"):
        raise RecipeError(f"{step}: {_strip_error(result)}")
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


def _page_label_html(label: str, plan: dict) -> str:
    """Side labels and label rows sit on the page, not on an image: dark text
    (white vanished on a white page), white on a dark page or label box."""
    if _HTML_TAG.search(label):
        return label
    behind = plan.get("label_background")
    if behind is None:
        behind = plan.get("background")
    dark = False
    if behind is not None and str(behind).lower() not in ("none", "transparent"):
        from pyfigures.mcp_tools.core import _color_to_int
        try:
            c = _color_to_int(behind)
            dark = (0.299 * (c >> 16 & 255) + 0.587 * (c >> 8 & 255) + 0.114 * (c & 255)) < 128
        except ValueError:
            pass
    if dark:
        return f"<font color=#ffffff>{html.escape(label, quote=False)}</font>"
    return html.escape(label, quote=False)


def _series_panels(pyf, group_path):
    """[(group_path, image_index)] of every panel of the montage / split group
    at *group_path*, nested row groups included."""
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _navigate_group
    grp, err = _navigate_group(ET.parse(pyf).getroot(), group_path)
    if err:
        raise RecipeError(err)
    found = []

    def walk(g, path):
        content = g.find("content")
        if content is None:
            return
        n_img = n_grp = 0
        for child in content:
            if child.tag == "Image2D":
                if child.findtext("isText", "False") != "True":
                    found.append((list(path), n_img))
                n_img += 1
            elif child.tag == "Group":
                walk(child, path + [n_grp])
                n_grp += 1

    walk(grp, list(group_path))
    return found


def _last_series_panel(pyf, group_path):
    """(group_path, image_index) of the last panel of the montage / split
    group at *group_path* (a multi-row montage nests one group per row)."""
    import xml.etree.ElementTree as ET
    from pyfigures.mcp_tools.core import _navigate_group
    grp, err = _navigate_group(ET.parse(pyf).getroot(), group_path)
    if err:
        raise RecipeError(err)
    from pyfigures.mcp_tools.core import _is_empty_placeholder
    path = list(group_path)
    while True:
        content = list(grp.find("content"))
        imgs = [c for c in content if c.tag == "Image2D"]
        # the last frame, not the empty panel padding a montage's last row
        real = [i for i, c in enumerate(imgs) if not _is_empty_placeholder(c)]
        if real:
            return path, real[-1]
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
    elif kind == "vectorcraft":
        res = M.export_vectorcraft(out, target)
    elif kind == "deckcraft":
        res = M.export_deckcraft(out, target)
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
        raise RecipeError(f"{step}: {_strip_error(result)}")
    return result


def _fill_template(M, out, template, files):
    """Copy *template* to *out* and put *files* in its slots, in order;
    returns (n_filled, warnings)."""
    import shutil
    shutil.copyfile(template, out)
    # drop the sidecars of a previous build (as create_figure does)
    for ext in (".caption.json", ".stats.json", ".alttext.json", ".sources.json", ".target.json"):
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


def _crop_to_aspect(img, target, name):
    """Centre-crop an Image2D element (on top of its own crop) to the aspect
    ratio *target* (width / height). Returns a warning, or ''."""
    from pyfigures.mcp_tools.core import _child_text, _decode, _raw_size_from_file, _set_child_text
    fn = _decode(_child_text(img, "filename"))
    size = _raw_size_from_file(fn) if isinstance(fn, str) else None
    if not size:
        return f"grid: panel {name!r} kept its own size (no image size to crop)"
    crop = {k: int(float(_child_text(img, f"crop_{k}") or 0))
            for k in ("left", "right", "top", "bottom")}
    w = size[0] - crop["left"] - crop["right"]
    h = size[1] - crop["top"] - crop["bottom"]
    if w <= 0 or h <= 0 or abs(w / h - target) / target < 0.005:
        return ""
    if w / h > target:
        extra = int(round(w - h * target))
        crop["left"] += extra // 2
        crop["right"] += extra - extra // 2
        side = f"{extra} px left/right"
    else:
        extra = int(round(h - w / target))
        crop["top"] += extra // 2
        crop["bottom"] += extra - extra // 2
        side = f"{extra} px top/bottom"
    for k, v in crop.items():
        _set_child_text(img, f"crop_{k}", str(v))
    kept = (size[0] - crop["left"] - crop["right"]) * (size[1] - crop["top"] - crop["bottom"])
    pct = 100 * kept / (size[0] * size[1])
    msg = (f"grid: panel {name!r} centre-cropped by {side} to the grid's {target:.2f} aspect "
           f"ratio ({pct:.0f}% of the image shown)")
    if pct < 50:
        # a picture route kept 17-25% of an overview (ChatGPT audit, 19 Oct)
        msg += (" — most of the image is cut away: if the whole field matters, give the panel "
                "a cell span closer to the image's shape, or use a formula ( , / ) which keeps "
                "whole images")
    return msg


def _arrange_layout(out, plan):
    """Move the one-panel rows built for a layout formula into the formula's
    nested groups (rows = X, stacks = Y; a grid = a stack of rows whose cells
    are cropped to one aspect ratio). Panels move with everything on them."""
    from collections import Counter
    from pyfigures.mcp_tools.core import (_child_text, _decode, _load, _new_group_elem,
                                          _next_group_id, _raw_size_from_file, _save)
    tree, root = _load(out)
    tops = root.findall("Group")
    ids = plan["layout_ids"]
    if len(tops) != len(ids):
        return [f"layout: expected {len(ids)} built panels, found {len(tops)} rows; "
                "the panels were left as rows"]
    leaf = {}
    for pid, g in zip(ids, tops):
        kids = list(g.find("content"))
        leaf[pid] = kids[0] if len(kids) == 1 else g      # a split / montage / glob keeps its group
    space = plan["spacing"]
    next_id = [_next_group_id(root)]
    warnings = []

    def group(orientation, children):
        el = _new_group_elem(orientation, space=space, group_id=next_id[0])
        next_id[0] += 1
        for c in children:
            el.find("content").append(c)
        return el

    def aspect(el):
        if el.tag != "Image2D":
            return None
        fn = _decode(_child_text(el, "filename"))
        size = _raw_size_from_file(fn) if isinstance(fn, str) else None
        if not size:
            return None
        w = size[0] - sum(int(float(_child_text(el, f"crop_{k}") or 0)) for k in ("left", "right"))
        h = size[1] - sum(int(float(_child_text(el, f"crop_{k}") or 0)) for k in ("top", "bottom"))
        return w / h if w > 0 and h > 0 else None

    def build(node):
        t = node["type"]
        if t == "panel":
            return leaf[node["id"]]
        if t in ("row", "col"):
            return group("X" if t == "row" else "Y", [build(k) for k in node["children"]])
        from pyfigures.layout_formula import grid_cells
        cells = grid_cells(node)
        ratios = [a for a in (aspect(leaf[p]) for r in cells for p in r) if a]
        if ratios:
            target = Counter(round(a, 2) for a in ratios).most_common(1)[0][0]
            for r in cells:
                for p in r:
                    if leaf[p].tag == "Image2D":
                        w = _crop_to_aspect(leaf[p], target, p)
                    else:
                        w = f"grid: panel {p!r} is not a single image: kept its own size"
                    if w:
                        warnings.append(w)
        rows = [group("X", [leaf[p] for p in r]) for r in cells]
        return rows[0] if len(rows) == 1 else group("Y", rows)

    def as_top(el):
        return el if el.tag == "Group" else group("X", [el])

    t = plan["layout"]
    # a picture layout: every image is cropped to the shape of the cells it
    # spans (cell ratio = the most common one), so rows and columns line up
    spans = {}

    def collect(node):
        if node["type"] == "panel":
            if "cells" in node:
                spans[node["id"]] = node["cells"]
        else:
            for k in node["children"]:
                collect(k)
    collect(t)
    if spans:
        per_cell = [(aspect(leaf[p]), cw / ch) for p, (cw, ch) in spans.items()]
        ones = [a for (a, s), (cw, ch) in zip(per_cell, spans.values()) if a and cw == ch == 1]
        pool = ones or [a / s for a, s in per_cell if a]
        if pool:
            cell = Counter(round(a, 2) for a in pool).most_common(1)[0][0]
            for p, (cw, ch) in spans.items():
                if leaf[p].tag == "Image2D":
                    w = _crop_to_aspect(leaf[p], cell * cw / ch, p)
                else:
                    w = f"layout: panel {p!r} is not a single image: kept its own size"
                if w:
                    warnings.append(w.replace("grid's", "cells'"))
    if t["type"] == "col":
        new_tops = [as_top(build(k)) for k in t["children"]]
    elif t["type"] == "grid":
        g = build(t)
        new_tops = list(g.find("content")) if _decode(_child_text(g, "orientation")) == "Y" else [g]
    else:
        new_tops = [as_top(build(t))]
    children = list(root)
    at = children.index(tops[0])
    for g in tops:
        root.remove(g)
    for k, g in enumerate(new_tops):
        root.insert(at + k, g)
    _save(tree, out, recompute=True)
    return warnings


def _zoom_list(plan):
    """Every zoom inset with its current size: "make the insets larger" needs
    it (Gemma 12B rebuilt the zoom without a size and the inset stayed the
    same)."""
    zooms = []
    for _row_opts, row in plan["rows"]:
        for kind, path, opts in row:
            for z in _as_list(opts.get("zoom") or []):
                if isinstance(z, dict) and "box" in z:
                    zooms.append({"panel": os.path.basename(str(path)), "box": z["box"],
                                  "size": z.get("size", 0.4)})
    return zooms


def _calibration_warnings(plan) -> list:
    """Where a scale bar's pixel size comes from: models copied the example
    0.1 µm/pixel into figures given no calibration (Qwen3 30B, despite the
    documentation). A px_to_unit the image file does not carry is flagged as
    user-supplied-only; one that contradicts the file's own is flagged too.
    Nothing is blocked: a calibration the user gave is legitimate."""
    from pyfigures.mcp_tools.workflow import _try_read_image_info
    missing, clash = {}, []
    for _row_opts, row in plan["rows"]:
        for kind, path, opts in row:
            px = opts.get("px_to_unit")
            if not opts.get("scale_bar") or not px or not isinstance(path, str):
                continue
            try:
                own = _try_read_image_info(path).get("px_to_unit")
            except Exception:
                own = None
            name = os.path.basename(path)
            if own is None:
                missing.setdefault(px, []).append(name)
            elif abs(float(own) - float(px)) > 0.01 * float(own):
                clash.append(f"{name}: the file says {own:.4g} per pixel, the recipe {px}")
    out = [f"scale bars use px_to_unit {px} from the recipe for {', '.join(sorted(set(names)))}: "
           f"the image file(s) carry no pixel size — keep it only if the user gave this "
           f"calibration (example values such as 0.1 are not real calibrations)"
           for px, names in missing.items()]
    if clash:
        out.append("pixel size differs from the image metadata — " + "; ".join(clash))
    return out


def _burned_text_warnings(plan) -> list:
    """Text burned into a source image near its edge (Fiji's sample-image
    notice stayed in a model-built figure, overlapping the scale bar): the
    crop that removes it, as a suggestion only (pyfigures/burned_text.py)."""
    from pyfigures.burned_text import burned_text_warning
    out = []
    seen = set()
    for _row_opts, row in plan["rows"]:
        for kind, path, opts in row:
            if kind not in ("image", "split", "montage") or not isinstance(path, str):
                continue
            key = (path, json.dumps(opts.get("crop") or {}, sort_keys=True))
            if key in seen:
                continue
            seen.add(key)
            w = burned_text_warning(path, opts.get("crop"))
            if w:
                out.append(w)
    return out


def recipe_zooms(recipe_path: str) -> list:
    """_zoom_list of a recipe file, [] when it is missing or invalid."""
    try:
        return _zoom_list(_plan(load_recipe(recipe_path), recipe_path))
    except Exception:
        return []


def zoom_size_changes(old: list, new: list) -> list:
    """Warnings for zoom insets whose size changed between two versions of a
    recipe (recipe_zooms) while their box stayed the same: a rebuild for
    another edit (colours) silently shrank an enlarged inset (Qwen3 30B,
    0.6 -> 0.4)."""
    out = []
    for z in new:
        for o in old:
            if o["panel"] == z["panel"] and list(o["box"]) == list(z["box"]) \
                    and o["size"] != z["size"]:
                # the direction in words: Qwen3 30B called 0.8 -> 0.6 "enlarged"
                way = "SMALLER" if float(z["size"]) < float(o["size"]) else "LARGER"
                out.append(f"zoom inset on {z['panel']} (box {list(z['box'])}) is now {way}: "
                           f"size {o['size']} -> {z['size']} from the previous recipe; if this "
                           f"edit was about something else, put size: {o['size']} back"
                           + (" (to enlarge it, size must go ABOVE "
                              f"{o['size']}, at most 1)" if way == "SMALLER" else ""))
    return out


def build_figure_from_recipe(recipe_path: str) -> dict:
    """Build the figure described by *recipe_path*; returns a summary dict.
    Raises RecipeError on any invalid input or failed step. A build that fails
    half-way leaves the output as it was (absent, or the previous figure);
    only a failed ``checks`` entry keeps the new figure, as documented."""
    from pyfigures import history
    plan = _plan(load_recipe(recipe_path), recipe_path)
    before = history.capture(plan["output"])
    try:
        return _build_plan(plan, recipe_path)
    except RecipeChecksFailed:
        raise
    except BaseException:
        history.restore(before)
        raise


def _build_plan(plan: dict, recipe_path: str) -> dict:
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.workflow import _finalize_draft, _caption_stub
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

    def series_finish(group_path, opts, step, default="last"):
        """Scale bar of a montage / split group: one bar, on the last panel (a
        split's merge: the panels share one scale, the author's choice);
        scale_bar_panels: all puts one on every panel."""
        w = []
        if opts.get("scale_bar"):
            if opts.get("scale_bar_panels", default) == "all":
                targets = _series_panels(out, group_path)
            else:
                targets = [_last_series_panel(out, group_path)]
            for sp, si in targets:
                w += scale_bar(sp, si, opts["scale_bar"], opts.get("px_to_unit"), step)
        return w

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
        from pyfigures.mcp_tools.core import _orientation
        orientation = _orientation(row_opts.get("orientation", "X"))
        row_spacing = row_opts.get("spacing", plan["spacing"])
        warnings += _check(M.add_group(out, orientation=orientation, spacing=row_spacing),
                           f"row {r + 1}")
        gp = [r]
        i = -1                      # index of the row's last Image2D panel
        n_sub = 0                   # montage / split groups nested in this row
        for c, (kind, path, opts) in enumerate(row):
            if isinstance(path, str) and kind not in ("script", "colorbar", "equation", "tex"):
                name = os.path.basename(path)
            elif isinstance(path, list):
                name = f"{len(path)} channel files"
            else:
                name = kind
            step = f"row {r + 1}, panel {c + 1} ({name})"
            if kind == "plot":
                kw = {k: opts[k] for k in ("kind", "error", "ylabel", "xlabel", "title",
                                           "stats_mode", "annotate_stats",
                                           "only_significant", "label", "latex", "colors")
                      if k in opts}
                warnings += _check(M.add_data_plot(out, gp, path, **kw), step)
                n_plots += 1
                i += 1
                continue
            if kind == "montage":
                kw = {k: opts[k] for k in _MONTAGE_KEYS | {"crop"} if k in opts}
                warnings += _check(M.add_stack_montage(out, path, parent_group_path=gp,
                                                       spacing=row_spacing, **kw), step)
                warnings += series_finish(gp + [n_sub], opts, step)
                n_sub += 1
                n_series += 1
                continue
            if kind == "split":
                kw = {k: opts[k] for k in ("names", "colors", "gray", "merge_label",
                                           "projection", "frame", "series",
                                           "label_placement", "crop") if k in opts}
                if "merge" in opts:
                    kw["include_merge"] = bool(opts["merge"])
                src = {"channel_files": path} if isinstance(path, list) else {"stack_path": path}
                warnings += _check(M.add_channel_split(out, parent_group_path=gp,
                                                       spacing=row_spacing, **src, **kw), step)
                warnings += series_finish(gp + [n_sub], opts, step)
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
                if opts.get("crop"):
                    tf = {f"crop_{k}": v for k, v in opts["crop"].items()}
                    warnings += _check(M.transform_image(out, gp, i, **tf), step + " crop")
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
            if kind == "tex":
                label = _label_html(str(opts["label"])) if opts.get("label") else ""
                warnings += _check(M.add_latex_code(out, gp, path, preamble=opts.get("preamble"),
                                                    label=label), step)
                i += 1
                n_other += 1
                continue
            if kind == "equation":
                kw = {k: opts[k] for k in ("font_size", "color", "fontset", "engine", "preamble", "font")
                      if k in opts}
                if opts.get("label"):
                    kw["label"] = _label_html(str(opts["label"]))
                warnings += _check(M.add_equation(out, gp, path, **kw), step)
                i += 1
                n_other += 1
                continue
            label = opts.get("label") or ""
            if label:
                label = _label_html(str(label))
            extra = {"page": int(opts["page"])} if opts.get("page") is not None else {}
            warnings += _check(M.add_image(out, gp, path, label=label, **extra), step)
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

    # a layout formula: every panel was built as its own row, with all its
    # settings; now arrange them into the formula's nested groups
    if plan.get("layout"):
        warnings += _arrange_layout(out, plan)

    lettered = 0
    if plan["letter_panels"]:
        lettered, _ = _finalize_draft(out, True, plan["letter_placement"], None, None, "")

    # side labels and label rows add panels / groups: last row first, so the
    # indices of the rows still to do never shift
    for r in reversed(range(len(plan["rows"]))):
        row_opts = plan["rows"][r][0]
        if row_opts.get("side_label"):
            warnings += _check(M.add_side_label(
                out, [r], _page_label_html(row_opts["side_label"], plan),
                position=row_opts.get("side_label_position", "left")), f"row {r + 1} side label")
        if "labels" in row_opts:
            labels = row_opts["labels"]
            labels = ([_page_label_html(x, plan) for x in labels] if isinstance(labels, list)
                      else _page_label_html(labels, plan))
            warnings += _check(M.add_label_row(
                out, [r], labels, position=row_opts.get("labels_position", "above"),
                text_orientation=row_opts.get("labels_orientation", "horizontal")),
                f"row {r + 1} labels")

    if plan["colors"]:
        # after every per-panel LUT: the whole figure in these colours
        warnings += _check(M.set_figure_colors(out, plan["colors"]), "colors")
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
    height = {"fit_height": plan["fit_height"], "max_height_mm": plan["max_height_mm"]}
    resized = None
    if plan["journal"]:
        resized = M.resize_figure(out, journal=plan["journal"], column=plan["column"],
                                  dpi=plan["dpi"], **height)
        warnings += _check(resized, "journal resize")
    elif plan["width"]:
        resized = M.resize_figure(out, dpi=plan["dpi"], **plan["width"], **height)
        warnings += _check(resized, "resize")
    fit = re.search(r"At [\d.]+mm wide the figure is .*?Choices: .*?\.(?=  |$)", resized or "")
    if fit:
        warnings.append(fit.group(0))            # too tall for the page: what was done + choices
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
        r = json.loads(_ok(M.consolidate_figure(out, dest, download_remote=plan["download_remote"]),
                           "consolidate"))
        bundle = r["files_folder"]
        for miss in r.get("not_downloaded") or []:
            warnings.append(f"remote image kept as a link (download failed): {miss['url']} ({miss['error']})")

    n_rows = len(plan["rows"])
    zooms = _zoom_list(plan)
    warnings += _calibration_warnings(plan)
    warnings += _burned_text_warnings(plan)
    if any(isinstance(path, str) and path.lower().endswith(".pdf")
           for _ro, row in plan["rows"] for _k, path, _o in row):
        from pyfigures.extras import has_pymupdf, pdf_vector_note
        if not has_pymupdf():
            warnings.append(pdf_vector_note())
    import xml.etree.ElementTree as _ET
    from pyfigures.mcp_tools.core import layout_rows
    try:
        actual = layout_rows(_ET.parse(out).getroot())
    except Exception:
        actual = []
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
        "actual_layout": actual,
        "layout_note": "actual_layout is read from the SAVED figure (' | ' side by side, ' / ' "
                       "stacked, '[file xN]' a channel split or montage): check it matches "
                       "the requested arrangement — a successful build only means the recipe "
                       "ran",
        **({"zoom_insets": zooms,
            "zoom_note": "size = the inset's width as a fraction of its panel (0 < size <= 1); "
                         "to enlarge an inset raise its zoom's size (e.g. 0.4 -> 0.55), keep "
                         "the same box (the box is the region shown, not the inset)"}
           if zooms else {}),
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
