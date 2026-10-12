"""
Regression tests for the typography-tidy helper: the pure core function
(batoolset.strings.typography), the MCP tidy_text tool, and the GUI action.
"""
import os
import tempfile

import numpy as np
import pytest

from batoolset.img import Img
from batoolset.strings.typography import tidy_typography as T, tidy_html as H


class TestCore:
    @pytest.mark.parametrize('src,want', [
        ('2*3', '2×3'),
        ('10 * 20', '10 × 20'),
        ('37 degrees C', '37 °C'),
        ('45 degrees', '45°'),
        ('10µm', '10 µm'),
        ('2.5mm', '2.5 mm'),
        ('50kDa', '50 kDa'),
        ('10-20', '10–20'),
        ('-5', '−5'),
        ('a   b', 'a b'),
        ('trailing   ', 'trailing'),
    ])
    def test_applies(self, src, want):
        assert T(src) == want

    @pytest.mark.parametrize('src', [
        '2D', '3D', 'H2O', 'CO2', '10K cells', 'p53', 'T2A', '10x',
        '5 degrees of freedom', '2024-01-15', 'a=2*b',
    ])
    def test_leaves_alone(self, src):
        assert T(src) == src

    def test_idempotent(self):
        s = 'heated 37 degrees C for 10-20min at -5 and 2*3'
        assert T(s) == T(T(s))

    def test_none_and_empty(self):
        assert T('') == '' and T(None) is None


class TestHtml:
    def test_tags_untouched(self):
        assert H('<font color="#ff0000">2*3</font>') == '<font color="#ff0000">2×3</font>'

    def test_style_block_protected(self):
        html = '<style>p { margin:-1px 0 0 0; }</style><body>10µm</body>'
        out = H(html)
        assert 'margin:-1px' in out          # CSS negative not mangled
        assert '10 µm' in out                 # body text tidied

    def test_none_and_empty(self):
        assert H('') == '' and H(None) is None


@pytest.fixture
def sample_tif():
    p = os.path.join(tempfile.mkdtemp(), 't.tif')
    Img(np.full((16, 16), 90, dtype=np.uint8), dimensions='hw').save(p)
    return p


class TestMcpTidyText:
    def test_tidy_text_changes_and_is_reported(self, sample_tif):
        from pyfigures.mcp_server import tidy_text, create_figure, add_image
        pyf = os.path.join(tempfile.mkdtemp(), 'm.pyf')
        create_figure(pyf)                       # free-canvas
        add_image(pyf, [], sample_tif, label='bar 20µm at -3 range 4-8')
        res = tidy_text(pyf)
        assert 'changed' in res and '1 of' in res
        from batoolset.files.tools import read_string_from_file
        assert 'µm' in read_string_from_file(pyf)
        # second run is a no-op (idempotent)
        assert '0 of' in tidy_text(pyf)


class TestGuiAction:
    @pytest.fixture
    def gui(self, qapp):
        from qtpy.QtWidgets import QMessageBox
        QMessageBox.warning = staticmethod(lambda *a, **k: QMessageBox.Yes)
        from pyfigures.gui.pfgui import EZFIG_GUI
        EZFIG_GUI.show_tips = lambda self: None
        g = EZFIG_GUI()
        yield g
        g._dirty = False
        g.close()

    def test_menu_has_action(self, gui):
        labels = []
        for act in gui.menuBar.actions():
            if act.menu() and act.text() == 'Annotations':
                labels = [a.text() for a in act.menu().actions()]
        assert any('Tidy text typography' in l for l in labels)

    def test_tidy_all_text_fixes_captions_only(self, gui, sample_tif):
        from batoolset.drawings.shapes.image2d import Image2D
        from batoolset.drawings.shapes.txt2d import TAText2D
        img = Image2D(sample_tif)
        img.annotations.append(TAText2D('scale 10µm at 2*3 range 5-9 val -5'))
        img.annotations.append(TAText2D('2D H2O 10K cells'))   # must stay
        gui.paint.EZFIG_panel.shapes_to_draw.append(img)
        gui.paint.EZFIG_panel.update_size()
        gui.tidy_all_text()
        p0 = img.annotations[0].getPlainText()
        for tok in ['10 µm', '5–9', '−5', '2×3']:
            assert tok in p0, (tok, p0)
        assert img.annotations[1].getPlainText() == '2D H2O 10K cells'
