"""“Show me how”: short guides that teach one operation in the running GUI.

An MCP client (or the command line, or Help → Show me how…) picks an
authored guide by its id; the GUI then highlights the real menus and controls
in a floating, closable bubble and the *user* performs the clicks. Showing a
guide never edits the figure.

Three modes stay distinct:

* **Do it**: the ordinary MCP tools edit the figure.
* **Show me how**: :func:`show` opens the guide in the running GUI.
* **Explain**: :func:`explain` returns the same authored steps as text, with no
  GUI needed.

This module has no Qt dependency. The guide registry lives here; the GUI side
(``pyfigures.gui.show_me_how``) builds the highlighted steps from it, and each
GUI window opens a small local mailbox that :func:`show`, :func:`status` and
:func:`close` write requests to::

    ~/.pyfigures/gui_sessions/<pid>_<token>/session.json     (written by the GUI)
    ~/.pyfigures/gui_sessions/<pid>_<token>/<id>.request.json  (written here)
    ~/.pyfigures/gui_sessions/<pid>_<token>/<id>.response.json (GUI's answer)

A request must carry the session's random token and is refused after 30 s;
it can only name a guide from the registry (never code, coordinates or
arbitrary menu paths).

Command line::

    python -m pyfigures.guides list
    python -m pyfigures.guides explain "crop an image"
    python -m pyfigures.guides show split_channels [--figure fig.pyf]
    python -m pyfigures.guides status
    python -m pyfigures.guides close
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Step kinds (the GUI turns each into one or more highlighted steps):
#   {"select": "image" | "channel_image"}      click a panel first
#   {"menu": [top, sub, ..., action]}           one highlighted step per level
#   {"context": "text"}                         right-click route (canvas highlighted)
#   {"dialog": "text"}                          what to do in the dialog that opened
# "done" names the result the GUI watches for (see gui/show_me_how.py):
#   split_created, scalebar_added, inset_added, lut_changed, crop_changed,
#   panel_added, dialog_closed.

GUIDES: dict[str, dict] = {
    "split_channels": {
        "title": "Split channels (each channel + merge)",
        "summary": "Turn a multi-channel image into a row of single channels plus a merge.",
        "keywords": ["split", "channel", "channels", "separate", "merge row", "rgb"],
        "steps": [
            {"select": "channel_image",
             "text": "Click the multi-channel image you want to split. The guide does not "
                     "select or change it for you."},
            {"menu": ["Annotations", "Stack views", "Channel split (each channel + merge)…"]},
            {"dialog": "Name the channels, choose their colours and keep <b>Add the merge</b> "
                       "checked if you want it. Click <b>Ok</b>. A new row is added; the "
                       "original panel stays."},
        ],
        "alternative": "Right-click the image → Split ▶ → Channel split (Gray mode) or "
                       "(Magenta/Green mode).",
        "done": "split_created",
        "mcp": "add_channel_split",
    },
    "add_scale_bars": {
        "title": "Add scale bars to every panel",
        "summary": "Add a calibrated scale bar to all image panels at once.",
        "keywords": ["scale bar", "scalebar", "scale", "bar", "micron", "µm", "um", "calibration"],
        "steps": [
            {"menu": ["Annotations", "Add scale bar to all panels…"]},
            {"dialog": "Enter the pixel size and the bar length (for example 10 µm), choose "
                       "the corner, then click <b>Ok</b>."},
        ],
        "alternative": "One panel only: double-click it (Edit Image) and use its scale-bar "
                       "settings.",
        "done": "scalebar_added",
        "mcp": "set_scale_bar_all",
    },
    "zoom_inset": {
        "title": "Add a zoom inset (magnified detail)",
        "summary": "Box a region of a panel and show it magnified in a corner with leader lines.",
        "keywords": ["zoom", "inset", "magnify", "magnified", "callout", "detail", "enlarge region"],
        "steps": [
            {"select": "image", "text": "Click the panel that holds the detail you want to magnify."},
            {"menu": ["Annotations", "Add zoom callout to selected panel…"]},
            {"dialog": "Set the region (x, y, width, height in image pixels), the corner and "
                       "the inset size, then click <b>Ok</b>."},
        ],
        "alternative": "Double-click the panel → Annotations tab: draw a rectangle, then "
                       "<b>Rect ROI → Inset</b>.",
        "done": "inset_added",
        "mcp": "add_zoom_callout",
    },
    "set_lut": {
        "title": "Change channel colours (LUTs)",
        "summary": "Choose the colour of each channel (for example magenta and green).",
        "keywords": ["lut", "luts", "colour", "color", "colours", "colors", "magenta", "green",
                     "pseudocolour", "recolour", "recolor"],
        "steps": [
            {"select": "image", "text": "Click the image whose colours you want to change."},
            {"context": "<b>Right-click</b> the selected image, open <b>Appearance ▶</b> and "
                        "choose <b>Set LUT(s)</b>."},
            {"dialog": "Pick a colour for each channel and click <b>Ok</b>. For a channel "
                       "split, changing the merge also recolours the channel names."},
        ],
        "alternative": "Appearance ▶ → Reset LUT(s) goes back to the original colours.",
        "done": "lut_changed",
        "mcp": "set_lut",
    },
    "crop_image": {
        "title": "Crop or rotate a panel",
        "summary": "Trim pixels from the edges of a panel (for example burned-in text) or rotate it.",
        "keywords": ["crop", "trim", "cut", "rotate", "rotation", "edges", "remove text", "footer"],
        "steps": [
            {"select": "image", "text": "Click the panel you want to crop."},
            {"context": "<b>Double-click</b> the selected panel (or right-click → <b>Edit "
                        "Image</b>) to open the image editor."},
            {"dialog": "Open the <b>Rotate + Crop</b> tab, enter how many pixels to remove from "
                       "each side (or an angle), then click <b>Ok</b>."},
        ],
        "alternative": "Right-click a row → Crop & size ▶ to give all panels the same crop.",
        "done": "crop_changed",
        "mcp": "transform_image",
    },
    "panel_letters": {
        "title": "Panel letters (A, B, C…)",
        "summary": "Set the style and position of the automatic panel letters.",
        "keywords": ["letter", "letters", "lettering", "label panels", "a b c", "panel labels"],
        "steps": [
            {"menu": ["Lettering", "Parameters"]},
            {"dialog": "Choose the letter style, size and corner, then click <b>Ok</b>. "
                       "Automatic lettering is the checkbox in the toolbar."},
        ],
        "alternative": "Right-click a panel → Text & lettering ▶ → Change lettering parameters.",
        "done": "dialog_closed",
        "mcp": "add_corner_labels",
    },
    "add_data_plot": {
        "title": "Add a data plot from a CSV",
        "summary": "Make a box/bar/scatter plot panel (with statistics) from a CSV file.",
        "keywords": ["plot", "graph", "chart", "csv", "box plot", "bar plot", "statistics", "stats"],
        "steps": [
            {"menu": ["Annotations", "Add data plot from CSV…"]},
            {"dialog": "Pick the CSV, the plot type and the statistics options, then click "
                       "<b>Ok</b>. The plot is added as a new panel."},
        ],
        "alternative": "",
        "done": "panel_added",
        "mcp": "add_data_plot",
    },
    "channel_merge": {
        "title": "Merge single-channel images",
        "summary": "Overlay separate single-channel images into one coloured composite.",
        "keywords": ["merge", "overlay", "composite", "combine channels"],
        "steps": [
            {"menu": ["Annotations", "Add multi-channel merge…"]},
            {"dialog": "Choose the channel images and their colours, then click <b>Ok</b>."},
        ],
        "alternative": "",
        "done": "panel_added",
        "mcp": "add_channel_merge",
    },
    "journal_check": {
        "title": "Check a figure against a journal",
        "summary": "Check width, fonts, scale bars and labels against a journal's rules.",
        "keywords": ["journal", "compliance", "submission", "ready", "guidelines", "nature",
                     "science", "cell", "pnas", "check"],
        "steps": [
            {"menu": ["QC", "Check journal compliance…"]},
            {"dialog": "Choose the journal and column width and read the PASS/FAIL report."},
        ],
        "alternative": "QC → Apply journal guidelines… resizes and fixes fonts in one go.",
        "done": "dialog_closed",
        "mcp": "check_journal_compliance",
    },
    "apply_journal": {
        "title": "Resize a figure for a journal",
        "summary": "Resize to a journal column width and raise fonts to its minimum.",
        "keywords": ["resize", "width", "column", "journal", "apply guidelines", "double column",
                     "single column"],
        "steps": [
            {"menu": ["QC", "Apply journal guidelines…"]},
            {"dialog": "Choose the journal (or a style you imported) and the column, then click "
                       "<b>Ok</b>."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "apply_journal_guidelines",
    },
    "check_resolution": {
        "title": "Check print resolution (DPI)",
        "summary": "See the printed DPI of each panel at the figure's size.",
        "keywords": ["dpi", "resolution", "pixelated", "print"],
        "steps": [
            {"menu": ["QC", "Check print resolution…"]},
            {"dialog": "Read the DPI of each panel; panels below the limit are listed first."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "check_resolution",
    },
    "export_pptx": {
        "title": "Export to editable PowerPoint",
        "summary": "Save the figure as a PowerPoint file with editable text and playable movies.",
        "keywords": ["powerpoint", "pptx", "ppt", "slides", "editable", "export"],
        "steps": [
            {"menu": ["File", "Export As", "PowerPoint (editable)…"]},
            {"dialog": "Choose where to save the .pptx and click <b>Save</b>."},
        ],
        "alternative": "File → Export As → PDF / SVG / PNG / TIF for other formats.",
        "done": "dialog_closed",
        "mcp": "export_pptx",
    },
    "figure_caption": {
        "title": "Write the figure caption",
        "summary": "Write or edit the caption/legend stored beside the figure.",
        "keywords": ["caption", "legend", "figure legend", "text below"],
        "steps": [
            {"menu": ["File", "Figure caption / legend…"]},
            {"dialog": "Type the caption and click <b>Ok</b>; it is saved beside the .pyf."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "set_figure_caption",
    },
    "presubmission_review": {
        "title": "Run all pre-submission checks",
        "summary": "Run every check (journal, resolution, scale bars, integrity) in one report.",
        "keywords": ["review", "all checks", "pre-submission", "presubmission", "qc", "audit"],
        "steps": [
            {"menu": ["QC", "Pre-submission review (all checks)…"]},
            {"dialog": "Read the report; each problem says how to fix it."},
        ],
        "alternative": "",
        "done": "dialog_closed",
        "mcp": "figure_review_brief",
    },
    "colour_blind_preview": {
        "title": "Preview for colour-blind readers",
        "summary": "See the figure as readers with colour-vision deficiencies see it.",
        "keywords": ["colour blind", "color blind", "colorblind", "deuteranopia", "accessibility",
                     "cvd"],
        "steps": [
            {"menu": ["Help", "Preview figure under colour-blindness…"]},
            {"dialog": "Compare the simulated views; avoid red/green pairs that look alike."},
        ],
        "alternative": "Help → Show color-blind assistant suggests safe palettes.",
        "done": "dialog_closed",
        "mcp": "simulate_color_blindness",
    },
}

_WORD = re.compile(r"[a-zµ0-9]+")


def _norm(text: str) -> str:
    return " ".join(_WORD.findall(str(text).lower()))


def find_guide(query: str) -> tuple[str | None, list[str]]:
    """(guide_id, candidates) for an id or a free-text request ("show me how
    to crop"). guide_id is None when nothing matches or the request is
    ambiguous; candidates then lists the best matches."""
    q = str(query or "").strip()
    if q in GUIDES:
        return q, [q]
    key = q.lower().replace("-", "_").replace(" ", "_")
    if key in GUIDES:
        return key, [key]
    words = _norm(q)
    if not words:
        return None, []
    scores = {}
    for gid, g in GUIDES.items():
        score = 0
        for kw in g["keywords"]:
            k = _norm(kw)
            if k and re.search(r"\b" + re.escape(k) + r"\b", words):
                score += 2 if " " in k else 1
        for w in _norm(g["title"]).split():
            if len(w) > 3 and re.search(r"\b" + re.escape(w) + r"\b", words):
                score += 1
        if score:
            scores[gid] = score
    if not scores:
        return None, []
    ranked = sorted(scores, key=lambda g: -scores[g])
    best = scores[ranked[0]]
    tied = [g for g in ranked if scores[g] == best]
    return (ranked[0] if len(tied) == 1 else None), ranked[:4]


def step_texts(guide_id: str) -> list[str]:
    """The guide's steps as plain instructions (the same text the GUI shows)."""
    g = GUIDES[guide_id]
    out = []
    for s in g["steps"]:
        if "menu" in s:
            out.append("Choose " + " → ".join(s["menu"]) + ".")
        else:
            text = s.get("text") or s.get("context") or s.get("dialog") or ""
            out.append(re.sub(r"<[^>]+>", "", text))
    if g.get("alternative"):
        out.append("Alternative: " + re.sub(r"<[^>]+>", "", g["alternative"]))
    return out


def list_guides() -> list[dict]:
    return [{"id": gid, "title": g["title"], "summary": g["summary"],
             "do_it_tool": g.get("mcp", "")} for gid, g in GUIDES.items()]


def explain(query: str) -> dict:
    """Explain mode: the authored steps as text (no GUI needed)."""
    gid, cands = find_guide(query)
    if gid is None:
        return {"status": "unknown_operation" if not cands else "ambiguous",
                "candidates": cands, "available": list(GUIDES)}
    g = GUIDES[gid]
    return {"status": "explained", "guide": gid, "title": g["title"],
            "steps": step_texts(gid), "do_it_tool": g.get("mcp", ""),
            "operation_executed": False}


# ---------------------------------------------------------------------------
# Mailbox client (talks to the GUI windows)
# ---------------------------------------------------------------------------

def sessions_root() -> str:
    """Where GUI windows open their mailboxes (PYFIGURES_GUI_SESSIONS overrides)."""
    return (os.environ.get("PYFIGURES_GUI_SESSIONS")
            or os.path.join(os.path.expanduser("~"), ".pyfigures", "gui_sessions"))


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
    except ImportError:          # cannot tell: trust the session file
        return True
    return psutil.pid_exists(int(pid))


def live_sessions() -> list[dict]:
    """Running GUI windows that accept guides, newest first. Folders of
    windows that are gone (crash) are removed."""
    root = sessions_root()
    out = []
    try:
        names = os.listdir(root)
    except OSError:
        return []
    for name in names:
        folder = os.path.join(root, name)
        path = os.path.join(folder, "session.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not _pid_alive(data.get("pid", 0)):
            try:
                import shutil
                shutil.rmtree(folder, ignore_errors=True)
            except Exception:
                pass
            continue
        data["folder"] = folder
        out.append(data)
    out.sort(key=lambda d: -float(d.get("created", 0)))
    return out


def _pick_session(figure_path: str | None):
    sessions = live_sessions()
    if not sessions:
        return None, sessions
    if figure_path:
        want = os.path.normcase(os.path.abspath(figure_path))
        for s in sessions:
            fig = s.get("figure") or ""
            if fig and os.path.normcase(os.path.abspath(fig)) == want:
                return s, sessions
    return sessions[0], sessions


def _request(action: str, topic: str | None = None, figure_path: str | None = None,
             timeout: float = 5.0) -> dict:
    session, sessions = _pick_session(figure_path)
    if session is None:
        return {"status": "gui_unavailable", "operation_executed": False,
                "error": "No PyFigures window is open. Start the GUI (python -m pyfigures) "
                         "and ask again, or use explain mode for the steps as text."}
    rid = uuid.uuid4().hex
    folder = session["folder"]
    req = os.path.join(folder, rid + ".request.json")
    resp = os.path.join(folder, rid + ".response.json")
    payload = {"version": 1, "token": session["token"], "created": time.time(),
               "action": action, "topic": topic}
    from .atomic_io import write_atomic
    write_atomic(req, json.dumps(payload))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(resp):
            try:
                with open(resp, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                time.sleep(0.05)
                continue
            try:
                os.remove(resp)
            except OSError:
                pass
            data.setdefault("window_figure", session.get("figure") or "")
            if len(sessions) > 1:
                data["windows_open"] = len(sessions)
            return data
        time.sleep(0.05)
    try:
        os.remove(req)
    except OSError:
        pass
    return {"status": "gui_unavailable", "operation_executed": False,
            "error": f"The PyFigures window did not answer within {timeout:g} s "
                     "(busy, or a modal dialog is waiting)."}


def show(query: str, figure_path: str | None = None) -> dict:
    """Show me how: open the guide in the running GUI. The user does the clicks."""
    gid, cands = find_guide(query)
    if gid is None:
        return {"status": "unknown_operation" if not cands else "ambiguous",
                "candidates": cands, "available": list(GUIDES), "operation_executed": False}
    result = _request("show", gid, figure_path)
    if result.get("status") == "gui_unavailable":
        result["steps_as_text"] = step_texts(gid)
    return result


def status(figure_path: str | None = None) -> dict:
    return _request("status", None, figure_path)


def close(figure_path: str | None = None) -> dict:
    return _request("close", None, figure_path)


def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="python -m pyfigures.guides",
                                description="Show-me-how guides for the PyFigures GUI.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    for name in ("explain", "show"):
        sp = sub.add_parser(name)
        sp.add_argument("operation")
        sp.add_argument("--figure", default=None)
    for name in ("status", "close"):
        sp = sub.add_parser(name)
        sp.add_argument("--figure", default=None)
    a = p.parse_args(argv)
    if a.cmd == "list":
        res = list_guides()
    elif a.cmd == "explain":
        res = explain(a.operation)
    elif a.cmd == "show":
        res = show(a.operation, a.figure)
    elif a.cmd == "status":
        res = status(a.figure)
    else:
        res = close(a.figure)
    print(json.dumps(res, indent=2, ensure_ascii=True))
    return 0 if not (isinstance(res, dict) and res.get("status") in
                     ("gui_unavailable", "error", "unknown_operation", "ambiguous")) else 1


if __name__ == "__main__":
    sys.exit(main())
