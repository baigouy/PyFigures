from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import sys
from batoolset.drawings.shapes.Position import Position
from batoolset.drawings.shapes.serializablefont import SerializableQFont
from batoolset.pyqts.tools import get_html_text_with_font, get_items_of_combo
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QCheckBox, QPushButton, QFontDialog, QLineEdit,QColorDialog,QApplication,QComboBox)
from qtpy.QtGui import QColor, QFont
from qtpy.QtCore import Qt

class AutoLetteringOptions(QWidget):
    def __init__(self, font=None,parent=None, letter_layout='panel', row_letter_align='top'):
        super().__init__(parent)

        # Create a vertical box layout to hold the widgets
        vbox = QVBoxLayout()
        self.setLayout(vbox)

        # Create the background color section
        self.bg_color_check = QCheckBox('Background color')
        self.bg_color_check.setToolTip('A box behind each letter. Without it, black or white '
                                       'letters switch colour where the image under them would '
                                       'hide them (one colour for the figure where possible).')
        self.bg_color_check.setChecked(True)
        self.bg_color_button = QPushButton('Choose color')
        self.bg_color_button.setEnabled(True)
        hbox = QHBoxLayout()
        hbox.addWidget(self.bg_color_check)
        hbox.addWidget(self.bg_color_button)
        vbox.addLayout(hbox)

        # Connect the signals for the background color section
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        self.bg_color_check.stateChanged.connect(
            lambda: self.bg_color_button.setEnabled(self.bg_color_check.isChecked()))

        # self.bg_color_check.stateChanged.connect(self.toggle_bg_color)

        # Create the foreground color section
        self.fg_color_check = QLabel('Foreground color')
        # self.fg_color_check.setChecked(True)
        self.fg_color_button = QPushButton('Choose color')
        self.fg_color_button.setEnabled(True)
        hbox = QHBoxLayout()
        hbox.addWidget(self.fg_color_check)
        hbox.addWidget(self.fg_color_button)
        vbox.addLayout(hbox)

        # Connect the signals for the foreground color section
        self.fg_color_button.clicked.connect(self.choose_fg_color)
        # self.fg_color_check.stateChanged.connect(
        #     lambda: self.fg_color_button.setEnabled(self.fg_color_check.isChecked()))

        # self.fg_color_check.stateChanged.connect(self.toggle_fg_color)

        # Create the font section
        self.font_button = QPushButton('Choose font')
        # self.font_size_label = QLabel('Size:')
        # self.font_size_edit = QLineEdit()
        # self.font_size_edit.setFixedWidth(50)
        # self.font_size_edit.setText('12')
        # self.font_style_label = QLabel('Style:')
        # self.font_style_edit = QLineEdit()
        # self.font_style_edit.setFixedWidth(50)
        # self.font_style_edit.setText('Normal')
        hbox = QHBoxLayout()
        hbox.addWidget(self.font_button)
        # hbox.addWidget(self.font_size_label)
        # hbox.addWidget(self.font_size_edit)
        # hbox.addWidget(self.font_style_label)
        # hbox.addWidget(self.font_style_edit)
        vbox.addLayout(hbox)

        # Connect the signals for the font section
        self.font_button.clicked.connect(self.choose_font)

        position_label = QLabel("Position:")

        # Create a QComboBox for the vertical position
        self.vertical_combo = QComboBox()
        self.vertical_combo.addItems(["Top", "Bottom", "Center_V"])
        # event_filter = ComboBoxEventFilter(self.vertical_combo)

        # Create a QComboBox for the horizontal position
        self.horizontal_combo = QComboBox()
        self.horizontal_combo.addItems(["Left", "Right", "Center_H"])

        hbox2 = QHBoxLayout()
        hbox2.addWidget(position_label)
        hbox2.addWidget(self.vertical_combo)
        hbox2.addWidget(self.horizontal_combo)

        vbox.addLayout(hbox2)

        # one letter in each panel (at the position above), or one letter per
        # row drawn outside the row, in a margin on its left (row_letters.py)
        layout_label = QLabel("Letters:")
        self.layout_combo = QComboBox()
        self.layout_combo.addItem("One in each panel", 'panel')
        self.layout_combo.addItem("One per row, outside on the left", 'row')
        self.layout_combo.setToolTip('"One per row": a single letter for each row of the figure, '
                                     'in a margin left of the row (the rows are narrowed so the '
                                     'figure keeps its width). The panels then carry no letter.')
        self.row_align_combo = QComboBox()
        self.row_align_combo.addItem("Top of the row", 'top')
        self.row_align_combo.addItem("Middle of the row", 'center')
        self.row_align_combo.setToolTip('Where the row letter sits next to its row: level with the '
                                        'top of the row (and of its column titles), or its middle.')
        hbox3 = QHBoxLayout()
        hbox3.addWidget(layout_label)
        hbox3.addWidget(self.layout_combo)
        hbox3.addWidget(self.row_align_combo)
        vbox.addLayout(hbox3)
        self.set_letter_layout(letter_layout, row_letter_align)
        self.layout_combo.currentIndexChanged.connect(self._layout_changed)

        # Set initial values for the options

        # self.font_family = 'Arial'
        # self.font_size = 12
        # self.font_style = 'Normal'

        # Create a QFont object # Arial is a free twin of Helvetica --> so most likely the font to use!!!
        if font is not None:
            self.font = font
        else:
            self.font = QFont('Arial', pointSize=12, weight=QFont.Normal)


        if isinstance(self.font, SerializableQFont):
            # background None = "no background box" (the checkbox was off)
            bg = getattr(self.font, 'background', None)
            fg = getattr(self.font, 'foreground', None)
            self.bg_color = QColor.fromRgb(bg) if bg is not None else QColor('white')
            self.bg_color_check.setChecked(bg is not None)
            self.fg_color = QColor.fromRgb(fg) if fg is not None else QColor('black')
            # position_as_string = self.font.placement.position_to_string()
            if isinstance(getattr(self.font, 'placement', None), Position):
                # (used to read self.associated_text, which this widget never
                # has: an AttributeError as soon as a placement was saved)
                position_as_string = self.font.placement.position_to_string()

                for iii, pos in enumerate(get_items_of_combo(self.horizontal_combo)):
                    if pos.lower() in position_as_string:
                        self.horizontal_combo.setCurrentIndex(iii)
                        break
                for iii, pos in enumerate(get_items_of_combo(self.vertical_combo)):
                    if pos.lower() in position_as_string:
                        self.vertical_combo.setCurrentIndex(iii)
                        break
        else:
            self.bg_color = QColor('white')  # maybe invert it ???
            self.fg_color = QColor('black')

            # Create a QLabel for the position

        # event_filter = ComboBoxEventFilter(self.horizontal_combo)
        # print(self.font.family())
        # print(self.font.pointSize())
        # print(self.font.weight())
            # reload placement from text

                # get it from the combo

        # Set the font properties
        # self.font.setFamily(self.font_family)
        # self.font.setPointSize(self.font_size)
        # if self.font_style == 'Normal':
            # For font style, 'Normal' corresponds to QFont.Normal weight which is equivalent to QFont.Weight.Normal
            # self.font.setWeight(QFont.Normal)


    def set_letter_layout(self, letter_layout='panel', row_letter_align='top'):
        from pyfigures.gui.row_letters import normalise_layout, normalise_align
        self.layout_combo.setCurrentIndex(max(0, self.layout_combo.findData(normalise_layout(letter_layout))))
        self.row_align_combo.setCurrentIndex(max(0, self.row_align_combo.findData(normalise_align(row_letter_align))))
        self._layout_changed()

    def _layout_changed(self, *args):
        # the corner is for letters in the panels, the alignment for row letters
        per_row = self.get_letter_layout() == 'row'
        self.row_align_combo.setEnabled(per_row)
        self.vertical_combo.setEnabled(not per_row)
        self.horizontal_combo.setEnabled(not per_row)

    def get_letter_layout(self):
        return self.layout_combo.currentData() or 'panel'

    def get_row_letter_align(self):
        return self.row_align_combo.currentData() or 'top'

    def choose_bg_color(self):
        """
        Opens a QColorDialog to choose the background color.
        """
        color = QColorDialog.getColor(self.bg_color, self)
        if color.isValid():
            self.bg_color = color

    def toggle_bg_color(self, state):
        """
        Enables or disables the background color button depending on the
        state of the background color checkbox.
        """
        self.bg_color_button.setEnabled(state == Qt.Checked)

    def choose_fg_color(self):
        """
        Opens a QColorDialog to choose the foreground color.
        """
        color = QColorDialog.getColor(self.fg_color, self)
        if color.isValid():
            self.fg_color = color

    # def toggle_fg_color(self, state):
    #     """
    #     Enables or disables the foreground color button depending on the
    #     state of the foreground color checkbox.
    #     """
    #     self.fg_color_button.setEnabled(state == Qt.Checked)



    # def choose_font(self):
    #     """
    #     Opens a QFontDialog to choose the font.
    #     """
    #     font, ok = QFontDialog.getFont(QFont(self.font_family,
    #                                           self.font_size,
    #                                           self.font_style),
    #                                     self)
    #     if ok:
    #         self.font_family = font.family()
    #         self.font_size = font.pointSize()
    #         self.font_style = font.styleName()
    #         self.font_size_edit.setText(str(self.font_size))
    #         self.font_style_edit.setText(self.font_style)

    def choose_font(self):
        font_dialog = QFontDialog(self)
        font_dialog.setCurrentFont(self.font)
        if font_dialog.exec_():
            font = font_dialog.selectedFont()
            # self.font_family = font.family()
            # self.font_size = font.pointSize()
            # self.font_weight = font.weight()
            # self.font_italic = font.italic()

            self.font = font

            # self.font_preview.setFont(font)
            # self.font_preview.setText(self.text_input.text())
            # self.update_font_label()

    def get_font(self):
        # font = self.font_combo.currentFont()
        # font.setPointSize(self.font_size_spin.value())
        # font.setBold(self.bold_check.isChecked())
        # font.setItalic(self.italic_check.isChecked())
        return self.font

    def get_bg_color(self):
        if self.bg_color_check.isChecked():
            return self.bg_color.rgb()
        else:
            return None

    def get_fg_color(self):
        # if self.fg_color_check.isChecked():
        return self.fg_color.rgb()
        # else:
        #     return None

    def get_options(self):
        """
        Returns a dictionary containing the current values of the options.
        """
        options = {
            'bg_color': self.get_bg_color(),
            'fg_color': self.get_fg_color(),
            'font_family': self.font.family(),
            'font_size': self.font.pointSize(),
            'font_style': self.font.styleName(),
        }
        return options

    def get_serializable_font(self):
        # return SerializableQFont(family=self.font.family(), pointSize=self.font.pointSize(),
        #                          weight=self.font.weight(), italic=self.font.i,
        #                          background=font_dict.get('italic', None), foreground=font_dict.get('italic', None))
        tmp = SerializableQFont(self.font)
        tmp.foreground = self.get_fg_color()
        tmp.background = self.get_bg_color()
        tmp.placement = Position(self.vertical_combo.currentText()+'-'+self.horizontal_combo.currentText())
        return tmp


if __name__ == '__main__':
    app = QApplication(sys.argv)
    options_widget = AutoLetteringOptions()
    options_widget.show()

    # get current font
    font = options_widget.get_font()

    # get current background color
    bg_color = options_widget.get_bg_color()

    # get current foreground color
    fg_color = options_widget.get_fg_color()


    print(font, bg_color, fg_color)


    print(get_html_text_with_font('this is a test of your system',font)) # TODO --> allow font to be modified and alike

    print(options_widget.get_serializable_font())
    sys.exit(app.exec_())