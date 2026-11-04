"""Image search tools: index a folder of images and find images by what they
show (pyfigures.image_search; embeddings and descriptions from the chat
assistant's optional Embeddings… settings)."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Literal

from mcp.server.fastmcp import Image
from mcp.types import ToolAnnotations

from .app import mcp
from .. import image_search as S

INDEX_TIME_BUDGET_S = 100      # one call stays well under the chat's 180 s tool timeout


@mcp.tool()
def index_image_folder(folder: str, describe: Literal["auto", "on", "off"] = "auto") -> str:
    """Index (or update) the image files of *folder* and its subfolders so that
    search_images can find them by content ("confocal gut with DAPI").

    Each image is described in a few sentences by a vision model (Mistral:
    mistral-small-latest), then its file name, folder, size and description are
    embedded. The models are the chat assistant's Embeddings… settings.
    *describe*: "auto" describes when a vision model is set up, "on" requires
    it, "off" indexes names and metadata only. Describing SENDS A SMALL
    THUMBNAIL OF EACH IMAGE to that model: tell the user before the first
    index of a folder.

    Incremental: only new or changed images are read again. One call works
    for about 100 s; when the result says remaining > 0, call it again to go
    on (or run `python -m pyfigures.image_search index FOLDER` for big folders).
    The index is stored in <folder>/.pyfigures_image_index.
    """
    try:
        result = S.index_folder(folder, describe, time_budget=INDEX_TIME_BUDGET_S)
    except (S.ImageSearchUnavailable, ValueError) as exc:
        return f"ERROR: {exc}"
    if result["remaining"]:
        result["next"] = "Not finished: call index_image_folder again with the same folder to go on."
    return json.dumps(result, ensure_ascii=False, indent=1)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def search_images(query: str, folder: str, limit: int = 8, show: bool = True) -> list | str:
    """Find image files by what they show, in a folder indexed with
    index_image_folder (or in a subfolder of one): "wing disc stained for
    E-cadherin", "western blot", "brightfield embryo", "40x confocal gut".

    Returns the best matches first: path, score (similarity, higher is
    closer), the image's indexed description and size. *show* adds a contact
    sheet of numbered thumbnails (1 = best) so the user can pick.
    To put a found image in the figure use add_image with its path.
    Read-only: no figure or file is changed.
    """
    try:
        results = S.search(folder, query, limit=max(1, min(int(limit), 40)))
    except (S.ImageSearchUnavailable, ValueError) as exc:
        return f"ERROR: {exc}"
    listing = json.dumps({"query": query, "n_results": len(results),
                          "results": [{k: v for k, v in r.items() if k != "thumbnail"} for r in results]},
                         ensure_ascii=False, indent=1)
    if not (show and results):
        return listing
    out = os.path.join(tempfile.mkdtemp(prefix="pyf_image_search_"), "matches.png")
    S.contact_sheet(results, out)
    return [listing, Image(path=out)]
