"""
Regression tests for companion/sidecar files that must never be opened as images.

Leica LAS X writes a real `.lif` image plus a `.lifext` metadata sidecar. The
sidecar looks like an image to file pickers and drag-and-drop, but Bio-Formats
reads it into a bogus image with wrong dimensions instead of erroring. Only the
`.lif` itself is a real image; `.lifext` must be rejected everywhere.
"""
import numpy as np
import pytest

from batoolset.img import (
    is_forbidden_image_file,
    get_series_info,
    FORBIDDEN_IMAGE_EXTS,
)


class TestForbiddenExtHelper:
    def test_lifext_is_forbidden(self):
        assert is_forbidden_image_file(r'C:\imgs\260304_test_muscle_clones1.lifext')

    def test_case_insensitive(self):
        assert is_forbidden_image_file('SAMPLE.LIFEXT')
        assert is_forbidden_image_file('Sample.LifExt')

    def test_real_lif_is_allowed(self):
        assert not is_forbidden_image_file('sample.lif')

    @pytest.mark.parametrize('name', ['a.tif', 'a.tiff', 'a.png', 'a.jpg', 'a.svg', 'a.lsm'])
    def test_ordinary_images_allowed(self, name):
        assert not is_forbidden_image_file(name)

    def test_non_string_inputs(self):
        assert not is_forbidden_image_file(None)
        assert not is_forbidden_image_file(123)
        assert not is_forbidden_image_file(['a.lifext'])

    def test_lifext_registered(self):
        assert '.lifext' in FORBIDDEN_IMAGE_EXTS


class TestGetSeriesInfoSkipsForbidden:
    def test_lifext_reports_single_series_without_probing(self):
        # must short-circuit to (1, None): probing would hit Bio-Formats and lie
        assert get_series_info(r'C:\imgs\clones.lifext') == (1, None)


class TestGuiRejectsForbidden:
    def test_resolve_series_drops_lifext_keeps_real_files(self, qapp):
        from pyfigures.gui.pfgui import EZFIG_GUI
        EZFIG_GUI.show_tips = lambda self: None
        gui = EZFIG_GUI()
        try:
            out = gui._resolve_series_for_files([r'C:\imgs\clones.lifext', r'C:\imgs\real.tif'])
            assert out == [r'C:\imgs\real.tif']
        finally:
            gui._dirty = False  # avoid the unsaved-changes prompt on close in headless tests
            gui.close()
