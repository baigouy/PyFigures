"""2026-11-19 (user, live app): "first 20 files in sample_images_FIJI" left out the
.xlsx and .csv files among them ("I even asked for files, so they must have been
in"). scan_folder listed images only, in a case-sensitive order (every lowercase
name after all capitalised ones), and the model put the first file beside the
batch, where every item replaced it: it was dropped, then re-added last."""
import asyncio
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pyfigures.mcp_tools.workflow import scan_folder

NAMES = ["Zebra.tif", "apple.png", "aaa_measurements.xlsx", "10-b.tif", "2-a.tif",
         "notes.txt", "~$aaa_measurements.xlsx", "Beta.csv"]


def _folder(tmp_path):
    from PIL import Image
    for name in NAMES:
        p = tmp_path / name
        if name.endswith((".tif", ".png")):
            Image.new("L", (4, 4)).save(p)
        else:
            p.write_text("x,y\n1,2\n")
    return str(tmp_path)


def test_files_come_in_the_file_browsers_order(tmp_path):
    out = json.loads(scan_folder(_folder(tmp_path)))
    assert [os.path.basename(f) for f in out["files"]] == ["2-a.tif", "10-b.tif", "apple.png", "Zebra.tif"]


def test_the_other_files_are_listed_in_their_place(tmp_path):
    out = json.loads(scan_folder(_folder(tmp_path)))
    assert [(os.path.basename(o["file"]), o["kind"]) for o in out["other_files"]] == [
        ("aaa_measurements.xlsx", "table"), ("Beta.csv", "table"), ("notes.txt", "text")]
    assert out["all_files_in_order"] == ["2-a.tif", "10-b.tif", "aaa_measurements.xlsx", "apple.png",
                                         "Beta.csv", "notes.txt", "Zebra.tif"]
    assert "add_folder_files" in out["other_files_note"] and "tables as data plots" in out["other_files_note"]


def test_an_explicit_pattern_lists_only_what_it_matches(tmp_path):
    out = json.loads(scan_folder(_folder(tmp_path), pattern="*.tif"))
    assert "other_files" not in out and out["count"] == 3          # 2-a, 10-b, Zebra


def test_a_folder_of_images_only_adds_nothing(tmp_path):
    from PIL import Image
    Image.new("L", (4, 4)).save(tmp_path / "a.png")
    assert "other_files" not in json.loads(scan_folder(str(tmp_path)))


def _dispatch():
    from mcp.server.fastmcp import FastMCP
    from pyfigures.assistant.categorized_mcp import build_server
    calls = []
    full = FastMCP("fake")

    @full.tool()
    def delete_last_rows(count: int, label: str = "") -> dict:      # a name the chat exposes
        calls.append((count, label))
        return {"result": f"deleted {count}", "document_changed": True}

    run = build_server(full, lambda *a, **k: {})._tool_manager._tools["use_pyfigures_tool"].fn
    return (lambda **kw: asyncio.run(run(**kw))), calls


def test_an_argument_every_batch_item_replaces_is_an_item_of_its_own():
    run, calls = _dispatch()
    out = run(tool_name="delete_last_rows", arguments={"label": "x", "count": 1},
              batch=[{"count": 2}, {"count": 3}])
    assert calls == [(1, "x"), (2, "x"), (3, "x")] and out["batch_done"] == 3


def test_a_missing_group_path_is_the_figure_itself():
    """chat 2026-11-19: all 21 add_image of a batch failed on the missing group_path, then
    "Retrying with group_path=[]" was shown to the user."""
    from mcp.server.fastmcp import FastMCP
    from pyfigures.assistant.categorized_mcp import build_server
    seen = []
    full = FastMCP("fake")

    @full.tool()
    def delete_last_rows(group_path: list[int], count: int) -> str:
        seen.append((group_path, count))
        return "ok"

    run = build_server(full, lambda *a, **k: {})._tool_manager._tools["use_pyfigures_tool"].fn
    out = asyncio.run(run(tool_name="delete_last_rows", arguments={}, batch=[{"count": 1}, {"count": 2}]))
    assert seen == [([], 1), ([], 2)] and out["batch_done"] == 2


def test_the_files_of_a_folder_bring_their_rule():
    from pyfigures.assistant.categorized_mcp import request_rules
    rules = request_rules(r"create a fig with the first 20 files in C:\Users\me\sample_images")
    assert "add_folder_files" in rules
    assert "add_folder_files" not in request_rules("save the file as a pdf")


def test_the_note_on_other_files_comes_first(tmp_path):
    out = json.loads(scan_folder(_folder(tmp_path)))
    keys = list(out)
    assert keys.index("other_files_note") < keys.index("files")
    assert "aaa_measurements.xlsx" in out["other_files_note"]


def test_a_shared_argument_stays_shared():
    run, calls = _dispatch()
    run(tool_name="delete_last_rows", arguments={"label": "x"}, batch=[{"count": 2}, {"count": 3, "label": "y"}])
    assert calls == [(2, "x"), (3, "y")]


# --- files with no extension (macOS): judged by their content (user, 2026-11-19) ---

def _no_extension_folder(tmp_path):
    from PIL import Image
    import pandas as pd
    tmp_path.mkdir(parents=True, exist_ok=True)
    Image.new("L", (6, 4)).save(tmp_path / "blobs", format="PNG")
    Image.new("L", (6, 4)).save(tmp_path / "wing", format="TIFF")
    Image.new("RGB", (6, 4)).save(tmp_path / "metal", format="JPEG")
    pd.DataFrame({"g": ["a", "b", "c"], "v": [1, 2, 3]}).to_excel(tmp_path / "measures.xlsx", index=False)
    os.rename(tmp_path / "measures.xlsx", tmp_path / "measures")
    (tmp_path / "factors").write_text("g,v\na,1\nb,2\nc,3\nd,4\n")
    (tmp_path / "readme").write_text("just some notes")
    (tmp_path / ".DS_Store").write_bytes(b"\x00\x00\x00\x01Bud1")
    return tmp_path


def test_images_with_no_extension_are_found_by_their_content(tmp_path):
    from batoolset.img import is_image_file, sniff_image_format
    d = _no_extension_folder(tmp_path)
    assert [sniff_image_format(str(d / n)) for n in ("blobs", "wing", "metal")] == ["png", "tiff", "jpeg"]
    assert not is_image_file(str(d / "factors")) and not is_image_file(str(d / ".DS_Store"))
    out = json.loads(scan_folder(str(d)))
    assert [os.path.basename(f) for f in out["files"]] == ["blobs", "metal", "wing"]
    assert {os.path.basename(o["file"]): o["kind"] for o in out["other_files"]} == {
        "factors": "table", "measures": "table", "readme": "text"}


def test_a_workbook_with_no_extension_reads_as_a_workbook(tmp_path):
    from staplot.api import is_excel, read_table
    d = _no_extension_folder(tmp_path)
    assert is_excel(str(d / "measures")) and not is_excel(str(d / "factors"))
    assert read_table(str(d / "measures")).shape == (3, 2)


def test_add_folder_files_places_images_and_tables_in_order(tmp_path):
    """Told three times that "files" include the tables, the model still added images
    only: one operation takes the files in their order, tables as data plots."""
    from pyfigures.mcp_server import create_figure, add_folder_files
    d = _no_extension_folder(tmp_path / "data")
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf, mode="canvas")
    out = add_folder_files(pyf, str(d), first=3)
    assert "Added 3 of the 3 file(s)" in out and "blobs, factors, measures" in out, out
    assert "Data plots made from the tables: factors, measures" in out
    out = add_folder_files(pyf, str(d), names=["readme"])
    assert "Not placed" in out and "readme (text)" in out


def test_a_dropped_folder_brings_its_tables_at_their_place(tmp_path):
    from pyfigures.gui.pfgui import _folder_drop_items
    d = _no_extension_folder(tmp_path)
    items, left_out = _folder_drop_items(str(d))
    got = [os.path.basename(getattr(i, "path", i)) + (":table" if hasattr(i, "kind") else "") for i in items]
    assert got == ["blobs", "factors:table", "measures:table", "metal", "wing"]
    assert left_out == ["readme"]
