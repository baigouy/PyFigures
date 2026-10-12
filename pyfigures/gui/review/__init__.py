"""Async figure-review workflow: export a self-contained HTML snapshot that a
reviewer can annotate (click-to-pin comments) with zero install and no network
connection, then import their comments back into PyFigures.

This is intentionally NOT live/collaborative editing: the owner is always the
only one who edits the .pyf; reviewers only ever see a flattened raster and
leave positioned notes. Off by default — only reachable via the "Review" menu.

Layout:
  html_export.py  — export/import logic + JSON sidecar read/write, no Qt dependency
  dialog.py        — the Qt "view review comments" dialog
  send.py          — mailto compose-and-attach helper (never sends anything itself)
  _template.py     — the reviewer-facing HTML/JS page

See docs/REVIEW_WORKFLOW.md for a plain-English walkthrough of the workflow.
"""
from .html_export import (
    build_review_html,
    export_review_html,
    extract_comments,
    sidecar_path,
    load_sidecar_comments,
    save_sidecar_comments,
    merge_comments,
)
from .dialog import show_review_comments_dialog
from .send import build_mailto_url, default_review_request_text, reveal_in_file_manager

__all__ = [
    "build_review_html",
    "export_review_html",
    "extract_comments",
    "sidecar_path",
    "load_sidecar_comments",
    "save_sidecar_comments",
    "merge_comments",
    "show_review_comments_dialog",
    "build_mailto_url",
    "default_review_request_text",
    "reveal_in_file_manager",
]
