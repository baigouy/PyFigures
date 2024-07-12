from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel, QSpinBox, QHBoxLayout

class EmptyImageParametersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.width_spinbox = QSpinBox()
        self.width_spinbox.setMinimum(1)
        self.width_spinbox.setMaximum(10000)
        self.width_spinbox.setValue(512)
        self.width_spinbox.setSingleStep(16)

        self.height_spinbox = QSpinBox()
        self.height_spinbox.setMinimum(1)
        self.height_spinbox.setMaximum(10000)
        self.height_spinbox.setValue(512)
        self.height_spinbox.setSingleStep(16)

        self.aspect_ratio_label = QLabel("AR: 1.0")

        self.update_aspect_ratio()

        self.width_spinbox.valueChanged.connect(self.update_aspect_ratio)
        self.height_spinbox.valueChanged.connect(self.update_aspect_ratio)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Width:"))
        layout.addWidget(self.width_spinbox)
        layout.addWidget(QLabel("Height:"))
        layout.addWidget(self.height_spinbox)
        layout.addWidget(QLabel("Aspect Ratio (Width / Height):"))
        layout.addWidget(self.aspect_ratio_label)

    def update_aspect_ratio(self):
        width = self.width_spinbox.value()
        height = self.height_spinbox.value()

        if height != 0:
            aspect_ratio = width / height
            self.aspect_ratio_label.setText(f"AR: {aspect_ratio:.3f}")
        else:
            self.aspect_ratio_label.setText("AR: -")

    def get_image_size(self):
        return self.width_spinbox.value(), self.height_spinbox.value()

    def get_parameters(self):
        return self.width_spinbox.value(), self.height_spinbox.value()