"""Chat 2026-11-23 (local Qwen3.8 27B): "build a fig with 5 random images from <folder>" went to
draft_figure, which writes a NEW .pyf; the open figure stayed empty, the model drafted again
into "live.pyf" (a stray file in the working folder). add_folder_files now picks random files
for the open figure, the request brings that hint, and draft_figure says where it wrote."""
import json
import os

import numpy as np

from pyfigures.assistant import categorized_mcp
from pyfigures.mcp_tools import workflow


def _folder(tmp_path, n=9):
    from PIL import Image
    folder = tmp_path / 'imgs'
    folder.mkdir()
    for i in range(n):
        Image.fromarray((np.random.rand(16, 16) * 255).astype('uint8')).save(folder / f'img_{i}.png')
    (folder / 'table.csv').write_text('a,b\n1,2\n3,4\n')
    return folder


def test_random_images_only_go_in_the_given_figure(tmp_path, monkeypatch):
    folder = _folder(tmp_path)
    added = []
    monkeypatch.setattr(workflow, 'add_image', lambda pyf, path, image: added.append(os.path.basename(image)) or 'ok')
    monkeypatch.setattr(workflow, 'add_data_plot', lambda *a, **k: added.append('PLOT') or 'ok')
    runs = set()
    for _ in range(6):
        added.clear()
        workflow.add_folder_files(str(tmp_path / 'f.pyf'), str(folder), first=5, pick='random', images_only=True)
        assert len(added) == 5 and 'PLOT' not in added and len(set(added)) == 5
        runs.add(tuple(sorted(added)))
    assert len(runs) > 1                                # really random, not the first five
    assert workflow.add_folder_files('x.pyf', str(folder), pick='any').startswith('ERROR')


def test_the_request_brings_the_random_hint():
    rules = categorized_mcp.request_rules(r'build a fig with 5 random images from C:\data\sample_images_FIJI')
    assert 'pick="random"' in rules and 'draft_figure writes a separate new file' in rules
    assert 'RANDOM' not in categorized_mcp.request_rules('make the letters bold')


def test_draft_figure_says_the_open_figure_is_unchanged():
    import inspect
    first = ' '.join(inspect.getdoc(workflow.draft_figure).splitlines()[:2])
    assert 'NEW .pyf file' in first and 'not the open figure: add_folder_files' in first
    assert "the figure open in PyFigures is unchanged" in inspect.getsource(workflow.draft_figure)
