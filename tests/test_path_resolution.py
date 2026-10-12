"""
Portable figures: source paths that no longer exist are found relative to the
.pyf's current location (figure moved to another folder / disk / OS).

Run with PYTEST_QT_API=pyqt6.
"""
from __future__ import annotations

import json
import os
import shutil
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")


def _png(path, h=20, w=30, val=100):
    from PIL import Image
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.full((h, w), val, np.uint8)).save(path)
    return path


def _linux_figure(root_dir):
    """A figure saved on Linux (/home/alice/Bureau/exp/...) now living under
    root_dir/exp/ on this machine, data in root_dir/exp/data/."""
    from pyfigures.mcp_server import create_figure, add_image
    exp = os.path.join(root_dir, "exp")
    a = _png(os.path.join(exp, "data", "a.png"))
    b = _png(os.path.join(exp, "data", "sub", "b.png"), 30, 20)
    pyf = os.path.join(exp, "figs", "fig.pyf")
    os.makedirs(os.path.dirname(pyf), exist_ok=True)
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], a)
    add_image(pyf, [0], b)
    # rewrite the stored paths to what the Linux machine saved
    tree = ET.parse(pyf)
    for img in tree.getroot().iter("Image2D"):
        fn = img.find("filename")
        p = fn.text.strip('"').replace("\\", "/")
        rel = p.split("/exp/", 1)[1]
        fn.text = f'""/home/alice/Bureau/exp/{rel}""'
    tree.write(pyf, encoding="unicode")
    return pyf, a, b


def test_resolver_finds_linux_paths(tmp_path):
    from pyfigures.path_resolution import PathResolver
    pyf, a, b = _linux_figure(str(tmp_path))
    r = PathResolver(pyf)
    assert os.path.samefile(r.resolve("/home/alice/Bureau/exp/data/a.png"), a)
    # second file resolved through the learned prefix
    assert r.learned
    assert os.path.samefile(r.resolve("/home/alice/Bureau/exp/data/sub/b.png"), b)
    assert r.resolve("/home/alice/Bureau/exp/data/none.png") is None
    # existing paths are left alone
    assert r.resolve(a) is None


def test_windows_path_resolved_on_the_other_side(tmp_path):
    from pyfigures.path_resolution import PathResolver
    pyf, a, _ = _linux_figure(str(tmp_path))
    r = PathResolver(pyf)
    assert os.path.samefile(r.resolve(r"D:\old\stuff\exp\data\a.png"), a)


def test_bare_name_only_next_to_pyf(tmp_path):
    from pyfigures.path_resolution import PathResolver
    d = str(tmp_path)
    _png(os.path.join(d, "x.png"))            # far up: must NOT match a bare name
    pyf = os.path.join(d, "deep", "er", "fig.pyf")
    os.makedirs(os.path.dirname(pyf))
    open(pyf, "w").close()
    assert PathResolver(pyf).resolve("/elsewhere/x.png") is None
    here = _png(os.path.join(d, "deep", "er", "x.png"))
    assert os.path.samefile(PathResolver(pyf).resolve("/elsewhere/x.png"), here)


def test_unchanged_xml_when_nothing_moved(tmp_path):
    from pyfigures.path_resolution import resolve_moved_paths
    from pyfigures.mcp_server import create_figure, add_image
    d = str(tmp_path)
    pyf = os.path.join(d, "f.pyf")
    create_figure(pyf, num_groups=1)
    add_image(pyf, [0], _png(os.path.join(d, "a.png")))
    xml = open(pyf, encoding="utf-8").read()
    out, moved = resolve_moved_paths(xml, pyf)
    assert moved == {} and out is xml


def test_list_filenames_and_scripts_resolved(tmp_path):
    from pyfigures.path_resolution import resolve_moved_paths_in_tree
    from pyfigures.mcp_server import _make_channel_merge_script, _encode_str, _decode
    pyf, a, b = _linux_figure(str(tmp_path))
    tree = ET.parse(pyf)
    imgs = list(tree.getroot().iter("Image2D"))
    imgs[0].find("filename").text = ('""[\'/home/alice/Bureau/exp/data/a.png\', '
                                     '\'/home/alice/Bureau/exp/data/sub/b.png\']""')
    script = _make_channel_merge_script(["/home/alice/Bureau/exp/data/a.png",
                                         "/home/alice/Bureau/exp/data/sub/b.png"],
                                        [(0, 1, 0), (1, 0, 1)], "sum")
    imgs[1].find("custom_loading_script").text = _encode_str(script)
    moved = resolve_moved_paths_in_tree(tree.getroot(), pyf)
    assert len(moved) == 2
    lst = imgs[0].find("filename").text
    assert "/home/alice" not in lst and lst.startswith('""[')
    new_script = _decode(imgs[1].find("custom_loading_script").text)
    assert "/home/alice" not in new_script
    compile(new_script, "<merge>", "exec")


def test_mcp_tools_use_relocated_files(tmp_path):
    """MCP edits resolve moved files: true sizes are read from the relocated
    files (b.png is 20x30) and the found paths are saved."""
    from pyfigures.mcp_server import set_spacing
    pyf, a, b = _linux_figure(str(tmp_path))
    set_spacing(pyf, [0], 4)
    got = {}
    for img in ET.parse(pyf).getroot().iter("Image2D"):
        fn = img.findtext("filename").strip('"')
        got[os.path.basename(fn)] = (fn, float(img.findtext("width")),
                                     float(img.findtext("height")))
    assert "/home/alice" not in got["b.png"][0]
    assert got["b.png"][1:] == (20.0, 30.0)


def test_find_moved_files_tool(tmp_path):
    from pyfigures.mcp_server import find_moved_files
    pyf, a, b = _linux_figure(str(tmp_path))
    os.remove(b)
    r = json.loads(find_moved_files(pyf))
    assert len(r["relocated"]) == 1 and r["written"] is False
    assert r["still_missing"] == ["/home/alice/Bureau/exp/data/sub/b.png"]
    assert "/home/alice/Bureau/exp/data/a.png" in open(pyf, encoding="utf-8").read()
    r = json.loads(find_moved_files(pyf, apply=True))
    assert r["written"] is True
    assert "/home/alice/Bureau/exp/data/a.png" not in open(pyf, encoding="utf-8").read()


def test_remap_paths_sees_stored_paths(tmp_path):
    from pyfigures.mcp_server import remap_paths
    pyf, a, b = _linux_figure(str(tmp_path))
    out = remap_paths(pyf, "/home/alice/Bureau/", "Z:/x/", dry_run=True)
    assert "Would change 2 path(s)" in out


def test_gui_open_resolves_moved_files(qapp, monkeypatch, tmp_path):
    from qtpy.QtWidgets import QMessageBox
    from pyfigures.gui.pfgui import EZFIG_GUI
    EZFIG_GUI.show_tips = lambda self: None
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    pyf, a, b = _linux_figure(str(tmp_path))
    g = EZFIG_GUI()
    g.reload_state(pyf, append=False)
    fns = [c.filename for c in g.paint.EZFIG_panel.shapes_to_draw[0].content]
    assert all(os.path.isfile(f) for f in fns), fns
    assert getattr(g, "_n_paths_relocated", 0) == 2
    g._dirty = False
