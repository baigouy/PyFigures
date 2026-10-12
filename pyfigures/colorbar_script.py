"""Shared builder for a LUT intensity calibration bar ("colour bar").

A colour bar is realised as a scripted matplotlib panel: this module produces
the Python snippet that, when run inside a PyFigures Image2D, draws a colourbar
whose colours match a named PyFigures LUT. Both the MCP tool
(``add_lut_calibration_bar``) and the GUI ("Add colour bar…") build the exact
same script through here, so they can never drift apart.

Pure text generation — no Qt, no matplotlib imported here.
"""
from __future__ import annotations

ORIENTATIONS = ("vertical", "horizontal")


def build_calibration_bar_script(
    lut: str = "GRAY",
    vmin: float = 0.0,
    vmax: float = 255.0,
    label: str = "",
    orientation: str = "vertical",
    ticks: list[float] | None = None,
    tick_labels: list[str] | None = None,
) -> str:
    """Return the custom_loading_script for a LUT calibration bar.

    Raises ValueError on an invalid orientation or a ticks/tick_labels length
    mismatch, so callers get one consistent validation.
    """
    if orientation not in ORIENTATIONS:
        raise ValueError("orientation must be 'vertical' or 'horizontal'")
    if ticks is not None and tick_labels is not None and len(ticks) != len(tick_labels):
        raise ValueError("ticks and tick_labels must have the same length")

    # Explicit figure size + axes rectangle avoids matplotlib's tight-layout
    # complaint on a colourbar-only figure and leaves room for ticks + label.
    if orientation == "vertical":
        figsize, axes_rect = "(0.9, 3.2)", "[0.18, 0.06, 0.28, 0.88]"
    else:
        figsize, axes_rect = "(3.2, 0.95)", "[0.06, 0.5, 0.88, 0.28]"

    lines = [
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "from matplotlib.colorbar import ColorbarBase",
        "from matplotlib.colors import Normalize, ListedColormap",
        "from batoolset.luts.lut_minimal_test import PaletteCreator",
        # resolve the PyFigures LUT name to a matplotlib Colormap (same colours
        # the matching image uses); fail loudly on an unknown name.
        "_pc = PaletteCreator()",
        f"_lut = {lut!r}",
        "if _lut in _pc.matplot_lib_luts:",
        "    _cmap = plt.get_cmap(_lut[len('MATPLOTLIB_'):] "
        "if _lut.startswith('MATPLOTLIB_') else _lut)",
        "elif _lut in _pc.list:",
        "    _cmap = ListedColormap(np.asarray(_pc.create3(_pc.list[_lut]), "
        "dtype=float) / 255.0)",
        "else:",
        "    raise ValueError('unknown LUT %r - use a name accepted by set_lut' % _lut)",
        f"fig = plt.figure(figsize={figsize})",
        f"ax = fig.add_axes({axes_rect})",
        f"_cb = ColorbarBase(ax, cmap=_cmap, norm=Normalize(vmin={float(vmin)}, "
        f"vmax={float(vmax)}), orientation={orientation!r})",
    ]
    if ticks is not None:
        lines.append(f"_cb.set_ticks({[float(t) for t in ticks]!r})")
        if tick_labels is not None:
            lines.append(f"_cb.set_ticklabels({[str(t) for t in tick_labels]!r})")
    if label:
        lines.append(f"_cb.set_label({label!r})")
    lines.append("self.img = fig")
    return "\n".join(lines)
