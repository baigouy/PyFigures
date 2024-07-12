from batoolset.settings.global_settings import set_UI  # set the UI to qtpy
set_UI()
import time
from batoolset.draw.shapes.serializableguiparams import SerializableGUIparameters
# import filecmp # TODO use that to avoid duplicating a save in undo/redo --> future dev, not urgent
from pyfigures.gui.colorassistant import ColorAssistant
from pyfigures.gui.panelcreationwidget import PanelCreator
from batoolset.dims.tools import pixels_to_cm, pixels_to_inch
from pyfigures.gui.pagelimitswidget import PageLimitsWidget
from pyfigures.gui.tipdialog import TipDialog
from datetime import datetime
from pyfigures.gui.about_dialog_pzf import AboutDialog
from batoolset.dicts.tools import dict_diff
from batoolset.files.tools import smart_name_parser
from pyfigures.gui.keep_tst_images_for_pzf import mega_image_tst, mini_test, mini_tst_svg_rotation, \
    mini_figure, tst_stacks_n_sizes, tst_empties_and_templates, tst_scale_bar, channel_n_lut_test
# import pzfconfig  # path to the consolidated file and variables shared throughout the software
from batoolset.xml.tools import _replace_filename_tags, _update_filename_of_consolidated_files  # , _remove_insets
from pyfigures.gui.user_extra_translation import ExtraTranslationWidget
from batoolset.strings.tools import increment_letter
from pyfigures.gui.autolettering_widget import AutoLetteringOptions
from batoolset.draw.shapes.Position import Position
from batoolset.draw.shapes.serializablefont import SerializableQFont
from batoolset.lists.tools import find_all_objects_of_type, find_first_index, find_first_object_of_type, \
    divide_list_into_sublists, compare_lists_sets
from batoolset.pyqt.tools import get_html_text_with_font, get_shape_after_rotation_and_crop, getCtrlModifierAsString
import os
from batoolset.files.tools import write_string_to_file, read_string_from_file, consolidate_files, \
    smartly_consolidate_files_to_reduce_dupes, consolidate_files2
from batoolset.serialization.tools import deserialize_to_dict, has_custom_script, clone_object
from batoolset.serialization.tools import clone_object, object_to_xml, create_object
from pyfigures.gui.emptyimagedialog import EmptyImageParametersWidget
from pyfigures.gui.customdialog import CustomDialog
from batoolset.draw.shapes.group import Group, set_to_size, set_to_width, set_to_height, set_to_width_im2d, \
    set_to_height_im2d, areIndicesOverlapping
from pyfigures.gui.group_builder_GUI import PanelOrRow
from batoolset.draw.shapes.rectangle2d import Rectangle2D
from batoolset.img import Img, guess_dimensions, start_JVM, stop_JVM
import traceback
from qtpy.QtGui import QColor, QTextCursor, QTextCharFormat, QKeySequence, QTransform
from qtpy.QtWidgets import QApplication, QStackedWidget, QWidget, QTabWidget, QScrollArea, QVBoxLayout, QPushButton, \
    QGridLayout, QTextBrowser, QFrame, QProgressBar, QGroupBox, QAction, QDialog, QDockWidget, QLabel, QMenu, QShortcut, \
    QCheckBox, QSpinBox, QMainWindow, QToolBar, QComboBox, QMenuBar, QMessageBox, QLineEdit
from qtpy.QtCore import Signal, QEvent, Qt, QRect, QRectF, QTimer,QObject,QPoint, QPointF
import qtawesome as qta
import logging
import numpy as np
import matplotlib.pyplot as plt
from batoolset.dialogs.opensave import saveFileDialog, openFileNameDialog
from batoolset.draw.shapes.circle2d import Circle2D
from batoolset.draw.shapes.ellipse2d import Ellipse2D
from batoolset.draw.shapes.freehand2d import Freehand2D
from batoolset.draw.shapes.image2d import Image2D
from batoolset.draw.shapes.line2d import Line2D
from batoolset.draw.shapes.point2d import Point2D
from batoolset.draw.shapes.polygon2d import Polygon2D
from batoolset.draw.shapes.polyline2d import PolyLine2D
from batoolset.draw.shapes.scalebar import ScaleBar
from batoolset.draw.shapes.square2d import Square2D
from batoolset.draw.shapes.txt2d import TAText2D
from pyfigures.gui.scrollableEZFIG import scrollable_EZFIG
from batoolset.tools.qthandler import XStream, QtHandler
from batoolset.uitools.blinker import Blinker
from batoolset.GUI.overlay_hints import Overlay
import atexit
import tempfile
from batoolset.tools.logger import TA_logger  # logging

logger = TA_logger()

__MAJOR__ = 1
__MINOR__ = 0
__MICRO__ = 0
__RELEASE__ = 'a'  # https://www.python.org/dev/peps/pep-0440/#public-version-identifiers --> alpha beta, ...
__VERSION__ = ''.join(
    [str(__MAJOR__), '.', str(__MINOR__), '.'.join([str(__MICRO__)]) if __MICRO__ != 0 else '', __RELEASE__])
__AUTHOR__ = 'Benoit Aigouy'
# __NAME__ = 'Py-Fig: Scientific Figure Creation' # TODO think about a name and how to handle that # PyFigures --> other possible name
__SHORT__NAME__ = 'PyFigures'
__NAME__ = f'{__SHORT__NAME__}: Effortless Creation of High-Quality Scientific Figures'  # TODO think about a name and how to handle that # PyFigures --> other possible name
__EMAIL__ = 'benoit.aigouy@gmail.com'
__DESCRIPTION__ = """PyFigures will assist you assemble publication ready scientific figures in no time."""

# DEBUG = False
DEBUG = True

def cleanup_temp_dir(temp_dir):
    try:
        # print('cleaning up temp dir')
        temp_dir.cleanup()
    except Exception as e:
        print(f"Error cleaning up temporary directory: {e}")

class EZFIG_GUI(QMainWindow):
    # stop_threads = False
    spinBoxEnterPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # if sys.platform == "darwin":
        #     self.ctrl_key = "Meta"  # Command key on macOS
        # else:
        #     self.ctrl_key = "Ctrl" # Control key on other platforms
        self.ctrl_key = getCtrlModifierAsString()

        self.row_or_col_assembly_widget()  # the widget that contain the row or col panels
        self.initUI()
        self.color_assistant = None  # Add this line

        self.activate_or_reset_undo_redo()
        self.save_state(show_popup=False)  # maybe not needed
        self.setAcceptDrops(True)  # we accept DND but just to transfer it to the current list handlers!!!

        # TODO --> add a single tip with all at the beginning and then randomly change tip with a timer maybe add a check both for auto next or alike
        self.tips = [
            # key tips
            "To load images, drag and drop them onto the software.",
            "Combine two images or groups by selecting one and dragging it onto the other.",
            "In this tool, clicking on an object selects the top parent, and each subsequent click selects a more nested element.",
            "Extrude an image/group from its parent by dragging and dropping it onto the background.",
            "View available actions by right-clicking on an image/group.",
            "Edit/annotate an image by double-clicking on it.",
            "Edit a text by double-clicking on it.",
            "You can link a Python script to an image, enabling you to import unsupported formats and/or plot matplotlib graphs. To do this, double-click on an image to edit it and go to the script tab to enter your script. Within the script, you can access `self.filename` to get the associated file(s). End your script with `self.img = your_script_generated_np_array_or_matplotlib_fig`.",
            "To revert an error, use " + self.ctrl_key + "+Z. To redo, use " + self.ctrl_key + "+Shift+Z or " + self.ctrl_key + "+Y.",
            "Use the keyboard arrows to rearrange/reorder elements within a figure or groups.",
            "Contact: benoit.aigouy@gmail.com",
            # less important tips
            "Edit a scale bar by double-clicking on it.",
            "Convert a figure to a template using the template menu or by right-clicking on a selection for partial conversion. This allows for easy recycling of a figure layout and mass production. Then, drag and drop image(s)/file(s) onto the template to assign them to the template.",
            "Did you know that files can be consolidated? This means that all the files associated with a figure will be saved in a .files folder. Please ensure that .pyf and .files are always kept together. Also, avoid mixing consolidated images and non-consolidated ones in a figure.",
            "It is possible to draw Regions of Interest (ROIs) on an image. You can add text at predefined and floating positions to an image. Just double click on an image to access its annotations.",
            "Shapes associated with an image can be reordered. Drag and drop items in the layers list.",
            "Pressing Delete can remove the selected annotation from an image.",
            "Pressing Delete can remove the selection from the current figure image.",
            "Did you know that there is a list of shortcuts available in the help menu?",
            "To add labels above or below an image group, select it, right-click to open the menu, and then choose the appropriate entry in the context menu.",
            "To add text labels to your group, right click on it and select the appropriate entry.",
            "This tool automatically adjusts the layout for you.",
            "To adjust an element's width, select it and set the new size in the menu bar. To resize the entire figure, leave nothing selected and set the size in the menu bar.",
            "To disable automated lettering, uncheck the box in the menu bar.",
            "The .pyf file format is a type of XML/text format, making it suitable for serialization purposes.",
            "The .pyf file saves the path of associated files, but not the files themselves. To store associated files as well, use the consolidation feature.",
            "Always move the .pyf file and the .files folder together when working with a consolidated .pyf file, otherwise links will be lost!",
            "You can export files as vector formats (PDF, SVG) or as raster images (TIF, PNG, JPG) from the file menu.",
            "The default file format for saving in this tool is .pyf, which is a pure XML/text format.",
            "To begin automated lettering from a specific letter, change the letter in the menu bar.",
            "To use capital letters for automated lettering, enter 'A' in the menu bar.",
            "Select a group then press shift on another group, all the groups in between will be selected.",
            "Select a group then press " + self.ctrl_key + " to add another groups to the current selection.",
        ]

        first_tip = "\n<br><br>-".join(self.tips[:11])
        first_tip = '-' + first_tip
        self.tips = [f'<b>Tip {iii}: </b>{tip}' for iii, tip in enumerate(self.tips, start=1)]
        self.tips.insert(0, first_tip)

        # dialog = TipDialog(self, self.tips)
        # dialog.exec_()
        # Show the TipDialog at launch (using a QTimer to avoid recursion)
        # QTimer.singleShot(0, lambda: self.show_tips())
        QTimer.singleShot(0, self.show_tips)

        # Install the event filter on the central widget
        # self.event_filter = WheelEventFilter()
        # self.installEventFilter(self.event_filter)


    def activate_or_reset_undo_redo(self):
        self.undo_stack = []
        self.redo_stack = []
        self.current_index = 0
        self.counter = 0
        self.last_called_state = None
        self.temp_dir = tempfile.TemporaryDirectory()
        self.current_file = None

        if hasattr(self, 'temp_dir') and self.temp_dir.name:
            cleanup_temp_dir(self.temp_dir)

        # this is a trick to make sure that this will ultimately be cleaned even if soft crashes, exactly what I wanted to have!!!
        self.temp_dir = tempfile.TemporaryDirectory()
        atexit.register(cleanup_temp_dir, self.temp_dir)

        self.update_button_state()

    def initUI(self):
        try:
            screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
            centerPoint = QApplication.desktop().screenGeometry(screen).center()
        except:
            from qtpy.QtGui import QGuiApplication
            centerPoint = QGuiApplication.primaryScreen().geometry().center()

        # should even fit on old computer screens (1024x768)
        window_width = 980
        window_height = 720
        self.setGeometry(
            QRect(centerPoint.x() - int(window_width / 2), centerPoint.y() - int(window_height / 2),
                  window_width,
                  window_height))

        self.setWindowIcon(
            qta.icon('fa.newspaper-o', color=QColor(200, 200, 200)))  # very easy to change the color of my icon

        # zoom parameters
        self.setWindowTitle(__NAME__ + ' v' + str(__VERSION__))

        # this is the default paint window of TA
        self.paint = scrollable_EZFIG(show_drawing_commands=False, add_status_bar=False)  # these two things eat up a lot of space and makes it not necessarily nice
        self.paint.EZFIG_panel.selectionChanged.connect(self.selectionUpdated)
        self.paint.EZFIG_panel.informative_message_required.connect(self.show_popup)
        self.paint.EZFIG_panel.undo_redo_save_required.connect(self.save_state)
        self.paint.EZFIG_panel.update_text_rows.connect(self.arrange_text_rows)
        self.paint.EZFIG_panel.focus_required.connect(
            self.paint.scroll_to_item)  # REALLY NO CLUE WHY THAT DOES NOT WORK UNLESS I PRESS CTRL T --> and REALLY NO CLUE HOW TO FIX THAT but low priority bug!!!
        self.paint.EZFIG_panel.update_letters_required.connect(self.update_letters)
        self.paint.EZFIG_panel.force_update_size_of_parent.connect(self.update_size_of_object)
        self.paint.EZFIG_panel.open_lettering_parameters.connect(self.change_lettering_parameters)
        # self.paint.EZFIG_panel.templatify_figure.connect(self.templatify_figure)

        self.serializable_font = SerializableQFont()

        self.list = []  # now this is the currently dragged object

        # can maybe ask the nb of threads to use here too
        self.logger_console = QTextBrowser(self)
        self.logger_console.setReadOnly(True)
        self.logger_console.textCursor().movePosition(QTextCursor.Left, QTextCursor.KeepAnchor, 1)
        self.logger_console.setHtml('<html>')
        self.logger_console.ensureCursorVisible()
        self.logger_console.document().setMaximumBlockCount(1000)  # limits to a 1000 entrees

        if not DEBUG:
            try:
                XStream.stdout().messageWritten.connect(self.set_html_black)
                XStream.stderr().messageWritten.connect(self.set_html_red)
                self.handler = QtHandler()
                self.handler.setFormatter(logging.Formatter(TA_logger.default_format))
                # change default handler for logging
                TA_logger.setHandler(self.handler)
            except:
                traceback.print_exc()

        self.groupBox_logging = QGroupBox('Log')
        self.groupBox_logging.setToolTip("Shows current status.")
        self.groupBox_logging.setMinimumWidth(250)
        self.groupBox_logging.setEnabled(True)
        # groupBox layout
        self.groupBox_pretrain_layout = QGridLayout()
        self.groupBox_pretrain_layout.addWidget(self.logger_console, 0, 0)
        self.groupBox_logging.setLayout(self.groupBox_pretrain_layout)

        self.setCentralWidget(self.paint)
        statusBar = self.statusBar()  # sets an empty status bar --> then can add messages in it
        self.paint.statusBar = statusBar

        if False:
            # so far the progress bar is nit useful --> discard it until required
            # add progress bar to status bar
            self.pbar = QProgressBar(self)
            self.pbar.setToolTip('Shows current progress')
            # self.pbar.setGeometry(200, 80, 250, 20)
            statusBar.addWidget(self.pbar)

            self.stop_all_threads_button = QPushButton('Stop')
            self.stop_all_threads_button.setToolTip(
                "Stops the running function or deep learning prediction as soon as possible.")
            self.stop_all_threads_button.clicked.connect(self.stop_threads_immediately)
            statusBar.addWidget(self.stop_all_threads_button)

            self.about = QPushButton()
            self.about.setIcon(qta.icon('mdi.information-variant', options=[{'scale_factor': 1.5}]))
            self.about.clicked.connect(self.about_dialog)
            self.about.setToolTip('About...')
            statusBar.addWidget(self.about)

        # the esc key removes the selection --> can be useful when the selection takes the whole screen
        escShortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        escShortcut.activated.connect(self.paint.EZFIG_panel.remove_sel)
        escShortcut.setContext(Qt.ApplicationShortcut)  # make sure the shorctut always remain active

        delShortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
        delShortcut.activated.connect(self.paint.EZFIG_panel.delete_selection)
        delShortcut.setContext(Qt.ApplicationShortcut)  # make sure the shorctut always remain active

        del2Shortcut = QShortcut(QKeySequence(Qt.Key_Backspace),
                                 self)  # maybe use that to move left and the space bar to move right so that the arrows can be kept for moving elements verys slowly ???
        del2Shortcut.activated.connect(self.paint.EZFIG_panel.delete_selection)
        del2Shortcut.setContext(Qt.ApplicationShortcut)  # make sure the shorctut always remain active

        # spaceBarShortcut = QShortcut(QKeySequence(Qt.Key_Space), self) # use it or remove it TODO
        # spaceBarShortcut.activated.connect(self.paint.EZFIG_panel.space_bar_pressed)
        # spaceBarShortcut.setContext(Qt.ApplicationShortcut)

        up_shortcut = QShortcut(QKeySequence(Qt.Key_Up), self)  # use it or remove it TODO
        up_shortcut.activated.connect(self.paint.EZFIG_panel.up_pressed)
        up_shortcut.setContext(Qt.ApplicationShortcut)

        down_shortcut = QShortcut(QKeySequence(Qt.Key_Down), self)  # use it or remove it TODO
        down_shortcut.activated.connect(self.paint.EZFIG_panel.down_pressed)
        down_shortcut.setContext(Qt.ApplicationShortcut)

        left_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)  # use it or remove it TODO
        left_shortcut.activated.connect(self.paint.EZFIG_panel.left_pressed)
        left_shortcut.setContext(Qt.ApplicationShortcut)

        right_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)  # use it or remove it TODO
        right_shortcut.activated.connect(self.paint.EZFIG_panel.right_pressed)
        right_shortcut.setContext(Qt.ApplicationShortcut)

        # print('QKeySequence.Copy',QKeySequence.Copy)
        # duplicate_shortcut = QKeySequence.Copy  # Start with the Copy shortcut (Ctrl+C or Command+C)
        # duplicate_shortcut = QKeySequence(duplicate_shortcut[0].replace("C", "D"))
        # print(duplicate_shortcut)

        # Platform-specific key sequence
        ctrl_D_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+D"), self)
        ctrl_D_shortcut.activated.connect(self.paint.EZFIG_panel.duplicate_sel)
        ctrl_D_shortcut.setContext(Qt.ApplicationShortcut)

        ctrl_V_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+V"), self)
        ctrl_V_shortcut.activated.connect(self.paint.EZFIG_panel.duplicate_sel)
        ctrl_V_shortcut.setContext(Qt.ApplicationShortcut)

        # Create a shortcut for Ctrl+S and connect it to the save_pzf method
        save_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+S"), self)
        save_shortcut.activated.connect(self.save_pyfigures)
        save_shortcut.setContext(Qt.ApplicationShortcut)

        tmp_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+T"), self) # Ctrl+T
        tmp_shortcut.activated.connect(self.tst_function)
        tmp_shortcut.setContext(Qt.ApplicationShortcut)

        undo_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+Z"), self)
        undo_shortcut.activated.connect(self.undo)
        undo_shortcut.setContext(Qt.ApplicationShortcut)

        redo_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+Shift+Z"), self)
        redo_shortcut.activated.connect(self.redo)
        redo_shortcut.setContext(Qt.ApplicationShortcut)

        redo_shortcut2 = QShortcut(QKeySequence(f"{self.ctrl_key}+Y"), self)
        redo_shortcut2.activated.connect(self.redo)
        redo_shortcut2.setContext(Qt.ApplicationShortcut)

        select_all_shortcut = QShortcut(QKeySequence(f"{self.ctrl_key}+A"), self)
        select_all_shortcut.activated.connect(self.select_all)
        select_all_shortcut.setContext(Qt.ApplicationShortcut)

        self.blinker = Blinker()
        self.to_blink_after_worker_execution = None
        self.threading_enabled = True

        self.overlay = Overlay(self.centralWidget())  # maybe ok if draws please wait somewhere
        self.overlay.hide()

        self.mainToolBar = QToolBar(self)
        self.mainToolBar.setObjectName("mainToolBar")
        self.addToolBar(Qt.TopToolBarArea, self.mainToolBar)

        self.new_ico = QAction(qta.icon('mdi.newspaper-plus', color_disabled='lightgray'), 'New figure', self)  # 'mdi.new-box'
        self.new_ico.triggered.connect(self.new_fig)

        self.open_ico = QAction(qta.icon('fa.folder-open-o', color_disabled='lightgray'), 'Open', self)  # 'mdi.new-box'
        self.open_ico.triggered.connect(lambda: self.reload_state(path_to_xml_file=None, append=False))

        self.save_in_bar = QAction(qta.icon('fa.save', color_disabled='lightgray'), 'Save', self)
        self.save_in_bar.triggered.connect(self.save_pyfigures)

        self.export_as_tif_ico = QAction(qta.icon('mdi.export', color_disabled='lightgray'), 'Export as raster image',
                                         self)
        self.export_as_tif_ico.triggered.connect(self.export_as_tif)

        # Create QComboBox for 'Fit to'
        fit_to_label = QLabel("Figure width:")
        self.fit_to_combo = QComboBox()
        self.fit_to_combo.addItems(["Width", "Height"])
        if False:
            fit_to_label = QLabel("Fit to:")
            size_label = QLabel("Size:")

        self.size_spinbox = QSpinBox()

        self.size_spinbox.installEventFilter(self)
        self.size_spinbox.setRange(32, 4096)
        self.size_spinbox.setValue(512)  # 21 cm is 595 px
        self.size_spinbox.valueChanged.connect(
            self.on_size_spinbox_value_changed)  # spinbox value finished is so much better

        # self.force_update_layout_button =QPushButton(self)
        # self.force_update_layout_button.setIcon(qta.icon('fa.check', color_disabled='lightgray'))
        # self.force_update_layout_button.setText('Sel')
        # self.force_update_layout_button.setStyleSheet("""
        #     QPushButton {
        #         border: none;
        #         background-color: transparent;
        #     }
        #     QPushButton:pressed {
        #         background-color: lightgray;
        #     }
        # """)
        self.force_update_layout_button = QAction(qta.icon('fa.check', color_disabled='lightgray'),
                                                  'Update selection size', self)
        # self.force_update_layout_button_associated = QAction('All', self)
        self.force_update_layout_button_associated = QLabel('All', self)
        self.force_update_layout_button.triggered.connect(self.on_size_spinbox_value_changed_delayed)
        # self.force_update_layout_button_associated.triggered.connect(self.on_size_spinbox_value_changed_delayed)
        # self.force_update_layout_button.clicked.connect(self.on_size_spinbox_value_changed_delayed)


        self.main_space_spinner_changed_timer = QTimer(self)
        self.main_space_spinner_changed_timer.setSingleShot(True)
        self.main_space_spinner_changed_timer.setInterval(800)  # Delay in milliseconds (e.g., 500ms)
        self.main_space_spinner_changed_timer.timeout.connect(self.update_space_and_paint)

        space_label = QLabel('Y Spacing:')
        self.main_space_spinner =  QSpinBox()
        self.main_space_spinner.setRange(0, 1024)
        self.main_space_spinner.setValue(3)  # 21 cm is 595 px
        # launch a timer and update
        self.main_space_spinner.valueChanged.connect(self.update_space_and_paint_delayed)


        # Set up a timer to delay the execution of the code in the valueChanged slot
        self.value_changed_timer = QTimer(self)
        self.value_changed_timer.setSingleShot(True)
        self.value_changed_timer.setInterval(800)  # Delay in milliseconds (e.g., 500ms)
        self.value_changed_timer.timeout.connect(self.on_size_spinbox_value_changed_delayed)

        # self.spinBoxEnterPressed.connect(self.on_spin_box_enter_pressed) # the pb of this is that if the value is changed it and also one presses enter then the button is called twice -−> so better put a button that would be simpler
        self.spinBoxEnterPressed.connect(
            self.on_size_spinbox_value_changed)  # use the same timer to avoid having issues with the size being executed twice to avoid  # the pb of this is that if the value is changed it and also one presses enter then the button is called twice -−> so better put a button that would be simpler
        # Create value label
        self.value_label = QLabel(f'px {chr(8776)}18.06')

        # Create combobox for units
        self.unit_combobox = QComboBox(self)
        self.unit_combobox.addItems(["Cm", "Inches"])
        self.unit_combobox.currentIndexChanged.connect(self.update_size_in_unit)
        self.update_size_in_unit()

        # Create QCheckBox for 'Auto Positioning'
        if False:
            self.auto_positioning_checkbox = QCheckBox("Auto Positioning")
            self.auto_positioning_checkbox.setChecked(True)

        # Create undo and redo buttons

        self.undo_button = QAction(qta.icon('fa5s.undo', color_disabled='lightgray'), 'Undo', self)
        self.redo_button = QAction(qta.icon('fa5s.redo', color_disabled='lightgray'), 'Redo', self)
        self.undo_button.triggered.connect(self.undo)
        self.redo_button.triggered.connect(self.redo)

        self.auto_lettering_checkbox = QCheckBox('Auto Lettering', self)
        self.auto_lettering_checkbox.setChecked(True)
        # Connect the stateChanged signal to the on_state_changed method
        self.auto_lettering_checkbox.stateChanged.connect(self.paint.EZFIG_panel.update)

        # Create a line edit
        self.letter_line_edit = QLineEdit(self)
        self.letter_line_edit.setText('a')
        # Limit the size of the text to one letter
        self.letter_line_edit.setMaxLength(1)
        # Set the width of the line edit to a small size (e.g., 50 pixels)
        self.letter_line_edit.setFixedWidth(30)
        # Connect the returnPressed signal to a function
        self.letter_line_edit.returnPressed.connect(self.paint.EZFIG_panel.update)

        # Connect the textChanged signal to a function
        self.letter_line_edit.textChanged.connect(self.paint.EZFIG_panel.update)

        # Create "Current size in cm" label
        # current_size_label = QLabel("Correspondence px to unit:")

        self.page_bounds_checkbox = QCheckBox("Page Bounds")
        self.page_bounds_checkbox.setChecked(False)
        self.page_bounds_checkbox.stateChanged.connect(self.on_page_bounds_changed)

        # Add QWidgets directly to  the QToolBar
        self.mainToolBar.addAction(self.open_ico)
        self.mainToolBar.addAction(self.new_ico)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.save_in_bar)
        self.mainToolBar.addAction(self.export_as_tif_ico)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addAction(self.undo_button)
        self.mainToolBar.addAction(self.redo_button)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addWidget(fit_to_label)
        if False:
            self.mainToolBar.addWidget(self.fit_to_combo)
            self.mainToolBar.addWidget(size_label)
        self.mainToolBar.addWidget(self.size_spinbox)
        self.mainToolBar.addWidget(self.value_label)
        self.mainToolBar.addWidget(self.unit_combobox)
        self.mainToolBar.addAction(self.force_update_layout_button)
        # self.mainToolBar.addAction(self.force_update_layout_button_associated)
        # self.mainToolBar.addWidget(self.force_update_layout_button)
        self.mainToolBar.addWidget(self.force_update_layout_button_associated)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addWidget(space_label)
        self.mainToolBar.addWidget(self.main_space_spinner)
        if False:
            self.mainToolBar.addWidget(self.auto_positioning_checkbox)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addWidget(self.auto_lettering_checkbox)
        self.mainToolBar.addWidget(self.letter_line_edit)
        self.mainToolBar.addSeparator()
        self.mainToolBar.addWidget(self.page_bounds_checkbox)

        self.setStatusBar(statusBar)
        self.menuBar = QMenuBar(self)
        self.menuMenu = QMenu(self.menuBar)
        self.menuMenu.setObjectName("menuMenu")
        self.setMenuBar(self.menuBar)
        file_menu = self.menuBar.addMenu("File")

        open_action = QAction('Open', self)
        file_menu.addAction(open_action)
        open_action.triggered.connect(lambda: self.reload_state(path_to_xml_file=None, append=True))

        new_action = QAction('New', self)
        file_menu.addAction(new_action)
        new_action.triggered.connect(self.new_fig)

        # Add a separator
        file_menu.addSeparator()
        save_action = QAction("Save", self)
        file_menu.addAction(save_action)
        save_action.triggered.connect(self.save_pyfigures)

        save_as_action = QAction("Save As...", self)
        file_menu.addAction(save_as_action)
        save_as_action.triggered.connect(lambda: self.save_pyfigures(file=None))

        save_n_consolidate_action = QAction("Save And Consolidate...", self)
        file_menu.addAction(save_n_consolidate_action)
        save_n_consolidate_action.triggered.connect(lambda: self.save_and_consolidate())

        # Add a separator
        file_menu.addSeparator()
        export_as_svg_action = QAction("Export as svg", self)
        file_menu.addAction(export_as_svg_action)
        export_as_svg_action.triggered.connect(self.export_as_svg)

        export_as_pdf_action = QAction("Export as pdf", self)
        file_menu.addAction(export_as_pdf_action)
        export_as_pdf_action.triggered.connect(self.export_as_pdf)

        export_as_tif_action = QAction("Export as... (jpg, tif, png)", self)
        file_menu.addAction(export_as_tif_action)
        export_as_tif_action.triggered.connect(self.export_as_tif)

        selection = self.menuBar.addMenu("Selection")
        reset_selection = QAction("Reset Selection", self)  # ? shall I say it like that
        selection.addAction(reset_selection)
        reset_selection.triggered.connect(lambda: (self.paint.EZFIG_panel.set_current_selection(None),
                                                   self.paint.EZFIG_panel.update()))  # cool I didn't know one can do that...

        duplicate_selection = QAction("Duplicate Selection", self)  # ? shall I say it like that
        selection.addAction(duplicate_selection)
        duplicate_selection.triggered.connect(self.paint.EZFIG_panel.duplicate)  # cool I didn't know one can do that...

        lettering = self.menuBar.addMenu("Lettering")
        lettering_parameters = QAction("Parameters", self)  # ? shall I say it like that
        lettering.addAction(lettering_parameters)
        lettering_parameters.triggered.connect(
            self.change_lettering_parameters)  # cool I didn't know one can do that...

        annots = self.menuBar.addMenu("Annotations")
        rm_all_annots = QAction("Remove all annotations (ROIs, scale bars, texts, ...)", self)  # ? shall I say it like that
        annots.addAction(rm_all_annots)
        rm_all_annots.triggered.connect(self.paint.EZFIG_panel.remove_all_annotations)  # cool I didn't know one can do that...
        rm_all_scale = QAction("Remove all scale bars", self)  # ? shall I say it like that
        annots.addAction(rm_all_scale)
        rm_all_scale.triggered.connect(lambda:self.paint.EZFIG_panel.remove_stuff(type_of_stuff=ScaleBar))  # cool I didn't know one can do that...
        rm_all_texts = QAction("Remove all texts", self)  # ? shall I say it like that
        annots.addAction(rm_all_texts)
        rm_all_texts.triggered.connect(lambda:self.paint.EZFIG_panel.remove_stuff(type_of_stuff=TAText2D))  # cool I didn't know one can do that...
        rm_all_ROIs = QAction("Remove all ROIs", self)  # ? shall I say it like that
        annots.addAction(rm_all_ROIs)
        rm_all_ROIs.triggered.connect(lambda:self.paint.EZFIG_panel.remove_stuff(type_of_stuff=[Circle2D, Ellipse2D,Freehand2D,  Line2D,Point2D, Polygon2D, PolyLine2D, Rectangle2D,Square2D]))  # cool I didn't know one can do that...
        rm_all_insets = QAction("Remove all insets", self)  # ? shall I say it like that
        annots.addAction(rm_all_insets)
        rm_all_insets.triggered.connect(lambda:self.paint.EZFIG_panel.remove_stuff(type_of_stuff=Image2D))

        template = self.menuBar.addMenu("Template")
        templatify_action = QAction("Convert figure to template", self)  # ? shall I say it like that
        template.addAction(templatify_action)
        templatify_action.triggered.connect(self.templatify_figure)  # cool I didn't know one can do that...

        help_menu = self.menuBar.addMenu('Help')
        about_soft = QAction("About", self)  # ? shall I say it like that
        help_menu.addAction(about_soft)
        about_soft.triggered.connect(self.show_about_dialog)
        # Add an action to show tips
        show_tips_action = QAction("Show Tips", self)
        show_tips_action.triggered.connect(self.show_tips)
        help_menu.addAction(show_tips_action)
        # Add an action to show shortcuts
        show_shortcuts_action = QAction("List shortcuts", self)
        show_shortcuts_action.triggered.connect(self.show_shortcuts_dialog)
        help_menu.addAction(show_shortcuts_action)

        show_color_blind_assistant = QAction('Show color-blind assistant', self)
        show_color_blind_assistant.triggered.connect(self.launch_color_assistant)
        help_menu.addAction(show_color_blind_assistant)


    def update_space_and_paint_delayed(self):
        self.main_space_spinner_changed_timer.start()

    # I need to store this value and also I need a timer to prevent changing this too often -−> TODO
    # I also need to get the stuff there
    def update_space_and_paint(self):
        try:
            # print('really updating space')
            self.paint.EZFIG_panel.space = self.main_space_spinner.value()
            self.paint.EZFIG_panel.update()
            self.paint.EZFIG_panel.undo_redo_save_required.emit()
        except:
            pass

    def on_page_bounds_changed(self):
        if self.page_bounds_checkbox.isChecked():
            # print('page bounds changed ACTION REQUIRED!!!')
            main = PageLimitsWidget()
            custom_dialog = CustomDialog(title="Page Bounds",
                                         message=None,
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=main, options=['Done'], parent=self, auto_adjust=True)
            if custom_dialog.exec_() == QDialog.Accepted:
                w, h = main.get_values()
                self.paint.EZFIG_panel.bounds = QRectF(self.paint.EZFIG_panel._EXTRA_PADDING,
                                                       self.paint.EZFIG_panel._EXTRA_PADDING, w, h)
                self.paint.EZFIG_panel.update()
        else:
            # print('I need to reset the page bounds --> TODO')
            self.paint.EZFIG_panel.bounds = None
            self.paint.EZFIG_panel.update()

    def update_size_in_unit(self):
        if 'nch' in self.unit_combobox.currentText():
            value = pixels_to_inch(self.size_spinbox.value())
        else:
            value = pixels_to_cm(self.size_spinbox.value())
        rounded_value_str = "px "+str(chr(8776))+"{:.1f}".format(round(value, 1))  #
        self.value_label.setText(rounded_value_str)
        # print('update size in cm or in inches to display ACTION REQUIRED', self.size_spinbox.value(),  self.unit_combobox.currentText(), self.value_label)

    def show_shortcuts_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Shortcuts')

        layout = QVBoxLayout(dialog)

        # Generate HTML content dynamically
        html_content = """
                <html>
                <head>
                    <style>
                        table {
                            border-collapse: collapse;
                            width: 100%;
                        }
                        th, td {
                            text-align: left;
                            padding: 8px;
                            border-bottom: 1px solid #ddd;
                        }
                        th {
                            background-color: #f2f2f2;
                        }
                    </style>
                </head>
                <body>
                    <table>
                        <tr><th>Shortcut</th><th>Effect</th></tr>
                """

        shortcuts = [
            ("" + self.ctrl_key + "+D", "Duplicate selection"),
            ("" + self.ctrl_key + "+V", "Duplicate selection"),
            ("" + self.ctrl_key + "+S", "Save"),
            # ("Ctrl+T", "Test function"),
            ("" + self.ctrl_key + "+Z", "Undo"),
            ("" + self.ctrl_key + "+Shift+Z or " + self.ctrl_key + "+Y", "Redo"),
            ("Delete", "Delete selection"),
            ("Backspace", "Delete selection"),
            ("Esc", "Deselect selection"),
            # ("Space", "Space bar pressed"),
            ("Up Arrow", "Move up/left the selected element within the figure or a group"),
            ("Left Arrow", "Move up/left the selected element within the figure or a group"),
            ("Down Arrow", "Move down/right the selected element within the figure or a group"),
            ("Right Arrow", "Move down/right the selected element within the figure or a group"),
        ]

        for shortcut, effect in shortcuts:
            html_content += f"<tr><td>{shortcut}</td><td>{effect}</td></tr>"

        html_content += """
                    </table>
                </body>
                </html>
                """

        browser = QTextBrowser()
        browser.setHtml(html_content)
        browser.setReadOnly(True)
        layout.addWidget(browser)

        # Create a close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        # dialog.adjustSize()
        # Set a minimum size for the dialog
        dialog.setMinimumSize(600, 400)

        # Set the size policy for the dialog
        # dialog.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        dialog.exec_()

    def show_tips(self):
        dialog = TipDialog(self, self.tips)
        dialog.exec_()

    def show_about_dialog(self):
        current_year = datetime.now().year
        if current_year > 2024:
            year_string = f"-{current_year}"
        else:
            year_string = ""
        about_dialog = AboutDialog(self, title=__NAME__, name=__SHORT__NAME__,
                                   version=f"Version {__MAJOR__}.{__MINOR__}.{__MICRO__} {__RELEASE__}",
                                   description=__DESCRIPTION__, copyright=f"© 2024{year_string} {__AUTHOR__}",
                                   email=__EMAIL__, ok_or_close="Ok")
        about_dialog.exec_()

    def show_popup(self, str):
        self.paint.show_popup(str)

    def launch_color_assistant(self):
        # print('I am called, ACTION REQUIRED!!!')
        if self.color_assistant is None or not self.color_assistant.isVisible():
            self.color_assistant = ColorAssistant(capture_width=256, capture_height=128)
        self.color_assistant.show()


    def update_size_of_object(self, cur_sel, value=None):

        # print('I am called', cur_sel, value)

        if cur_sel is None:
            return

        if value is None:
            value = self.size_spinbox.value()

        # print('I am called2', cur_sel, value)

        # print('this object must have its size updated ACTION REQUIRED SOON', cur_sel)
        # if several are selected --> I could really use that or also hach THIS TO
        # print('TODO NEEDS IMPROVEMENT AND NEED TO SUPPORT THE STUFF') # shall I remove the height version of it --> maybe simpler and simpler code
        if isinstance(cur_sel, Group):
            # print(self.paint.EZFIG_panel.selected_shape)
            # set_to_size(self.paint.EZFIG_panel.selected_shape, value)

            # get the element above or below it

            if 'idth' in self.fit_to_combo.currentText():
                try:
                    set_to_width(cur_sel, value)
                except:
                    print('error occurred in setting width1')
                    traceback.print_exc()
                    # sys.exit(0)
            else:
                try:
                    set_to_height(cur_sel, value)
                except:
                    print('error occurred in setting height1')
                    traceback.print_exc()
        elif isinstance(cur_sel, Image2D):
            if 'idth' in self.fit_to_combo.currentText():
                try:
                    set_to_width_im2d(cur_sel, value)
                except:
                    print('error occurred in setting width2')
                    traceback.print_exc()
            else:
                try:
                    set_to_height_im2d(cur_sel, value)
                except:
                    print('error occurred in setting height2')
                    traceback.print_exc()

    def selectionUpdated(self):
        # the alternative is to put all as right click --> maybe an idea

        # print('SELECTION WAS CHANGED --> MAKE USE OF THIS TO UPDATE THE INTERFACE OPTIONS ') # -−> TODO
        # print('CURRENT SELECTION', self.paint.EZFIG_panel.selected_shape)

        tmp = self.paint.EZFIG_panel.selected_shape
        if not isinstance(self.paint.EZFIG_panel.selected_shape, list):
            tmp = [tmp]

        if (compare_lists_sets(tmp, self.paint.EZFIG_panel.shapes_to_draw) and self.paint.EZFIG_panel.shapes_to_draw) or not self.paint.EZFIG_panel.selected_shape:
            self.force_update_layout_button_associated.setText('All')
            # self.force_update_layout_button.setToolTip()
        else:
            self.force_update_layout_button_associated.setText('Sel')

        # Create a QWidget to hold the layout
        if False:
            dock_widget_contents = QWidget()

            # Create a QVBoxLayout to arrange widgets vertically
            dock_widget_layout = QVBoxLayout()
            dock_widget_layout.setAlignment(
                Qt.AlignTop)  # Set the alignment of the layout # FINALLY I CAN GET MY TEXT AT THE TOP  -−> TRY TO ALWAYS USE THAT

        # if isinstance(self.paint.EZFIG_panel.selected_shape, list):
        #     # label = QLabel("MULTI SELECTION DETECTED --> TODO")
        #     dock_widget_contents = self.row_or_col_assembly
        #     self.row_or_col_context_menu()
        # else:
        #
        #     print('debugging 23')
        #     if self.paint.EZFIG_panel.selected_shape is None:
        #         # label = QLabel(
        #         #     'SINGLE SELECTION DETECTED --> TODO ' + str(type(self.paint.EZFIG_panel.selected_shape)) + str(
        #         #         self.paint.EZFIG_panel.selected_shape))
        #         # if isinstance(self.paint.EZFIG_panel.selected_shape, Image2D):
        #         #     self.image_context_menu()
        #         # elif isinstance(self.paint.EZFIG_panel.selected_shape, Group):
        #         #     print('edit group stuff')
        #         #     self.group_context_menu(self.paint.EZFIG_panel.contextMenu)
        #     # else:
        #         # label = QLabel('SELECTION RESET DETECTED --> TODO')
        #         self.default_context_menu()

        if False:
            # Add the label to the layout
            dock_widget_layout.addWidget(label)

            # Set the layout to the dock widget contents
            dock_widget_contents.setLayout(dock_widget_layout)

    def dragEnterEvent(self, event):
        if not self.acceptDrops():
            logger.warning('Drag and drop not supported in "Preview" mode, please select another tab.')
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self.acceptDrops():
            logger.warning('Drag and drop not supported in "Preview" mode, please select another tab.')
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()
        # handle DND on drop

    def dropEvent(self, event):
        if not self.acceptDrops():
            logger.warning('Drag and drop not supported in "Preview" mode, please select another tab.')
            event.ignore()
            return

        # print('inside DND, event',  event.mimeData().hasUrls())
        # #
        # for url in event.mimeData().urls():
        #     print(url)


        if event.mimeData().hasUrls():
            self.list = []
            event.setDropAction(Qt.CopyAction)


            urls = []
            for url in event.mimeData().urls():
                urls.append(url.toLocalFile())
                # event.mimeData().removeUrls([url])
            # add all dropped items to the list
            for url in urls:
                # item = QListWidgetItem(os.path.basename(url), self.list)
                # item.setToolTip(url)
                # self.list.addItem(item)
                # self.add_file_to_list_if_supported(url)
                if os.path.isfile(url):
                    self.list.append(url)





            # try to do things here --> TODO --> ask if should be added as a row or as a col and what should be set (height or width --> TODO)
            # self.add_image()
            # event.ignore()
            event.accept()

            if self.list:

                event_pos_in_current_widget = event.pos()
                event_pos_global = self.mapToGlobal(event_pos_in_current_widget)
                event_pos_in_target_widget = self.paint.EZFIG_panel.mapFromGlobal(event_pos_global)

                # event_pos_in_target_widget = self.paint.EZFIG_panel.mapFromGlobal(event_pos_global)
                event_pos_global2 = self.mapToGlobal(self.paint.EZFIG_panel.mapFromGlobal(event.pos()))

                # event_pos_in_target_widget_scaled = event_pos_in_target_widget/ self.paint.EZFIG_panel.scale
                event_pos_in_target_widget_scaled = event_pos_in_target_widget / self.paint.EZFIG_panel.scale

                # event_pos_in_target_widget = self.paint.EZFIG_panel.scrollArea.mapFromGlobal(event_pos_global)
                event_pos_in_target_widget = self.paint.scrollArea.mapFromGlobal(event_pos_global)

                # event_pos_in_target_widget_scaled = event_pos_in_current_widget/ self.paint.EZFIG_panel.scale

                # can I get the shape below that
                all_shapes_below, first_encounter_below, drop_target, all_encounters_in_shape_below_mouse, all_encounters_of_sel_shape_below_mouse, top_parent_of_sel, immediate_parentof_sel, top_parent_of_drop_target = self.paint.EZFIG_panel.get_all_shapes_involved_in_DND_process_by_mouse_position(
                    event, event_pos_in_target_widget_scaled)

                # print('grabouilla', all_shapes_below)
                # print('grabouilla2', all_encounters_in_shape_below_mouse)

                # there is a bug --> it does not seem to detect the position properly --> is that due to scaling or alike errors???

                # print('is_contained in first',self.paint.EZFIG_panel.shapes_to_draw[0].content[0].getRect(all=True).contains(event_pos_in_target_widget_scaled))

                # I can make use of the shapes below the mouse to decide the options -−> such as to add the stuff below the mouse and for example replace template
                # TODO --> à faire !!!

                # Map the position of the drop event to global coordinates
                global_pos = self.mapToGlobal(event.pos())

                # global_pos = event_pos_in_current_widget
                # global_pos = event_pos_in_current_widget

                # try:
                #     event.ignore()
                # except:
                #     traceback.print_exc()
                # print('comparison of pos', event_pos_in_current_widget, event_pos_global, event_pos_in_target_widget, event_pos_in_target_widget_scaled)
                # Open the context menu at the mapped position
                try:
                    # Open the context menu at the position of the drop event
                    self.add_image_from_an_external_source_context_menu(self.list, all_encounters_in_shape_below_mouse if all_encounters_in_shape_below_mouse is not None else all_encounters_of_sel_shape_below_mouse)
                    start_time = time.time()
                    self.paint.EZFIG_panel.contextMenu.exec_(global_pos)
                    end_time = time.time()
                    time_spent = end_time - start_time

                    if time_spent<0.1:  # DEV NOTE −−> KEEP THAT
                        # assume the popup didn't show and try an ultimate rescue
                        # DEV NOTE KEEP NB MEGA TODO -−> THIS IS A VERY HACKY SOLUTION TO GET THE MENU TO SHOW IN UBUNTU WAYLAND
                        # ON UBUNTU WAYLAND THE MAPPING IS NOT POSSIBLE TO THE MAIN WINDOW AND SO THE CONTEXT MENU DOES NOT SHOW SO WE CREATE A PARENTLESS MENU THAT WILL ALWAYS SHOW ALTHOUGH AT AN ERRONEOUS POSITION BUT THAT IS BETTER THAN NOTHING

                        # Create a context menu
                        context_menu = QMenu() # NB KEEP NOT PUTTING SELF IS THE ONLY WAY TO GET IT RIGHT --> that is really a pb
                        for action in self.paint.EZFIG_panel.contextMenu.actions():
                            context_menu.addAction(action)
                        context_menu.exec_(QPoint(0,0))
                except:
                    traceback.print_exc()
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()
        # self.list = [] # shall I reset it ???

    def add_image_from_an_external_source_context_menu(self, lst, all_encounters_in_shape_below_mouse):
        # print('MENU FOR WHAT TO DO WITH EXTERNAL IMAGES !!! −> MEGA ACTION REQUIRED!!!')

        self.paint.EZFIG_panel.contextMenu = QMenu(self)

        # if the image is actually a .pyf file I should just try to open it directly using the open menu and warn that there is an error!!!


        # and see how to fuse them if there are many pyfs and if there is a mix then warn


        # MEGA TODO -−> add a check to see if there are .pyf files in the dropped list and if this is a mix -> put a warning else concatenate the files in the same order without resetting the previous ones --> TODO --> implement the code and make sure a new save file name is created

        pyf_list = []
        if lst:
            pyf_list = [elm for elm in lst if (isinstance(elm, str) and elm.lower().endswith('.pyf'))]

            if pyf_list:
                # self.show_popup('Importing several pyf files please wait...')
                # time.sleep(2)
                # print('loading several .pyf files please be patient...')
                for elm in pyf_list:
                    try:
                        if has_custom_script(read_string_from_file(elm)):
                            reply = QMessageBox.warning(self, 'Security Warning',
                                                        '<span style="color: red;">The file contains custom script code. ' \
                                                        'Opening this file may pose security risks, as it could execute untrusted or malicious code. ' \
                                                        'Only proceed if you trust the source of the file and understand the implications.<br><br>' \
                                                        'Do you REALLY want to continue?</span>',
                                                        QMessageBox.Yes | QMessageBox.No)
                            if reply == QMessageBox.No:
                                continue
                        self.reload_state(path_to_xml_file=elm, append=True)
                    except:
                        traceback.print_exc()
                        logger.error('could not read '+str(elm))
                self.current_file = None # force not overwrite on current file

            lst = [elm for elm in lst if elm not in pyf_list] # we remove pyf files from the list
            # we clean the lst from pyf files and open the pyf content

        if not lst:
            if pyf_list:
                self.paint.EZFIG_panel.undo_redo_save_required.emit()
            return

        ignore = self.paint.EZFIG_panel.contextMenu.addAction("Ignore")
        # do not offer row if single image

        if len(lst) > 1:
            self.paint.EZFIG_panel.contextMenu.addSeparator()
            add_to_new_row = self.paint.EZFIG_panel.contextMenu.addAction("To row")
            add_to_new_row.triggered.connect(lambda: self.add_images_to_new_row(lst=lst))

            add_to_new_col = self.paint.EZFIG_panel.contextMenu.addAction("To column")
            add_to_new_col.triggered.connect(lambda: self.add_images_to_new_col(lst=lst))

            self.paint.EZFIG_panel.contextMenu.addSeparator()
            # add_as_panel = self.paint.EZFIG_panel.contextMenu.addAction("Add as grid panel (Rows + Cols)")
            add_as_panel = self.paint.EZFIG_panel.contextMenu.addAction("To panel")
            add_as_panel.triggered.connect(lambda: self.create_panel(lst=lst))
        # else:
        #     if isinstance(lst[0], str) and lst[0].lower().endswith('.pyf'):
        #         # open it with the default open menu --> TODO
        #         self.reload_state(path_to_xml_file=lst[0], append=True)
                # I could add the rest maybe --> easy in fact todo
                # return
        # if one of the images below is a template --> offer
        # search for image2D in all_encounters_in_shape_below_mouse

        # print('single object is dragged')

        if all_encounters_in_shape_below_mouse: # why is that None
            # check if there is a template image below the mous and if this is the case, then offer replace it
            potential_target = find_first_object_of_type(all_encounters_in_shape_below_mouse, Image2D)
            if potential_target is not None and potential_target.is_template():
                # replace its name by that of the new
                self.paint.EZFIG_panel.contextMenu.addSeparator()
                set_image_in_template = self.paint.EZFIG_panel.contextMenu.addAction(
                    "Assign DND content to template image")
                set_image_in_template.triggered.connect(lambda: self.assign_to_template(potential_target, self.list))

        self.paint.EZFIG_panel.contextMenu.addSeparator()
        all_as_single_images = self.paint.EZFIG_panel.contextMenu.addAction("Add as single image(s)")
        all_as_single_images.triggered.connect(lambda: self.all_images_directly(lst=lst))

        # duplicate = self.paint.EZFIG_panel.contextMenu.addAction("Duplicate Selection")
        # duplicate.triggered.connect(self.paint.EZFIG_panel.duplicate)
        #
        # combine_as_row = self.paint.EZFIG_panel.contextMenu.addAction("Combine Horizontally (Row)")
        # combine_as_row.triggered.connect(self.combine_in_new_row)
        # combine_as_col = self.paint.EZFIG_panel.contextMenu.addAction("Combine Vertically (Col)")
        # combine_as_col.triggered.connect(self.combine_in_new_col)

    def assign_to_template(self, template, filenames_to_assign):
        # get it and clone it and replace it

        # print('filenames_to_assign',filenames_to_assign)

        template.filename = str(filenames_to_assign) if len(filenames_to_assign) > 1 else filenames_to_assign[
            0]  # this will work both for single and multiple images
        # print('template.filename', template.filename)
        # reloaded_image = clone_object(template)

        # I need replace template by reloaded image TODO --> then
        # maybe I could reinitialize the image with the parameters --> it would kind of be the same as calling init again except that some variables may persist but that would have the advantage of keeping the object in place and therefore simplifying everything --> worth trying

        props = template.to_dict()

        # print('props modified', props)

        # reloaded_image = clone_object(template) # weird --> clone also shows up as error --> see why
        # print('vs', reloaded_image.to_dict())
        # self.paint.EZFIG_panel.shapes_to_draw.append(reloaded_image)

        # props['filename']=
        # if 'template_rect' in props:
        #     props['template_rect']=None
        # template.__init__(*[str(filenames_to_assign)], **props) # we reinit in place the image -−> it is kinda the same as cloning but is simpler because I will not lose the position of the object
        template.__init__(
            **props)  # we reinit in place the image -−> it is kinda the same as cloning but is simpler because I will not lose the position of the object

        top_parent = self.paint.EZFIG_panel.get_top_parent_of_shape(template)

        if top_parent is not None:
            try:
                top_parent.update()
            except:
                pass
            self.update_size_of_object(top_parent)
            # set_to_width(top_parent, top_parent.size)

        # direct = Image2D(str(filenames_to_assign))

        # dict_diff(direct.to_dict(), template.to_dict(), verbose=True)

        self.paint.EZFIG_panel.update()
        self.paint.EZFIG_panel.update_size()

        # I probably need to update the parent --> TODO

        # TODO --> also need to arrange text and request focus

        # self.paint.EZFIG_panel.set_current_selection(template)
        # self.paint.EZFIG_panel.update_letters_required.emit()
        # self.paint.EZFIG_panel.focus_required.emit()
        self.paint.EZFIG_panel.update_text_rows.emit()
        self.paint.EZFIG_panel.undo_redo_save_required.emit()

    def all_images_directly(self, lst):
        if lst is not None:
            for elm in lst:
                self.paint.EZFIG_panel.shapes_to_draw.append(Image2D(elm))
                self.paint.EZFIG_panel.force_update_size_of_parent.emit(self.paint.EZFIG_panel.shapes_to_draw[-1])
            self.paint.EZFIG_panel.update()
            self.paint.EZFIG_panel.update_size()

            # TODO --> also need to arrange text and request focus

            self.paint.EZFIG_panel.set_current_selection(self.paint.EZFIG_panel.shapes_to_draw[-1])
            self.paint.EZFIG_panel.update_letters_required.emit()
            self.paint.EZFIG_panel.update_text_rows.emit()
            self.paint.EZFIG_panel.focus_required.emit()
            self.paint.EZFIG_panel.set_current_selection(self.paint.EZFIG_panel.shapes_to_draw[-1])
            self.paint.EZFIG_panel.undo_redo_save_required.emit()
            # rows =

    def create_panel(self, lst):
        # print('create Panel called --> ACTION REQUIRED')
        #
        # panel_dialog = PanelCreator(self, len(lst))
        # custom_dialog = CustomDialog(title="Panel or Row",
        #                              message=None,
        #                              # main_widget=main, options=['Ok', 'Cancel'], parent=self)
        #                              main_widget=panel_dialog, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)
        # if custom_dialog.exec_() == QDialog.Accepted:
        #     print(panel_dialog.get_values())
        # Create a QTimer instance
        timer = QTimer(self)
        timer.setSingleShot(True)  # Timer will fire only once
        timer.timeout.connect(lambda: self.paint.EZFIG_panel._create_panel_real(lst))
        timer.start(300)

        # else nothing to do

    def add_images_to_new_row(self, lst):
        self.paint.EZFIG_panel._add_as_new_group(lst, orientation='X', remove_from_parents=False)

    def add_images_to_new_col(self, lst):
        self.paint.EZFIG_panel._add_as_new_group(lst, orientation='Y', remove_from_parents=False)

    def eventFilter(self, obj, event):
        if obj == self.size_spinbox and event.type() == QEvent.KeyRelease:
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.spinBoxEnterPressed.emit()
                return True
        return super().eventFilter(obj, event)

    def on_size_spinbox_value_changed(self, value=None):
        """
        This slot is called when the value of the size_spinbox changes.
        """
        self.update_size_in_unit()
        # Restart the timer every time the value changes
        self.value_changed_timer.start()

    def save_state(self, show_popup=True):
        if self.undo_stack and self.current_index < len(self.undo_stack):
            # User is undoing or redoing, do not save the state
            return

        file_path = os.path.join(self.temp_dir.name, f"state_{self.counter}.xml")
        self.counter += 1
        self._save_state_to_file(file_path, popup='State Saved' if show_popup else None)

        # print('checks before', self.current_index, self.last_called_state, file_path, self.undo_stack, self.redo_stack)

        self.undo_stack = self.undo_stack[:self.current_index]
        if not self.last_called_state in self.undo_stack and not self.last_called_state is None:  # very hacky but somehow seems required
            self.undo_stack.append(self.last_called_state)
        self.undo_stack.append(file_path)
        self.current_index = len(self.undo_stack)  # Update the current index
        self.redo_stack = []

        # print('checks after', self.current_index, self.last_called_state, file_path, self.undo_stack, self.redo_stack)

        self.last_called_state = file_path

        self.update_button_state()

        return self.last_called_state

        # print('save state called', self.undo_stack)

    def undo(self):
        recall_required = False
        if self.undo_stack and 0 < self.current_index <= len(self.undo_stack):
            file_path = self.undo_stack[self.current_index - 1]

            if file_path == self.last_called_state:
                # print('duplicate action need call undo one more time to make sense')
                recall_required = True

            # print('entering undo',file_path)
            self.last_called_state = file_path
            # with open(file_path, "r") as f:
            #     self.text_edit.setPlainText(f.read())
            if not recall_required and file_path:
                self.reload_state(file_path, append=False)

            # self.redo_stack.append(self.undo_stack.pop())
            del self.undo_stack[self.current_index - 1]
            # self.redo_stack.insert(0, file_path)
            self.redo_stack.append(file_path)
            self.current_index -= 1
        self.update_button_state()

        if recall_required:
            self.undo()

    def select_all(self):
        if self.paint.EZFIG_panel.shapes_to_draw:
            self.paint.EZFIG_panel.selected_shape = list(self.paint.EZFIG_panel.shapes_to_draw)
            self.paint.EZFIG_panel.set_current_selection(self.paint.EZFIG_panel.selected_shape)
            self.paint.EZFIG_panel.update()
        else:
            self.paint.EZFIG_panel.selected_shape = None

    def redo(self):
        recall_required = False
        if self.redo_stack:
            file_path = self.redo_stack.pop()  # why pop ???

            if file_path == self.last_called_state:
                recall_required = True

            self.last_called_state = file_path
            self.undo_stack.append(file_path)
            self.current_index += 1
            if not recall_required and file_path:
                self.reload_state(file_path, append=False)
        self.update_button_state()
        if recall_required:
            self.redo()

    def reload_state(self, path_to_xml_file, append=True, skip_add_to_stack=False, warn_on_reload=False):
        if warn_on_reload:
            reply = QMessageBox.warning(self, 'Warning',
                                        'All unsaved changes will be lost. Are you sure you want to create a new file?',
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        if not path_to_xml_file:
            # offer an opening of a file and warn
            path_to_xml_file = openFileNameDialog(parent_window=self,
                                                  extensions="Supported Files (*.pyf);;All Files (*)")

            if path_to_xml_file:  # the user really wants to load another file --> reset undo redo
                if has_custom_script(read_string_from_file(path_to_xml_file)):
                    reply = QMessageBox.warning(self, 'Security Warning',
                                                '<span style="color: red;">The file contains custom script code. ' \
                                                'Opening this file may pose security risks, as it could execute untrusted or malicious code. ' \
                                                'Only proceed if you trust the source of the file and understand the implications.<br><br>' \
                                                'Do you REALLY want to continue?</span>',
                                                QMessageBox.Yes | QMessageBox.No)
                    if reply == QMessageBox.No:
                        return
                self.activate_or_reset_undo_redo()

        if path_to_xml_file:
            xml_string = read_string_from_file(path_to_xml_file)

            if os.path.exists(smart_name_parser(path_to_xml_file, 'full_no_ext') + '.files'):
                # replace all names in files with consolidated ones
                # we fix all filenames at launch
                xml_string = _update_filename_of_consolidated_files(path_to_xml_file, xml_string)

                # print(xml_string)

            properties = deserialize_to_dict(xml_string)
            # print(properties)
            objects = create_object(list.__name__, properties)

            for elm in reversed(objects):
                # if there is a font parameter in the xml --> we get it and remove it from the rest of the list
                if isinstance(elm, SerializableQFont):
                    self.serializable_font = elm
                    objects.remove(elm)
                if isinstance(elm, SerializableGUIparameters):
                    # we restore main GUI Y spacing and soon maybe other GUI parameters
                    self.main_space_spinner.blockSignals(True)
                    self.main_space_spinner.setValue(elm.space)
                    self.paint.EZFIG_panel.space = elm.space
                    self.main_space_spinner.blockSignals(False)
                    objects.remove(elm)

            if append:
                self.paint.EZFIG_panel.shapes_to_draw.extend(objects)
            else:
                self.paint.EZFIG_panel.shapes_to_draw = objects

            self.paint.EZFIG_panel.set_current_selection(
                None)  # need empty the selection because the chance that it works is limited
            self.arrange_text_rows()
            self.paint.EZFIG_panel.update_size()
            self.paint.EZFIG_panel.update()

            if not skip_add_to_stack:
                if not self.undo_stack:  # if there is no undo --> add one
                    self.save_state(show_popup=False)

    def update_button_state(self):
        self.undo_button.setEnabled(self.current_index > 0)
        self.redo_button.setEnabled(len(self.redo_stack) > 0)

    def closeEvent(self, event):
        try:
            # Close the ColorAssistant if it exists
            if self.color_assistant is not None:
                self.color_assistant.close()
        except:
            traceback.print_exc()

        self.temp_dir.cleanup()

        stop_JVM()

        event.accept()

    def arrange_text_rows(self):
        for iii, cur_sel in enumerate(self.paint.EZFIG_panel.shapes_to_draw):
            if cur_sel.isText:
                idx = self.paint.EZFIG_panel.shapes_to_draw.index(cur_sel)
                before = None
                after = None
                if idx != -1:
                    try:
                        before_idx = idx - 1
                        if before_idx >= 0:
                            before = self.paint.EZFIG_panel.shapes_to_draw[before_idx]
                    except:
                        before = None
                    try:
                        after_idx = idx + 1
                        if after_idx >= 0:
                            after = self.paint.EZFIG_panel.shapes_to_draw[after_idx]
                    except:
                        after = None

                group_to_fit_to = before
                if cur_sel.isText == 'below':
                    # TODO --> apply the parameters of the below things
                    group_to_fit_to = after

                if isinstance(cur_sel, Image2D):
                    cur_sel=[cur_sel]

                if group_to_fit_to:
                    try:
                        indices_of_all_shapes = [elm.annotations[0].range for elm in cur_sel]
                        overlap_detected = areIndicesOverlapping(indices_of_all_shapes)

                        if overlap_detected:
                            # MEGA TODO maybe if overlap is detected --> THEN --> reconvert to 0,1,2,3,4,5,6,7...
                            print('THERE IS AN OVERLAP BETWEEN YOUR IMAGES -−> THIS WILL CAUSE AN ERROR IN THE TEXT ALIGNMENTS')
                            raise Exception('not implemented yet')

                        # I should get rect corresponding to this
                        if isinstance(group_to_fit_to, Group):
                            # this is not a group --> nothing todo --> it can only be applied to groups
                            # return
                            bounding_rects_corresponding_to_indices = [group_to_fit_to.getCombinedBoundsAtIndices(rng) for
                                                                   rng in indices_of_all_shapes]
                        else:
                            # for single images
                            bounding_rects_corresponding_to_indices = [group_to_fit_to.getRect(all=True)]

                        for iii, elm_dest in enumerate(cur_sel):
                            try:
                                # elm_dest = cur_sel[iii]
                                elm_dest.setWidth(bounding_rects_corresponding_to_indices[iii].width())
                                # elm_dest.setHeight(elm_src.height(scale=True))
                                elm_dest.set_to_scale(1)
                            except:
                                # traceback.print_exc()
                                # print('not same size error, in theory I should remove all the extra texts of not plot them maybe -−> think of that --> cna I set width and height to None ???')
                                pass  # no big deal the guys can delete them if they don't need them anymore

                        if isinstance(cur_sel, Group):
                            try:
                                cur_sel.space=group_to_fit_to.space
                            except:
                                # TODO MAYBE CHECK THAT THIS IS OK NOW
                                cur_sel.space= 3
                            cur_sel.pack()


                        # finally I need to set it to parent width
                        # set_to_width(cur_sel, group_to_fit_to.width(scale=True))
                        if False:
                            for iii, elm in enumerate(cur_sel):
                                try:
                                    # elm.setHeight(max_h)
                                    print('final size', elm.getRect(), elm.getRect(all=True))
                                    elm_dest = group_to_fit_to[iii]
                                    print('final size src', elm_dest.getRect(), elm_dest.getRect(all=True))
                                except:
                                    pass  # no big deal if fails --> it is just because things are out of bounds
                    except:
                        traceback.print_exc()
                        print('error in sizing the label text row')
                #     continue
                # else:
                #     print('use default packing because parent not found')
        self.paint.EZFIG_panel.update_size()
        self.paint.EZFIG_panel.update()
        # do I need to save state I am not sure there and anyway this can be done anytime...

    # def arrange_text_rows_old(self):
    #     for iii,cur_sel in enumerate(self.paint.EZFIG_panel.shapes_to_draw):
    #         # this should be done after any other formatting of the figure
    #         if cur_sel.isText:
    #             idx = self.paint.EZFIG_panel.shapes_to_draw.index(cur_sel)
    #             # print('I am called with', cur_sel.isText, iii, idx)
    #             before = None
    #             after = None
    #             if idx != -1:
    #                 try:
    #                     before_idx = idx - 1
    #                     if before_idx >= 0:
    #                         before = self.paint.EZFIG_panel.shapes_to_draw[before_idx]
    #                 except:
    #                     before = None
    #                 try:
    #                     after_idx = idx + 1
    #                     if after_idx >= 0:
    #                         after = self.paint.EZFIG_panel.shapes_to_draw[after_idx]
    #                 except:
    #                     after = None
    #                 # print('before and after', before, after)
    #
    #             group_to_fit_to = before
    #             # group_to_fit_to = self.paint.EZFIG_panel.shapes_to_draw[2]
    #             if cur_sel.isText == 'below':
    #                 # TODO --> apply the parameters of the below things
    #                 group_to_fit_to = after
    #
    #             if group_to_fit_to:
    #                 try:
    #                     indices_of_all_shapes = [[0, 0], [1, 1],
    #                                              [2, 2]]  # now I really need to take this into account --> TODO
    #
    #                     overlap_detected = areIndicesOverlapping(indices_of_all_shapes)
    #
    #                     for iii, elm_src in enumerate(group_to_fit_to):
    #                         try:
    #                             elm_dest = cur_sel[iii]
    #                             elm_dest.setWidth(elm_src.width(all=True))
    #                             # elm_dest.setHeight(elm_src.height(scale=True))
    #                             elm_dest.set_to_scale(1)
    #                         except:
    #                             # traceback.print_exc()
    #                             # print('not same size error, in theory I should remove all the extra texts of not plot them maybe -−> think of that --> cna I set width and height to None ???')
    #                             pass # no big deal the guys can delete them if they don't need them anymore
    #                         # then do the same
    #                     cur_sel.pack()
    #
    #                     # finally I need to set it to parent width
    #                     # set_to_width(cur_sel, group_to_fit_to.width(scale=True))
    #                     if False:
    #                         for iii, elm in enumerate(cur_sel):
    #                             try:
    #                                 # elm.setHeight(max_h)
    #                                 print('final size', elm.getRect(), elm.getRect(all=True))
    #                                 elm_dest = group_to_fit_to[iii]
    #                                 print('final size src', elm_dest.getRect(), elm_dest.getRect(all=True))
    #                             except:
    #                                 pass  # no big deal if fails --> it is just because things are out of bounds
    #                 except:
    #                     traceback.print_exc()
    #                     print('error in sizing the label text row')
    #             #     continue
    #             # else:
    #             #     print('use default packing because parent not found')
    #     self.paint.EZFIG_panel.update_size()
    #     self.paint.EZFIG_panel.update()
    #     # do I need to save state I am not sure there and anyway this can be done anytime...

    def on_size_spinbox_value_changed_delayed(self):
        # print('spin box size changed called',self.sender())

        """
        This slot is called when the timer times out, delaying the execution of the code.
        """
        value = self.size_spinbox.value()

        # print(f"Size spinbox value changed: {value}")

        # if there is a selection --> then set its size to the desired value!!

        if self.paint.EZFIG_panel.selected_shape is None:
            # apply to all
            sel = self.paint.EZFIG_panel.shapes_to_draw
        else:
            if not isinstance(self.paint.EZFIG_panel.selected_shape, list):
                sel = [self.paint.EZFIG_panel.selected_shape]
            else:
                sel = self.paint.EZFIG_panel.selected_shape
        if sel:
            # may need to be done several times if nested text label rows
            for iii, cur_sel in enumerate(sel):
                self.update_size_of_object(cur_sel, value)

                # print('final SQJDKHQSKDJH', cur_sel.getRect(), cur_sel.getRect(all=True), cur_sel.scale, cur_sel.getAR())

            # print('update called ACTION REQUIRED TO MATCH TEXT TO BELOW OR ABOVE CONTENT −−> TODO --> NEED A SMART MOVE')

            self.arrange_text_rows()
            self.paint.EZFIG_panel.update()
            self.save_state(show_popup=True)
            # I need save the current state so that it can be undone (ideally I should check that smthg was really changed that would be better or somehow check that the saved files ae not the same )

    def combine_in_new_group(self, orientation='X'):
        if isinstance(self.paint.EZFIG_panel.selected_shape, list) and len(self.paint.EZFIG_panel.selected_shape) != 1:
            new_group = Group(*self.paint.EZFIG_panel.selected_shape, orientation=orientation)
            for elm in self.paint.EZFIG_panel.selected_shape:
                self.paint.EZFIG_panel.shapes_to_draw.remove(elm)
            # set_to_size(new_group, 512)
            self.paint.EZFIG_panel.selected_shape = None  # reset selection
            self.selectionUpdated()
            self.paint.EZFIG_panel.shapes_to_draw.append(new_group)
            self.paint.EZFIG_panel.update()
            # self.update()

    def combine_in_new_row(self):
        self.combine_in_new_group(orientation='X')

    def combine_in_new_col(self):
        self.combine_in_new_group(orientation='Y')

    def add_image(self):
        # TODO --> there is a bug with AVG_Rat_Hippocampal_Neuron.png -> why is that
        if self.list:
            main = PanelOrRow()
            custom_dialog = CustomDialog(title="Row Or Column",
                                         message=None,
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=main, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)
            if custom_dialog.exec_() == QDialog.Accepted:
                # print('add image --> TODO --> implement that --> ACTION REQUIRED')
                # if False:
                #     selected_files =  self.list.get_selection(mode='multi')
                # print('selection',selected_files)
                # remove sel -−> TODO
                # if selected_files is not None and selected_files:

                orientation, size, space = main.get_parameters()

                # self.list.removeSel()
                # I need ope the images or parse strings if they are there
                # group = Group(*selected_files,orientation='Y' if self.sender() == self.add_to_col else 'X')
                # group = Group(*self.list,orientation='Y' if self.sender() == self.add_to_col else 'X')
                # group = Group(*self.list, orientation=random.choice(['Y', 'X']))
                group = Group(*self.list, orientation=orientation, space=space, size=size)
                set_to_width(group, size)
                # print(group.getRect(scale=True))
                self.paint.EZFIG_panel.shapes_to_draw.append(group)
                self.paint.EZFIG_panel.update()  # this is required to show the update

    def raise_exception(self):
        try:
            raise Exception('NOT IMPLEMENTED YET −−> TODO')
        except:
            traceback.print_exc()

    def row_or_col_context_menu(self, menu=None):
        if menu is None:
            self.paint.EZFIG_panel.contextMenu = QMenu(self)
        else:
            self.paint.EZFIG_panel.contextMenu = menu
        ignore = self.paint.EZFIG_panel.contextMenu.addAction("Ignore")

        duplicate = self.paint.EZFIG_panel.contextMenu.addAction("Duplicate Selection")
        duplicate.triggered.connect(self.paint.EZFIG_panel.duplicate)

        combine_as_row = self.paint.EZFIG_panel.contextMenu.addAction("Combine Horizontally (Row)")
        combine_as_row.triggered.connect(self.combine_in_new_row)
        combine_as_col = self.paint.EZFIG_panel.contextMenu.addAction("Combine Vertically (Col)")
        combine_as_col.triggered.connect(self.combine_in_new_col)

    def row_or_col_assembly_widget(self):
        self.row_or_col_assembly = QWidget()
        vbox = QVBoxLayout()
        vbox.setAlignment(Qt.AlignTop)

        # maybe also add it to the right click --> TODO
        self.add_to_row = QPushButton('row')
        self.add_to_row.setIcon(qta.icon('ri.layout-row-line'))
        self.add_to_row.setToolTip("add selection as a row")
        # self.add_to_row.clicked.connect(self.add_image)
        self.add_to_row.clicked.connect(self.combine_in_new_row)

        self.add_to_col = QPushButton('column')
        self.add_to_col.setToolTip("add selection as a column")
        self.add_to_col.setIcon(qta.icon('ri.layout-column-line'))
        # self.add_to_col.clicked.connect(self.add_image)
        self.add_to_col.clicked.connect(self.combine_in_new_col)

        vbox.addWidget(self.add_to_row)
        vbox.addWidget(self.add_to_col)

        self.row_or_col_assembly.setLayout(vbox)

    def set_html_red(self, text):
        # quick n dirty log coloring --> improve when I have time
        textCursor = self.logger_console.textCursor()
        textCursor.movePosition(QTextCursor.End)
        self.logger_console.setTextCursor(textCursor)
        format = QTextCharFormat()
        format.setForeground(QColor(255, 0, 0))  # red
        self.logger_console.setCurrentCharFormat(format)
        self.logger_console.insertPlainText(text)
        self.logger_console.verticalScrollBar().setValue(self.logger_console.verticalScrollBar().maximum())

    def set_html_black(self, text):
        # quick n dirty log coloring --> improve when I have time
        textCursor = self.logger_console.textCursor()
        textCursor.movePosition(QTextCursor.End)
        self.logger_console.setTextCursor(textCursor)
        format = QTextCharFormat()
        format.setForeground(QColor(0, 0, 0))  # black
        self.logger_console.setCurrentCharFormat(format)
        self.logger_console.insertPlainText(text)

    def _save_state_to_file(self, file, popup=None):
        neo_list = list(self.paint.EZFIG_panel.shapes_to_draw)
        neo_list.append(self.serializable_font)
        neo_list.append(SerializableGUIparameters(space=self.main_space_spinner.value()))# add GUI parameters
        xml_string = object_to_xml(neo_list, is_list=True)
        write_string_to_file(file, xml_string)
        if popup:
            self.show_popup(popup)

    def new_fig(self):
        reply = QMessageBox.warning(self, 'Warning',
                                    'All unsaved changes will be lost. Are you sure you want to create a new file?',
                                    QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.activate_or_reset_undo_redo()
            self.paint.EZFIG_panel.shapes_to_draw = []
            self.paint.EZFIG_panel.set_current_selection(None)
            self.paint.EZFIG_panel.update_size()
            self.paint.EZFIG_panel.update()

    def update_letters(self):
        letter = self.letter_line_edit.text()
        shall_add_letter = self.auto_lettering_checkbox.isChecked() and letter
        # TODO prevent dupes and see why it does not get the virtual ones
        _, all_images = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(
            exclude_images_without_filename=False, include_insets=False)
        # maybe need further remove the other stuff

        # Try to edit all the elements by adding a letter to them before updating them -−> TODO
        for elm in all_images:
            # list all image except insets
            # and add to each of them a letter --> should be easy in fact
            # TODO --> A FAIRE
            if elm.isText:  # do not label again text labels
                continue
            # if the stuff contains others then delete them
            if elm.annotations:
                for l in reversed(elm.annotations):
                    if isinstance(l, TAText2D) and l.is_letter:
                        elm.annotations.remove(l)
            if shall_add_letter:
                txt_to_add = self.serializable_font.get_TaText2D_with_font(letter)
                elm.annotations.insert(0, txt_to_add)
                letter = increment_letter(letter)

    # def remove_all_annotations(self):
    #     print('remove all annotations called')
    #     self.paint.EZFIG_panel.remove_all_annotations()


    def change_lettering_parameters(self):
        main = AutoLetteringOptions()

        custom_dialog = CustomDialog(title="Auto lettering",
                                     message=None,
                                     main_widget=main, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)

        if custom_dialog.exec_() == QDialog.Accepted:
            self.serializable_font = main.get_serializable_font()
            self.paint.EZFIG_panel.update()
            self.save_state(show_popup=True)

    def save_and_consolidate(self):
        # TODO add a warning/warnings not to mix and or pick files manually
        # TODO ask for a file out for consolidation

        output_filename = saveFileDialog(parent_window=self,
                                         extensions="Supported Files (*.pyf);;All Files (*)",
                                         default_ext='.pyf')
        if output_filename:

            # this is the consolidation code first attempt
            full_list_of_filenames_to_consolidate, full_list_of_images = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation()
            # print('full list of images', full_list_of_images)
            # print('len', len(full_list_of_images))
            # print('full_list_of_filenames_to_consolidate', full_list_of_filenames_to_consolidate)
            # print('len2', len(full_list_of_filenames_to_consolidate))
            # now print the consolidated files and the expected filenames

            save_output_folder = smart_name_parser(output_filename, 'TA') + '.files'

            # full_list_of_filenames_to_consolidate, consolidated_file_list = smartly_consolidate_files_to_reduce_dupes(full_list_of_filenames_to_consolidate,'mock_folder.files')
            full_list_of_filenames_to_consolidate, consolidated_file_list = smartly_consolidate_files_to_reduce_dupes(
                full_list_of_filenames_to_consolidate, save_output_folder)
            # print('debug1', len(full_list_of_filenames_to_consolidate) == len(consolidated_file_list))
            # print('debug2', len(full_list_of_filenames_to_consolidate), len(consolidated_file_list))

            # for f1, f2 in zip(full_list_of_filenames_to_consolidate, consolidated_file_list):
            #     print(f1, '->', f2)

            consolidate_files2(save_output_folder, full_list_of_filenames_to_consolidate, consolidated_file_list)

            # clone all and save it as a .pyf file

            # save all
            self._save_state_to_file(output_filename)
            self.reload_state(output_filename, append=False, skip_add_to_stack=True)

            self.activate_or_reset_undo_redo()

            # now list all images again and replace the names in the files by the consolidated version and then save it again with same name

            _, full_list_of_images = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation()

            for elm in full_list_of_images:
                elm.consolidate_names(full_list_of_filenames_to_consolidate, consolidated_file_list)
                # proceed to replacement directly within the file

            self._save_state_to_file(output_filename)

    def templatify_figure(self):  # , stuff_to_consolidate=None

        # code is a bit redundant with code in self.paint.EZFIG_panel.templatify but the code below is most likely faster for big figs... --> see if I should dedup the code some day ???

        # if stuff_to_consolidate == False:
        #     stuff_to_consolidate = None
        # print('stuff_to_consolidate', stuff_to_consolidate)

        # trying to templatify all
        # --> just remove all the filenames and keep all the rest --> that should do it
        # --> maybe offer remove all annotations and or letters in a single click

        # maybe warn
        # how can I save as a template vs an error -−> maybe put @template@ as the name -> then I know it is a template --> smart idea
        # if template --> set it to orange and if DND on it then add it to the image below -> can be done rapidly

        # also allow multiple files

        # keep all but templates --> read all images (it may be tricky for insets) -−> can I edit and

        self.current_file = None  # we reset the current file to avoid accidentally overriding a figure
        _, full_list_of_images = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(
            include_insets=False)  # stuff_to_consolidate=stuff_to_consolidate,

        for img in full_list_of_images:
            # DEV NOT KEEP for all the images convert image to rect --> this is mandatory to avoid weird issues with templates
            if img.filename is None:
                continue
            else:
                rect = img.getRect(raw=True)
                img.img = QRectF(0, 0, rect.width(), rect.height())

        # I should probably remove all the insets from images
        for img in full_list_of_images:
            # we remove insets as I can't think of an easy way of recreating it dynamically??? except maybe if I store the rect along with the image --> or if I assign a crop variable to rects that need do crops
            if img.annotations:
                for elm in reversed(img.annotations):
                    if isinstance(elm, Image2D):
                        img.annotations.remove(elm)

        file_to_hack = self.save_state(show_popup=False)

        _replace_filename_tags(file_to_hack)

        # _remove_insets(file_to_hack) # DOES NOT WORK

        self.reload_state(file_to_hack, append=False, skip_add_to_stack=True)  # see if

        # for img in full_list_of_images:
        #     # old_name=img.filename
        #     img.filename='@template@'
        #     copy = clone_object(img)
        #     # img.filename=old_name
        #
        #     print('TODO replace parent image by clone')

        # a much simpler stuff wrould be to replace all the filename tags in a save state by '@template@' and then to realod it --> so much simpler than to update each and every image -> TODO

        # just save the file and get it -−> TODO

        # self.save_state(show_popup=False)
        # recover the last saved file from the stack and replace all the filename tags by the desired values then just resave the file exactly as it is and reload it --> TODO

        # then I need to replace all --> TODO
        # see how to code the replacement

        # I probably need to clone all

        self.paint.EZFIG_panel.update()
        self.paint.EZFIG_panel.update_size()

            # print('found AR', AR)
            # print('end debugging same AR')
        # try to force all images to that now

    def tst_function(self):

        # if True:
        #     pzfconfig.path_to_last_consolidated_file = random.random()
        #     print('last consolidated path', pzfconfig.path_to_last_consolidated_file)
        #     return

        self._debug_check_of_shapes()

        if False:
            self.same_width_and_height()
            return

        if True:
            self.same_AR_as_first()
            return

        if False:  # this should not be useful again -−> so maybe I can remove that at some point
            # manual correction of translation error until autoreg is up and running
            main = ExtraTranslationWidget()

            custom_dialog = CustomDialog(title="manual_correction",
                                         message=None,
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=main, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)

            if custom_dialog.exec_() == QDialog.Accepted:
                # self.serializable_font = main.get_serializable_font()
                # self.paint.EZFIG_panel.update()
                # self.save_state(show_popup=True)
                # self.paint.EZFIG_panel.shapes_to_draw[0].content[0].extra_user_translation = main.get_translation()
                try:
                    scale = self.paint.EZFIG_panel.selected_shape.scale
                    translation = main.get_translation()
                    self.paint.EZFIG_panel.selected_shape.extra_user_translation = (
                    translation[0] * scale, translation[1] * scale)  # le pb est que ce truc depend de la scale
                except:
                    traceback.print_exc()

                self.paint.EZFIG_panel.update()
            return

        if False:
            self.save_and_consolidate()

            # that should be done

            # now I need to clone all and then change names in all the clones and set this as the new image

            # the last thing I need to do is reinject all of these in the clones

    def _debug_check_of_shapes(self):

        # c'est bon
        print(self.undo_stack)
        print(self.redo_stack)

        if self.paint.EZFIG_panel.selected_shape is not None and not isinstance(self.paint.EZFIG_panel.selected_shape, list):
            print('sel shape', self.paint.EZFIG_panel.selected_shape)
            print('type', type(self.paint.EZFIG_panel.selected_shape))
            try:
                print('size',self.paint.EZFIG_panel.selected_shape.get_raw_size())
            except:
                pass
            try:
                print('getRect', self.paint.EZFIG_panel.selected_shape.getRect())
                print('getRect scale=True', self.paint.EZFIG_panel.selected_shape.getRect(scale=True))
                print('getRect all=True', self.paint.EZFIG_panel.selected_shape.getRect(all=True))
            except:
                pass
            try:
                print('shape size', self.paint.EZFIG_panel.selected_shape.size)
            except:
                pass
        else:
            for shape in self.paint.EZFIG_panel.shapes_to_draw:
                print('sel shape', shape)
                print('type', type(shape))
                print('getRect', shape.getRect())
                try:
                    print('getRect scale=True', shape.getRect(scale=True))
                    print('getRect all=True', shape.getRect(all=True))
                except:
                    pass
                try:
                    print('shape size', shape.size)
                except:
                    pass

    def save_pyfigures(self, file='auto'):
        # print('SAVING AS PZF CALLED')

        if file == 'auto' or file is False:
            file = self.current_file

        success = False
        if not file:
            # file = saveFileDialog(parent_window=self, extensions="Supported Files (*.pyf);;All Files (*)",
            file = saveFileDialog(parent_window=self, extensions="Supported Files (*.pyf);;All Files (*)",
                                  default_ext='.pyf')
            if file:
                self.current_file = file
                success = True
        else:
            success = True

        if self.current_file and success:
            self._save_state_to_file(self.current_file, popup=f'{self.current_file} Saved')

    def export_as_svg(self):
        output_file = saveFileDialog(parent_window=self, extensions="Supported Files (*.svg);;All Files (*)",
                                     default_ext='.svg')
        self._save(output_file)

    def export_as_pdf(self):
        output_file = saveFileDialog(parent_window=self, extensions="Supported Files (*.pdf);;All Files (*)",
                                     default_ext='.pdf')
        self._save(output_file)

    # could do export as raster and handle the stuff
    def export_as_tif(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="Supported Files (*.tif *.jpg *.png);;All Files (*)",
                                     default_ext='.tif')
        self._save(output_file)

    def _save(self, output_file):
        if output_file is not None:
            self.paint.EZFIG_panel.save(output_file)


if __name__ == '__main__':

    # with jvm_context():
        # vraiment pas mal --> j'y suis presque...
        import sys
        start_JVM()

        app = QApplication(sys.argv)
        w = EZFIG_GUI()
        demo = True

        if False:
            import skimage

            f = '/E/Sample_images/sample_images_FIJI/blobs.png'
            img = skimage.io.imread(f)  # why is that
            print('**', img.shape)
            img = skimage.io.imread('/E/Sample_images/sample_images_PA/test.png')
            print('**2', img.shape)

            # fix is there !!!
            import imageio
            from skimage.io._plugins import imageio_plugin

            print('***', imageio_plugin.imread(f).shape)  # wrong order
            print('***', imageio.v2.imread(f).shape)  # order ok --> but do I wanna change my code ?
            f = '/E/Sample_images/sample_images_PA/test.png'
            print('***', imageio_plugin.imread(f).shape)  # wrong order
            print('***', imageio.v2.imread(f).shape)  # order ok --> but do I wanna change my code ?

            img = Img(f)  # it does not work because it is channel first --> need a squeeze to only keep the relevant dims
            print(img.metadata['dimensions'])  # --> it returns hwc whereas it is chw -->  which makes no sense
            img = np.squeeze(img)  #
            print(img.shape)
            img = Img('/E/Sample_images/sample_images_FIJI/first-instar-brain.tif')
            print(img.metadata['dimensions'])
            print(img.shape)

        if demo:
            # w.paint.EZFIG_panel.shapes_to_draw = tst_stacks_n_sizes()
            w.paint.EZFIG_panel.shapes_to_draw = channel_n_lut_test()
            # w.paint.EZFIG_panel.shapes_to_draw = mega_image_tst()
            # w.paint.EZFIG_panel.shapes_to_draw = tst_scale_bar()
            # w.paint.EZFIG_panel.shapes_to_draw = tst_empties_and_templates()
            # w.paint.EZFIG_panel.shapes_to_draw = mini_figure()
            # w.paint.EZFIG_panel.shapes_to_draw = mini_figure(single=True)
            # w.paint.EZFIG_panel.shapes_to_draw = mini_tst_svg_rotation()
            # w.paint.EZFIG_panel.shapes_to_draw = mini_tst_svg_rotation(single=True, rotation=0)
            # w.paint.EZFIG_panel.shapes_to_draw = mini_tst_svg_rotation(single=False, rotation=0)
            # w.paint.EZFIG_panel.shapes_to_draw = mini_tst_svg_rotation(single=2, rotation=0)
            # w.paint.EZFIG_panel.shapes_to_draw = mini_tst_svg_rotation(single=False, rotation=45)
            # w.paint.EZFIG_panel.shapes_to_draw = mini_tst_svg_rotation(single=False, rotation=45)

            # w.paint.EZFIG_panel.shapes_to_draw = [mini_test(return_image_directly=True)]
            # w.paint.EZFIG_panel.shapes_to_draw = mini_test(return_image_directly=False)

            # w.save_state(show_popup=False)
            w.on_size_spinbox_value_changed_delayed()

            # w.list.add_to_list(['/E/Sample_images/sample_images_FIJI/AuPbSn40.jpg', '/E/Sample_images/sample_images_FIJI/Cell_Colony.jpg', '/E/Sample_images/sample_images_FIJI/colocsample1bRGB_BG.tif'], check_if_supported=False)
            if False:
                w.list.add_to_list(
                    ['/E/Sample_images/sample_images_FIJI/blobs.png', '/E/Sample_images/sample_images_FIJI/AuPbSn40.jpg',
                     '/E/Sample_images/sample_images_FIJI/Cell_Colony.jpg',
                     '/E/Sample_images/sample_images_FIJI/colocsample1bRGB_BG.tif',
                     '/E/Sample_images/sample_images_FIJI/first-instar-brain.tif'], check_if_supported=False)

            # --> all is ok !!!
            # ça marche --> tt marche --> voir comment faire la suite

        # w.setWindowIcon(app_icon)

        # NB il y a des bugs d'elements qui sont à droite --> petit pb d'alignement --> probablement un pb
        # faire toujours fitter le plot à sa taille --> TODO

        w.show()
        sys.exit(app.exec_())
