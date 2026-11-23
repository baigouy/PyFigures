"""User 2026-11-23 (chat: "can you use an ROI that would even better fit to the shape of the
blobs"; the model answered that detection only does boxes and ellipses): "polygonal ROI could be
done by default in the segmentation". detect_objects now traces each object's outline by default;
rect / ellipse remain when asked."""
import json
import os
import xml.etree.ElementTree as ET

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _shoelace(pts):
    x = np.array([p[0] for p in pts])
    y = np.array([p[1] for p in pts])
    return 0.5 * abs(float(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))


def _figure(tmp_path):
    import tifffile
    from pyfigures import mcp_server as M
    img = np.full((120, 160), 20, np.uint8)
    yy, xx = np.mgrid[:120, :160]
    img[(yy - 40) ** 2 + (xx - 40) ** 2 <= 18 ** 2] = 220          # a disc, r = 18
    img[60:100, 90:100] = 220                                       # an L: 40 x 10 ...
    img[90:100, 90:140] = 220                                       # ... + 10 x 50
    tif = str(tmp_path / "shapes.tif")
    tifffile.imwrite(tif, img)
    pyf = str(tmp_path / "f.pyf")
    M.create_figure(pyf, num_groups=1)
    M.add_image(pyf, [0], tif)
    return pyf


def test_outlines_by_default_and_they_follow_the_shapes(tmp_path):
    from pyfigures import mcp_server as M
    pyf = _figure(tmp_path)
    res = json.loads(M.detect_objects(pyf, [0], 0, min_area=50))
    assert res["shape"] == "polygon" and res["added"] == 2
    from pyfigures.object_detection import detect
    import tifffile
    objects, _ = detect(tifffile.imread(str(tmp_path / "shapes.tif")), min_area=50, outline_grow=1)
    for o in objects:
        poly = _shoelace(o["outline"])
        assert 0.85 * o["area"] < poly < 1.3 * o["area"], (o["area"], poly)    # hugs the object
        assert poly < o["width"] * o["height"]
    ell = min(objects, key=lambda o: o["area"] / (o["width"] * o["height"]))     # the L
    assert _shoelace(ell["outline"]) < 0.5 * ell["width"] * ell["height"]       # not its box
    tags = [a.tag for a in ET.parse(pyf).getroot().find(".//Image2D").find("annotations")]
    assert tags == ["Polygon2D", "Polygon2D"]


def test_boxes_and_ellipses_when_asked(tmp_path):
    from pyfigures import mcp_server as M
    pyf = _figure(tmp_path)
    assert json.loads(M.detect_objects(pyf, [0], 0, min_area=50, shape="rect"))["added"] == 2
    assert json.loads(M.detect_objects(pyf, [0], 0, min_area=50, shape="circle"))["added"] == 2   # = ellipse
    tags = [a.tag for a in ET.parse(pyf).getroot().find(".//Image2D").find("annotations")]
    assert tags == ["Rectangle2D"] * 2 + ["Ellipse2D"] * 2
    assert M.detect_objects(pyf, [0], 0, shape="star").startswith("ERROR: shape is \"polygon\"")
