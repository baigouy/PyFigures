"""get_fig_rect caches a matplotlib panel's tight size (measuring it re-lays out
every tick label, and layout asks thousands of times while a figure opens:
templates_only.pyf took 25-50 s to open lazily). The cache must never return
a stale size."""
import os
import time

import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from batoolset.matplolibs.tools import get_fig_rect, _compute_fig_rect, invalidate_fig_rect  # noqa: E402


def _same(fig):
    a, b = get_fig_rect(fig), _compute_fig_rect(fig)
    return abs(a.width() - b.width()) < 1e-6 and abs(a.height() - b.height()) < 1e-6


@pytest.mark.parametrize("edit", [
    lambda f, ax: ax.set_xlabel("a much longer x label with several words"),
    lambda f, ax: ax.set_ylim(0, 100000),
    lambda f, ax: ax.set_title("Title\nsecond line"),
    lambda f, ax: f.set_size_inches(3, 2),
    lambda f, ax: ax.legend(["s"], loc="center left", bbox_to_anchor=(1, 0.5)),
    lambda f, ax: f.suptitle("Super title"),
    lambda f, ax: ax.set_yscale("log"),
    lambda f, ax: ax.set_axis_off(),
    lambda f, ax: f.text(0.99, 0.01, "note"),
])
def test_cache_follows_edits(edit):
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [4, 1, 9])
    get_fig_rect(fig)                      # fill the cache
    edit(fig, ax)
    assert _same(fig)


def test_returns_copies_and_explicit_invalidation():
    fig, ax = plt.subplots()
    ax.plot([1, 2], [1, 2])
    r = get_fig_rect(fig)
    r.setWidth(1)                          # caller mutates its rect
    assert get_fig_rect(fig).width() > 1
    ax.tick_params(labelsize=30)           # not in the fingerprint
    invalidate_fig_rect(fig)
    assert _same(fig)


def test_cached_calls_are_cheap():
    fig, ax = plt.subplots()
    ax.plot(range(50))
    get_fig_rect(fig)
    t = time.perf_counter()
    for _ in range(500):
        get_fig_rect(fig)
    assert time.perf_counter() - t < 1.0   # was ~0.017 s per call → ~8 s


def test_lazy_open_of_plot_panels_is_fast(qapp, sample_dir):
    path = os.path.join(sample_dir, "test_templates_only.pyf")
    if not os.path.isfile(path):
        pytest.skip("sample figures not available")
    from batoolset.serializations.tools import deserialize_to_dict, create_object
    from batoolset.drawings.shapes.image2d import Image2D
    props = deserialize_to_dict(open(path, encoding="utf-8").read())
    t = time.perf_counter()
    Image2D._lazy_mode = True
    try:
        objs = create_object(list.__name__, props)
    finally:
        Image2D._lazy_mode = False
    assert objs
    assert time.perf_counter() - t < 15    # 25-50 s before the cache, ~2 s after
