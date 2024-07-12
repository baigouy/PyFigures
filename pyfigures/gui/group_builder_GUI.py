import sys
from qtpy import QtWidgets, QtCore
from batoolset.draw.shapes.group import Group

class PanelOrRow(QtWidgets.QWidget):
    def __init__(self, group=None, hide_size=False):
        super().__init__()
        self.hide_size = hide_size
        self.init_ui()
        if isinstance(group, Group):
            # get the parameters and set them to the GUI
            space = group.space
            orientation = group.orientation
            self.space_spinbox.setValue(space)
            if orientation=='Y':
                self.orientation_combo.setCurrentIndex(1)

    def init_ui(self):
        orientation_label = QtWidgets.QLabel("Orientation:")
        self.orientation_combo = QtWidgets.QComboBox()
        self.orientation_combo.addItems(["X", "Y"])
        self.orientation_combo.setCurrentIndex(0)  # Set default to 'X'

        # if not self.hide_size:
        size_label = QtWidgets.QLabel("Size:")
        self.size_spinbox = QtWidgets.QSpinBox()
        self.size_spinbox.setRange(1, 20000)  # Set the range of the spin box
        # self.size_spinbox.setMinimum(1)
        self.size_spinbox.setValue(512)  # Set default value

        space_label = QtWidgets.QLabel("Space:")
        self.space_spinbox = QtWidgets.QSpinBox()
        self.space_spinbox.setRange(0, 256)  # Set the range of the spin box
        self.space_spinbox.setValue(3)  # Set default value

        layout = QtWidgets.QGridLayout()
        layout.addWidget(orientation_label, 0, 0)
        layout.addWidget(self.orientation_combo, 0, 1)
        if not self.hide_size:
            layout.addWidget(size_label, 1, 0)
            layout.addWidget(self.size_spinbox, 1, 1)
        layout.addWidget(space_label, 2, 0)
        layout.addWidget(self.space_spinbox, 2, 1)

        self.setLayout(layout)

    def get_parameters(self):
        orientation = self.orientation_combo.currentText()
        size = self.size_spinbox.value()
        space = self.space_spinbox.value()

        return orientation, size, space


def main():
    app = QtWidgets.QApplication(sys.argv)

    window = PanelOrRow()
    window.setWindowTitle("QtPy Example")
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
