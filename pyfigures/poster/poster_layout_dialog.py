"""Layout gallery dialog: pick a pre-designed page layout ("template"), the
way you'd pick a slide layout in PowerPoint, and fill it with the photos
already on the poster page. Standalone widget — talks to the rest of the
poster module only through pyfigures.poster.poster_templates, and to the
caller only through the exec()/selected_layout result, same pattern as any
other Qt dialog here.
"""
from batoolset.settings.global_settings import set_UI
set_UI()

from qtpy.QtCore import Qt, QRectF, QSize
from qtpy.QtGui import QPainter, QColor, QPen, QPixmap, QIcon
from qtpy.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QLabel, QDialogButtonBox, QCheckBox
)

from pyfigures.poster.poster_templates import LAYOUTS, list_layouts

THUMB_W = 120
THUMB_H = 90


def _render_layout_thumb(slots):
    """A small preview pixmap: a white page with each slot drawn as a blue
    rectangle (tilted if the slot has a theta) — a miniature of what
    apply_layout() would produce."""
    pm = QPixmap(THUMB_W, THUMB_H)
    pm.fill(QColor(235, 235, 235))
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing, True)
    page_rect = pm.rect().adjusted(3, 3, -3, -3)
    painter.setPen(QPen(QColor(130, 130, 130), 1))
    painter.setBrush(QColor(255, 255, 255))
    painter.drawRect(page_rect)
    for slot in slots:
        x = page_rect.left() + slot['x'] * page_rect.width()
        y = page_rect.top() + slot['y'] * page_rect.height()
        w = slot['w'] * page_rect.width()
        h = slot['h'] * page_rect.height()
        painter.save()
        painter.translate(x + w / 2.0, y + h / 2.0)
        theta = slot.get('theta', 0.0)
        if theta:
            painter.rotate(theta)
        painter.setPen(QPen(QColor(60, 120, 200), 1))
        painter.setBrush(QColor(160, 200, 240))
        painter.drawRect(QRectF(-w / 2.0, -h / 2.0, w, h))
        painter.restore()
    painter.end()
    return pm


class LayoutGalleryDialog(QDialog):
    """After exec(), self.selected_layout is the chosen layout name (or None
    if cancelled), and self.sketch_mode is True if "Sketch as empty slots"
    was checked — i.e. add the layout as unfilled placeholders (no photos
    needed yet) instead of filling it with photos already on the page."""

    def __init__(self, parent=None, image_count=None):
        super().__init__(parent)
        self.setWindowTitle('Choose a layout')
        self.resize(560, 420)
        self.selected_layout = None
        self.sketch_mode = False

        layout = QVBoxLayout(self)
        if image_count:
            layout.addWidget(QLabel(
                f'{image_count} photo(s) on the page — layouts needing that many '
                'slots are listed first. Extra photos are left where they are; '
                'a layout with more slots than photos only fills the first ones.'))

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListWidget.IconMode)
        self.list_widget.setIconSize(QSize(THUMB_W, THUMB_H))
        self.list_widget.setResizeMode(QListWidget.Adjust)
        self.list_widget.setMovement(QListWidget.Static)
        self.list_widget.setSpacing(10)
        layout.addWidget(self.list_widget)

        entries = list_layouts()
        if image_count:
            entries.sort(key=lambda e: (e['slot_count'] != image_count, e['slot_count']))
        for entry in entries:
            slots = LAYOUTS[entry['name']]['slots']
            plural = '' if entry['slot_count'] == 1 else 's'
            item = QListWidgetItem(QIcon(_render_layout_thumb(slots)),
                                   f"{entry['label']}\n({entry['slot_count']} photo{plural})")
            item.setData(Qt.UserRole, entry['name'])
            item.setToolTip(entry['description'])
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        self.list_widget.itemDoubleClicked.connect(self._accept_item)

        self.sketch_checkbox = QCheckBox('Sketch as empty slots (no photos yet — fill them in later)')
        layout.addWidget(self.sketch_checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_current)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_item(self, item):
        self.selected_layout = item.data(Qt.UserRole)
        self.sketch_mode = self.sketch_checkbox.isChecked()
        self.accept()

    def _accept_current(self):
        item = self.list_widget.currentItem()
        if item is not None:
            self.selected_layout = item.data(Qt.UserRole)
        self.sketch_mode = self.sketch_checkbox.isChecked()
        self.accept()
