"""Export/import for the async figure-review workflow — no Qt dependency.

Builds a self-contained HTML snapshot a reviewer can annotate (click-to-pin
comments) with zero install and no network connection, and parses their
comments back out of the file they send back.

Comments are kept in a JSON sidecar file next to the .pyf (``<name>.review.json``)
rather than inside the .pyf's own XML/object model, so this feature never touches
the batoolset serialization engine.
"""
import base64
import json
import os
import re
from pathlib import Path

from ._template import TEMPLATE

_COMMENT_BLOCK_RE = re.compile(
    r'<script id="pyfigures-review-data" type="application/json">(.*?)</script>',
    re.S,
)


def build_review_html(image_path: str, source_name: str = "figure", comments=None,
                       author: str = "", owner_email: str = "") -> str:
    """Return a self-contained HTML string embedding *image_path* plus a
    click-to-pin commenting UI. *comments* pre-seeds existing pins (for
    round-tripping an already-reviewed file). *owner_email*, if given, pre-fills
    the "send back by email" button's recipient."""
    img_bytes = Path(image_path).read_bytes()
    ext = Path(image_path).suffix.lstrip(".").lower() or "png"
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
    data_uri = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", source_name) or "figure"
    placed = [c for c in comments or [] if c.get("x") is not None]
    general = "\n".join(c.get("text", "") for c in comments or [] if c.get("x") is None)
    payload = json.dumps({"comments": placed, "author": author, "owner_email": owner_email,
                          "general": general})
    html = TEMPLATE
    html = html.replace("__IMAGE_DATA_URI__", data_uri)
    html = html.replace("__SOURCE_NAME__", safe_name)
    html = html.replace("__COMMENTS_JSON__", payload)
    return html


def export_review_html(image_path: str, out_path: str, source_name: str = "figure", owner_email: str = ""):
    html = build_review_html(image_path, source_name=source_name, owner_email=owner_email)
    Path(out_path).write_text(html, encoding="utf-8")


def extract_comments(html_path: str) -> list:
    """Parse a (possibly reviewed) PyFigures review HTML file and return its
    comment list: [{x, y, text, author, ts}, ...] with x/y in 0..1 fractions; a
    comment on a region also has w/h, one on the whole figure has general=True
    and no position."""
    text = Path(html_path).read_text(encoding="utf-8")
    m = _COMMENT_BLOCK_RE.search(text)
    if not m:
        raise ValueError("This file doesn't contain PyFigures review data.")
    data = json.loads(m.group(1))
    comments = list(data.get("comments", []))
    # a comment on the whole figure (no position) comes first
    general = str(data.get("general") or "").strip()
    if general:
        comments.insert(0, {"x": None, "y": None, "general": True, "text": general,
                            "author": data.get("author", ""), "ts": ""})
    return comments


def sidecar_path(pyf_path: str) -> str:
    return str(Path(pyf_path).with_suffix("")) + ".review.json"


def load_sidecar_comments(pyf_path: str) -> list:
    path = sidecar_path(pyf_path)
    if not os.path.exists(path):
        return []
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("comments", [])
    except Exception:
        return []


def save_sidecar_comments(pyf_path: str, comments: list):
    path = sidecar_path(pyf_path)
    Path(path).write_text(json.dumps({"comments": comments}, indent=2), encoding="utf-8")


def merge_comments(existing: list, incoming: list) -> list:
    """Append incoming comments that aren't already present (by x/y/text/author/ts)."""
    def key_of(c):      # a whole-figure comment has no position
        return (round(c.get("x") or 0, 4), round(c.get("y") or 0, 4), c.get("text", ""), c.get("ts", ""))
    seen = {key_of(c) for c in existing}
    merged = list(existing)
    for c in incoming:
        key = key_of(c)
        if key not in seen:
            merged.append(c)
            seen.add(key)
    return merged
