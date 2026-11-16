"""Zoom controls floating over the bottom-left corner of the figure area (the right is the chat's side) of the main window (2026-11-16: "zoom
buttons and fit to view ... I still feel it's missing"). The canvas could
zoom only by keyboard (Ctrl + / Ctrl - / Ctrl 0) and fit-to-window was not
reachable at all. Here: Fit / 100 % / − / zoom % / + (icons), and Ctrl + mouse wheel
on the canvas. All use the canvas' own zoom (scrollable_EZFIG.scaleImage)."""
from __future__ import annotations

from qtpy.QtCore import QEvent, QObject, QSize, Qt
from qtpy.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

MIN_SCALE, MAX_SCALE = 0.05, 16.0


class _CtrlWheel(QObject):
    """Ctrl + wheel over the canvas zooms (the wheel alone still scrolls)."""

    def __init__(self, bar):
        super().__init__(bar)
        self.bar = bar

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = event.angleDelta().y()
            if step:
                self.bar.zoom_by(1.1 if step > 0 else 1 / 1.1)
            return True
        return False


class ZoomBar(QFrame):     # a QFrame, not a plain QWidget (PySide2 crash with plain QWidget)
    def __init__(self, paint, parent=None):
        super().__init__(parent)
        self.paint = paint
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(1)

        def button(text, tip, slot, icon=None):
            b = QToolButton(self)
            b.setText(text)
            if icon:
                try:
                    from batoolset.icons.tools import get_icon
                    b.setIcon(get_icon(icon))
                    b.setIconSize(QSize(22, 22))    # the toolbar's size, not the status bar's tiny one
                    b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                except Exception:
                    pass                          # no icon font: the text stays
            b.setToolTip(tip)
            b.setAutoRaise(True)
            b.clicked.connect(lambda _checked=False: slot())
            layout.addWidget(b)
            return b
        self.fit_button = button('Fit', 'Fit the whole figure in the window', self.fit, 'mdi.fit-to-page-outline')
        self.reset_button = button('100 %', 'Actual size (Ctrl 0)', lambda: self.set_scale(1.0),
                                   'mdi.numeric-1-box-outline')
        self.out_button = button('−', 'Zoom out (Ctrl -, or Ctrl + mouse wheel)', lambda: self.zoom_by(1 / 1.1),
                                 'mdi.magnify-minus-outline')
        self.label = QLabel('100 %', self)
        self.label.setMinimumWidth(48)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setToolTip('Zoom of the figure on screen (the figure itself does not change)')
        layout.addWidget(self.label)
        self.in_button = button('+', 'Zoom in (Ctrl +, or Ctrl + mouse wheel)', lambda: self.zoom_by(1.1),
                                'mdi.magnify-plus-outline')
        self._wheel = _CtrlWheel(self)
        paint.scrollArea.viewport().installEventFilter(self._wheel)
        # floats over the bottom-left corner of the figure area (the right side is the
        # chat's): a row of its own under the canvas left too much empty grey (the user)
        self.setObjectName('ZoomBar')
        self.setStyleSheet('#ZoomBar { background: rgba(240, 240, 240, 225); border: 1px solid #b4b4b4; '
                           'border-radius: 4px; } #ZoomBar QLabel { color: black; }')
        layout.setContentsMargins(2, 1, 4, 1)
        self.adjustSize()
        self._corner = _Corner(self)
        paint.scrollArea.installEventFilter(self._corner)
        self.place()
        # every zoom (keyboard shortcuts included) goes through scaleImage: keep the % in step
        original = paint.scaleImage

        def scale_image(scale, _original=original):
            _original(scale)
            self.refresh()
        paint.scaleImage = scale_image
        self.refresh()

    def scale(self):
        return float(getattr(self.paint.EZFIG_panel, 'scale', 1.0) or 1.0)

    def set_scale(self, scale):
        self.paint.scaleImage(min(max(float(scale), MIN_SCALE), MAX_SCALE))

    def zoom_by(self, factor):
        self.set_scale(self.scale() * factor)

    def fit(self):
        if self.paint.EZFIG_panel.shapes_to_draw:
            self.paint.fit_to_window()

    def refresh(self):
        self.label.setText(f'{self.scale() * 100:.0f} %')

    def place(self):
        """Bottom-left corner of the scroll area, above its horizontal scroll bar."""
        area = self.paint.scrollArea
        bar = area.horizontalScrollBar()
        below = bar.height() if bar.isVisible() else 0
        self.adjustSize()
        self.move(6, max(0, area.height() - self.height() - below - 6))
        self.raise_()


class _Corner(QObject):
    """Keeps the zoom bar in its corner when the window is resized."""

    def __init__(self, bar):
        super().__init__(bar)
        self.bar = bar

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest):
            self.bar.place()
        return False
