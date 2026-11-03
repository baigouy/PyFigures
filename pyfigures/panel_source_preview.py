"""The whole source image of one panel, uncropped, with pixel rulers and the
current crop outlined: what an MCP client needs to choose crop values.

A figure preview shows each panel small and already cropped, so a model asked
to "crop g so the nuclei fill the frame" cropped, previewed, uncropped and
cropped again until it ran out of steps (2026-11-03). Shared by the live chat
tool preview_panel and the headless MCP tool preview_panel_source.
"""
import math


def _step(size):
    """A round ruler step giving about 8 ticks over *size* pixels."""
    raw = max(size / 8, 1)
    power = 10 ** math.floor(math.log10(raw))
    for f in (1, 2, 5, 10):
        if raw <= f * power:
            return int(f * power)
    return int(10 * power)


def qimage_to_rgb(qimage):
    """A QImage as an (h, w, 3) uint8 array."""
    import numpy as np
    from qtpy.QtGui import QImage
    image = qimage.convertToFormat(QImage.Format.Format_RGB888)
    w, h = image.width(), image.height()
    ptr = image.constBits()
    ptr.setsize(image.bytesPerLine() * h)
    rows = np.frombuffer(ptr, np.uint8).reshape(h, image.bytesPerLine())
    return rows[:, :w * 3].reshape(h, w, 3).copy()


def panel_crop(panel):
    """(left, top, right, bottom) crop of an Image2D, in source pixels."""
    return tuple(int(round(float(getattr(panel, 'crop_' + side, 0) or 0)))
                 for side in ('left', 'top', 'right', 'bottom'))


def stretch(rgb):
    """*rgb* with its 0.5-99.8 percentile range spread over 0-255: dim
    fluorescence (nuclei barely above black) becomes visible. Display only."""
    import numpy as np
    low, high = np.percentile(rgb, (0.5, 99.8))
    if high <= low:
        return rgb
    return (np.clip((rgb.astype(np.float32) - low) / (high - low), 0, 1) * 255).astype(np.uint8)


def render(rgb, crop, out_path, title='', brighten=True):
    """Save *rgb* with pixel rulers, a light grid and *crop* outlined.
    Returns a one-line description of what the picture shows."""
    if brighten:
        rgb = stretch(rgb)
    import matplotlib
    matplotlib.use('Agg', force=False)
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    h, w = rgb.shape[:2]
    left, top, right, bottom = crop
    inch = 8.0
    fig, ax = plt.subplots(figsize=(inch, inch * h / w if w else inch), dpi=110)
    ax.imshow(rgb, interpolation='nearest', extent=(0, w, h, 0))
    step = _step(max(w, h))
    ax.set_xticks(range(0, w + 1, step))
    ax.set_yticks(range(0, h + 1, step))
    ax.tick_params(labelsize=8, top=True, labeltop=True, right=True, labelright=True)
    ax.grid(color='#00e5ff', alpha=0.35, linewidth=0.6)
    if any(crop):
        ax.add_patch(Rectangle((left, top), w - left - right, h - top - bottom, fill=False,
                               edgecolor='yellow', linewidth=1.8, linestyle='--'))
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    kept = f'kept x {left}-{w - right}, y {top}-{h - bottom}' if any(crop) else 'no crop'
    ax.set_title((title + '\n' if title else '') + f'source {w}x{h} px; current crop left={left} top={top} '
                 f'right={right} bottom={bottom} ({kept}, yellow box)', fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    shown = ' Contrast stretched for this preview only; the figure is unchanged.' if brighten else ''
    return (f'Whole source of the panel, {w}x{h} px, with pixel rulers (x left to right, y top to bottom).{shown} '
            f'Current crop: left={left}, top={top}, right={right}, bottom={bottom} ({kept}, dashed yellow box). '
            f'To keep the region x0-x1, y0-y1 set crop_left=x0, crop_top=y0, crop_right={w}-x1, crop_bottom={h}-y1.')


def panel_rgb(panel):
    """The panel's displayed pixels (LUTs, channels, projection, flips), uncropped."""
    if getattr(panel, 'qimage', None) is None:
        if getattr(panel, 'img', None) is None and hasattr(panel, 'load_img'):
            panel.load_img()
        if getattr(panel, 'qimage', None) is None and hasattr(panel, 'update_qimage'):
            panel.update_qimage()
    if getattr(panel, 'qimage', None) is None:
        raise ValueError('This panel has no pixel image (a template, a plot script or a missing file); '
                         'there is nothing to crop by pixels.')
    return qimage_to_rgb(panel.qimage)


def preview_panel(panel, out_path, title='', brighten=True):
    """Render *panel*'s whole source with rulers to *out_path*; returns its description."""
    return render(panel_rgb(panel), panel_crop(panel), out_path, title, brighten)
