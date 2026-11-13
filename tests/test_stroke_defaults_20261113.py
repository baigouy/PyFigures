"""ROI lines were 2 pt thick by default from the chat and the MCP (user, 2026-11-13: "the
line stroke of ROIs is too big, typically it should be by default 0.65 pt"). The stroke
is in points on the page (the image's size does not change it); the panel editor
already drew 0.65 pt."""
import inspect
import json

import pytest

from pyfigures.mcp_server import (add_roi_rect, add_roi_ellipse, add_roi_line, add_roi_polygon,
                                  add_zoom_callout, detect_objects, get_annotations, create_figure, add_image)


@pytest.mark.parametrize('tool', [add_roi_rect, add_roi_ellipse, add_roi_line, add_roi_polygon,
                                  add_zoom_callout, detect_objects])
def test_rois_default_to_a_paper_line(tool):
    assert inspect.signature(tool).parameters['stroke'].default == 0.65
    assert 'points on the page' in tool.__doc__


def test_a_zoom_callout_box_and_leaders_are_065_pt(tmp_path):
    import numpy as np
    from PIL import Image
    p = str(tmp_path / 'f.pyf')
    create_figure(p, mode='groups', num_groups=1)
    Image.fromarray(np.full((100, 120), 90, np.uint8)).save(tmp_path / 'a.png')
    add_image(p, [0], str(tmp_path / 'a.png'))
    add_zoom_callout(p, [0], 0, source_x=10, source_y=50, source_w=20, source_h=20,
                     parent_width=120, parent_height=100)
    strokes = {a['type']: a.get('stroke') for a in json.loads(get_annotations(p)) if a.get('stroke') is not None}
    assert strokes.get('Rectangle2D') == 0.65 and strokes.get('Line2D') == 0.65, strokes
