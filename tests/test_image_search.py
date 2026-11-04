"""Image search (pyfigures.image_search and the index_image_folder /
search_images tools) with a stand-in embedder and vision model: no network,
no key. Run: pytest tests/test_image_search.py"""
import json
import os
import re

import numpy as np
import pytest
import tifffile
from PIL import Image as PILImage

from pyfigures import image_search as S

VOCAB = ("gut", "dapi", "nuclei", "wing", "disc", "blot", "blots", "western", "bands", "embryo", "brightfield",
         "fluorescence", "confocal", "cadherin", "image", "file", "plot")


class FakeEmbedder:
    """Bag-of-words vectors over VOCAB; descriptions from a table keyed by the
    file name the prompt gives (the stand-in 'sees' the picture through it)."""

    def __init__(self, model="mistral/mistral-embed", vision="mistral/mistral-small-latest", seen=None):
        self.model_id, self.vision_id = model, vision
        self.seen = {} if seen is None else seen
        self.described, self.embedded, self.fail = [], [], None

    def embed(self, texts, model=None):
        self.embedded.extend(texts)
        out = []
        for text in texts:
            tokens = re.findall(r"[a-z]+", text.lower())
            out.append([float(tokens.count(w)) for w in VOCAB] + [0.01])
        return out

    def describe(self, image, prompt, mime="image/jpeg"):
        assert image[:2] == b"\xff\xd8"                     # a JPEG thumbnail
        assert PILImage.open(__import__("io").BytesIO(image)).size[0] <= S.DESCRIBE_PX
        name = re.search(r"file name is (.+)\.$", prompt).group(1)
        self.described.append(name)
        if self.fail:
            raise RuntimeError(self.fail)
        return self.seen.get(name, "An image.")


SEEN = {"img_001.tif": "Confocal fluorescence micrograph of the gut, nuclei stained with DAPI in blue.",
        "scan7.png": "A western blot with dark bands in five lanes.",
        "IMG_2210.png": "Brightfield photograph of an embryo."}


def _folder(root):
    os.makedirs(root / "2024" / "blots")
    tifffile.imwrite(root / "img_001.tif", (np.random.rand(2, 60, 80) * 3000).astype(np.uint16),
                     imagej=True, metadata={"axes": "CYX"})
    PILImage.fromarray((np.random.rand(50, 70, 3) * 255).astype(np.uint8)).save(root / "2024" / "blots" / "scan7.png")
    PILImage.fromarray((np.random.rand(40, 40, 3) * 255).astype(np.uint8)).save(root / "2024" / "IMG_2210.png")
    (root / "notes.txt").write_text("not an image")
    return str(root)


@pytest.fixture
def folder(tmp_path):
    return _folder(tmp_path / "images")


@pytest.fixture
def embedder():
    return FakeEmbedder(seen=SEEN)


def test_index_then_search_by_what_the_image_shows(folder, embedder):
    result = S.index_folder(folder, embedder=embedder)
    assert (result["images"], result["updated"], result["described"], result["remaining"]) == (3, 3, 3, 0)
    assert sorted(embedder.described) == sorted(SEEN)
    found = S.search(folder, "gut nuclei DAPI", embedder=embedder)
    assert os.path.basename(found[0]["path"]) == "img_001.tif" and "DAPI" in found[0]["description"]
    assert found[0]["info"]["width"] == 80 and found[0]["info"]["channels"] == 2
    assert os.path.isfile(found[0]["thumbnail"])
    top = S.search(folder, "western blot bands", limit=1, embedder=embedder)
    assert [os.path.basename(r["path"]) for r in top] == ["scan7.png"]


def test_file_and_folder_names_are_indexed_as_words():
    assert S.words("WT_gut-DAPI_40x.tif") == "WT gut DAPI 40x"
    assert S.words("wingDisc.png") == "wing Disc"
    text = S.entry_text("2024/western_blots/scan7.png", {"width": 70, "height": 50}, "Bands.")
    assert text.splitlines() == ["Image file: scan7", "Folder: 2024 / western blots",
                                 "70 x 50 pixels", "Shows: Bands."]


def test_reindexing_is_incremental(folder, embedder):
    S.index_folder(folder, embedder=embedder)
    embedder.described.clear()
    again = S.index_folder(folder, embedder=embedder)
    assert (again["updated"], again["unchanged"], embedder.described) == (0, 3, [])
    os.remove(os.path.join(folder, "2024", "IMG_2210.png"))
    path = os.path.join(folder, "img_001.tif")
    tifffile.imwrite(path, np.zeros((30, 30), np.uint16))
    os.utime(path, (1, 1))
    again = S.index_folder(folder, embedder=embedder)
    assert (again["updated"], again["removed"], embedder.described) == (1, 1, ["img_001.tif"])
    assert {os.path.basename(r["path"]) for r in S.search(folder, "image", embedder=embedder)} == {
        "img_001.tif", "scan7.png"}


def test_describe_off_sends_no_pixels(folder, embedder):
    result = S.index_folder(folder, describe="off", embedder=embedder)
    assert embedder.described == [] and result["description_model"] is None
    assert os.path.basename(S.search(folder, "blots", embedder=embedder)[0]["path"]) == "scan7.png"   # folder name
    S.index_folder(folder, embedder=embedder)                        # auto later: now described
    assert sorted(embedder.described) == sorted(SEEN)


def test_describe_on_needs_a_vision_model(folder):
    with pytest.raises(S.ImageSearchUnavailable, match="vision model"):
        S.index_folder(folder, describe="on", embedder=FakeEmbedder(vision=""))
    S.index_folder(folder, embedder=FakeEmbedder(vision=""))         # auto: names and metadata only


def test_another_embedding_model_needs_a_new_index_but_not_new_descriptions(folder, embedder):
    S.index_folder(folder, embedder=embedder)
    other = FakeEmbedder(model="local/nomic-embed-text", seen=SEEN)
    with pytest.raises(S.ImageSearchUnavailable, match="index the folder again"):
        S.search(folder, "gut", embedder=other)
    result = S.index_folder(folder, embedder=other)
    assert result["updated"] == 3 and other.described == []        # texts re-embedded only
    assert S.search(folder, "gut", embedder=other)


def test_time_budget_stops_and_the_next_call_goes_on(folder, embedder, monkeypatch):
    monkeypatch.setattr(S, "CHUNK", 1)
    first = S.index_folder(folder, embedder=embedder, time_budget=0)
    assert (first["updated"], first["remaining"]) == (1, 2)
    second = S.index_folder(folder, embedder=embedder, time_budget=None)
    assert (second["updated"], second["unchanged"], second["remaining"]) == (2, 1, 0)


def test_failing_descriptions_stop_the_run(folder, embedder):
    embedder.fail = "HTTP 401: no key"
    with pytest.raises(S.ImageSearchUnavailable, match="401"):
        S.index_folder(folder, embedder=embedder)
    assert S.Index.load(folder).entries == {}                       # nothing half-indexed
    embedder.fail = None
    assert S.index_folder(folder, embedder=embedder)["described"] == 3


def test_a_subfolder_is_searched_with_its_parents_index(folder, embedder):
    S.index_folder(folder, embedder=embedder)
    found = S.search(os.path.join(folder, "2024"), "gut DAPI image", embedder=embedder)
    assert {os.path.basename(r["path"]) for r in found} == {"scan7.png", "IMG_2210.png"}


def test_unindexed_folder_and_unreadable_image(tmp_path, embedder):
    with pytest.raises(S.ImageSearchUnavailable, match="not indexed"):
        S.search(str(tmp_path), "gut", embedder=embedder)
    (tmp_path / "broken.png").write_bytes(b"not a png")
    result = S.index_folder(str(tmp_path), embedder=embedder)
    entry = S.Index.load(str(tmp_path)).entries["broken.png"]
    assert result["updated"] == 1 and "could not read" in entry["error"] and embedder.described == []
    assert S.search(str(tmp_path), "broken", embedder=embedder)[0]["thumbnail"] is None


def test_tools(folder, embedder, monkeypatch):
    from pyfigures.mcp_tools import image_search as T
    monkeypatch.setattr(S, "configured_embedder", lambda: embedder)
    indexed = json.loads(T.index_image_folder(folder))
    assert indexed["images"] == 3 and "next" not in indexed
    listing, sheet = T.search_images("gut DAPI", folder, limit=3)
    results = json.loads(listing)["results"]
    assert os.path.basename(results[0]["path"]) == "img_001.tif" and "thumbnail" not in results[0]
    assert PILImage.open(sheet.path).size[0] > 0
    assert isinstance(T.search_images("gut", folder, show=False), str)
    assert T.search_images("gut", os.path.dirname(folder)).startswith("ERROR: ")


def test_without_embeddings_the_tools_explain_what_to_set_up(folder, monkeypatch):
    from pyfigures.mcp_tools import image_search as T
    pytest.importorskip("qtpy_ai_sidecar.embeddings")
    from qtpy_ai_sidecar import embeddings
    monkeypatch.setattr(embeddings, "configured", lambda: None)
    assert "Embeddings…" in T.index_image_folder(folder)


def test_chat_finds_the_tools():
    from pyfigures.assistant import live_mcp
    from pyfigures.assistant.categorized_mcp import build_server
    tools = build_server(live_mcp.mcp, live_mcp.request)._tool_manager._tools
    first = lambda q: tools['find_pyfigures_tools'].fn(query=q)['tools'][0]['name']
    assert first("find the image of the gut with DAPI") == "search_images"
    assert first("search my pictures for a western blot") == "search_images"
    assert first("index this folder of images") == "index_image_folder"
    assert tools['use_pyfigures_tool'] is not None
