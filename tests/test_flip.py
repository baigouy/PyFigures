"""Image flips are drawing properties (Image2D.flip_h / flip_v): the displayed
image is mirrored, the loaded pixels, channels and pixel size stay the original.
The image editor, the recipe and the MCP tool transform_image all set them."""
import json
import os
import xml.etree.ElementTree as ET

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

# what older versions wrote: a loading script re-reading the file through matplotlib
LEGACY_SCRIPT = ("try:\n    import tifffile as _tf\n    arr = _tf.imread(file_path)\nexcept Exception:\n"
                 "    arr = None\n# flip\narr = arr[:, ::-1]\nfig = plt.figure()\nself.img = fig\n")


def _tif(path):
    """Two 16-bit channels, 0.25 µm pixels: channel 0 bright on the left column,
    channel 1 bright on the top row."""
    import tifffile
    a = np.zeros((2, 20, 30), np.uint16)
    a[0, :, 0] = 4000
    a[1, 0, :] = 900
    tifffile.imwrite(path, a, imagej=True, resolution=(4, 4), metadata={"axes": "CYX", "unit": "um"})
    return str(path)


def _pixels(img):
    q = img.qimage.convertToFormat(img.qimage.Format.Format_RGB32)
    ptr = q.constBits()
    ptr.setsize(q.sizeInBytes())
    return np.frombuffer(ptr, np.uint8).reshape(q.height(), q.bytesPerLine() // 4, 4)[:, :q.width(), :3].copy()


@pytest.mark.parametrize("h,v", [(True, False), (False, True), (True, True)])
def test_flip_mirrors_the_display_and_keeps_the_original_pixels(qapp, tmp_path, h, v):
    from batoolset.drawings.shapes.image2d import Image2D
    from batoolset.serializations.tools import clone_object
    src = _tif(tmp_path / "two_channels.tif")
    plain = Image2D(src)
    flipped = Image2D(src, flip_h=h, flip_v=v)
    expected = _pixels(plain)
    if h:
        expected = expected[:, ::-1]
    if v:
        expected = expected[::-1]
    assert np.array_equal(_pixels(flipped), expected)
    assert np.array_equal(np.asarray(flipped.img), np.asarray(plain.img))    # data untouched
    assert flipped.img.dtype == np.uint16 and flipped.img.shape == (20, 30, 2)
    assert flipped.px_to_unit_conversion_factor == pytest.approx(0.25)
    copy = clone_object(flipped)                                             # save / undo path
    assert (copy.flip_h, copy.flip_v) == (h, v)
    assert np.array_equal(_pixels(copy), expected)


def test_set_flip_and_the_xml_text_values(qapp, tmp_path):
    from batoolset.drawings.shapes.image2d import Image2D
    src = _tif(tmp_path / "a.tif")
    panel = Image2D(src)
    before = _pixels(panel)
    panel.set_flip(True, None)
    assert np.array_equal(_pixels(panel), before[:, ::-1])
    panel.set_flip(False, None)
    assert np.array_equal(_pixels(panel), before)
    assert Image2D(src, flip_h="True", flip_v="False").flip_h is True        # read back from a .pyf
    assert Image2D(src, flip_h="False").flip_h is False


def _image(pyf, index=0):
    return [e for e in ET.parse(pyf).getroot().iter("Image2D")][index]


def test_transform_image_sets_the_properties_not_a_script(tmp_path):
    from pyfigures import mcp_server as M
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="canvas")
    M.add_image(pyf, [], _tif(tmp_path / "a.tif"))
    out = M.transform_image(pyf, [], 0, flip_h=True)
    assert "flip=horizontal" in out, out
    img = _image(pyf)
    assert (img.findtext("flip_h"), img.findtext("flip_v")) == ("True", "False")
    assert img.findtext("custom_loading_script") in (None, "None")
    M.transform_image(pyf, [], 0, flip_v=True)                 # the other axis is kept
    assert (_image(pyf).findtext("flip_h"), _image(pyf).findtext("flip_v")) == ("True", "True")
    assert "flip=cleared" in M.transform_image(pyf, [], 0, flip_h=False, flip_v=False)


def test_exported_png_is_mirrored(tmp_path):
    """The export draws the flipped panel (not only the screen)."""
    from PIL import Image
    from pyfigures import mcp_server as M
    src = str(tmp_path / "corner.png")
    a = np.zeros((40, 60, 3), np.uint8)
    a[:10, :10] = 255                              # white block top-left
    Image.fromarray(a).save(src)
    pngs = {}
    for flip in (False, True):
        pyf = str(tmp_path / f"fig{flip}.pyf")
        M.create_figure(pyf, mode="canvas")
        M.add_image(pyf, [], src)
        if flip:
            M.transform_image(pyf, [], 0, flip_h=True)
        out = str(tmp_path / f"fig{flip}.png")
        M.export_figure(pyf, out, dpi=72)
        pngs[flip] = np.asarray(Image.open(out).convert("L"), float)
    plain, mirrored = pngs[False], pngs[True]
    assert plain.shape == mirrored.shape
    assert np.abs(mirrored - plain[:, ::-1]).mean() < 3, "the export is not the left-right mirror"
    assert np.abs(mirrored - plain).mean() > 3


def test_transform_image_converts_an_old_flip_script(tmp_path):
    from pyfigures import mcp_server as M
    from pyfigures.mcp_tools.core import _encode_str
    pyf = str(tmp_path / "fig.pyf")
    M.create_figure(pyf, mode="canvas")
    M.add_image(pyf, [], _tif(tmp_path / "a.tif"))
    tree = ET.parse(pyf)
    img = next(tree.getroot().iter("Image2D"))
    node = img.find("custom_loading_script")
    if node is None:
        node = ET.SubElement(img, "custom_loading_script")
    node.text = _encode_str(LEGACY_SCRIPT)
    tree.write(pyf, encoding="unicode")
    M.transform_image(pyf, [], 0, flip_v=True)                 # horizontal came from the script
    img = _image(pyf)
    assert (img.findtext("flip_h"), img.findtext("flip_v")) == ("True", "True")
    assert img.findtext("custom_loading_script") == "None"


def test_legacy_state_recognises_only_old_flip_scripts():
    from pyfigures.flip import legacy_state
    assert legacy_state(LEGACY_SCRIPT) == (True, False)
    assert legacy_state(None) is None
    assert legacy_state("self.img = Img(file_path)") is None


def test_recipe_flip_sets_the_properties(tmp_path):
    from pyfigures.recipe import build_figure_from_recipe
    _tif(tmp_path / "a.tif")
    (tmp_path / "r.json").write_text(json.dumps(
        {"output": "fig.pyf", "rows": [[{"image": "a.tif", "flip": "hv"}]]}), encoding="utf-8")
    build_figure_from_recipe(str(tmp_path / "r.json"))
    img = _image(str(tmp_path / "fig.pyf"))
    assert (img.findtext("flip_h"), img.findtext("flip_v")) == ("True", "True")
    assert img.findtext("custom_loading_script") in (None, "None")


def test_image_editor_flip_boxes(qapp, tmp_path):
    """Ticking a box mirrors the edited image at once; an old flip script shows as ticked and
    is replaced by the properties (the original pixels reloaded) when the user changes it."""
    from batoolset.drawings.shapes.image2d import Image2D
    from pyfigures.gui.annotation_editor import MainWindow, VectorialDrawPane2
    src = _tif(tmp_path / "a.tif")
    ed = MainWindow(qt_viewer=VectorialDrawPane2(background=Image2D(src)))
    before = _pixels(ed.qt_viewer.background)
    assert not ed.flip_h_checkbox.isChecked() and not ed.flip_v_checkbox.isChecked()
    ed.flip_h_checkbox.setChecked(True)
    assert ed.qt_viewer.background.flip_h is True
    assert np.array_equal(_pixels(ed.qt_viewer.background), before[:, ::-1])

    legacy = Image2D(src, custom_loading_script=LEGACY_SCRIPT)
    ed = MainWindow(qt_viewer=VectorialDrawPane2(background=legacy))
    assert ed.flip_h_checkbox.isChecked() and not ed.flip_v_checkbox.isChecked()
    ed.flip_v_checkbox.setChecked(True)
    bg = ed.qt_viewer.background
    assert bg.custom_loading_script is None and (bg.flip_h, bg.flip_v) == (True, True)
    assert bg.img.dtype == np.uint16                          # the original file, not the 8-bit copy
    assert np.array_equal(_pixels(bg), before[::-1, ::-1])
