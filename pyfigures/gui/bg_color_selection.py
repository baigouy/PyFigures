from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QLabel, QPushButton, QWidget, QHBoxLayout,QColorDialog,QDialog
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QMainWindow

class BackgroundColorPicker(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create label and color picker button
        self.label = QLabel('Background color:')
        self.color_button = QPushButton()
        self.color_button.setFocusPolicy(Qt.NoFocus)
        # self.color_button.setStyleSheet("background-color: %s" % QColor(0, 0, 0).name())
        self.color_button.clicked.connect(self.pick_color)

        # Create reset button
        self.reset_button = QPushButton('Reset')
        self.reset_button.setFocusPolicy(Qt.NoFocus)
        self.reset_button.clicked.connect(self.reset_color)

        # Create layout and add widgets
        layout = QHBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.color_button)
        layout.addWidget(self.reset_button)
        self.setLayout(layout)

        self.color=None

        # Set initial color
        # self.set_color(QColor(0, 0, 0))

    def pick_color(self):
        dialog = QColorDialog(self)
        dialog.show()
        result = dialog.exec_()

        if result == QDialog.Accepted:
            c = dialog.selectedColor()
            if c.isValid():  # make sure the user did not cancel otherwise ignore # useless with current code
               self.set_color(c)
        elif result == QDialog.Rejected:
            pass
        else:
             self.set_color(None)

    def reset_color(self):
        # Reset color to default (black)
        self.set_color(None)

    def set_color(self, color):
        if color is not None:
            # Set color of color picker button and emit signal
            self.color_button.setStyleSheet("background-color: %s" % color.name())
            self.color = color
        else:
            self.color_button.setStyleSheet('background-color: none;')
            self.color = None


    def get_color(self):
        # Return current color
        # return self.color
        if isinstance(self.color, QColor):
            self.color = self.color.rgb() & 0xFFFFFF
        return self.color


def main():
    # Create QApplication instance
    app = QApplication([])

    # Create QMainWindow instance
    window = QMainWindow()

    # Create BackgroundColorPicker widget
    color_picker = BackgroundColorPicker()

    # Set central widget of QMainWindow to BackgroundColorPicker widget
    window.setCentralWidget(color_picker)

    # Show QMainWindow
    window.show()

    # Run QApplication event loop
    app.exec_()

if __name__ == '__main__':
    main()