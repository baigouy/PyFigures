from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QFormLayout, QDoubleSpinBox, QComboBox, QPushButton, QLabel
from batoolset.dims.tools import cm_to_pixels

# size of one unit in cm; mm first: journals give their widths in mm
_UNIT_IN_CM = {"mm": 0.1, "cm": 1.0, "inches": 2.54}
_SUFFIX = {"mm": " mm", "cm": " cm", "inches": " in"}


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
        self.width_spinbox.setRange(0, 10000)
        self.width_spinbox.setSingleStep(1)
        self.width_spinbox.setSuffix(" mm")
        self.width_spinbox.setValue(210.0)
        form_layout.addRow("Width:", self.width_spinbox)

        self.height_spinbox = QDoubleSpinBox()
        self.height_spinbox.setRange(0, 10000)
        self.height_spinbox.setSingleStep(1)
        self.height_spinbox.setSuffix(" mm")
        self.height_spinbox.setValue(297.0)
        form_layout.addRow("Height:", self.height_spinbox)

        self.unit_combobox = QComboBox()
        self.unit_combobox.addItems(list(_UNIT_IN_CM))
        self._unit = self.unit_combobox.currentText()
        self.unit_combobox.currentIndexChanged.connect(self.update_unit)
        form_layout.addRow("Unit:", self.unit_combobox)


    def update_unit(self):
        # Convert the values from the previous unit to the new one
        unit = self.unit_combobox.currentText()
        factor = _UNIT_IN_CM[self._unit] / _UNIT_IN_CM[unit]
        width = self.width_spinbox.value() * factor
        height = self.height_spinbox.value() * factor
        step = 1 if unit == "mm" else 0.1
        for spin, value in ((self.width_spinbox, width), (self.height_spinbox, height)):
            spin.setSuffix(_SUFFIX[unit])
            spin.setSingleStep(step)
            spin.setValue(value)
        self._unit = unit

    def get_values(self):
        cm = _UNIT_IN_CM[self.unit_combobox.currentText()]
        width = cm_to_pixels(self.width_spinbox.value() * cm)
        height = cm_to_pixels(self.height_spinbox.value() * cm)
        return width, height

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    widget = PageLimitsWidget()
    widget.show()

    print(widget.get_values())
    sys.exit(app.exec_())
