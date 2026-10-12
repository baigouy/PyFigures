from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtWidgets import QWidget, QComboBox, QVBoxLayout,QApplication
import sys

class DimensionChooser(QWidget):
    def __init__(self, dimensions):
        super().__init__()

        self.dimensions = list(dimensions)
        self.combo_box = QComboBox()
        self.combo_box.addItems(self.dimensions)

        layout = QVBoxLayout()
        layout.addWidget(self.combo_box)

        self.setLayout(layout)

    def get_current_dimension(self):
        return self.combo_box.currentText()


def main():
    app = QApplication(sys.argv)

    dimensions = "dhwc"
    chooser = DimensionChooser(dimensions)
    chooser.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
