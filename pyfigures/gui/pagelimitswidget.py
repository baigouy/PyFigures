from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QComboBox, QPushButton, QLabel
from batoolset.dims.tools import cm_to_inch, inch_to_cm, inch_to_pixels, cm_to_pixels

class PageLimitsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        form_layout = QFormLayout()
        layout.addLayout(form_layout)

        self.width_spinbox = QDoubleSpinBox()
        self.width_spinbox.setSingleStep(0.1)
        self.width_spinbox.setSuffix(" cm")
        self.width_spinbox.setValue(21.0)
        form_layout.addRow("Width:", self.width_spinbox)

        self.height_spinbox = QDoubleSpinBox()
        self.height_spinbox.setSingleStep(0.1)
        self.height_spinbox.setSuffix(" cm")
        self.height_spinbox.setValue(29.7)
        form_layout.addRow("Height:", self.height_spinbox)

        self.unit_combobox = QComboBox()
        self.unit_combobox.addItems(["cm", "inches"])
        self.unit_combobox.currentIndexChanged.connect(self.update_unit)
        form_layout.addRow("Unit:", self.unit_combobox)


    def update_unit(self):
        # Convert the values between cm and inches as needed
        width = self.width_spinbox.value()
        height = self.height_spinbox.value()
        unit = self.unit_combobox.currentText()
        if unit == "inches":
            width = cm_to_inch(width)
            height =cm_to_inch(height)
        else:
            width = inch_to_cm(width)
            height = inch_to_cm(height)

        if unit == "cm":
            self.width_spinbox.setSuffix(" cm")
            self.height_spinbox.setSuffix(" cm")
        else:
            self.width_spinbox.setSuffix(" in")
            self.height_spinbox.setSuffix(" in")

        self.width_spinbox.setValue(width)
        self.height_spinbox.setValue(height)

    def get_values(self):
        width = self.width_spinbox.value()
        height = self.height_spinbox.value()
        unit = self.unit_combobox.currentText()
        #
        # if unit == "inches":
        #     width_cm = width_cm * 2.54
        #     height_cm = height_cm * 2.54
        #
        # self.label.setText(f"Width: {width_cm} cm, Height: {height_cm} cm")

        if 'nch' in unit:
            width = inch_to_pixels(width)
            height = inch_to_pixels(height)
        else:
            width = cm_to_pixels(width)
            height = cm_to_pixels(height)

        return width, height

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    widget = PageLimitsWidget()
    widget.show()

    print(widget.get_values())
    sys.exit(app.exec_())
