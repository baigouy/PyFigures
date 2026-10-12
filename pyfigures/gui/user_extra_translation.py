from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import sys
from qtpy.QtWidgets import QApplication, QWidget, QSpinBox, QPushButton, QVBoxLayout, QLabel,QHBoxLayout
from qtpy.QtCore import Qt

class ExtraTranslationWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.dx_label = QLabel("dx:", self)
        self.dy_label = QLabel("dy:", self)
        self.dx_spinbox = QSpinBox(self)
        self.dy_spinbox = QSpinBox(self)
        # Set the range of the spin boxes to include negative numbers
        self.dx_spinbox.setRange(-1024, 1024)
        self.dy_spinbox.setRange(-1024, 1024)
        # self.get_translation_button = QPushButton("Get Translation", self)

        layout = QVBoxLayout(self)

        hbox1 = QHBoxLayout()
        hbox1.addWidget(self.dx_label)
        hbox1.addWidget(self.dx_spinbox)
        layout.addLayout(hbox1)

        hbox2 = QHBoxLayout()
        hbox2.addWidget(self.dy_label)
        hbox2.addWidget(self.dy_spinbox)
        layout.addLayout(hbox2)

        # layout.addWidget(self.get_translation_button)
        #
        # self.get_translation_button.clicked.connect(self.get_translation)

    def get_translation(self):
        dx = self.dx_spinbox.value()
        dy = self.dy_spinbox.value()

        # print(f"User's extra translation: {user_extra_translation}")
        return dx, dy

if __name__ == "__main__":
    app = QApplication(sys.argv)

    widget = ExtraTranslationWidget()
    widget.setWindowTitle("Translation Widget")
    widget.show()

    print(widget.get_translation())

    sys.exit(app.exec_())