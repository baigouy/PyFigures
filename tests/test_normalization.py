"""
Regression tests for batoolset.drawings.shapes.image2d._normalize_to_uint8.

History: numpy>=2 computes `255.0 / (mx - mn)` in the dtype of mx/mn (NEP 50),
so float16 images with small display ranges overflowed the scale to inf and the
whole displayed image became NaN (RuntimeWarning: overflow encountered in
divide / invalid value encountered in multiply / invalid value encountered in
cast). Similar overflows happened for float64 images with extreme values and
for ranges whose scale exceeds float32 max.

Every test here runs with RuntimeWarning promoted to an error: normalization of
ANY finite display range must be silent, and min/max of the range must map to
exactly 0/255.
"""
import numpy as np
import pytest

from batoolset.drawings.shapes.image2d import _normalize_to_uint8


pytestmark = pytest.mark.filterwarnings('error::RuntimeWarning')


# ---------------------------------------------------------------------------
# The exact failure modes seen in the wild
# ---------------------------------------------------------------------------

class TestOverflowRegressions:
    def test_float16_tiny_range(self):
        """float16 image with a small range: 255/range overflows float16 -> was all-NaN."""
        a = np.array([[0.0, 1e-4], [2e-4, 3e-4]], dtype=np.float16)
        r = _normalize_to_uint8(a, a.min(), a.max())
        assert r.dtype == np.uint8
        assert r[0, 0] == 0
        assert r[1, 1] == 255

    def test_float16_full_range(self):
        """float16 spanning its whole representable range."""
        a = np.array([[-65000.0, 0.0], [1000.0, 65000.0]], dtype=np.float16)
        r = _normalize_to_uint8(a, a.min(), a.max())
        assert r[0, 0] == 0
        assert r[1, 1] == 255

    def test_float64_hot_pixel_beyond_float32(self):
        """float64 image with a hot pixel far above float32 max, custom display range."""
        a = np.array([[0.0, 100.0], [1e300, 200.0]], dtype=np.float64)
        r = _normalize_to_uint8(a, 0.0, 200.0)
        assert r[0, 0] == 0
        assert r[1, 0] == 255   # hot pixel clips to the top of the range
        assert r[1, 1] == 255

    def test_float64_range_beyond_float32(self):
        """display range itself does not fit in float32."""
        a = np.array([[-1e40, 0.0], [1e40, 2e40]], dtype=np.float64)
        r = _normalize_to_uint8(a, -1e40, 2e40)
        assert r[0, 0] == 0
        assert r[1, 1] == 255

    def test_float32_range_with_scale_beyond_float32(self):
        """range so small that 255/range exceeds float32 max -> float64 fallback."""
        a = np.array([[0.0, 1e-38], [2e-38, 4e-38]], dtype=np.float32)
        r = _normalize_to_uint8(a, 0.0, 4e-38)
        assert r[0, 0] == 0
        assert r[1, 1] == 255

    def test_subnormal_range_returns_black(self):
        """range so small that even float64 cannot hold the scale -> black, not NaN."""
        a = np.array([[0.0, 5e-324]], dtype=np.float64)
        r = _normalize_to_uint8(a, 0.0, 5e-324)
        assert r.dtype == np.uint8
        assert r.max() == 0

    def test_nan_and_inf_pixels(self):
        """NaN renders black, +/-inf clip to the ends of the range."""
        a = np.array([[np.inf, -np.inf], [np.nan, 5.0]], dtype=np.float32)
        r = _normalize_to_uint8(a, 0.0, 10.0)
        assert r[0, 0] == 255
        assert r[0, 1] == 0
        assert r[1, 0] == 0
        assert r[1, 1] == 128

    def test_non_finite_display_range_uses_the_finite_pixels(self):
        # a NaN / inf bound (from NaN or inf pixels) used to give a black image
        a = np.array([[0.0, 1.0]], dtype=np.float32)
        assert _normalize_to_uint8(a, 0.0, np.inf).tolist() == [[0, 255]]
        assert _normalize_to_uint8(a, np.nan, 1.0).tolist() == [[0, 255]]
        # nothing finite at all: black, no crash
        assert _normalize_to_uint8(np.array([[np.nan]], np.float32), np.nan, np.nan).max() == 0

    def test_inverted_or_flat_range_returns_black(self):
        a = np.array([[0.0, 1.0]], dtype=np.float32)
        assert _normalize_to_uint8(a, 5.0, 5.0).max() == 0
        assert _normalize_to_uint8(a, 10.0, 0.0).max() == 0


# ---------------------------------------------------------------------------
# Standard dtypes keep working (LUT paths + generic path)
# ---------------------------------------------------------------------------

class TestStandardDtypes:
    def test_uint8_identity(self):
        a = np.array([[0, 128], [200, 255]], dtype=np.uint8)
        r = _normalize_to_uint8(a, np.uint8(0), np.uint8(255))
        assert list(r.ravel()) == [0, 128, 200, 255]

    def test_uint8_scaled_max_maps_to_255(self):
        a = np.array([0, 100, 200], dtype=np.uint8)
        r = _normalize_to_uint8(a, np.uint8(0), np.uint8(200))
        assert r[0] == 0
        assert r[2] == 255   # was 254 with truncating cast + inexact scale

    def test_uint16(self):
        a = (np.arange(4, dtype=np.uint16) * 1000)
        r = _normalize_to_uint8(a, a.min(), a.max())
        assert r[0] == 0
        assert r[-1] == 255

    def test_int64_extreme_values(self):
        a = np.array([0, 2 ** 60], dtype=np.int64)
        r = _normalize_to_uint8(a, a.min(), a.max())
        assert r[0] == 0
        assert r[1] == 255

    @pytest.mark.parametrize('dtype', [np.uint8, np.uint16, np.int16, np.int32,
                                       np.float16, np.float32, np.float64])
    def test_all_dtypes_map_min_max_to_0_255(self, dtype):
        a = np.array([[10, 20], [30, 110]], dtype=dtype)
        r = _normalize_to_uint8(a, a.min(), a.max())
        assert r.dtype == np.uint8
        assert r[0, 0] == 0
        assert r[1, 1] == 255

    def test_numpy_scalar_min_max_accepted(self):
        """min/max always arrive as numpy scalars from img.min()/img.max() —
        the scale math must not run in the image dtype (NEP 50 regression)."""
        a = np.linspace(0, 1e-3, 16, dtype=np.float16).reshape(4, 4)
        r = _normalize_to_uint8(a, a.min(), a.max())  # numpy float16 scalars
        assert r[0, 0] == 0
        assert r[-1, -1] == 255


# ---------------------------------------------------------------------------
# Full Image2D display path (the code path that warned in the GUI)
# ---------------------------------------------------------------------------

class TestImage2DUpdateQimage:
    @pytest.mark.parametrize('arr', [
        np.linspace(0, 1e-4, 64 * 64, dtype=np.float16).reshape(64, 64),
        np.array([[0.0, 100.0], [1e300, 200.0]], dtype=np.float64),
        np.full((8, 8), np.nan, dtype=np.float32),
    ], ids=['float16_tiny_range', 'float64_hot_pixel', 'all_nan'])
    def test_update_qimage_is_silent(self, qapp, arr):
        """Building an Image2D (which normalizes for display in update_qimage)
        must not emit numpy RuntimeWarnings for pathological pixel data."""
        from batoolset.drawings.shapes.image2d import Image2D
        img2d = Image2D(arr)
        assert img2d.qimage is not None
