from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtWidgets import QWidget, QApplication, QVBoxLayout, QSpinBox, QCheckBox, QHBoxLayout, QLabel,QGridLayout
from qtpy.QtCore import Qt

class SpaceSelectorWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        grid = QGridLayout()

        label = QLabel('Space:')
        # label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spinbox = QSpinBox()
        self.spinbox.setRange(0, 1000)
        self.spinbox.setValue(3)

        self.apply_to_page = QCheckBox('Also apply space to main page')
        self.apply_to_page.setChecked(False)

        grid.addWidget(label, 0, 0)
        grid.addWidget(self.spinbox, 0, 1)
        grid.addWidget(self.apply_to_page, 1, 0, 1, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 7)

        self.setLayout(grid)

    def is_apply_to_page_checked(self):
        return self.apply_to_page.isChecked()

    def get_space_value(self):
        return self.spinbox.value()


if __name__ == '__main__':
    app = QApplication([])

    # create an instance of SpaceSelectorWidget
    space_selector = SpaceSelectorWidget()
    space_selector.show()

    # get the state of the checkbox
    apply_to_page = space_selector.is_apply_to_page_checked()

    # get the value of the spin box
    value = space_selector.get_space_value()

    print(apply_to_page, value)

    app.exec_()
