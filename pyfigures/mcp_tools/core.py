"""PyFigures MCP tools — Shared helpers: .pyf XML encoding, atomic save + layout recompute, element builders, colours, scale bars, sidecars, panel iteration.

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
    _warn,
)

# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _decode(text: str | None):
    """Decode a serialized PyFigures XML value to a Python value."""
    if text is None:
        return None
    t = text.strip()
    if t == "None":
        return None
    if t == "True":
        return True
    if t == "False":
        return False
    # Double-quoted string:  ""value""
    if t.startswith('""') and t.endswith('""') and len(t) >= 4:
        return t[2:-2]
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _encode_str(value: str) -> str:
    """Encode a string for PyFigures XML (wrap in double-quotes)."""
    return f'""{ value }""'


def _strip_tags(s: str) -> str:
    """Best-effort plain text from a possibly-HTML string (for length/logging)."""
    import re as _re
    # Qt rich text carries a <head><style>…</style></head> block: drop its CSS
    s = _re.sub(r"<(style|head|script)[^>]*>.*?</\1>", "", s or "", flags=_re.DOTALL | _re.IGNORECASE)
    return _re.sub(r"<[^>]+>", "", s)


def _escape_if_plain(s: str) -> str:
    """Escape XML/HTML specials in *s* only if it looks like plain text (no tag).
    Lets callers pass either plain labels ("p<0.001") or ready HTML ("<b>*</b>")."""
    if s and "<" in s and ">" in s and _strip_tags(s) != s:
        return s  # already contains markup — leave verbatim
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _encode_value(value: str) -> str:
    """Encode a user-supplied value string for storage in PyFigures XML.

    Applies the correct encoding automatically so callers do not need to know
    the internal ``""…""`` convention:

    ===========================  ============================================
    User passes                  Stored as
    ===========================  ============================================
    ``"None"``                   ``None``
    ``"True"`` / ``"False"``     ``True`` / ``False``
    Numeric string (``"3.14"``)  ``3.14``
    List / dict literal          stored as-is (Python repr)
    ``"PyQt6…"`` object string   stored as-is
    Anything else                ``""value""``  (PyFigures string encoding)
    ===========================  ============================================
    """
    # a number, true/false or a list from a JSON client (crop_left=100 raised
    # "'int' object has no attribute 'strip'"): its Python spelling
    if value is None or isinstance(value, (bool, int, float, list, tuple, dict)):
        return repr(list(value) if isinstance(value, tuple) else value)
    v = str(value).strip()
    # Keywords / sentinels
    if v in ("None", "True", "False"):
        return v
    # Numeric
    try:
        int(v)
        return v
    except ValueError:
        pass
    try:
        float(v)
        return v
    except ValueError:
        pass
    # Python collection literal or Qt object string → store verbatim
    if (v.startswith("[") and v.endswith("]")) or \
       (v.startswith("{") and v.endswith("}")) or \
       v.startswith("PyQt"):
        return v
    # Plain text string → PyFigures encoding
    return _encode_str(v)


# Friendly names a model (or a user) is likely to use, mapped to the stored
# tag. list_insets reports "size_fraction", so set_inset_property must accept it.
_IMAGE_PROPERTY_ALIASES = {
    "size_fraction": "fraction_of_parent_image_width_if_image_is_inset",
    "inset_size_fraction": "fraction_of_parent_image_width_if_image_is_inset",
    "fraction_of_parent_width": "fraction_of_parent_image_width_if_image_is_inset",
    "rotation": "theta",
    "angle": "theta",
    "luts": "LUTs",
    "lut": "LUTs",
    "comments": "user_comments",
    "pixel_size": "px_to_unit_conversion_factor",
}

# Stored fields that are not Image2D.__init__ arguments
_IMAGE_EXTRA_FIELDS = {"color", "fill_color", "stroke", "line_style", "immutable", "isSet",
                       "incompressible_width", "incompressible_height", "translation",
                       "lower_indices", "upper_indices", "lower_values", "upper_values"}
_IMAGE_FIELDS_CACHE: set[str] = set()


def _image_field_names() -> set[str]:
    """Every property name an Image2D stores."""
    if not _IMAGE_FIELDS_CACHE:
        import inspect
        from batoolset.drawings.shapes.image2d import Image2D as _Image2D
        params = inspect.signature(_Image2D.__init__).parameters
        _IMAGE_FIELDS_CACHE.update(k for k in params if k not in ("self", "args", "kwargs"))
        _IMAGE_FIELDS_CACHE.update(_IMAGE_EXTRA_FIELDS)
    return _IMAGE_FIELDS_CACHE


def _resolve_image_property(elem: ET.Element, name: str) -> tuple[str | None, str | None]:
    """(stored tag, None) for a known Image2D property name or alias, else
    (None, error message). An unknown name used to be written as a new,
    ignored XML field while the tool reported success."""
    name = (name or "").strip()
    known = _image_field_names() | {c.tag for c in elem}
    if name in known:
        return name, None
    alias = _IMAGE_PROPERTY_ALIASES.get(name.lower())
    if alias:
        return alias, None
    lower = {k.lower(): k for k in known}
    if name.lower() in lower:
        return lower[name.lower()], None
    import difflib
    close = difflib.get_close_matches(name, sorted(known | set(_IMAGE_PROPERTY_ALIASES)), n=3)
    hint = f" Did you mean: {', '.join(close)}?" if close else ""
    return None, (f"ERROR: unknown property '{name}' — nothing was changed.{hint} "
                  "Use list_image_properties() / list_insets() for the valid names.")


def _stored_image_property(pyf_path: str, group_path: list[int], image_index: int,
                           tag: str, inset_index: int | None = None) -> str:
    """The value of *tag* as it is in the saved file (after the save's own
    processing), so a tool reports what was really stored, not the request."""
    _, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return "?"
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return "?"
    elem = imgs[image_index]
    if inset_index is not None:
        annots = elem.find("annotations")
        insets = [] if annots is None else [c for c in annots if c.tag == "Image2D"]
        if not 0 <= inset_index < len(insets):
            return "?"
        elem = insets[inset_index]
    child = elem.find(tag)
    return "(not stored)" if child is None else str(child.text)


_NORMALIZATION_KEYS = {"per_channel", "range", "min_value", "max_value", "ignore_hot_spots"}


def _normalization_to_store(text) -> tuple[str | None, str | None]:
    """(stored text, error) for a normalization given as JSON or a Python
    dict literal. The renderer reads it with ast.literal_eval, so the JSON form
    of the docs ('{"per_channel": true}') must be stored as a Python literal:
    as JSON it failed to parse and the panel was drawn solid white."""
    bad = _normalization_error(text)
    if bad:
        return None, bad
    import ast
    import json
    if isinstance(text, dict):
        return repr(text), None
    try:
        return repr(json.loads(str(text))), None
    except ValueError:
        return repr(ast.literal_eval(str(text))), None


def _normalization_error(text) -> str | None:
    """Why *text* is not a normalization the renderer understands (a dict
    such as '{"per_channel": true}' or '{"range": "custom", "min_value": 200,
    "max_value": 3500}'), or None. A bare word like 'weird' used to be stored
    and then substring-matched by the renderer ('range' in 'weird')."""
    import ast
    import json
    if isinstance(text, dict):
        d = text
    else:
        try:
            d = json.loads(str(text))
        except ValueError:
            try:
                d = ast.literal_eval(str(text))
            except (ValueError, SyntaxError):
                d = None
    usage = ("normalization must be a dict such as '{\"per_channel\": true}', "
             "'{\"range\": \"display\"}' or '{\"range\": \"custom\", \"min_value\": 200, "
             "\"max_value\": 3500}'")
    if not isinstance(d, dict):
        return f"{usage}, not {text!r}"
    unknown = sorted(set(d) - _NORMALIZATION_KEYS)
    if unknown:
        return f"unknown normalization key(s) {unknown}; use {sorted(_NORMALIZATION_KEYS)}"
    rng = d.get("range")
    if rng not in (None, "all", "display", "custom"):
        return f"normalization range must be 'all', 'display' or 'custom', not {rng!r}"
    if rng == "custom":
        lo, hi = d.get("min_value"), d.get("max_value")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                   for v in (lo, hi)):
            return "a 'custom' range needs numeric min_value and max_value"
        if lo >= hi:
            return f"min_value ({lo}) must be below max_value ({hi})"
    hot = d.get("ignore_hot_spots")
    if hot not in (None, False, True) and not (isinstance(hot, (int, float)) and 0 <= hot < 1):
        return f"ignore_hot_spots must be a fraction between 0 and 1 (got {hot!r})"
    return None


def _check_property_value(tag: str, raw: str) -> str | None:
    """Range checks for the properties where a bad value silently breaks the
    render. Returns an error message, or None when the value is acceptable."""
    if tag == "fraction_of_parent_image_width_if_image_is_inset":
        try:
            v = float(raw)
        except ValueError:
            return f"ERROR: {tag} must be a number between 0 (exclusive) and 1."
        if not (0.0 < v <= 1.0):
            return f"ERROR: {tag} must be between 0 (exclusive) and 1, got {v}."
    if tag == "opacity":
        try:
            v = float(raw)
        except ValueError:
            return "ERROR: opacity must be a number between 0 and 1."
        if not (0.0 <= v <= 1.0):
            return f"ERROR: opacity must be between 0 and 1, got {v}."
    if tag in ("crop_left", "crop_right", "crop_top", "crop_bottom", "theta"):
        try:
            v = None if raw == "None" else float(raw)
        except ValueError:
            return f"ERROR: {tag} must be a number."
        if v is not None and not math.isfinite(v):
            return f"ERROR: {tag} must be a finite number, got {raw}."
        if tag != "theta" and v is not None and v < 0:
            return f"ERROR: {tag} is the pixels removed from that side and cannot be negative."
    if tag == "normalization" and raw not in ("None", ""):
        bad = _normalization_error(_decode(raw) if raw.startswith('""') else raw)
        if bad:
            return f"ERROR: {bad}"
    if tag == "border_size" and raw != "None":
        try:
            v = float(raw)
        except ValueError:
            return "ERROR: border_size must be a number of pixels."
        if not (math.isfinite(v) and v >= 0):
            return f"ERROR: border_size must be 0 (no border) or more pixels, got {raw}."
    return None


def _child_text(elem: ET.Element, tag: str):
    child = elem.find(tag)
    return _decode(child.text) if child is not None else None


def _set_child_text(elem: ET.Element, tag: str, raw_text: str):
    child = elem.find(tag)
    if child is None:
        child = ET.SubElement(elem, tag)
    child.text = raw_text


def _load(pyf_path: str, resolve: bool = True) -> tuple[ET.ElementTree, ET.Element]:
    """Parse a .pyf. With *resolve* (default), source paths that no longer exist
    are looked up relative to the .pyf's current location (figure moved to
    another folder / disk / OS) — see pyfigures.path_resolution. A later
    _save() then stores the found locations."""
    tree = ET.parse(pyf_path)
    root = tree.getroot()
    if resolve:
        from ..path_resolution import resolve_moved_paths_in_tree
        resolve_moved_paths_in_tree(root, pyf_path)
    return tree, root


def _atomic_write_text(path: str, text: str) -> None:
    """Write *text* to *path* atomically (temp file in the same folder, then
    os.replace), so a crash mid-write can never leave a truncated .pyf. Retries
    the replace briefly: OneDrive / antivirus can hold the target for a moment."""
    from ..atomic_io import write_atomic
    write_atomic(path, text)


def _raw_size_from_file(filename) -> tuple[int, int] | None:
    """(width, height) of an image in source pixels, read from the file header
    without decoding pixels. None for non-files, SVGs, videos, multi-series
    containers or anything unreadable (those keep their stored size)."""
    if not filename or not isinstance(filename, str):
        return None
    if filename.split("#", 1)[0].rstrip("/\\").lower().endswith(".zarr"):
        try:                       # OME-Zarr (local or URL): the level that is read
            from batoolset.ome_zarr import level_size
            _, w, h = level_size(filename)
            return w, h
        except Exception:
            return None
    from batoolset.omero_web import is_omero_url
    if is_omero_url(filename):
        try:                       # OMERO image: its size from OMERO.web
            from batoolset.omero_web import size_of
            return size_of(filename)
        except Exception:
            return None
    if not os.path.isfile(filename):
        return None
    low = filename.lower()
    if low.endswith((".svg", ".pdf")):     # vector panels have no pixel size
        return None
    if low.endswith((".tif", ".tiff")):
        try:
            import tifffile as _tf
            with _tf.TiffFile(filename) as t:
                p = t.pages[0]
                # imagewidth/imagelength are right even for planar (C,H,W) pages,
                # where p.shape[1] would be the height
                return int(p.imagewidth), int(p.imagelength)
        except Exception:
            pass
    try:
        from PIL import Image as _PI
        with _PI.open(filename) as im:
            return int(im.size[0]), int(im.size[1])
    except Exception:
        return None


def _channel_count_from_file(filename) -> int | None:
    """Number of colour channels of an image file (3 for RGB, the C axis of a
    TIFF), read from the header; None when unknown."""
    if not isinstance(filename, str) or not os.path.isfile(filename):
        return None
    if filename.lower().endswith((".tif", ".tiff")):
        try:
            import tifffile as _tf
            with _tf.TiffFile(filename) as t:
                s = t.series[0]
                for ax in ("C", "S"):
                    if ax in s.axes:
                        return int(s.shape[s.axes.index(ax)])
                # 'Q': an axis tifffile could not name (it may hold the channels)
                return None if "Q" in s.axes else 1
        except Exception:
            return None
    try:
        from PIL import Image as _PI
        with _PI.open(filename) as im:
            return len([b for b in im.getbands() if b != "A"])
    except Exception:
        return None


def _z_stack_projection(img: ET.Element, filename) -> str:
    """A new Z stack shows its max projection when the user's preference says
    so (View → Show new Z stacks as max projection, on by default), as in the
    GUI: added through the MCP server it always showed its first slice, often
    nearly black. Sets the projection on *img* and returns a note, or ''.
    Only TIFFs are checked (from the header); only stacks whose last extra
    axis is Z, so a time series keeps its first frame — the GUI's rule."""
    if not isinstance(filename, str) or not filename.lower().endswith((".tif", ".tiff")) \
            or not os.path.isfile(filename):
        return ""
    try:
        import tifffile as _tf
        with _tf.TiffFile(filename) as t:
            axes, shape = t.series[0].axes, t.series[0].shape
    except Exception:
        return ""
    extra = [a for a in axes if a not in "YXCS"]
    if not extra or extra[-1] != "Z" or shape[axes.index("Z")] < 2:
        return ""
    n_z = shape[axes.index("Z")]
    try:
        from pyfigures.gui.user_prefs import load_max_project_z_stacks
        project = load_max_project_z_stacks()
    except Exception:
        project = True
    if project:
        _set_child_text(img, "projection", "max")
        return (f"\nNOTE: Z stack of {n_z} slices: shown as its max projection "
                f"(configure_image projection='none' shows one slice).")
    return (f"\nNOTE: Z stack of {n_z} slices: its first slice is shown "
            f"(configure_image projection='max' for a max projection).")


def _reset_luts_for_new_file(img: ET.Element, filename: str) -> str:
    """When a panel gets another file (a template slot filled) whose channel
    count differs from its stored LUTs, drop the LUTs and channel choice so the
    file shows with its defaults (a grey image in a two-channel slot was drawn
    as a dark green one). Returns a note, or ''."""
    luts = _child_text(img, "LUTs")
    if isinstance(luts, str) and luts.startswith("["):      # stored as "['GREEN', 'RED']"
        import ast
        try:
            luts = ast.literal_eval(luts)
        except (ValueError, SyntaxError):
            return ""
    n = _channel_count_from_file(filename)
    if not isinstance(luts, list) or not n or len(luts) == n:
        return ""
    _set_child_text(img, "LUTs", "None")
    _set_child_text(img, "channels", _encode_str("None"))
    return (f" The slot's {len(luts)} colour(s) {luts} did not fit the file's {n} channel(s): "
            f"reset to the defaults (set_lut to choose).")


def _crop_fit_error(img: ET.Element) -> str | None:
    """An error when the stored crop removes the whole image (a local model
    cropped 430 px from each side of a 512 px image: the panel was built from
    nothing and drawn stretched), else None."""
    size = _raw_size_from_file(_first_filename(img))
    if not size:
        return None

    def _c(name):
        try:
            return max(0, int(float(_child_text(img, name) or 0)))
        except (TypeError, ValueError):
            return 0

    w, h = size
    lr = _c("crop_left") + _c("crop_right")
    tb = _c("crop_top") + _c("crop_bottom")
    if lr >= w or tb >= h:
        return (f"the crop removes the whole image: the source is {w} x {h} px and the crop "
                f"takes {lr} px across (left + right) and {tb} px down (top + bottom). "
                f"Crop values are pixels removed from each side (not coordinates), e.g. "
                f"crop_bottom=24 removes a 24 px strip at the bottom. To show a small "
                f"region magnified, keep the image and add a zoom callout "
                f"(add_zoom_callout; recipe: zoom: {{box: [x, y, width, height]}}).")
    return None


def _first_filename(img: ET.Element) -> str | None:
    """The (first) source file of an Image2D element, or None."""
    import ast
    fn = _child_text(img, "filename")
    if not isinstance(fn, str) or fn in ("None", "", _TEMPLATE_SENTINEL):
        return None
    if fn.startswith("[") and fn.endswith("]"):
        try:
            lst = ast.literal_eval(fn)
        except Exception:
            return None
        return lst[0] if lst and isinstance(lst[0], str) else None
    return fn


def _sync_raw_sizes(root: ET.Element) -> int:
    """Make every file-backed Image2D store its TRUE source size.

    New panels created by this server carry no size, and the layout engine then
    assumes a 512x512 placeholder, so every image was laid out as a square until
    the GUI reopened the file. Stale sizes (source replaced by a different-sized
    file) have the same effect. Returns the number of panels updated."""
    n = 0
    for img in root.iter("Image2D"):
        sc = _child_text(img, "custom_loading_script")
        if isinstance(sc, str) and sc not in ("", "None"):
            continue  # scripted panel: size comes from the script's output
        wh = _raw_size_from_file(_first_filename(img))
        if wh is None:
            continue
        cur_w, cur_h = _child_text(img, "width"), _child_text(img, "height")
        try:
            same = abs(float(cur_w) - wh[0]) < 0.5 and abs(float(cur_h) - wh[1]) < 0.5
        except (TypeError, ValueError):
            same = False
        if not same:
            _set_child_text(img, "width", f"{float(wh[0])}")
            _set_child_text(img, "height", f"{float(wh[1])}")
            n += 1
    return n


def _save(tree: ET.ElementTree, pyf_path: str, recompute: bool = False):
    _sync_raw_sizes(tree.getroot())
    ET.indent(tree, space="  ")
    buf = io.StringIO()
    tree.write(buf, encoding="unicode", xml_declaration=True)
    _atomic_write_text(pyf_path, buf.getvalue())
    # source snapshot (<figure>.sources.json): report files that changed since
    # the previous save, then make the current files the reference
    try:
        from pyfigures.source_snapshot import compare_and_record, describe
        changed = describe(compare_and_record(pyf_path, tree.getroot()))
        if changed:
            _warn(changed.replace("\n", " "))
    except Exception as e:           # never block a save on the snapshot
        print(f"pyfigures-mcp: source snapshot skipped ({type(e).__name__}: {e})",
              file=sys.stderr)
    if recompute:
        err = _auto_recompute(pyf_path)
        if err:
            _warn(f"figure saved, but the automatic layout update failed ({err}); "
                  "positions may be stale until the figure is reopened in PyFigures.")


def _auto_recompute(pyf_path: str) -> str:
    """Re-run PyFigures' layout engine on all top-level groups at their current size.

    After structural edits (add/remove images, change orientation/spacing, …)
    the stored x/y positions can be stale.  This function re-deserialises the
    file with the PyFigures engine, calls ``set_to_width`` for every top-level
    group using its stored ``size`` attribute, then re-serialises.

    Then stacks the top-level rows vertically exactly like the GUI's default
    ("auto") layout does on paint, so stored y positions are consistent too.

    Panel scripts (data plots, channel merges, ...) are NOT executed for panels
    that already have a stored size — laying out a figure must not run panel
    code, and re-running every plot's statistics on each edit was slow. Only a
    brand-new scripted panel with no size yet is run once to measure it.

    Returns an empty string on success or a short error description on failure
    (the caller reports it as a warning — layout recompute is best-effort).
    """
    try:
        from batoolset.settings.global_settings import set_UI as _set_UI
        _set_UI()
        _ensure_qapp()
        from batoolset.drawings.shapes.image2d import Image2D as _Image2D
        from batoolset.serializations.tools import (
            deserialize_to_dict as _d2d,
            create_object as _co,
            object_to_xml as _to_xml,
        )
        from batoolset.drawings.shapes.group import Group as _Group, set_to_width as _stw
        from batoolset.figure.alignment import pack2 as _pack2, align2 as _align2, \
            align_positions as _align_positions
    except Exception as exc:
        return f"layout engine unavailable: {exc}"

    try:
        xml_content = Path(pyf_path).read_text(encoding="utf-8")
        space = 3.0
        try:
            sp = ET.fromstring(xml_content).find("SerializableGUIparameters/space")
            if sp is not None and sp.text:
                space = float(sp.text)
        except (ET.ParseError, ValueError):
            pass
        _Image2D._lazy_mode = True
        _Image2D._skip_sized_scripts = True
        try:
            props = _d2d(xml_content)
            objects = _co(list.__name__, props)
        finally:
            _Image2D._lazy_mode = False
            _Image2D._skip_sized_scripts = False

        top_groups = [o for o in objects if isinstance(o, _Group)]
        if not top_groups:
            return ""  # free-canvas figure — nothing to recompute
        for grp in top_groups:
            try:
                w = float(getattr(grp, "size", 0) or 0)
            except (TypeError, ValueError):
                w = 0.0
            if not (math.isfinite(w) and w > 0):
                # no intended width stored: keep the group's current width;
                # a never-packed group has an empty (±inf) rect -> GUI default 512
                cur = float(grp.getRect(all=True).width())
                w = cur if (math.isfinite(cur) and cur > 0) else 512.0
            if len(getattr(grp, "content", [])) > 0:
                _stw(grp, w)

        # vertical stacking, as MyWidget.repack_all() does in auto mode
        drawables = [o for o in objects
                     if hasattr(o, "setTopLeft") and hasattr(o, "getRect")
                     and not (hasattr(o, "content") and len(o.content) == 0)]
        if drawables:
            drawables[0].setTopLeft(50, 50)
            _align2(_align_positions[2], *drawables)
            _pack2(space, "Y", False, *drawables)

        new_xml = _sanitize_recomputed_xml(_to_xml(objects, is_list=True))
        if new_xml is not None:
            # the engine drops an object it cannot rebuild (a whole group
            # when its layout raised): never write a figure that lost panels
            def _count(text):
                r = ET.fromstring(text)
                return sum(1 for _ in r.iter("Image2D")), sum(1 for _ in r.iter("Group"))
            if _count(new_xml) != _count(xml_content):
                return ("the layout engine could not rebuild every panel; kept the figure as "
                        "saved (nothing was lost)")
        if new_xml is None:
            # an empty sub-group (just added, to be filled) has no extent and
            # the engine cannot lay out its parents: nothing visible changed,
            # the layout is redone when a panel goes into it
            if any(g.find(".//Image2D") is None
                   for g in ET.fromstring(xml_content).iter("Group")):
                return ""
            return ("layout engine produced non-finite geometry; kept the "
                    "positions as saved")
        _atomic_write_text(pyf_path, new_xml)
        squeezed = _squeezed_panels(top_groups, _Image2D)
        if squeezed:
            _warn(squeezed)
        for msg in _failed_scripts(objects, _Image2D):
            _warn(msg)
        return ""
    except Exception as exc:
        return f"layout recompute failed: {type(exc).__name__}: {exc}"


def _failed_scripts(objects, image_cls) -> list[str]:
    """Warnings for panel scripts run by this layout pass (new scripted
    panels) that raised or set no image: the panel is otherwise just empty."""
    out = []

    def walk(items):
        for o in items:
            if isinstance(o, image_cls):
                if not getattr(o, "custom_loading_script", None):
                    continue
                log = getattr(o, "script_log", "") or ""
                if "An error occurred" in log:
                    first = log.split("An error occurred:", 1)[1].strip().splitlines()[0]
                    out.append(f"a panel script failed ({first}); the panel is empty.")
                elif getattr(o, "img", None) is None and log:
                    out.append("a panel script did not set self.img; the panel is empty.")
            walk(getattr(o, "content", []) or [])

    walk(objects)
    return out


_MIN_PANEL_PX = 4


def _squeezed_panels(groups, image_cls) -> str:
    """A warning when the layout left panels only a few pixels wide or high —
    a figure too narrow for its panels and gaps (200 frames in one row, a
    width of 5 px): they render as nothing."""
    small = []
    worst = None

    def walk(obj, parent):
        nonlocal worst
        for c in getattr(obj, "content", []) or []:
            if isinstance(c, image_cls):
                # shown size = raw size / scale (the engine gives a negative
                # scale when the gaps alone are wider than the figure)
                try:
                    w, h = c.get_raw_size()
                    side = min(float(w), float(h)) / float(c.scale)
                except Exception:
                    continue
                if not math.isfinite(side):
                    continue
                if side < _MIN_PANEL_PX:
                    small.append(c)
                    if worst is None or side < worst[0]:
                        worst = (side, parent if parent is not None else obj)
            else:
                walk(c, obj)

    for g in groups:
        walk(g, None)
    if not small:
        return ""
    side, grp = worst
    n = len(getattr(grp, "content", []) or [])
    smallest = "no room at all" if side <= 0 else f"the smallest {side:.1f} px"
    return (f"{len(small)} panel(s) are less than {_MIN_PANEL_PX} px on a side ({smallest}, "
            f"in a group of {n}): the figure is too narrow for its panels and "
            f"the gaps between them, and they will not show. Wrap the row (columns=…), "
            f"show fewer panels, reduce the spacing or widen the figure.")


_GEOM_TAGS = ("x", "y", "width", "height")


def _sanitize_recomputed_xml(xml_text: str) -> str | None:
    """Post-process the engine's re-serialised figure.

    An empty group has no extent: the engine reports an infinite/empty rect for
    it, which must not be written (a Group with x=inf / size=-inf fails to load
    and drops its content). Empty groups are therefore written back the way a
    fresh group looks (no geometry, size 512). If any other element still has
    non-finite geometry, returns None so the caller keeps the file unchanged."""
    root = ET.fromstring(xml_text)

    def _finite(el, tag):
        t = el.findtext(tag)
        if t is None:
            return True
        try:
            return math.isfinite(float(t))
        except ValueError:
            return True  # non-numeric field: not geometry we produced

    for grp in root.iter("Group"):
        content = grp.find("content")
        if content is None or len(content) == 0:
            for tag in _GEOM_TAGS:
                el = grp.find(tag)
                if el is not None:
                    grp.remove(el)
            if not _finite(grp, "size"):
                grp.find("size").text = "512.0"
    for el in root.iter():
        if el.tag in ("Group", "Image2D") and not all(
                _finite(el, t) for t in _GEOM_TAGS + ("size", "scale")):
            return None
    # Group IDs come from a process-wide instance counter in the engine (they
    # are reassigned on every load and never read back). Renumber them in
    # document order so the same figure always serialises identically —
    # reproducible, diffable files (e.g. figures rebuilt from a recipe).
    for n, grp in enumerate(root.iter("Group"), start=1):
        id_el = grp.find("ID")
        if id_el is not None:
            id_el.text = str(n)
    out = io.StringIO()
    ET.ElementTree(root).write(out, encoding="unicode", xml_declaration=True)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Figure-level helpers
# ---------------------------------------------------------------------------

def _top_groups(root: ET.Element) -> list[ET.Element]:
    """Return top-level <Group> elements (direct children of <list>)."""
    return [c for c in root if c.tag == "Group"]


_PLOT_CSV = re.compile(r"_csv\s*=\s*(['\"])(.+?)\1")


def _panel_token(img: ET.Element) -> str:
    """Short name of a panel for layout_rows: the file name, '<csv> (plot)'
    for a data plot, '(script panel)' otherwise."""
    fn = _child_text(img, "filename")
    if isinstance(fn, str) and fn and fn != "@template@":
        return Path(fn).name
    script = _child_text(img, "custom_loading_script")
    if script:
        m = _PLOT_CSV.search(str(script))
        if m:
            return f"{Path(m.group(2)).name} (plot)"
        return "(script panel)"
    return "(template slot)" if _is_template(img) else "(empty)"


def _layout_token(el: ET.Element, top: bool = False) -> str | None:
    if el.tag == "Image2D":
        return None if el.findtext("isText", "False") == "True" else _panel_token(el)
    if el.tag != "Group" or _is_label_row_group(el):
        return None
    content = el.find("content")
    parts = [t for t in (_layout_token(c) for c in (list(content) if content is not None else []))
             if t]
    if not parts:
        return None
    if len(parts) > 1 and len(set(parts)) == 1:
        # a channel split / montage: the same file several times
        tok = f"[{parts[0]} x{len(parts)}]"
    elif len(parts) == 1:
        tok = parts[0]
    else:
        tok = (" | " if _child_text(el, "orientation") != "Y" else " / ").join(parts)
        if not top:
            tok = f"({tok})"
    return tok


def layout_rows(root: ET.Element) -> list[str]:
    """The figure's ACTUAL arrangement, read from the saved file: one line per
    top-level row, panels by file name, ' | ' side by side, ' / ' stacked,
    '( )' a nested group, '[name xN]' the N panels of a channel split or
    montage. Build replies carry it so a model compares what was saved with
    what was asked (Qwen 9B kept a wrong row through five edits while
    describing the requested one)."""
    rows = []
    for el in root:
        tok = _layout_token(el, top=True)
        if tok:
            rows.append(f"row {len(rows) + 1}: {tok}")
    return rows


def _all_groups(root: ET.Element) -> list[ET.Element]:
    """BFS over all <Group> elements in the document."""
    result, queue = [], list(root)
    while queue:
        elem = queue.pop(0)
        if elem.tag == "Group":
            result.append(elem)
        queue.extend(list(elem))
    return result


def _html_to_plain(html: str) -> str:
    """Strip Qt HTML to plain text, removing style/head/script blocks first."""
    # Remove block-level noise that carries non-label text (CSS etc.)
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<head[^>]*>.*?</head>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Normalise whitespace
    return " ".join(text.split()).strip()


_TEMPLATE_SENTINEL = "@template@"


def _is_template(img: ET.Element) -> bool:
    """Return True if this Image2D is an unfilled template slot."""
    fn = _child_text(img, "filename")
    return fn == _TEMPLATE_SENTINEL or (fn is None and img.find("template_rect") is not None)


def _template_size(img: ET.Element) -> str:
    """Return 'WxH' from template_rect, or '?' if absent."""
    tr = img.find("template_rect")
    if tr is None or not tr.text:
        return "?"
    # 'PyQt6.QtCore.QRectF(x, y, w, h)'
    m = re.search(r"QRectF\([\d.]+,\s*[\d.]+,\s*([\d.]+),\s*([\d.]+)\)", tr.text)
    if m:
        return f"{int(float(m.group(1)))}x{int(float(m.group(2)))}"
    return "?"


# ---------------------------------------------------------------------------
# Color helpers
# ---------------------------------------------------------------------------

_NAMED_COLORS: dict[str, int] = {
    "white": 0xFFFFFF, "black": 0, "red": 0xFF0000, "green": 0x00FF00,
    "blue": 0x0000FF, "yellow": 0xFFFF00, "cyan": 0x00FFFF,
    "magenta": 0xFF00FF, "gray": 0x808080, "grey": 0x808080,
    "orange": 0xFF8000, "pink": 0xFF69B4, "purple": 0x800080,
    "lime": 0x00FF00,
}


def _color_to_int(color_spec) -> int:
    """Convert a color specification (name, #rrggbb, or integer) to int."""
    if isinstance(color_spec, (int, float)):
        return int(color_spec)
    s = str(color_spec).strip()
    if s.lower() in _NAMED_COLORS:
        return _NAMED_COLORS[s.lower()]
    # Hex string (#rrggbb, rrggbb, or #rgb)
    s_hex = s.lstrip("#")
    if len(s_hex) == 3 and all(c in "0123456789abcdefABCDEF" for c in s_hex):
        s_hex = s_hex[0] * 2 + s_hex[1] * 2 + s_hex[2] * 2
    if len(s_hex) in (6, 8) and all(c in "0123456789abcdefABCDEF" for c in s_hex):
        return int(s_hex[-6:], 16)
    raise ValueError(
        f"Cannot parse color {color_spec!r}. "
        "Use a name (white, yellow, …), #rrggbb hex, or an integer."
    )


def _label_background_text(spec) -> str:
    """XML value of a TAText2D ``fill_color`` (the box drawn behind a label):
    "none" / "" / False -> "None" (no box), else the colour as an int."""
    if spec is None or spec is False or str(spec).strip().lower() in ("", "none", "transparent"):
        return "None"
    return str(_color_to_int(spec))


def _color_to_hex(color_int: int) -> str:
    return f"#{color_int & 0xFFFFFF:06x}"


# ---------------------------------------------------------------------------
# Scale bar helpers
# ---------------------------------------------------------------------------

def _scale_bar_legend_html(text: str, text_color: str | int = "white") -> str:
    """Return minimal Qt HTML for a scale bar legend label."""
    if isinstance(text_color, int):
        hex_col = _color_to_hex(text_color)
    else:
        s = str(text_color).strip()
        hex_col = _color_to_hex(_color_to_int(s)) if not s.startswith("#") else s
    return f'<font color="{hex_col}">{text}</font>'


def _find_scale_bar(img: ET.Element) -> ET.Element | None:
    """Return the first <ScaleBar> child of <annotations>, or None."""
    annots = img.find("annotations")
    if annots is None:
        return None
    return annots.find("ScaleBar")


def _scalebar_info(sb: ET.Element) -> dict:
    """Extract the key scale bar fields as a plain dict."""
    legend_el = sb.find("legend")
    legend_html = legend_el.text or "" if legend_el is not None else ""
    plain_label = _html_to_plain(legend_html) if legend_html else ""
    return {
        "bar_width_in_units":          _decode(sb.findtext("bar_width_in_units")),
        "unit_to_pixel_conversion_factor": _decode(sb.findtext("unit_to_pixel_conversion_factor")),
        "placement":                   sb.findtext("placement") or "",
        # the drawn colour; files without bar_color draw white whatever `color` says
        "bar_color":                   _decode(sb.findtext("bar_color")) if sb.find("bar_color") is not None
                                       and sb.findtext("bar_color") not in (None, "None") else 0xFFFFFF,
        "isSet":                       _decode(sb.findtext("isSet")),
        "label_plain":                 plain_label,
        "label_html":                  legend_html,
    }


def _new_scalebar_elem(
    bar_width_in_units: float,
    legend_html: str,
    placement: str = "bottom right",
    bar_color: int = 0xFFFFFF,
    px_to_unit: float = 1.0,
) -> ET.Element:
    """Build a complete <ScaleBar> XML element."""
    sb = ET.Element("ScaleBar")
    # Geometry fields are placeholders — PyFigures recomputes on render.
    for tag, val in [
        ("x",                   "0.0"),
        ("y",                   "0.0"),
        ("width",               "50.0"),
        ("height",              "20.0"),
        ("color",               str(int(bar_color))),
        ("fill_color",          "None"),
        ("stroke",              "0.65"),
        ("opacity",             "1.0"),
        ("isSet",               "True"),
        ("scale",               "1"),
        ("line_style",          "None"),
        ("theta",               "0"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",           "False"),
        ("__init_called__",     "True"),
        ("__version__",         "1.0"),
        # 'bar' is a Rectangle2D child re-created by ScaleBar.__init__; the
        # reference is passed as **kwargs and ignored during deserialization.
        ("bar",                 "Rectangle2D-placeholder"),
    ]:
        ET.SubElement(sb, tag).text = val
    # legend is TAText2D serialized as raw HTML (no ""..."" double-quote wrap)
    ET.SubElement(sb, "legend").text = legend_html
    ET.SubElement(sb, "bar_width_in_units").text = str(float(bar_width_in_units))
    ET.SubElement(sb, "unit_to_pixel_conversion_factor").text = str(float(px_to_unit))
    ET.SubElement(sb, "placement").text = placement
    # the bar's drawn colour (ScaleBar.bar_color); `color` above is legacy
    ET.SubElement(sb, "bar_color").text = str(int(bar_color))
    return sb


def _nice_bar_length(max_units: float) -> float:
    """Largest 1/2/5 x 10^k not above *max_units* (a readable bar length)."""
    import math
    if max_units <= 0:
        return 0.0
    k = math.floor(math.log10(max_units))
    for m in (5, 2, 1):
        if m * 10 ** k <= max_units:
            return float(m * 10 ** k)
    return float(10 ** k)


# formats whose header may carry a pixel size (PNG / JPEG never do)
_CALIBRATED_FORMATS = (".tif", ".tiff", ".lsm", ".czi", ".lif", ".nd2", ".oib", ".oif", ".ims",
                       ".zarr", ".ome.zarr", ".vsi", ".lei")


def _file_pixel_size(path) -> float | None:
    """The pixel size (units per pixel) the image file itself records, or None.
    TIFFs are read from their tags; the microscope formats through the image
    reader (slower, only for them)."""
    if not isinstance(path, str) or not path or path == "@template@":
        return None
    low = path.lower()
    if not low.endswith(_CALIBRATED_FORMATS):
        return None
    try:
        if low.endswith((".tif", ".tiff")):
            from .workflow import _try_read_image_info
            v = _try_read_image_info(path).get("px_to_unit")
        else:
            from pyfigures.stack_info import stack_info
            v = stack_info(path).get("vx")
        v = float(v) if v else None
        return v if v and v > 0 else None
    except Exception:
        return None


def _pixel_size(img: ET.Element) -> tuple[float | None, str]:
    """(pixel size, where it comes from) for a panel: 'metadata' (the image
    file records it), 'figure' (set in the figure: by hand, or a value the
    file does not carry) or 'none' — then a scale bar is drawn at 1 unit per
    pixel, which is NOT a calibration."""
    try:
        stored = float(_child_text(img, "px_to_unit_conversion_factor") or 0)
    except (TypeError, ValueError):
        stored = 0.0
    own = _file_pixel_size(_first_filename(img))
    if stored > 0:
        if own is not None and abs(own - stored) <= 0.01 * own:
            return stored, "metadata"
        return stored, "figure"
    if own is not None:
        return own, "metadata"
    return None, "none"


def _scale_bar_length_error(img: ET.Element, bar_width_in_units: float,
                            px_to_unit: float | None, unit: str = "µm") -> str | None:
    """An error when the bar would be as wide as the (cropped) image or wider —
    it was drawn clipped to the panel, i.e. at a wrong length (a model asked for
    100 µm at 0.1 µm/px on a 512 px image), or when the length or the pixel
    size is not a positive number. None when fine or unknown."""
    if px_to_unit is not None and not px_to_unit > 0:
        return (f"px_to_unit must be the pixel size, a positive number of {unit} per pixel "
                f"(got {px_to_unit}).")
    if not bar_width_in_units > 0:
        return f"the scale bar length must be a positive number of {unit} (got {bar_width_in_units})."
    px = px_to_unit
    if px is None:
        try:
            px = float(_child_text(img, "px_to_unit_conversion_factor") or 0)
        except (TypeError, ValueError):
            px = 0
    if not px or px <= 0 or bar_width_in_units <= 0:
        return None
    size = _raw_size_from_file(_first_filename(img))
    if not size:
        return None

    def _c(name):
        try:
            return max(0, int(float(_child_text(img, name) or 0)))
        except (TypeError, ValueError):
            return 0

    visible = size[0] - _c("crop_left") - _c("crop_right")
    if visible <= 0:
        return None
    bar_px = bar_width_in_units / px
    if bar_px < visible:
        return None
    width_units = visible * px
    suggestion = _nice_bar_length(width_units * 0.25)
    return (f"a {bar_width_in_units:g} {unit} bar is {bar_px:.0f} px at {px:g} {unit}/px, but the "
            f"image is only {visible} px ({width_units:g} {unit}) wide — it would be cut to "
            f"the panel and show a wrong length. Use a shorter bar, e.g. {suggestion:g} {unit}"
            f" (about a quarter of the width), or check px_to_unit (the pixel size).")


def _apply_scalebar_to_img(
    img: ET.Element,
    bar_width_in_units: float,
    legend_html: str,
    placement: str,
    bar_color: int,
    px_to_unit: float | None,
) -> str:
    """Add or update a ScaleBar on *img*. Returns 'added' or 'updated'."""
    # Optionally update the image-level pixel-size field so PyFigures uses the
    # correct conversion factor when rendering (it overrides the ScaleBar's own
    # unit_to_pixel_conversion_factor at render time from this value).
    if px_to_unit is not None:
        _set_child_text(img, "px_to_unit_conversion_factor", str(float(px_to_unit)))

    annots = img.find("annotations")
    if annots is None:
        annots = ET.SubElement(img, "annotations")

    sb = annots.find("ScaleBar")
    if sb is not None:
        # Update existing fields in-place
        _set_child_text(sb, "bar_width_in_units", str(float(bar_width_in_units)))
        legend_el = sb.find("legend")
        if legend_el is None:
            legend_el = ET.SubElement(sb, "legend")
        legend_el.text = legend_html
        _set_child_text(sb, "placement", placement)
        _set_child_text(sb, "color", str(int(bar_color)))
        _set_child_text(sb, "bar_color", str(int(bar_color)))   # what is drawn
        _set_child_text(sb, "isSet", "True")
        if px_to_unit is not None:
            _set_child_text(sb, "unit_to_pixel_conversion_factor", str(float(px_to_unit)))
        return "updated"
    else:
        eff_px = px_to_unit if px_to_unit is not None else 1.0
        annots.append(_new_scalebar_elem(bar_width_in_units, legend_html, placement, bar_color, eff_px))
        return "added"


def _image_summary(img: ET.Element, idx: int, prefix: str = "") -> str:
    if _is_template(img):
        ts = _template_size(img)
        script = _child_text(img, "custom_loading_script")
        script_tag = "  [has script]" if script is not None else ""
        return f"{prefix}Image {idx}: <template slot>  [{ts}]{script_tag}  (use fill_template() to assign a file)"
    filename = _child_text(img, "filename") or ""
    filename = Path(filename).name if filename else "<no file>"
    annotations = img.find("annotations")
    annot_parts = []
    if annotations is not None:
        for ta in annotations.findall("TAText2D"):
            raw = _child_text(ta, "text") or ""
            plain = _html_to_plain(raw)[:40]
            placement = _child_text(ta, "placement") or ""
            # a freely placed text (arrow label, bracket star) has no placement
            annot_parts.append(f'"{plain}"' + (f" ({placement})" if placement else " (free)"))
        # ROIs, arrows and brackets were not listed at all
        kinds = {"Rectangle2D": "rectangle", "Ellipse2D": "ellipse", "Line2D": "line",
                 "Polygon2D": "polygon", "PolyLine2D": "polyline", "Freehand2D": "freehand"}
        counts: dict[str, int] = {}
        for c in annotations:
            if c.tag in kinds:
                counts[kinds[c.tag]] = counts.get(kinds[c.tag], 0) + 1
        if counts:
            annot_parts.append("shapes: " + ", ".join(
                f"{n} {k}{'s' if n > 1 else ''}" for k, n in counts.items()))
    annot_str = ", ".join(annot_parts) if annot_parts else "—"
    w = _child_text(img, "width")
    h = _child_text(img, "height")
    size_str = f"{int(w)}x{int(h)}" if isinstance(w, (int, float)) and isinstance(h, (int, float)) else "?"
    script = _child_text(img, "custom_loading_script")
    script_tag = "  [has script]" if script is not None else ""
    # Scale bar summary
    sb = _find_scale_bar(img)
    if sb is not None:
        bw = sb.findtext("bar_width_in_units") or "?"
        pl = sb.findtext("placement") or ""
        legend_el = sb.find("legend")
        lbl = _html_to_plain(legend_el.text or "") if legend_el is not None else ""
        sb_tag = f"  [scale bar: {lbl or bw} {pl}]"
    else:
        sb_tag = ""
    # Inset summary
    annots_el = img.find("annotations")
    n_insets = len([c for c in annots_el if c.tag == "Image2D"]) if annots_el is not None else 0
    inset_tag = f"  [{n_insets} inset(s)]" if n_insets else ""
    return f"{prefix}Image {idx}: {filename}  [{size_str}]  annotations: {annot_str}{script_tag}{sb_tag}{inset_tag}"


def _is_label_row_group(grp: ET.Element) -> bool:
    """Return True if this Group is a text-row/label-row (isText != False)."""
    ist = grp.findtext("isText", "False")
    return ist not in ("False", "")


def _label_row_summary(grp: ET.Element, label: str, depth: int = 0) -> list[str]:
    """One-line summary for a text-row Group."""
    pad = "  " * depth
    ist = _decode(grp.findtext("isText", "False")) or "?"
    content = grp.find("content")
    texts = []
    if content is not None:
        for img in content:
            if img.tag == "Image2D":
                ann = img.find("annotations")
                if ann is not None:
                    for ta in ann.findall("TAText2D"):
                        raw = _child_text(ta, "text") or ""
                        plain = _html_to_plain(raw)[:30]
                        texts.append(f'"{plain}"')
    texts_str = ", ".join(texts) if texts else "(empty)"
    # isText names where the images are ('below' = a row above its group)
    where = {"below": "above the next group", "above": "below the previous group"}.get(ist, repr(ist))
    return [f"{pad}{label} [LABEL ROW, {where}]: {texts_str}"]


def _group_summary(grp: ET.Element, label: str, depth: int = 0,
                   path: list[int] | None = None) -> list[str]:
    """Lines describing *grp*. Sub-groups are named by their group_path and
    images by their image_index, both counted the way the tools count them
    (sub-groups among Group children, images among Image2D children), not by
    position among all children."""
    pad = "  " * depth
    if _is_label_row_group(grp):
        return _label_row_summary(grp, label, depth)
    orientation = _child_text(grp, "orientation") or "?"
    space = _child_text(grp, "space")
    content = grp.find("content")
    children = list(content) if content is not None else []
    lines = [f"{pad}{label} [orientation={orientation}, spacing={space}, {len(children)} children]"]
    n_groups = n_images = 0
    for child in children:
        if child.tag == "Group":
            sub = (path or []) + [n_groups]
            n_groups += 1
            lines.extend(_group_summary(child, f"Group {sub}", depth + 1, sub))
        elif child.tag == "Image2D":
            i = n_images
            n_images += 1
            ist = child.findtext("isText", "False")
            if ist == "True":
                # inline side label — show its text
                ann = child.find("annotations")
                texts = []
                if ann is not None:
                    for ta in ann.findall("TAText2D"):
                        plain = _html_to_plain(_child_text(ta, "text") or "")[:30]
                        texts.append(f'"{plain}"')
                lines.append(f"{pad}  Side-label {i}: {', '.join(texts) or '(empty)'}")
            else:
                lines.append(_image_summary(child, i, pad + "  "))
    return lines


# ---------------------------------------------------------------------------
# Element factories (used by the creation/mutation tools below)
# ---------------------------------------------------------------------------

_ORIENTATIONS = {"x": "X", "row": "X", "horizontal": "X", "h": "X", "side by side": "X",
                 "y": "Y", "column": "Y", "col": "Y", "vertical": "Y", "v": "Y", "stacked": "Y"}


def _orientation(value) -> str | None:
    """'X' / 'Y' from the words people use (row / column, horizontal /
    vertical…), or None."""
    return _ORIENTATIONS.get(str(value).strip().lower())


_PLACEMENT_WORDS = {"top", "bottom", "left", "right", "center", "centre", "middle"}


def _placement_error(placement) -> str | None:
    """Why *placement* is not a corner/side/centre ('top left', 'bottom-right',
    'center'…), or None."""
    words = [w for w in re.split(r"[\s\-_]+", str(placement).strip().lower()) if w]
    if words and len(words) <= 2 and set(words) <= _PLACEMENT_WORDS:
        return None
    return (f"placement must be a corner or side such as 'top left', 'top right', "
            f"'bottom left', 'bottom right' or 'center', not {placement!r}")


def _corner_error(placement) -> str | None:
    """Why *placement* is not one of the four corners ('bottom right',
    'top-left'…), or None — scale bars only go in a corner."""
    words = {w for w in re.split(r"[\s\-_]+", str(placement).strip().lower()) if w}
    if len(words) == 2 and words & {"top", "bottom"} and words & {"left", "right"}:
        return None
    return (f"placement must be a corner: 'top left', 'top right', 'bottom left' or "
            f"'bottom right', not {placement!r}")


_PIL_CHECKED = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp")


def _unreadable_image(filename: str) -> str | None:
    """Why a local image file cannot be used, or None. Only cheap checks:
    missing, a folder, empty, or a PNG/JPEG/BMP/GIF/WebP/TIFF whose header is
    not an image (a text file renamed .png); other formats are left to their
    readers."""
    name = str(filename)
    if filename is None or not name.strip():
        return "the filename is empty: give the path of the image file"
    from batoolset.ome_zarr import is_zarr_path
    if is_zarr_path(name):                # OME-Zarr: a folder or URL, read by its own reader
        return _unreadable_zarr(name)
    from batoolset import omero_web as O
    if O.is_omero_url(name):
        return _unreadable_omero(name)
    if name.lower().startswith(("http://", "https://", "omero:")) \
            or "#" in os.path.basename(name).split(".")[-1] or name in ("None", "@template@"):
        return None
    if os.path.isdir(name):
        return f"{name} is a folder, not an image (create_figure_from_folder takes a folder)"
    if not os.path.isfile(name):
        # a file not there (yet) is allowed — a layout made before the data,
        # files on another computer — but said (_missing_image_note)
        return None
    if os.path.getsize(name) == 0:
        return f"{name} is empty (0 bytes)"
    ext = os.path.splitext(name)[1].lower()
    try:
        if ext in _PIL_CHECKED:
            from PIL import Image
            with Image.open(name) as im:
                im.verify()
        elif ext in (".tif", ".tiff"):
            import tifffile
            with tifffile.TiffFile(name) as t:
                if not t.pages:
                    return f"{name} holds no image"
    except Exception as e:
        return f"{name} cannot be read as an image ({type(e).__name__}: {e})"
    return None


def _unreadable_zarr(name: str) -> str | None:
    """Why an OME-Zarr path (local or URL, optionally ``#level=N``) cannot be
    used, or None. Reads its metadata only (a plain, non-OME local store is
    tried with the generic reader). A local store not there (yet) is allowed,
    as for files."""
    import re
    from batoolset import ome_zarr as Z
    store, _, frag = name.partition("#")
    level = None
    if frag:
        m = re.fullmatch(r"level=(\d+)", frag.strip())
        if not m:
            return (f"after an OME-Zarr path only '#level=N' can follow (N = a pyramid level, "
                    f"see inspect_ome_zarr); got '#{frag}'")
        level = int(m.group(1))
    if not Z.is_url(store) and not os.path.exists(store):
        return None
    try:
        info = Z.describe(store)
    except ImportError:
        return None                          # no zarr package: said when it is read
    except Exception as e:
        if Z.is_url(store):
            return f"cannot read the OME-Zarr image {store} ({type(e).__name__}: {e})"
        if level is None:
            try:
                from batoolset.img import Img
                Img(store)                   # a plain zarr store (not OME)
                return None
            except Exception:
                pass
        return f"{store} is not a readable OME-Zarr image ({type(e).__name__}: {e})"
    n = len(info.get("levels") or [])
    if level is not None and not 0 <= level < n:
        return f"level {level} out of range: {os.path.basename(store.rstrip('/'))} has {n} level(s), 0..{n - 1}"
    return None


def _unreadable_omero(url: str) -> str | None:
    """Why an OMERO.web image link cannot be used, or None: server not
    reachable, no such image, planes it does not have (metadata only). A
    server asking for a login is allowed: the GUI asks for it when the figure
    is opened (or OMERO_USERNAME / OMERO_PASSWORD for the MCP server)."""
    from batoolset import omero_web as O
    try:
        O.describe(url)
    except O.OmeroLoginRequired:
        return None
    except Exception as e:
        reason = str(e) if isinstance(e, (ValueError, FileNotFoundError)) else f"{type(e).__name__}: {e}"
        return f"cannot use the OMERO image {url}: {reason}"
    return None


def _missing_image_note(filename: str) -> str:
    """A warning line when *filename* does not exist (yet): the panel stays
    empty until it does, or until remap_paths points it to the file."""
    from pyfigures.path_resolution import source_exists
    name = str(filename)
    if name in ("None", "@template@") or name.lower().startswith("omero:") or source_exists(name):
        return ""
    return (f"\nWARNING: {name} does not exist (yet): the panel stays empty until it does — "
            f"or point the figure at the file with remap_paths / set_image_filename.")


def _new_image2d(filename: str) -> ET.Element:
    """Create an Image2D element matching the current PyFigures schema.

    Field set is derived from real GUI-saved .pyf files to ensure
    round-trip compatibility.  All positioning fields (x, y, width, height,
    scale) are left at 0 / 1.0 — PyFigures recomputes them on first render.
    """
    img = ET.Element("Image2D")
    for tag, val in [
        # ── identity / positioning ────────────────────────────────────────
        ("filename",        _encode_str(filename)),
        # ── image options ─────────────────────────────────────────────────
        ("projection",              "None"),
        ("projection_z_start",      "None"),   # Z-stack range (new field)
        ("projection_z_end",        "None"),
        ("normalization",           "None"),
        ("isText",                  "False"),
        ("channels",                _encode_str("None")),
        ("LUTs",                    "None"),
        ("dimensions",              "None"),
        # ── publication settings (new fields) ────────────────────────────
        ("publication_style",           "True"),
        ("publication_font_size",       "12"),
        ("publication_line_width",      "0.65"),
        ("publication_font",            _encode_str("Arial")),
        ("publication_svg_stroke_width","0.65"),
        ("_raw_svg_bytes",              "None"),
        # ── misc ──────────────────────────────────────────────────────────
        ("px_to_unit_conversion_factor", "0"),
        ("user_comments",   _encode_str("")),
        ("custom_loading_script", "None"),
        ("serie_to_open",   "None"),           # multi-series (LIF, CZI)
        ("crop_left",       "0"),
        ("crop_right",      "0"),
        ("crop_top",        "0"),
        ("crop_bottom",     "0"),
        ("line_style",      "None"),
        ("placement",       "top right"),
        ("fraction_of_parent_image_width_if_image_is_inset", "0.25"),
        ("border_size",     "None"),
        ("border_color",    "16777215"),
        ("lower_indices",   "None"),
        ("lower_values",    "None"),
        ("upper_indices",   "None"),
        ("upper_values",    "None"),
        ("color",           "16777215"),
        ("fill_color",      "None"),
        ("stroke",          "0.65"),
        ("opacity",         "1"),
        ("isSet",           "False"),
        ("scale",           "1.0"),
        ("theta",           "None"),           # must be None, not 0
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",       "False"),
        ("__init_called__", "True"),
        ("__version__",     "1.0"),
        # QPointF translation — required by newer batoolset deserialization
        ("translation",     "PyQt6.QtCore.QPointF()"),
    ]:
        ET.SubElement(img, tag).text = val
    # extra_user_translation: two empty <int/> elements (x, y offsets).
    # Older batoolset used <str>str</str> — that format causes load errors
    # in current versions.
    etu = ET.SubElement(img, "extra_user_translation")
    ET.SubElement(etu, "int")
    ET.SubElement(etu, "int")
    ET.SubElement(img, "annotations")
    return img


_PANEL_LETTER_RE = re.compile(r"^\(?[A-Za-z]{1,2}\)?\.?$")


def _looks_like_panel_letter(text: str) -> bool:
    """'A', 'b', '(c)', 'AA', 'D.' are panel letters; 'Merge', 'WT', 'GFP' are
    descriptive labels. (Two-letter all-caps like 'WT' are treated as letters
    only when they are a doubled letter such as 'AA'.)"""
    t = _strip_tags(text or "").strip()
    if not _PANEL_LETTER_RE.match(t):
        return False
    core = t.strip("().")
    return len(core) == 1 or (len(core) == 2 and core[0].lower() == core[1].lower())


def _corner_brightness(img: ET.Element, placement: str) -> float | None:
    """corner_brightness() for a panel element of a .pyf file."""
    import ast
    script = _child_text(img, "custom_loading_script")
    if isinstance(script, str) and script not in ("", "None"):
        return script_corner_brightness(script, placement)
    fn = _child_text(img, "filename")
    if not isinstance(fn, str) or fn.startswith("["):
        return None                         # channel merge: fluorescence-like
    if fn.lower().endswith((".svg", ".pdf")):
        return 1.0                          # equation / diagram on white, as the GUI judges it
    luts = _child_text(img, "LUTs")
    if isinstance(luts, str) and luts not in ("", "None", "[]"):
        try:
            luts = ast.literal_eval(luts)
        except Exception:
            pass

    def _crop(name):
        try:
            return max(0, int(float(_child_text(img, name) or 0)))
        except (TypeError, ValueError):
            return 0

    crop = tuple(_crop(n) for n in ("crop_left", "crop_right", "crop_top", "crop_bottom"))
    return corner_brightness(_first_filename(img), placement, crop, luts)


def corner_brightness(path, placement: str = "top left", crop=(0, 0, 0, 0),
                      luts=None) -> float | None:
    """Mean brightness (0 dark … 1 bright) of the displayed corner of image
    file *path* where a label at *placement* goes (the outer ~20 % x 15 % of
    the area left by *crop* = (left, right, top, bottom) pixels), or None when
    the pixels cannot be read cheaply (stacks with a coloured LUT, URLs,
    vector files). Shared by the MCP tools and the GUI lettering."""
    if not isinstance(path, str) or not os.path.isfile(path) \
            or path.lower().endswith((".svg", ".pdf")):
        return None
    peak = 1.0
    if luts and luts not in ("None", "[]") and not (
            isinstance(luts, (list, tuple)) and all(str(l).lower() in ("gray", "grey", "none") for l in luts)):
        # a coloured LUT keeps black black and makes white its own colour:
        # judge the raw corner, dimmed by how light that colour is (it used
        # to give up here, and the figure's black letter vanished on the
        # dark corner of a green image)
        peak = _lut_peak_luminance(luts)
        if peak is None:
            return None
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return None
    key = (os.path.abspath(path), stamp, str(placement).lower(), tuple(int(c or 0) for c in crop))
    if key not in _CORNER_CACHE:            # the GUI re-letters on every refresh
        if len(_CORNER_CACHE) > 512:
            _CORNER_CACHE.clear()
        _CORNER_CACHE[key] = _read_corner_brightness(path, str(placement).lower(), key[3])
    raw = _CORNER_CACHE[key]
    return None if raw is None else raw * peak


_CORNER_CACHE: dict = {}


def _lut_peak_luminance(luts) -> float | None:
    """Relative luminance (0…1) of the brightest colour of the LUT(s) shown —
    the lightest of several channels — or None when a name is unknown."""
    names = [luts] if isinstance(luts, str) else [l for l in (luts or []) if l]
    names = [str(n) for n in names if str(n).lower() not in ("none", "gray", "grey")] or ["GRAY"]
    best = 0.0
    for name in names:
        try:
            if name.upper() in ("GRAY", "GREY"):
                rgb = (1.0, 1.0, 1.0)
            elif name.startswith("MATPLOTLIB_"):
                import matplotlib
                rgb = matplotlib.colormaps[name[len("MATPLOTLIB_"):]](1.0)[:3]
            else:
                from batoolset.luts.lut_minimal_test import PaletteCreator, list_available_luts
                table = PaletteCreator().create3(list_available_luts()[name])
                rgb = [v / 255.0 for v in table[-1][:3]]
        except Exception:
            return None
        best = max(best, 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2])
    return best


def script_corner_brightness(script, placement: str = "top left") -> float | None:
    """corner_brightness() for a scripted panel, from what its script draws:
    charts and colour bars sit on white, channel merges on black, kymographs
    and orthogonal views look like the stack they come from. None when the
    script is not one PyFigures writes."""
    import ast
    import re
    if not isinstance(script, str):
        return None
    if "from staplot import api" in script or "ColorbarBase(" in script:
        return 1.0
    if "# pyfigures:channel_merge" in script:
        return 0.0                         # coloured channels added on black
    if "# pyfigures:kymograph" in script or "# pyfigures:orthogonal_views" in script:
        def value(name):
            m = re.search(rf"^{name} = (.+)$", script, flags=re.M)
            try:
                return ast.literal_eval(m.group(1)) if m else None
            except (ValueError, SyntaxError):
                return None
        path = value("_path")
        if not isinstance(path, str):
            return None
        line = value("_line")
        if "# pyfigures:kymograph" in script and isinstance(line, tuple) and len(line) == 4:
            # time runs down, the line across: a left corner is the start of
            # the line, a right one its end (the stack's corner is elsewhere)
            return _line_end_brightness(path, line, "right" in str(placement).lower())
        return corner_brightness(path, placement)
    return None


def _line_end_brightness(path, line, at_end: bool) -> float | None:
    """Brightness (0…1, displayed as corner_brightness judges it) of the first
    or last fifth of a line drawn on the first plane of *path*."""
    import numpy as np
    try:
        if path.lower().endswith((".tif", ".tiff")):
            import tifffile as _tf
            with _tf.TiffFile(path) as t:
                arr = t.pages[0].asarray()
        else:
            from PIL import Image as _PI
            with _PI.open(path) as im:
                arr = np.asarray(im.convert("L"))
    except Exception:
        return None
    arr = np.asarray(arr, dtype=np.float64)
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        arr = arr[..., :3].mean(axis=-1)
    if arr.ndim != 2:
        return None
    x1, y1, x2, y2 = (float(v) for v in line)
    t = np.linspace(0.8, 1.0, 20) if at_end else np.linspace(0.0, 0.2, 20)
    xs = np.clip(np.round(x1 + (x2 - x1) * t).astype(int), 0, arr.shape[1] - 1)
    ys = np.clip(np.round(y1 + (y2 - y1) * t).astype(int), 0, arr.shape[0] - 1)
    lo, hi = np.percentile(arr, (1, 99)) if arr.max() > 255 else (0.0, 255.0)
    if hi <= lo:
        return 0.0
    return float(np.clip((arr[ys, xs].mean() - lo) / (hi - lo), 0, 1))


def _read_corner_brightness(path, placement, crop):
    import numpy as np
    try:
        if path.lower().endswith((".tif", ".tiff")):
            import tifffile as _tf
            with _tf.TiffFile(path) as t:
                arr = t.pages[0].asarray()
        else:
            from PIL import Image as _PI
            with _PI.open(path) as im:
                arr = np.asarray(im.convert("RGB") if im.mode not in ("L", "I;16", "I", "F") else im)
    except Exception:
        return None
    arr = np.asarray(arr, dtype=np.float64)
    if arr.ndim == 3 and arr.shape[-1] in (3, 4):
        arr = arr[..., :3].mean(axis=-1)
    if arr.ndim != 2 or arr.size == 0:
        return None
    h, w = arr.shape
    left, right, top, bottom = (max(0, int(c or 0)) for c in crop)
    view = arr[top:h - bottom if bottom else h, left:w - right if right else w]
    if view.size == 0:
        view = arr
    if arr.max() > 255:
        lo, hi = np.percentile(view, (1, 99))   # 16-bit: displayed with auto contrast
    else:
        lo, hi = 0.0, 255.0
    vh, vw = view.shape
    ch, cw = max(1, int(vh * 0.15)), max(1, int(vw * 0.2))
    rows = slice(0, ch) if "top" in placement else (slice(vh - ch, vh) if "bottom" in placement
                                                    else slice((vh - ch) // 2, (vh + ch) // 2))
    cols = slice(0, cw) if "left" in placement else (slice(vw - cw, vw) if "right" in placement
                                                     else slice((vw - cw) // 2, (vw + cw) // 2))
    corner = view[rows, cols]
    if hi <= lo:
        return 0.0
    return float(np.clip((corner.mean() - lo) / (hi - lo), 0, 1))


def letter_colours(brightness: list) -> list:
    """Colours (0xRRGGBB) of panel letters without a box whose corners have
    these *brightness* values (0 dark … 1 bright, None unknown). One colour for
    the whole figure — white when most corners are dark, black when most are
    bright — switched only on a panel where it would vanish (a first letter
    came out black and the others white). Unknown corners take the figure
    colour; all unknown: white. Shared by the GUI and the MCP server."""
    known = [b for b in brightness if b is not None]
    dark = sum(1 for b in known if b < 0.5)
    base = 0xFFFFFF if dark * 2 >= len(known) else 0x000000
    out = []
    for b in brightness:
        if b is not None and base == 0xFFFFFF and b > 0.6:
            out.append(0x000000)
        elif b is not None and base == 0x000000 and b < 0.4:
            out.append(0xFFFFFF)
        else:
            out.append(base)
    return out


def _label_color_for(img: ET.Element, text: str, placement: str = "top left") -> int | None:
    """Default colour of a plain-text label on *img*: white on a dark corner
    (fluorescence: the black default was nearly invisible), black on a bright
    one (bright field, white backgrounds), white when the pixels cannot be
    read; the default (black) on a plot / scripted panel; None for HTML text
    that sets its own colour. HTML without a colour ("<b>A</b>") follows the
    same rule: it came out black, invisible on fluorescence."""
    if re.search(r"<\s*/?\s*[A-Za-z][^>]*>", text or "") and re.search(r"colou?r\s*[:=]", text, re.I):
        return None
    bright = _corner_brightness(img, placement or "top left")
    script = _child_text(img, "custom_loading_script")
    if isinstance(script, str) and script not in ("", "None") and bright is None:
        return None                 # a script PyFigures did not write: the default
    if bright is not None and bright > 0.6:
        return 0x000000
    return 0xFFFFFF


def _label_plain_text(text) -> str:
    """The visible text of a (possibly HTML) label."""
    import html
    t = re.sub(r"<style\b[^>]*>.*?</style>", "", str(text or ""), flags=re.S | re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", t)).strip().strip('"').strip()


def _same_labels(annots: ET.Element, text: str, placement: str) -> list:
    """Text labels already at *placement* that show the same text as *text*:
    adding a re-styled copy replaces them (a second, white "A" was drawn over
    the first, black one)."""
    plain = _label_plain_text(text)
    if not plain:
        return []
    out = []
    for ta in annots.findall("TAText2D"):
        where = str(_child_text(ta, "placement") or "").strip('"').lower()
        if where == str(placement).lower() and _label_plain_text(_child_text(ta, "text")) == plain:
            out.append(ta)
    return out


def _new_tatext2d(text: str, placement: str = "top left",
                  is_letter: bool | None = None,
                  color: int | None = None) -> ET.Element:
    """Create a TAText2D annotation element.

    *is_letter*: None = decide from the text. Only real panel letters may be
    flagged: the GUI's auto-lettering renames every is_letter annotation to
    A, B, C…, which silently replaced descriptive labels such as "Merge".
    *color*: 0xRRGGBB text colour, None = PyFigures default (black). Applied
    through the label's rich text — TAText2D's ``color`` field is not the
    glyph colour."""
    if is_letter is None:
        is_letter = _looks_like_panel_letter(text)
    if color is not None:
        text = f'<font color=#{int(color) & 0xFFFFFF:06x}>{text}</font>'
    ta = ET.Element("TAText2D")
    for tag, val in [
        ("text",            _encode_str(text)),
        ("color",           "None"),
        ("fill_color",      "None"),
        ("stroke",          "0.65"),
        ("opacity",         "1.0"),
        ("isSet",           "False"),
        ("scale",           "1"),
        ("line_style",      "None"),
        ("theta",           "0"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",       "True"),
        ("__init_called__", "True"),
        ("__version__",     "1.0"),
        ("placement",       placement),
        ("text_orientation", _encode_str("X")),
        ("range",           "None"),
        ("_TAText2D__version", "1.0"),
        ("is_letter",       "True" if is_letter else "False"),
    ]:
        ET.SubElement(ta, tag).text = val
    return ta


def _new_group_elem(orientation: str = "X", space: int = 3, group_id: int = 1) -> ET.Element:
    """Create a new empty Group element."""
    grp = ET.Element("Group")
    ET.SubElement(grp, "content")
    for tag, val in [
        ("space",       str(space)),
        ("orientation", _encode_str(orientation)),
        ("size",        "512.0"),
        ("ID",          str(group_id)),
        ("fill_color",  "None"),
        ("immutable",   "False"),
        ("isText",      "False"),
    ]:
        ET.SubElement(grp, tag).text = val
    return grp


def _next_group_id(root: ET.Element) -> int:
    """Return one more than the highest existing group ID (or 1 if none)."""
    ids: set[int] = set()
    for grp in _all_groups(root):
        id_el = grp.find("ID")
        if id_el is not None and id_el.text:
            try:
                ids.add(int(id_el.text))
            except ValueError:
                pass
    return max(ids, default=0) + 1


def _navigate_group(root: ET.Element, group_path: list[int]) -> tuple[ET.Element | None, str]:
    """Navigate to a Group element by path.

    [0]    → first top-level Group.
    [0, 1] → second sub-Group inside first top-level Group.
    Returns (element, ""). On failure returns (None, error_message).
    """
    if not group_path:
        return None, "group_path must not be empty"
    if any(int(i) < 0 for i in group_path):
        # Python would count -1 from the end: a group the caller did not name
        return None, f"group_path {list(group_path)} has a negative index; indices start at 0"
    tops = _top_groups(root)
    if group_path[0] >= len(tops):
        return None, f"top-level group index {group_path[0]} out of range ({len(tops)} groups)"
    current = tops[group_path[0]]
    for depth, sub_idx in enumerate(group_path[1:], start=1):
        content = current.find("content")
        if content is None:
            return None, f"group at depth {depth - 1} has no <content>"
        sub_groups = [c for c in content if c.tag == "Group"]
        if sub_idx >= len(sub_groups):
            return None, (
                f"sub-group index {sub_idx} out of range at depth {depth} "
                f"({len(sub_groups)} sub-groups)"
            )
        current = sub_groups[sub_idx]
    return current, ""


def _get_container(
    root: ET.Element,
    group_path: list[int],
    refuse_label_rows: bool = False,
) -> tuple[ET.Element | None, str]:
    """Return the direct parent element of Image2D items.

    []     → root itself (free-canvas mode: images are direct children of <list>).
    [i]    → <content> element of top-level group i.
    [i, j] → <content> element of sub-group j inside group i.

    When *refuse_label_rows* is True (used by all image-writing tools) an error
    is returned if the resolved group is a label-row group (isText != False).
    Label-row groups only hold text cells; adding image panels to them is illegal
    and will crash PyFigures.

    Returns (element, ""). On failure returns (None, error_message).
    """
    if not group_path:
        return root, ""          # free-canvas: images live directly under <list>
    grp, err = _navigate_group(root, group_path)
    if err:
        return None, err
    if refuse_label_rows and _is_label_row_group(grp):
        tops = _top_groups(root)
        content_paths = [
            f"[{i}]" for i, g in enumerate(tops)
            if not _is_label_row_group(g)
        ]
        return None, (
            f"group {group_path} is a label-row group (isText != False) — "
            "it only holds text cells and cannot contain image panels. "
            f"Content groups in this figure: {', '.join(content_paths) or 'none'}. "
            "Call describe_figure() to identify the correct group_path."
        )
    content = grp.find("content")
    if content is None:
        content = ET.SubElement(grp, "content")
    return content, ""


def _append_image(container: ET.Element, img: ET.Element, is_root: bool = False):
    """Append *img* to *container*.

    When *container* is the root <list> element (free-canvas mode), the image
    is inserted before the metadata trailer elements so the order stays clean:
    Image2D* → SerializableQFont → SerializableGUIparameters.
    """
    if is_root:
        _METADATA_TAGS = {"SerializableQFont", "SerializableGUIparameters"}
        insert_pos = len(list(container))
        for i, child in enumerate(container):
            if child.tag in _METADATA_TAGS:
                insert_pos = i
                break
        container.insert(insert_pos, img)
    else:
        container.append(img)


# ---------------------------------------------------------------------------
# Additional MCP Tools
# ---------------------------------------------------------------------------

_ROI_PROTECTED = {"ScaleBar", "Image2D"}  # never removed by remove_annotation


def _roi_children(annots: ET.Element) -> list[ET.Element]:
    """All annotation children that can be listed/removed (excludes ScaleBar + insets)."""
    return [c for c in annots if c.tag not in _ROI_PROTECTED]


def _describe_roi(el: ET.Element, idx: int) -> dict:
    """Return a concise dict description of any annotation element."""
    t = el.tag
    base = {"annotation_index": idx, "type": t}
    if t == "TAText2D":
        raw = _child_text(el, "text") or ""
        base["text"] = _html_to_plain(raw)
        base["placement"] = _child_text(el, "placement") or ""
    elif t in ("Rectangle2D", "Ellipse2D"):
        for k in ("x", "y", "width", "height"):
            v = _child_text(el, k)
            base[k] = float(v) if v is not None else None
        base["color"] = _child_text(el, "color")
        base["fill_color"] = _child_text(el, "fill_color")
    elif t == "Line2D":
        for k in ("x1", "y1", "x2", "y2"):
            v = _child_text(el, k)
            base[k] = float(v) if v is not None else None
        base["arrow"] = _child_text(el, "arrow")
        base["color"] = _child_text(el, "color")
        # 'line', 'arrow' or 'arrowhead' (a head alone: its line is too short to show)
        from ..arrowheads import is_head_only
        arrow = str(base["arrow"]) == "True"
        both = str(_child_text(el, "arrow_at_both_ends")) == "True"
        if None not in (base["x1"], base["y1"], base["x2"], base["y2"]) and \
                is_head_only(base["x1"], base["y1"], base["x2"], base["y2"], arrow):
            base["kind"] = "arrowhead"
        else:
            base["kind"] = ("double arrow" if both else "arrow") if arrow else "line"
    elif t in ("Polygon2D", "PolyLine2D", "Freehand2D"):
        raw = _child_text(el, "coords_as_list") or "[]"
        try:
            import ast as _ast
            flat = _ast.literal_eval(raw)
            pts = [[flat[i], flat[i + 1]] for i in range(0, len(flat) - 1, 2)]
        except Exception:
            pts = []
        base["points"] = pts
        base["color"] = _child_text(el, "color")
    elif t == "ScaleBar":
        base["type"] = "scale_bar (protected)"
    elif t == "Image2D":
        base["type"] = "inset (protected)"
    if t in ("Rectangle2D", "Ellipse2D", "Line2D", "Polygon2D", "PolyLine2D", "Freehand2D"):
        for k in ("stroke", "opacity"):
            v = _child_text(el, k)
            try:
                base[k] = float(v) if v not in (None, "None") else None
            except ValueError:
                base[k] = None
        fill = _child_text(el, "fill_color")
        base["fill_color"] = None if fill in (None, "None") else fill
        style = _child_text(el, "line_style")
        base["line_style"] = {"[4, 4]": "dashed", "[1, 3]": "dotted",
                              "[6, 3, 1, 3]": "dash-dot"}.get(str(style), "solid" if style in (None, "None") else str(style))
    return base


# ---------------------------------------------------------------------------
# Journal presets  (width in mm per column format)
# ---------------------------------------------------------------------------
# Only sizes the journal's own page states (pages read in October 2026, saved in
# chatGPT_validation/2026-10-15/manuscript_verification_2026-10-16/guidelines):
# a journal offers just the columns its page gives — "triple" for journals
# laid out in three columns (Science). Publisher-wide presets (Elsevier,
# Springer, Wiley) and eLife (its page gives upload minimums, not column
# widths) were removed: import such a journal's page instead
# (pyfigures/journal_styles.py, QC → Journal styles…).
_COLUMN_ORDER = ("single", "1.5", "double", "triple")
_JOURNAL_PRESETS: dict[str, dict[str, float]] = {
    "nature":    {"single": 89,  "1.5": 136, "double": 183},
    "nature communications": {"single": 88, "double": 180},
    "nature methods": {"double": 180},
    "science":   {"single": 57,  "double": 121, "triple": 184},
    "cell":      {"single": 85,  "1.5": 114, "double": 174},
    "plos":      {"single": 132, "double": 190.5},
    "embo":      {"single": 87,  "double": 180},
    "jcb":       {"single": 85,  "double": 175},
    "pnas":      {"single": 87,  "1.5": 114, "double": 178},
}
_JOURNAL_SOURCES: dict[str, dict[str, str]] = {
    "nature": {"url": "https://www.nature.com/nature/for-authors/final-submission",
               "says": "89 mm wide (single column) and 183 mm wide (double column); a "
                       "column-and-a-half where necessary (120–136 mm)"},
    "nature communications": {"url": "https://www.nature.com/ncomms/submit/how-to-submit",
                              "says": "single column 88 mm, double column 180 mm"},
    "nature methods": {"url": "https://www.nature.com/nmeth/submission-guidelines/aip-and-formatting",
                       "says": "figure panels saved at a maximum width of 180 mm (no column "
                               "widths given; same rule for Nature Medicine and Nature Cell Biology)"},
    "science": {"url": "https://www.science.org/content/page/instructions-preparing-initial-manuscript",
                "says": "5.7 cm (1 column), 12.1 cm (2 columns) or 18.4 cm (3 columns)"},
    "cell": {"url": "https://www.cell.com/information-for-authors/figure-guidelines",
             "says": "two-column formats: 8.5 cm (1 column), 11.4 cm (1.5 columns), 17.4 cm "
                     "(full width); three-column formats: 5.5 / 11.4 / 17.4 cm"},
    "plos": {"url": "https://journals.plos.org/plosone/s/figures",
             "says": "full page width 190.5 mm, text column 132 mm (figures 66.8–190.5 mm)"},
    "embo": {"url": "https://www.embopress.org/page/journal/14602075/authorguide",
             "says": "final size between 87 mm and 180 mm wide"},
    "jcb": {"url": "https://rupress.org/jcb/pages/fig-vid-guidelines",
            "says": "preferred single width 85 mm; maximum 175 mm (7 in)"},
    "pnas": {"url": "https://www.pnas.org/pb-assets/authors/digitalart.pdf",
             "says": "1 column 8.7 cm, 1.5 columns 11.4 cm, 2 columns 17.8 cm (page 2)"},
}

# Normalise aliases (titles whose page gives the same sizes)
_JOURNAL_ALIASES = {
    "ncomms": "nature communications",
    "nature cell biology": "nature methods",
    "nature medicine": "nature methods",
    "cell reports": "cell",
    "current biology": "cell",
    "developmental cell": "cell",
    "plos biology": "plos",
    "plos genetics": "plos",
    "plos one": "plos",
    "embo journal": "embo",
    "the embo journal": "embo",
    "journal of cell biology": "jcb",
}

_COLUMN_WORDS = {
    "single": "single", "1": "single", "one": "single", "1 column": "single",
    "one column": "single", "single column": "single",
    "1.5": "1.5", "1.5 column": "1.5", "one and a half": "1.5", "intermediate": "1.5",
    "column and a half": "1.5",
    "half": "half", "half page": "half", "half width": "half", "half page width": "half",
    "double": "double", "2": "double", "two": "double", "2 column": "double",
    "two column": "double", "double column": "double",
    "triple": "triple", "3": "triple", "three": "triple", "3 column": "triple",
    "three column": "triple", "triple column": "triple",
}


def _column_key(column, available) -> str:
    """'single' | '1.5' | 'double' | 'triple' for the words people use
    ('2 columns', 'three', 'full width' = the widest the journal has)."""
    c = " ".join(str(column).lower().replace("-", " ").split())
    c = c[:-1] if c.endswith("s") else c
    if c in ("full", "full width", "full page", "full page width", "widest"):
        return [k for k in _COLUMN_ORDER if k in available][-1]
    key = _COLUMN_WORDS.get(c)
    if key is None:
        raise ValueError(f"Unknown column {column!r}. Use one of: "
                         + ", ".join(k for k in _COLUMN_ORDER if k in available) + ".")
    return key


def _journal_columns_text(key) -> str:
    return ", ".join(f"{c} {_JOURNAL_PRESETS[key][c]:g} mm"
                     for c in _COLUMN_ORDER if c in _JOURNAL_PRESETS[key])


# A journal whose page gives only a full width (Nature Methods: "maximum width
# of 180 mm") still prints half-page figures. Their width is not on the page,
# so it is estimated as two columns side by side with a 5 mm gap (Nature's own
# pages: 89 mm single = (183 - 5) / 2) and always reported as an estimate.
_HALF_PAGE_GAP_MM = 5.0
HALF_PAGE_NOTE = "estimated, not on the journal's page: (full width - 5 mm gap) / 2"


def estimated_half_page_mm(full_mm: float) -> float:
    return round((float(full_mm) - _HALF_PAGE_GAP_MM) / 2.0, 1)


def _half_page(journal, widths: dict) -> tuple[float, str]:
    """(estimated mm, note) for column='half' — only when *widths* has a full
    width and no single column; otherwise say which real column to use."""
    if "single" in widths:
        raise ValueError(f"{journal!r} gives its own column sizes "
                         f"({', '.join(f'{c} {widths[c]:g} mm' for c in widths)}); "
                         "use one of them instead of an estimated half page.")
    full = max(widths.values())
    return estimated_half_page_mm(full), HALF_PAGE_NOTE


def _journal_width(journal: str, column: str) -> tuple[float, str]:
    """(target width in mm, note) for a journal + column. The note is empty for
    a size the journal's page states, and says so when it is an estimate
    (column='half page' on a journal that gives only a full width)."""
    j = journal.lower().strip()
    j = _JOURNAL_ALIASES.get(j, j)
    presets = None if j.startswith("custom:") else _JOURNAL_PRESETS.get(j)
    if presets is None:
        from ..journal_styles import find_style, width_mm, list_styles
        style = find_style(journal)
        if style is not None:
            mm, rule = width_mm(style, column)
            return float(mm), (HALF_PAGE_NOTE if rule == "half (estimated)" else "")
        saved = [s["use_as"] for s in list_styles()]
        raise ValueError(
            f"Unknown journal {journal!r}. "
            f"Built-in journals: {', '.join(sorted(_JOURNAL_PRESETS))}"
            + (f"; saved journal styles: {', '.join(saved)}" if saved else "")
            + ". To add it, copy the figure-guidelines part of the journal's web page and "
              "import it (GUI: QC → Journal styles…; MCP: prepare_journal_style_import "
              "then save_journal_style)."
        )
    col_key = _column_key(column, presets)
    if col_key == "half":
        return _half_page(journal, presets)
    if col_key not in presets:
        hint = ("; column='half page' gives an estimated half-page width"
                if "single" not in presets else "")
        raise ValueError(f"{journal!r} has no {col_key} column size; its page gives: "
                         f"{_journal_columns_text(j)}{hint}.")
    return presets[col_key], ""


# The maximum figure height a journal's page states (same pages as the widths;
# journals not listed give none: import their page to add one).
_JOURNAL_MAX_HEIGHT: dict[str, tuple[float, str]] = {
    "nature": (247, "The full depth of a Nature page is 247 mm"),
    "plos": (222.3, "Height maximum 22.23 cm: the figure occupies the whole page, caption "
                    "excluded"),
    "pnas": (225, "Recommended max height: 54 picas / 9” / 22.5 cm (digital art guidelines)"),
}


def _journal_max_height(journal: str | None) -> tuple[float, str] | None:
    """(max height mm, what the page says) for a built-in journal or a saved
    style with a height rule; None when the journal gives no maximum height."""
    if not journal:
        return None
    j = journal.lower().strip()
    j = _JOURNAL_ALIASES.get(j, j)
    if not j.startswith("custom:") and j in _JOURNAL_PRESETS:
        return _JOURNAL_MAX_HEIGHT.get(j)
    from ..journal_styles import find_style
    style = find_style(journal)
    if style is None:
        return None
    best = None
    for r in style["rules"]:
        if r["kind"] != "height" or r["unit"] != "mm" \
                or r["relation"] not in ("max", "recommended", "target", "range"):
            continue
        v = r["maximum"] if r["relation"] == "range" else r["value"]
        if best is None or v < best[0]:
            best = (float(v), f"rule '{r['label']}': {r['evidence_quote'] or r['applies_to']}")
    return best


def _height_choices(journal, width_mm: float, height_mm: float, max_mm: float) -> list:
    """What to do with a figure taller than the journal allows, for the user
    to choose: [(kind, column, width mm, text)] with kind 'shrink' (narrow
    until it fits), 'column' (the widest journal column it fits in, heights
    estimated as proportional to the width) and 'off' (keep the width)."""
    fit_w = width_mm * max_mm / height_mm
    out = [("shrink", None, fit_w,
            f"fit_height='shrink' narrows it to about {fit_w:.0f}mm (between column sizes)")]
    cols = {}
    if journal:
        from ..journal_styles import journal_info
        try:
            cols = journal_info(journal).get("columns_mm") or {}
        except Exception:
            cols = {}
    fitting = [(mm, c) for c, mm in cols.items() if mm < width_mm - 0.5 and mm <= fit_w + 0.5]
    if fitting:
        mm, c = max(fitting)
        out.append(("column", c, float(mm),
                    f"fit_height='column' uses the {c} column ({mm:g}mm, about "
                    f"{height_mm * mm / width_mm:.0f}mm tall)"))
    out.append(("off", None, width_mm,
                f"fit_height=false keeps {width_mm:.0f}mm ({height_mm:.0f}mm tall, over the "
                f"{max_mm:g}mm maximum)"))
    return out


def _figure_height_mm(pyf_path: str) -> float | None:
    """Height of the laid-out figure (all top-level groups) in mm, or None."""
    try:
        objs, Group, _Image2D = _load_objects_lazy(pyf_path)
        rects = [o.getRect(all=True) for o in objs if isinstance(o, Group)]
    except Exception:
        return None
    if not rects:
        return None
    top = min(r.top() for r in rects)
    bottom = max(r.bottom() for r in rects)
    return (bottom - top) / 72.0 * 25.4                   # canvas unit = 1 pt


def _width_mm_for_journal(journal: str, column: str) -> float:
    """Return the target width in mm for a journal + column-count combination.
    Built-in presets first; then journal styles saved from a journal's own
    guidelines (pyfigures/journal_styles.py; 'custom:<title>' reaches one whose
    title is also a built-in name). See _journal_width for the note saying
    whether the width is the journal's or an estimate."""
    return _journal_width(journal, column)[0]


# ---------------------------------------------------------------------------
# ROI helpers
# ---------------------------------------------------------------------------

def _flatten_points(points) -> list[float]:
    """Accept [[x,y],...] or [x,y,x,y,...] — return flat float list."""
    if not points:
        return []
    if isinstance(points[0], (list, tuple)):
        flat = []
        for p in points:
            flat.extend([float(p[0]), float(p[1])])
        return flat
    return [float(v) for v in points]


def _roi_fill_color_str(fill_color) -> str:
    if fill_color is None:
        return "None"
    return str(_color_to_int(fill_color))


def _new_roi_rect(
    x: float, y: float, w: float, h: float,
    color: int, fill_color, stroke: float, opacity: float,
) -> ET.Element:
    el = ET.Element("Rectangle2D")
    for tag, val in [
        ("x", str(float(x))), ("y", str(float(y))),
        ("width", str(float(w))), ("height", str(float(h))),
        ("color", str(color)), ("fill_color", _roi_fill_color_str(fill_color)),
        ("stroke", str(float(stroke))), ("opacity", str(float(opacity))),
        ("isSet", "False"), ("scale", "1"), ("line_style", "None"),
        ("theta", "0"), ("incompressible_width", "0"), ("incompressible_height", "0"),
        ("immutable", "False"), ("__init_called__", "True"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_roi_ellipse(
    x: float, y: float, w: float, h: float,
    color: int, fill_color, stroke: float, opacity: float,
) -> ET.Element:
    el = ET.Element("Ellipse2D")
    for tag, val in [
        ("x", str(float(x))), ("y", str(float(y))),
        ("width", str(float(w))), ("height", str(float(h))),
        ("color", str(color)), ("fill_color", _roi_fill_color_str(fill_color)),
        ("stroke", str(float(stroke))), ("opacity", str(float(opacity))),
        ("scale", "1"), ("line_style", "None"),
        ("theta", "0"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_roi_line(
    x1: float, y1: float, x2: float, y2: float,
    color: int, stroke: float, opacity: float,
    arrow: bool, arrow_at_both_ends: bool,
    head_width_scaler: float = 4, head_length_scaler: float = 12,
) -> ET.Element:
    """Line2D ROI. With *arrow* the head's point is exactly (x2, y2) (and
    (x1, y1) for a double arrow); its half-width / length are the stroke times
    *head_width_scaler* / *head_length_scaler*."""
    el = ET.Element("Line2D")
    for tag, val in [
        ("x1", str(float(x1))), ("y1", str(float(y1))),
        ("x2", str(float(x2))), ("y2", str(float(y2))),
        ("color", str(color)), ("stroke", str(float(stroke))),
        ("opacity", str(float(opacity))), ("scale", "1"),
        ("line_style", "None"), ("theta", "0"),
        ("arrow", str(arrow)), ("arrow_at_both_ends", str(arrow_at_both_ends)),
        ("arrowhead_width_scaler", repr(head_width_scaler)),
        ("arrowhead_height_scaler", repr(head_length_scaler)),
        ("fill_color", "None"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_roi_polygon(
    flat_coords: list[float],
    shape_tag: str,  # "Polygon2D" | "PolyLine2D" | "Freehand2D"
    color: int, fill_color, stroke: float, opacity: float,
) -> ET.Element:
    el = ET.Element(shape_tag)
    ET.SubElement(el, "coords_as_list").text = str(flat_coords)
    for tag, val in [
        ("isSet", "False"),
        ("color", str(color)), ("fill_color", _roi_fill_color_str(fill_color)),
        ("stroke", str(float(stroke))), ("opacity", str(float(opacity))),
        ("scale", "1"), ("line_style", "None"), ("theta", "0"), ("__version__", "1.0"),
    ]:
        ET.SubElement(el, tag).text = val
    return el


def _new_free_text(html: str, x: float, y: float) -> ET.Element:
    """A TAText2D placed at an absolute image-pixel (x, y) rather than snapped to
    a corner. placement='None' makes it 'free/relative' so it draws at its own
    coordinates (like a ROI line), which is what significance labels need."""
    ta = ET.Element("TAText2D")
    for tag, val in [
        ("x",               str(float(x))),
        ("y",               str(float(y))),
        ("text",            _encode_str(html)),
        ("color",           "None"),
        ("fill_color",      "None"),
        ("stroke",          "0.65"),
        ("opacity",         "1.0"),
        ("isSet",           "False"),
        ("scale",           "1"),
        ("line_style",      "None"),
        ("theta",           "0"),
        ("incompressible_width",  "0"),
        ("incompressible_height", "0"),
        ("immutable",       "True"),
        ("__init_called__", "True"),
        ("__version__",     "1.0"),
        ("placement",       "None"),
        ("text_orientation", _encode_str("X")),
        ("range",           "None"),
        ("_TAText2D__version", "1.0"),
        ("is_letter",       "False"),
    ]:
        ET.SubElement(ta, tag).text = val
    return ta


def _roi_outside_error(img, xs, ys) -> str:
    """Why a shape cannot be added when it lies entirely outside its image
    (drawings are cropped to the panel, so it would not show at all); '' when
    any part is inside or the image size is unknown. *xs*, *ys*: the shape's
    coordinates in raw pixels."""
    size = _raw_size_from_file(_first_filename(img)) if img is not None else None
    if not size or not xs or not ys:
        return ""
    w, h = size
    if max(xs) < 0 or max(ys) < 0 or min(xs) > w or min(ys) > h:
        return (f"the shape ({min(xs):g}..{max(xs):g}, {min(ys):g}..{max(ys):g}) is entirely "
                f"outside the {w}×{h} px image; drawings are cropped to the panel, so it would "
                f"not show. Coordinates are raw image pixels from the top-left corner.")
    return ""


def _get_annots_for_roi(root, group_path, image_index):
    """Return (tree, annots_el, err) for a ROI-add operation."""
    container, err = _get_container(root, group_path, refuse_label_rows=True)
    if err:
        return None, None, err
    imgs = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(imgs):
        return None, None, f"image_index {image_index} out of range ({len(imgs)} images)."
    img = imgs[image_index]
    annots = img.find("annotations")
    if annots is None:
        annots = ET.SubElement(img, "annotations")
    return img, annots, ""


# ---------------------------------------------------------------------------
# Figure caption / legend
# ---------------------------------------------------------------------------

def _caption_sidecar_path(pyf_path: str) -> str:
    """Caption store: a JSON sidecar beside the .pyf (same stem). Kept OUT of the
    .pyf XML on purpose — unknown fields break SerializableGUIparameters
    deserialization (resets the figure's real font/spacing on GUI load)."""
    return os.path.splitext(pyf_path)[0] + ".caption.json"


def _read_caption(pyf_path: str):
    p = _caption_sidecar_path(pyf_path)
    if not os.path.isfile(p):
        return None, None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("title"), d.get("caption")
    except Exception:
        return None, None


def _stats_sidecar_path(pyf_path: str) -> str:
    """Statistics-provenance store: a JSON sidecar beside the .pyf (same stem),
    kept OUT of the figure XML for the same reason as the caption sidecar. Holds
    one entry per data-driven test (data plots + significance brackets) so the
    adjustment ledger can report the exact tests and p-values used."""
    return os.path.splitext(pyf_path)[0] + ".stats.json"


def _read_stats(pyf_path: str) -> list:
    p = _stats_sidecar_path(pyf_path)
    if not os.path.isfile(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except Exception:
        return []


def _append_stats_entry(pyf_path: str, entry: dict):
    entries = _read_stats(pyf_path)
    entries.append(entry)
    _atomic_write_text(_stats_sidecar_path(pyf_path),
                       json.dumps(entries, ensure_ascii=False, indent=2))


def _clear_derived_sidecars(pyf_path: str) -> list[str]:
    """Remove the sidecars that describe a figure's CONTENT (statistics record,
    alt text) — used when a new figure replaces the file, so the Methods text
    and alt text never report panels of the previous figure. The caption
    (author prose) is kept. Returns the removed paths."""
    removed = []
    stem = os.path.splitext(pyf_path)[0]
    for p in (_stats_sidecar_path(pyf_path), stem + ".alttext.json", stem + ".target.json"):
        if os.path.isfile(p):
            os.remove(p)
            removed.append(p)
    return removed


def _auto_test_via_staplot(columns: dict):
    """Run staplot's auto_test on ``{group: [values]}`` and return its record,
    or None if staplot is unavailable. Soft dependency — never raises on import."""
    try:
        from staplot import api as _api
    except Exception:
        return None
    try:
        tbl = _api.table_from_columns(columns)
        return _api.auto_test(tbl)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------------------
# Journal-guidelines compliance: resolution, font size, and one-shot reformat
# ---------------------------------------------------------------------------

_MCP_QAPP = None  # module-level hold for the QApplication (must not be GC'd)


def _target_sidecar_path(pyf_path: str) -> str:
    """The figure's size target (journal + column, or a width) — what it was
    last sized for, so a later "is it ready for submission?" checks THAT target
    instead of a guess. A sidecar, like the caption: unknown fields in the .pyf
    XML break its GUI deserialization."""
    return os.path.splitext(pyf_path)[0] + ".target.json"


def _store_target(pyf_path: str, journal: str | None, column: str, width_mm: float,
                  max_height_mm: float | None = None) -> None:
    data = {"width_mm": round(float(width_mm), 3)}
    if journal:
        data.update(journal=journal, column=column)
    if max_height_mm:
        data["max_height_mm"] = float(max_height_mm)       # narrowed to fit this height
    try:
        _atomic_write_text(_target_sidecar_path(pyf_path), json.dumps(data, indent=2))
    except OSError:
        pass


def _stored_target(pyf_path: str) -> dict | None:
    try:
        with open(_target_sidecar_path(pyf_path), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data.get("width_mm") else None
    except (OSError, ValueError):
        return None


def _resolve_target_for(pyf_path, journal, column, width_mm, width_cm, width_in):
    """_resolve_target_mm, falling back on the figure's stored target when no
    target is given."""
    if journal is None and width_mm is None and width_cm is None and width_in is None:
        stored = _stored_target(pyf_path)
        if stored:
            if stored.get("journal"):
                mm, src = _resolve_target_mm(stored["journal"], stored.get("column", "single"),
                                             None, None, None)
                return mm, src + " (the figure's stored target)"
            return float(stored["width_mm"]), f"{stored['width_mm']}mm (the figure's stored target)"
    return _resolve_target_mm(journal, column, width_mm, width_cm, width_in)


def _resolve_target_mm(
    journal: str | None, column: str,
    width_mm: float | None, width_cm: float | None, width_in: float | None,
) -> tuple[float, str]:
    """Resolve a target physical figure width (mm) from journal preset or explicit
    units. Raises ValueError if nothing usable is given."""
    if journal is not None:
        mm, note = _journal_width(journal, column)
        return mm, f"{journal!r} {column}-column = {mm:g}mm" + (f" ({note})" if note else "")
    # a width of -5 mm 'passed' every resolution check (negative DPI)
    for name, v in (("width_mm", width_mm), ("width_cm", width_cm), ("width_in", width_in)):
        if v is not None and not (isinstance(v, (int, float)) and math.isfinite(v) and v > 0):
            raise ValueError(f"{name} must be a positive width (got {v!r}).")
    if width_mm is not None:
        return float(width_mm), f"{width_mm}mm"
    if width_cm is not None:
        return float(width_cm) * 10.0, f"{width_cm}cm"
    if width_in is not None:
        return float(width_in) * 25.4, f"{width_in}in"
    raise ValueError("specify a target width — one of: journal, width_mm, width_cm, width_in.")


def _ensure_qapp():
    """The QApplication of in-process tools, created once and kept: a
    QApplication that is garbage-collected crashes (0xC0000409), and Qt's
    teardown at interpreter exit can crash too (pyfigures.qt_exit)."""
    from qtpy.QtWidgets import QApplication as _QApp
    global _MCP_QAPP
    if _QApp.instance() is None:
        from pyfigures.offscreen import ensure_offscreen_fonts
        ensure_offscreen_fonts()     # offscreen on Windows has no fonts otherwise
    _MCP_QAPP = _QApp.instance() or _QApp(sys.argv[:1])
    from pyfigures.qt_exit import skip_qt_teardown
    skip_qt_teardown()
    return _MCP_QAPP


def _load_objects_lazy(pyf_path: str):
    """Deserialize a .pyf into PyFigures objects without loading pixel data.
    Returns (objects_list, Group_cls, Image2D_cls). Raises on import/parse error."""
    from batoolset.settings.global_settings import set_UI as _set_UI
    _set_UI()
    _ensure_qapp()
    from batoolset.drawings.shapes.image2d import Image2D as _Image2D
    from batoolset.drawings.shapes.group import Group as _Group
    from batoolset.serializations.tools import (
        deserialize_to_dict as _d2d, create_object as _co,
    )
    from ..path_resolution import resolve_moved_paths
    xml_content, _ = resolve_moved_paths(Path(pyf_path).read_text(encoding="utf-8"), pyf_path)
    _Image2D._lazy_mode = True
    try:
        objects = _co(list.__name__, _d2d(xml_content))
    finally:
        _Image2D._lazy_mode = False
    return objects, _Group, _Image2D


# ---------------------------------------------------------------------------
# heavy GUI ops exposed via a headless subprocess (video / consolidate)
# ---------------------------------------------------------------------------
def _run_headless_op(args: list[str], timeout: int = 600):
    """Run pyfigures.gui.headless_ops in a subprocess. Returns (ok, message)."""
    cmd = [sys.executable, "-m", "pyfigures.gui.headless_ops", *args]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_API", "pyqt6")
    env["PYTHONIOENCODING"] = "utf-8"     # read back as UTF-8 (accents, µ, —)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"operation timed out after {timeout}s"
    if proc.returncode != 0:
        from .export import _render_error_message
        text = (proc.stderr or proc.stdout or "").strip()
        if not text:            # a native crash says nothing
            return False, (f"the {args[0]} process stopped unexpectedly (exit code "
                           f"{proc.returncode}); try again")
        return False, _render_error_message(text)
    return True, (proc.stdout or "").strip()


def _restyle_html_batch(htmls: list[str], **attrs) -> list[str] | str:
    """Merge font attributes (font_family, font_size, bold, italic, underline,
    color) over each rich text, keeping its own formatting — in one Qt
    subprocess for all of them. Returns the new texts, or an error string."""
    if not htmls:
        return []
    workdir = tempfile.mkdtemp(prefix="pyf_style_")
    params_path = os.path.join(workdir, "params.json")
    out_path = os.path.join(workdir, "out.json")
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump({"htmls": list(htmls), **attrs}, f)
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_API", "pyqt6")
    env["PYTHONIOENCODING"] = "utf-8"     # read back as UTF-8 (accents, µ, —)
    try:
        proc = subprocess.run([sys.executable, "-m", "pyfigures.gui.style_text_headless",
                               params_path, out_path], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              stdin=subprocess.DEVNULL, env=env, timeout=300)
    except subprocess.TimeoutExpired:
        return "styling timed out"
    if proc.returncode != 0 or not os.path.isfile(out_path):
        return (proc.stderr or proc.stdout or "styling failed").strip()
    with open(out_path, encoding="utf-8") as f:
        res = json.load(f)
    fam = attrs.get("font_family")
    if fam and res.get("font_installed") is False:
        _warn_missing_font(fam)
    return res["htmls"]


def _warn_missing_font(family: str) -> None:
    """Warn when *family* is not installed here, naming the font it is really
    drawn and exported in and installed alternatives to offer."""
    rep = _font_report([family])
    st = rep.get("status", {}).get(family) if isinstance(rep, dict) else None
    if st is None:
        _warn(f"the font {family!r} may not be installed here (list_fonts lists what is available).")
    elif not st["installed"]:
        alts = ", ".join(repr(a) for a in st["alternatives"]) or "none found"
        _warn(f"the font {family!r} is not installed here: it is drawn and exported as "
              f"{st['drawn_as']!r}. Installed alternatives: {alts} (list_fonts lists all).")


def _font_report(resolve=()) -> dict | str:
    """The font report of pyfigures.gui.portable_fonts (installed families, the
    family each of *resolve* is really drawn and exported in). Qt is needed, so
    it runs in a subprocess. Returns the dict, or an error string."""
    out_json = os.path.join(tempfile.mkdtemp(prefix="pyf_fonts_"), "fonts.json")
    args = ["fonts", out_json]
    if resolve:
        args += ["--resolve", *resolve]
    ok, msg = _run_headless_op(args)
    if not ok:
        return msg
    if not os.path.isfile(out_json):
        return f"font report not produced: {msg}"
    with open(out_json, encoding="utf-8") as f:
        return json.load(f)


# generic CSS / Qt names: not a font of their own, never "missing"
_GENERIC_FAMILIES = {"sans serif", "sans-serif", "serif", "monospace", "ms shell dlg 2", "system-ui"}


def _text_families(root: ET.Element) -> list[str]:
    """Every font family the figure asks for: the figure font and the families
    in its texts' rich text (generic names left out)."""
    fams = []
    fig = _figure_font(root).get("font_family")
    if fig:
        fams.append(fig)
    for ta in root.iter("TAText2D"):
        raw = _decode((ta.find("text").text if ta.find("text") is not None else "") or "")
        for m in re.finditer(r"font-family:\s*([^;\"]+)", raw or ""):
            for part in m.group(1).split(","):
                name = part.strip().strip("'\"").replace("&quot;", "").replace("&#x27;", "").strip()
                if name and name.lower() not in _GENERIC_FAMILIES and name not in fams:
                    fams.append(name)
    return fams


def _figure_font(root: ET.Element) -> dict:
    """The figure font set with set_figure_properties (font_family,
    font_size, italic), {} when none was set."""
    el = root.find("SerializableQFont")
    if el is None:
        return {}
    out = {}
    fam = _decode(el.findtext("family"))
    if fam and fam != "None":
        out["font_family"] = fam
    try:
        size = float(el.findtext("size") or "")
        if size > 0:
            out["font_size"] = size
    except ValueError:
        pass
    if (el.findtext("italic") or "") == "True":
        out["italic"] = True
    return out


def _restyle_letters(root: ET.Element, **attrs) -> tuple[int, str | None]:
    """Give every panel letter (A, B, C…) the figure font. (count, error)."""
    letters = []
    for img in _iter_panel_elements(root):
        annots = img.find("annotations")
        if annots is None:
            continue
        letters += [ta for ta in annots.findall("TAText2D")
                    if (ta.findtext("is_letter") or "") in ("True", "b'True'")]
    attrs = {k: v for k, v in attrs.items() if v is not None}
    if not letters or not attrs:
        return 0, None
    new = _restyle_html_batch([_decode(ta.findtext("text")) or "" for ta in letters], **attrs)
    if isinstance(new, str):
        return 0, new
    for ta, html in zip(letters, new):
        _set_child_text(ta, "text", _encode_str(html))
    return len(letters), None


def _is_empty_placeholder(img: ET.Element) -> bool:
    """An Image2D with nothing in it: no file, no script, not text — the empty
    panel padding a grid or montage row so its panels keep the same size."""
    if img.findtext("isText", "False") == "True":
        return False
    fn = _decode(img.findtext("filename"))
    script = _decode(img.findtext("custom_loading_script"))
    svg = img.findtext("_raw_svg_bytes")
    return fn in (None, "", "None") and script in (None, "", "None") and svg in (None, "", "None")


def _iter_panel_elements(root: ET.Element):
    """Yield Image2D elements that are real layout panels — not the ones nested
    inside a panel's annotations / insets / ScaleBar."""
    parent = {c: p for p in root.iter() for c in p}
    for img in root.iter("Image2D"):
        node, skip = img, False
        while node in parent:
            node = parent[node]
            if node.tag in ("annotations", "insets", "ScaleBar"):
                skip = True
                break
        if not skip:
            yield img
