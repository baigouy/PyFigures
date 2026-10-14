"""A QPainter for QSvgGenerator that honours drawImage/drawPixmap source rects.

Qt's SVG paint engine (at least up to Qt 6.4) ignores the *source rectangle*
of ``drawImage(target, image, source)``: it writes the whole image into the
target box. A cropped panel was therefore exported to SVG as the full,
uncropped image squeezed (distorted) into the cropped panel's box.

``CroppingPainter`` crops the image itself before handing it to Qt, so the SVG
contains exactly the pixels that are shown. The figure code calls
``painter.drawImage(...)`` from Python, so overriding the methods here is
enough. Other paint devices do not need it.
"""
from qtpy.QtCore import QPoint, QPointF, QRect, QRectF
from qtpy.QtGui import QImage, QPainter, QPixmap


def real_font_families(svg_text):
    """Qt's SVG writer names the font that was asked for ("Sans Serif", an
    alias), not the one Qt drew with: returns *svg_text* with the real family
    (e.g. Arial), so Illustrator, Inkscape and browsers use the same font."""
    import re
    from qtpy.QtGui import QFont, QFontInfo
    resolved = {}

    def real(m):
        name = m.group(1)
        if name not in resolved:
            resolved[name] = QFontInfo(QFont(name)).family() or name
        return f'font-family="{resolved[name]}"'

    return re.sub(r'font-family="([^"]+)"', real, svg_text)


def _source_rect(src):
    if isinstance(src, QRectF):
        return QRect(int(round(src.x())), int(round(src.y())),
                     max(1, int(round(src.width()))), max(1, int(round(src.height()))))
    return src


class CroppingPainter(QPainter):

    def _crop_call(self, base, kind, args, kwargs):
        a = list(args)
        # (target, image, source[, flags])
        if len(a) >= 3 and isinstance(a[1], kind) and isinstance(a[2], (QRect, QRectF)):
            src = _source_rect(a[2])
            if src.isValid() and (src.x() or src.y() or src.width() != a[1].width()
                                  or src.height() != a[1].height()):
                sub = a[1].copy(src)
                target = a[0]
                if isinstance(target, (QPoint, QPointF)):
                    return base(self, target, sub)
                # (target, image, whole-image source): no 2-argument QRectF
                # overload exists for drawPixmap
                whole = QRectF(sub.rect()) if isinstance(target, QRectF) else sub.rect()
                return base(self, target, sub, whole)
        # (x, y, image, sx, sy, sw, sh[, flags]) — QImage only
        if len(a) >= 4 and isinstance(a[2], kind) and not isinstance(a[0], (QRect, QRectF, QPoint, QPointF)):
            sx, sy = (a + [0, 0])[3:5]
            sw = a[5] if len(a) > 5 else -1
            sh = a[6] if len(a) > 6 else -1
            img = a[2]
            if sw is None or sw < 0:
                sw = img.width() - sx
            if sh is None or sh < 0:
                sh = img.height() - sy
            if sx or sy or sw != img.width() or sh != img.height():
                return base(self, QPointF(a[0], a[1]), img.copy(QRect(int(sx), int(sy), int(sw), int(sh))))
        return base(self, *args, **kwargs)

    def drawImage(self, *args, **kwargs):
        return self._crop_call(QPainter.drawImage, QImage, args, kwargs)

    def drawPixmap(self, *args, **kwargs):
        return self._crop_call(QPainter.drawPixmap, QPixmap, args, kwargs)
