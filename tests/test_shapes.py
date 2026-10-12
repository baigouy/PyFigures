"""
Tests for shape classes in batoolset/drawings/shapes/.

Sections:
  - No-Qt tests: Position, SerializableGUIparameters, areIndicesOverlapping
  - Qt tests (require qapp fixture): Rectangle2D, Square2D, Circle2D, Ellipse2D,
    Line2D, Point2D, Polygon2D, PolyLine2D, Freehand2D, ScaleBar,
    SerializableQFont, TAText2D, Group
"""
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_false(d):
    return all(not v for v in d.values())


# ===========================================================================
# Position  (no Qt)
# ===========================================================================

class TestPosition:
    def setup_method(self):
        from batoolset.drawings.shapes.Position import Position
        self.Position = Position

    def test_empty_by_default(self):
        p = self.Position()
        assert p.isEmpty()

    def test_set_top_left(self):
        p = self.Position('top-left')
        assert p.check_position('top')
        assert p.check_position('left')
        assert not p.check_position('bottom')
        assert not p.check_position('right')

    def test_set_bottom_right(self):
        p = self.Position('bottom-right')
        assert p.check_position('bottom')
        assert p.check_position('right')

    def test_set_center_h(self):
        p = self.Position('center_h')
        assert p.check_position('center_h')

    def test_position_to_string_roundtrip(self):
        for pos in ('top left', 'bottom right', 'center_h', 'top right'):
            p = self.Position(pos)
            s = p.position_to_string()
            assert s  # non-empty
            p2 = self.Position(s)
            assert p2.get_position() == p.get_position()

    def test_is_not_empty_after_set(self):
        p = self.Position('top')
        assert not p.isEmpty()

    def test_get_packing_orientation_top(self):
        from batoolset.drawings.shapes.Position import packing_modes
        p = self.Position('top')
        assert p.get_packing_orientation() == packing_modes[1]

    def test_get_packing_orientation_bottom(self):
        from batoolset.drawings.shapes.Position import packing_modes
        p = self.Position('bottom')
        assert p.get_packing_orientation() == packing_modes[3]

    def test_str(self):
        p = self.Position('top left')
        assert 'top' in str(p)
        assert 'left' in str(p)


# ===========================================================================
# SerializableGUIparameters  (no Qt)
# ===========================================================================

class TestSerializableGUIparameters:
    def test_instantiation(self):
        from batoolset.drawings.shapes.serializableguiparams import SerializableGUIparameters
        obj = SerializableGUIparameters(space=5)
        assert obj.space == 5

    def test_different_space(self):
        from batoolset.drawings.shapes.serializableguiparams import SerializableGUIparameters
        assert SerializableGUIparameters(space=0).space == 0
        assert SerializableGUIparameters(space=42).space == 42


# ===========================================================================
# areIndicesOverlapping  (no Qt)
# ===========================================================================

class TestAreIndicesOverlapping:
    def setup_method(self):
        from batoolset.drawings.shapes.group import areIndicesOverlapping
        self.fn = areIndicesOverlapping

    def test_no_overlap(self):
        assert self.fn([[0, 1], [2, 3]]) is False

    def test_overlap(self):
        assert self.fn([[0, 2], [2, 4]]) is True

    def test_single_element_no_overlap(self):
        assert self.fn([[0, 1]]) is False

    def test_adjacent_no_overlap(self):
        # [0,1] ends at 1; [2,3] starts at 2 — no overlap
        assert self.fn([[0, 1], [2, 3], [4, 5]]) is False

    def test_overlap_in_middle(self):
        assert self.fn([[0, 1], [3, 5], [4, 6]]) is True


# ===========================================================================
# Rectangle2D  (Qt)
# ===========================================================================

class TestRectangle2D:
    def test_basic_geometry(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=10, y=20, width=100, height=50)
        assert r.x() == 10
        assert r.y() == 20
        assert r.width() == 100
        assert r.height() == 50

    def test_default_color(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=0, y=0, width=10, height=10)
        assert r.color == 0xFFFFFF

    def test_custom_color(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=0, y=0, width=10, height=10, color=0xFF0000)
        assert r.color == 0xFF0000

    def test_to_dict_keys(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=5, y=5, width=80, height=40)
        d = r.to_dict()
        for key in ('x', 'y', 'width', 'height'):
            assert key in d

    def test_to_dict_values(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=5, y=5, width=80, height=40)
        d = r.to_dict()
        assert d['width'] == 80
        assert d['height'] == 40

    def test_aspect_ratio(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=0, y=0, width=200, height=100)
        assert r.getAR() == pytest.approx(2.0)
        assert r.getAR(invert=True) == pytest.approx(0.5)

    def test_getRect(self, qapp):
        from batoolset.drawings.shapes.rectangle2d import Rectangle2D
        r = Rectangle2D(x=1, y=2, width=30, height=15)
        rect = r.getRect()
        assert rect.width() == pytest.approx(30)
        assert rect.height() == pytest.approx(15)


# ===========================================================================
# Square2D  (Qt)
# ===========================================================================

class TestSquare2D:
    def test_is_square(self, qapp):
        from batoolset.drawings.shapes.square2d import Square2D
        s = Square2D(x=0, y=0, width=64)
        assert s.width() == s.height()

    def test_width_value(self, qapp):
        from batoolset.drawings.shapes.square2d import Square2D
        s = Square2D(x=0, y=0, width=128)
        assert s.width() == 128


# ===========================================================================
# Ellipse2D  (Qt)
# ===========================================================================

class TestEllipse2D:
    def test_basic(self, qapp):
        from batoolset.drawings.shapes.ellipse2d import Ellipse2D
        e = Ellipse2D(x=0, y=0, width=50, height=30)
        assert e.width() == 50
        assert e.height() == 30

    def test_to_dict(self, qapp):
        from batoolset.drawings.shapes.ellipse2d import Ellipse2D
        e = Ellipse2D(x=0, y=0, width=50, height=30)
        d = e.to_dict()
        assert 'width' in d
        assert 'height' in d


# ===========================================================================
# Circle2D  (Qt)
# ===========================================================================

class TestCircle2D:
    def test_is_circle(self, qapp):
        from batoolset.drawings.shapes.circle2d import Circle2D
        c = Circle2D(x=0, y=0, width=64)
        assert c.width() == c.height()

    def test_width_value(self, qapp):
        from batoolset.drawings.shapes.circle2d import Circle2D
        c = Circle2D(x=0, y=0, width=100)
        assert c.width() == 100


# ===========================================================================
# Line2D  (Qt)
# ===========================================================================

class TestLine2D:
    def test_basic(self, qapp):
        from batoolset.drawings.shapes.line2d import Line2D
        line = Line2D(x1=0, y1=0, x2=10, y2=0)
        assert line.width() == pytest.approx(10)

    def test_to_dict(self, qapp):
        from batoolset.drawings.shapes.line2d import Line2D
        line = Line2D(x1=0, y1=0, x2=10, y2=0)
        d = line.to_dict()
        assert isinstance(d, dict)

    def test_vertical_line_height(self, qapp):
        from batoolset.drawings.shapes.line2d import Line2D
        line = Line2D(x1=5, y1=0, x2=5, y2=20)
        assert line.height() == pytest.approx(20)


# ===========================================================================
# Point2D  (Qt)
# ===========================================================================

class TestPoint2D:
    def test_instantiation(self, qapp):
        from batoolset.drawings.shapes.point2d import Point2D
        p = Point2D(x=10, y=20)
        assert p.width() == 0
        assert p.height() == 0

    def test_to_dict(self, qapp):
        from batoolset.drawings.shapes.point2d import Point2D
        p = Point2D(x=10, y=20)
        d = p.to_dict()
        assert isinstance(d, dict)


# ===========================================================================
# Polygon2D  (Qt)
# ===========================================================================

class TestPolygon2D:
    def test_instantiation_empty(self, qapp):
        from batoolset.drawings.shapes.polygon2d import Polygon2D
        poly = Polygon2D()
        assert poly is not None

    def test_with_coords(self, qapp):
        from batoolset.drawings.shapes.polygon2d import Polygon2D
        # coords_as_list is a flat list: [x0, y0, x1, y1, ...]
        poly = Polygon2D(coords_as_list=[0, 0, 10, 0, 10, 10, 0, 10])
        assert poly.width() > 0
        assert poly.height() > 0

    def test_to_dict(self, qapp):
        from batoolset.drawings.shapes.polygon2d import Polygon2D
        poly = Polygon2D(coords_as_list=[0, 0, 10, 0, 10, 10])
        d = poly.to_dict()
        assert isinstance(d, dict)


# ===========================================================================
# PolyLine2D  (Qt)
# ===========================================================================

class TestPolyLine2D:
    def test_instantiation(self, qapp):
        from batoolset.drawings.shapes.polyline2d import PolyLine2D
        pl = PolyLine2D(coords_as_list=[0, 0, 10, 5, 20, 0])
        assert pl is not None

    def test_bounding_rect(self, qapp):
        from batoolset.drawings.shapes.polyline2d import PolyLine2D
        pl = PolyLine2D(coords_as_list=[0, 0, 10, 5, 20, 0])
        assert pl.width() > 0


# ===========================================================================
# Freehand2D  (Qt)
# ===========================================================================

class TestFreehand2D:
    def test_instantiation(self, qapp):
        from batoolset.drawings.shapes.freehand2d import Freehand2D
        fh = Freehand2D(coords_as_list=[0, 0, 5, 5, 10, 0])
        assert fh is not None

    def test_invert_coords(self, qapp):
        from batoolset.drawings.shapes.freehand2d import Freehand2D
        fh = Freehand2D(coords_as_list=[1, 2, 3, 4], invert_coords=True)
        assert fh is not None


# ===========================================================================
# TAText2D  (Qt)
# ===========================================================================

class TestTAText2D:
    def test_instantiation(self, qapp):
        from batoolset.drawings.shapes.txt2d import TAText2D
        t = TAText2D(text='Hello')
        assert t is not None

    def test_range_default_none(self, qapp):
        from batoolset.drawings.shapes.txt2d import TAText2D
        t = TAText2D(text='A')
        assert t.range is None

    def test_range_set(self, qapp):
        from batoolset.drawings.shapes.txt2d import TAText2D
        t = TAText2D(text='A', range=[0, 2])
        assert t.range == [0, 2]

    def test_is_letter_default(self, qapp):
        from batoolset.drawings.shapes.txt2d import TAText2D
        t = TAText2D(text='A')
        assert t.is_letter is False


# ===========================================================================
# SerializableQFont  (Qt)
# ===========================================================================

class TestSerializableQFont:
    def test_instantiation(self, qapp):
        from batoolset.drawings.shapes.serializablefont import SerializableQFont
        f = SerializableQFont()
        assert f is not None

    def test_to_dict_from_dict_roundtrip(self, qapp):
        from batoolset.drawings.shapes.serializablefont import SerializableQFont
        f = SerializableQFont(foreground=0xFF0000)
        d = f.to_dict()
        f2 = SerializableQFont.from_dict(d)
        assert f2 is not None
        assert f2.foreground == f.foreground


# ===========================================================================
# ScaleBar  (Qt)
# ===========================================================================

class TestScaleBar:
    def test_instantiation(self, qapp):
        from batoolset.drawings.shapes.scalebar import ScaleBar
        sb = ScaleBar(bar_width_in_units=10, legend='10 µm', unit_to_pixel_conversion_factor=2)
        assert sb is not None

    def test_legend(self, qapp):
        from batoolset.drawings.shapes.scalebar import ScaleBar
        sb = ScaleBar(bar_width_in_units=5, legend='5 µm')
        assert sb is not None


# ===========================================================================
# Group  (Qt)
# ===========================================================================

class TestGroup:
    def test_empty_group(self, qapp):
        from batoolset.drawings.shapes.group import Group
        g = Group()
        assert g is not None

    def _make_images(self, n):
        from batoolset.drawings.shapes.image2d import Image2D
        Image2D._lazy_mode = True
        try:
            return [Image2D(width=90, height=90) for _ in range(n)]
        finally:
            Image2D._lazy_mode = False

    def test_group_with_images(self, qapp):
        from batoolset.drawings.shapes.group import Group
        images = self._make_images(3)
        g = Group(*images)
        assert len(g.content) == 3

    def test_get_combined_bounds(self, qapp):
        from batoolset.drawings.shapes.group import Group
        images = self._make_images(3)
        g = Group(*images)
        bounds = g.getCombinedBoundsAtIndices([0, 2])
        assert bounds is not None

    def test_get_combined_bounds_empty_returns_none(self, qapp):
        from batoolset.drawings.shapes.group import Group
        images = self._make_images(3)
        g = Group(*images)
        assert g.getCombinedBoundsAtIndices([]) is None


# ===========================================================================
# Image2D publication style  (no Qt for pure-logic tests; Qt for renderer tests)
# ===========================================================================

class TestImage2DPublicationStyleNoQt:
    """Tests for publication style that do not require Qt."""

    def test_best_helvetica_clone_returns_string(self):
        from batoolset.matplolibs.tools import best_helvetica_clone
        font = best_helvetica_clone()
        assert isinstance(font, str)
        assert len(font) > 0

    def test_best_helvetica_clone_is_available(self):
        import matplotlib.font_manager as fm
        from batoolset.matplolibs.tools import best_helvetica_clone
        available = {f.name.lower() for f in fm.fontManager.ttflist}
        assert best_helvetica_clone().lower() in available

    def test_transform_svg_bytes_stroke_replaced(self):
        from batoolset.drawings.shapes.image2d import Image2D
        svg = b'<svg><path style="stroke-width: 2px"/></svg>'
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        img.publication_svg_stroke_width = 0.65
        result = img._transform_svg_bytes(svg)
        assert b'0.65pt' in result
        assert b'2px' not in result

    def test_transform_svg_bytes_stroke_attr_replaced(self):
        from batoolset.drawings.shapes.image2d import Image2D
        svg = b'<svg><path stroke-width="3"/></svg>'
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        img.publication_svg_stroke_width = 0.65
        result = img._transform_svg_bytes(svg)
        assert b'0.65pt' in result

    def test_transform_svg_bytes_font_family_replaced(self):
        from batoolset.drawings.shapes.image2d import Image2D
        svg = b'<svg><text style="font-family: Times New Roman"/></svg>'
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        img.publication_font = 'Arial'
        result = img._transform_svg_bytes(svg)
        assert b'Arial' in result
        assert b'Times New Roman' not in result

    def test_transform_svg_bytes_no_stroke_when_none(self):
        from batoolset.drawings.shapes.image2d import Image2D
        svg = b'<svg><path style="stroke-width: 2px"/></svg>'
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        img.publication_svg_stroke_width = None
        result = img._transform_svg_bytes(svg)
        assert b'2px' in result  # unchanged

    def test_transform_svg_bytes_no_font_when_none(self):
        from batoolset.drawings.shapes.image2d import Image2D
        svg = b'<svg><text style="font-family: Times New Roman"/></svg>'
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        img.publication_font = None
        result = img._transform_svg_bytes(svg)
        assert b'Times New Roman' in result  # unchanged


class TestImage2DPublicationStyleDefaults:
    """Default parameter values — needs Qt for Image2D construction."""

    def test_publication_style_default_true(self, qapp):
        from batoolset.drawings.shapes.image2d import Image2D
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        assert img.publication_style is True

    def test_publication_font_size_default(self, qapp):
        from batoolset.drawings.shapes.image2d import Image2D
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        assert img.publication_font_size == 12

    def test_publication_line_width_default(self, qapp):
        from batoolset.drawings.shapes.image2d import Image2D
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        assert img.publication_line_width == 0.65

    def test_publication_svg_stroke_width_default(self, qapp):
        from batoolset.drawings.shapes.image2d import Image2D
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        assert img.publication_svg_stroke_width == 0.65

    def test_publication_font_default_is_helvetica_clone(self, qapp):
        from batoolset.drawings.shapes.image2d import Image2D
        from batoolset.matplolibs.tools import best_helvetica_clone
        Image2D._lazy_mode = True
        try:
            img = Image2D(width=10, height=10)
        finally:
            Image2D._lazy_mode = False
        assert img.publication_font == best_helvetica_clone()


class TestImage2DPublicationStyleMatplotlib:
    """Tests for matplotlib figure export mode."""

    def _make_mpl_image2d(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        from batoolset.drawings.shapes.image2d import Image2D
        fig, ax = plt.subplots()
        x = np.linspace(0, 2 * np.pi, 50)
        ax.plot(x, np.sin(x), linewidth=2.0)
        ax.set_xlabel('X', fontsize=14)
        img = Image2D(fig, publication_style=True,
                      publication_font_size=6, publication_line_width=0.25)
        return img, fig

    def test_display_buffer_does_not_change_linewidth(self, qapp):
        import matplotlib.pyplot as plt
        img, fig = self._make_mpl_image2d()
        lw_before = [ln.get_linewidth() for ax in fig.get_axes() for ln in ax.get_lines()]
        img._toBuffer(bufferType='svg')
        lw_after = [ln.get_linewidth() for ax in fig.get_axes() for ln in ax.get_lines()]
        for b, a in zip(lw_before, lw_after):
            assert abs(b - a) < 1e-6
        plt.close(fig)

    def test_export_buffer_restores_linewidth(self, qapp):
        import matplotlib.pyplot as plt
        img, fig = self._make_mpl_image2d()
        lw_before = [ln.get_linewidth() for ax in fig.get_axes() for ln in ax.get_lines()]
        img._toBuffer(bufferType='svg', apply_publication=True)
        lw_after = [ln.get_linewidth() for ax in fig.get_axes() for ln in ax.get_lines()]
        for b, a in zip(lw_before, lw_after):
            assert abs(b - a) < 1e-6
        plt.close(fig)

    def test_export_buffer_reduces_stroke_in_svg(self, qapp):
        import re
        import matplotlib.pyplot as plt
        img, fig = self._make_mpl_image2d()
        buf = img._toBuffer(bufferType='svg', apply_publication=True)
        svg_text = buf.read().decode('utf-8')
        widths = [float(v) for v in re.findall(r'stroke-width:\s*([\d.]+)', svg_text)]
        if widths:
            assert max(widths) < 2.0, f"Stroke widths not reduced: max={max(widths):.2f}"
        plt.close(fig)

    def test_enter_exit_export_mode_restores_renderer(self, qapp):
        import matplotlib.pyplot as plt
        img, fig = self._make_mpl_image2d()
        original_renderer = img.renderer
        img.enter_export_mode()
        img.exit_export_mode()
        assert img.renderer is original_renderer
        plt.close(fig)


class TestImage2DPublicationStyleSVG:
    """Tests for SVG image export mode."""

    def _make_svg_bytes(self, stroke='2'):
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            f'<path style="stroke: black; stroke-width: {stroke}px" d="M0 0 L100 100"/>'
            f'</svg>'
        ).encode('utf-8')

    def test_enter_exit_export_mode_svg(self, qapp):
        import tempfile, os
        from batoolset.drawings.shapes.image2d import Image2D
        svg_bytes = self._make_svg_bytes(stroke='3')
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            f.write(svg_bytes)
            svg_path = f.name
        try:
            img = Image2D(svg_path,
                          publication_style=True, publication_svg_stroke_width=0.65)
            original_renderer = img.renderer
            img.enter_export_mode()
            export_renderer = img.renderer
            img.exit_export_mode()
            assert img.renderer is original_renderer
            # The export renderer should differ (transformed SVG bytes)
            assert export_renderer is not original_renderer
        finally:
            os.unlink(svg_path)

    def test_enter_export_mode_disabled_does_not_swap(self, qapp):
        import tempfile, os
        from batoolset.drawings.shapes.image2d import Image2D
        svg_bytes = self._make_svg_bytes(stroke='3')
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
            f.write(svg_bytes)
            svg_path = f.name
        try:
            img = Image2D(svg_path, publication_style=False)
            original_renderer = img.renderer
            img.enter_export_mode()
            assert img.renderer is original_renderer
            img.exit_export_mode()
        finally:
            os.unlink(svg_path)
