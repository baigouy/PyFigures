import traceback

from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import sys
from qtpy.QtCore import QPoint, QRect, Qt, QTimer,QSize
from qtpy.QtGui import QColor, QPainter, QPixmap,QImage
from qtpy.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PIL import Image, ImageGrab, ImageQt


class ColorAssistant(QWidget):
    def __init__(self, parent=None, capture_width=128, capture_height=96):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Window)
        self.capture_size = QSize(capture_width, capture_height)
        self.setWindowTitle('Color Assistant')

        self._label_red = QLabel(self)
        self._label_green = QLabel(self)
        self._label_blue = QLabel(self)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._label_red)
        layout.addWidget(self._label_green)
        layout.addWidget(self._label_blue)
        self.setLayout(layout)

        # import os
        # os.environ['DISPLAY']=':0'
        success = False
        try:
            import pyautogui
            success=True

            # this can be fixed using "xhost +SI:localuser:$(whoami)" but the pb is that it is very slow and painful so forget about in on ubuntu wayland, that just does not work

        except:
            traceback.print_exc()
            print('Error, color assistant will not work on this system')

        if success:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self.update_pixel_color)
            self._timer.start(100)  # Update every 100ms

            self.original_size = self.capture_size

            self.show()

    def sizeHint(self):
        return QSize(self.capture_size.width(), self.capture_size.height() * 3)

    def paintEvent(self, event):
        super().paintEvent(event)
        self.update_pixel_color()

    def update_pixel_color(self):
        try:
            import pyautogui
            x, y = pyautogui.position()
            half_width = self.capture_size.width() // 2
            half_height = self.capture_size.height() // 2
            rect = QRect(x - half_width, y - half_height, self.capture_size.width(), self.capture_size.height())

            image = ImageGrab.grab(bbox=(rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height()))
            rgb_image = image.convert('RGB')

            r, g, b = rgb_image.split()

            widget_width = self.width()
            label_height = self.height() // 3

            for channel, label in zip((r, g, b), (self._label_red, self._label_green, self._label_blue)):
                qimage = QImage(channel.tobytes(), channel.width, channel.height, QImage.Format_Grayscale8)
                pixmap = QPixmap.fromImage(qimage)

                scaled_pixmap = pixmap.scaled(widget_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                label.setPixmap(scaled_pixmap)
                label.setAlignment(Qt.AlignCenter)

            self.adjustSize()
        except:
            # traceback.print_exc()
            pass

    def resizeEvent(self, event):
        widget_width = self.width()
        widget_height = self.height()
        num_labels = 3
        label_width = widget_width
        label_height = widget_height // num_labels

        original_aspect_ratio = self.original_size.width() / self.original_size.height()
        current_aspect_ratio = label_width / label_height

        if current_aspect_ratio > original_aspect_ratio:
            new_width = int(label_height * original_aspect_ratio)
            new_height = label_height
        else:
            new_width = label_width
            new_height = int(label_width / original_aspect_ratio)

        scaled_size = QSize(new_width, new_height)
        self._label_red.setFixedSize(scaled_size)
        self._label_green.setFixedSize(scaled_size)
        self._label_blue.setFixedSize(scaled_size)

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

        super().resizeEvent(event)

def main():
    app = QApplication(sys.argv)

    # Create ColorAssistant with 128x96 capture size
    mouse_tracker = ColorAssistant(capture_width=128, capture_height=96)

    app.installEventFilter(mouse_tracker)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
