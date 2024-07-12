from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import sys
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QDoubleSpinBox, QSpinBox, QPushButton, \
    QLabel, QColorDialog, QLineEdit
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

class InsetWidget(QWidget):
    def __init__(self, parent=None, input_inset=None):
        super().__init__()
        self.parent = parent

        # Create the main layout
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Create the percentage layout
        percentage_layout = QHBoxLayout()
        main_layout.addLayout(percentage_layout)

        # Create the percentage label
        percentage_label = QLabel("Percentage:")
        percentage_layout.addWidget(percentage_label)

        # Create the percentage spinner
        self.percentage_spinner = QDoubleSpinBox()
        self.percentage_spinner.setRange(0.05, 0.75)
        self.percentage_spinner.setSingleStep(0.01)
        try:
            self.percentage_spinner.setValue(input_inset.fraction_of_parent_image_width_if_image_is_inset)
        except:
            self.percentage_spinner.setValue(0.25)

        percentage_layout.addWidget(self.percentage_spinner)

        # Create the border layout
        border_layout = QHBoxLayout()
        main_layout.addLayout(border_layout)

        # Create the border label
        border_label = QLabel("Border size (px):")
        border_layout.addWidget(border_label)

        # Create the border spinner
        self.border_spinner = QSpinBox()
        self.border_spinner.setRange(0, 64)
        self.border_spinner.setSingleStep(1)
        try:
            self.border_spinner.setValue(input_inset.border_size)
        except:
            self.border_spinner.setValue(3)
        border_layout.addWidget(self.border_spinner)

        # Create the color layout
        color_layout = QHBoxLayout()
        main_layout.addLayout(color_layout)

        # Create the color label
        color_label = QLabel("Color:")
        color_layout.addWidget(color_label)

        # Create the color button
        self.color_button = QPushButton("Pick color")
        self.color_button.clicked.connect(self.pick_color)
        color_layout.addWidget(self.color_button)

        # Create the line edit for the color
        self.color_line_edit = QLineEdit()
        self.color_line_edit.setReadOnly(True)
        color_layout.addWidget(self.color_line_edit)


        # Set the initial color
        try:
            self.color = QColor.fromRgb(input_inset.border_color)
        except:
            self.color = QColor(255, 255, 255)

        # print(self.color.name)
        self.set_color(self.color)

    def pick_color(self):
        # Create the color dialog
        color_dialog = QColorDialog(self.parent)

        # Set the initial color
        color_dialog.setCurrentColor(self.color)

        # Show the color dialog and get the selected color
        if color_dialog.exec_():
            self.color = color_dialog.currentColor()

    def get_percentage(self):
        return self.percentage_spinner.value()

    def get_border_size(self):
        return self.border_spinner.value()

    def get_color(self):
        return self.color

    #

    def set_color(self, color):
        self.color = color
        self.color_line_edit.setText(color.name())
        self.color_line_edit.setStyleSheet(f"background-color: {color.name()};")


    def get_values(self):
        return {
            "percentage": self.get_percentage(),
            "border_size": self.get_border_size(),
            "color": None if self.get_border_size() == 0 else self.get_color(),
        }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = InsetWidget()
    widget.show()


    # Example of recovering the values
    percentage = widget.get_percentage()
    border_size = widget.get_border_size()
    color = widget.get_color()

    print(f"Percentage: {percentage}")
    print(f"Border size: {border_size}")
    print(widget.get_values())

    sys.exit(app.exec_())