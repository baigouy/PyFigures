"""PyFigures MCP tools — keeping figures honest and consistent: changed-source
detection, copying a finished figure's style onto another one, and alt text
(accessibility description) for submission.
"""
from __future__ import annotations

import copy
import csv
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

from .app import mcp
from .core import (
    _all_groups,
    _child_text,
    _decode,
    _encode_str,
    _first_filename,
    _html_to_plain,
    _iter_panel_elements,
    _load,
    _read_caption,
    _read_stats,
    _save,
    _scalebar_info,
    _set_child_text,
    _top_groups,
)


# ---------------------------------------------------------------------------
# 3. changed source files
# ---------------------------------------------------------------------------
@mcp.tool()
def check_source_changes(pyf_path: str, accept: bool = False) -> str:
    """List source images / CSVs that changed (or disappeared) since the figure
    was last saved.

    PyFigures re-reads its sources every time a figure opens, so re-processing an
    image or editing a CSV silently changes the figure. Each save records a
    snapshot of the sources (size, date, content hash) in
    ``<figure>.sources.json``; this compares the files with it. Files that were
    only touched or copied (same content) are not reported.

    *accept*: record the current files as the new reference (what saving the
      figure also does).
    """
    from pyfigures.source_snapshot import compare, record, describe, figure_sources
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    sources = figure_sources(pyf_path)
    res = compare(pyf_path, sources)
    if not res["recorded"]:
        msg = (f"No snapshot yet for {os.path.basename(pyf_path)} (it is written when the "
               f"figure is saved) — {len(sources)} source file(s) found.")
        if accept:
            record(pyf_path, sources)
            msg += " Snapshot recorded now."
        return msg
    text = describe(res)
    if accept:
        record(pyf_path, sources)
    if not text:
        return (f"All {res['unchanged']} source file(s) are unchanged since the figure was "
                f"saved ({res['saved']})."
                + (f" {len(res['added'])} new source(s) since then." if res["added"] else ""))
    return text + ("\nAccepted: the current files are now the reference." if accept else
                   "\nReopen / re-render the figure to see the new versions; "
                   "call again with accept=true (or save the figure) to accept them.")


# ---------------------------------------------------------------------------
# 6. copy style from another figure
# ---------------------------------------------------------------------------
_STYLE_ASPECTS = ("fonts", "letters", "scale_bars", "spacing", "plots")
_PLOT_STYLE_FIELDS = ("publication_style", "publication_font_size", "publication_line_width",
                      "publication_font", "publication_svg_stroke_width")


def _letters(root):
    out = []
    for img in _iter_panel_elements(root):
        annots = img.find("annotations")
        if annots is None:
            continue
        for ta in annots.findall("TAText2D"):
            if (ta.findtext("is_letter") or "") in ("True", "b'True'"):
                out.append(ta)
    return out


def _panel_scalebars(root):
    out = []
    for img in _iter_panel_elements(root):
        annots = img.find("annotations")
        if annots is not None:
            out.extend(annots.findall("ScaleBar"))
    return out


def _retext(template_html: str, template_plain: str, new_plain: str) -> str | None:
    """Put *new_plain* into *template_html* in place of its text, keeping the
    styling (font, size, weight, colour). None if the text can't be located."""
    import html as _html
    for needle in (template_plain, _html.escape(template_plain, quote=False)):
        if needle and template_html.count(">" + needle + "<") == 1:
            return template_html.replace(">" + needle + "<",
                                         ">" + _html.escape(new_plain, quote=False) + "<")
    return None


def _group_depths(root):
    """{Group element: depth} (top-level groups = 0)."""
    depth = {}

    def walk(grp, d):
        depth[grp] = d
        content = grp.find("content")
        if content is not None:
            for c in content:
                if c.tag == "Group":
                    walk(c, d + 1)
    for g in _top_groups(root):
        walk(g, 0)
    return depth


@mcp.tool()
def copy_style(
    source_pyf: str,
    target_pyf: str,
    aspects: list[str] | None = None,
    dry_run: bool = False,
) -> str:
    """Make *target_pyf* look like *source_pyf* (e.g. a figure already accepted
    by the journal): same fonts, panel-letter style, scale-bar style, spacing
    and plot styling. Content (images, text, positions) is not touched.

    *aspects*: any of "fonts" (figure font + panel-letter font settings),
      "letters" (letter size / weight / colour / corner, letter case),
      "scale_bars" (bar colour, thickness, corner, label font/colour),
      "spacing" (gaps between panels, per nesting level),
      "plots" (publication style of chart panels: font, font size, line
      widths). Default: all.
    *dry_run*: report what would change without writing.
    """
    aspects = list(aspects) if aspects else list(_STYLE_ASPECTS)
    bad = [a for a in aspects if a not in _STYLE_ASPECTS]
    if bad:
        return f"ERROR: unknown aspect(s) {bad}; choose from {list(_STYLE_ASPECTS)}."
    for p in (source_pyf, target_pyf):
        if not os.path.isfile(p):
            return f"ERROR: no such .pyf file: {p}"
    _, src = _load(source_pyf, resolve=False)
    tree, tgt = _load(target_pyf)
    report = []

    if "fonts" in aspects:
        sf = src.find("SerializableQFont")
        if sf is None:
            report.append("fonts: the source has no stored font settings — skipped")
        else:
            tf = tgt.find("SerializableQFont")
            new = copy.deepcopy(sf)
            if tf is None:
                gp = tgt.find("SerializableGUIparameters")
                pos = list(tgt).index(gp) if gp is not None else len(tgt)
                tgt.insert(pos, new)
            else:
                tgt.insert(list(tgt).index(tf), new)
                tgt.remove(tf)
            fam = _decode(sf.findtext("family"))
            report.append(f"fonts: figure font {fam!r} {sf.findtext('size')} pt, "
                          f"letter corner {_decode(sf.findtext('placement'))!r}")

    if "letters" in aspects:
        s_letters = _letters(src)
        t_letters = _letters(tgt)
        if not s_letters:
            report.append("letters: the source has no panel letters — skipped")
        elif not t_letters:
            report.append("letters: the target has no panel letters — skipped "
                          "(add them first, e.g. add_corner_labels)")
        else:
            model = s_letters[0]
            m_html = _decode(model.findtext("text")) or ""
            m_plain = _html_to_plain(m_html).strip()
            upper = m_plain[:1].isupper() if m_plain else True
            m_place = model.findtext("placement")
            n = 0
            for ta in t_letters:
                plain = _html_to_plain(_decode(ta.findtext("text")) or "").strip()
                letter = plain.upper() if upper else plain.lower()
                new_html = _retext(m_html, m_plain, letter)
                if new_html is not None:
                    _set_child_text(ta, "text", _encode_str(new_html))
                if m_place:
                    _set_child_text(ta, "placement", m_place)
                n += 1
            report.append(f"letters: {n} letter(s) restyled like {m_plain!r} "
                          f"({'upper' if upper else 'lower'} case, {m_place})")

    if "scale_bars" in aspects:
        s_bars = _panel_scalebars(src)
        t_bars = _panel_scalebars(tgt)
        if not s_bars:
            report.append("scale_bars: the source has no scale bars — skipped")
        elif not t_bars:
            report.append("scale_bars: the target has no scale bars — skipped")
        else:
            model = s_bars[0]
            info = _scalebar_info(model)
            n = 0
            for sb in t_bars:
                for tag in ("color", "bar_color", "placement", "opacity"):
                    v = model.findtext(tag)
                    if v is not None:
                        _set_child_text(sb, tag, v)
                t_plain = _scalebar_info(sb)["label_plain"]
                new_html = _retext(info["label_html"], info["label_plain"].strip(), t_plain.strip()) \
                    if t_plain else None
                if new_html is not None:
                    sb.find("legend").text = new_html
                n += 1
            report.append(f"scale_bars: {n} bar(s) now {model.findtext('placement')}, colour "
                          f"#{int(float(info['bar_color'])) & 0xFFFFFF:06x}, label styled "
                          f"like {info['label_plain'].strip()!r}")

    if "spacing" in aspects:
        s_depth = _group_depths(src)
        by_level = {}
        for g, d in s_depth.items():
            try:
                by_level.setdefault(d, []).append(int(float(g.findtext("space"))))
            except (TypeError, ValueError):
                pass
        if not by_level:
            report.append("spacing: the source has no groups — skipped")
        else:
            common = {d: Counter(v).most_common(1)[0][0] for d, v in by_level.items()}
            deepest = max(common)
            n = 0
            for g, d in _group_depths(tgt).items():
                _set_child_text(g, "space", str(common.get(d, common[deepest])))
                n += 1
            sgp, tgp = src.find("SerializableGUIparameters"), tgt.find("SerializableGUIparameters")
            if sgp is not None and tgp is not None and sgp.findtext("space") is not None:
                _set_child_text(tgp, "space", sgp.findtext("space"))
            report.append(f"spacing: {n} group(s) set to "
                          + ", ".join(f"level {d}: {s}" for d, s in sorted(common.items())))

    if "plots" in aspects:
        charts = [i for i in _iter_panel_elements(src)
                  if "from staplot import api" in (_decode(i.findtext("custom_loading_script")) or "")]
        model = charts[0] if charts else next(iter(_iter_panel_elements(src)), None)
        if model is None:
            report.append("plots: the source has no panels — skipped")
        else:
            vals = {f: model.findtext(f) for f in _PLOT_STYLE_FIELDS if model.findtext(f) is not None}
            n = 0
            for img in _iter_panel_elements(tgt):
                for f, v in vals.items():
                    _set_child_text(img, f, v)
                n += 1
            report.append(f"plots: publication style of {n} panel(s) set to font "
                          f"{_decode(vals.get('publication_font'))!r} "
                          f"{vals.get('publication_font_size')} pt, lines "
                          f"{vals.get('publication_line_width')}")

    if not dry_run:
        _save(tree, target_pyf, recompute="spacing" in aspects)
    head = ("Would apply" if dry_run else "Applied") + \
        f" the style of {os.path.basename(source_pyf)} to {os.path.basename(target_pyf)}:"
    return head + "\n" + "\n".join("  " + r for r in report)


# ---------------------------------------------------------------------------
# 7. alt text
# ---------------------------------------------------------------------------
def _alt_path(pyf_path):
    return os.path.splitext(pyf_path)[0] + ".alttext.json"


_LUT_WORDS = {"GRAY": "grayscale", "GREY": "grayscale", "DEFAULT": "",
              "RED": "red", "GREEN": "green", "BLUE": "blue", "CYAN": "cyan",
              "MAGENTA": "magenta", "YELLOW": "yellow"}


def _lut_word(name):
    if not name or name == "None":
        return ""
    if name.upper() in _LUT_WORDS:
        return _LUT_WORDS[name.upper()]
    if name.upper().startswith("MATPLOTLIB_"):
        return name.split("_", 1)[1].rstrip("_r").replace("_", " ") + " colour map"
    return name.replace("_", " ").lower()


def _csv_groups(path, kind):
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except OSError:
        return []
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []
    header = [c.strip() for c in rows[0]]

    def isnum(s):
        try:
            float(s)
            return True
        except ValueError:
            return False
    body = rows[1:]
    if kind != "grouped" and len(header) == 2 and body and not isnum(body[0][0]) and isnum(body[0][1]):
        seen = []
        for r in body:
            if r and r[0].strip() and r[0].strip() not in seen:
                seen.append(r[0].strip())
        return seen
    return [h for h in header if h]


def _join(words):
    words = [w for w in words if w]
    if len(words) <= 1:
        return "".join(words)
    return ", ".join(words[:-1]) + " and " + words[-1]


def _panel_description(img, stats):
    """(kind, sentence) for one panel element."""
    from .content import _MERGE_MARKER
    from .stacks import _KYMO_MARK, _ORTHO_MARK
    import ast
    script = _decode(img.findtext("custom_loading_script")) or ""
    fn = _first_filename(img)
    comment = _decode(img.findtext("user_comments")) or ""
    annots = img.find("annotations")
    labels, extras = [], []
    if annots is not None:
        for ta in annots.findall("TAText2D"):
            if (ta.findtext("is_letter") or "") not in ("True", "b'True'"):
                t = _html_to_plain(_decode(ta.findtext("text")) or "").strip()
                if t:
                    labels.append(t)
        bars = annots.findall("ScaleBar")
        if bars:
            lab = _scalebar_info(bars[0])["label_plain"].strip()
            extras.append(f"scale bar {lab}" if lab else "a scale bar")
        from ..arrowheads import is_head_only
        arrows = [l for l in annots.findall("Line2D") if (l.findtext("arrow") or "") == "True"]
        heads = [l for l in arrows if is_head_only(*(l.findtext(k) or 0 for k in ("x1", "y1", "x2", "y2")), True)]
        n_arrows = len(arrows) - len(heads)
        if n_arrows:
            extras.append(f"{n_arrows} arrow{'s' if n_arrows > 1 else ''} marking features")
        if heads:
            extras.append(f"{len(heads)} arrowhead{'s' if len(heads) > 1 else ''} marking features")
        insets = annots.findall("Image2D")
        if insets:
            extras.append("a magnified inset" if len(insets) == 1 else f"{len(insets)} magnified insets")
        rois = [e for e in annots if e.tag in ("Rectangle2D", "Ellipse2D", "Polygon2D", "Freehand2D")]
        if rois:
            extras.append(f"{len(rois)} outlined region{'s' if len(rois) > 1 else ''}")

    if script.startswith(_MERGE_MARKER):
        m = re.search(r"^_colors = (.*)$", script, re.M)
        try:
            cols = ast.literal_eval(m.group(1)) if m else []
        except (ValueError, SyntaxError):
            cols = []
        names = {(1.0, 0.0, 0.0): "red", (0.0, 1.0, 0.0): "green", (0.0, 0.0, 1.0): "blue",
                 (1.0, 0.0, 1.0): "magenta", (0.0, 1.0, 1.0): "cyan", (1.0, 1.0, 0.0): "yellow",
                 (1.0, 1.0, 1.0): "gray", (0.502, 0.502, 0.502): "gray"}
        cw = [names.get(tuple(round(float(v), 3) for v in c), "") for c in cols]
        base = f"merged fluorescence image of {len(cols) or 'several'} channels"
        if cw and all(cw):
            base += f" ({_join(cw)})"
        kind = "merge"
    elif "from staplot import api" in script:
        m = re.search(r"kind=('[a-z]+')", script)
        pk = ast.literal_eval(m.group(1)) if m else "data"
        c = re.search(r"^_csv = (.*)$", script, re.M)
        csvp = ast.literal_eval(c.group(1)) if c else None
        groups = _csv_groups(csvp, pk) if csvp else []
        yl = re.search(r"ylabel=('(?:[^'\\]|\\.)*')", script)
        ylabel = ast.literal_eval(yl.group(1)) if yl else ""
        base = {"bar": "bar chart", "box": "box plot", "violin": "violin plot",
                "scatter": "scatter plot", "grouped": "grouped bar chart"}.get(pk, "chart")
        if ylabel:
            base += f" of {ylabel}"
        if groups and pk != "scatter":
            base += f" comparing {_join(groups[:8])}" + (" and others" if len(groups) > 8 else "")
        entry = next((s for s in stats if s.get("csv") == csvp), None)
        if entry and entry.get("test"):
            sig = [c for c in entry.get("comparisons") or [] if (c.get("p") or 1) < 0.05]
            base += f"; {entry['test']}"
            if entry.get("comparisons") is not None:
                base += (f", {len(sig)} significant difference{'s' if len(sig) != 1 else ''}"
                         if sig else ", no significant difference")
        kind = "plot"
    elif script.startswith(_KYMO_MARK):
        base, kind = "kymograph (position along a line against time, time downwards)", "kymo"
    elif script.startswith(_ORTHO_MARK):
        base, kind = "orthogonal views of a 3-D stack (XY with side views XZ and YZ)", "ortho"
    elif script and script != "None":
        base, kind = "computed image panel", "script"
    elif fn:
        luts = _decode(img.findtext("LUTs"))
        try:
            luts = ast.literal_eval(luts) if isinstance(luts, str) and luts != "None" else None
        except (ValueError, SyntaxError):
            luts = None
        chans = _decode(img.findtext("channels"))
        try:
            chans = ast.literal_eval(chans) if isinstance(chans, str) and chans != "None" else None
        except (ValueError, SyntaxError):
            chans = None
        words = []
        if luts:
            shown = [l for i, l in enumerate(luts) if not chans or (i < len(chans) and chans[i])]
            words = [_lut_word(l) for l in shown]
        words = [w for w in words if w]
        proj = _decode(img.findtext("projection"))
        base = "micrograph"
        if words:
            base = (f"{words[0]} micrograph" if len(words) == 1
                    else f"micrograph with {_join(words)} channels")
        if proj and proj not in ("None", ""):
            base = f"{proj}-intensity projection " + base
        kind = "image"
    else:
        base, kind = "empty panel", "empty"
    if comment.startswith("[series "):
        kind = "series:" + kind
    return kind, base, labels, extras


@mcp.tool()
def generate_alt_text(pyf_path: str, save: bool = False) -> str:
    """Draft alt text (an accessibility description of the figure for readers
    using screen readers — requested by a growing number of journals) from the
    figure's own content: panel letters, what each panel is (micrograph and its
    colours, merge, montage, chart type and compared groups with the recorded
    statistics, kymograph…), labels, scale bars and arrows, plus the caption
    title.

    Returns {"short": one sentence (< 250 characters), "long": panel by panel}.
    Review and edit it — it describes structure, not the biological finding.
    *save*: store it in ``<figure>.alttext.json`` (else use set_alt_text).
    """
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    _, root = _load(pyf_path)
    stats = _read_stats(pyf_path)
    title, _cap = _read_caption(pyf_path)
    from .core import _is_empty_placeholder
    panels = []          # [letter, kind, base, labels, extras, count]
    for img in _iter_panel_elements(root):
        if _is_empty_placeholder(img):
            continue                    # padding of a grid / montage row: not a panel
        annots = img.find("annotations")
        letter = ""
        if annots is not None:
            for ta in annots.findall("TAText2D"):
                if (ta.findtext("is_letter") or "") in ("True", "b'True'"):
                    letter = _html_to_plain(_decode(ta.findtext("text")) or "").strip().strip("().")
                    break
        kind, base, labels, extras = _panel_description(img, stats)
        comment = _decode(img.findtext("user_comments")) or ""
        # a montage / channel split is described once; each split panel has
        # its own letter ("Panels B–D: the same field shown channel by channel")
        if kind.startswith("series:") and not comment.startswith("[series 1/") and panels \
                and panels[-1][1].startswith("series:"):
            prev = panels[-1]
            if comment.endswith(": merge"):
                prev[7] = True               # the split's merge panel: not a channel
            else:
                prev[3].extend(labels)
            prev[5] += 1
            if letter:
                prev[8].append(letter)
            if extras:
                prev[4][:] = sorted(set(prev[4]) | set(extras))
            continue
        panels.append([letter, kind, base, labels, extras, 1, comment, False, [letter] if letter else []])

    parts = []
    for letter, kind, base, labels, extras, count, comment, has_merge, letters in panels:
        who = f"Panel {letter}" if letter else "A panel"
        if len(letters) > 1:
            who = f"Panels {letters[0]}–{letters[-1]}"
        if kind.startswith("series:"):
            if "montage of" in comment:
                what = f"a montage of {count} frames" + (f" ({labels[0]} to {labels[-1]})" if len(labels) > 1 else "")
                if "z=" in comment:
                    what = f"a series of {count} Z sections" + (f" ({labels[0]} to {labels[-1]})" if len(labels) > 1 else "")
            elif "channel split" in comment:
                n_ch = count - (1 if has_merge else 0)
                what = (f"the same field shown channel by channel ({_join(labels)})" if labels
                        else f"{n_ch} single-channel views")
                if has_merge:
                    what += ", then merged"
            else:
                what = f"a series of {count} {base}s"
            sentence = f"{who}: {what}"
        else:
            sentence = f"{who}: {base}"
            if labels:
                sentence += f", labelled {_join(labels)}"
        if extras:
            sentence += f", with {_join(extras)}"
        parts.append(sentence + ".")

    n = sum(max(1, len(p[8])) for p in panels)      # lettered panels (a split has several)
    kinds = Counter(p[1] for p in panels if not p[1].startswith("series:"))
    what = []
    for k, word in (("image", "micrograph"), ("merge", "merged image"), ("plot", "chart"),
                    ("kymo", "kymograph"), ("ortho", "orthogonal view")):
        if kinds.get(k):
            what.append(f"{kinds[k]} {word}{'s' if kinds[k] > 1 else ''}")
    series = sum(1 for p in panels if p[1].startswith("series:"))
    if series:
        what.append(f"{series} image series")
    lead = (f"{title.rstrip('.')}: " if title else "") + \
        f"figure with {n} panel{'s' if n != 1 else ''}" + (f" ({_join(what)})" if what else "") + "."
    short = lead if len(lead) <= 250 else lead[:247].rstrip() + "…"
    long_text = lead + " " + " ".join(parts)
    out = {"short": short, "long": long_text, "panels": n}
    if save:
        with open(_alt_path(pyf_path), "w", encoding="utf-8") as f:
            json.dump({"short": short, "long": long_text}, f, ensure_ascii=False, indent=2)
        out["saved"] = _alt_path(pyf_path)
    return json.dumps(out, ensure_ascii=False, indent=2)


@mcp.tool()
def set_alt_text(pyf_path: str, long: str, short: str | None = None) -> str:
    """Store the figure's alt text (after reviewing / editing the draft from
    generate_alt_text) in ``<figure>.alttext.json``. *short* defaults to the
    first sentence of *long*."""
    if not os.path.isfile(pyf_path):
        return f"ERROR: no such .pyf file: {pyf_path}"
    long = (long or "").strip()
    if not long:
        return "ERROR: alt text is empty."
    if short is None:
        short = re.split(r"(?<=[.!?])\s", long, maxsplit=1)[0]
    with open(_alt_path(pyf_path), "w", encoding="utf-8") as f:
        json.dump({"short": short.strip(), "long": long}, f, ensure_ascii=False, indent=2)
    return f"Alt text saved to {_alt_path(pyf_path)} ({len(long)} characters)."


def read_alt_text(pyf_path: str) -> dict | None:
    try:
        with open(_alt_path(pyf_path), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# call history and undo (pyfigures/history.py)
# ---------------------------------------------------------------------------
@mcp.tool()
def list_history(pyf_path: str, last: int = 20) -> str:
    """List the MCP calls made on a figure, newest last: tool, arguments,
    status, whether it changed the figure and whether it was undone.

    Every MCP call that names a figure is logged beside it (in
    <figure>.history/), with the figure as it was before each changing call,
    so the user can see what was done and undo it (undo_last). Read-only."""
    from pyfigures import history
    return history.describe(pyf_path, last)


@mcp.tool()
def undo_last(pyf_path: str, steps: int = 1, force: bool = False) -> str:
    """Undo the last *steps* changing MCP calls on a figure: the .pyf and its
    sidecars (caption, statistics, alt text, target) go back to their state
    before those calls. The undo is logged too.

    Refused when the figure was changed since by something that is not logged
    (the GUI, another program), because restoring would drop that change; pass
    force=True only if the user agrees to lose it. Use list_history first to
    see what will be undone."""
    from pyfigures import history
    return history.undo_last(pyf_path, steps, force)


# ---------------------------------------------------------------------------
# the server itself (pyfigures/mcp_control.py)
# ---------------------------------------------------------------------------
@mcp.tool()
def mcp_server_info() -> str:
    """How this PyFigures MCP server is set up: the Python running it, the
    number of tools, which MCP clients have it registered (Claude Code /
    Claude Desktop / LM Studio start it themselves when needed) and whether
    the HTTP server is running. Read-only: registering, starting and stopping
    are done by the user (GUI Tools > MCP server…, or
    python -m pyfigures.mcp_control)."""
    from pyfigures import mcp_control
    n_tools = len(mcp._tool_manager.list_tools())
    return (f"PyFigures MCP server, {n_tools} tools, Python {sys.executable}\n"
            + mcp_control.describe())


# ---------------------------------------------------------------------------
# bug recordings (GUI Help > Debug > Record a bug; pyfigures/gui/bug_recorder.py)
# ---------------------------------------------------------------------------
@mcp.tool()
def list_bug_recordings(folder: str | None = None) -> str:
    """The bug recordings the user made in the GUI (Help > Debug > Start
    recording a bug…), newest first: folder, date, number of steps, Python
    errors caught and what the user said went wrong. *folder*: another
    recordings folder (default: the user's own, outside any source tree).
    Read one with read_bug_recording."""
    from pyfigures.gui.bug_recorder import list_recordings, recordings_dir
    recs = list_recordings(folder)
    return json.dumps({"folder": folder or recordings_dir(), "recordings": recs},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def read_bug_recording(path: str) -> str:
    """One bug recording, step by step: what the user did (menu actions,
    right-click / drop-menu choices, drops, dialogs with their values, file
    pickers, canvas double-clicks and drags), the figure's rows after each
    step, Python errors with tracebacks, the steps the user ticked as wrong,
    what went wrong and what was expected, and the screenshot of each step
    (paths: open them to see). The starting figure is start.pyf in the
    folder. A regression test is made from it with
    python -m pyfigures.gui.bug_recorder make-test <folder> <tests/recordings/name>."""
    from pyfigures.gui.bug_recorder import read_recording
    if not os.path.exists(path):
        return f"ERROR: no such recording: {path}"
    try:
        return json.dumps(read_recording(path), ensure_ascii=False, indent=1)
    except (OSError, ValueError, KeyError) as e:
        return f"ERROR: could not read {path}: {e}"
