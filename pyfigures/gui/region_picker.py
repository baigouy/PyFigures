"""A thumbnail of an image on which a rectangle is drawn with the mouse —
the zoom-callout dialog asked for the region as four numbers with no idea of
where they land. Coordinates are image pixels, kept in sync with spin boxes.
"""
from __future__ import annotations

from qtpy.QtCore import QPointF, QRectF, Qt, Signal
from qtpy.QtGui import QColor, QPainter, QPen, QPixmap
from qtpy.QtWidgets import QLabel


class RegionPicker(QLabel):
    """Shows *qimage* scaled to at most *max_side* px; drag to draw the
    region. regionChanged(x, y, w, h) in image pixels."""
    regionChanged = Signal(int, int, int, int)

    def __init__(self, qimage, image_size, parent=None, max_side=320):
        super().__init__(parent)
        self.image_w, self.image_h = int(image_size[0]), int(image_size[1])
        pm = QPixmap.fromImage(qimage) if qimage is not None and not qimage.isNull() else QPixmap()
        if pm.isNull():
            pm = QPixmap(max(1, self.image_w), max(1, self.image_h))
            pm.fill(QColor(60, 60, 60))
        self._pixmap = pm.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        self.setFixedSize(self._pixmap.size())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setToolTip("Drag on the image to draw the region to magnify")
        self.region = QRectF()
        self._start = None

    def _to_image(self, pos) -> QPointF:
        sx = self.image_w / max(1, self.width())
        sy = self.image_h / max(1, self.height())
        return QPointF(min(max(pos.x(), 0), self.width()) * sx, min(max(pos.y(), 0), self.height()) * sy)

    def set_region(self, x, y, w, h):
        self.region = QRectF(x, y, w, h)
        self.update()

    def mousePressEvent(self, event):
        self._start = self._to_image(event.position() if hasattr(event, 'position') else event.pos())

    def mouseMoveEvent(self, event):
        if self._start is None:
            return
        end = self._to_image(event.position() if hasattr(event, 'position') else event.pos())
        self.region = QRectF(self._start, end).normalized()
        self.update()

    def mouseReleaseEvent(self, event):
        self.mouseMoveEvent(event)
        self._start = None
        r = self.region
        if r.width() >= 1 and r.height() >= 1:
            self.regionChanged.emit(int(round(r.x())), int(round(r.y())),
                                    int(round(r.width())), int(round(r.height())))

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)
        if not self.region.isNull():
            sx = self.width() / max(1, self.image_w)
            sy = self.height() / max(1, self.image_h)
            r = self.region
            p.setPen(QPen(QColor(255, 220, 0), 2))
            p.drawRect(QRectF(r.x() * sx, r.y() * sy, r.width() * sx, r.height() * sy))
        p.end()
