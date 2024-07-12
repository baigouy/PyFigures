# mdi.beta
# mdi.alpha
# mdi.gamma
from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import traceback
from batoolset.pyqt.tools import get_items_of_combo, disable_wheel_for_combo_and_spin
# another way of doing greek
# https://www.htmlhelp.com/reference/html40/entities/symbols.html
import sys
import os
from batoolset.draw.shapes.Position import Position
from batoolset.draw.shapes.txt2d import TAText2D
from qtpy.QtWidgets import QApplication, QMainWindow, QAction, QTextEdit, QColorDialog, QFontDialog, QFileDialog, QMenu, QToolButton, QLabel, QSpinBox, QPushButton,QWidget, QVBoxLayout, QSizePolicy,QToolBar,QComboBox,QGroupBox
# from qtpy.QtCore import QObject, QEvent
from qtpy.QtGui import QTextCursor, QFont, QTextCharFormat, QColor, QIcon, QPalette,QTextDocument, QTextOption,QBrush
from qtpy.QtCore import Qt, QSize
import qtawesome as qta
from qtpy.QtCore import Slot
from qtpy.QtCore import Signal
from functools import partial
#
#
#
# class ComboBoxEventFilter(QObject):
#     def __init__(self, combo_box):
#         super().__init__()
#         self._combo_box = combo_box
#         self._combo_box.installEventFilter(self)
#
#     def eventFilter(self, obj, event):
#         if obj == self._combo_box and event.type() == QEvent.Wheel:
#             return True  # Filter out the mouse wheel event
#         return False  # Pass through other events



class TextEditor(QWidget):

    # textChangedByUser = Signal()
    formatChanged = Signal()

    def __init__(self, associated_text=None, show_position=True, show_text_orientation=True, show_range=False, select_all=False):
        super().__init__()
        # select_all = False

        # Create a QGroupBox
        self.groupBox = QGroupBox("Edit text:")  # replace "Your Title Here" with your desired title







        self.textEdit = QTextEdit()
        # Create a default QTextCharFormat object
        # self.default_format = QTextCharFormat() # get the default format and use that if text is in a given list

        # Set the default format to the current character format
        self.textEdit.setLineWrapMode(QTextEdit.NoWrap)  # required to get the drawn text to really mimic this object !!!
        self.associated_text=None

        if associated_text is None:
            self.textDocument = self.textEdit.document()
        else:
            if isinstance(associated_text, TAText2D):
                self.textDocument = associated_text.doc
                self.set_textedit_bg_color(associated_text.fill_color)

                # reset text if within a list
                # Select all text

                # self.textEdit.mergeCurrentCharFormat(self.default_format)
                # Set the default character format for the document
                # default_format = QTextCharFormat()
                # self.textDocument .setCurrentCharFormat(default_format)
                # Create a default QTextCharFormat
                # default_format = QTextCharFormat()
                # # Set the properties of the default format as desired
                # default_format.setFontPointSize(12)  # Example: Set font size to 12
                # default_format.setFontFamily("Arial")  # Example: Set font family to Arial
                # default_format.setForeground(QColor(Qt.black))
                # # Apply the default format to the QTextDocument
                # self.textDocument.setDefaultFont(default_format.font())  # Apply the font to the document
            elif isinstance(associated_text, QTextDocument):
                self.textDocument = associated_text
            else:
                self.textDocument = QTextDocument()
                # print('associated_text in there', associated_text)
                # if isinstance(associated_text, list) and not associated_text: # MEGA DIRTY HACK for unknow reason the passed associated text is [] when text is empty and that creates errors --> how can i fix that ???
                #     associated_text=''
                self.textDocument.setHtml(associated_text)

            self.textEdit.setDocument(self.textDocument)
        self.associated_text = associated_text
        # self.textChanged = Signal(str)
        if isinstance(self.associated_text, TAText2D): # if the text is a tatext then update it when needed
            # self.textEdit.textChanged.connect(self.refresh)
            self.textEdit.textChanged.connect(self.onTextChanged)
            # self.textEdit.focusChanged.connect(self.onTextChanged)
            # self.formatChanged.connect(self.refresh)
            self.formatChanged.connect(self.onTextChanged)

            # self.textEdit.textChanged.connect(self.emitTextChangedByUser)
        self.initUI(show_range, show_position,show_text_orientation)

        # Set the size policy and minimum/maximum size of the widget
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # self.textEdit.selectAll()
        try:
            if select_all:

                try:
                    # Get the HTML text of the document
                    html_text = self.textDocument.toPlainText()
                    # print('html_text', html_text)
                    if html_text == 'Your text here':
                        # self.reset_text_format(self.textDocument)
                        self.textEdit.selectAll()

                        default_format = QTextCharFormat()
                        default_format.setForeground(QColor("black"))
                        self.textEdit.setCurrentCharFormat(default_format)
                        # self.select_all_text(self.textDocument)
                        # Select all the text in the document
                        # cursor = QTextCursor(self.textDocument)
                        # cursor.select(QTextCursor.Document)
                except:
                    traceback.print_exc()




                # self.textEdit.setTextColor(QColor("black"))

                # Set the default text color for new text

        except:
            pass # no big deal if it fails

        self.setMinimumSize(450, 300)
        self.setMaximumHeight(300)

        disable_wheel_for_combo_and_spin(self)
        # self.setMaximumSize(440, 140)
        # self.setMaximumSize(400, 140)
        # self.resize(270, 140)
        # self.setBaseSize(270, 140)


    # def emitTextChangedByUser(self):
    #     self.textChangedByUser.emit()

    # def reset_text_format(self, text_document):
    #     # Create a new QTextCharFormat object with the desired default format
    #     default_format = QTextCharFormat()
    #     default_format.setForeground(QColor("black"))  # Set the default text color to black
    #
    #     # Get a QTextCursor for the entire document
    #     cursor = QTextCursor(text_document)
    #
    #     # Apply the default format to the entire document
    #     cursor.select(QTextCursor.Document)
    #     cursor.mergeCharFormat(default_format)
    #     cursor.clearSelection()
    #
    #     # Set the default format for new text
    #     text_document.setDefaultTextOption(default_format)
    #     text_document.setDefaultTextOption(default_format)
    def select_all_text(self,text_document):
        # Get a QTextCursor for the entire document
        cursor = QTextCursor(text_document)

        # Select the entire document
        cursor.select(QTextCursor.Document)

        # Return the selected text
        return cursor.selectedText()

    def reset_text_format(self,text_document):
        # Create a new QTextCharFormat object with the desired default format
        default_format = QTextCharFormat()
        default_format.setForeground(QColor("black"))  # Set the default text color to black

        # Get a QTextCursor for the entire document
        cursor = QTextCursor(text_document)

        # Apply the default format to the entire document
        cursor.select(QTextCursor.Document)
        cursor.mergeCharFormat(default_format)
        cursor.clearSelection()

        # Create a new QTextOption with the default format
        text_option = QTextOption()
        # text_option.setTextOption(default_format)

        # Set the default format for new text
        text_document.setDefaultTextOption(text_option)

    def initUI(self, show_range=False, show_position=True, show_text_orientation=True):
        # self.setWindowTitle('Text Editor')
        # self.setGeometry(100, 100, 800, 600)
        # self.setGeometry(100, 100, 250, 120)

        # Create a QTextEdit widget

        # self.setCentralWidget(self.textEdit)

        # Create a QTextDocument

        # Create a layout and add the QTextEdit and toolbar to it
        self.layout = QVBoxLayout(self)

        if self.associated_text is not None and self.associated_text.is_letter:
            self.layout.addWidget(QLabel('<font color=#FF0000>The letter is edited automatically, it cannot be edited.</font>'))
            self.setEnabled(False)

        self.layout.addWidget(self.textEdit)
        # self.layout.addWidget(self.toolbar)
        # self.setLayout(self.layout)

        # Set the layout to the QGroupBox
        self.groupBox.setLayout(self.layout)

        # Create actions for formatting options
        self.createActions()
        # self.createMenus()

        cur_show_positions = False
        if isinstance(self.associated_text, TAText2D):
            if isinstance(self.associated_text.placement, Position):
                cur_show_positions=True
                # I also need to relaod the position

        self.createToolbars(add_positions=cur_show_positions if show_position else show_position, add_range=show_range, show_text_orientation=show_text_orientation)

        # Add the QGroupBox to the main widget
        out = QVBoxLayout()
        out.addWidget(self.groupBox)
        self.setLayout(out)  # create a layout for the main widget
        # self.layout().addWidget(self.groupBox)

    def createActions(self):
        # Create actions with icons
        self.italicAction = QAction(qta.icon('fa.italic'), 'Italic', self)
        # self.italicAction.setCheckable(True) # COULD BE NICE TO USE THAT AND UPDATE THIS STATUS BASED ON THE CURRENT SELECTION --> todo
        self.italicAction.triggered.connect(self.toggleItalic)
        # self.italicAction.triggered.connect(self.onTextChanged)

        self.boldAction = QAction(qta.icon('fa.bold'), 'Bold', self)
        # self.boldAction.setCheckable(True)
        self.boldAction.triggered.connect(self.toggleBold)
        # self.boldAction.triggered.connect(self.onTextChanged)

        self.underlineAction = QAction(qta.icon('fa.underline'), 'Underline', self)
        # self.underlineAction.setCheckable(True)
        self.underlineAction.triggered.connect(self.toggleUnderline)

        self.superscriptAction = QAction(qta.icon('fa.superscript'), 'Superscript', self)
        # self.superscriptAction.setCheckable(True)
        self.superscriptAction.triggered.connect(self.toggleSuperscript)

        self.subcriptAction = QAction(qta.icon('fa.subscript'), 'Subscript', self)
        # self.superscriptAction.setCheckable(True)
        self.subcriptAction.triggered.connect(self.toggleSubscript)

        self.fontAction = QAction(qta.icon('fa.font'), 'Font', self)
        self.fontAction.triggered.connect(self.setFont)

        self.bgColorAction = QAction(qta.icon('fa.paint-brush'), 'Background Color', self)
        self.bgColorAction.triggered.connect(self.setBackgroundColor)

        self.fgColorAction = QAction(qta.icon('fa.paint-brush'), 'Foreground Color', self)
        self.fgColorAction.triggered.connect(self.setForegroundColor)

        # self.fontSizeAction = QAction(qta.icon('fa.text-height'), 'Font Size', self)
        # self.fontSizeAction.triggered.connect(self.setFontSize)

        self.alignLeftAction = QAction(qta.icon('fa.align-left'), 'Align Left', self)
        self.alignLeftAction.triggered.connect(lambda: self.setAlignment(Qt.AlignLeft))

        self.alignCenterAction = QAction(qta.icon('fa.align-center'), 'Align Center', self)
        self.alignCenterAction.triggered.connect(lambda: self.setAlignment(Qt.AlignCenter))

        self.alignRightAction = QAction(qta.icon('fa.align-right'), 'Align Right', self)
        self.alignRightAction.triggered.connect(lambda: self.setAlignment(Qt.AlignRight))

        self.orientationAction = QAction(qta.icon('fa.rotate-right'), 'Orientation', self)
        self.orientationAction.triggered.connect(self.setOrientation)

        self.saveAction = QAction(qta.icon('fa.save'), 'Save', self)
        self.saveAction.triggered.connect(self.saveDocument)

        self.loadAction = QAction(qta.icon('fa.folder-open'), 'Load', self)
        self.loadAction.triggered.connect(self.loadDocument)

    def createToolbars(self, add_positions=False, add_range=False, show_text_orientation=True):
        # Create toolbars
        # toolbar = self.addToolBar('Formatting')
        toolbar = QToolBar('Formatting')

        toolbar.addAction(self.fontAction)
        # self.fontSizeLabel = QLabel('Ft Size:')
        self.fontSizeSpinner = QSpinBox()
        # self.fontSizeSpinner.setFocusPolicy(Qt.NoFocus)
        self.fontSizeSpinner.setMinimum(1)
        self.fontSizeSpinner.setMaximum(100)
        self.fontSizeSpinner.setValue(12)
        # self.fontSizeSpinner.valueChanged.connect(self.setFontSize)
        self.fontSizeSpinner.valueChanged.connect(self.setFontSizeFromSpinner)
        # toolbar.addWidget(self.fontSizeLabel)
        toolbar.addWidget(self.fontSizeSpinner)
        toolbar.addAction(self.fontAction)
        color_menu = QMenu("Fg/Bg color", self)

        self.defaultColorAction = QAction('Foreground Color', self)
        self.defaultColorAction.triggered.connect(self.setForegroundColor)

        color_menu.addAction(self.fgColorAction)
        color_menu.addAction(self.bgColorAction)

        fg_bg_color_button = QToolButton()
        fg_bg_color_button.setMenu(color_menu)
        fg_bg_color_button.setDefaultAction(self.defaultColorAction)
        fg_bg_color_button.setPopupMode(QToolButton.MenuButtonPopup)
        fg_bg_color_button.setText("Fg/Bg color")
        toolbar.addWidget(fg_bg_color_button)


        # toolbar.addAction(self.bgColorAction)
        # toolbar.addAction(self.fgColorAction)
        # toolbar.addWidget(self.fgColorButton)
        toolbar.addSeparator()
        self.createButtons(toolbar)
        toolbar.addSeparator()
        toolbar.addAction(self.italicAction)
        toolbar.addAction(self.boldAction)
        toolbar.addAction(self.underlineAction)
        toolbar.addAction(self.superscriptAction)
        toolbar.addAction(self.subcriptAction)


        # toolbar.addAction(self.bgColorAction)
        # toolbar.addAction(self.fgColorAction)
        # toolbar.addAction(self.fontSizeAction)
        # Font size spinner


        # self.contourColor = QPushButton()  # new Commons.PaintedButton()
        # # if self.qt_viewer.contour_color is not None:
        # #     contourColor.setStyleSheet("background-color: "+self.qt_viewer.contour_color.name())
        # #     contourColor.setText(self.qt_viewer.contour_color.name())
        # # else:
        # #     contourColor.setText(str(self.qt_viewer.contour_color))
        # self.set_button_color(self.contourColor, None)
        # self.contourColor.clicked.connect(self.setForegroundColor)

        # toolbar.addWidget(self.contourColor)

        if False:
            # keep this and maybe use this for future development
            toolbar.addSeparator()
            toolbar.addAction(self.alignLeftAction)
            toolbar.addAction(self.alignCenterAction)
            toolbar.addAction(self.alignRightAction)
            toolbar.addSeparator()
            toolbar.addAction(self.orientationAction)
            toolbar.addSeparator()
            toolbar.addAction(self.saveAction)
            toolbar.addAction(self.loadAction)

        # Add Greek letter buttons to the toolbar

        # create a second toolbar to handle postions

        # return toolbar
        # Add the toolbar to the layout of the TextEditor widget
        self.layout.addWidget(toolbar)

        if add_range:
            # TODO add an add orientation of text
            toolbar4 = QToolBar("Text position bar")
            position_label = QLabel("Begin (count starts at 0):")
            self.begin_position_spinner = QSpinBox()
            self.begin_position_spinner.setFocusPolicy(Qt.NoFocus)
            position_label2 = QLabel("End:") # (txt can span n elements)
            self.end_position_spinner = QSpinBox()
            self.end_position_spinner.setFocusPolicy(Qt.NoFocus)

            # print('DABIDA')
            if isinstance(self.associated_text, TAText2D):
                    if self.associated_text.range:

                        # print('inside range', self.associated_text.range, type(self.associated_text.range))

                        try:
                            self.begin_position_spinner.setValue(self.associated_text.range[0])
                            self.end_position_spinner.setValue(self.associated_text.range[-1])
                        except:
                            # traceback.print_exc()
                            # print('error setting range')
                            pass

                        # print('all set')
                        # print(self.begin_position_spinner.value())
                        # print(self.end_position_spinner.value())

            self.begin_position_spinner.valueChanged.connect(self.text_label_range_positioning) # TODO update image range if set
            self.end_position_spinner.valueChanged.connect(self.text_label_range_positioning)

            toolbar4.addWidget(position_label)
            toolbar4.addWidget(self.begin_position_spinner)
            toolbar4.addWidget(position_label2)
            toolbar4.addWidget(self.end_position_spinner)

            # self.text_orientation_combo.currentIndexChanged.connect(self.handle_text_orientation_change)

            # TODO I need connect the spinner

            self.layout.addWidget(toolbar4)


        if show_text_orientation:
            # TODO add an add orientation of text
            toolbar3 = QToolBar("Text Orientation Toolbar")
            position_label = QLabel("Text orientation:")
            self.text_orientation_combo = QComboBox()
            self.text_orientation_combo.addItems(["X", "-X", "Y", "-Y"])

            if isinstance(self.associated_text, TAText2D):
                if self.associated_text.text_orientation:
                    for iii, pos in enumerate(get_items_of_combo(self.text_orientation_combo)):
                        if pos.lower().strip() == self.associated_text.text_orientation.lower().strip():
                            self.text_orientation_combo.setCurrentIndex(iii)
                            break

            toolbar3.addWidget(position_label)
            toolbar3.addWidget(self.text_orientation_combo)

            self.text_orientation_combo.currentIndexChanged.connect(self.handle_text_orientation_change)
            self.layout.addWidget(toolbar3)

        if add_positions:
            # now we add a positional toolbar
            # Create a new QToolBar
            toolbar2 = QToolBar("Position Toolbar")

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

            if isinstance(self.associated_text, TAText2D):
                # reload placement from text
                if isinstance(self.associated_text.placement, Position):
                    # print('current value of text position',self.associated_text.placement.position_to_string())
                    position_as_string =self.associated_text.placement.position_to_string()

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
            toolbar2.addWidget(position_label)
            toolbar2.addWidget(self.vertical_combo)
            toolbar2.addWidget(self.horizontal_combo)

            # Connect the combo boxes to a slot that handles the position change
            self.vertical_combo.currentIndexChanged.connect(self.handle_position_change)
            self.horizontal_combo.currentIndexChanged.connect(self.handle_position_change)
            self.layout.addWidget(toolbar2)

    # def set_button_color(self, btn, color):
    #     if color is not None:
    #         btn.setStyleSheet("background-color: " + color.name())
    #         btn.setText(color.name())
    #     else:
    #         btn.setStyleSheet('')  # reset style sheet
    #         btn.setText(str(color))

    def createButtons(self, toolbar):
        greek_letters = [
            # ("Alpha", "Α", "α"),
            ("Alpha", None, "α"),
            # ("Beta", "Β", "β"),
            ("Beta", None, "β"),
            ("Gamma", "Γ", "γ"),
            ("Delta", "Δ", "δ"),
            # ("Epsilon", "Ε", "ε"),
            ("Epsilon", None, "ε"),
            # ("Zeta", "Ζ", "ζ"),
            ("Zeta", None, "ζ"),
            # ("Eta", "Η", "η"),
            ("Eta", None, "η"),
            ("Theta", None, "θ"),
            # ("Iota", "Ι", "ι"),
            ("Iota", None, "ι"),
            # ("Kappa", "Κ", "κ"),
            ("Kappa", None, "κ"),
            ("Lambda", "Λ", "λ"),
            # ("Mu", "Μ", "μ"),
            ("Mu", None, "μ"),
            # ("Nu", "Ν", "ν"),
            ("Nu", None, "ν"),
            ("Xi", "Ξ", "ξ"),
            ("Omicron", "Ο", "ο"),
            ("Pi", "Π", "π"),
            ("Sigma", "Σ", "σ"),
            # ("Rho", "Ρ", "ρ"),
            ("Rho", None, "ρ"),
            ("Sigma", "Σ", "σ"),
            # ("Tau", "Τ", "τ"),
            ("Tau", None, "τ"),
            # ("Upsilon", "Υ", "υ"),
            ("Phi", "Φ", "φ"),
            ("Chi", "Χ", "χ"),
            ("Psi", "Ψ", "ψ"),
            ("Omega", "Ω", "ω")
        ]

        # Create a dropdown menu for Greek letters
        greek_menu = QMenu("µ", self)

        for name, upper, lower2 in greek_letters:
            if lower2 is not None:
                action = QAction(lower2, self)
                action.triggered.connect(lambda checked, lower=lower2: self.insertText(lower))
                greek_menu.addAction(action)

            if upper is not None:
                action2 = QAction(upper, self)
                action2.triggered.connect(lambda checked, lower=upper: self.insertText(lower))
                greek_menu.addAction(action2)

    # for name, upper, lower2 in greek_letters:
    #         # action = QAction(lower, self)
    #         # try:
    #         #     action = QAction(qta.icon(f'mdi.{name.lower()}'), lower2, self)
    #         # except:
    #
    #         toolbar.addAction(action)
    #
    #         if upper is None:
    #             continue
    #         action2 = QAction(upper, self)
    #         # action.triggered.connect(lambda checked, lower=lower: self.insertText(lower))
    #         # action2.triggered.connect(lambda: self.insertText(upper))
    #         action2.triggered.connect(lambda checked, lower=upper: self.insertText(lower))
    #         toolbar.addAction(action2)
        # Add the dropdown menu to the toolbar
        # toolbar.addMenu(greek_menu)

        micron = QAction('µ', self)
        micron.triggered.connect(lambda checked, lower='µ': self.insertText('µ'))

        # Create a tool button with the dropdown menu
        greek_button = QToolButton()
        greek_button.setDefaultAction(micron) # by default set it to micron as this will be the most used in biology!!!
        greek_button.setMenu(greek_menu)
        greek_button.setPopupMode(QToolButton.MenuButtonPopup)
        greek_button.setText("µ")
        toolbar.addWidget(greek_button)

    # @Slot()
    # def simulateTextChangedEvent(self):
    #     # Emit the textChanged event programmatically
    #     print('simulating event')
    #     # self.textEdit.textChanged.emit()
    #     self.textEdit.textChanged.emit()
    #     # self.addWhitespace()
    #     # self.removeWhitespace()

    def handle_text_orientation_change(self):
        if isinstance(self.associated_text, TAText2D):
            self.associated_text.text_orientation = self.text_orientation_combo.currentText()
            self.formatChanged.emit()  # fire update

    def handle_position_change(self):
        # print('position changed --> ACTION REQUIRED')
        if isinstance(self.associated_text, TAText2D):
            self.associated_text.placement = Position(self.vertical_combo.currentText()+'-'+self.horizontal_combo.currentText())
            self.formatChanged.emit() # fire update

    def addWhitespace(self):
        self.textEdit.insertPlainText(" ")

    def removeWhitespace(self):
        cursor = self.textEdit.textCursor()
        cursor.movePosition(cursor.StartOfLine, cursor.KeepAnchor)
        cursor.removeSelectedText()

    def onTextChanged(self):
        if self.associated_text and isinstance(self.associated_text, TAText2D):
            # print('I have just been called')
            # print('associated text changed')
            # Update the associated object with the text from the QTextEdit
            self.associated_text.setDoc(self.textDocument) #gj.doc =self.textDocument
            # self.associated_text.setHtml(self.textEdit.toHtml())
            # Emit the textChanged signal with the updated text
            # self.textEdit.textChanged.emit()
            # self.simulateTextChangedEvent()


    def insertText(self, text):
        cursor = self.textEdit.textCursor()
        cursor.insertText(text)

    # def createMenus(self):
    #     # Create menus
    #     fileMenu = self.menuBar().addMenu('&File')
    #     fileMenu.addAction(self.saveAction)
    #     fileMenu.addAction(self.loadAction)
    #
    #     editMenu = self.menuBar().addMenu('&Edit')
    #     formatMenu = editMenu.addMenu(qta.icon('fa.edit'), 'Format')
    #     formatMenu.addAction(self.italicAction)
    #     formatMenu.addAction(self.boldAction)
    #     formatMenu.addAction(self.underlineAction)
    #     formatMenu.addAction(self.superscriptAction)
    #     formatMenu.addSeparator()
    #     formatMenu.addAction(self.fontAction)
    #     formatMenu.addAction(self.bgColorAction)
    #     formatMenu.addAction(self.fgColorAction)
    #     formatMenu.addAction(self.fontSizeAction)
    #     formatMenu.addSeparator()
    #     formatMenu.addAction(self.alignLeftAction)
    #     formatMenu.addAction(self.alignCenterAction)
    #     formatMenu.addAction(self.alignRightAction)
    #     formatMenu.addSeparator()
    #     formatMenu.addAction(self.orientationAction)

    def setAlignment(self, alignment):
        cursor = self.textEdit.textCursor()
        blockFormat = cursor.blockFormat()
        blockFormat.setAlignment(alignment)
        cursor.setBlockFormat(blockFormat)
        self.textEdit.setFocus()

    # def toggleItalic(self):
    #     self.toggleFormat(QFont.StyleItalic)
    def toggleItalic(self):
        self.toggleFormat(QTextCharFormat.FontItalic, not self.textEdit.fontItalic())

    # def toggleBold(self):
    #     self.toggleFormat(QFont.Bold)
    # def toggleBold(self):
    #     self.toggleFormat(QTextCharFormat.FontWeight, QFont.Bold)

    # def toggleBold(self):
    #     cursor = self.textEdit.textCursor()
    #     charFormat = cursor.charFormat()
    #     isBold = charFormat.fontWeight() == QFont.Bold
    #     charFormat.setFontWeight(QFont.Bold if not isBold else QFont.Normal)
    #     cursor.mergeCharFormat(charFormat)
    #     self.textEdit.setFocus()
    def toggleBold(self):
        # cursor = self.textEdit.textCursor()
        cursor, initial_selection = self._update_selection_to_all_if_none()
        charFormat = QTextCharFormat()

        # Check if there is a selection
        # if not cursor.hasSelection():
        #     # If no selection, set entire text to bold
        #     charFormat.setFontWeight(QFont.Bold)
        # else:
            # If there is a selection, toggle the bold formatting
        # isBold = charFormat.fontWeight() == QFont.Bold
        charFormat.setFontWeight(QFont.Bold if not cursor.charFormat().fontWeight() == QFont.Bold else QFont.Normal)
        cursor.mergeCharFormat(charFormat)



        self.textEdit.setFocus()
        self._reset_cursor(cursor, initial_selection)
        # self.simulateTextChangedEvent()
        # self.formatChanged.emit()

    def toggleUnderline(self):
        # cursor = self.textEdit.textCursor()
        cursor, initial_selection = self._update_selection_to_all_if_none()
        charFormat =QTextCharFormat()
        # if not cursor.hasSelection():
        #     charFormat.setFontWeight(not charFormat.fontUnderline())
        # else:
        charFormat.setFontUnderline(not cursor.charFormat().fontUnderline())
        cursor.mergeCharFormat(charFormat)
        self.textEdit.setFocus()
        self._reset_cursor(cursor, initial_selection)

    # def toggleSuperscript(self):
    #     self.toggleFormat(QTextCharFormat.VerticalAlignment, QTextCharFormat.AlignSuperScript)
    def toggleSuperscript(self):
        # cursor = self.textEdit.textCursor()
        cursor, initial_selection = self._update_selection_to_all_if_none()
        charFormat = QTextCharFormat()
        currentAlignment = charFormat.verticalAlignment()

        # Toggle between superscript and normal alignment
        if currentAlignment == QTextCharFormat.AlignSuperScript:
            charFormat.setVerticalAlignment(QTextCharFormat.AlignNormal)
        else:
            charFormat.setVerticalAlignment(QTextCharFormat.AlignSuperScript)

        cursor.mergeCharFormat(charFormat)
        self.textEdit.setFocus()
        self._reset_cursor(cursor, initial_selection)

    def toggleSubscript(self):
        # cursor = self.textEdit.textCursor()
        cursor,initial_selection = self._update_selection_to_all_if_none()
        charFormat = QTextCharFormat()

        # Toggle between subscript and normal alignment
        if cursor.charFormat().verticalAlignment() == QTextCharFormat.AlignSubScript:
            charFormat.setVerticalAlignment(QTextCharFormat.AlignNormal)
        else:
            charFormat.setVerticalAlignment(QTextCharFormat.AlignSubScript)

        cursor.mergeCharFormat(charFormat)
        self.textEdit.setFocus()
        self._reset_cursor(cursor, initial_selection)

    # def toggleFormat(self, propertyId, value):
    #     cursor = self.textEdit.textCursor()
    #     charFormat = cursor.charFormat()
    #     charFormat.setVerticalAlignment(value)
    #     cursor.mergeCharFormat(charFormat)
    #     self.textEdit.setFocus()

    def toggleFormat(self, propertyId, value):
        # cursor = self.textEdit.textCursor()
        cursor, initial_selection = self._update_selection_to_all_if_none()
        charFormat = QTextCharFormat()# is that ok, maybe I should only select the relevant format of the text and alike

        if propertyId == QTextCharFormat.FontWeight:
            charFormat.setFontWeight(value)
        elif propertyId == QTextCharFormat.FontItalic:
            charFormat.setFontItalic(value)
        elif propertyId == QTextCharFormat.TextUnderlineStyle:
            charFormat.setFontUnderline(not  cursor.charFormat().fontUnderline())
        elif propertyId == QTextCharFormat.VerticalAlignment:
            charFormat.setVerticalAlignment(value)

        cursor.mergeCharFormat(charFormat)
        self.textEdit.setFocus()
        self._reset_cursor(cursor, initial_selection)

    # def toggleFormat(self, format, value=None):
    #     cursor = self.textEdit.textCursor()
    #     if cursor.hasSelection():
    #         start, end = cursor.selectionStart(), cursor.selectionEnd()
    #         selection = self.textDocument.findBlock(start)
    #         cursor.setPosition(end)
    #         while selection.isValid() and selection.position() <= end:
    #             charFormat = selection.charFormat()
    #             if value is None:
    #                 charFormat.setFontWeight(format)
    #             else:
    #                 charFormat.setProperty(format, value)
    #             cursor.mergeCharFormat(charFormat)
    #             selection = selection.next()
    #     else:
    #         charFormat = cursor.charFormat()
    #         if value is None:
    #             charFormat.setFontWeight(format)
    #         else:
    #             charFormat.setProperty(format, value)
    #         cursor.mergeCharFormat(charFormat)
    #     self.textEdit.setFocus()

    # def setFont(self):
    #     font, ok = QFontDialog.getFont(self.textEdit.currentFont(), self)
    #     if ok:
    #         self.textEdit.setCurrentFont(font)

    def setFont(self):
        font, ok = QFontDialog.getFont(self.textEdit.currentFont(), self)
        # print('dabouyo', font, ok)
        if ok:
            # print('updating text ', font)

            # print('size inside da stuff', font.pointSize())

            # cursor = self.textEdit.textCursor()
            cursor, initial_selection = self._update_selection_to_all_if_none()
            charFormat = QTextCharFormat()
            # Set the font for the entire text if no selection
            # if not cursor.hasSelection():
            #     cursor.select(QTextCursor.Document)
            #     charFormat.setFont(font)
            # else:
                # Set the font for the selected text
            charFormat.setFont(font)
            cursor.mergeCharFormat(charFormat) # in this case I should not merge but directly update it



            # cursor.setCharFormat(charFormat) # in this case I should not merge but directly update it
            self.textEdit.setFocus()
            self._reset_cursor(cursor, initial_selection)
            self.setFontSize(font.pointSize())

    def setBackgroundColor(self):
        # if color is None:
        #     color = QColorDialog.getColor()
            color_dialog = QColorDialog(self)
            # Set the window flags to include the Qt.WindowStaysOnTopHint flag
            color_dialog.setWindowFlags(Qt.WindowStaysOnTopHint | color_dialog.windowFlags())
    #     color_dialog.setOptions(QColorDialog.DontUseNativeDialog)  # Ensure it's not a native dialog
        #     color_dialog.move(self.geometry().center())  # Center the color dialog on the parent window
        #     color = color_dialog.getColor()
            if color_dialog.exec_():
                color = color_dialog.selectedColor()
                if color.isValid():
                    self.textEdit.setStyleSheet("background-color: {}".format(color.name()))
                    if isinstance(self.associated_text, TAText2D):
                        if isinstance(self.associated_text, TAText2D):
                            # self.associated_text.fill_color = color.rgb() & 0xFFFFFF
                            # print('color here', color.rgb() & 0xFFFFFF)
                            self.associated_text.fill_color = color.rgb() & 0xFFFFFF
                            self.set_textedit_bg_color(color)
                            # print('setting color of tatetsxt', self.associated_text.fill_color)
                            self.formatChanged.emit()
            # else: # not sure this would be smart --> but how can I delete a bg if it is ever set ???
            #     if self.associated_text:
            #         if isinstance(self.associated_text, TAText2D):
            #             self.associated_text.fill_color = None
            #             # print('setting color of tatetsxt', self.associated_text.fill_color)
            #             self.formatChanged.emit()

    def int_color_to_html_color(self,color_int):
        # Make sure the color_int is a valid 32-bit integer
        if color_int is not None:
            color_int = color_int & 0xFFFFFF
        else:
            color_int = 0xFFFFFF

        # Convert the integer to a hexadecimal string with leading zeros
        hex_color = "{:06x}".format(color_int)

        # Add a leading hash (#) symbol and return the HTML color
        return "#" + hex_color
    def set_textedit_bg_color(self, color=None):
        # print('inside set_textedit_bg_color', color)
        if color is None and isinstance(self.associated_text, TAText2D):
            color = self.associated_text.fill_color
        # print('inside2 set_textedit_bg_color',color)
        if color:
            # print('inside 3')
            if isinstance(color, QColor):
                # print('inside 4')
                if color.isValid():
                    # print('inside 5')
                    self.textEdit.setStyleSheet("background-color: {}".format(color.name()))
            else:
                # print('inside 6') # --> ok so indeed yellow is there
                # print('color conversion', QColor(color).name(), QColor(color).rgb(), int(QColor(color).rgb()))
                # print('col',color)
                # self.textEdit.setStyleSheet("background-color: {}".format(QColor(color).name()))
                # print('converted_color',color, self.int_color_to_html_color(color& 0xFFFFFF))
                self.textEdit.setStyleSheet("background-color: {}".format(self.int_color_to_html_color(color)))
        else:
            # print('inside 7')
            # self.textEdit.setStyleSheet("background-color: none;")
            self.textEdit.setStyleSheet("background-color: #d0d0d0;")
            # self.textEdit.setStyleSheet("background-color: transparent;")
        # print('inside 8')
        self.update()

    def refresh(self):
        self.set_textedit_bg_color()

        # else:
        #     self.textEdit.setStyleSheet("background-color: {}".format(color.name()))



    def _update_selection_to_all_if_none(self):
        text_cursor = self.textEdit.textCursor()
        initial_selection = text_cursor.selectionStart(), text_cursor.selectionEnd()

        # Check if there's a selection
        if not text_cursor.hasSelection():
            # Select all the text
            text_cursor.select(QTextCursor.Document)
            self.textEdit.setTextCursor(text_cursor)

        return text_cursor,initial_selection


    def _reset_cursor(self, text_cursor, initial_selection):
        # Restore the initial selection
        text_cursor.setPosition(initial_selection[0])
        text_cursor.setPosition(initial_selection[1], QTextCursor.KeepAnchor)
        self.textEdit.setTextCursor(text_cursor)


    def setForegroundColor(self):
        # text_cursor = self.textEdit.textCursor()
        # # Store the initial selection
        # initial_selection = text_cursor.selectionStart(), text_cursor.selectionEnd()
        #
        # # Check if there's a selection
        # if not text_cursor.hasSelection():
        #     # Select all the text
        #     text_cursor.select(QTextCursor.Document)
        #     self.textEdit.setTextCursor(text_cursor)

        text_cursor,initial_selection = self._update_selection_to_all_if_none()

        # color = QColorDialog.getColor()
        color_dialog = QColorDialog(self)
        # Set the window flags to include the Qt.WindowStaysOnTopHint flag
        color_dialog.setWindowFlags(Qt.WindowStaysOnTopHint | color_dialog.windowFlags())
        #     color_dialog.setOptions(QColorDialog.DontUseNativeDialog)  # Ensure it's not a native dialog
        #     color_dialog.move(self.geometry().center())  # Center the color dialog on the parent window
        #     color = color_dialog.getColor()
        if color_dialog.exec_():
            color = color_dialog.selectedColor()
            if color.isValid():
                self.textEdit.setTextColor(color)
            # text_cursor.mergeCharFormat({'foreground': QBrush(color)})

        self._reset_cursor(text_cursor,initial_selection)

    def get_selection_size(text_edit):
        text_cursor = text_edit.textCursor()
        selected_text = text_cursor.selectedText()
        selection_size = len(selected_text)
        return selection_size

    # def setFont(self):
    #     font, ok = QFontDialog.getFont(self.textEdit.currentFont(), self)
    #     if ok:
    #         cursor = self.textEdit.textCursor()
    #         cursor.beginEditBlock()
    #         charFormat = cursor.charFormat()
    #         charFormat.setFont(font)
    #         cursor.mergeCharFormat(charFormat)
    #         cursor.endEditBlock()

    # def setFontSize(self):
    #     font, ok = QFontDialog.getFont(self.textEdit.currentFont(), self)
    #     if ok:
    #         cursor = self.textEdit.textCursor()
    #         cursor.beginEditBlock()
    #         charFormat = cursor.charFormat()
    #         charFormat.setFontPointSize(font.pointSize())
    #         cursor.mergeCharFormat(charFormat)
    #         cursor.endEditBlock()
    # def setFontSize(self):
    #     font, ok = QFontDialog.getFont(self.textEdit.currentFont(), self)
    #     if ok:
    #         font_size = font.pointSize()
    #         if font_size > 0:  # Check if the font size is valid
    #             cursor = self.textEdit.textCursor()
    #             cursor.beginEditBlock()
    #             charFormat = cursor.charFormat()
    #             charFormat.setFontPointSize(font_size)
    #             cursor.mergeCharFormat(charFormat)
    #             cursor.endEditBlock()
    #         else:
    #             print("Invalid font size selected.")

    def text_label_range_positioning(self):

        # if self.sender()==self.begin_position_spinner:
        # value = self.sender().value()

        if self.end_position_spinner.value() < self.begin_position_spinner.value() and self.sender()== self.begin_position_spinner:
            # Temporarily disconnect the QSpinBoxes
            self.begin_position_spinner.valueChanged.disconnect(self.text_label_range_positioning)
            self.end_position_spinner.valueChanged.disconnect(self.text_label_range_positioning)

            self.end_position_spinner.setValue(self.begin_position_spinner.value())

            # Reconnect the QSpinBoxes
            self.begin_position_spinner.valueChanged.connect(self.text_label_range_positioning)
            self.end_position_spinner.valueChanged.connect(self.text_label_range_positioning)
        elif self.end_position_spinner.value() < self.begin_position_spinner.value() and self.sender()== self.end_position_spinner:
            # Temporarily disconnect the QSpinBoxes
            self.begin_position_spinner.valueChanged.disconnect(self.text_label_range_positioning)
            self.end_position_spinner.valueChanged.disconnect(self.text_label_range_positioning)

            self.begin_position_spinner.setValue(self.end_position_spinner.value())

            # Reconnect the QSpinBoxes
            self.begin_position_spinner.valueChanged.connect(self.text_label_range_positioning)
            self.end_position_spinner.valueChanged.connect(self.text_label_range_positioning)
        # self.value = value

        # print(value, self.sender()==self.begin_position_spinner, self.sender()==self.end_position_spinner)
        # maybe set the range directly in every TATextD --> in several ways that is the simplest thing to do

        if isinstance(self.associated_text, TAText2D):
            if isinstance(self.associated_text, TAText2D):
               self.associated_text.range = [self.begin_position_spinner.value(), self.end_position_spinner.value()]



    def setFontSizeFromSpinner(self):
        font_size = self.fontSizeSpinner.value()
        self.setFontSize(font_size)

    # def setFontSize(self, font_size):
    #     if font_size > 0:  # Check if the font size is valid
    #
    #
    #
    #         cursor = self.textEdit.textCursor()
    #         cursor.beginEditBlock()
    #         charFormat = cursor.charFormat()
    #         charFormat.setFontPointSize(font_size)
    #         cursor.mergeCharFormat(charFormat)
    #         cursor.endEditBlock()
    #     else:
    #         print("Invalid font size selected.")
    def setFontSize(self, font_size):

        # print('font_size debug', font_size)
        if font_size > 0:  # Check if the font size is valid
            cursor, initial_selection = self._update_selection_to_all_if_none()
            # cursor = self.textEdit.textCursor()
            # cursor.beginEditBlock()
            # charFormat = cursor.charFormat()
            # charFormat.setFontPointSize(font_size) # this does not work
            # cursor.mergeCharFormat(charFormat)
            # charFormat = cursor.charFormat()
            # font = charFormat.font()
            # font.setPointSizeF(font_size)
            # charFormat.setFontPointSize(font_size)
            # cursor.mergeCharFormat(charFormat)

            # Create a new QTextCharFormat and set the font size
            char_format = QTextCharFormat()
            char_format.setFontPointSize(font_size)


            # Merge the new format with the cursor's current format
            cursor.mergeCharFormat(char_format)


            # cursor.endEditBlock()

            # print('dabouyo')

            # self.textEdit.setFocus()

            self._reset_cursor(cursor, initial_selection)
        else:
            print("Invalid font size selected.")


    def setOrientation(self):
        self.toggleFormat(QTextCharFormat.VerticalAlignment, QTextCharFormat.AlignNormal)

    def saveDocument(self):
        filename=None
        # print(filename)
        if filename is None:
            filename = 'test_txt_as_html2.html'
        with open(filename, 'w') as file:
            # file.write(self.textDocument.toHtml())
            html_content = self.textDocument.toHtml()
            # if True: # force save bg color
            #     bg_color = self.textEdit.palette().color(QPalette.Base).name()
            #     html_content = f'<div style="background-color: {bg_color};">{html_content}</div>' # may not be the best way of doing that --> TODO -−> think about it

                # same for alignment --> see how I can do that ???
            file.write(html_content)

    def loadDocument(self):
        filename = None
        if filename is None:
            filename = 'test_txt_as_html2.html'
        with open(filename, 'r') as file:
            # html_content = file.read()
            # self.textDocument.setHtml(html_content)
            html_content = file.read()
            self.textDocument.setHtml(html_content)

            # Extract and set background color if available
            # if 'background-color' in html_content:
            #     start_index = html_content.find('background-color:') + len('background-color:') + 1
            #     end_index = html_content.find(';', start_index)
            #     bg_color = html_content[start_index:end_index]
            #     self.setBackgroundColor(QColor(bg_color))


if __name__ == '__main__':
    app = QApplication(sys.argv)



    tst = TAText2D('<font color="red">A</font>', placement='top-left')


    html = '''
    <!DOCTYPE html>
    <html>
      <head>
        <title>Font Face</title>
      </head>
      <body>
        <font color="red">
          <font face="Symbol" size="5">Symbol</font><br />
          <font face="Times New Roman" size="5">Times New Roman</font><br />
          <font face="Verdana" size="5">Verdana</font><br />
          <font face="Comic Sans MS" size="5">Comic Sans MS</font><br />
          <font face="WildWest" size="5">WildWest</font><br />
          <font face="Bedrock" size="5">Bedrock</font><br />
        </font>
      </body>
    </html>
    '''

    # tst = TAText2D(html, placement='top-left', fill_color=0xAAAAAA)
    # tst = TAText2D(html, placement='top-left', fill_color=0xAAAAAA)
    tst = TAText2D(html, placement='top-left')
    print(tst.fill_color)


    # editor.textEdit.setText(tst.getHtmlText())

    print('#'*20)
    # editor = TextEditor(tst)
    editor = TextEditor(tst, show_text_orientation=False, show_position=False, show_range=False)
    print(editor.associated_text.fill_color)
    print('#' * 20)

    # somehow it enters twice and I
    print('initial color', editor.int_color_to_html_color(tst.fill_color))
    # the error seems to be created there
    print('-'*20)
    # before that --> ok upon refresh --> error

    editor.refresh()
    print('*'*20)
    # editor = TextEditor()

    print('final color', editor.int_color_to_html_color(tst.fill_color))
    print('final color', editor.int_color_to_html_color(editor.associated_text.fill_color))

    editor.show()



    # print(tst.getPlainText())
    sys.exit(app.exec_())