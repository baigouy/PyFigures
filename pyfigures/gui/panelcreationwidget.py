from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import sys
from qtpy.QtWidgets import QApplication, QWidget, QGridLayout, QRadioButton, QSpinBox, QVBoxLayout, QPushButton, QLabel,QCheckBox,QButtonGroup
from qtpy.QtCore import Qt

class PanelCreator(QWidget):
    def __init__(self, parent, num_widgets):
        super().__init__(parent)
        self.num_widgets = num_widgets
        self.initUI()

    def initUI(self):

        self.order_radio_top_down = QRadioButton("Top-down (images better be same size or AR)")
        # self.order_radio_top_down.toggled.connect(self.update_order_radio)
        self.order_radio_left_right = QRadioButton("Left-right")
        self.order_radio_left_right.setChecked(True)
        # self.order_radio_left_right.toggled.connect(self.update_order_radio)
        # Create a QButtonGroup
        self.group = QButtonGroup(self)
        # Add radio buttons to the QButtonGroup
        self.group.addButton(self.order_radio_top_down)
        self.group.addButton(self.order_radio_left_right)

        self.row_radio = QRadioButton("Specify Rows")
        self.col_radio = QRadioButton("Specify Columns")
        self.row_radio.setChecked(True)
        self.row_radio.toggled.connect(self.update_other_value)
        self.col_radio.toggled.connect(self.update_other_value)

        self.num_rows = QSpinBox(self)
        self.num_rows.setRange(1, 10)
        self.num_rows.setValue(2)
        self.num_rows.valueChanged.connect(self.update_other_value)

        self.num_cols = QSpinBox(self)
        self.num_cols.setRange(1, 10)
        self.num_cols.setValue(5)
        self.num_cols.valueChanged.connect(self.update_other_value)

        self.add_empty_checkbox = QCheckBox("Add Empty Placeholders (if row/col is partially empty)")
        self.add_empty_checkbox.setChecked(True)
        self.add_empty_checkbox.setVisible(False)

        self.size_message_label = QLabel("")
        # self.size_message_label.setStyleSheet("color: green; font-weight: bold;")

        main_layout = QVBoxLayout()

        radio_layout = QGridLayout()
        radio_layout.addWidget(QLabel('Panel filling:'), 0, 0)
        radio_layout.addWidget(self.order_radio_left_right, 0, 1)
        radio_layout.addWidget(self.order_radio_top_down, 0, 2)
        radio_layout.addWidget(self.row_radio, 1, 0)
        radio_layout.addWidget(self.num_rows, 1, 1,1,2)
        radio_layout.addWidget(self.col_radio, 2, 0)
        radio_layout.addWidget(self.num_cols, 2, 1,1,2)


        main_layout.addLayout(radio_layout)
        main_layout.addWidget(self.add_empty_checkbox)
        main_layout.addWidget(self.size_message_label)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)

        main_layout.addLayout(self.grid)

        self.setLayout(main_layout)

        self.update_other_value()

        self.setWindowTitle('Grid Panel Generator')
        self.show()

    # def update_order_radio(self, state):
    #     if state:
    #         self.order_radio.setText("Top-down")
    #     else:
    #         self.order_radio.setText("Left-right")
    def update_other_value(self):
        num_rows = self.num_rows.value()
        num_cols = self.num_cols.value()
        total_slots = num_rows * num_cols

        if total_slots > self.num_widgets:
            self.add_empty_checkbox.setVisible(True)
            self.size_message_label.setText("")
        else:
            self.add_empty_checkbox.setVisible(False)
            self.size_message_label.setText("number_of_images = num_cols * num_rows")

        if self.row_radio.isChecked():
            num_cols = self.num_widgets // num_rows if self.num_widgets % num_rows == 0 else self.num_widgets // num_rows + 1
            self.num_cols.setValue(num_cols)
        else:
            num_rows = self.num_widgets // num_cols if self.num_widgets % num_cols == 0 else self.num_widgets // num_cols + 1
            self.num_rows.setValue(num_rows)
        # print(self.get_values())

    def get_values(self):
        num_rows = self.num_rows.value()
        num_cols = self.num_cols.value()
        add_empty_images = self.add_empty_checkbox.isChecked()
        # total_slots = num_cols * num_rows
        # missing_elements = total_slots - self.num_widgets

        values = {
            'num_rows': num_rows,
            'num_cols': num_cols,
            'add_empty_images': add_empty_images,
            # 'missing_elements': missing_elements,
            'order':'X' if self.order_radio_left_right.isChecked() else 'Y'
        }

        return values

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = PanelCreator(None,10)
    print(ex.get_values())
    sys.exit(app.exec_())