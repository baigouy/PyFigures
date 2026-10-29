"""PyFigures MCP tools — FastMCP server object and the tool decorator (reports warnings).

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

mcp = FastMCP(
    "pyfigures",
    instructions=(
        "Inspect, create, and edit PyFigures .pyf scientific-figure layout files. "
        "Tools for reading: describe_figure, get_xml, get_annotations, list_images. "
        "Tools for creating: create_figure, add_group, add_image. "
        "Tools for editing: set_spacing, set_orientation, reorder_children, resize_figure, "
        "set_annotation_text, add_annotation, add_corner_labels, remove_annotation, "
        "add_roi_rect, add_roi_ellipse, add_roi_line, add_roi_polygon, "
        "add_significance_bracket (stats bar + * / n.s. / p-value label over a plot), remove_group, "
        "remove_image, set_image_filename, fill_template, batch_fill_templates, "
        "clone_image, move_image, set_size, layout_canvas, remap_paths. "
        "Scale bar tools: get_scale_bar, set_scale_bar, remove_scale_bar, set_scale_bar_all. "
        "Inset / picture-in-picture tools: add_inset, add_zoom_callout (magnified-detail "
        "box + inset + leader lines), list_insets, remove_inset, set_inset_property. "
        "Row/column label tools: add_label_row, add_side_label, list_label_rows, remove_label_row. "
        "Figure-level settings: get_figure_properties, set_figure_properties; "
        "caption/legend: set_figure_caption, get_figure_caption, export_caption "
        "(stored in a .caption.json sidecar beside the .pyf, exportable for submission). "
        "Fonts: list_fonts(query=None) lists the installed font families (optionally "
        "filtered by name) and what Helvetica/Arial are really drawn in; a font that is "
        "not installed is drawn and exported as a substitute, which check_journal_compliance "
        "names (drop redistributable clones in pyfigures/gui/fonts for cross-machine "
        "reproducibility); set the figure font with set_figure_properties(font_family=...). "
        "LUTs: list_luts(query=None) lists the colour tables set_lut accepts (optionally "
        "filtered by name) and checks whether a name exists; null in set_lut keeps a "
        "channel's current LUT. "
        "Multi-channel microscopy: add_channel_merge overlays single-channel images "
        "into one pseudo-coloured composite (DAPI+GFP+RFP → merge). "
        "Image display tools: transform_image (rotation/crop/opacity/flip), "
        "set_lut (colour LUTs + normalization), "
        "configure_image (channels, Z-projection, serie_to_open, normalization). "
        "Tools for scripted images: add_scripted_image, get_script, set_script. "
        "Use add_scripted_image to add a matplotlib/numpy panel in one step — "
        "never call add_image + set_script separately for this purpose. "
        "Generic property access (covers ALL Image2D fields): "
        "list_image_properties, get_image_property, set_image_property. "
        "Layout recompute: recompute_layout (explicit trigger; all structural tools "
        "already call this automatically). "
        "Raw XML fallback: write_xml. "
        "Folder-to-figure workflow: scan_folder (list files + layout suggestions), "
        "create_figure_from_folder (one-shot create + populate from a folder), "
        "auto_configure_images (auto-set LUTs + scale bars from image metadata). "
        "Journal guidelines: paste a journal's figure requirements, extract the "
        "numbers, then use apply_journal_guidelines (one-shot resize + font + labels "
        "+ scale bars) or the individual checkers check_journal_compliance (read-only "
        "PASS/FAIL report), check_resolution (per-panel print DPI at the target "
        "width), and enforce_min_font_size (raise all fonts to the minimum); "
        "list_journal_presets enumerates the built-in journal column widths. "
        "A journal that is not built in: when the user pastes its guidelines page, call "
        "prepare_journal_style_import, answer with the JSON it asks for (every rule "
        "quoting the text), then save_journal_style; the saved style is then usable as "
        "journal=<use_as> everywhere (list_journal_styles, get_journal_style). "
        "Integrity: check_image_integrity screens panels for exact file reuse, "
        "cross-panel duplication (incl. flipped/rotated/inverted) and within-panel "
        "copy-move cloning before submission; export_adjustment_ledger produces a "
        "per-panel image-adjustment provenance record + a ready-to-paste Methods "
        "paragraph disclosing brightness/contrast/LUT/crop/rotation/scripts. "
        "Rendering: render_preview returns a PNG image of the figure so you can "
        "visually verify a layout you built/edited (catch overlaps, clipping, "
        "wrong LUT, missing panels); export_figure writes the final deliverable "
        "to PNG/TIFF/JPG/SVG/PDF at a chosen DPI; export_print_ready writes a "
        "high-DPI CMYK/RGB TIFF for print submission; export_latex writes an "
        "Inkscape-style 'PDF + LaTeX' pair (text-free graphics + \\input-able "
        "LaTeX overlay so labels use the document font and real math) for physicists "
        "(with_caption=True wraps it in a figure float with the stored \\caption). "
        "QC + finishing: audit_figure inventories every panel and flags those "
        "missing a scale bar or a label; style_annotation restyles a label's "
        "font/size/bold/italic/underline/colour while preserving its rich "
        "formatting (super/subscript, per-word colour); add_lut_calibration_bar "
        "adds an intensity colour bar matching a LUT. "
        "Templates/sharing: templatify_figure turns a figure into reusable "
        "template slots; consolidate_figure bundles all image files beside the "
        ".pyf; export_video animates time-stack/video panels to mp4. Review: "
        "export_review writes an HTML review page, list_review_comments / "
        "import_review_comments manage reviewer comments. Accessibility: "
        "simulate_color_blindness renders the figure as a colour-blind reader "
        "would see it (deuteranopia/protanopia/tritanopia); generate_alt_text / "
        "set_alt_text draft and store the figure's alt text. "
        "Arrows: add_arrow points an arrow AT a pixel (tip exact at any size). "
        "Stacks: a stack is one image by default; opt-in views are "
        "add_stack_montage (time/Z frames + stamps), add_channel_split (channels + "
        "merge), add_kymograph and add_orthogonal_views. Upkeep: "
        "check_source_changes (sources changed since the last save), copy_style "
        "(fonts / letters / scale bars / spacing from another figure). Backgrounds: "
        "set_figure_properties(page_background=...) colours the whole figure behind "
        "the panels (the gaps); set_label_background boxes the labels. "
        "WHOLE FIGURES: the simplest route is a recipe — read recipe_reference, write "
        "the figure as one YAML/JSON recipe and build it with "
        "build_figure_from_recipe(recipe_path, recipe_text=...); to change it, edit "
        "the recipe and build again. Use the individual tools for small edits. "
        "Good practice: after building or editing, look at render_preview and "
        "compare what was asked with what is there; a reply starting with ERROR "
        "means nothing (or not everything) was changed. Every call is logged beside "
        "the figure: list_history shows them, undo_last reverts the last change(s). "
        "Never invent pixel sizes, "
        "units or statistics design: ask the user or read the image metadata. "
        "TEACHING: when the user asks how to do something themselves (\"show me how\"), "
        "call show_me_how(<operation>) — it highlights the real menus in their open "
        "PyFigures window and they do the clicks; explain_how gives the steps as text."
    ),
)

_fastmcp_tool = mcp.tool


def _keep_text_arguments_as_text():
    """FastMCP parses a string argument as JSON when the parameter is not
    annotated exactly ``str`` — so ``recipe_text: str | None`` given a JSON
    recipe arrived as a dict and was refused ("Input should be a valid
    string"), and a text "null" became None. Text parameters (str, or str |
    None) keep the text they were given."""
    import typing
    from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata
    original = FuncMetadata.pre_parse_json
    if getattr(original, "_pyfigures", False):
        return

    def is_text(annotation):
        args = typing.get_args(annotation)
        # str | dict | None (a recipe as text or as an object): text stays text
        return annotation is str or (str in args and set(args) <= {str, dict, type(None)})

    def is_text_list(annotation):
        # list[str] or list[str] | None
        if typing.get_origin(annotation) is list:
            return typing.get_args(annotation) == (str,)
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return len(args) == 1 and is_text_list(args[0])

    def pre_parse_json(self, data):
        fields = self.arg_model.model_fields
        text = {k: v for k, v in data.items() if isinstance(v, str)
                and k in fields and is_text(fields[k].annotation)}
        parsed = original(self, data)
        parsed.update(text)
        for k, v in parsed.items():
            # one label sent as a plain string (add_corner_labels(top_right="α / β"))
            # is that one label, not a validation error
            if isinstance(v, str) and k in fields and is_text_list(fields[k].annotation):
                parsed[k] = [v]
        return parsed

    pre_parse_json._pyfigures = True
    FuncMetadata.pre_parse_json = pre_parse_json


_keep_text_arguments_as_text()


_NOT_LOGGED = {"list_history", "undo_last"}     # they read / write the log themselves


def _figures_of_call(fn, args, kwargs) -> list[str]:
    """The .pyf files a tool call names (any argument ending in .pyf, and a
    recipe's output), for the call history."""
    if fn.__name__ in _NOT_LOGGED:
        return []
    try:
        import inspect
        bound = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
    except TypeError:
        return []
    found = []
    for value in bound.values():
        for v in (value if isinstance(value, (list, tuple)) else [value]):
            if isinstance(v, str) and v.lower().endswith(".pyf"):
                found.append(os.path.abspath(v))
    if fn.__name__ == "build_figure_from_recipe":
        try:
            from pyfigures.recipe import _resolve
            text = bound.get("recipe_text")
            path = bound.get("recipe_path") or ""
            if text is None and os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
            if isinstance(text, dict):
                data = text
            elif text:
                if path.lower().endswith(".json"):
                    data = json.loads(text)
                else:
                    import yaml
                    data = yaml.safe_load(text)
            else:
                data = None
            out = data.get("output") if isinstance(data, dict) else None
            if isinstance(out, str):
                found.append(_resolve(os.path.dirname(os.path.abspath(path)), out))
        except Exception:
            pass
    return list(dict.fromkeys(found))


def _sub_group_hint(fn, args, kwargs) -> str:
    """' — group [0] holds no image itself, only sub-group(s) [0, 0]: …' for
    an image_index refused in a group that only holds sub-groups (after a
    move or stack_with_image a model kept asking group [0] for its images)."""
    import inspect
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
        pyf = bound.get("pyf_path")
        gp = bound.get("group_path", bound.get("src_group_path"))
        if not isinstance(pyf, str) or not isinstance(gp, list) or not gp:
            return ""
        from .core import _load, _navigate_group
        _, root = _load(pyf)
        grp, err = _navigate_group(root, gp)
        content = grp.find("content") if grp is not None else None
        n = sum(1 for c in content if c.tag == "Group") if content is not None else 0
    except Exception:
        return ""
    if not n:
        return ""
    subs = ", ".join(str(list(gp) + [i]) for i in range(n))
    return (f" Group {list(gp)} holds no image itself, only sub-group(s) {subs}: "
            f"use that group_path for their images (describe_figure lists them).")


_OUTPUT_ARGS = ("out_path", "out_html")
_DOCUMENT_ARGS = ("pyf_path", "poster_path", "album_path", "old_pyf", "new_pyf", "source_pyf")


def _output_clash(fn, args, kwargs) -> str | None:
    """Why the call's output file would overwrite its own figure or one of the
    figure's source images, or None. export_figure(fig, 'camera.png') replaced
    the camera.png the figure was built from."""
    import inspect
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
    except TypeError:
        return None
    outs = [bound[k] for k in _OUTPUT_ARGS if isinstance(bound.get(k), str) and bound[k]]
    docs = [bound[k] for k in _DOCUMENT_ARGS if isinstance(bound.get(k), str) and bound[k]]
    if not outs or not docs:
        return None

    def key(p):
        return os.path.normcase(os.path.abspath(p))
    protected = {key(d): f"the document itself ({os.path.basename(d)})" for d in docs}
    for d in docs:
        if not os.path.isfile(d):
            continue
        if not d.lower().endswith(".pyf"):
            # posters / albums (XML, older ones JSON): every path-like string
            try:
                import xml.etree.ElementTree as ET
                data = [v for el in ET.parse(d).getroot().iter() for v in el.attrib.values()]
            except Exception:
                try:
                    with open(d, encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    continue
            stack = [data]
            while stack:
                v = stack.pop()
                if isinstance(v, dict):
                    stack.extend(v.values())
                elif isinstance(v, list):
                    stack.extend(v)
                elif isinstance(v, str) and os.path.splitext(v)[1] and ("/" in v or "\\" in v):
                    p = v if os.path.isabs(v) else os.path.join(os.path.dirname(d), v)
                    protected.setdefault(key(p), f"a source image of the document ({os.path.basename(v)})")
            continue
        try:
            from .core import _load, _decode
            _, root = _load(d, resolve=False)
        except Exception:
            continue
        for el in root.iter("filename"):
            name = _decode(el.text) if el.text else None
            names = name if isinstance(name, list) else [name]
            if isinstance(name, str) and name.startswith("["):
                import ast
                try:
                    names = ast.literal_eval(name)
                except (ValueError, SyntaxError):
                    names = [name]
            for n in names:
                if isinstance(n, str) and n not in ("None", "@template@", ""):
                    protected.setdefault(key(n), f"a source image of the figure ({os.path.basename(n)})")
    for o in outs:
        what = protected.get(key(o))
        if what:
            return f"ERROR: {o} is {what}: exporting there would overwrite it. Choose another out_path."
    return None


_PATH_SUFFIXES = ("_path", "_pyf", "_html", "_dir", "filename", "folder")


def _empty_path_argument(fn, args, kwargs) -> str | None:
    """Why the call passes an empty file or folder path, or None. '' resolved
    to the working directory: index_figures(index_path='') tried to replace
    the current folder with its index file, and get_xml('') raised a raw
    PermissionError."""
    import inspect
    try:
        sig = inspect.signature(fn)
        bound = sig.bind_partial(*args, **kwargs).arguments
    except TypeError:
        return None
    for name, value in bound.items():
        if sig.parameters[name].default == "":     # '' means "none" there (show_me_how)
            continue
        if name.endswith(_PATH_SUFFIXES) and isinstance(value, str) and not value.strip():
            return f"ERROR: {name} is empty: give a file or folder path. Nothing was changed."
    return None


# Numbers whose meaning is the same in every tool: (lowest, highest, lowest
# included). A schema sweep of all tools found -1 strokes, 0 dpi renders that
# crashed, -1 rows per kymograph frame, 10-million-dpi exports, 1e9 pt fonts.
_RANGES = {
    **{n: (0, 2400, False) for n in ("dpi", "thumb_dpi", "min_dpi")},
    **{n: (0, 1000, False) for n in ("font_size", "font_pt", "min_pt", "min_font_pt")},
    **{n: (0, 1000, True) for n in ("stroke", "border_size", "inset_border", "tick", "label_gap")},
    **{n: (0, 100000, True) for n in ("spacing", "spacing_px", "default_spacing", "gap", "gap_mm",
                                     "margin_mm", "frame_height")},
    **{n: (0, 100000, False) for n in ("max_dimension", "max_dim", "width_px", "scale_bar_width",
                                       "bar_width_in_units", "scale_bar_units", "radius_mm")},
    **{n: (0, 10000, False) for n in ("width_mm", "height_mm", "max_height_mm")},
    "width_cm": (0, 1000, False), "width_in": (0, 400, False),
    "line_width": (0, 1000, False), "z_scale": (0, 1000, False),
    **{n: (0, 1e6, False) for n in ("px_to_unit", "scale_bar_px_to_unit")},
    **{n: (0, 1000, False) for n in ("columns", "num_cols", "num_rows", "block")},
    "min_clones": (0, 1e6, False),
}


def _out_of_range_argument(fn, args, kwargs) -> str | None:
    """Why an argument is out of its range, an unknown placement, an empty
    font name or a negative group index, or None. Only arguments the caller
    passed are checked, and a value equal to the parameter's default is
    always allowed (frame_height=0 means 'automatic')."""
    import inspect
    try:
        sig = inspect.signature(fn)
        bound = sig.bind_partial(*args, **kwargs).arguments
    except TypeError:
        return None
    from .core import _corner_error, _placement_error
    for name, value in bound.items():
        default = sig.parameters[name].default
        if value is None or isinstance(value, bool) or value == default:
            continue
        if name in _RANGES and isinstance(value, (int, float)):
            lo, hi, lo_ok = _RANGES[name]
            if value < lo or (value == lo and not lo_ok) or value > hi:
                low = ("not negative" if lo_ok and lo == 0 else "positive" if lo == 0
                       else f"{'≥' if lo_ok else '>'} {lo:g}")
                return (f"ERROR: {name} must be {low} and at most {hi:g} (got {value!r}). "
                        "Nothing was changed.")
        elif name.endswith("placement") and isinstance(value, str):
            bad = _corner_error(value) if name == "bar_placement" else _placement_error(value)
            if bad:
                return f"ERROR: {name}: {bad}. Nothing was changed."
        elif name == "projection" and isinstance(value, str) \
                and value.strip().lower() not in ("max", "min", "avg", "none", ""):
            return f"ERROR: projection must be 'max', 'min', 'avg' or 'none' (got {value!r})."
        elif name in ("font_family", "font") and isinstance(value, str) and not value.strip():
            return f"ERROR: {name} is empty: give a font name (list_fonts shows them)."
        elif name.endswith("group_path") and isinstance(value, (list, tuple)) \
                and any(isinstance(i, int) and i < 0 for i in value):
            return f"ERROR: {name} {list(value)} has a negative index; use describe_figure for the paths."
    return None


def _non_finite_argument(fn, args, kwargs) -> str | None:
    """Why the call carries a NaN / infinite number (alone or in a list), or
    None. They were saved as ROI corners, bracket heights, arrow tails, pixel
    sizes... (a rectangle at x=nan) or crashed int() conversions."""
    import inspect
    try:
        bound = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
    except TypeError:
        return None

    def bad(v, depth=0):
        if isinstance(v, float):
            return not math.isfinite(v)
        if isinstance(v, (list, tuple)) and depth < 3:
            return any(bad(x, depth + 1) for x in v)
        if isinstance(v, dict) and depth < 3:
            return any(bad(x, depth + 1) for x in v.values())
        return False
    for name, value in bound.items():
        if bad(value):
            return f"ERROR: {name} must hold finite numbers (got {value!r}). Nothing was changed."
    return None


def _tool_with_warnings(*t_args, **t_kwargs):
    """Drop-in for ``mcp.tool()``: runs the tool, then appends any warning raised
    via _warn() during the call (e.g. a failed layout recompute) to a plain-text
    result, so a tool never silently reports success. JSON results are left
    untouched (the warning still goes to the server log)."""
    import functools
    register = _fastmcp_tool(*t_args, **t_kwargs)

    def deco(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            _TOOL_WARNINGS.clear()
            clash = (_non_finite_argument(fn, args, kwargs) or _empty_path_argument(fn, args, kwargs)
                     or _out_of_range_argument(fn, args, kwargs) or _output_clash(fn, args, kwargs))
            if clash:
                return clash
            from .core import ColorError
            try:
                res = fn(*args, **kwargs)
            except ColorError as e:
                # raised while reading the arguments, before anything is saved
                res = f"ERROR: {e}"
            except FileNotFoundError as e:
                # a clear answer instead of a raw "[Errno 2]" traceback text
                missing = e.filename or str(e)
                hint = (" — create it first with create_figure (or build_figure_from_recipe)"
                        if str(missing).lower().endswith(".pyf") else "")
                res = f"ERROR: file not found: {missing}{hint}."
            if isinstance(res, str) and res.startswith("ERROR: image_index") \
                    and "out of range (0 images)" in res:
                res += _sub_group_hint(fn, args, kwargs)
            if _TOOL_WARNINGS and isinstance(res, str) \
                    and not res.lstrip().startswith(("{", "[")):
                res = res + "\n" + "\n".join("WARNING: " + w for w in _TOOL_WARNINGS)
            _TOOL_WARNINGS.clear()
            return res

        # MCP clients see a refused request as a tool error (isError=true), not
        # as a successful reply that happens to start with "ERROR:" — models
        # took those for completed edits. Python callers keep the string.
        # every call a client makes on a figure is logged beside it, with the
        # figure as it was before a changing call, so it can be undone
        # (pyfigures/history.py). Python callers — recipes building through
        # these functions, the GUI — are not logged call by call.
        @functools.wraps(fn)
        def over_mcp(*args, **kwargs):
            figures = _figures_of_call(fn, args, kwargs)
            before = {}
            if figures:
                from pyfigures import history
                before = {p: history.capture(p) for p in figures}
            try:
                res = inner(*args, **kwargs)
            except Exception as e:
                res = f"ERROR: {type(e).__name__}: {e}"
                _log_calls(fn, args, kwargs, figures, before, res)
                raise
            _log_calls(fn, args, kwargs, figures, before, res)
            if isinstance(res, str) and res.lstrip().startswith("ERROR"):
                from mcp.server.fastmcp.exceptions import ToolError
                raise ToolError(res.strip())
            return res
        register(over_mcp)
        return inner

    return deco


def _log_calls(fn, args, kwargs, figures, before, res):
    if figures:
        from pyfigures import history
        try:
            import inspect
            bound = inspect.signature(fn).bind_partial(*args, **kwargs)
            for p in figures:
                history.record(p, fn.__name__, dict(bound.arguments), res, before[p])
        except Exception as e:     # the log never blocks a tool
            print(f"pyfigures-mcp: call history skipped ({type(e).__name__}: {e})",
                  file=sys.stderr)


mcp.tool = _tool_with_warnings


# Warnings raised while a tool runs (e.g. a failed layout recompute). The tool
# wrapper installed below appends them to the tool's text result, so a problem
# is reported instead of the tool claiming success.
_TOOL_WARNINGS: list[str] = []


def _warn(msg: str) -> None:
    _TOOL_WARNINGS.append(msg)
    print("pyfigures-mcp WARNING: " + msg, file=sys.stderr)
