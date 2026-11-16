"""'10 randomly selected images': the model took the first files of the sorted
list (Mistral Large 4, 2026-11-16). scan_folder(sample=N) draws them at random."""
from __future__ import annotations

import json

import pytest

M = pytest.importorskip("pyfigures.mcp_server")


def test_a_random_sample_of_the_folder(tmp_path):
    from PIL import Image
    for i in range(30):
        Image.new("L", (8, 8), i).save(tmp_path / f"img_{i:02d}.png")
    d = json.loads(M.scan_folder(str(tmp_path), sample=10, seed=1))
    assert len(d["random_sample"]) == 10 and len(set(d["random_sample"])) == 10
    assert set(d["random_sample"]) <= set(d["files"])
    assert d["random_sample"] != d["files"][:10]
    assert json.loads(M.scan_folder(str(tmp_path), sample=10, seed=1))["random_sample"] == d["random_sample"]
    assert len(json.loads(M.scan_folder(str(tmp_path), sample=99))["random_sample"]) == 30
    assert "random_sample" not in json.loads(M.scan_folder(str(tmp_path)))
