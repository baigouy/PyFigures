"""Every image Fiji opens is accepted (2026-10-21: the Fiji sample images
.dcm, .dm3, .IPL, .SEQ and .ipw were refused by the drop, though they load);
only text files are refused. Fluoview / shaped TIFFs follow their own axes as
Fiji does (Z was read as channels, a 0 resolution tag fell back to one plane)
and a position axis is a series. A file no reader opens is reported, never
added as a broken panel."""
from __future__ import annotations

import glob
import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

from batoolset.img import Img, get_series_info, is_image_file, list_image_files_in_folder

FIJI = r"C:\Users\aigouy\OneDrive\Desktop\test_images\sample_images_FIJI"


@pytest.mark.parametrize("name", ["CT.dcm", "x.DICOM", "dnasample1.dm3", "Blend_Final.IPL", "HEART.SEQ",
                                  "mitosis-test.ipw", "a.tif", "b.lsm", "c.mov", "d.nii.gz", "e.pgm"])
def test_image_formats_fiji_opens_are_accepted(name):
    assert is_image_file(name)


@pytest.mark.parametrize("name", ["notes.txt", "MaMuT_TGMM_Parhyale_demo.xml", "t.csv", "m.json",
                                  "x.lifext", "a.docx"])
def test_text_and_other_files_are_refused(name):
    assert not is_image_file(name)


def test_a_dropped_folder_keeps_its_images_only(tmp_path):
    for n in ("a.dcm", "b.dm3", "c.txt", "d.xml", "e.tif"):
        (tmp_path / n).write_bytes(b"x")
    assert [os.path.basename(p) for p in list_image_files_in_folder(str(tmp_path))] == ["a.dcm", "b.dm3", "e.tif"]


def _shaped(path, axes, shape, **kw):
    import tifffile
    data = (np.arange(int(np.prod(shape))) % 251).astype(np.uint8).reshape(shape)
    tifffile.imwrite(str(path), data, metadata={"axes": axes}, **kw)
    return str(path), data


def test_tiff_axes_are_followed_when_no_imagej_description(tmp_path):
    path, data = _shaped(tmp_path / "tz.tif", "TZYX", (3, 4, 30, 40))
    img = Img(path)
    assert img.metadata["dimensions"] == "tdhw" and img.shape == (3, 4, 30, 40)
    assert np.array_equal(np.asarray(img), data)


def test_a_position_axis_is_a_series(tmp_path):
    path, data = _shaped(tmp_path / "pos.tif", "TRZCYX", (5, 3, 4, 2, 20, 24))
    n, names = get_series_info(path)
    assert n == 3 and names[0] == "Position 1"
    img = Img(path, serie_to_open=2)
    assert img.metadata["dimensions"] == "tdhwc" and img.shape == (5, 4, 20, 24, 2)
    assert np.array_equal(np.asarray(img), np.moveaxis(data[:, 2], 2, -1))
    with pytest.raises(IndexError):
        Img(path, serie_to_open=3)


def test_a_zero_resolution_tag_is_ignored(tmp_path):
    path, _ = _shaped(tmp_path / "zres.tif", "ZYX", (4, 20, 24), resolution=((0, 1), (0, 1)))
    img = Img(path)
    assert img.metadata["dimensions"] == "dhw" and img.shape == (4, 20, 24)


@pytest.mark.skipif(not os.path.isdir(FIJI), reason="the Fiji sample images are not on this computer")
@pytest.mark.parametrize("name,shape,dims", [
    ("MF-2CH-Z-T.tif", (5, 4, 256, 256, 2), "tdhwc"),     # Fiji: 5 series of 2C x 4Z x 5T
    ("10-31 E1.tif", (16, 21, 512, 512), "tdhw"),          # Fiji: 21Z x 16T
    ("CT.dcm", (495, 888), "hw"),
    ("HEART.SEQ", (30, 512, 512), "dhw"),
])
def test_fiji_samples_load_as_fiji_shows_them(name, shape, dims):
    # In a child process: some of these formats are read by Fiji, and a Java VM
    # started inside the test process (it raises access violations on purpose,
    # and stays loaded) made later Qt tests crash at random places.
    import json
    import subprocess
    import sys
    code = ("import json, sys; from batoolset.img import Img; img = Img(sys.argv[1]); "
            "print('RESULT ' + json.dumps([list(img.shape), img.metadata['dimensions']]))")
    run = subprocess.run([sys.executable, "-c", code, os.path.join(FIJI, name)],
                         capture_output=True, text=True, timeout=600)
    line = next((l for l in run.stdout.splitlines() if l.startswith("RESULT ")), None)
    assert line is not None, run.stdout[-2000:] + run.stderr[-2000:]
    got_shape, got_dims = json.loads(line[len("RESULT "):])
    assert tuple(got_shape) == shape and got_dims == dims


@pytest.mark.skipif(not os.path.isdir(FIJI), reason="the Fiji sample images are not on this computer")
def test_every_fiji_sample_but_text_is_accepted():
    refused = sorted(os.path.basename(p) for p in glob.glob(os.path.join(FIJI, "*")) if not is_image_file(p))
    assert refused == ["MaMuT_TGMM_Parhyale_demo.xml", "MessedUpColoc.txt", "first-instar-brain.txt"]


def test_an_unreadable_file_is_reported_not_added(qapp, tmp_path):
    import gui_e2e_harness as H
    from qtpy.QtWidgets import QApplication
    bad = tmp_path / "broken.dcm"
    bad.write_bytes(b"\0not an image at all" * 10)
    good = tmp_path / "good.png"
    from PIL import Image
    Image.fromarray(np.full((20, 30), 90, np.uint8)).save(good)
    g = H.new_gui(qapp)
    try:
        g.add_images_to_new_row([str(bad), str(good)])
        H.settle(qapp, g, lambda: "broken.dcm" in g.statusBar().currentMessage())
        for _ in range(5):
            QApplication.processEvents()
        names = [os.path.basename(i.filename) for i in H.images(g)]
        assert names == ["good.png"], names
    finally:
        g._mark_clean()
        H.close_gui(qapp, g)
