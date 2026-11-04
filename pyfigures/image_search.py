"""Image search: find the image files of a folder by what they show
("confocal gut with DAPI", "western blot", "wing disc 40x").

Each image is indexed once as a short text -- its file name and folder split
into words, its size, channels and pixel size, and, when a vision model is
available, a few sentences describing what the picture shows -- and that text
is embedded. A query is embedded the same way and the images are ranked by
similarity. Both models come from qtpy_ai_sidecar's optional embeddings
(chat panel > tools menu > Embeddings…): mistral-embed for the text and
mistral-small-latest for the descriptions with the Mistral source, or a server
on this computer. Describing sends a 512 px thumbnail of each image to that
model; describe="off" sends only the file names and metadata.

The index lives in the folder (``.pyfigures_image_index/``: index.json,
vectors.npy and 256 px thumbnails), covers its subfolders and is incremental:
only new or changed images are read again. Searching a subfolder uses the
index of an indexed parent folder.

Used by the MCP tools index_image_folder / search_images (and so the chat),
and from a terminal:
    python -m pyfigures.image_search index FOLDER [--describe auto|on|off]
    python -m pyfigures.image_search search FOLDER "what you look for"
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

INDEX_DIRNAME = ".pyfigures_image_index"
VERSION = 1
DESCRIBE_PX = 512          # thumbnail sent to the vision model
THUMB_PX = 256             # thumbnail kept in the index (result sheets)
CHUNK = 16                 # images described / embedded between two saves
PARALLEL = 4               # description requests in flight
DESCRIBE_CHOICES = ("auto", "on", "off")
PROMPT = ("You describe scientific images for a search index. In 2 to 4 plain sentences say what this "
          "image shows: the kind of image (fluorescence or confocal micrograph, brightfield, electron "
          "micrograph, photograph, gel or blot, plot or chart, diagram, ...), the specimen or subject "
          "(organism, tissue, cells, structures) when recognisable, the colours or channels, and any "
          "visible text, scale bar or labels. Only describe what is visible; say so when unsure. "
          "Its file name is {name}.")


class ImageSearchUnavailable(RuntimeError):
    """No embeddings configured, the source cannot be reached, or no index."""


# ---------------------------------------------------------------------------
# models (qtpy_ai_sidecar's optional embeddings)
# ---------------------------------------------------------------------------
def configured_embedder():
    try:
        from qtpy_ai_sidecar import embeddings
    except ImportError:
        raise ImageSearchUnavailable(
            "Image search needs the chat assistant's embeddings (pip install qtpy-ai-sidecar), "
            "then the chat panel's tools menu > Embeddings…: Mistral AI API or a local server") from None
    embedder = embeddings.configured()
    if embedder is None:
        raise ImageSearchUnavailable(
            "Embeddings are off: choose a source in the chat panel's tools menu > Embeddings… "
            "(Mistral AI API, or a local server)")
    return embedder


# ---------------------------------------------------------------------------
# what is indexed for one image
# ---------------------------------------------------------------------------
def words(name: str) -> str:
    """'WT_gut-DAPI_40x.tif' -> 'WT gut DAPI 40x': file and folder names as
    words the embedding model can read (camelCase split too)."""
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", name)
    stem = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)
    return " ".join(w for w in re.split(r"[\s_\-.]+", stem) if w)


def image_info(path: str, size=None) -> dict:
    info = {}
    if size:
        info["width"], info["height"] = size
    try:
        from .mcp_tools.workflow import _try_read_image_info      # TIFF channels and pixel size
        info.update(_try_read_image_info(path))
    except Exception:
        pass
    return info


def entry_text(rel: str, info: dict, description: str = "") -> str:
    folder, name = os.path.split(rel)
    lines = ["Image file: " + words(name)]
    if folder:
        lines.append("Folder: " + " / ".join(words(p) for p in re.split(r"[\\/]", folder) if p))
    facts = []
    if info.get("width"):
        facts.append(f"{info['width']} x {info['height']} pixels")
    if info.get("channels"):
        facts.append(f"{info['channels']} channel(s)")
    if info.get("px_to_unit"):
        facts.append(f"pixel size {info['px_to_unit']:.4g} {info.get('unit', '')}".strip())
    if facts:
        lines.append(", ".join(facts))
    if description:
        lines.append("Shows: " + description)
    return "\n".join(lines)


def _rgb(path: str):
    """The image as PyFigures displays a new panel (LUTs, Z projection), as
    (h, w, 3) uint8 with the contrast stretched (dim fluorescence)."""
    from batoolset.settings.global_settings import set_UI
    from .mcp_tools.core import _ensure_qapp
    from .panel_source_preview import panel_rgb, stretch
    set_UI()
    _ensure_qapp()
    from batoolset.drawings.shapes.image2d import Image2D
    return stretch(panel_rgb(Image2D(path)))


def _jpeg(rgb, px: int) -> bytes:
    from PIL import Image
    picture = Image.fromarray(rgb)
    picture.thumbnail((px, px))
    out = io.BytesIO()
    picture.save(out, "JPEG", quality=85)
    return out.getvalue()


# ---------------------------------------------------------------------------
# the index
# ---------------------------------------------------------------------------
def _is_image(name: str) -> bool:
    from batoolset.img import is_image_file
    return is_image_file(name)


def list_images(folder: str) -> list[str]:
    """Image files under *folder* (subfolders too, hidden folders skipped),
    as paths relative to it, '/'-separated."""
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.startswith(".") and _is_image(name):
                out.append(os.path.relpath(os.path.join(dirpath, name), folder).replace(os.sep, "/"))
    return out


class Index:
    """index.json (entries keyed by relative path, in vector order) and
    vectors.npy (unit-length rows) in <folder>/.pyfigures_image_index."""

    def __init__(self, folder: str):
        self.folder = os.path.abspath(folder)
        self.dir = os.path.join(self.folder, INDEX_DIRNAME)
        self.meta = {"version": VERSION, "embedding_model": "", "folder": self.folder}
        self.entries: dict[str, dict] = {}
        self.vectors: dict[str, np.ndarray] = {}

    @classmethod
    def load(cls, folder: str) -> "Index":
        index = cls(folder)
        try:
            with open(os.path.join(index.dir, "index.json"), encoding="utf-8") as f:
                data = json.load(f)
            matrix = np.load(os.path.join(index.dir, "vectors.npy"))
        except (OSError, ValueError):
            return index
        entries = data.get("entries", [])
        if data.get("version") != VERSION or len(entries) != len(matrix):
            return index                       # unreadable: rebuilt from scratch
        index.meta.update({k: v for k, v in data.items() if k != "entries"})
        for entry, vector in zip(entries, matrix):
            index.entries[entry["path"]] = entry
            index.vectors[entry["path"]] = vector
        return index

    def exists(self) -> bool:
        return os.path.isfile(os.path.join(self.dir, "index.json"))

    def save(self):
        from .atomic_io import write_atomic
        os.makedirs(self.dir, exist_ok=True)
        keys = [k for k in self.entries if k in self.vectors]
        matrix = (np.stack([self.vectors[k] for k in keys]).astype(np.float32) if keys
                  else np.zeros((0, 0), np.float32))
        buffer = io.BytesIO()
        np.save(buffer, matrix)
        write_atomic(os.path.join(self.dir, "vectors.npy"), buffer.getvalue())
        write_atomic(os.path.join(self.dir, "index.json"), json.dumps(
            {**self.meta, "entries": [self.entries[k] for k in keys]}, ensure_ascii=False, indent=1))

    def thumbnail_path(self, rel: str) -> str:
        return os.path.join(self.dir, "thumbs", hashlib.sha1(rel.encode()).hexdigest()[:16] + ".jpg")


def _key(path: str):
    st = os.stat(path)
    return [st.st_mtime, st.st_size]


def find_index(folder: str) -> tuple[Index, str]:
    """The index covering *folder* (its own, else an indexed parent's) and
    the subfolder prefix to keep ('' for the whole index)."""
    folder = os.path.abspath(folder)
    current = folder
    while True:
        index = Index.load(current)
        if index.exists() and index.entries:
            prefix = os.path.relpath(folder, current).replace(os.sep, "/")
            return index, "" if prefix == "." else prefix + "/"
        parent = os.path.dirname(current)
        if parent == current:
            raise ImageSearchUnavailable(f"{folder} is not indexed yet: index it first "
                                         "(index_image_folder, or python -m pyfigures.image_search index)")
        current = parent


def index_folder(folder: str, describe: str = "auto", time_budget: float | None = None,
                 embedder=None, progress=None) -> dict:
    """Index (or update) the images of *folder* and its subfolders.

    describe: "auto" describes the images when a vision model is set up (the
    Mistral source always has one), "on" requires one, "off" indexes names
    and metadata only (no pixels leave the computer).
    time_budget: seconds after which to stop and save (a later call goes on
    where it stopped); None runs to the end.
    progress(done, total): optional callback.
    Returns counts; "remaining" > 0 when stopped by the time budget.
    """
    if describe not in DESCRIBE_CHOICES:
        raise ValueError(f"describe must be one of {', '.join(DESCRIBE_CHOICES)}")
    folder = os.path.abspath(os.path.expanduser(folder))
    if not os.path.isdir(folder):
        raise ValueError(f"No such folder: {folder}")
    embedder = embedder or configured_embedder()
    vision = embedder.vision_id if describe != "off" else ""
    if describe == "on" and not vision:
        raise ImageSearchUnavailable("No vision model for descriptions: name one in the chat panel's "
                                     "tools menu > Embeddings… (Image descriptions), or use describe='off'")
    start = time.monotonic()
    index = Index.load(folder)
    files = list_images(folder)
    present = set(files)
    removed = [k for k in index.entries if k not in present]
    for rel in removed:
        index.entries.pop(rel)
        index.vectors.pop(rel, None)
        try:
            os.remove(index.thumbnail_path(rel))
        except OSError:
            pass
    if index.meta.get("embedding_model") != embedder.model_id:
        index.vectors.clear()                  # another embedding model: every text again
    index.meta["embedding_model"] = embedder.model_id

    todo = []
    for rel in files:
        entry = index.entries.get(rel)
        stale = (entry is None or entry.get("key") != _key(os.path.join(folder, rel))
                 or entry.get("description_model", "") != vision)
        if stale or rel not in index.vectors:
            todo.append((rel, stale))
    done, failed, described = 0, [], 0
    stopped = False
    pool = ThreadPoolExecutor(PARALLEL) if vision else None
    try:
        for at in range(0, len(todo), CHUNK):
            # >=: Windows' monotonic clock ticks every ~15 ms, so a budget of 0
            # read 0 elapsed and '>' never stopped
            if time_budget is not None and done and time.monotonic() - start >= time_budget:
                stopped = True
                break
            chunk = todo[at:at + CHUNK]
            pictures = {}
            for rel, stale in chunk:
                if not stale:
                    continue                   # only the text is embedded again
                path = os.path.join(folder, rel)
                entry = {"path": rel, "key": _key(path), "description": "", "description_model": vision}
                try:
                    rgb = _rgb(path)
                    entry["info"] = image_info(path, (rgb.shape[1], rgb.shape[0]))
                    os.makedirs(os.path.dirname(index.thumbnail_path(rel)), exist_ok=True)
                    with open(index.thumbnail_path(rel), "wb") as f:
                        f.write(_jpeg(rgb, THUMB_PX))
                    if vision:
                        pictures[rel] = _jpeg(rgb, DESCRIBE_PX)
                except Exception as exc:       # unreadable: still found by its name
                    entry["info"] = image_info(path)
                    entry["error"] = f"could not read the image: {exc}"[:300]   # retried when the file changes
                index.entries[rel] = entry
            if pictures:
                names = list(pictures)
                answers = pool.map(lambda r: _describe(embedder, r, pictures[r]), names)
                errors = []
                for rel, (text, error) in zip(names, answers):
                    if error:
                        index.entries[rel]["error"] = f"description failed: {error}"[:300]
                        index.entries[rel]["description_model"] = ""   # tried again next time
                        failed.append(rel)
                        errors.append(error)
                    else:
                        index.entries[rel]["description"] = text
                        described += 1
                if len(errors) == len(names):
                    # every request failed (key, quota, network): stop rather than
                    # go through the whole folder; what was done is kept
                    for rel, _ in chunk:
                        if rel not in index.vectors:
                            index.entries.pop(rel, None)
                    index.save()
                    raise ImageSearchUnavailable(f"Describing the images failed: {errors[0]}")
            rels = [rel for rel, _ in chunk]
            texts = [entry_text(rel, index.entries[rel].get("info", {}), index.entries[rel].get("description", ""))
                     for rel in rels]
            for rel, text in zip(rels, texts):
                index.entries[rel]["text"] = text
            try:
                vectors = embedder.embed(texts)
            except Exception as exc:
                index.save()
                raise ImageSearchUnavailable(f"Embedding failed: {exc}") from None
            for rel, vector in zip(rels, vectors):
                v = np.asarray(vector, dtype=np.float32)
                index.vectors[rel] = v / (np.linalg.norm(v) or 1.0)
            done += len(chunk)
            index.save()
            if progress:
                progress(done, len(todo))
    finally:
        if pool:
            pool.shutdown()
    if not todo and (removed or not index.exists()):
        index.save()
    return {"folder": folder, "index": index.dir, "images": len(files), "updated": done,
            "unchanged": len(files) - len(todo), "removed": len(removed), "described": described,
            "description_failures": len(failed), "failed_files": failed[:10],
            "remaining": len(todo) - done if stopped else 0,
            "embedding_model": embedder.model_id, "description_model": vision or None}


def _describe(embedder, rel, jpeg):
    try:
        return embedder.describe(jpeg, PROMPT.format(name=os.path.basename(rel))), None
    except Exception as exc:
        return "", exc


def search(folder: str, query: str, limit: int = 10, embedder=None) -> list[dict]:
    """The *limit* images of *folder* (and subfolders) closest to *query*,
    best first: {path, score, description, thumbnail}."""
    if not str(query).strip():
        raise ValueError("Empty query")
    index, prefix = find_index(os.path.abspath(os.path.expanduser(folder)))
    embedder = embedder or configured_embedder()
    if index.meta.get("embedding_model") != embedder.model_id:
        raise ImageSearchUnavailable(
            f"{index.folder} was indexed with {index.meta.get('embedding_model')}, but the embeddings are now "
            f"{embedder.model_id}: index the folder again (only the texts are re-embedded)")
    keys = [k for k in index.entries if k in index.vectors and k.startswith(prefix)]
    if not keys:
        return []
    try:
        [q] = embedder.embed([query])
    except Exception as exc:
        raise ImageSearchUnavailable(f"Embedding the query failed: {exc}") from None
    q = np.asarray(q, dtype=np.float32)
    q /= np.linalg.norm(q) or 1.0
    matrix = np.stack([index.vectors[k] for k in keys])
    if matrix.shape[1] != q.shape[0]:
        raise ImageSearchUnavailable("The index does not match the embedding model: index the folder again")
    scores = matrix @ q
    out = []
    for i in np.argsort(-scores)[:max(1, int(limit))]:
        entry = index.entries[keys[i]]
        thumb = index.thumbnail_path(keys[i])
        out.append({"path": os.path.join(index.folder, *keys[i].split("/")),
                    "score": round(float(scores[i]), 4),
                    "description": entry.get("description", ""),
                    "info": entry.get("info", {}),
                    "thumbnail": thumb if os.path.isfile(thumb) else None})
    return out


def contact_sheet(results: list[dict], out_path: str, columns: int = 4) -> str:
    """The results' thumbnails in a numbered grid (1 = best), saved as PNG."""
    from PIL import Image, ImageDraw
    cell, pad = THUMB_PX // 2 + 8, 4
    rows = (len(results) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell, max(1, rows) * (cell + 14)), "white")
    draw = ImageDraw.Draw(sheet)
    for n, result in enumerate(results):
        x, y = (n % columns) * cell, (n // columns) * (cell + 14)
        if result.get("thumbnail"):
            with Image.open(result["thumbnail"]) as thumb:
                thumb = thumb.convert("RGB")
                thumb.thumbnail((cell - 2 * pad, cell - 2 * pad))
                sheet.paste(thumb, (x + pad, y + pad))
        else:
            draw.rectangle((x + pad, y + pad, x + cell - pad, y + cell - pad), outline="grey")
        name = os.path.basename(result["path"])
        draw.text((x + pad, y + cell - 2), f"{n + 1}. {name[:30]}", fill="black")
    sheet.save(out_path)
    return out_path


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(prog="python -m pyfigures.image_search", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("index", help="index or update the images of a folder")
    p.add_argument("folder")
    p.add_argument("--describe", choices=DESCRIBE_CHOICES, default="auto")
    p = sub.add_parser("search", help="search an indexed folder")
    p.add_argument("folder")
    p.add_argument("query")
    p.add_argument("-n", "--limit", type=int, default=10)
    args = parser.parse_args(argv)
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)     # one line per request otherwise
    try:
        if args.command == "index":
            result = index_folder(args.folder, args.describe,
                                  progress=lambda d, t: print(f"\r{d}/{t}", end="", flush=True))
            print()
            print(json.dumps(result, indent=1))
        else:
            for n, r in enumerate(search(args.folder, args.query, args.limit), 1):
                print(f"{n:2d}. {r['score']:.3f}  {r['path']}")
                if r["description"]:
                    print("     " + r["description"][:200])
    except (ImageSearchUnavailable, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    main()
