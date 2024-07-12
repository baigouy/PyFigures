from batoolset.draw.shapes.Position import Position
from batoolset.pyqt.tools import get_items_of_combo
from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from batoolset.draw.shapes.scalebar import ScaleBar
from batoolset.draw.shapes.txt2d import TAText2D
from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout, QDoubleSpinBox, QCheckBox,QLabel,QHBoxLayout,QGroupBox,QComboBox
# from qtpy.QtCore import Qt, QSizeF
from pyfigures.gui.simple_text_editor import TextEditor

class ScaleBarEditor(QWidget):
    def __init__(self, parent=None, scale_bar=None):
        super().__init__(parent)

        self.scale_bar = scale_bar
        if self.scale_bar is None or not isinstance(scale_bar,ScaleBar):
            self.text_editor = TextEditor(TAText2D(placement=None), show_position=False, show_text_orientation=False, show_range=False)
        else:
            self.text_editor =TextEditor(self.scale_bar.legend, show_position=False, show_text_orientation=False, show_range=False)
        # Create a label for the size_spinner
        self.size_label = QLabel('Size in final unit <br>(verify px to unit conversion factor):', self)
        # self.size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.size_spinner = QDoubleSpinBox(self)
        self.size_spinner.setRange(0.000000001, 1000000000.0)
        self.size_spinner.setSingleStep(0.1)
        self.size_spinner.setValue(10)

        if self.scale_bar:
            self.size_spinner.setValue(self.scale_bar.bar_width_in_units)

        self.check_box = QCheckBox('Enable Text', self)
        self.check_box.setChecked(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.check_box)
        layout.addWidget(self.text_editor)
        # layout.addWidget(self.size_spinner)

        # Create a horizontal layout for the size_label and size_spinner
        hlayout = QHBoxLayout()
        hlayout.addWidget(self.size_label)
        hlayout.addWidget(self.size_spinner)
        layout.addLayout(hlayout)  # Add the horizontal layout to the main layout





        if True:
            # now we add a positional toolbar
            # Create a new QToolBar
            # Create a QLabel for the position
            position_label = QLabel("Position:")

            # Create a QComboBox for the vertical position
            self.vertical_combo = QComboBox()
            self.vertical_combo.addItems(["Top", "Bottom", "Center_V"])
            # event_filter = ComboBoxEventFilter(self.vertical_combo)

            # Create a QComboBox for the horizontal position
            self.horizontal_combo = QComboBox()
            self.horizontal_combo.addItems(["Left", "Right", "Center_H"])
            # event_filter = ComboBoxEventFilter(self.horizontal_combo)

            # if isinstance(self.associated_text, TAText2D):
            if True:
                # reload placement from text
                if isinstance(self.scale_bar.placement, Position):
                    # print('current value of text position',self.associated_text.placement.position_to_string())
                    position_as_string =self.scale_bar.placement.position_to_string()

                    for iii,pos in enumerate(get_items_of_combo(self.horizontal_combo)):
                        if pos.lower() in position_as_string:
                            self.horizontal_combo.setCurrentIndex(iii)
                            break
                    for iii,pos in enumerate(get_items_of_combo(self.vertical_combo)):
                        # print(pos.lower() in position_as_string, pos[1:], position_as_string)
                        if pos.lower() in position_as_string:
                            self.vertical_combo.setCurrentIndex(iii)
                            break
                    # get it from the combo


            # Add the label and combo boxes to the toolbar
            layout.addWidget(position_label)
            layout.addWidget(self.vertical_combo)
            layout.addWidget(self.horizontal_combo)


            # Connect the combo boxes to a slot that handles the position change
            self.vertical_combo.currentIndexChanged.connect(self.handle_position_change)
            self.horizontal_combo.currentIndexChanged.connect(self.handle_position_change)
            # layout.addWidget(toolbar2)



        # self.size_spinner.valueChanged.connect(self.update_size)
        self.check_box.stateChanged.connect(self.update_text_visibility)
        self.check_box.setChecked(True)



    def handle_position_change(self):
        # print('position changed --> ACTION REQUIRED')
        # if isinstance(self.associated_text, TAText2D):
        self.scale_bar.placement = Position(self.vertical_combo.currentText()+'-'+self.horizontal_combo.currentText())
            # self.formatChanged.emit() # fire update

    # def update_size(self, value):
    #     new_size = QSizeF(self.text_editor.width() * value, self.text_editor.height() * value)
    #     self.text_editor.setFixedSize(new_size.toSize())


    # maybe put the
    # def update_text_visibility(self, state):
    #     if state == Qt.Checked:
    #         print('changing state to True')
    #         self.text_editor.textEdit.setEnabled(True)
    #         self.text_editor.textEdit.setFocus()  # Make sure the QTextEdit has the keyboard input focus
    #         # self.text_editor.setHidden(True)
    #         # self.text_editor.setVisible(True)
    #         # self.text_editor.update()  # Force the TextEditor to be repainted
    #     else:
    #         print('changing state to False')
    #         self.text_editor.textEdit.setEnabled(False)
    #         # self.text_editor.setHidden(False)
    #         # self.text_editor.setVisible(False)
    #     # self.update()
    def update_text_visibility(self):
        # print(f'update_text_visibility called with state: {state}')
        if not self.check_box.isChecked():
            # print('changing state to True')
            # self.text_editor.setVisible(True)
            self.text_editor.setHidden(True)
            # self.text_editor.textEdit.setEnabled(True)
            # self.text_editor.textEdit.setFocus()  # Make sure the QTextEdit has the keyboard input focus
        else:
            # print('changing state to False')
            # self.text_editor.setVisible(False)
            self.text_editor.setHidden(False)
            # self.text_editor.textEdit.setEnabled(False)

    def getScaleBar(self):




        if self.scale_bar is None:
            return ScaleBar(bar_width_in_units=self.size_spinner.value(), legend=self.text_editor.associated_text if self.check_box.isChecked() else '')
        else:
            self.scale_bar.setBarWidth(self.size_spinner.value())

            print('changing scale bar size to:',self.size_spinner.value())

            self.scale_bar.legend=self.text_editor.associated_text if self.check_box.isChecked() else ''
            self.scale_bar.update_bar_at_scale(1.)
            return self.scale_bar

if __name__ == '__main__':
    app = QApplication([])

    scale_bar = ScaleBar(30, '<font color="#FF00FF">10µm</font>')

    editor = ScaleBarEditor(scale_bar=scale_bar)
    editor.show()

    scale_bar_out =editor.getScaleBar()
    print(scale_bar_out)
    print(scale_bar_out.to_dict())


    app.exec_()
