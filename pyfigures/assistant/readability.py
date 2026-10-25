"""Opt-in measured label diagnostics. No changes, no model call, no restyling."""
from qtpy.QtGui import QColor
from qtpy.QtCore import QRectF
from .partner_gui import panels, letter_info
from pyfigures.gui.pfgui import TAText2D


def contrast(foreground, background):
    def luminance(color):
        c = QColor(color)
        values = [v / 255 for v in (c.red(), c.green(), c.blue())]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + .05) / (a + .05)


def inspect_readability(window):
    canvas = window.paint.EZFIG_panel
    canvas.repaint()
    entries = []
    for gp, ix, panel in panels(canvas.shapes_to_draw):
        for index, text in enumerate(panel.annotations or []):
            if isinstance(text, TAText2D) and text.getPlainText().strip():
                entries.append((panel, text, '/'.join(map(str, (*gp, ix))), index))
    issues, labels, hidden = [], [], []
    image = None
    # One render without text lets us sample its actual displayed background.
    if canvas.width() * canvas.height() <= 16000000:
        try:
            for _, text, _, _ in entries:
                hidden.append((text, text.__dict__.get('draw')))
                text.draw = lambda *args, **kwargs: None
            image = canvas.grab().toImage()
        finally:
            for text, original in hidden:
                if original is None:
                    text.__dict__.pop('draw', None)
                else:
                    text.draw = original
            canvas.repaint()
    for panel, text, pid, index in entries:
        rect = QRectF(text.x(), text.y(), text.width(), text.height())
        bounds = QRectF(panel.x(), panel.y(), panel.width(), panel.height())
        key = dict(panel_id=pid, annotation_index=index, text=text.getPlainText()[:80])
        if not bounds.contains(rect):
            issues.append({**key, 'issue': 'outside_panel', 'note': 'Text bounds extend outside the panel; may be intentional placement. Review for clipping.'})
        info = letter_info(text)
        fill = info.get('background')
        samples = []
        if fill:
            samples = [contrast(info['color'], fill)]
        elif image is not None:
            for fx in (.1, .3, .5, .7, .9):
                for fy in (.1, .3, .5, .7, .9):
                    x, y = int((rect.x() + rect.width() * fx) * canvas.scale), int((rect.y() + rect.height() * fy) * canvas.scale)
                    if 0 <= x < image.width() and 0 <= y < image.height():
                        samples.append(contrast(info['color'], image.pixelColor(x, y)))
        if samples:
            samples.sort()
            ratio = samples[len(samples) // 2]
            if ratio < 4.5:
                issues.append({**key, 'issue': 'low_contrast', 'contrast_ratio': round(ratio, 2),
                               'note': 'Measured background samples; photo texture, opacity and font size can affect readability.'})
        else:
            issues.append({**key, 'issue': 'contrast_unknown', 'note': 'No rendered background samples available; contrast not verified.'})
        for other, other_rect in labels:
            if rect.intersects(other_rect):
                issues.append({**key, 'issue': 'possible_overlap', 'other': other})
        labels.append((key, rect))
    return dict(labels_checked=len(entries), issues=issues[:200], issue_count=len(issues),
                changes_made=False, note='Heuristic bounding-box and sampled contrast checks, not a publication-quality guarantee. No model call.')
