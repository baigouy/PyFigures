"""PyFigures MCP tools — Rendering, export, audit/review, figure library, source data, diffs, print-ready output, integrity and adjustment ledger.

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
    _atomic_write_text,
    _caption_sidecar_path,
    _decode,
    _encode_str,
    _get_container,
    _html_to_plain,
    _iter_panel_elements,
    _label_background_text,
    _load,
    _load_objects_lazy,
    _read_caption,
    _read_stats,
    _run_headless_op,
    _save,
    _set_child_text,
    _strip_tags,
)
from .structure import (
    add_scripted_image,
)
from .content import (
    _parse_channel_merge_script,
)
from .annotations import (
    list_fonts,
)
from .qc import (
    check_journal_compliance,
    check_resolution,
    check_scale_consistency,
)

# ---------------------------------------------------------------------------
# rendering (figure -> image)
# ---------------------------------------------------------------------------
# Rendering needs Qt; this server is deliberately Qt-free, so the render runs in
# a short-lived subprocess (also isolates any Qt crash from the server).
_RENDER_RASTER_EXTS = {".png", ".tif", ".tiff", ".jpg", ".jpeg"}
_RENDER_VECTOR_EXTS = {".svg", ".pdf"}
_RENDER_EXTS = _RENDER_RASTER_EXTS | _RENDER_VECTOR_EXTS


def _run_render(pyf_path: str, out_path: str, dpi: int, timeout: int = 300):
    """Render *pyf_path* -> *out_path* in a subprocess. Returns (ok, message)."""
    cmd = [sys.executable, "-m", "pyfigures.gui.render_headless",
           pyf_path, out_path, "--dpi", str(int(dpi))]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_API", "pyqt6")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"rendering timed out after {timeout}s"
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or \
            f"renderer exited with code {proc.returncode}"
        return False, msg
    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        return False, "renderer reported success but wrote no output"
    return True, out_path


@mcp.tool()
def export_figure(pyf_path: str, out_path: str, dpi: int = 300) -> str:
    """Render a .pyf figure to a final image file — the shippable deliverable.

    This produces exactly what the GUI's File -> Export produces (same layout,
    fonts, scale bars, labels), rendered off-screen.

    *out_path* extension selects the format:
      - raster: .png (lossless, alpha), .tif/.tiff (lossless, for journals),
        .jpg/.jpeg (lossy)
      - vector: .svg, .pdf (resolution-independent; *dpi* is ignored for these)
    *dpi* is the raster output resolution (300 = journal print quality; use 600
    for line art). Geometry is defined at 72 DPI, so higher dpi scales up.

    Returns JSON with the absolute output path and file size. To preview a
    figure visually without writing a permanent file, use render_preview.
    """
    ext = os.path.splitext(out_path)[1].lower()
    if ext not in _RENDER_EXTS:
        return (f"ERROR: unsupported output extension {ext!r}. Use one of: "
                + ", ".join(sorted(_RENDER_EXTS)))
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    out_path = os.path.abspath(out_path)
    ok, msg = _run_render(pyf_path, out_path, dpi)
    if not ok:
        return f"ERROR: {msg}"
    return json.dumps({
        "output": out_path,
        "format": ext.lstrip("."),
        "dpi": None if ext in _RENDER_VECTOR_EXTS else int(dpi),
        "bytes": os.path.getsize(out_path),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def render_preview(pyf_path: str, dpi: int = 100, max_dimension: int = 1400) -> Image:
    """Render a .pyf figure to a PNG and return it as an image you can see.

    Use this to visually check a figure you built or edited — to catch overlaps,
    clipping, a wrong LUT, a missing panel, or bad label placement — without
    writing a permanent file. For the final deliverable use export_figure.

    *dpi* controls render resolution (100 is a light, fast preview; raise it to
    inspect fine detail). The result is downscaled so its longest side is at most
    *max_dimension* pixels to keep it lightweight.
    """
    if not os.path.isfile(pyf_path):
        raise ValueError(f"no such .pyf file: {pyf_path}")
    tmp = os.path.join(tempfile.mkdtemp(prefix="pyf_preview_"), "preview.png")
    ok, msg = _run_render(pyf_path, tmp, dpi)
    if not ok:
        raise RuntimeError(f"could not render preview: {msg}")

    # Downscale for a lightweight payload (Pillow is a plain dependency, not Qt).
    try:
        from PIL import Image as PILImage
        im = PILImage.open(tmp)
        im.load()
        if max(im.size) > max_dimension:
            im.thumbnail((max_dimension, max_dimension), PILImage.LANCZOS)
        buf = io.BytesIO()
        im.convert("RGBA").save(buf, format="PNG")
        data = buf.getvalue()
    except Exception:
        with open(tmp, "rb") as f:
            data = f.read()
    return Image(data=data, format="png")


# ---------------------------------------------------------------------------
# figure-wide audit
# ---------------------------------------------------------------------------
def _annot_children(img_elem):
    """Return the list of child elements of an Image2D's <annotations>."""
    annots = img_elem.find("annotations")
    return list(annots) if annots is not None else []


def _panel_label_texts(img_elem):
    """Plain-text of every TAText2D label on a panel (letters, names, etc.)."""
    out = []
    for child in _annot_children(img_elem):
        if child.tag == "TAText2D":
            raw = _decode(child.findtext("text"))
            if raw:
                out.append(_html_to_plain(raw).strip())
    return [t for t in out if t]


@mcp.tool()
def audit_figure(pyf_path: str) -> str:
    """Inventory every panel and flag what's missing — a quick QC pass.

    For each Image2D panel (across all groups) reports: its filename, location
    (group_path + image_index), whether it has a scale bar, and the text labels
    on it (letter labels, channel names, etc.). Then a summary lists the panels
    with NO scale bar and the panels with NO text label — the two things
    reviewers most often ask to add.

    Read-only. Use this after building a figure to catch panels you forgot to
    label or scale-bar, then fix them with set_scale_bar / add_annotation /
    add_corner_labels.
    """
    _, root = _load(pyf_path)
    panels: list[dict] = []

    def _collect(container, path):
        for ii, img in enumerate(c for c in container if c.tag == "Image2D"):
            children = _annot_children(img)
            has_bar = any(c.tag == "ScaleBar" for c in children)
            labels = _panel_label_texts(img)
            fname = _decode(img.findtext("filename"))
            panels.append({
                "group_path": list(path),
                "image_index": ii,
                "filename": fname,
                "scale_bar": has_bar,
                "labels": labels,
                "n_labels": len(labels),
            })

    def _walk(grp, path):
        content = grp.find("content")
        if content is None:
            return
        _collect(content, path)
        for si, sub in enumerate(c for c in content if c.tag == "Group"):
            _walk(sub, path + [si])

    _collect(root, [])                       # free-canvas panels
    for gi, g in enumerate(c for c in root if c.tag == "Group"):
        _walk(g, [gi])

    missing_bar = [{"group_path": p["group_path"], "image_index": p["image_index"],
                    "filename": p["filename"]}
                   for p in panels if not p["scale_bar"]]
    missing_label = [{"group_path": p["group_path"], "image_index": p["image_index"],
                      "filename": p["filename"]}
                     for p in panels if p["n_labels"] == 0]

    return json.dumps({
        "n_panels": len(panels),
        "n_with_scale_bar": sum(1 for p in panels if p["scale_bar"]),
        "n_with_label": sum(1 for p in panels if p["n_labels"]),
        "panels_missing_scale_bar": missing_bar,
        "panels_missing_label": missing_label,
        "panels": panels,
    }, ensure_ascii=False, indent=2)


_REVIEW_RUBRIC = [
    "Message: is the figure's main comparison/result obvious at a glance, or do "
    "you have to hunt for it?",
    "Evidence: are the effects the caption claims actually visible in the panels "
    "(not just asserted)?",
    "Misleading elements: truncated or inconsistent axes, saturated/clipped "
    "images, cherry-picked contrast, 'n.s.' brackets presented as results, or "
    "panels compared at different physical scales.",
    "Colour accessibility: do the key colours stay distinguishable under the "
    "colour-blind simulations? Avoid red/green as the only distinction.",
    "Legibility: are labels, axis text and the scale-bar legend readable at the "
    "target print column width?",
    "Caption completeness: scale-bar length + unit stated? n per group given? the "
    "statistical test named? every panel letter (A, B, C…) defined?",
    "Layout & polish: balanced panel sizes, aligned edges, consistent scale bars "
    "and fonts, sensible whitespace.",
]


@mcp.tool()
def figure_review_brief(pyf_path: str, journal: str | None = None,
                        column: str = "single") -> str:
    """Assemble a **pre-submission reviewer brief** — everything an AI (or human)
    reviewer needs to critique a figure the way a referee would, in one call.

    Runs all the mechanical QC (audit, print resolution, scale-bar consistency,
    image integrity, journal compliance, fonts) and gathers the caption, then
    returns them together with a **visual-critique rubric** — the judgment calls
    a checklist can't make (is the message clear, are the claimed effects
    visible, is anything misleading, is the colour scheme accessible, is the
    caption complete).

    To complete the review, the caller should also *look at the figure*: call
    render_preview(pyf_path) to see it and simulate_color_blindness(pyf_path,
    cvd_type=…) for the accessibility check, then judge each rubric item and
    combine that with the mechanical findings here. (The bundled ``figure-review``
    skill walks an assistant through exactly this.)

    *journal* / *column*: optional — enables resolution + compliance checks at the
    journal's column width.

    Returns JSON: the caption, a ``mechanical_checks`` block, the ``visual_rubric``
    and which colour-blind simulations to run.
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"

    def _run(fn, *a, **k):
        try:
            r = fn(*a, **k)
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"
        if isinstance(r, str):
            try:
                return json.loads(r)
            except Exception:
                return r
        return r

    title, caption = _read_caption(pyf_path)
    checks: dict = {
        "audit": _run(audit_figure, pyf_path),
        "scale_consistency": _run(check_scale_consistency, pyf_path),
        "image_integrity": _run(check_image_integrity, pyf_path),
        "fonts": _run(list_fonts),
    }
    if journal:
        checks["journal_compliance"] = _run(check_journal_compliance, pyf_path,
                                            journal=journal, column=column)
        checks["resolution"] = _run(check_resolution, pyf_path,
                                    journal=journal, column=column)
    else:
        checks["resolution"] = _run(check_resolution, pyf_path)

    return json.dumps({
        "figure": os.path.basename(pyf_path),
        "caption_present": bool(caption or title),
        "caption": ({"title": title, "text": caption} if (caption or title) else None),
        "mechanical_checks": checks,
        "visual_rubric": _REVIEW_RUBRIC,
        "cvd_checks_recommended": ["deuteranopia", "protanopia", "tritanopia"],
        "how_to_complete": (
            "This brief covers the mechanical checks only. To finish the review, "
            "render the figure (render_preview) and the colour-blind simulations "
            "(simulate_color_blindness), visually judge each item in visual_rubric, "
            "and report findings by severity alongside the mechanical results."),
    }, ensure_ascii=False, indent=2)


def _extract_figure_meta(pyf_path: str):
    """Extract searchable metadata from a .pyf: panels (file + labels), caption."""
    try:
        root = ET.parse(pyf_path).getroot()
    except Exception:
        return None
    panels = []
    for img in _iter_panel_elements(root):
        fn = _decode(img.findtext("filename"))
        base = (os.path.basename(str(fn))
                if fn and fn not in ("None", "@template@") else None)
        panels.append({"file": base, "label": _panel_letter_label(img),
                       "labels": _panel_labels_texts(img)})
    title, caption = _read_caption(pyf_path)
    return {
        "path": os.path.abspath(pyf_path),
        "name": os.path.basename(pyf_path),
        "mtime": os.path.getmtime(pyf_path),
        "n_panels": len(panels),
        "panels": panels,
        "title": title,
        "caption": caption,
    }


@mcp.tool()
def index_figures(root_dir: str, index_path: str | None = None,
                  with_thumbnails: bool = False, thumb_dpi: int = 40) -> str:
    """Build (or update) a searchable **figure library index** by scanning a
    folder tree for ``.pyf`` files — so you can later find and reuse past figures
    and panels with search_figures().

    For each figure it records the panels (source filenames + labels), the
    caption and the modified time. Re-running is incremental: figures unchanged
    since the last index are skipped. Optionally renders a small thumbnail per
    figure (*with_thumbnails*, cached beside the index).

    *root_dir*: folder tree to scan. *index_path*: where to write the JSON index
    (default ``<root_dir>/.pyfigures_index.json``).

    Returns JSON with counts (new / updated / unchanged) and the index path.
    """
    if not os.path.isdir(root_dir):
        return f"ERROR: no such folder: {root_dir}"
    root_dir = os.path.abspath(root_dir)
    if index_path is None:
        index_path = os.path.join(root_dir, ".pyfigures_index.json")
    index_path = os.path.abspath(index_path)

    existing = {}
    if os.path.isfile(index_path):
        try:
            with open(index_path, encoding="utf-8") as f:
                for e in json.load(f).get("figures", []):
                    existing[e["path"]] = e
        except Exception:
            existing = {}

    pyfs = []
    for dp, _dn, fnames in os.walk(root_dir):
        for fn in fnames:
            if fn.lower().endswith(".pyf"):
                pyfs.append(os.path.abspath(os.path.join(dp, fn)))

    def _change_key(pyf):
        # the caption lives in a sidecar: editing it must re-index the figure
        # even though the .pyf itself is unchanged
        key = [os.path.getmtime(pyf)]
        side = _caption_sidecar_path(pyf)
        key.append(os.path.getmtime(side) if os.path.isfile(side) else 0.0)
        return key

    thumbs_dir = index_path + ".thumbs"
    entries, n_new, n_updated, n_skipped = [], 0, 0, 0
    failed = []
    for ap in sorted(pyfs):
        mt = os.path.getmtime(ap)
        key = _change_key(ap)
        prev = existing.get(ap)
        if (prev and prev.get("change_key") == key
                and (not with_thumbnails or prev.get("thumbnail"))):
            entries.append(prev)
            n_skipped += 1
            continue
        meta = _extract_figure_meta(ap)
        if meta is None:
            failed.append(ap)
            continue
        meta["mtime"] = mt
        meta["change_key"] = key
        if with_thumbnails:
            import hashlib
            os.makedirs(thumbs_dir, exist_ok=True)
            tp = os.path.join(thumbs_dir, hashlib.md5(ap.encode()).hexdigest()[:12] + ".png")
            ok, _ = _run_render(ap, tp, thumb_dpi)
            meta["thumbnail"] = tp if ok else None
        entries.append(meta)
        n_updated += 1 if prev else 0
        n_new += 0 if prev else 1

    # drop thumbnails of figures that are no longer indexed
    if os.path.isdir(thumbs_dir):
        keep = {os.path.normcase(os.path.abspath(e["thumbnail"]))
                for e in entries if e.get("thumbnail")}
        for fn in os.listdir(thumbs_dir):
            fp = os.path.join(thumbs_dir, fn)
            if os.path.normcase(os.path.abspath(fp)) not in keep:
                try:
                    os.remove(fp)
                except OSError:
                    pass

    _atomic_write_text(index_path, json.dumps({"root": root_dir, "figures": entries},
                                              ensure_ascii=False, indent=2))
    return json.dumps({
        "index": index_path,
        "figures_indexed": len(entries),
        "new": n_new, "updated": n_updated, "unchanged": n_skipped,
        "failed": len(failed),
        "failed_files": failed[:20],
        "thumbnails": with_thumbnails,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def search_figures(query: str, index_path: str, limit: int = 20) -> str:
    """Search a figure library index (built by index_figures) by keyword — find
    the figure or panel you're looking for across past projects.

    Matches *query* words against each figure's path, panel source filenames,
    panel labels/text and caption. Figures matching all query words rank highest.

    *query*: space-separated keywords (e.g. "WT gut immunofluorescence").
    *index_path*: the index written by index_figures.
    *limit*: max results (default 20).

    Returns JSON: ranked results with the figure path, a caption snippet, the
    panels that matched, and a thumbnail path if one was indexed.
    """
    if not os.path.isfile(index_path):
        return (f"ERROR: no index at {index_path}. Run index_figures() first.")
    tokens = [t for t in re.split(r"\W+", query.lower()) if t]
    if not tokens:
        return "ERROR: empty query."
    try:
        with open(index_path, encoding="utf-8") as f:
            figs = json.load(f).get("figures", [])
    except Exception as e:
        return f"ERROR: could not read index — {type(e).__name__}: {e}"

    results = []
    for fig in figs:
        panel_files = [p["file"] for p in fig.get("panels", []) if p.get("file")]
        parts = [fig.get("path", ""), fig.get("name", ""), fig.get("title") or "",
                 fig.get("caption") or ""] + panel_files
        for p in fig.get("panels", []):
            parts.extend(p.get("labels") or [])
        blob = " ".join(parts).lower()
        score, matched = 0, []
        for t in tokens:
            c = blob.count(t)
            if c:
                score += c
                matched.append(t)
        if not score:
            continue
        if len(matched) == len(tokens):
            score += 5                       # boost figures matching every word
        results.append({
            "path": fig["path"], "name": fig.get("name"), "score": score,
            "matched": matched, "n_panels": fig.get("n_panels"),
            "caption_snippet": (fig.get("caption") or "")[:160],
            "matching_panels": [pf for pf in panel_files
                                if any(t in pf.lower() for t in tokens)],
            "thumbnail": fig.get("thumbnail"),
        })
    results.sort(key=lambda r: -r["score"])
    results = results[:max(1, limit)]
    return json.dumps({"query": query, "n_results": len(results),
                       "results": results}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# annotation text styling (font / size / bold / italic / underline / colour)
# ---------------------------------------------------------------------------
@mcp.tool()
def style_annotation(
    pyf_path: str,
    group_path: list[int],
    image_index: int,
    annotation_index: int,
    font_family: str | None = None,
    font_size: float | None = None,
    bold: bool | None = None,
    italic: bool | None = None,
    underline: bool | None = None,
    color: str | None = None,
    background: str | int | None = None,
) -> str:
    """Restyle a text annotation's font WITHOUT losing its rich formatting.

    Annotation text is a Qt rich-text document that may mix per-word colour,
    super/subscript and bold spans. This merges the attributes you specify over
    the whole label and leaves the rest intact: e.g. setting *font_size* keeps a
    superscript and existing per-word colours; only setting *color* changes the
    colour (it deliberately overrides per-word colours since you asked for one).

    Pass only the attributes you want to change (leave the rest as null):
      *font_family*  e.g. "Arial", "Helvetica"
      *font_size*    point size, e.g. 12
      *bold* / *italic* / *underline*  true/false
      *color*        any CSS/Qt colour, e.g. "#000000", "red"
      *background*   a filled box behind the text so it reads on any image,
                     e.g. "black", "white", "#202020"; "none" removes it

    To change the label *text* instead of its style, use set_annotation_text.
    *group_path*: [] free-canvas, [0] group 0, [0,1] sub-group.
    *annotation_index*: 0-based index among TAText2D elements on that image
    (as reported by get_annotations).
    """
    if all(v is None for v in
           (font_family, font_size, bold, italic, underline, color, background)):
        return ("ERROR: nothing to change — set at least one of font_family, "
                "font_size, bold, italic, underline, color, background.")
    bg = None
    if background is not None:
        try:
            bg = _label_background_text(background)
        except ValueError as e:
            return f"ERROR: {e}"

    tree, root = _load(pyf_path)
    container, err = _get_container(root, group_path)
    if err:
        return f"ERROR: {err}"
    images = [c for c in container if c.tag == "Image2D"]
    if not 0 <= image_index < len(images):
        return f"ERROR: image_index {image_index} out of range (0..{len(images)-1})."
    annots = images[image_index].find("annotations")
    texts = [c for c in (annots if annots is not None else []) if c.tag == "TAText2D"]
    if not 0 <= annotation_index < len(texts):
        return (f"ERROR: annotation_index {annotation_index} out of range "
                f"(0..{len(texts)-1}); this panel has {len(texts)} text annotation(s).")

    elem = texts[annotation_index]
    if bg is not None:
        _set_child_text(elem, "fill_color", bg)
    if all(v is None for v in (font_family, font_size, bold, italic, underline, color)):
        _save(tree, pyf_path)
        return json.dumps({
            "styled": {"group_path": group_path, "image_index": image_index,
                       "annotation_index": annotation_index},
            "applied": {"background": background},
        }, ensure_ascii=False, indent=2)
    current_html = _decode(elem.findtext("text")) or ""

    # Restyle the HTML in a Qt subprocess (keeps this server Qt-free / crash-safe).
    workdir = tempfile.mkdtemp(prefix="pyf_style_")
    params_path = os.path.join(workdir, "params.json")
    out_path = os.path.join(workdir, "out.html")
    with open(params_path, "w", encoding="utf-8") as f:
        json.dump({
            "html": current_html,
            "font_family": font_family, "font_size": font_size,
            "bold": bold, "italic": italic, "underline": underline,
            "color": color,
        }, f)
    cmd = [sys.executable, "-m", "pyfigures.gui.style_text_headless",
           params_path, out_path]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_API", "pyqt6")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              env=env, timeout=120)
    except subprocess.TimeoutExpired:
        return "ERROR: styling timed out"
    if proc.returncode != 0 or not os.path.isfile(out_path):
        return f"ERROR: {(proc.stderr or proc.stdout or 'styling failed').strip()}"
    with open(out_path, "r", encoding="utf-8") as f:
        new_html = f.read()

    _set_child_text(elem, "text", _encode_str(new_html))
    _save(tree, pyf_path)

    changed = {k: v for k, v in {
        "font_family": font_family, "font_size": font_size, "bold": bold,
        "italic": italic, "underline": underline, "color": color,
        "background": background,
    }.items() if v is not None}
    return json.dumps({
        "styled": {"group_path": group_path, "image_index": image_index,
                   "annotation_index": annotation_index},
        "applied": changed,
        "note": "Reopen the figure in PyFigures to see the change.",
    }, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# LUT intensity calibration bar
# ---------------------------------------------------------------------------
@mcp.tool()
def add_lut_calibration_bar(
    pyf_path: str,
    group_path: list[int],
    lut: str = "GRAY",
    vmin: float = 0.0,
    vmax: float = 255.0,
    label: str = "",
    orientation: str = "vertical",
    ticks: list[float] | None = None,
    tick_labels: list[str] | None = None,
    panel_label: str = "",
    panel_label_placement: str = "top left",
) -> str:
    """Add an intensity calibration bar (colour bar) matching a LUT.

    Reviewers routinely ask for the intensity scale that goes with a
    pseudo-coloured / LUT image. This adds a compact colour-bar panel — a
    gradient of *lut* from *vmin* to *vmax* with tick labels — as a scripted
    matplotlib panel, so it renders and exports like any other panel.

    *lut*: a PyFigures LUT name (GRAY, GREEN, RED, FIRE, AFM_HOT, RAINBOW_1, …
    or MATPLOTLIB_viridis, MATPLOTLIB_jet, …) — pass the same name you gave the
    matching image in set_lut so the colours line up.
    *vmin*/*vmax*: the intensity values at the bar's ends (e.g. 0 and 255 for an
    8-bit image, or the min/max you normalised a 16-bit image to).
    *label*: axis label, e.g. "Intensity (a.u.)" or "GFP (a.u.)".
    *orientation*: "vertical" or "horizontal".
    *ticks*/*tick_labels*: optional explicit tick positions and their labels
    (e.g. ticks=[0,255], tick_labels=["low","high"]).
    *panel_label*: optional corner letter for the bar panel itself.

    *group_path*: [] free-canvas, [0] group 0, [0,1] sub-group.
    Returns the new panel's image index.
    """
    from pyfigures.colorbar_script import build_calibration_bar_script
    try:
        script = build_calibration_bar_script(
            lut=lut, vmin=vmin, vmax=vmax, label=label,
            orientation=orientation, ticks=ticks, tick_labels=tick_labels)
    except ValueError as e:
        return f"ERROR: {e}"

    return add_scripted_image(
        pyf_path, group_path, script,
        label=panel_label, label_placement=panel_label_placement,
    )


# ---------------------------------------------------------------------------
# templates: convert a whole figure into reusable template slots
# ---------------------------------------------------------------------------
@mcp.tool()
def templatify_figure(pyf_path: str) -> str:
    """Convert every image panel into an empty template slot (GUI: Template →
    Convert figure to template).

    Keeps the entire layout, annotations, scale bars and labels, but clears each
    panel's linked file (sets it to the ``@template@`` placeholder) so the figure
    becomes a reusable skeleton. Fill the slots later with fill_template() /
    batch_fill_templates(). Scripted panels and existing template slots are left
    untouched.

    Returns how many panels were converted.
    """
    tree, root = _load(pyf_path)
    n = 0
    for img in root.iter("Image2D"):
        fn = img.find("filename")
        current = _decode(fn.text) if fn is not None else None
        # only convert panels backed by a real file (skip scripted / already-template)
        if not current or current == "@template@":
            continue
        _set_child_text(img, "filename", _encode_str("@template@"))
        pxf = img.find("px_to_unit_conversion_factor")
        if pxf is not None:
            pxf.text = "0"          # is_template() resets the conversion factor
        n += 1
    _save(tree, pyf_path)
    return (f"Converted {n} panel(s) into template slots. "
            "Fill them with fill_template() or batch_fill_templates().")


# ---------------------------------------------------------------------------
# review workflow (share a figure for comments, then pull the comments back)
# ---------------------------------------------------------------------------
@mcp.tool()
def export_review(pyf_path: str, out_html: str, dpi: int = 150) -> str:
    """Export a self-contained HTML review page for a figure (GUI: Review →
    Export for review).

    Renders the figure and embeds it in a single .html file that a colleague can
    open in any browser to leave positional comments; their saved copy can later
    be pulled back with import_review_comments(). Any comments already stored in
    the figure's sidecar are included.

    *out_html*: destination .html path. *dpi*: render resolution for the embedded
    image (150 is a good screen default).
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    if not out_html.lower().endswith((".html", ".htm")):
        return "ERROR: out_html must end in .html"
    out_html = os.path.abspath(out_html)
    tmp_png = os.path.join(tempfile.mkdtemp(prefix="pyf_review_"), "fig.png")
    ok, msg = _run_render(pyf_path, tmp_png, dpi)
    if not ok:
        return f"ERROR: could not render figure for review: {msg}"
    try:
        from pyfigures.gui.review.html_export import export_review_html
        source = os.path.splitext(os.path.basename(pyf_path))[0]
        export_review_html(tmp_png, out_html, source_name=source)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    return json.dumps({"output": out_html, "bytes": os.path.getsize(out_html)},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def list_review_comments(pyf_path: str) -> str:
    """List the review comments stored in a figure's sidecar (GUI: Review → View
    review comments). Returns each comment's position, text and author (JSON)."""
    try:
        from pyfigures.gui.review.html_export import load_sidecar_comments
        comments = load_sidecar_comments(pyf_path)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    return json.dumps({"count": len(comments), "comments": comments},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def import_review_comments(pyf_path: str, review_html: str) -> str:
    """Pull comments from a reviewed HTML page back into the figure's sidecar
    (GUI: Review → Import review comments).

    *review_html*: the .html a reviewer saved after commenting. New comments are
    merged with any already stored. Returns the merged comment count.
    """
    if not os.path.isfile(review_html):
        return f"ERROR: no such review file: {review_html}"
    try:
        from pyfigures.gui.review.html_export import (
            extract_comments, load_sidecar_comments, merge_comments,
            save_sidecar_comments)
        incoming = extract_comments(review_html)
        merged = merge_comments(load_sidecar_comments(pyf_path), incoming)
        save_sidecar_comments(pyf_path, merged)
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"
    return json.dumps({"imported": len(incoming), "total": len(merged)},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def export_video(pyf_path: str, out_path: str, frame_mode: str = "freeze",
                 bg_color: str = "0,0,0") -> str:
    """Render a figure's video / time-stack panels to a movie file (GUI: Export
    As → Video). Only works if the figure contains a video or t-stack panel.

    *out_path*: .mp4, .mov, .mkv, .webm or .avi.
    *frame_mode*: what shorter panels show once their frames run out —
    ``"freeze"`` (hold last frame) or ``"blank"`` (background colour).
    *bg_color*: "R,G,B" background for blank frames (0-255 each).

    With PyAV installed (``pip install av``, bundles ffmpeg) mp4/mov/mkv are
    H.264 and webm is VP9 — they play everywhere, including on a Mac; without
    it OpenCV writes the old MPEG-4 codec and the result carries a WARNING.

    Returns the output path, size and codec.
    """
    if frame_mode not in ("freeze", "blank"):
        return "ERROR: frame_mode must be 'freeze' or 'blank'."
    if not out_path.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
        return "ERROR: out_path must end in .mp4, .mov, .mkv, .webm or .avi."
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    out_path = os.path.abspath(out_path)
    ok, msg = _run_headless_op(
        ["video", pyf_path, out_path, "--frame-mode", frame_mode, "--bg", bg_color])
    if not ok:
        return f"ERROR: {msg}"
    from batoolset.img import _av_codec_for
    codec = _av_codec_for(out_path) or ("mjpeg" if out_path.lower().endswith(".avi") else "mpeg4")
    res = json.dumps({"output": out_path, "bytes": os.path.getsize(out_path), "codec": codec},
                     ensure_ascii=False, indent=2)
    if codec == "mpeg4":
        res += ("\nWARNING: written with the old MPEG-4 codec, which QuickTime / Safari / "
                "PowerPoint can't play; install PyAV (pip install av) for H.264.")
    return res


@mcp.tool()
def export_latex(pyf_path: str, out_path: str, image_format: str = "pdf",
                 with_caption: bool = False) -> str:
    """Export 'PDF + LaTeX' (GUI: Export As → PDF + LaTeX) — a text-free vector
    graphics file plus an \\input-able LaTeX overlay that typesets the figure's
    labels via LaTeX. Popular with physicists: labels use the document's fonts and
    render real math ($\\alpha$, subscripts, equations) instead of baked-in bitmaps.

    Writes two files next to *out_path*: ``<stem>.<fmt>`` (graphics, no text) and
    ``<stem>.<fmt>_tex`` (the LaTeX overlay). *image_format* is pdf (default, vector
    — best), png, or svg.

    If *with_caption* is true and a caption has been stored for this figure via
    set_figure_caption() (its ``<stem>.caption.json`` sidecar), the overlay is
    wrapped in a ``figure`` float carrying a ``\\caption{...}`` (title in bold,
    LaTeX auto-numbers "Figure N:"). Off by default — the plain overlay is a bare
    picture group you \\input inside your own float.

    In the paper::

        \\usepackage{graphicx,color}
        \\def\\svgwidth{\\columnwidth}\\input{figure.pdf_tex}

    Returns JSON with both output paths and the \\input usage line. No LaTeX
    installation is needed to export — it is compiled later in your document.
    """
    fmt = image_format.lower().lstrip(".")
    if fmt not in ("pdf", "png", "svg"):
        return "ERROR: image_format must be 'pdf', 'png' or 'svg'."
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    out_path = os.path.abspath(out_path)
    caption_note = None
    if with_caption:
        title, cap = _read_caption(pyf_path)
        if not cap:
            caption_note = ("with_caption was set but no caption is stored for this "
                            "figure — set one with set_figure_caption() first; "
                            "exported the plain overlay instead.")
    # deterministic output paths (do not parse stdout — loading a figure can print
    # JVM/Fiji init noise there); mirrors save_latex's naming
    graphics = os.path.splitext(out_path)[0] + "." + fmt
    tex = graphics + "_tex"
    argv = ["latex", pyf_path, out_path, "--format", fmt]
    if with_caption and caption_note is None:
        argv.append("--with-caption")
    ok, msg = _run_headless_op(argv)
    if not ok:
        return f"ERROR: {msg}"
    if not (os.path.isfile(graphics) and os.path.isfile(tex)):
        return f"ERROR: LaTeX export reported success but files are missing ({graphics}, {tex})"
    tex_name = os.path.basename(tex)
    result = {
        "graphics": graphics,
        "latex_overlay": tex,
        "usage": "\\usepackage{graphicx,color}  then  "
                 "\\def\\svgwidth{\\columnwidth}\\input{" + tex_name + "}",
        "caption_embedded": bool(with_caption and caption_note is None),
        "bytes": os.path.getsize(tex),
    }
    if caption_note:
        result["note"] = caption_note
    return json.dumps(result, ensure_ascii=False, indent=2)


def _editable_export(pyf_path: str, out_path: str, fmt: str):
    """Run the headless editable export; returns (summary dict | None, error str | None)."""
    if not os.path.isfile(pyf_path):
        return None, f"no such .pyf file: {pyf_path}"
    out_path = os.path.abspath(out_path)
    ok, msg = _run_headless_op(["editable", pyf_path, out_path, "--format", fmt])
    if not ok:
        return None, msg
    if not os.path.isfile(out_path):
        return None, f"export reported success but {out_path} is missing"
    summary = {"path": out_path}
    # the JSON summary is the last stdout line (figure loading may print noise before it)
    for line in reversed(msg.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                summary = json.loads(line)
            except ValueError:
                pass
            break
    summary["path"] = out_path
    summary["bytes"] = os.path.getsize(out_path)
    return summary, None


@mcp.tool()
def export_pptx(pyf_path: str, out_path: str) -> str:
    """Export the figure as an **editable PowerPoint** slide (.pptx) — like
    QuickFigures' PowerPoint export (GUI: Export As → PowerPoint (editable)).

    The slide is the size of the figure. Every panel is a group holding its
    picture(s) plus native PowerPoint objects: the panel letters, channel names,
    labels and scale-bar text are editable text boxes; scale bars, ROIs, arrows,
    brackets and vector plots are editable shapes. Cropped / rotated panels keep
    their crop and rotation. Text inside data plots (tick labels) is exported as
    exact outlines, not editable text.

    Returns JSON: path, size in points, number of images / shapes / text boxes
    and panel groups. Needs the ``python-pptx`` package.
    """
    if not out_path.lower().endswith(".pptx"):
        return "ERROR: out_path must end in .pptx."
    summary, err = _editable_export(pyf_path, out_path, "pptx")
    if err:
        return f"ERROR: {err}"
    return json.dumps(summary, ensure_ascii=False, indent=2)


@mcp.tool()
def export_illustrator_script(pyf_path: str, out_path: str) -> str:
    """Export the figure as an **Adobe Illustrator script** (.jsx) that rebuilds
    it in Illustrator from native objects (GUI: Export As → Adobe Illustrator
    script), like QuickFigures' Illustrator export.

    Writes ``<stem>.jsx`` plus an ``<stem>_assets`` folder with the panel images
    (PNG); keep them together. In Illustrator: File → Scripts → Other Script…,
    pick the .jsx. The script creates an RGB document the size of the figure with
    one group per panel: embedded images, live text (Arial by default, as
    PostScript fonts ArialMT / Arial-BoldMT…) and vector paths for scale bars,
    ROIs, arrows, brackets and vector plots.

    Illustrator already opens PyFigures' SVG and PDF exports; the script gives a
    cleaner result (one group per panel, real text frames, no clipping masks).

    Returns JSON: path, assets folder, size in points and object counts.
    """
    if not out_path.lower().endswith(".jsx"):
        return "ERROR: out_path must end in .jsx."
    summary, err = _editable_export(pyf_path, out_path, "jsx")
    if err:
        return f"ERROR: {err}"
    summary["usage"] = "Illustrator: File > Scripts > Other Script... and choose " + os.path.basename(out_path)
    return json.dumps(summary, ensure_ascii=False, indent=2)


@mcp.tool()
def consolidate_figure(pyf_path: str, out_pyf: str) -> str:
    """Save a self-contained copy of the figure with every referenced image
    bundled next to it (GUI: File → Save And Consolidate).

    Copies all linked image files into an ``<out>.files`` folder beside *out_pyf*
    and rewrites the figure to point at them, so the .pyf can be moved/shared
    without breaking image links. Returns the output path.
    """
    if not out_pyf.lower().endswith(".pyf"):
        return "ERROR: out_pyf must end in .pyf."
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    out_pyf = os.path.abspath(out_pyf)
    ok, msg = _run_headless_op(["consolidate", pyf_path, out_pyf])
    if not ok:
        return f"ERROR: {msg}"
    files_dir = os.path.splitext(out_pyf)[0] + ".files"
    return json.dumps({
        "output": out_pyf,
        "files_folder": files_dir if os.path.isdir(files_dir) else None,
    }, ensure_ascii=False, indent=2)


def _panel_source_files(fn: str | None, script: str | None) -> list[str]:
    """Return the source files a panel depends on: its linked image, plus any
    CSV (data plots) or channel images (merges) referenced in its script."""
    srcs: list[str] = []
    if fn and fn not in ("None", "@template@"):
        srcs.append(fn)
    if script:
        m = re.search(r"_csv\s*=\s*(['\"])(.*?)\1", script)
        if m:
            srcs.append(m.group(2))
        mlist = re.search(r"_files\s*=\s*\[(.*?)\]", script, re.S)
        if mlist:
            srcs.extend(v for _, v in re.findall(r"(['\"])(.*?)\1", mlist.group(1)))
    # de-dup, preserve order
    seen, out = set(), []
    for s in srcs:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


@mcp.tool()
def export_source_data(pyf_path: str, out_dir: str, dpi: int = 300,
                       image_format: str = "png") -> str:
    """Assemble a journal-style **Source Data bundle** for the figure — the folder
    of underlying data + provenance that many journals now require alongside each
    figure.

    Writes *out_dir* containing:
      * ``figure.<png|pdf>`` — the rendered figure;
      * ``sources/`` — a copy of every panel's underlying source file: the linked
        image, the CSV behind a data-plot panel, or the channel images behind a
        merge, renamed by panel (e.g. ``panelA__counts.csv``). Non-file scripted
        panels get their script saved as ``panelX__script.py``;
      * ``caption.txt`` — the figure caption/legend (if set);
      * ``statistics.json`` — the recorded tests + p-values (if any);
      * ``methods.txt`` — the adjustment-provenance + statistics Methods
        paragraphs from export_adjustment_ledger;
      * ``MANIFEST.txt`` — a per-panel index mapping each panel to its source
        file(s), so a reader can trace any panel back to its data.

    Reuses the caption/stats sidecars, the adjustment ledger and export_figure.
    Returns JSON summarising what was bundled.

    Example::

        export_source_data("fig.pyf", "/out/Figure1_SourceData")
    """
    import shutil
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    image_format = image_format.lower()
    if image_format not in ("png", "pdf", "tif", "tiff"):
        return "ERROR: image_format must be png, pdf, tif or tiff."
    out_dir = os.path.abspath(out_dir)
    sources_dir = os.path.join(out_dir, "sources")
    os.makedirs(sources_dir, exist_ok=True)

    try:
        root = ET.parse(pyf_path).getroot()
    except Exception as e:
        return f"ERROR: could not parse .pyf: {type(e).__name__}: {e}"

    # ── render the figure ────────────────────────────────────────────────────
    fig_out = os.path.join(out_dir, f"figure.{image_format}")
    render = export_figure(pyf_path, fig_out, dpi=dpi)
    figure_ok = os.path.isfile(fig_out)

    # ── per-panel source files + manifest ────────────────────────────────────
    manifest_lines = [f"Source data for: {os.path.basename(pyf_path)}", ""]
    panels_info = []
    used_names: set[str] = set()
    idx = 0
    for img in root.iter("Image2D"):
        fn = _decode(img.findtext("filename"))
        script = _decode(img.findtext("custom_loading_script"))
        if (not fn or fn in ("None", "@template@")) and not script:
            continue
        label = _panel_letter_label(img) or f"{idx}"
        tag = "panel" + re.sub(r"[^A-Za-z0-9]", "", str(label)) or f"panel{idx}"
        srcs = _panel_source_files(fn, script)
        copied = []
        for s in srcs:
            if os.path.isfile(s):
                base = f"{tag}__{os.path.basename(s)}"
                dest = base
                k = 1
                while dest in used_names:
                    dest = f"{tag}_{k}__{os.path.basename(s)}"
                    k += 1
                used_names.add(dest)
                try:
                    shutil.copy2(s, os.path.join(sources_dir, dest))
                    copied.append(dest)
                except Exception:
                    pass
            else:
                copied.append(f"(missing: {os.path.basename(str(s))})")
        # scripted panel with no on-disk source → save its script
        if script and not any(os.path.isfile(s) for s in srcs):
            sname = f"{tag}__script.py"
            try:
                with open(os.path.join(sources_dir, sname), "w", encoding="utf-8") as f:
                    f.write(script)
                copied.append(sname)
            except Exception:
                pass
        manifest_lines.append(f"Panel {label}: " + (", ".join(copied) if copied
                                                     else "(no external source)"))
        panels_info.append({"panel": label, "sources": copied})
        idx += 1

    # ── caption ──────────────────────────────────────────────────────────────
    title, caption = _read_caption(pyf_path)
    caption_written = False
    if caption or title:
        with open(os.path.join(out_dir, "caption.txt"), "w", encoding="utf-8") as f:
            if title:
                f.write(title.strip() + "\n\n")
            f.write((caption or "").strip() + "\n")
        caption_written = True

    # ── statistics ───────────────────────────────────────────────────────────
    stats_entries = _read_stats(pyf_path)
    if stats_entries:
        with open(os.path.join(out_dir, "statistics.json"), "w", encoding="utf-8") as f:
            json.dump(stats_entries, f, ensure_ascii=False, indent=2)

    # ── methods (provenance + stats paragraphs) ──────────────────────────────
    methods_written = False
    try:
        led = json.loads(export_adjustment_ledger(pyf_path))
        parts = [p for p in (led.get("methods_paragraph"),
                             led.get("statistics_methods_paragraph")) if p]
        if parts:
            with open(os.path.join(out_dir, "methods.txt"), "w", encoding="utf-8") as f:
                f.write("\n\n".join(parts) + "\n")
            methods_written = True
    except Exception:
        pass

    with open(os.path.join(out_dir, "MANIFEST.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(manifest_lines) + "\n")

    return json.dumps({
        "output_dir": out_dir,
        "figure": fig_out if figure_ok else None,
        "figure_render_note": None if figure_ok else render,
        "panels": panels_info,
        "n_source_files": len(os.listdir(sources_dir)),
        "caption": caption_written,
        "statistics": bool(stats_entries),
        "methods": methods_written,
    }, ensure_ascii=False, indent=2)


def _panel_labels_texts(img: ET.Element) -> list[str]:
    annots = img.find("annotations")
    out = []
    if annots is not None:
        for a in annots.iter("TAText2D"):
            tx = _strip_tags(_decode(a.findtext("text")) or "").strip()
            if tx:
                out.append(tx)
    return sorted(out)


def _panel_scalebar_info(img: ET.Element):
    annots = img.find("annotations")
    sb = annots.find("ScaleBar") if annots is not None else None
    if sb is None:
        return None
    try:
        w = float(sb.findtext("bar_width_in_units"))
    except (TypeError, ValueError):
        w = None
    legend = _strip_tags(_decode(sb.findtext("legend")) or "").strip()
    return {"width": w, "legend": legend or None}


def _diff_panel_signatures(pyf_path: str) -> list[dict]:
    """One comparable signature per real panel: file, labels, scale bar,
    adjustments, pixel size and (best-effort) geometry."""
    root = ET.parse(pyf_path).getroot()
    xml_panels = list(_iter_panel_elements(root))

    geoms = []
    try:
        objects, Group, Image2D = _load_objects_lazy(pyf_path)

        def _walk(items):
            for c in items:
                if isinstance(c, Image2D):
                    geoms.append(c)
                elif isinstance(c, Group):
                    _walk(getattr(c, "content", []))
        _walk(objects)
    except Exception:
        geoms = []
    use_geom = len(geoms) == len(xml_panels)

    sigs = []
    for i, img in enumerate(xml_panels):
        fn = _decode(img.findtext("filename"))
        base = (os.path.basename(str(fn))
                if fn and fn not in ("None", "@template@") else "(scripted/none)")
        adj, _ = _panel_adjustments(img)
        try:
            pxu = float(img.findtext("px_to_unit_conversion_factor") or 0) or None
        except (TypeError, ValueError):
            pxu = None
        geom = None
        if use_geom:
            try:
                g = geoms[i]
                geom = {"x": round(g.x(), 1), "y": round(g.y(), 1),
                        "w": round(g.width(all=True), 1), "h": round(g.height(all=True), 1)}
            except Exception:
                geom = None
        sigs.append({
            "file": base,
            "labels": _panel_labels_texts(img),
            "scale_bar": _panel_scalebar_info(img),
            "adjustments": sorted(a["type"] for a in adj),
            "px_to_unit": pxu,
            "geometry": geom,
        })
    return sigs


def _match_and_diff(old_sigs, new_sigs, move_tol: float = 2.0):
    from collections import defaultdict

    def keyed(sigs):
        seen, out, order = defaultdict(int), {}, []
        for s in sigs:
            k = (s["file"], seen[s["file"]])
            seen[s["file"]] += 1
            out[k] = s
            order.append(k)
        return out, order

    old_k, old_order = keyed(old_sigs)
    new_k, new_order = keyed(new_sigs)
    changes = []

    for k in new_order:
        if k not in old_k:
            changes.append({"type": "panel_added", "panel": new_k[k]["file"],
                            "detail": f"panel '{new_k[k]['file']}' added"})
    for k in old_order:
        if k not in new_k:
            changes.append({"type": "panel_removed", "panel": old_k[k]["file"],
                            "detail": f"panel '{old_k[k]['file']}' removed"})

    for k in old_order:
        if k not in new_k:
            continue
        o, nw = old_k[k], new_k[k]
        f = o["file"]
        if o["geometry"] and nw["geometry"]:
            og, ng = o["geometry"], nw["geometry"]
            if abs(og["x"] - ng["x"]) > move_tol or abs(og["y"] - ng["y"]) > move_tol:
                changes.append({"type": "panel_moved", "panel": f,
                                "detail": f"'{f}' moved ({og['x']},{og['y']}) -> ({ng['x']},{ng['y']})"})
            if abs(og["w"] - ng["w"]) > move_tol or abs(og["h"] - ng["h"]) > move_tol:
                changes.append({"type": "panel_resized", "panel": f,
                                "detail": f"'{f}' resized {og['w']}x{og['h']} -> {ng['w']}x{ng['h']}"})
        if (o["scale_bar"] is None) != (nw["scale_bar"] is None):
            changes.append({"type": "scale_bar_changed", "panel": f,
                            "detail": f"scale bar {'added' if nw['scale_bar'] else 'removed'} on '{f}'"})
        elif o["scale_bar"] and nw["scale_bar"] and o["scale_bar"] != nw["scale_bar"]:
            changes.append({"type": "scale_bar_changed", "panel": f,
                            "detail": f"scale bar on '{f}': {o['scale_bar']} -> {nw['scale_bar']}"})
        if o["labels"] != nw["labels"]:
            changes.append({"type": "label_changed", "panel": f,
                            "detail": f"labels on '{f}': {o['labels']} -> {nw['labels']}"})
        if o["adjustments"] != nw["adjustments"]:
            added_adj = sorted(set(nw["adjustments"]) - set(o["adjustments"]))
            removed_adj = sorted(set(o["adjustments"]) - set(nw["adjustments"]))
            det = []
            if added_adj:
                det.append("added " + ", ".join(added_adj))
            if removed_adj:
                det.append("removed " + ", ".join(removed_adj))
            changes.append({"type": "adjustment_changed", "panel": f,
                            "detail": f"'{f}': " + "; ".join(det)})
        if o["px_to_unit"] != nw["px_to_unit"]:
            changes.append({"type": "pixel_size_changed", "panel": f,
                            "detail": f"pixel size on '{f}': {o['px_to_unit']} -> {nw['px_to_unit']}"})
    return changes


@mcp.tool()
def diff_figures(old_pyf: str, new_pyf: str) -> str:
    """Compare two versions of a figure and report **what changed** — the tool for
    revision rounds ("what did I change since submission?").

    Matches panels between the two files by source filename (and occurrence
    order) and reports, as structured JSON: panels **added / removed / moved /
    resized**, **scale-bar** changes (added/removed/length), **label / text**
    edits, **image-adjustment** changes (LUT, brightness/contrast, crop, rotation,
    flip, projection, custom script), **pixel-size** changes, and a **caption**
    change (from the sidecars). For a visual side-by-side with a pixel-difference
    overlay, use export_figure_diff.

    Example::

        diff_figures("figure1_submitted.pyf", "figure1_revised.pyf")
    """
    for p in (old_pyf, new_pyf):
        if not os.path.isfile(p):
            return f"ERROR: no such .pyf file: {p}"
    try:
        old_sigs = _diff_panel_signatures(old_pyf)
        new_sigs = _diff_panel_signatures(new_pyf)
    except Exception as e:
        return f"ERROR: could not analyse figures — {type(e).__name__}: {e}"

    changes = _match_and_diff(old_sigs, new_sigs)

    # caption change (sidecars)
    o_title, o_cap = _read_caption(old_pyf)
    n_title, n_cap = _read_caption(new_pyf)
    if (o_title, o_cap) != (n_title, n_cap):
        if not (o_title or o_cap):
            det = "caption added"
        elif not (n_title or n_cap):
            det = "caption removed"
        else:
            det = "caption text edited"
        changes.append({"type": "caption_changed", "panel": None, "detail": det})

    by_type: dict = {}
    for c in changes:
        by_type[c["type"]] = by_type.get(c["type"], 0) + 1

    return json.dumps({
        "old": os.path.basename(old_pyf),
        "new": os.path.basename(new_pyf),
        "panels_old": len(old_sigs),
        "panels_new": len(new_sigs),
        "n_changes": len(changes),
        "changes_by_type": by_type,
        "changes": changes,
        "summary": (f"{len(changes)} change(s) between {os.path.basename(old_pyf)} and "
                    f"{os.path.basename(new_pyf)}." if changes
                    else f"No differences detected between {os.path.basename(old_pyf)} "
                         f"and {os.path.basename(new_pyf)}."),
    }, ensure_ascii=False, indent=2)


def _png_data_uri(path: str) -> str:
    import base64
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")


def _make_pixel_diff(old_png: str, new_png: str, out_png: str, threshold: int = 20):
    """Write a diff overlay: the new render with pixels that differ from the old
    tinted red. Returns the fraction of pixels that changed."""
    import numpy as np
    from PIL import Image as PILImage
    oa = np.asarray(PILImage.open(old_png).convert("RGB"), dtype=np.int16)
    na = np.asarray(PILImage.open(new_png).convert("RGB"), dtype=np.int16)
    H = max(oa.shape[0], na.shape[0])
    W = max(oa.shape[1], na.shape[1])

    def _pad(arr):
        p = np.full((H, W, 3), 255, dtype=np.int16)
        p[:arr.shape[0], :arr.shape[1], :] = arr
        return p

    oa, na = _pad(oa), _pad(na)
    delta = np.abs(oa - na).max(axis=2)          # per-pixel max channel diff
    mask = delta > threshold
    base = na.astype(np.uint8)
    blended = base.copy()
    # 50% red tint where changed
    blended[mask] = (0.5 * base[mask] + 0.5 * np.array([255, 0, 0])).astype(np.uint8)
    PILImage.fromarray(blended).save(out_png)
    return float(mask.mean())


@mcp.tool()
def export_figure_diff(old_pyf: str, new_pyf: str, out_html: str, dpi: int = 150) -> str:
    """Export a **visual diff** of two figure versions as a self-contained HTML
    page — the revision-round companion to diff_figures.

    Renders both figures, embeds them side by side (submitted vs revised) plus a
    **pixel-difference overlay** (changed pixels tinted red), and lists every
    structural change (panels added/removed/moved/resized, scale-bar/label/
    adjustment/caption edits). One file, no external assets — open in any browser
    or attach to a response-to-reviewers.

    *out_html*: destination .html. *dpi*: render resolution (150 = screen).

    Example::

        export_figure_diff("fig1_submitted.pyf", "fig1_revised.pyf", "diff.html")
    """
    import html as _html
    for p in (old_pyf, new_pyf):
        if not os.path.isfile(p):
            return f"ERROR: no such .pyf file: {p}"
    if not out_html.lower().endswith((".html", ".htm")):
        return "ERROR: out_html must end in .html"
    out_html = os.path.abspath(out_html)

    tmp = tempfile.mkdtemp(prefix="pyf_diff_")
    old_png = os.path.join(tmp, "old.png")
    new_png = os.path.join(tmp, "new.png")
    diff_png = os.path.join(tmp, "diff.png")
    ok1, m1 = _run_render(old_pyf, old_png, dpi)
    ok2, m2 = _run_render(new_pyf, new_png, dpi)
    if not ok1 or not ok2:
        return f"ERROR: could not render figures — {m1 if not ok1 else m2}"
    try:
        changed_frac = _make_pixel_diff(old_png, new_png, diff_png)
    except Exception as e:
        return f"ERROR: could not compute pixel diff — {type(e).__name__}: {e}"

    diff = json.loads(diff_figures(old_pyf, new_pyf))
    rows = "\n".join(
        f'<li class="ch-{_html.escape(c["type"])}"><b>{_html.escape(c["type"])}</b>'
        f' — {_html.escape(c["detail"])}</li>'
        for c in diff["changes"]) or "<li>No structural changes detected.</li>"

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Figure diff: {_html.escape(diff['old'])} vs {_html.escape(diff['new'])}</title>
<style>
 body{{font-family:system-ui,Arial,sans-serif;margin:24px;color:#1a1a1a}}
 h1{{font-size:20px}} .sub{{color:#666;margin-bottom:16px}}
 .cols{{display:flex;gap:16px;flex-wrap:wrap;align-items:flex-start}}
 figure{{margin:0;flex:1 1 300px;min-width:260px}}
 figcaption{{font-size:12px;color:#555;margin-bottom:6px;font-weight:600}}
 img{{max-width:100%;border:1px solid #ddd;background:
   repeating-conic-gradient(#f4f4f4 0% 25%,#fff 0% 50%) 50%/16px 16px}}
 ul{{line-height:1.6;font-size:14px;padding-left:18px}}
 li b{{font-family:ui-monospace,Consolas,monospace;font-size:12px;color:#0a5}}
 .ch-panel_removed b,.ch-scale_bar_changed b{{color:#c0392b}}
 .ch-panel_added b{{color:#1e824c}}
</style></head><body>
<h1>Figure diff</h1>
<div class="sub">{_html.escape(diff['old'])} &rarr; {_html.escape(diff['new'])} &middot;
 {diff['n_changes']} change(s) &middot; {changed_frac*100:.1f}% of pixels differ</div>
<div class="cols">
 <figure><figcaption>Submitted (old)</figcaption><img src="{_png_data_uri(old_png)}"></figure>
 <figure><figcaption>Revised (new)</figcaption><img src="{_png_data_uri(new_png)}"></figure>
 <figure><figcaption>Difference (red = changed pixels)</figcaption><img src="{_png_data_uri(diff_png)}"></figure>
</div>
<h2>Changes ({diff['n_changes']})</h2>
<ul>{rows}</ul>
</body></html>"""
    try:
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(doc)
    except Exception as e:
        return f"ERROR: could not write HTML — {type(e).__name__}: {e}"
    return json.dumps({
        "output": out_html,
        "n_changes": diff["n_changes"],
        "changed_pixel_fraction": round(changed_frac, 4),
        "bytes": os.path.getsize(out_html),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def export_print_ready(
    pyf_path: str,
    out_path: str,
    color_mode: str = "cmyk",
    dpi: int = 300,
) -> str:
    """Export a print-ready raster of the figure — a high-DPI TIFF, optionally in
    CMYK, for journals that require it for the printed version.

    Renders the figure through the normal publication path (fonts are rasterised
    into the image, so they are inherently 'embedded') and writes a TIFF with the
    resolution tagged.

    *out_path*: output file (.tif / .tiff).
    *color_mode*: "cmyk" (default — many print workflows want CMYK) or "rgb".
    *dpi*: print resolution (>=300 recommended; 600 for line art).

    Note: the CMYK conversion is a naive, non-colour-managed RGB→CMYK (no ICC
    profile), fine for layout/proofing; for colour-critical print, do the final
    conversion in a colour-managed tool with the publisher's ICC profile. For a
    vector deliverable with embedded fonts, export a PDF via export_figure (Qt's
    PDF writer embeds fonts) or export_latex.

    Returns JSON with the output path, colour mode, dpi and size.
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    color_mode = color_mode.lower()
    if color_mode not in ("cmyk", "rgb"):
        return "ERROR: color_mode must be 'cmyk' or 'rgb'."
    if not out_path.lower().endswith((".tif", ".tiff")):
        return "ERROR: out_path must end in .tif or .tiff."
    if dpi < 100:
        return "ERROR: dpi must be at least 100."
    out_path = os.path.abspath(out_path)

    tmp_png = os.path.join(tempfile.mkdtemp(prefix="pyf_print_"), "render.png")
    ok, msg = _run_render(pyf_path, tmp_png, dpi)
    if not ok:
        return f"ERROR: could not render figure: {msg}"
    try:
        from PIL import Image as PILImage
        im = PILImage.open(tmp_png)
        if im.mode in ("RGBA", "P", "LA"):
            bg = PILImage.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        if color_mode == "cmyk":
            im = im.convert("CMYK")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        im.save(out_path, format="TIFF", dpi=(dpi, dpi), compression="tiff_lzw")
    except Exception as e:
        return f"ERROR: print export failed: {type(e).__name__}: {e}"
    return json.dumps({
        "output": out_path,
        "color_mode": color_mode.upper(),
        "dpi": dpi,
        "bytes": os.path.getsize(out_path),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def check_image_integrity(
    pyf_path: str,
    max_dim: int = 512,
    hamming_threshold: int = 6,
    block: int = 24,
    min_clones: int = 3,
) -> str:
    """Screen a figure's panels for image-integrity red flags before submission.

    Reads each panel's *source pixels* and reports three kinds of issue that
    journals and readers increasingly scrutinise:

      * **exact file reuse** - the identical image file used in two panels;
      * **cross-panel duplication** - one panel is a near-duplicate of another,
        including when it has been flipped, rotated 90/180/270 deg or
        contrast-inverted (common ways a reused blot/micrograph is disguised);
      * **within-panel cloning** - a textured region copy-pasted elsewhere in
        the same panel (copy-move retouching).

    This is a *screening aid, not proof of misconduct*: a flagged match can be
    perfectly legitimate (an intentional inset, a shared loading control, a
    montage of the same field). Always review flagged panels yourself.

    *max_dim*: panels are downscaled to this many px on the long edge before
    comparison (speed/robustness). *hamming_threshold*: 0-64, lower = stricter
    duplication matching (default 6 ~ 90%% similar). *block*: copy-move block
    size in px. *min_clones*: how many cloned block-pairs before a panel is
    flagged (raise to reduce false positives on repetitive textures).

    Returns a JSON report with the flagged pairs/panels, similarity scores, the
    detected transform, any load errors, and a plain-language summary.
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    if not 0 <= hamming_threshold <= 64:
        return "ERROR: hamming_threshold must be between 0 and 64."
    out_json = os.path.join(tempfile.mkdtemp(prefix="pyf_integrity_"), "report.json")
    # integrity_ops writes JSON to out_json (never stdout, which Fiji/JVM can
    # pollute); run it directly in a subprocess to isolate any loader crash.
    cmd = [sys.executable, "-m", "pyfigures.gui.integrity_ops", pyf_path, out_json,
           "--max-dim", str(max_dim), "--hamming-threshold", str(hamming_threshold),
           "--block", str(block), "--min-clones", str(min_clones)]
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=600)
    except subprocess.TimeoutExpired:
        return "ERROR: integrity analysis timed out after 600s"
    if proc.returncode != 0 or not os.path.isfile(out_json):
        return f"ERROR: {(proc.stderr or proc.stdout or 'integrity analysis failed').strip()}"
    with open(out_json, encoding="utf-8") as f:
        return f.read()


def _panel_letter_label(img: ET.Element):
    """Return the panel's letter label (a/b/…) if it carries one, else None."""
    annots = img.find("annotations")
    if annots is None:
        return None
    for a in annots.iter("TAText2D"):
        il = (a.findtext("is_letter") or "").strip()
        tx = a.findtext("text")
        if il in ("True", "b'True'") and tx:
            return _strip_tags(_decode(tx) or "").strip() or None
    return None


def _panel_adjustments(img: ET.Element):
    """Derive the list of pixel-affecting adjustments applied to one panel from
    its stored state. Returns (adjustments, is_nonlinear_or_custom)."""
    import ast

    def txt(tag):
        v = img.findtext(tag)
        return v.strip() if v is not None else None

    def is_set(v):
        return v not in (None, "", "None", "none", "b'None'")

    adj = []
    nonlinear = False

    # crop
    crops = {}
    for side in ("crop_left", "crop_right", "crop_top", "crop_bottom"):
        try:
            crops[side] = int(float(txt(side) or 0))
        except Exception:
            crops[side] = 0
    if any(crops.values()):
        adj.append({
            "type": "crop", "linear": True,
            "detail": {k: v for k, v in crops.items() if v},
            "text": "cropped (" + ", ".join(f"{k.split('_')[1]} {v}px"
                                             for k, v in crops.items() if v) + ")",
        })

    # rotation
    th = txt("theta")
    if is_set(th) and th not in ("0", "0.0"):
        adj.append({"type": "rotation", "linear": True,
                    "detail": {"degrees": th},
                    "text": f"rotated {th}°".replace("°", " deg")})

    # brightness/contrast = linear display-range normalization
    norm = txt("normalization")
    if is_set(norm):
        rng = None
        try:
            d = ast.literal_eval(norm)
            if isinstance(d, dict):
                lo = d.get("min_value", d.get("min"))
                hi = d.get("max_value", d.get("max"))
                if lo is not None and hi is not None:
                    rng = f"{lo}-{hi}"
        except Exception:
            pass
        adj.append({"type": "brightness_contrast", "linear": True,
                    "detail": {"display_range": rng or norm},
                    "text": "brightness/contrast adjusted (linear display range"
                            + (f" {rng}" if rng else "") + ")"})

    # per-channel min/max display ranges (alt encoding)
    if any(is_set(txt(t)) for t in ("lower_values", "upper_values")):
        adj.append({"type": "brightness_contrast", "linear": True,
                    "detail": {"lower_values": txt("lower_values"),
                               "upper_values": txt("upper_values")},
                    "text": "per-channel display range (brightness/contrast) set"})

    # pseudo-colour LUT
    luts = txt("LUTs")
    if is_set(luts):
        adj.append({"type": "lut", "linear": True,
                    "detail": {"LUTs": _decode(luts)},
                    "text": "pseudo-coloured with a LUT"})

    # Z / t projection
    proj = txt("projection")
    if is_set(proj):
        zs, ze = txt("projection_z_start"), txt("projection_z_end")
        rng = f" slices {zs}-{ze}" if is_set(zs) and is_set(ze) else ""
        adj.append({"type": "projection", "linear": True,
                    "detail": {"projection": _decode(proj), "z_start": zs, "z_end": ze},
                    "text": f"{_decode(proj)}-intensity projection{rng}"})

    # channel subset
    ch = txt("channels")
    if is_set(ch) and _decode(ch) not in (None, "None"):
        adj.append({"type": "channels", "linear": True,
                    "detail": {"channels": _decode(ch)},
                    "text": "channel subset selected"})

    # multi-series selection
    serie = txt("serie_to_open")
    if is_set(serie):
        adj.append({"type": "series", "linear": True,
                    "detail": {"serie_to_open": serie},
                    "text": f"series {serie} of a multi-series file"})

    # custom loading script: known channel merge, benign flip, or arbitrary code
    script = img.findtext("custom_loading_script")
    merge = _parse_channel_merge_script(_decode(script)) if script else None
    if merge is not None:
        names = " + ".join(os.path.basename(f) for f in merge["files"])
        adj.append({"type": "channel_merge", "linear": True,
                    "detail": {"files": merge["files"], "mode": merge["mode"],
                               "normalization": merge["normalization"]},
                    "text": f"channels merged ({merge['mode']}: {names})"})
        if merge["normalization"] == "per_channel":
            adj.append({"type": "brightness_contrast", "linear": True,
                        "detail": {"display_range": "per-channel min-max"},
                        "text": "each channel linearly rescaled to its own min-max "
                                "(brightness/contrast)"})
        return adj, nonlinear
    if script and script.strip() not in ("", "None"):
        low = script.lower()
        flip_h = "arr[:, ::-1]" in script
        flip_v = "arr[::-1, :]" in script
        looks_like_flip_only = "# flip" in low and "self.img = fig" in low
        if flip_h or flip_v:
            dirs = []
            if flip_h:
                dirs.append("horizontal")
            if flip_v:
                dirs.append("vertical")
            adj.append({"type": "flip", "linear": True,
                        "detail": {"directions": dirs},
                        "text": f"mirrored ({'/'.join(dirs)})"})
            if "_lo, _hi = arr.min(), arr.max()" in script:
                adj.append({"type": "brightness_contrast", "linear": True,
                            "detail": {"display_range": "min-max (non-8-bit sources)"},
                            "text": "if the source is not 8-bit, intensities linearly "
                                    "rescaled to its min-max for display"})
        if not looks_like_flip_only:
            nonlinear = True
            adj.append({"type": "custom_script", "linear": False,
                        "detail": {"note": "arbitrary custom loading/processing script"},
                        "text": "CUSTOM loading/processing script applied — verify it "
                                "performs no non-linear or region-selective manipulation"})
    return adj, nonlinear


@mcp.tool()
def export_adjustment_ledger(pyf_path: str) -> str:
    """Produce an image-adjustment provenance ledger for the figure — a per-panel
    record of every pixel-affecting operation, plus a ready-to-paste Methods
    paragraph. Journals require disclosure of image adjustments (brightness/
    contrast, LUTs, rotation, cropping, etc.); this reconstructs them from what
    is actually stored in the figure so nothing is forgotten.

    Reports, for each panel: the adjustments applied (crop, rotation, flip,
    linear brightness/contrast display range, pseudo-colour LUT, Z/t projection,
    channel/series selection, or a custom processing script), whether they are
    all linear + whole-image, and flags panels that use a custom script (which
    must be checked for non-linear or selective manipulation).

    Also checks whether panels that share a LUT use *inconsistent* display
    ranges — journals expect the same adjustment across compared panels.

    Returns JSON with per-panel adjustments, a plain-language ``methods_paragraph``
    you can adapt for your manuscript, and any integrity ``flags``. This is a
    disclosure aid — it reports settings, it does not judge acceptability.
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    try:
        root = ET.parse(pyf_path).getroot()
    except Exception as e:
        return f"ERROR: could not parse .pyf: {type(e).__name__}: {e}"

    panels = []
    flags = []
    idx = 0
    lut_to_ranges: dict[str, set] = {}
    for img in root.iter("Image2D"):
        fn = _decode(img.findtext("filename"))
        script = _decode(img.findtext("custom_loading_script"))
        has_script = isinstance(script, str) and script.strip() not in ("", "None")
        merge = _parse_channel_merge_script(script) if has_script else None
        if fn == "@template@":
            continue
        if not fn or fn == "None":
            # file-less panels: data plots are charts, not image data; any other
            # scripted panel generates pixels and must be disclosed
            if not has_script or "from staplot import api" in script:
                continue
        adj, nonlinear = _panel_adjustments(img)
        label = _panel_letter_label(img)
        if fn and fn != "None":
            name = os.path.basename(fn)
        elif merge is not None:
            name = "merge of " + " + ".join(os.path.basename(f) for f in merge["files"])
        else:
            name = "(script-generated panel)"
        panels.append({
            "index": idx,
            "label": label,
            "file": name,
            "adjustments": adj,
            "all_linear": not nonlinear,
        })
        if nonlinear:
            flags.append(f"Panel {label or idx} ({name}) uses a custom processing "
                         f"script — verify no non-linear/selective manipulation.")
        # collect LUT->range pairs for consistency check
        lut = next((a["detail"].get("LUTs") for a in adj if a["type"] == "lut"), None)
        rng = next((a["detail"].get("display_range") for a in adj
                    if a["type"] == "brightness_contrast"), None)
        if lut:
            lut_to_ranges.setdefault(str(lut), set()).add(str(rng))
        idx += 1

    for lut, ranges in lut_to_ranges.items():
        real = {r for r in ranges if r not in ("None", None)}
        if len(real) > 1:
            flags.append(f"Panels sharing LUT {lut} use different display ranges "
                         f"({', '.join(sorted(real))}) — journals expect a consistent "
                         f"adjustment across compared panels.")

    # methods paragraph
    sentences = []
    for p in panels:
        who = f"Panel {p['label']}" if p["label"] else f"Panel {p['index']} ({p['file']})"
        if not p["adjustments"]:
            sentences.append(f"{who}: no adjustments.")
        else:
            sentences.append(f"{who}: " + "; ".join(a["text"] for a in p["adjustments"]) + ".")
    any_adj = any(p["adjustments"] for p in panels)
    any_custom = any(not p["all_linear"] for p in panels)
    lead = ("Image adjustments were applied to the entire image of each panel"
            + (" and, except where noted, were linear" if not any_custom
               else "; panels flagged below used a custom script that must be verified")
            + ". " if any_adj else "No image adjustments were applied. ")
    methods_paragraph = lead + " ".join(sentences)

    # statistics provenance (from the .stats.json sidecar written by add_data_plot
    # / add_significance_bracket_from_data) — feeds the Methods 'Statistical
    # analysis' sentence.
    stats_entries = _read_stats(pyf_path)
    tests_used: list[str] = []
    for s in stats_entries:
        if s.get("source") == "data_plot" and s.get("test"):
            if s.get("effects") is not None:                      # two-way ANOVA
                eff = "; ".join(f"{e['effect']} p={e['p']:.3g}"
                                for e in s["effects"] if e.get("p") is not None)
                tests_used.append(f"{s['test']} ({eff})" if eff else s["test"])
            elif s.get("r") is not None:                         # correlation
                tests_used.append(f"{s['test']} (r={s['r']:.3g}, "
                                  f"p={s.get('p', float('nan')):.3g}, n={s.get('n')})")
            else:                                                # group comparison
                corr = f", {s['correction']}" if s.get("correction") else ""
                tests_used.append(f"{s['test']}{corr}")
        elif s.get("source") == "significance_bracket" and s.get("test"):
            ga, gb = s.get("group_a", "A"), s.get("group_b", "B")
            tests_used.append(f"{s['test']} ({ga} vs {gb}, p={s.get('p', float('nan')):.4g})")
    stats_paragraph = ""
    if tests_used:
        uniq = list(dict.fromkeys(tests_used))
        stats_paragraph = ("Statistical analysis: " + "; ".join(uniq) + ". "
                           "Significance is indicated as * p<0.05, ** p<0.01, "
                           "*** p<0.001, **** p<0.0001; n.s., not significant.")

    return json.dumps({
        "panels_total": len(panels),
        "panels_adjusted": sum(1 for p in panels if p["adjustments"]),
        "panels_with_custom_script": sum(1 for p in panels if not p["all_linear"]),
        "panels": panels,
        "flags": flags,
        "methods_paragraph": methods_paragraph,
        "statistics": stats_entries,
        "statistics_methods_paragraph": stats_paragraph,
        "note": "Disclosure aid: reconstructed from the figure's stored state. "
                "Region-selective edits made outside PyFigures cannot be seen here.",
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def simulate_color_blindness(pyf_path: str, cvd_type: str = "deuteranopia",
                             out_path: str | None = None, dpi: int = 120,
                             max_dimension: int = 1400) -> Image:
    """Render a figure as a colour-blind reader would see it and return the image
    (pairs with the GUI's colour-blind assistant).

    Use this to check whether your colour choices stay distinguishable. *cvd_type*
    is "deuteranopia" (green-weak, most common), "protanopia" (red-weak) or
    "tritanopia" (blue-weak) — aliases like "red"/"green"/"blue" also work.
    Optionally pass *out_path* (.png) to also save the full-resolution simulated
    image. The returned preview is downscaled to *max_dimension* px.
    """
    if not os.path.isfile(pyf_path):
        raise ValueError(f"no such .pyf file: {pyf_path}")
    from pyfigures.cvd import resolve_type, simulate_array
    resolve_type(cvd_type)                      # validate early (raises on bad type)

    tmp = os.path.join(tempfile.mkdtemp(prefix="pyf_cvd_"), "fig.png")
    ok, msg = _run_render(pyf_path, tmp, dpi)
    if not ok:
        raise RuntimeError(f"could not render figure: {msg}")

    from PIL import Image as PILImage
    import numpy as np
    im = PILImage.open(tmp).convert("RGBA")
    sim = simulate_array(np.asarray(im), cvd_type)
    sim_im = PILImage.fromarray(sim, mode="RGBA")

    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        sim_im.save(os.path.abspath(out_path))

    preview = sim_im.copy()
    if max(preview.size) > max_dimension:
        preview.thumbnail((max_dimension, max_dimension), PILImage.LANCZOS)
    buf = io.BytesIO()
    preview.save(buf, format="PNG")
    return Image(data=buf.getvalue(), format="png")
