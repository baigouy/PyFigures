# all good now really start to use and finalize this tool once for good, because it could be very useful to the community for handling scientific figures...
# add a lot of tests to be sure all is now working and see if there can be speed imporvments made to it especially with graphs...

from batoolset.settings.global_settings import set_UI  # set the UI to qtpy
set_UI()
from batoolset.images.centralstore import ImageCentralStore
import time
from batoolset.drawings.shapes.serializableguiparams import SerializableGUIparameters
# import filecmp # TODO use that to avoid duplicating a save in undo/redo --> future dev, not urgent
from pyfigures.gui.colorassistant import ColorAssistant
from pyfigures.path_resolution import resolve_moved_paths
from pyfigures.gui.panelcreationwidget import PanelCreator
from batoolset.dims.tools import pixels_to_cm, pixels_to_inch
from pyfigures.gui.pagelimitswidget import PageLimitsWidget
from pyfigures.gui.tipdialog import TipDialog
from datetime import datetime
from pyfigures.gui.about_dialog_pzf import AboutDialog
from batoolset.icons.tools import get_icon
from batoolset.dicts.tools import dict_diff
from batoolset.files.tools import smart_name_parser
from pyfigures.gui.keep_tst_images_for_pzf import mega_image_tst, mini_test, mini_tst_svg_rotation, \
    mini_figure, tst_stacks_n_sizes, tst_empties_and_templates, tst_scale_bar, channel_n_lut_test
# import pzfconfig  # path to the consolidated file and variables shared throughout the software
from batoolset.xmls.tools import _replace_filename_tags, _update_filename_of_consolidated_files  # , _remove_insets
from pyfigures.gui.user_extra_translation import ExtraTranslationWidget
from batoolset.strings.tools import increment_letter
from pyfigures.gui.autolettering_widget import AutoLetteringOptions
from batoolset.drawings.shapes.Position import Position
from batoolset.drawings.shapes.serializablefont import SerializableQFont
from batoolset.lists.tools import find_all_objects_of_type, find_first_index, find_first_object_of_type, \
    divide_list_into_sublists, compare_lists_sets
from batoolset.pyqts.tools import get_html_text_with_font, get_shape_after_rotation_and_crop, getCtrlModifierAsString
import os
from batoolset.files.tools import write_string_to_file, read_string_from_file, consolidate_files, \
    smartly_consolidate_files_to_reduce_dupes, consolidate_files2
from batoolset.serializations.tools import deserialize_to_dict, has_custom_script, clone_object
from batoolset.serializations.tools import clone_object, object_to_xml, create_object
from pyfigures.gui.emptyimagedialog import EmptyImageParametersWidget
from batoolset.GUI.customdialog import CustomDialog
from batoolset.drawings.shapes.group import Group, set_to_size, set_to_width, set_to_height, set_to_width_im2d, \
    set_to_height_im2d, areIndicesOverlapping
from pyfigures.gui.group_builder_GUI import PanelOrRow
from batoolset.drawings.shapes.rectangle2d import Rectangle2D
from batoolset.img import Img, guess_dimensions, get_series_info, is_forbidden_image_file, list_image_files_in_folder, \
    is_image_file
import traceback
from qtpy.QtGui import QColor, QTextCursor, QTextCharFormat, QKeySequence, QTransform, QDesktopServices, \
    QIcon, QPixmap
from qtpy.QtWidgets import QApplication, QStackedWidget, QWidget, QTabWidget, QScrollArea, QVBoxLayout, QPushButton, \
    QGridLayout, QTextBrowser, QFrame, QProgressBar, QGroupBox, QAction, QDialog, QDockWidget, QLabel, QMenu, QShortcut, \
    QCheckBox, QSpinBox, QMainWindow, QToolBar, QComboBox, QMenuBar, QMessageBox, QLineEdit, QInputDialog, \
    QDoubleSpinBox, QTextEdit, QToolButton, QColorDialog
from qtpy.QtCore import Signal, QEvent, Qt, QRect, QRectF, QTimer,QObject,QPoint, QPointF,QThread,Slot,QRunnable,QThreadPool, QUrl
import qtawesome as qta
import logging
import numpy as np
import matplotlib.pyplot as plt
from batoolset.dialogs.opensave import saveFileDialog, openFileNameDialog, openFileNamesDialog
from batoolset.drawings.shapes.circle2d import Circle2D
from batoolset.drawings.shapes.ellipse2d import Ellipse2D
from batoolset.drawings.shapes.freehand2d import Freehand2D
from batoolset.drawings.shapes.image2d import Image2D
from batoolset.drawings.shapes.line2d import Line2D
from batoolset.drawings.shapes.point2d import Point2D
from batoolset.drawings.shapes.polygon2d import Polygon2D
from batoolset.drawings.shapes.polyline2d import PolyLine2D
from batoolset.drawings.shapes.scalebar import ScaleBar
from batoolset.drawings.shapes.square2d import Square2D
from batoolset.drawings.shapes.txt2d import TAText2D
from pyfigures.gui.scrollableEZFIG import scrollable_EZFIG
from batoolset.tools.qthandler import XStream, QtHandler
from batoolset.uis.blinker import Blinker
from batoolset.GUI.overlay_hints import Overlay
import atexit
import tempfile
from batoolset.tools.logger import TA_logger  # logging
from pyfigures.version import __VERSION__,__EMAIL__,__AUTHOR__, __URL__, __DESCRIPTION__, __NAME__, __SHORT__NAME__

# DEBUG = False
DEBUG = True # keep it like this because otherwise this redirects output --> in fact I need to edit my code to avoid redirections !!!

logger = TA_logger()

# class WorkerSignals(QObject):
#     finished = Signal()
#     result = Signal(object)
#
#
# class Worker(QRunnable):
#     finished = Signal()
#     result_ready = Signal(object)  # Signal to send the result back to the main thread
#
#     def __init__(self, func, *args, **kwargs):
#         super(Worker, self).__init__()
#         # super().__init__()
#         self.func = func
#         self.args = args
#         self.kwargs = kwargs
#         self.signals = WorkerSignals()
#
#     @Slot()
#     def run(self):
#
#         result=None
#         try:
#             if self.args and self.kwargs:
#                 result = self.func(*self.args, **self.kwargs)
#             elif self.args:
#                 print('self.args passed', self.args)
#                 result = self.func(*self.args)
#             else:
#                 result = self.func()
#             # self.result_ready.emit(result)
#         finally:
#             # self.finished.emit()
#             self.signals.result.emit(result)
#             self.signals.finished.emit()
#
#     # def on_task_finished(self, result):
#     #     self.label.setText(f"Status: {result}")
#     #     self.worker_thread.quit()
#     #     self.worker_thread.wait()

def cleanup_temp_dir(temp_dir):
    try:
        # print('cleaning up temp dir')
        temp_dir.cleanup()
    except Exception as e:
        print(f"Error cleaning up temporary directory: {e}")


class _PyfLoaderWorker(QObject):
    """Worker that reads and parses .pyf files off the main thread."""
    file_ready = Signal(str, object, bool)  # path, objects (or None if has_script), has_script
    file_error = Signal(str, str)           # path, error_message
    paths_relocated = Signal(str, int)      # path, number of source files found at a new location
    finished = Signal()

    def __init__(self, files, parent=None):
        super().__init__(parent)
        self.files = files
        self._cancelled = False

    def cancel(self):
        """Stop after the file being read (thread-safe flag)."""
        self._cancelled = True

    @Slot()
    def run(self):
        for path in self.files:
            if self._cancelled:
                break
            try:
                xml_string = read_string_from_file(path)
                if os.path.exists(smart_name_parser(path, 'full_no_ext') + '.files'):
                    xml_string = _update_filename_of_consolidated_files(path, xml_string)
                # figure moved to another folder / disk / OS: find its source files
                # relative to where the .pyf is now
                xml_string, moved = resolve_moved_paths(xml_string, path)
                if moved:
                    self.paths_relocated.emit(path, len(moved))
                if has_custom_script(xml_string):
                    # Ship the raw xml: building the objects executes the custom
                    # scripts, so for scripted files that must only happen after the
                    # user approved the security prompt (on the main thread).
                    # (Plain field values are parsed with safe_literal_eval, which
                    # never executes code.)
                    self.file_ready.emit(path, xml_string, True)
                else:
                    # Only deserialize to dict here; create_object() stays on the main
                    # thread because it builds Qt objects (and runs panel scripts).
                    # Pixel loading happens later on _ImgLoaderWorker threads; Fiji /
                    # Bio-Formats reads there are serialised by ij_reader.ij_lock.
                    properties = deserialize_to_dict(xml_string)
                    self.file_ready.emit(path, properties, False)
            except Exception as e:
                self.file_error.emit(path, str(e))
        self.finished.emit()


def _qt_alive(obj):
    """False once the C++ side of a Qt wrapper has been destroyed — a queued
    loader callback arriving after its window was deleted must not touch it
    (that was an access violation, not a Python exception)."""
    try:
        try:
            from PyQt6 import sip
        except ImportError:
            import sip
        return not sip.isdeleted(obj)
    except Exception:
        try:
            obj.objectName()
            return True
        except RuntimeError:
            return False


class _ImgLoaderWorker(QObject):
    """Loads Img pixel data for a list of file paths in a background thread.
    Results are stored directly in *results* dict to avoid Qt signal serialization
    stripping the Img numpy-subclass back to a plain ndarray (which loses metadata
    and breaks get_width()/get_height()).

    Optional *series_map* maps path -> serie_to_open (int) for multi-series files."""
    img_ready = Signal(str)   # path only — Img already written to self._results
    finished = Signal()

    def __init__(self, paths, results, series_map=None, parent=None):
        super().__init__(parent)
        self._paths = paths
        self._results = results   # dict: path -> Img or None, owned by caller
        self._series_map = series_map or {}
        self._cancelled = False

    def cancel(self):
        """Stop after the image being read (thread-safe flag)."""
        self._cancelled = True

    @Slot()
    def run(self):
        for path in self._paths:
            if self._cancelled:
                break
            try:
                from batoolset.drawings.shapes.image2d import is_vector_file
                if is_vector_file(path):
                    img = None        # SVG / PDF panels: Image2D draws the file itself
                else:
                    serie = self._series_map.get(path)
                    img = Img(path, serie_to_open=serie)
            except Exception:
                img = None
            self._results[path] = img   # write before signalling
            self.img_ready.emit(path)
        self.finished.emit()


class _ColourBarDialog(QFrame):
    """Small form to configure a LUT intensity calibration bar (colour bar).

    A QFrame (not a bare QWidget) is used as the container on purpose — a plain
    QWidget container can crash PyQt6 with 0xC0000409.
    """

    # A short, curated menu of common LUTs; the combo is editable so any LUT
    # name accepted by set_lut (all 227) can be typed in as well.
    _COMMON_LUTS = [
        "GRAY", "RED", "GREEN", "BLUE", "YELLOW", "CYAN", "MAGENTA", "ORANGE",
        "AFM_HOT", "RED_HOT", "GREEN_HOT", "BLUE_HOT", "RAINBOW_1",
        "MATPLOTLIB_viridis", "MATPLOTLIB_plasma", "MATPLOTLIB_inferno",
        "MATPLOTLIB_magma", "MATPLOTLIB_jet", "MATPLOTLIB_turbo",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        r = 0

        self.lut_combo = QComboBox(self)
        self.lut_combo.setEditable(True)
        self.lut_combo.addItems(self._COMMON_LUTS)
        grid.addWidget(QLabel("LUT:", self), r, 0)
        grid.addWidget(self.lut_combo, r, 1); r += 1

        self.vmin_edit = QLineEdit("0", self)
        grid.addWidget(QLabel("Min value:", self), r, 0)
        grid.addWidget(self.vmin_edit, r, 1); r += 1

        self.vmax_edit = QLineEdit("255", self)
        grid.addWidget(QLabel("Max value:", self), r, 0)
        grid.addWidget(self.vmax_edit, r, 1); r += 1

        self.label_edit = QLineEdit("", self)
        self.label_edit.setPlaceholderText("e.g. Intensity (a.u.)")
        grid.addWidget(QLabel("Axis label:", self), r, 0)
        grid.addWidget(self.label_edit, r, 1); r += 1

        self.orientation_combo = QComboBox(self)
        self.orientation_combo.addItems(["vertical", "horizontal"])
        grid.addWidget(QLabel("Orientation:", self), r, 0)
        grid.addWidget(self.orientation_combo, r, 1); r += 1

        self.ticks_edit = QLineEdit("", self)
        self.ticks_edit.setPlaceholderText("optional, e.g. 0, 128, 255")
        grid.addWidget(QLabel("Ticks:", self), r, 0)
        grid.addWidget(self.ticks_edit, r, 1); r += 1

        self.tick_labels_edit = QLineEdit("", self)
        self.tick_labels_edit.setPlaceholderText("optional, e.g. low, , high")
        grid.addWidget(QLabel("Tick labels:", self), r, 0)
        grid.addWidget(self.tick_labels_edit, r, 1); r += 1

    def values(self) -> dict:
        """Parse the form into build_calibration_bar_script() kwargs.

        Raises ValueError with a friendly message on bad input.
        """
        lut = self.lut_combo.currentText().strip()
        if not lut:
            raise ValueError("Please choose a LUT.")
        try:
            vmin = float(self.vmin_edit.text())
            vmax = float(self.vmax_edit.text())
        except ValueError:
            raise ValueError("Min and Max must be numbers.")

        def _split(text):
            return [p.strip() for p in text.split(",")] if text.strip() else None

        ticks_raw = _split(self.ticks_edit.text())
        ticks = None
        if ticks_raw is not None:
            try:
                ticks = [float(t) for t in ticks_raw]
            except ValueError:
                raise ValueError("Ticks must be a comma-separated list of numbers.")

        tick_labels = _split(self.tick_labels_edit.text())
        if tick_labels is not None and ticks is not None and \
                len(tick_labels) != len(ticks):
            raise ValueError("Tick labels must match the number of ticks.")

        return {
            "lut": lut, "vmin": vmin, "vmax": vmax,
            "label": self.label_edit.text().strip(),
            "orientation": self.orientation_combo.currentText(),
            "ticks": ticks, "tick_labels": tick_labels,
        }


class _JournalDialog(QFrame):
    """Pick a journal (or a custom column width) + options for the journal
    compliance / apply-guidelines / resolution tools."""

    from pyfigures.mcp_tools.core import _JOURNAL_PRESETS
    _JOURNALS = list(_JOURNAL_PRESETS)
    del _JOURNAL_PRESETS

    def __init__(self, parent=None, with_apply_options=False):
        super().__init__(parent)
        grid = QGridLayout(self)
        r = 0

        self.journal_combo = QComboBox(self)
        self.journal_combo.addItem("(custom width)")
        self.journal_combo.addItems(self._JOURNALS)
        self.journal_combo.setCurrentText("nature")
        grid.addWidget(QLabel("Journal:", self), r, 0)
        grid.addWidget(self.journal_combo, r, 1); r += 1

        self.column_combo = QComboBox(self)
        self.column_combo.addItems(["single", "1.5", "double"])
        grid.addWidget(QLabel("Column:", self), r, 0)
        grid.addWidget(self.column_combo, r, 1); r += 1

        self.width_mm_edit = QLineEdit("", self)
        self.width_mm_edit.setPlaceholderText("only if journal = custom, e.g. 85")
        grid.addWidget(QLabel("Custom width (mm):", self), r, 0)
        grid.addWidget(self.width_mm_edit, r, 1); r += 1
        self._select_stored_target(getattr(parent, 'current_file', None))

        self.min_dpi_edit = QLineEdit("300", self)
        grid.addWidget(QLabel("Min DPI:", self), r, 0)
        grid.addWidget(self.min_dpi_edit, r, 1); r += 1

        self.min_font_edit = QLineEdit("7", self)
        grid.addWidget(QLabel("Min font (pt):", self), r, 0)
        grid.addWidget(self.min_font_edit, r, 1); r += 1

        self.with_apply_options = with_apply_options
        if with_apply_options:
            self.panel_labels_check = QCheckBox("Add panel letters (a, b, c…)", self)
            grid.addWidget(self.panel_labels_check, r, 0, 1, 2); r += 1

    def _select_stored_target(self, pyf_path):
        """Open on the target the figure was last sized for (journal + column,
        or a custom width), as the MCP checks do."""
        if not pyf_path:
            return
        from pyfigures.mcp_tools.core import _stored_target
        target = _stored_target(pyf_path)
        if not target:
            return
        if target.get("journal") in self._JOURNALS:
            self.journal_combo.setCurrentText(target["journal"])
            self.column_combo.setCurrentText(str(target.get("column", "single")))
        else:
            self.journal_combo.setCurrentText("(custom width)")
            self.width_mm_edit.setText(f"{float(target['width_mm']):g}")

    def values(self) -> dict:
        journal = self.journal_combo.currentText()
        out = {"column": self.column_combo.currentText()}
        if journal == "(custom width)":
            txt = self.width_mm_edit.text().strip()
            if not txt:
                raise ValueError("Enter a custom width in mm, or pick a journal.")
            try:
                out["width_mm"] = float(txt)
            except ValueError:
                raise ValueError("Custom width must be a number (mm).")
        else:
            out["journal"] = journal
        try:
            out["min_dpi"] = int(self.min_dpi_edit.text())
            out["min_font_pt"] = float(self.min_font_edit.text())
        except ValueError:
            raise ValueError("Min DPI must be an integer and min font a number.")
        if self.with_apply_options:
            out["add_panel_labels"] = self.panel_labels_check.isChecked()
        return out


class _ScaleBarAllDialog(QFrame):
    """Configure a scale bar to apply to every panel at once."""

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        r = 0
        self.width_edit = QLineEdit("10", self)
        grid.addWidget(QLabel("Bar length (in units):", self), r, 0)
        grid.addWidget(self.width_edit, r, 1); r += 1
        self.unit_edit = QLineEdit("µm", self)
        grid.addWidget(QLabel("Unit:", self), r, 0)
        grid.addWidget(self.unit_edit, r, 1); r += 1
        self.px_edit = QLineEdit("", self)
        self.px_edit.setPlaceholderText("optional: pixels per unit")
        grid.addWidget(QLabel("Px→unit factor:", self), r, 0)
        grid.addWidget(self.px_edit, r, 1); r += 1
        self.placement_combo = QComboBox(self)
        self.placement_combo.addItems(["bottom right", "bottom left",
                                       "top right", "top left"])
        grid.addWidget(QLabel("Placement:", self), r, 0)
        grid.addWidget(self.placement_combo, r, 1); r += 1

    def values(self) -> dict:
        try:
            width = float(self.width_edit.text())
        except ValueError:
            raise ValueError("Bar length must be a number.")
        out = {"bar_width_in_units": width,
               "unit": self.unit_edit.text().strip() or "µm",
               "placement": self.placement_combo.currentText()}
        px = self.px_edit.text().strip()
        if px:
            try:
                out["px_to_unit"] = float(px)
            except ValueError:
                raise ValueError("Px→unit factor must be a number.")
        return out


class _RemapPathsDialog(QFrame):
    """Rewrite a path prefix on every image filename in the figure."""

    def __init__(self, parent=None):
        super().__init__(parent)
        grid = QGridLayout(self)
        self.old_edit = QLineEdit("", self)
        self.old_edit.setPlaceholderText(r"e.g. C:\old\data")
        self.new_edit = QLineEdit("", self)
        self.new_edit.setPlaceholderText(r"e.g. D:\new\data")
        grid.addWidget(QLabel("Old path prefix:", self), 0, 0)
        grid.addWidget(self.old_edit, 0, 1)
        grid.addWidget(QLabel("New path prefix:", self), 1, 0)
        grid.addWidget(self.new_edit, 1, 1)

    def values(self) -> dict:
        old = self.old_edit.text()
        new = self.new_edit.text()
        if not old:
            raise ValueError("Enter the old path prefix to replace.")
        return {"old_prefix": old, "new_prefix": new}


class EZFIG_GUI(QMainWindow):
    # stop_threads = False
    spinBoxEnterPressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)


        # self.threadpool = QThreadPool()

        # if sys.platform == "darwin":
        #     self.ctrl_key = "Meta"  # Command key on macOS
        # else:
        #     self.ctrl_key = "Ctrl" # Control key on other platforms
        self.ctrl_key = getCtrlModifierAsString()

        # file-state tracking (must exist before initUI sets the window title)
        self.current_file = None
        self._dirty = False

        self.row_or_col_assembly_widget()  # the widget that contain the row or col panels
        self.initUI()
        from pyfigures.gui.theme import load_saved_theme
        self._reload_toolbar_icons(load_saved_theme())
        self._active_img_loaders = []
        QApplication.instance().aboutToQuit.connect(self._stop_all_img_loaders)
        self.color_assistant = None  # Add this line

        self.activate_or_reset_undo_redo()
        self.save_state(show_popup=False)  # maybe not needed
        self._mark_clean()  # a freshly launched, empty figure has nothing to save yet
        self.setAcceptDrops(True)  # we accept DND but just to transfer it to the current list handlers!!!

        # TODO --> add a single tip with all at the beginning and then randomly change tip with a timer maybe add a check both for auto next or alike
        self.tips = [
            # key tips
            "Video demos available at https://www.youtube.com/playlist?list=PLCtF2DKlhKYd6oz6qZPgA_WrD025q5Bl7",
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
            "Pressing Delete can remove the selection from the current figure.",
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
            "Select a group then press " + self.ctrl_key + " to add (an)other group(s) to the current selection.",
        ]

        first_tip = "\n<br><br>-".join(self.tips[:12])
        first_tip = '-' + first_tip
        self.tips = [f'<b>Tip {iii}: </b>{tip}' for iii, tip in enumerate(self.tips, start=1)]
        self.tips.insert(0, first_tip)

        # dialog = TipDialog(self, self.tips)
        # dialog.exec_()
        # Show the TipDialog at launch (using a QTimer to avoid recursion)
        # QTimer.singleShot(0, lambda: self.show_tips())
        from pyfigures.gui.user_prefs import load_auto_show_tips
        if load_auto_show_tips():
            QTimer.singleShot(0, self.show_tips)

        # the MCP HTTP server, if the user asked for it to start with PyFigures
        # (Tools > MCP server…); one started here is stopped at close
        self._started_mcp_http = False
        try:
            from pyfigures.gui.mcp_server_dialog import autostart_http_server
            self._started_mcp_http = autostart_http_server()
        except Exception:
            traceback.print_exc()

        from pyfigures.gui.tutorial import TutorialController
        self._tutorial = TutorialController(self)

        # We create an image store to spare resources
        if True: # this takes even more memory as of now but I should be able to improve that in the future
            ImageCentralStore.init() # force in mem store to speed up the process

        # Install the event filter on the central widget
        # self.event_filter = WheelEventFilter()
        # self.installEventFilter(self.event_filter)


    def activate_or_reset_undo_redo(self):
        self.undo_stack = []
        self.redo_stack = []
        self.current_index = 0
        self.counter = 0
        self.last_called_state = None
        self.current_file = None

        # remove the undo files of the previous session before dropping the reference
        if getattr(self, 'temp_dir', None) is not None:
            cleanup_temp_dir(self.temp_dir)

        # this is a trick to make sure that this will ultimately be cleaned even if soft crashes, exactly what I wanted to have!!!
        self.temp_dir = tempfile.TemporaryDirectory()
        atexit.register(cleanup_temp_dir, self.temp_dir)

        self.update_button_state()

    def initUI(self):
        try:
            screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
            centerPoint = QApplication.desktop().screenGeometry(screen).center()
        except Exception:
            from qtpy.QtGui import QGuiApplication
            centerPoint = QGuiApplication.primaryScreen().geometry().center()

        # should even fit on old computer screens (1024x768)
        window_width = 980
        window_height = 720
        self.setGeometry(
            QRect(centerPoint.x() - int(window_width / 2), centerPoint.y() - int(window_height / 2),
                  window_width,
                  window_height))

        from pyfigures.icons import app_icon
        self.setWindowIcon(app_icon('pyfigures'))

        # zoom parameters
        self._update_window_title()

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
        self.paint.EZFIG_panel.force_update_store.connect(self.force_update_store)
        self.paint.EZFIG_panel.force_silent_spinner_update_in_parent.connect(self.force_silent_spinner_update_in_parent)
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
            except Exception:
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

        self.pbar = QProgressBar(self)
        self.pbar.setToolTip('Image loading progress')
        self.pbar.setMaximumWidth(200)
        self.pbar.setTextVisible(True)
        self.pbar.hide()
        statusBar.addPermanentWidget(self.pbar)

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

        self._up_shortcut = QShortcut(QKeySequence(Qt.Key_Up), self)  # use it or remove it TODO
        self._up_shortcut.activated.connect(self.paint.EZFIG_panel.up_pressed)
        self._up_shortcut.setContext(Qt.ApplicationShortcut)

        self._down_shortcut = QShortcut(QKeySequence(Qt.Key_Down), self)  # use it or remove it TODO
        self._down_shortcut.activated.connect(self.paint.EZFIG_panel.down_pressed)
        self._down_shortcut.setContext(Qt.ApplicationShortcut)

        self._left_shortcut = QShortcut(QKeySequence(Qt.Key_Left), self)  # use it or remove it TODO
        self._left_shortcut.activated.connect(self.paint.EZFIG_panel.left_pressed)
        self._left_shortcut.setContext(Qt.ApplicationShortcut)

        self._right_shortcut = QShortcut(QKeySequence(Qt.Key_Right), self)  # use it or remove it TODO
        self._right_shortcut.activated.connect(self.paint.EZFIG_panel.right_pressed)
        self._right_shortcut.setContext(Qt.ApplicationShortcut)

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

        self.new_ico = QAction(get_icon('mdi.newspaper-plus', color_disabled='lightgray'), 'New figure', self)  # 'mdi.new-box'
        self.new_ico.triggered.connect(self.new_fig)

        self.open_ico = QAction(get_icon('fa.folder-open-o', color_disabled='lightgray'), 'Open', self)  # 'mdi.new-box'
        self.open_ico.setToolTip('Open a .pyf figure, replacing the current one')
        self.open_ico.triggered.connect(lambda: self.open_figure(append=False))

        self.save_in_bar = QAction(get_icon('fa.save', color_disabled='lightgray'), 'Save', self)
        self.save_in_bar.triggered.connect(self.save_pyfigures)

        self.export_as_tif_ico = QAction(get_icon('mdi.export', color_disabled='lightgray'), 'Export as raster image',
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
        # self.force_update_layout_button.setIcon(get_icon('fa.check', color_disabled='lightgray'))
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
        self.force_update_layout_button = QAction(get_icon('fa.check', color_disabled='lightgray'),
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

        # figure-wide background: fills the gaps between panels (none = transparent)
        self.page_background_button = QToolButton()
        self.page_background_button.setText('Background')
        self.page_background_button.setPopupMode(QToolButton.InstantPopup)
        bg_menu = QMenu(self.page_background_button)
        for name, value in (('None (transparent)', None), ('White', 0xFFFFFF),
                            ('Black', 0x000000)):
            bg_menu.addAction(name).triggered.connect(
                lambda _checked=False, v=value: self._choose_page_background(v))
        bg_menu.addAction('Other colour…').triggered.connect(
            lambda _checked=False: self._choose_page_background('picker'))
        self.page_background_button.setMenu(bg_menu)
        self.page_background_button.setToolTip(
            'Figure background — the colour between panels and around them '
            '(transparent by default in PNG/TIFF)')


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

        self.undo_button = QAction(get_icon('fa5s.undo', color_disabled='lightgray'), 'Undo', self)
        self.redo_button = QAction(get_icon('fa5s.redo', color_disabled='lightgray'), 'Redo', self)
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
        self.mainToolBar.addWidget(self.page_background_button)
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

        open_action = QAction('Open…', self)
        open_action.setShortcut(QKeySequence(f"{self.ctrl_key}+O"))
        open_action.setToolTip('Open a .pyf figure, replacing the current one')
        file_menu.addAction(open_action)
        open_action.triggered.connect(lambda: self.open_figure(append=False))  # replace (same as toolbar)

        merge_action = QAction('Merge into current figure…', self)
        merge_action.setToolTip('Append the contents of another .pyf into the current figure')
        file_menu.addAction(merge_action)
        merge_action.triggered.connect(lambda: self.open_figure(append=True))  # merge/append

        new_action = QAction('New', self)
        new_action.setShortcut(QKeySequence(f"{self.ctrl_key}+N"))
        file_menu.addAction(new_action)
        new_action.triggered.connect(self.new_fig)

        url_action = QAction("Add image from URL / OME-Zarr / OMERO…", self)
        url_action.setToolTip("Add an image from an http(s) URL, an OME-Zarr image (a URL such as "
                              "https://…/image.zarr or a local .zarr folder, e.g. from the IDR) or an "
                              "image on your OMERO server (paste its OMERO.web link). For OME-Zarr "
                              "pick the pyramid level; for OMERO log in if asked.")
        file_menu.addAction(url_action)
        url_action.triggered.connect(self.add_image_from_url_action)

        equation_action = QAction("Add equation (LaTeX)…", self)
        equation_action.setToolTip("Type a LaTeX equation (e.g. \\Delta F/F_0); it is typeset as a "
                                   "vector panel, no TeX installation needed. Right-click it later to "
                                   "edit it.")
        file_menu.addAction(equation_action)
        equation_action.triggered.connect(self.add_equation_action)

        latex_code_action = QAction("Add LaTeX code panel…", self)
        latex_code_action.setToolTip("Write LaTeX code (a TikZ / pgfplots picture, a table, a whole "
                                     "document): compiled into a vector panel that stays editable "
                                     "(right-click → Edit LaTeX code…). Needs LaTeX.")
        file_menu.addAction(latex_code_action)
        latex_code_action.triggered.connect(self.add_latex_code_action)

        draft_action = QAction("Draft figure from folder…", self)
        draft_action.setToolTip("Auto-assemble a first-pass figure from a folder of "
                                "images and CSVs: grid layout, data plots, scale bars, "
                                "A/B/C letters, journal size and a caption stub.")
        file_menu.addAction(draft_action)
        draft_action.triggered.connect(self.draft_figure_action)

        recipe_action = QAction("Build figure from recipe…", self)
        recipe_action.setToolTip("Build a figure from a YAML/JSON recipe (rows of images, "
                                 "globs, stacks, merges and CSV plots; LUTs, crops, scale bars, "
                                 "text, shapes, arrows, insets, zooms, kymographs; journal size, "
                                 "fonts, caption, checks and exports; or a filled template) — "
                                 "reproducible and rebuildable "
                                 "when the data change. Reference: docs/RECIPES.md.")
        file_menu.addAction(recipe_action)
        recipe_action.triggered.connect(self.build_from_recipe_action)

        search_lib_action = QAction("Search figure library…", self)
        search_lib_action.setToolTip("Index a folder tree of past .pyf figures and "
                                     "search them by panel, label or caption to find "
                                     "and reuse a figure.")
        file_menu.addAction(search_lib_action)
        search_lib_action.triggered.connect(self.search_library_action)

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

        compare_action = QAction("Compare with another version…", self)
        compare_action.setToolTip("Visually diff the current figure against another "
                                  ".pyf — side-by-side renders, a pixel-difference "
                                  "overlay and a list of what changed.")
        file_menu.addAction(compare_action)
        compare_action.triggered.connect(self.compare_version_action)

        file_menu.addSeparator()
        caption_action = QAction("Figure caption / legend…", self)
        caption_action.setToolTip("Write the figure's caption/legend (stored beside "
                                  "the .pyf, exportable for submission).")
        file_menu.addAction(caption_action)
        caption_action.triggered.connect(self.figure_caption_action)

        alt_text_action = QAction("Alt text (accessibility)…", self)
        alt_text_action.setToolTip("Draft and edit the figure's description for screen-reader "
                                   "users (stored beside the .pyf).")
        file_menu.addAction(alt_text_action)
        alt_text_action.triggered.connect(self.alt_text_action)

        copy_style_action = QAction("Copy style from another figure…", self)
        copy_style_action.setToolTip("Give this figure the fonts, letters, scale bars, "
                                     "spacing and chart styling of another .pyf.")
        file_menu.addAction(copy_style_action)
        copy_style_action.triggered.connect(self.copy_style_action)

        # Add a separator
        file_menu.addSeparator()
        export_menu = file_menu.addMenu("Export As")

        _vector_title = QAction("— Vector —", self)
        _vector_title.setEnabled(False)
        export_menu.addAction(_vector_title)

        export_as_svg_action = QAction("SVG", self)
        export_menu.addAction(export_as_svg_action)
        export_as_svg_action.triggered.connect(self.export_as_svg)

        export_as_pdf_action = QAction("PDF", self)
        export_menu.addAction(export_as_pdf_action)
        export_as_pdf_action.triggered.connect(self.export_as_pdf)

        export_as_latex_action = QAction("PDF + LaTeX (text as LaTeX)…", self)
        export_as_latex_action.setToolTip(
            "Vector PDF with no text + a LaTeX overlay so labels use your document's "
            "fonts and real math ($\\alpha$, subscripts). \\input the .pdf_tex file.")
        export_menu.addAction(export_as_latex_action)
        export_as_latex_action.triggered.connect(self.export_as_latex)

        export_as_pptx_action = QAction("PowerPoint (editable)…", self)
        export_as_pptx_action.setToolTip(
            "One slide, one group per panel: pictures plus editable text boxes and shapes "
            "(letters, labels, scale bars, ROIs, arrows).")
        export_menu.addAction(export_as_pptx_action)
        export_as_pptx_action.triggered.connect(self.export_as_pptx)

        export_as_jsx_action = QAction("Adobe Illustrator script (.jsx)…", self)
        export_as_jsx_action.setToolTip(
            "A script that rebuilds the figure in Illustrator with live text and vector "
            "shapes (File > Scripts > Other Script…). Images go to a <name>_assets folder.")
        export_menu.addAction(export_as_jsx_action)
        export_as_jsx_action.triggered.connect(self.export_as_illustrator)

        export_menu.addSeparator()

        _raster_title = QAction("— Raster —", self)
        _raster_title.setEnabled(False)
        export_menu.addAction(_raster_title)

        export_as_png_action = QAction("PNG", self)
        export_menu.addAction(export_as_png_action)
        export_as_png_action.triggered.connect(self.export_as_png)

        export_as_tif_action = QAction("TIF", self)
        export_menu.addAction(export_as_tif_action)
        export_as_tif_action.triggered.connect(self.export_as_tif)

        export_as_jpg_action = QAction("JPEG", self)
        export_menu.addAction(export_as_jpg_action)
        export_as_jpg_action.triggered.connect(self.export_as_jpg)

        export_menu.addSeparator()
        _print_title = QAction("— Print —", self)
        _print_title.setEnabled(False)
        export_menu.addAction(_print_title)
        export_print_action = QAction("Print-ready TIFF (CMYK)…", self)
        export_print_action.setToolTip("High-DPI CMYK (or RGB) TIFF for print submission.")
        export_menu.addAction(export_print_action)
        export_print_action.triggered.connect(self.export_print_ready_action)

        export_menu.addSeparator()

        _video_title = QAction("— Video —", self)
        _video_title.setEnabled(False)
        export_menu.addAction(_video_title)

        export_as_video_action = QAction("Video (animate time-stacks)…", self)
        export_menu.addAction(export_as_video_action)
        export_as_video_action.triggered.connect(self.export_as_video)

        export_menu.addSeparator()
        _submission_title = QAction("— Submission —", self)
        _submission_title.setEnabled(False)
        export_menu.addAction(_submission_title)
        export_source_data_action = QAction("Source data bundle…", self)
        export_source_data_action.setToolTip(
            "Folder of underlying data + provenance for submission: the rendered "
            "figure, each panel's source image/CSV, the caption, the statistics and "
            "a Methods paragraph.")
        export_menu.addAction(export_source_data_action)
        export_source_data_action.triggered.connect(self.export_source_data_action)

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
        annots.addSeparator()
        tidy_text_action = QAction("Tidy text typography (×, °, units, ranges…)", self)
        tidy_text_action.setToolTip('Apply safe typography fixes to every label: 2*3→2×3, '
                                    '37 degrees C→37 °C, 10µm→10 µm, 10-20→10–20, -5→−5')
        annots.addAction(tidy_text_action)
        tidy_text_action.triggered.connect(self.tidy_all_text)

        annots.addSeparator()
        add_colour_bar_action = QAction("Add LUT colour bar…", self)
        add_colour_bar_action.setToolTip('Insert an intensity calibration bar '
                                         '(colour bar) matching a LUT')
        annots.addAction(add_colour_bar_action)
        add_colour_bar_action.triggered.connect(self.add_colour_bar)

        annots.addSeparator()
        scale_bar_all_action = QAction("Add scale bar to all panels…", self)
        annots.addAction(scale_bar_all_action)
        scale_bar_all_action.triggered.connect(self.add_scale_bar_all)

        annots.addSeparator()
        channel_merge_action = QAction("Add multi-channel merge…", self)
        channel_merge_action.setToolTip('Overlay several single-channel images '
                                        '(e.g. DAPI + GFP + RFP) into one pseudo-coloured merge panel')
        annots.addAction(channel_merge_action)
        channel_merge_action.triggered.connect(self.add_channel_merge_action)

        zoom_callout_action = QAction("Add zoom callout to selected panel…", self)
        zoom_callout_action.setToolTip('Box a region of the selected image and show it magnified '
                                       'in a corner inset, joined by leader lines')
        annots.addAction(zoom_callout_action)
        zoom_callout_action.triggered.connect(self.add_zoom_callout_action)

        arrow_action = QAction("Add arrow pointing at a feature…", self)
        arrow_action.setToolTip('Arrow whose point sits exactly on the chosen pixel of the '
                                'selected image, whatever the figure size')
        annots.addAction(arrow_action)
        arrow_action.triggered.connect(self.add_arrow_action)

        stack_menu = annots.addMenu("Stack views")
        for text, tip, slot in (
                ("Montage of frames (time / Z)…",
                 "Opt-in: several frames of the selected stack in a new row, with "
                 "time or depth stamps (a stack otherwise shows one image)",
                 self.add_stack_montage_action),
                ("Channel split (each channel + merge)…",
                 "New row: each channel of the selected image in gray with its name in "
                 "colour, then the merge",
                 self.add_channel_split_action),
                ("Kymograph along a line…",
                 "Position along a line against time, from the selected time stack",
                 self.add_kymograph_action),
                ("Orthogonal views (XZ / YZ)…",
                 "XY + YZ + XZ cut through a point of the selected Z stack",
                 self.add_orthogonal_views_action)):
            act = QAction(text, self)
            act.setToolTip(tip)
            stack_menu.addAction(act)
            act.triggered.connect(slot)

        data_plot_action = QAction("Add data plot from CSV…", self)
        data_plot_action.setToolTip('Render a bar / box / violin / scatter / grouped plot from a '
                                    'CSV of measurements, with automatic significance brackets '
                                    '(needs the staplot package)')
        annots.addAction(data_plot_action)
        data_plot_action.triggered.connect(self.add_data_plot_action)

        qc_menu = self.menuBar.addMenu("QC")
        audit_action = QAction("Audit figure (missing scale bars / labels)", self)
        qc_menu.addAction(audit_action)
        audit_action.triggered.connect(self.audit_figure_report)
        qc_menu.addSeparator()
        compliance_action = QAction("Check journal compliance…", self)
        qc_menu.addAction(compliance_action)
        compliance_action.triggered.connect(self.check_journal_compliance_report)
        resolution_action = QAction("Check print resolution…", self)
        qc_menu.addAction(resolution_action)
        resolution_action.triggered.connect(self.check_resolution_report)
        qc_menu.addSeparator()
        apply_journal_action = QAction("Apply journal guidelines…", self)
        qc_menu.addAction(apply_journal_action)
        apply_journal_action.triggered.connect(self.apply_journal_guidelines_action)
        enforce_font_action = QAction("Enforce minimum font size…", self)
        qc_menu.addAction(enforce_font_action)
        enforce_font_action.triggered.connect(self.enforce_min_font_action)
        qc_menu.addSeparator()
        mcp_history_action = QAction("MCP call history / undo…", self)
        mcp_history_action.setToolTip("Every call the MCP server made on this figure, and undo "
                                      "of the last changes it made.")
        qc_menu.addAction(mcp_history_action)
        mcp_history_action.triggered.connect(self.mcp_history_dialog)
        qc_menu.addSeparator()
        integrity_action = QAction("Check image integrity (duplicates / clones)…", self)
        integrity_action.setToolTip("Screen panels for reused, flipped/rotated or "
                                    "internally cloned images before submission.")
        qc_menu.addAction(integrity_action)
        integrity_action.triggered.connect(self.check_integrity_action)
        scale_consistency_action = QAction("Check scale-bar consistency…", self)
        scale_consistency_action.setToolTip("Flag panels whose displayed physical scale "
                                            "differs, so features can't be honestly "
                                            "compared by eye across panels.")
        qc_menu.addAction(scale_consistency_action)
        scale_consistency_action.triggered.connect(self.check_scale_consistency_action)
        review_action = QAction("Pre-submission review (all checks)…", self)
        review_action.setToolTip("Run every mechanical QC check at once and list the "
                                 "reviewer questions to judge before submitting.")
        qc_menu.addAction(review_action)
        review_action.triggered.connect(self.figure_review_action)
        ledger_action = QAction("Adjustment provenance ledger (Methods)…", self)
        ledger_action.setToolTip("Per-panel record of brightness/contrast, LUT, crop, "
                                 "rotation, scripts + a ready-to-paste Methods paragraph.")
        qc_menu.addAction(ledger_action)
        ledger_action.triggered.connect(self.adjustment_ledger_action)
        fonts_action = QAction("Fonts (portable / Helvetica)…", self)
        fonts_action.setToolTip("What Helvetica/Arial resolve to, and which portable "
                                "fonts are bundled for cross-machine reproducibility.")
        qc_menu.addAction(fonts_action)
        fonts_action.triggered.connect(self.fonts_report_action)
        qc_menu.addSeparator()
        changed_action = QAction("Check for changed source files…", self)
        changed_action.setToolTip("List images / CSVs that changed since the figure was "
                                  "saved (the figure silently follows its sources).")
        qc_menu.addAction(changed_action)
        changed_action.triggered.connect(self.check_source_changes_action)
        remap_action = QAction("Remap image paths…", self)
        qc_menu.addAction(remap_action)
        remap_action.triggered.connect(self.remap_paths_action)

        tools_menu = self.menuBar.addMenu("Tools")
        poster_action = QAction("Poster / collage designer…", self)
        poster_action.setToolTip("Separate tool for posters and photo-collage pages: images can be "
                                  "freely rotated (without cropping) and positioned, with a full-page "
                                  "background image. Independent from this figure editor and its files.")
        tools_menu.addAction(poster_action)
        poster_action.triggered.connect(self.open_poster_designer)
        album_action = QAction("Photo album designer…", self)
        album_action.setToolTip("Separate tool for photo books: a front cover, two-page spreads and "
                                "a back cover, with freely placed and rotated photos on each page.")
        tools_menu.addAction(album_action)
        album_action.triggered.connect(self.open_album_designer)
        tools_menu.addSeparator()
        mcp_server_action = QAction("MCP server…", self)
        mcp_server_action.setToolTip("Register the PyFigures MCP server with Claude or LM Studio "
                                     "(they start it when they need it), or start / stop it over HTTP.")
        tools_menu.addAction(mcp_server_action)
        mcp_server_action.triggered.connect(self.open_mcp_server_dialog)

        template = self.menuBar.addMenu("Template")
        templatify_action = QAction("Convert figure to template", self)  # ? shall I say it like that
        template.addAction(templatify_action)
        templatify_action.triggered.connect(self.templatify_figure)  # cool I didn't know one can do that...

        review_menu = self.menuBar.addMenu("Review")
        export_for_review_action = QAction("Export for review…", self)
        review_menu.addAction(export_for_review_action)
        export_for_review_action.triggered.connect(self.export_for_review)

        import_review_action = QAction("Import review comments…", self)
        review_menu.addAction(import_review_action)
        import_review_action.triggered.connect(self.import_review_comments)

        view_review_action = QAction("View review comments", self)
        review_menu.addAction(view_review_action)
        view_review_action.triggered.connect(self.view_review_comments)

        view_menu = self.menuBar.addMenu('View')
        theme_menu = view_menu.addMenu('Theme')
        self._theme_actions = {}
        from pyfigures.gui.theme import apply_theme, load_saved_theme
        _current_theme = load_saved_theme()
        for theme_name, label in (('system', 'System (auto)'), ('light', 'Light'), ('dark', 'Dark')):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(theme_name == _current_theme)
            act.triggered.connect(lambda checked, t=theme_name: self._apply_theme(t))
            theme_menu.addAction(act)
            self._theme_actions[theme_name] = act

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

        cvd_preview_action = QAction('Preview figure under colour-blindness…', self)
        cvd_preview_action.setToolTip('See the whole figure as a colour-blind '
                                      'reader would (deuteranopia / protanopia / '
                                      'tritanopia)')
        cvd_preview_action.triggered.connect(self.preview_color_blindness)
        help_menu.addAction(cvd_preview_action)

        help_menu.addSeparator()
        user_guide_action = QAction('User Guide', self)
        user_guide_action.triggered.connect(self.show_user_guide)
        help_menu.addAction(user_guide_action)

        install_latex = QAction('Install LaTeX for PyFigures…', self)
        install_latex.setToolTip('Download TinyTeX (a small TeX Live) for full-LaTeX equations, '
                                 '.tex documents and LaTeX data plots')
        install_latex.triggered.connect(self.install_latex_action)
        help_menu.addAction(install_latex)

        help_menu.addSeparator()
        beginner_tuto_action = QAction('▶  Beginner Tutorial', self)
        beginner_tuto_action.triggered.connect(self.start_beginner_tutorial)
        help_menu.addAction(beginner_tuto_action)

        advanced_tuto_action = QAction('▶  Medium Tutorial', self)
        advanced_tuto_action.triggered.connect(self.start_advanced_tutorial)
        help_menu.addAction(advanced_tuto_action)

        expert_tuto_action = QAction('▶  Advanced Tutorial', self)
        expert_tuto_action.triggered.connect(self.start_expert_tutorial)
        help_menu.addAction(expert_tuto_action)

        publication_tuto_action = QAction('▶  Publication & QC Tutorial', self)
        publication_tuto_action.triggered.connect(self.start_publication_tutorial)
        help_menu.addAction(publication_tuto_action)

        sharing_tuto_action = QAction('▶  Sharing, Review & Accessibility Tutorial', self)
        sharing_tuto_action.triggered.connect(self.start_sharing_tutorial)
        help_menu.addAction(sharing_tuto_action)

        stacks_tuto_action = QAction('▶  Stacks, Channels & Movies Tutorial', self)
        stacks_tuto_action.setToolTip('Projections, channel split, montages, kymographs, '
                                      'orthogonal views, channel merges and movie export')
        stacks_tuto_action.triggered.connect(self.start_stacks_tutorial)
        help_menu.addAction(stacks_tuto_action)

        automation_tuto_action = QAction('▶  Automate: Drafts, Recipes & Library Tutorial', self)
        automation_tuto_action.triggered.connect(self.start_automation_tutorial)
        help_menu.addAction(automation_tuto_action)

        poster_tuto_action = QAction('▶  Poster Tutorial', self)
        poster_tuto_action.setToolTip('Opens the poster / collage designer and guides you through it')
        poster_tuto_action.triggered.connect(self.start_poster_tutorial)
        help_menu.addAction(poster_tuto_action)

        album_tuto_action = QAction('▶  Photo Album Tutorial', self)
        album_tuto_action.setToolTip('Opens the photo album designer and guides you through it')
        album_tuto_action.triggered.connect(self.start_album_tutorial)
        help_menu.addAction(album_tuto_action)


    # Maps each persistent toolbar QAction to its qtawesome icon name.
    _TOOLBAR_ICON_MAP = [
        ('new_ico',                    'mdi.newspaper-plus'),
        ('open_ico',                   'fa.folder-open-o'),
        ('save_in_bar',                'fa.save'),
        ('export_as_tif_ico',          'mdi.export'),
        ('force_update_layout_button', 'fa.check'),
        ('undo_button',                'fa5s.undo'),
        ('redo_button',                'fa5s.redo'),
    ]

    def _apply_theme(self, theme_name):
        from pyfigures.gui.theme import apply_theme
        resolved = apply_theme(theme_name)  # returns 'light' or 'dark'
        for name, act in self._theme_actions.items():
            act.setChecked(name == theme_name)
        self._reload_toolbar_icons(resolved)

    def _reload_toolbar_icons(self, theme_name):
        # theme_name is always the resolved value ('light' or 'dark'), never 'system'.
        # Use explicit colors so icons are always visible regardless of theme,
        # and so the enabled/disabled contrast is preserved in both modes.
        # Dark : enabled = light gray, disabled = dim gray (clearly darker)
        # Light: enabled = dark gray,  disabled = light gray (clearly lighter)
        from pyfigures.gui.theme import resolve_theme
        resolved = resolve_theme(theme_name)  # handle 'system' if called directly
        if resolved == 'dark':
            color, color_disabled = '#dcdcdc', '#555555'
        else:
            color, color_disabled = '#404040', 'lightgray'
        for attr, icon_name in self._TOOLBAR_ICON_MAP:
            action = getattr(self, attr, None)
            if action is not None:
                action.setIcon(get_icon(icon_name, color=color, color_disabled=color_disabled))

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
        except Exception:
            pass

    def _set_page_background(self, color):
        """Apply a figure background (0xRRGGBB or None) to the canvas and show
        it on the toolbar button."""
        color = None if color is None else int(color) & 0xFFFFFF
        self.paint.EZFIG_panel.page_background = color
        btn = getattr(self, 'page_background_button', None)
        if btn is not None:
            if color is None:
                btn.setIcon(QIcon())
            else:
                pix = QPixmap(14, 14)
                pix.fill(QColor(color))
                btn.setIcon(QIcon(pix))
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.paint.EZFIG_panel.update()

    def _choose_page_background(self, color):
        """Toolbar Background menu: None / a colour / 'picker'."""
        if color == 'picker':
            cur = self.paint.EZFIG_panel.page_background
            picked = QColorDialog.getColor(QColor(0xFFFFFF if cur is None else cur), self,
                                           'Figure background')
            if not picked.isValid():
                return
            color = picked.rgb() & 0xFFFFFF
        if color == self.paint.EZFIG_panel.page_background:
            return
        self._set_page_background(color)
        self._mark_dirty()

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

    def start_beginner_tutorial(self):
        from pyfigures.gui.tutorial import beginner_steps
        self._tutorial.start(beginner_steps())

    def start_advanced_tutorial(self):
        from pyfigures.gui.tutorial import medium_steps
        self._tutorial.start(medium_steps())

    def start_expert_tutorial(self):
        from pyfigures.gui.tutorial import advanced_steps
        self._tutorial.start(advanced_steps())

    def start_publication_tutorial(self):
        from pyfigures.gui.tutorial import publication_steps
        self._tutorial.start(publication_steps())

    def start_sharing_tutorial(self):
        from pyfigures.gui.tutorial import sharing_steps
        self._tutorial.start(sharing_steps())

    def start_stacks_tutorial(self):
        from pyfigures.gui.tutorial import stacks_steps
        self._tutorial.start(stacks_steps())

    def start_automation_tutorial(self):
        from pyfigures.gui.tutorial import automation_steps
        self._tutorial.start(automation_steps())

    def start_poster_tutorial(self):
        """The poster tutorial runs in the poster window, which it opens."""
        self.open_poster_designer()
        self._poster_window.start_tutorial()

    def start_album_tutorial(self):
        """The photo album tutorial runs in the photo album window, which it opens."""
        self.open_album_designer()
        self._album_window.start_tutorial()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_tutorial'):
            self._tutorial.handle_resize()

    def show_user_guide(self):
        import webbrowser
        doc = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'pyfigures_user_guide.html')
        doc = os.path.normpath(doc)
        if os.path.exists(doc):
            webbrowser.open('file://' + doc)
        else:
            QMessageBox.information(self, 'User Guide',
                f'Documentation file not found at:\n{doc}\n\nRun docs/capture_screenshots.py to generate it.')

    def show_about_dialog(self):
        current_year = datetime.now().year
        if current_year > 2024:
            year_string = f"-{current_year}"
        else:
            year_string = ""
        about_dialog = AboutDialog(self, title=__NAME__, name=__SHORT__NAME__,
                                   version=f"Version {__VERSION__}",
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
                except Exception:
                    print('error occurred in setting width1')
                    traceback.print_exc()
                    # sys.exit(0)
            else:
                try:
                    set_to_height(cur_sel, value)
                except Exception:
                    print('error occurred in setting height1')
                    traceback.print_exc()
        elif isinstance(cur_sel, Image2D):
            if 'idth' in self.fit_to_combo.currentText():
                try:
                    set_to_width_im2d(cur_sel, value)
                except Exception:
                    print('error occurred in setting width2')
                    traceback.print_exc()
            else:
                try:
                    set_to_height_im2d(cur_sel, value)
                except Exception:
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

        if event.mimeData().hasUrls():
            self.list = []
            event.setDropAction(Qt.CopyAction)

            rejected = []
            unsupported = []
            empty_folders = []
            for url in event.mimeData().urls():
                url = url.toLocalFile()
                if os.path.isdir(url):
                    # a dropped folder loads every image within it (recursively),
                    # then the usual drop menu (row/column/panel/single) is offered
                    found = list_image_files_in_folder(url)
                    if found:
                        self.list.extend(found)
                    else:
                        empty_folders.append(url)
                elif os.path.isfile(url):
                    if is_forbidden_image_file(url):
                        rejected.append(url)
                        continue
                    if url.lower().endswith('.tex'):
                        # a LaTeX file becomes an equation panel (its document body)
                        eq = self._equation_from_tex(url)
                        if eq:
                            self.list.append(eq)
                        continue
                    if not (url.lower().endswith('.pyf') or is_image_file(url)):
                        # a .txt/.csv/.docx... used to be added as a broken panel
                        unsupported.append(url)
                        continue
                    self.list.append(url)

            event.accept()

            if rejected:
                names = ', '.join(os.path.basename(r) for r in rejected)
                logger.warning('Ignored unsupported companion file(s): ' + names +
                               ' - open the .lif file itself, not its sidecar.')
            if unsupported:
                names = ', '.join(os.path.basename(r) for r in unsupported)
                logger.warning('Ignored file(s) that are not images or figures: ' + names)
                self.statusBar().showMessage('Ignored (not an image or .pyf figure): ' + names, 8000)
            if empty_folders and not self.list:
                names = ', '.join(os.path.basename(f) for f in empty_folders)
                logger.warning('No loadable images found in folder(s): ' + names)

            if self.list:
                n = len(self.list)
                self.statusBar().showMessage(
                    f'Dropped {n} file{"s" if n > 1 else ""}, please wait...')
                QApplication.processEvents()

                event_pos_in_current_widget = event.pos()
                event_pos_global = self.mapToGlobal(event_pos_in_current_widget)
                event_pos_in_target_widget = self.paint.EZFIG_panel.mapFromGlobal(event_pos_global)
                event_pos_in_target_widget_scaled = event_pos_in_target_widget / self.paint.EZFIG_panel.scale

                all_shapes_below, first_encounter_below, drop_target, \
                    all_encounters_in_shape_below_mouse, all_encounters_of_sel_shape_below_mouse, \
                    top_parent_of_sel, immediate_parentof_sel, top_parent_of_drop_target = \
                    self.paint.EZFIG_panel.get_all_shapes_involved_in_DND_process_by_mouse_position(
                        event, event_pos_in_target_widget_scaled)

                global_pos = self.mapToGlobal(event.pos())

                try:
                    # Build the menu ONCE
                    self.add_image_from_an_external_source_context_menu(
                        self.list,
                        all_encounters_in_shape_below_mouse if all_encounters_in_shape_below_mouse
                        else all_encounters_of_sel_shape_below_mouse
                    )
                    self.raise_()
                    self.activateWindow()
                    # Show deferred so Wayland assigns transient parent
                    QTimer.singleShot(0, lambda: self._show_dnd_menu(global_pos))
                except Exception:
                    traceback.print_exc()
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()

    def _show_dnd_menu(self, global_pos):
        """Show DND menu as a positioned child widget — bypasses Wayland popup grab."""
        from qtpy.QtWidgets import QFrame, QVBoxLayout, QPushButton, QSizePolicy, QLabel

        menu = self.paint.EZFIG_panel.contextMenu
        if not menu or not menu.actions():
            return

        fake_menu = QFrame(self)
        fake_menu.setFrameShape(QFrame.StyledPanel)
        fake_menu.setFrameShadow(QFrame.Raised)
        fake_menu.setStyleSheet("""
            QFrame {
                background-color: palette(window);
                border: 1px solid palette(mid);
            }
            QPushButton {
                text-align: left;
                padding: 4px 20px;
                border: none;
                background: transparent;
            }
            QPushButton:hover {
                background-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QPushButton:disabled {
                color: palette(window-text);
                font-weight: bold;
                padding: 6px 8px 2px 8px;
                font-size: 10px;
                text-transform: uppercase;
            }
            QLabel#sep_label {
                color: palette(mid);
                font-size: 9px;
                padding: 0px 8px;
            }
        """)

        layout = QVBoxLayout(fake_menu)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        def close_menu():
            fake_menu.hide()
            fake_menu.deleteLater()

        def make_action_handler(action):
            def handler():
                close_menu()
                action.trigger()
            return handler

        for action in menu.actions():
            if action.isSeparator():
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setFrameShadow(QFrame.Sunken)
                layout.addWidget(sep)
            elif not action.isEnabled():
                # Section header — rendered as a small bold uppercase label
                lbl = QPushButton(action.text())
                lbl.setEnabled(False)
                lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                layout.addWidget(lbl)
            elif action.text() == 'Ignore':
                btn = QPushButton('✕  Cancel')
                btn.clicked.connect(close_menu)
                layout.addWidget(btn)
            else:
                btn = QPushButton(action.text())
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                btn.clicked.connect(make_action_handler(action))
                layout.addWidget(btn)

        # Close button at the bottom so user can always dismiss
        # sep = QFrame()
        # sep.setFrameShape(QFrame.HLine)
        # sep.setFrameShadow(QFrame.Sunken)
        # layout.addWidget(sep)
        # close_btn = QPushButton('✕  Close')
        # close_btn.setStyleSheet('color: red;')
        # close_btn.clicked.connect(close_menu)
        # layout.addWidget(close_btn)

        fake_menu.adjustSize()

        # Position within the main window bounds
        local_pos = self.mapFromGlobal(global_pos)
        x = min(max(0, local_pos.x()), self.width() - fake_menu.width())
        y = min(max(0, local_pos.y()), self.height() - fake_menu.height())
        fake_menu.move(x, y)
        fake_menu.show()
        fake_menu.raise_()

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
                lst_after_pyf = [elm for elm in lst if elm not in pyf_list]
                self._start_pyf_loader(pyf_list, only_pyf_drop=not lst_after_pyf)

            lst = [elm for elm in lst if elm not in pyf_list] # we remove pyf files from the list
            # we clean the lst from pyf files and open the pyf content

        if not lst:
            return  # .pyf loading (if any) is handled asynchronously by _start_pyf_loader

        # Series resolution happens AFTER the user picks a layout action (see _with_series below).
        def _with_series(fn):
            """Return a slot that resolves series for *lst* then calls fn(resolved_lst)."""
            def _slot():
                self.statusBar().showMessage('Checking file(s), please wait...')
                QApplication.setOverrideCursor(Qt.WaitCursor)
                QApplication.processEvents()  # flush UI so the message is visible before blocking
                try:
                    resolved = self._resolve_series_for_files(lst)
                finally:
                    QApplication.restoreOverrideCursor()
                # Do NOT clear the status bar here — if loading follows, _load_images_then_callback
                # will immediately replace it with its own "Loading…" message; if nothing was
                # loaded we clear it below.
                if resolved:
                    fn(resolved)
                else:
                    self.statusBar().clearMessage()
            return _slot

        def add_header(text):
            """Add a non-clickable section header to the context menu."""
            act = self.paint.EZFIG_panel.contextMenu.addAction(text)
            act.setEnabled(False)
            return act

        # ── Group: arrange multiple images ───────────────────────────────
        if len(lst) > 1:
            add_header("Arrange as group")
            add_to_new_row = self.paint.EZFIG_panel.contextMenu.addAction("↔  To row")
            add_to_new_row.triggered.connect(_with_series(self.add_images_to_new_row))
            add_to_new_col = self.paint.EZFIG_panel.contextMenu.addAction("↕  To column")
            add_to_new_col.triggered.connect(_with_series(self.add_images_to_new_col))
            add_as_panel = self.paint.EZFIG_panel.contextMenu.addAction("▦  To panel")
            add_as_panel.triggered.connect(_with_series(self.create_panel))
            self.paint.EZFIG_panel.contextMenu.addSeparator()

        # ── Group: combine with the image/group under the drop ───────────
        # When a file is dropped ONTO an existing image or group, offer to merge
        # the dropped image(s) with that shape into a new row or column. Uses the
        # top-level shape under the mouse (so dropping onto an image inside a row
        # combines with the whole row), excluding templates (handled below).
        combine_target = None
        if all_encounters_in_shape_below_mouse:
            enc = find_first_object_of_type(all_encounters_in_shape_below_mouse, (Image2D, Group))
            if enc is not None and not (isinstance(enc, Image2D) and enc.is_template()):
                combine_target = self.paint.EZFIG_panel.get_top_parent_of_shape(enc) or enc
                # don't combine with a pure text/label group
                if getattr(combine_target, 'isText', False):
                    combine_target = None
        if combine_target is not None:
            add_header("Combine with image below")
            combine_row = self.paint.EZFIG_panel.contextMenu.addAction("↔  To row (with image below)")
            combine_row.triggered.connect(_with_series(
                lambda resolved, t=combine_target: self.add_images_combined_with_target(resolved, t, 'X')))
            combine_col = self.paint.EZFIG_panel.contextMenu.addAction("↕  To column (with image below)")
            combine_col.triggered.connect(_with_series(
                lambda resolved, t=combine_target: self.add_images_combined_with_target(resolved, t, 'Y')))
            self.paint.EZFIG_panel.contextMenu.addSeparator()

        # ── Group: add individually ──────────────────────────────────────
        add_header("Add to canvas")
        all_as_single_images = self.paint.EZFIG_panel.contextMenu.addAction("➕  As single image(s)")
        all_as_single_images.triggered.connect(_with_series(self.all_images_directly))

        # ── Group: template assignment (only when dropping onto a template) ──
        if all_encounters_in_shape_below_mouse:
            potential_target = find_first_object_of_type(all_encounters_in_shape_below_mouse, Image2D)
            if potential_target is not None and potential_target.is_template():
                self.paint.EZFIG_panel.contextMenu.addSeparator()
                add_header("Template")
                set_image_in_template = self.paint.EZFIG_panel.contextMenu.addAction(
                    "⬜  Assign to template slot")
                set_image_in_template.triggered.connect(
                    lambda: self.assign_to_template(potential_target, self.list))

        # ── Cancel ───────────────────────────────────────────────────────
        self.paint.EZFIG_panel.contextMenu.addSeparator()
        self.paint.EZFIG_panel.contextMenu.addAction("Ignore")

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
            except Exception:
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

    def _load_images_then_callback(self, filenames, callback):
        """Load Img pixel data in a background thread, build Image2D on the main thread,
        then invoke callback(list_of_Image2D).  Non-string items are passed through unchanged.

        Items in *filenames* can be:
          - str: plain file path (no series preference)
          - (str, int): (file path, serie_to_open index) for multi-series files
          - any other object: passed through as-is
        """
        def _item_path_serie(item):
            """Return (path, serie_or_none) for a list item, or (None, None) if not a file."""
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
                return item[0], item[1]
            if isinstance(item, str):
                return item, None
            return None, None

        pending = [f for f in filenames if f is not None]
        str_paths = [_item_path_serie(f)[0] for f in pending if _item_path_serie(f)[0] is not None]
        # Build series map: path -> serie_to_open for items that specify a series
        series_map = {_item_path_serie(f)[0]: _item_path_serie(f)[1]
                      for f in pending
                      if _item_path_serie(f)[0] is not None and _item_path_serie(f)[1] is not None}

        if not str_paths:
            self.statusBar().clearMessage()
            callback([f for f in pending if _item_path_serie(f)[0] is None])
            return

        from batoolset.img import is_video_file
        if any(is_video_file(p) for p in str_paths):
            # no video reader at all: offer PyAV (bundles ffmpeg) before loading
            from pyfigures.gui.video_support import offer_video_support
            offer_video_support(self, 'read')

        n_total = len(str_paths)
        loaded_imgs = {}  # path -> Img or None; written by worker, read on main thread
        n_done = [0]

        self.pbar.setRange(0, n_total)
        self.pbar.setValue(0)
        self.pbar.show()
        self.statusBar().showMessage(f'Loading 0/{n_total} image(s)...')
        QApplication.setOverrideCursor(Qt.WaitCursor)

        def _on_img_ready(path):
            if not _qt_alive(self):
                return  # the window was destroyed while images were loading
            n_done[0] += 1
            self.pbar.setValue(n_done[0])
            self.statusBar().showMessage(f'Loading {n_done[0]}/{n_total} image(s)...')

        def _on_finished():
            if not _qt_alive(self):
                return
            QApplication.restoreOverrideCursor()
            self.pbar.hide()
            self.statusBar().clearMessage()
            result = []
            for item in pending:
                path, serie = _item_path_serie(item)
                if path is not None:
                    img = loaded_imgs.get(path)
                    Image2D._lazy_mode = True
                    try:
                        img2d = Image2D(path, serie_to_open=serie)
                    finally:
                        Image2D._lazy_mode = False
                    if img is not None:
                        img2d.img = img
                        img2d.update_qimage()
                else:
                    img2d = item
                result.append(img2d)
            callback(result)
            thread.quit()
            try:
                self._active_img_loaders.remove((thread, worker))
            except (ValueError, AttributeError):
                pass

        worker = _ImgLoaderWorker(str_paths, loaded_imgs, series_map=series_map)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.img_ready.connect(_on_img_ready, Qt.QueuedConnection)
        # end the thread from the worker itself: a queued quit needs the GUI event
        # loop, and a still-running QThread destroyed at exit crashes the process
        worker.finished.connect(thread.quit, Qt.DirectConnection)
        worker.finished.connect(_on_finished, Qt.QueuedConnection)
        thread.finished.connect(thread.deleteLater)
        # Keep Python references alive until the thread finishes (prevents GC)
        if not hasattr(self, '_active_img_loaders'):
            self._active_img_loaders = []
        self._active_img_loaders.append((thread, worker))
        thread.start()

    def _show_series_dialog(self, filename, series_names):
        """Show a dialog asking the user which series to open.

        Returns the selected series index (int) or None if the user cancels."""
        from qtpy.QtWidgets import QDialog, QVBoxLayout, QLabel, QListWidget, QPushButton, QHBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Select Series")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
        layout = QVBoxLayout(dlg)

        basename = os.path.basename(filename)
        layout.addWidget(QLabel(
            f"<b>{basename}</b> contains <b>{len(series_names)}</b> series.<br>"
            f"Select the series to open:"
        ))

        list_widget = QListWidget()
        for i, name in enumerate(series_names):
            list_widget.addItem(f"[{i}] {name}")
        list_widget.setCurrentRow(0)
        layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("Open")
        skip_btn = QPushButton("Skip file")
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(skip_btn)
        layout.addLayout(btn_layout)

        result = [None]

        def on_ok():
            result[0] = list_widget.currentRow()
            dlg.accept()

        ok_btn.clicked.connect(on_ok)
        skip_btn.clicked.connect(dlg.reject)
        list_widget.itemDoubleClicked.connect(lambda _: on_ok())

        dlg.exec_()
        return result[0]

    def _resolve_series_for_files(self, filenames):
        """Check each file for multiple series and ask the user to pick one if needed.

        Returns a new list where multi-series files are replaced with
        (filename, serie_index) tuples.  Files skipped by the user are omitted."""
        result = []
        for f in filenames:
            if not isinstance(f, str):
                result.append(f)
                continue
            if is_forbidden_image_file(f):
                # sidecar/companion file (e.g. Leica .lifext) — not a real image
                logger.warning('Skipping unsupported companion file: ' + os.path.basename(f) +
                               ' - open the .lif file itself, not its sidecar.')
                continue
            try:
                n, names = get_series_info(f)
            except Exception:
                n, names = 1, None
            if n > 1:
                serie_idx = self._show_series_dialog(f, names)
                if serie_idx is None:
                    continue  # user chose to skip this file
                result.append((f, serie_idx))
            else:
                result.append(f)
        return result

    def all_images_directly(self, lst):
        if not lst:
            return
        self._load_images_then_callback(lst, self._finish_add_single_images)

    def _finish_add_single_images(self, img2d_list):
        for img2d in img2d_list:
            self.paint.EZFIG_panel.shapes_to_draw.append(img2d)
            self.paint.EZFIG_panel.force_update_size_of_parent.emit(img2d)
            self.paint.EZFIG_panel.force_update_size_of_parent.emit(img2d)
        self.paint.EZFIG_panel.update()
        self.paint.EZFIG_panel.update_size()
        if self.paint.EZFIG_panel.shapes_to_draw:
            self.paint.EZFIG_panel.set_current_selection(self.paint.EZFIG_panel.shapes_to_draw[-1])
        self.paint.EZFIG_panel.update_letters_required.emit()
        self.paint.EZFIG_panel.update_text_rows.emit()
        self.paint.EZFIG_panel.focus_required.emit()
        if self.paint.EZFIG_panel.shapes_to_draw:
            self.paint.EZFIG_panel.set_current_selection(self.paint.EZFIG_panel.shapes_to_draw[-1])
        self.paint.EZFIG_panel.undo_redo_save_required.emit()

    def create_panel(self, lst):
        # Pre-load Image2D objects one per event-loop tick; once all are ready,
        # show the panel-layout dialog with Image2D objects (not raw filenames) so
        # Group.__init__ won't re-load them.
        self._load_images_then_callback(lst,
            lambda imgs: QTimer.singleShot(300, lambda: self.paint.EZFIG_panel._create_panel_real(imgs)))

    def add_image_from_url_action(self):
        """File > Add image from URL / OME-Zarr / OMERO…: one image, added as a
        new row. For OME-Zarr the pyramid level is chosen from the image's own
        levels; an OMERO link may need a login and, for a big stack, a choice
        of planes."""
        url, ok = QInputDialog.getText(
            self, 'Add image from URL / OME-Zarr / OMERO',
            'Image URL, OME-Zarr URL (…/image.zarr), local .zarr folder,\n'
            'or the OMERO.web link of an image (…/webclient/img_detail/ID/):')
        url = (url or '').strip()
        if not ok or not url:
            return
        from pyfigures.path_resolution import source_exists
        if not source_exists(url):
            QMessageBox.warning(self, 'Not found', f'No image found at:\n{url}')
            return
        from batoolset import omero_web as O
        if O.is_omero_url(url):
            url = self._prepare_omero_url(url)
            if url:
                self.add_images_to_new_row([url])
            return
        if url.split('#', 1)[0].rstrip('/\\').lower().endswith('.zarr'):
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                from batoolset import ome_zarr as Z
                info = Z.describe(url)
                default_level = Z.level_size(url)[0]
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, 'Cannot read OME-Zarr', f'{url}\n\n{type(e).__name__}: {e}')
                return
            QApplication.restoreOverrideCursor()
            names = [str(n).lower() for n in info['axes']]
            items = []
            for lv in info['levels']:
                sh = lv['shape']
                w = sh[names.index('x')] if 'x' in names else sh[-1]
                h = sh[names.index('y')] if 'y' in names else sh[-2]
                px = ''
                if 'x' in names:
                    i = names.index('x')
                    unit = (info['units'][i] or 'micrometer').lower()
                    px = f", {lv['scale'][i] * Z._UNIT_TO_UM.get(unit, 1.0):.3g} µm/px"
                items.append(f"Level {lv['level']}: {w} × {h} px{px}")
            if len(items) > 1:
                item, ok = QInputDialog.getItem(self, 'Pyramid level',
                                                'Resolution to read (level 0 = full):',
                                                items, default_level, False)
                if not ok:
                    return
                level = items.index(item)
                base = url.split('#', 1)[0]
                url = base if level == default_level else f'{base}#level={level}'
        self.add_images_to_new_row([url])

    def omero_login(self, base):
        """Ask for an OMERO user name and password and log in (session kept in
        memory only). Returns True once logged in, False if cancelled."""
        from batoolset import omero_web as O
        for _ in range(3):
            user, ok = QInputDialog.getText(self, 'OMERO login', f'User name on {base}:')
            if not ok or not user.strip():
                return False
            password, ok = QInputDialog.getText(self, 'OMERO login', f'Password for {user.strip()}:',
                                                QLineEdit.EchoMode.Password)
            if not ok:
                return False
            try:
                O.login(base, user.strip(), password)
                return True
            except Exception as e:
                QMessageBox.warning(self, 'OMERO login failed', str(e))
        return False

    def _prepare_omero_url(self, url):
        """The OMERO link to add (canonical form + plane selection), after any
        login and, for a stack too big to read whole, the choice of planes.
        None if cancelled or unreadable."""
        from batoolset import omero_web as O
        fragment = url.split('#', 1)[1] if '#' in url else ''
        while True:
            base, image_id = O.parse_omero_url(url)
            url = O.canonical_url(base, image_id) + (f'#{fragment}' if fragment else '')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                info = O.describe(url)
            except O.OmeroLoginRequired as e:
                QApplication.restoreOverrideCursor()
                if not self.omero_login(e.base):
                    return None
                continue
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, 'Cannot read the OMERO image', f'{url}\n\n{type(e).__name__}: {e}')
                return None
            QApplication.restoreOverrideCursor()
            size = info['size']
            n_bytes = size['width'] * size['height'] * info['rendered_planes'] * 2
            if info['rendered_planes'] <= O.MAX_PLANES and n_bytes <= O.DEFAULT_MAX_BYTES:
                return url
            default = f"z=0-{size['z'] - 1}&t=0" if size['z'] > 1 else 't=0'
            fragment, ok = QInputDialog.getText(
                self, 'Planes to read',
                f"{info['name'] or 'This image'} has {size['z']} Z × {size['t']} T × {size['c']} C "
                f"planes of {size['width']} × {size['height']} px: too many to read at once.\n"
                'Planes to read (z, t, c: e.g. z=0-9&t=0, or t=0,10,20&c=0,2):', text=default)
            fragment = (fragment or '').strip().lstrip('#')
            if not ok or not fragment:
                return None

    def _equation_dialog(self, **settings):
        """Run the equation dialog; return its values, or None if cancelled."""
        from pyfigures.gui.equation_dialog import EquationDialog
        dlg = EquationDialog(self, **settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.values()

    def _write_equation(self, v):
        from pyfigures import equations as E
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            engine = v.get('engine', 'mathtext')
            return E.make_equation(self.current_file, v['latex'], v['font_size'], v['color'],
                                   v['fontset'], engine, v.get('preamble'),
                                   v.get('font') if engine == 'latex' else None)
        except ValueError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, 'Cannot typeset the equation', str(e))
            return None
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

    def _equation_from_tex(self, tex_path):
        """A dropped .tex file -> the path of its panel (or None). A whole
        document (\\documentclass…: TikZ, a figure with \\includegraphics, a
        table) is compiled by LaTeX into a PDF panel (pyfigures.latex_document);
        a snippet is an equation, typeset with the LaTeX installation if there
        is one (full LaTeX), else its first formula with Matplotlib's mathtext."""
        from pyfigures import equations as E
        from pyfigures import latex_document as LD
        try:
            with open(tex_path, encoding='utf-8', errors='replace') as f:
                full = LD.is_full_document(f.read())
        except OSError as e:
            QMessageBox.warning(self, 'Cannot read the .tex file', str(e))
            return None
        if full:
            if E.find_tex_tool('pdflatex') is None:
                from pyfigures.gui.latex_support import offer_latex_install
                if not offer_latex_install(self, 'A .tex document is compiled by LaTeX'):
                    return None
            part = None
            try:
                parts = LD.parts_of(tex_path)
            except (OSError, ValueError):
                parts = []
            if len(parts) > 1:
                # several figures / tables / pictures: which one?
                names = [d for d, _ in parts]
                choice, ok = QInputDialog.getItem(
                    self, 'LaTeX document',
                    f'{os.path.basename(tex_path)} has {len(parts)} parts. Which one is the panel?',
                    names, 0, False)
                if not ok:
                    return None
                part = names.index(choice) + 1
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                return LD.make_document_panel(self.current_file, tex_path, part)
            except ValueError as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, 'Cannot compile the .tex document', str(e))
                return None
            finally:
                if QApplication.overrideCursor() is not None:
                    QApplication.restoreOverrideCursor()
        try:
            latex = E.read_tex_file(tex_path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, 'Cannot read the .tex file', str(e))
            return None
        if E.latex_available():
            v = {'latex': latex, 'font_size': 12.0, 'color': 'black', 'fontset': 'cm',
                 'engine': 'latex', 'preamble': E.DEFAULT_PREAMBLE}
        else:
            v = {'latex': E.mathtext_formula(latex), 'font_size': 12.0, 'color': 'black',
                 'fontset': 'cm', 'engine': 'mathtext'}
        return self._write_equation(v)

    def add_equation_action(self):
        """File > Add equation (LaTeX)…: the equation is added as a new row."""
        v = self._equation_dialog()
        if not v:
            return
        path = self._write_equation(v)
        if path:
            self.add_images_to_new_row([path])

    def edit_equation(self, shape):
        """Right-click > Edit equation…: retypeset *shape*'s equation in place
        (same displayed height to start with), then reflow the figure so every
        row keeps its width."""
        from pyfigures import equations as E
        settings = E.read_settings(getattr(shape, 'filename', None) or '')
        if settings is None:
            return
        v = self._equation_dialog(**settings)
        if not v:
            return
        path = self._write_equation(v)
        if not path or os.path.abspath(path) == os.path.abspath(shape.filename):
            return
        shown_height = shape.height()
        shape.filename = path
        shape.setFigure(path)
        size = shape.renderer.defaultSize()
        shape.setWidth(size.width())
        shape.setHeight(size.height())
        if shown_height > 0:
            shape.setToHeight(shown_height)
        self._lazy_size_drift = True
        self._reflow_after_lazy_load()
        self.paint.EZFIG_panel.update_size()
        self.paint.EZFIG_panel.update()
        self._mark_dirty()

    def _latex_code_dialog(self, code=""):
        """Run the LaTeX code dialog until the code compiles (or it is
        cancelled); returns (code, pdf) or None."""
        from pyfigures.gui.latex_code_dialog import LatexCodeDialog
        from pyfigures.gui.latex_support import offer_latex_install
        if not offer_latex_install(self, 'A LaTeX code panel is compiled by LaTeX') and not code:
            return None
        dlg = LatexCodeDialog(self, code)
        while dlg.exec() == QDialog.DialogCode.Accepted:
            if not dlg.update_preview():
                continue                          # show the error, let the user fix it
            from pyfigures.latex_document import latex_code_pdf
            return dlg.code(), latex_code_pdf(dlg.code())
        return None

    def add_latex_code_action(self, *_):
        """File > Add LaTeX code panel…: a panel whose script is LaTeX code
        (MCP: add_latex_code), added as a new row."""
        res = self._latex_code_dialog()
        if not res:
            return None
        code, _ = res
        img2d = Image2D(custom_loading_script=code)
        if img2d.renderer is None:
            QMessageBox.warning(self, 'LaTeX code', img2d.script_log or 'The code could not be compiled.')
            return None
        panel = self.paint.EZFIG_panel
        panel._add_as_new_group([img2d], orientation='X', remove_from_parents=False)
        panel.update_size()
        panel.update()
        panel.set_current_selection(img2d)
        panel.update_letters_required.emit()
        panel.undo_redo_save_required.emit()
        self._mark_dirty()
        return img2d

    def edit_latex_code(self, shape):
        """Right-click > Edit LaTeX code…: change a LaTeX code panel's code and
        show the new result in place (same displayed height)."""
        res = self._latex_code_dialog(shape.custom_loading_script or '')
        if not res:
            return False
        code, pdf = res
        if code == shape.custom_loading_script:
            return False
        shown_height = shape.height()
        shape.custom_loading_script = code
        shape._show_script_file(pdf)
        if shown_height > 0:
            shape.setToHeight(shown_height)
        self._lazy_size_drift = True
        self._reflow_after_lazy_load()
        self.paint.EZFIG_panel.update_size()
        self.paint.EZFIG_panel.update()
        self._mark_dirty()
        return True

    def add_images_to_new_row(self, lst):
        self._load_images_then_callback(lst,
            lambda imgs: self.paint.EZFIG_panel._add_as_new_group(imgs, orientation='X', remove_from_parents=False))

    def add_images_to_new_col(self, lst):
        self._load_images_then_callback(lst,
            lambda imgs: self.paint.EZFIG_panel._add_as_new_group(imgs, orientation='Y', remove_from_parents=False))

    def add_images_combined_with_target(self, lst, target, orientation='X'):
        """Combine the dropped image(s) with an existing on-canvas *target* shape
        into a new row/column group, placing the target first then the dropped
        image(s). Used when a file is dropped ONTO an existing image/group."""
        def _combine(imgs):
            # target still on canvas? (it may have been removed meanwhile) — if not,
            # just add the dropped images as a new group on their own
            panel = self.paint.EZFIG_panel
            combined = ([target] + imgs) if target is not None else imgs
            panel._add_as_new_group(combined, orientation=orientation, remove_from_parents=True)
        self._load_images_then_callback(lst, _combine)

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

    # ── file-state helpers (dirty flag, title, save-before-discard) ──────────
    def _update_window_title(self):
        """Reflect the current file and unsaved-changes state in the title bar."""
        try:
            name = os.path.basename(self.current_file) if self.current_file else 'Untitled'
            marker = ' •' if getattr(self, '_dirty', False) else ''
            self.setWindowTitle(f'{name}{marker} — {__NAME__} v{__VERSION__}')
        except Exception:
            self.setWindowTitle(__NAME__ + ' v' + str(__VERSION__))

    def _mark_dirty(self):
        if not getattr(self, '_dirty', False):
            self._dirty = True
            self._update_window_title()

    def _mark_clean(self):
        self._dirty = False
        self._update_window_title()

    def _maybe_save_before_discard(self, action_label='continuing'):
        """If there are unsaved changes, ask the user. Returns True if the caller
        may proceed (saved or explicitly discarded), False to cancel the action."""
        if not getattr(self, '_dirty', False):
            return True
        reply = QMessageBox.warning(
            self, 'Unsaved changes',
            f'This figure has unsaved changes. Save before {action_label}?',
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save)
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Discard:
            return True
        # Save: proceed only if the save actually completed (user may cancel the
        # save dialog, or the write may fail)
        return bool(self.save_pyfigures())

    def open_figure(self, append=False):
        """User-initiated Open. Replacing the figure (append=False) prompts to
        save first; merging (append=True) does not discard anything."""
        if not append and not self._maybe_save_before_discard('opening another figure'):
            return
        self.reload_state(path_to_xml_file=None, append=append)

    def save_state(self, show_popup=True):
        if self.undo_stack and self.current_index < len(self.undo_stack):
            # User is undoing or redoing, do not save the state
            return

        # This is the debounced undo-checkpoint save (fired from a Qt timer/slot).
        # Guard it so a failure here (e.g. disk full, serialization error) degrades
        # to a status-bar warning instead of propagating out of the slot — an
        # unhandled exception in a slot makes PyQt6 abort the app with 0xC0000409.
        try:
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

            # a new checkpoint means the figure changed since it was last saved to
            # a real file (init/load paths call _mark_clean() right after to reset)
            self._mark_dirty()

            return self.last_called_state
        except Exception:
            logger.error('Could not save undo checkpoint:\n' + traceback.format_exc())
            try:
                self.statusBar().showMessage('Could not save undo checkpoint (see log).')
            except Exception:
                pass
            return None

        # print('save state called', self.undo_stack)

    def _flush_pending_checkpoints(self):
        """An edit made less than 0.8 s ago (spacing spinner, a move) is still
        waiting for its debounced undo checkpoint. Record it now: otherwise the
        checkpoint landed AFTER the undo/redo, re-applied the edit and wiped
        the redo history."""
        spin_timer = getattr(self, 'main_space_spinner_changed_timer', None)
        if spin_timer is not None and spin_timer.isActive():
            spin_timer.stop()
            self.update_space_and_paint()
        panel_timer = getattr(self.paint.EZFIG_panel, 'timer', None)
        if panel_timer is not None and panel_timer.isActive():
            panel_timer.stop()
            self.paint.EZFIG_panel.emit_undo_redo_save_required()

    def undo(self):
        self._flush_pending_checkpoints()
        recall_required = False
        if not (self.undo_stack and 0 < self.current_index <= len(self.undo_stack)):
            self.update_button_state()
            return              # nothing to undo: not an edit, the figure stays clean
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
        self._mark_dirty()  # undone state differs from the last saved file

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
        self._flush_pending_checkpoints()
        recall_required = False
        if not self.redo_stack:
            self.update_button_state()
            return              # nothing to redo
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
        self._mark_dirty()  # redone state differs from the last saved file
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

            if path_to_xml_file:
                # Load in the background with progressive image display (same fast path
                # as drag-and-drop): the layout appears immediately and images fill in
                # one by one. The security prompt for script files and the undo reset
                # happen in _on_pyf_file_ready.
                self._start_pyf_loader([path_to_xml_file], append=append, reset_undo=True)
            return

        if path_to_xml_file:
            xml_string = read_string_from_file(path_to_xml_file)

            if os.path.exists(smart_name_parser(path_to_xml_file, 'full_no_ext') + '.files'):
                # replace all names in files with consolidated ones
                # we fix all filenames at launch
                xml_string = _update_filename_of_consolidated_files(path_to_xml_file, xml_string)

                # print(xml_string)
            # figure moved to another folder / disk / OS: find its source files
            # relative to where the .pyf is now
            xml_string, _moved = resolve_moved_paths(xml_string, path_to_xml_file)
            if _moved:
                self._on_pyf_paths_relocated(path_to_xml_file, len(_moved))

            properties = deserialize_to_dict(xml_string)
            # print(properties)
            objects = create_object(list.__name__, properties)

            gui_params = None
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
                    self._set_page_background(getattr(elm, 'background', None))
                    gui_params = elm
                    objects.remove(elm)

            if append:
                self.paint.EZFIG_panel.shapes_to_draw.extend(objects)
            else:
                self.paint.EZFIG_panel.shapes_to_draw = objects
                self._restore_lettering(gui_params)
                self._bind_label_maths(path_to_xml_file)

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
        # offer to save unsaved changes before quitting
        if not self._maybe_save_before_discard('quitting'):
            event.ignore()
            return

        try:
            # Close the ColorAssistant if it exists
            if self.color_assistant is not None:
                self.color_assistant.close()
        except Exception:
            traceback.print_exc()

        # graceful shutdown: abandon progressive loads and join loader threads so
        # nothing is mid-flight when the process ends
        try:
            self._cancel_lazy_loading()
        except Exception:
            pass
        try:
            self._stop_all_img_loaders()
        except Exception:
            pass
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass
        if getattr(self, '_started_mcp_http', False):
            try:
                from pyfigures.gui.mcp_server_dialog import stop_autostarted_http_server
                stop_autostarted_http_server()
            except Exception:
                traceback.print_exc()
        try:
            self._cleanup_qc_temp_dirs()
            self._discard_sidecar_stash()
        except Exception:
            pass

        event.accept()
        # NB: do NOT os._exit here. Force-terminating on window close breaks
        # multi-window use and headless tests (which close throwaway GUIs). The
        # process is force-terminated once, after the Qt event loop returns, in
        # run_pyfigures() — that is where the ImageJ/JVM non-daemon threads (which
        # would otherwise hang the interpreter) are dealt with.

    def _login_to_omero_servers_of(self, pyf_list):
        """A figure with images on a private OMERO server: log in (once per
        server) before its images are read in the background."""
        import re as _re
        from batoolset import omero_web as O
        checked = set()
        for path in pyf_list:
            try:
                with open(path, encoding='utf-8', errors='replace') as f:
                    text = f.read()
            except OSError:
                continue
            for url in _re.findall(r'https?://[^"<>\s]+', text):
                parsed = O.parse_omero_url(url.replace('&amp;', '&'))
                if parsed is None or parsed[0] in checked:
                    continue
                checked.add(parsed[0])
                try:
                    O.image_data(url.replace('&amp;', '&'))
                except O.OmeroLoginRequired as e:
                    QApplication.restoreOverrideCursor()
                    self.omero_login(e.base)
                except Exception:
                    pass                  # unreachable server etc.: reported when the image loads

    def _start_pyf_loader(self, pyf_list, only_pyf_drop=False, append=True, reset_undo=False):
        """Start a background thread to load .pyf files without blocking the UI.

        append=False replaces the current figure with the first loaded file
        (File>Open toolbar behaviour); reset_undo resets the undo stack right
        before the objects are applied (interactive Open)."""
        self._login_to_omero_servers_of(pyf_list)
        # until _on_pyf_loading_done has run on this thread: the loader thread
        # can end before its queued results reach the window (wait_for_images)
        self._pyf_loads_pending = getattr(self, '_pyf_loads_pending', 0) + 1
        self._pyf_only_drop = only_pyf_drop
        self._pyf_append = append
        self._pyf_reset_undo_pending = reset_undo
        self._pyf_replace_pending = not append
        # when a single .pyf fully replaces the figure, remember it so Save writes
        # back to it (instead of prompting for a new filename)
        self._pyf_single_source = pyf_list[0] if (len(pyf_list) == 1 and not append) else None
        if not append:
            self._bind_label_maths(self._pyf_single_source)
        self.statusBar().showMessage('Loading .pyf file(s), please wait...')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        thread = QThread(self)
        worker = _PyfLoaderWorker(pyf_list)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.file_ready.connect(self._on_pyf_file_ready)
        worker.file_error.connect(self._on_pyf_file_error)
        worker.paths_relocated.connect(self._on_pyf_paths_relocated)
        worker.finished.connect(self._on_pyf_loading_done)
        # direct: the thread ends even if the GUI event loop never runs again
        worker.finished.connect(thread.quit, Qt.DirectConnection)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Keep a reference so GC doesn't destroy thread/worker before they finish
        self._pyf_loader_thread = thread
        self._pyf_loader_worker = worker
        thread.start()

    @Slot(str, int)
    def _on_pyf_paths_relocated(self, path, n):
        # the figure in memory now points at the files' new location; saving
        # stores those paths (the resolver maps them back on the other OS)
        self._n_paths_relocated = n
        logger.info(f'{os.path.basename(path)}: found {n} moved source file(s) '
                    f'relative to the .pyf location')
        self.statusBar().showMessage(
            f'Found {n} source file(s) at a new location relative to the figure.', 8000)

    @Slot(str, object, bool)
    def _on_pyf_file_ready(self, path, properties, has_script):
        try:
            if has_script:
                reply = QMessageBox.warning(self, 'Security Warning',
                                            '<span style="color: red;">The file contains custom script code. '
                                            'Opening this file may pose security risks, as it could execute untrusted or malicious code. '
                                            'Only proceed if you trust the source of the file and understand the implications.<br><br>'
                                            'Do you REALLY want to continue?</span>',
                                            QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    QApplication.restoreOverrideCursor()
                    self.statusBar().clearMessage()
                    return
                # user approved: only now parse the xml and build the objects (which
                # runs the scripts). Scripted files then take the SAME progressive path as
                # plain files: scripts run during create_object below, but regular
                # images are loaded lazily with progress feedback instead of blocking.
                properties = deserialize_to_dict(properties)
            if True:
                # Build objects without loading pixel data (lazy mode) so the canvas
                # appears instantly with correct layout, then load images progressively.
                if getattr(self, '_pyf_reset_undo_pending', False):
                    self._pyf_reset_undo_pending = False
                    self.activate_or_reset_undo_redo()
                Image2D._lazy_mode = True
                try:
                    objects = create_object(list.__name__, properties)
                finally:
                    Image2D._lazy_mode = False
                if getattr(self, '_pyf_replace_pending', False):
                    # File>Open replaces the current figure (only for the first file)
                    self._pyf_replace_pending = False
                    self._cancel_lazy_loading()  # drop pending loads from the figure being replaced
                    self.paint.EZFIG_panel.shapes_to_draw = []
                    self.paint.EZFIG_panel.set_current_selection(None)
                    self._set_page_background(None)
                self._apply_pyf_objects(objects)
                # Collect all Image2D objects that still need pixel data — including
                # those nested in Groups (content) and insets stored in annotations —
                # and queue progressive loading.
                pending = []
                stack = list(objects)
                while stack:
                    obj = stack.pop()
                    if isinstance(obj, Image2D):
                        if obj.filename is not None and obj.img is None and obj.filename != '@template@':
                            pending.append(obj)
                    if hasattr(obj, 'content') and obj.content:
                        stack.extend(obj.content)
                    annots = getattr(obj, 'annotations', None)
                    if annots:
                        stack.extend([a for a in annots if isinstance(a, Image2D)])
                if pending:
                    if not hasattr(self, '_lazy_img_queue'):
                        self._lazy_img_queue = []
                    queue_was_empty = not self._lazy_img_queue
                    self._lazy_img_queue.extend(pending)
                    if queue_was_empty:
                        self._lazy_img_done = 0
                        self._lazy_img_total = len(pending)
                        # reset the drift flag for this loading session (see
                        # _on_img_ready / _reflow_after_lazy_load)
                        self._lazy_size_drift = False
                    else:
                        self._lazy_img_total = getattr(self, '_lazy_img_total', 0) + len(pending)
                    self.pbar.setRange(0, self._lazy_img_total)
                    self.pbar.setValue(getattr(self, '_lazy_img_done', 0))
                    self.pbar.show()
                    self.statusBar().showMessage(f'Loading {getattr(self, "_lazy_img_done", 0)}/{self._lazy_img_total} image(s)...')
                    if queue_was_empty:
                        QTimer.singleShot(0, self._load_next_lazy_image)
                else:
                    # No images to lazy-load — clear the wait state now
                    QApplication.restoreOverrideCursor()
                    self.statusBar().clearMessage()
        except Exception:
            traceback.print_exc()
            logger.error('could not load ' + str(path))
            # clear the wait state and tell the user instead of spinning forever
            QApplication.restoreOverrideCursor()
            self.pbar.hide()
            self.statusBar().showMessage('Could not open ' + os.path.basename(str(path)))
            QMessageBox.warning(self, 'File could not be opened',
                                'The file could not be opened:\n' + str(path))

    def _load_next_lazy_image(self):
        """Load one pending Image2D's pixel data in a background thread, then continue."""
        if not getattr(self, '_lazy_img_queue', None):
            # Queue empty — nothing to load (or already exhausted); ensure cursor is restored.
            self._reflow_after_lazy_load()
            QApplication.restoreOverrideCursor()
            self.pbar.hide()
            self.statusBar().clearMessage()
            return
        # token for the current loading session; _cancel_lazy_loading() bumps it so
        # background reads that finish after a New/replace become no-ops
        gen = getattr(self, '_lazy_generation', 0)

        img2d = self._lazy_img_queue.pop(0)
        if img2d.filename is None or img2d.img is not None:
            if self._lazy_img_queue:
                QTimer.singleShot(0, self._load_next_lazy_image)
            else:
                # Queue exhausted via skips — restore cursor now.
                self._flush_lazy_refresh()
                self._reflow_after_lazy_load()
                QApplication.restoreOverrideCursor()
                self.pbar.hide()
                self.statusBar().clearMessage()
            return

        lazy_results = {}
        serie = getattr(img2d, 'serie_to_open', None)
        series_map = {img2d.filename: serie} if serie is not None else {}
        worker = _ImgLoaderWorker([img2d.filename], lazy_results, series_map=series_map)
        thread = QThread(self)
        worker.moveToThread(thread)

        def _on_img_ready(path):
            if not _qt_alive(self) or getattr(self, '_lazy_generation', 0) != gen:
                return  # window gone, or loading cancelled (New/replace) — discard
            img = lazy_results.get(path)
            if img is not None:
                # The fast layout was computed from the size stored in the .pyf
                # (get_raw_size() falls back to the serialized width/height while
                # img is None). If the real file on disk has since been resized or
                # replaced, its true size differs and the stored layout is stale —
                # remember that so _reflow_after_lazy_load() repacks it. Otherwise
                # the figure stays misaligned until the user nudges a size by hand.
                try:
                    old_w, old_h = img2d.get_raw_size()
                except Exception:
                    old_w, old_h = None, None
                img2d.img = img
                img2d.update_qimage()
                try:
                    new_w, new_h = img2d.get_raw_size()
                    if (old_w and old_h and
                            (abs(new_w - old_w) > 0.5 or abs(new_h - old_h) > 0.5)):
                        self._lazy_size_drift = True
                except Exception:
                    pass
            self._schedule_lazy_refresh()

        def _on_finished():
            if not _qt_alive(self):
                return  # the window was destroyed while this image was loading
            try:
                thread.quit()
            except RuntimeError:
                pass
            try:
                self._active_img_loaders.remove((thread, worker))
            except (ValueError, AttributeError):
                pass
            if getattr(self, '_lazy_generation', 0) != gen:
                return  # cancelled — do not advance progress or chain to the next image
            self._lazy_img_done = getattr(self, '_lazy_img_done', 0) + 1
            self._schedule_lazy_refresh()
            if self._lazy_img_queue:
                QTimer.singleShot(0, self._load_next_lazy_image)
            else:
                self._flush_lazy_refresh()
                self._reflow_after_lazy_load()
                QApplication.restoreOverrideCursor()
                self.pbar.hide()
                self.statusBar().clearMessage()

        worker.img_ready.connect(_on_img_ready, Qt.QueuedConnection)
        # direct: the thread ends even if the GUI event loop never runs again
        worker.finished.connect(thread.quit, Qt.DirectConnection)
        worker.finished.connect(_on_finished, Qt.QueuedConnection)
        thread.started.connect(worker.run)
        thread.finished.connect(thread.deleteLater)
        if not hasattr(self, '_active_img_loaders'):
            self._active_img_loaders = []
        self._active_img_loaders.append((thread, worker))
        thread.start()

    _LAZY_REFRESH_MS = 150

    def _schedule_lazy_refresh(self):
        """While images stream in, refresh the canvas and the progress display
        at most every _LAZY_REFRESH_MS. Refreshing per image redrew the WHOLE
        figure each time (QProgressBar.setValue repaints synchronously, flushing
        the pending canvas update too): 44 full repaints = 2.3 s of a 5.5 s open
        of a 61-panel figure."""
        timer = getattr(self, '_lazy_refresh_timer', None)
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(self._LAZY_REFRESH_MS)
            timer.timeout.connect(self._flush_lazy_refresh)
            self._lazy_refresh_timer = timer
        if not timer.isActive():
            timer.start()

    def _flush_lazy_refresh(self):
        timer = getattr(self, '_lazy_refresh_timer', None)
        if timer is not None:
            timer.stop()
        done = getattr(self, '_lazy_img_done', 0)
        n_total = getattr(self, '_lazy_img_total', 1)
        try:
            self.pbar.setValue(done)
            if done < n_total:
                self.statusBar().showMessage(f'Loading {done}/{n_total} image(s)...')
        except Exception:
            pass
        self.paint.EZFIG_panel.update()

    def _reflow_after_lazy_load(self):
        """Repack the figure after progressive image loading finishes, but only if
        a loaded image's true pixel size differed from the size assumed during the
        fast (stored-size) layout.

        The fast open path lays the figure out from the sizes stored in the .pyf so
        the canvas appears instantly, then streams in the real pixels. If a file on
        disk was resized/replaced since the .pyf was saved, its stored size is stale
        and the row it sits in stays misaligned until the user nudges a size by hand.
        Repacking each top-level group to its intended width here (the same
        set_to_width the manual resize uses) makes the figure self-correct on open.
        Repacking is idempotent for rows whose sizes did not drift."""
        if not getattr(self, '_lazy_size_drift', False):
            return
        self._lazy_size_drift = False
        try:
            for shape in list(self.paint.EZFIG_panel.shapes_to_draw):
                if isinstance(shape, Group) and not getattr(shape, 'isText', False):
                    target = getattr(shape, 'size', None) or shape.getRect(all=True).width()
                    set_to_width(shape, target)
            # realign side-label text rows to the (possibly changed) group heights;
            # this also calls update_size() + update() on the panel
            self.arrange_text_rows()
        except Exception:
            traceback.print_exc()

    def _cancel_lazy_loading(self):
        """Abandon any in-progress progressive image loading (e.g. when the user
        presses New or opens a replacement figure). The image queue is emptied and
        the loading generation is bumped, so a background read still in flight
        finishes and is discarded instead of flooding the UI thread with
        update_qimage()/repaint work for images no longer on the canvas."""
        self._lazy_generation = getattr(self, '_lazy_generation', 0) + 1
        self._lazy_img_queue = []
        QApplication.restoreOverrideCursor()
        try:
            self.pbar.hide()
        except Exception:
            pass
        try:
            self.statusBar().clearMessage()
        except Exception:
            pass

    def _stop_all_img_loaders(self, timeout_ms=30000):
        """Stop every background loader thread (.pyf parsing and image reads) and
        wait for it — on close / application quit. A QThread destroyed while
        still running takes the whole process down, so the workers are told to
        stop after their current file and joined (one image read is bounded;
        the timeout only guards against a hung reader)."""
        pairs = list(getattr(self, '_active_img_loaders', []))
        pyf_thread = getattr(self, '_pyf_loader_thread', None)
        if pyf_thread is not None:
            pairs.append((pyf_thread, getattr(self, '_pyf_loader_worker', None)))
        for thread, worker in pairs:
            try:
                if worker is not None:
                    worker.cancel()
                    # drop callbacks already queued for this window: delivered
                    # after the window is gone they touched freed widgets
                    for sig_name in ('img_ready', 'finished'):
                        try:
                            getattr(worker, sig_name).disconnect()
                        except (TypeError, RuntimeError, AttributeError):
                            pass
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(timeout_ms):
                        logger.error('a background loader thread did not stop in time')
            except RuntimeError:
                pass        # the C++ thread was already deleted (deleteLater)
        self._active_img_loaders = []
        self._pyf_loader_thread = None
        self._pyf_loader_worker = None

    @Slot(str, str)
    def _on_pyf_file_error(self, path, error_msg):
        logger.error('could not read ' + str(path) + ': ' + error_msg)
        # never leave the wait cursor spinning silently on a failed load
        QApplication.restoreOverrideCursor()
        self.pbar.hide()
        self.statusBar().showMessage('Could not open ' + os.path.basename(str(path)))
        QMessageBox.warning(self, 'File could not be opened',
                            'The file could not be opened:\n' + str(path) +
                            '\n\nReason: ' + str(error_msg))

    @Slot()
    def _on_pyf_loading_done(self):
        self._pyf_loads_pending = max(0, getattr(self, '_pyf_loads_pending', 0) - 1)
        source = getattr(self, '_pyf_single_source', None)
        if self._pyf_only_drop:
            # a .pyf dropped onto the canvas becomes an unsaved new composition
            self.current_file = None
            self.save_state(show_popup=False)
            self._mark_dirty()
        elif source:
            # opened a single file as a replacement: Save should write back to it
            self.current_file = source
            self._mark_clean()
            # after the loading returns to the event loop: report changed sources
            QTimer.singleShot(0, lambda p=source: self._warn_changed_sources(p))
        else:
            # merged / multi-file open: ambiguous target, treat as unsaved
            self.current_file = None
            self._mark_dirty()
        # safety net: if no progressive image loading is pending, make sure the
        # wait cursor set in _start_pyf_loader is cleared (e.g. after errors)
        if not getattr(self, '_lazy_img_queue', None) and not getattr(self, '_active_img_loaders', []):
            QApplication.restoreOverrideCursor()

    def _apply_pyf_objects(self, objects):
        """Apply pre-parsed .pyf objects to the canvas (runs on main thread)."""
        gui_params = None
        for elm in reversed(list(objects)):
            if isinstance(elm, SerializableQFont):
                self.serializable_font = elm
                objects.remove(elm)
            if isinstance(elm, SerializableGUIparameters):
                self.main_space_spinner.blockSignals(True)
                self.main_space_spinner.setValue(elm.space)
                self.paint.EZFIG_panel.space = elm.space
                self.main_space_spinner.blockSignals(False)
                self._set_page_background(getattr(elm, 'background', None))
                gui_params = elm
                objects.remove(elm)
        fresh = not self.paint.EZFIG_panel.shapes_to_draw
        self.paint.EZFIG_panel.shapes_to_draw.extend(objects)
        if fresh:                       # (merging into a figure keeps its lettering)
            self._restore_lettering(gui_params)
        self.paint.EZFIG_panel.set_current_selection(None)
        self.arrange_text_rows()
        self.paint.EZFIG_panel.update_size()
        self.paint.EZFIG_panel.update()
        if not self.undo_stack:
            # The undo baseline serializes the whole figure (0.8 s for 61 panels):
            # take it once the figure is on screen instead of before.
            QTimer.singleShot(0, self._initial_undo_checkpoint)

    def _initial_undo_checkpoint(self):
        """Deferred undo baseline after opening a figure. Taking a checkpoint
        normally marks the figure as modified; this one must not (opening is
        not an edit), and it is skipped if an edit already made a checkpoint."""
        if self.undo_stack:
            return
        was_dirty = getattr(self, '_dirty', False)
        self.save_state(show_popup=False)
        if not was_dirty:
            self._mark_clean()

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
                    except Exception:
                        before = None
                    try:
                        after_idx = idx + 1
                        if after_idx >= 0:
                            after = self.paint.EZFIG_panel.shapes_to_draw[after_idx]
                    except Exception:
                        after = None

                # Don't rely on isText direction: user can move label rows, making it stale.
                # Pick the adjacent neighbor that is a real image group (not isText).
                group_to_fit_to = None
                for candidate in (before, after):
                    if candidate is not None and not getattr(candidate, 'isText', False):
                        group_to_fit_to = candidate
                        break

                if isinstance(cur_sel, Image2D):
                    cur_sel=[cur_sel]

                if group_to_fit_to:
                    try:
                        indices_of_all_shapes = [elm.annotations[0].range for elm in cur_sel]
                        # print(indices_of_all_shapes, group_to_fit_to)

                        if any(r is None for r in indices_of_all_shapes):
                            indices_of_all_shapes = [[i, i] for i in range(len(indices_of_all_shapes))]
                            for elm, rng in zip(cur_sel, indices_of_all_shapes):
                                elm.annotations[0].range = rng

                        overlap_detected = areIndicesOverlapping(indices_of_all_shapes)

                        if overlap_detected:
                            logger.info('Overlapping annotation ranges detected — resetting to default sequential ranges.')
                            indices_of_all_shapes = [[i, i] for i in range(len(indices_of_all_shapes))]
                            for elm, rng in zip(cur_sel, indices_of_all_shapes):
                                elm.annotations[0].range = rng

                        # I should get rect corresponding to this
                        if isinstance(group_to_fit_to, Group):
                            # Use only non-text content (side labels are isText and must be ignored)
                            # Ranges are stored as non-text-relative indices, so index into filtered list
                            non_text_content = [e for e in group_to_fit_to.content if not getattr(e, 'isText', False)]
                            def _bounds_at_non_text(begin, end, _ntc=non_text_content):
                                n = len(_ntc)
                                if n == 0:
                                    return None
                                begin = max(0, min(begin, n - 1))
                                end = max(0, min(end, n - 1))
                                if begin > end:
                                    begin, end = end, begin
                                rects = [_ntc[i].getRect(all=True) for i in range(begin, end + 1)]
                                left = min(r.x() for r in rects)
                                top = min(r.y() for r in rects)
                                right = max(r.x() + r.width() for r in rects)
                                bottom = max(r.y() + r.height() for r in rects)
                                return QRectF(left, top, right - left, bottom - top)
                            bounding_rects_corresponding_to_indices = [_bounds_at_non_text(rng[0], rng[1]) for rng in indices_of_all_shapes]
                        else:
                            # for single images
                            bounding_rects_corresponding_to_indices = [group_to_fit_to.getRect(all=True)]

                        for iii, elm_dest in enumerate(cur_sel):
                            try:
                                # elm_dest = cur_sel[iii]
                                elm_dest.setWidth(bounding_rects_corresponding_to_indices[iii].width())
                                # elm_dest.setHeight(elm_src.height(scale=True))
                                elm_dest.set_to_scale(1)
                            except Exception:
                                # traceback.print_exc()
                                # print('not same size error, in theory I should remove all the extra texts of not plot them maybe -−> think of that --> cna I set width and height to None ???')
                                pass  # no big deal the guys can delete them if they don't need them anymore

                        if isinstance(cur_sel, Group):
                            try:
                                cur_sel.space=group_to_fit_to.space
                            except Exception:
                                cur_sel.space= 3

                            cur_sel.pack()
                            cur_sel.update_bounds()  # pack() repositions content but doesn't update the group's own QRectF


                        # finally I need to set it to parent width
                        # set_to_width(cur_sel, group_to_fit_to.width(scale=True))
                        if False:
                            for iii, elm in enumerate(cur_sel):
                                try:
                                    # elm.setHeight(max_h)
                                    print('final size', elm.getRect(), elm.getRect(all=True))
                                    elm_dest = group_to_fit_to[iii]
                                    print('final size src', elm_dest.getRect(), elm_dest.getRect(all=True))
                                except Exception:
                                    pass  # no big deal if fails --> it is just because things are out of bounds
                    except Exception:
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
        panel = self.paint.EZFIG_panel
        sel = panel.selected_shape
        if isinstance(sel, list) and len(sel) > 1:
            if any(elm not in panel.shapes_to_draw for elm in sel):
                # a panel inside a row/column: the right-click "To row / To
                # column" handles that (this used to raise ValueError in the slot)
                self.statusBar().showMessage(
                    'Combine works on whole top-level panels/rows; for panels inside a group '
                    'use right-click → To row / To column.', 8000)
                return
            new_group = Group(*sel, orientation=orientation)
            index = min(panel.shapes_to_draw.index(elm) for elm in sel)
            for elm in sel:
                panel.shapes_to_draw.remove(elm)
            # set_to_size(new_group, 512)
            panel.selected_shape = None  # reset selection
            self.selectionUpdated()
            panel.shapes_to_draw.insert(index, new_group)   # where the first one was, not at the end
            panel.update_size()
            panel.update()
            panel.undo_redo_save_required.emit()            # an edit: undoable, marks the figure modified

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
        except Exception:
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
        self.add_to_row.setIcon(get_icon('ri.layout-row-line'))
        self.add_to_row.setToolTip("add selection as a row")
        # self.add_to_row.clicked.connect(self.add_image)
        self.add_to_row.clicked.connect(self.combine_in_new_row)

        self.add_to_col = QPushButton('column')
        self.add_to_col.setToolTip("add selection as a column")
        self.add_to_col.setIcon(get_icon('ri.layout-column-line'))
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
        neo_list.append(SerializableGUIparameters(
            space=self.main_space_spinner.value(),
            background=self.paint.EZFIG_panel.page_background,
            first_letter=self.letter_line_edit.text() or None,
            auto_lettering=self.auto_lettering_checkbox.isChecked()))  # add GUI parameters
        xml_string = object_to_xml(neo_list, is_list=True)
        # atomic: an interrupted save leaves the previous .pyf intact
        from pyfigures.atomic_io import write_atomic
        write_atomic(file, xml_string, make_dirs=True)
        # the LaTeX-typeset maths of its labels go with it (equations/labels)
        try:
            from batoolset.latex_tools import save_used
            save_used(file)
        except Exception:
            logger.error('could not save the typeset label maths:\n' + traceback.format_exc())
        if popup:
            self.show_popup(popup)

    def new_fig(self):
        if not self._maybe_save_before_discard('creating a new figure'):
            return
        self._cancel_lazy_loading()  # stop any progressive image loading still in flight
        self.activate_or_reset_undo_redo()
        self.paint.EZFIG_panel.shapes_to_draw = []
        self.paint.EZFIG_panel.set_current_selection(None)
        self._set_page_background(None)
        self._bind_label_maths(None)
        self.paint.EZFIG_panel.update_size()
        self.paint.EZFIG_panel.update()
        self.paint.EZFIG_panel.undo_redo_save_required.emit()
        self.paint.EZFIG_panel.force_update_store.emit()
        self.current_file = None
        self._discard_sidecar_stash()  # a new figure starts without caption/stats
        self._mark_clean()  # brand-new empty figure — nothing to save yet

    def tidy_all_text(self):
        """Apply the conservative typography fixes to every text label in the
        figure (captions, side labels, letters). Tags/formatting are preserved."""
        from batoolset.strings.typography import tidy_html
        panel = self.paint.EZFIG_panel
        _, all_images = panel.get_full_list_ofimages2D_for_consolidation(
            exclude_images_without_filename=False, include_insets=True)
        # collect every TAText2D once (image annotations cover captions, side
        # labels and auto-letters — all text lives on an image in this model)
        seen, texts = set(), []
        for im in all_images:
            for a in (getattr(im, 'annotations', None) or []):
                if isinstance(a, TAText2D) and id(a) not in seen:
                    seen.add(id(a))
                    texts.append(a)
        changed = 0
        for t in texts:
            try:
                html = t.getHtmlText()
                new = tidy_html(html)
                if new != html:
                    t.setText(new)
                    changed += 1
            except Exception:
                logger.error('tidy_text failed on a label:\n' + traceback.format_exc())
        if changed:
            panel.update_size()
            panel.update()
            panel.undo_redo_save_required.emit()
            self.statusBar().showMessage(f'Tidied typography in {changed} text label(s).')
        else:
            self.statusBar().showMessage('Typography already tidy — no changes needed.')

    def add_colour_bar(self):
        """Ask for LUT / range / label, then insert a matching intensity
        calibration bar (colour bar) as a scripted panel on the canvas."""
        dlg = _ColourBarDialog(self)
        cd = CustomDialog(
            title="Add colour bar",
            message="Configure the intensity calibration bar, then press Ok.",
            main_widget=dlg, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        try:
            params = dlg.values()
            from pyfigures.colorbar_script import build_calibration_bar_script
            script = build_calibration_bar_script(**params)
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid colour bar', str(e))
            return

        try:
            img2d = Image2D(custom_loading_script=script)
        except Exception:
            logger.error('Could not build colour bar:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Colour bar failed',
                                'Could not build the colour bar (see log).')
            return

        # Insert like a single dropped panel (mirrors _finish_add_single_images).
        panel = self.paint.EZFIG_panel
        panel.shapes_to_draw.append(img2d)
        panel.force_update_size_of_parent.emit(img2d)
        panel.update()
        panel.update_size()
        panel.set_current_selection(img2d)
        panel.update_letters_required.emit()
        panel.update_text_rows.emit()
        panel.focus_required.emit()
        panel.undo_redo_save_required.emit()
        self.statusBar().showMessage(
            f"Added a {params['lut']} colour bar — drag it into place.")

    def add_channel_merge_action(self):
        """Pick N single-channel images + a colour each, then add a merged
        composite panel (MCP: add_channel_merge — a scripted, re-rendering panel)."""
        files = openFileNamesDialog(
            parent_window=self,
            extensions="Images (*.tif *.tiff *.png *.jpg *.jpeg *.czi *.lif *.lsm);;All Files (*)")
        if not files:
            return
        if len(files) < 2:
            QMessageBox.information(self, 'Need at least two channels',
                                   'Pick two or more single-channel images to merge.')
            return

        # colour-blind-safe defaults matching the MCP (1→gray, 2→green+magenta, 3→RGB)
        _defaults = {2: ['green', 'magenta'], 3: ['red', 'green', 'blue'],
                     4: ['red', 'green', 'blue', 'gray']}
        default_colors = _defaults.get(len(files),
                                       ['gray', 'green', 'magenta', 'red', 'blue',
                                        'cyan', 'yellow'][:len(files)])
        palette = ['gray', 'green', 'magenta', 'red', 'blue', 'cyan', 'yellow', 'white']

        frame = QFrame(self)
        grid = QGridLayout(frame)
        grid.addWidget(QLabel('<b>Channel</b>', frame), 0, 0)
        grid.addWidget(QLabel('<b>Colour</b>', frame), 0, 1)
        color_combos = []
        for i, f in enumerate(files):
            grid.addWidget(QLabel(os.path.basename(f), frame), i + 1, 0)
            cb = QComboBox(frame)
            cb.addItems(palette)
            cb.setCurrentText(default_colors[i] if i < len(default_colors) else palette[i % len(palette)])
            grid.addWidget(cb, i + 1, 1)
            color_combos.append(cb)
        row = len(files) + 1
        grid.addWidget(QLabel('Blend mode:', frame), row, 0)
        mode_combo = QComboBox(frame)
        mode_combo.addItems(['sum', 'max'])
        grid.addWidget(mode_combo, row, 1)
        grid.addWidget(QLabel('Intensity scaling:', frame), row + 1, 0)
        norm_combo = QComboBox(frame)
        norm_combo.addItem('Stretch each channel (min-max)', 'per_channel')
        norm_combo.addItem('Keep raw intensities', 'none')
        norm_combo.setToolTip('Stretching is a brightness/contrast adjustment and is '
                              'listed in the adjustment ledger. Keep raw intensities '
                              'to compare brightness between merges.')
        grid.addWidget(norm_combo, row + 1, 1)
        grid.addWidget(QLabel('Panel label:', frame), row + 2, 0)
        label_edit = QLineEdit('Merge', frame)
        grid.addWidget(label_edit, row + 2, 1)

        cd = CustomDialog(title="Add multi-channel merge",
                          message="Assign a colour to each channel, then press Ok.",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return

        from pyfigures.mcp_server import add_channel_merge
        self._run_mcp_mutation(
            add_channel_merge,
            f"Added a {len(files)}-channel merge — drag it into place.",
            group_path=[],
            channel_files=list(files),
            colors=[cb.currentText() for cb in color_combos],
            mode=mode_combo.currentText(),
            label=label_edit.text().strip() or None,
            normalization=norm_combo.currentData(),
        )

    def _locate_panel(self, target):
        """(group_path, image_index) of *target* in the figure as the MCP tools
        address it: groups counted among sibling Groups, images among sibling
        Image2D panels. None if not found (e.g. an inset)."""
        def search(items, path, top_level):
            imgs = [s for s in items if isinstance(s, Image2D)]
            if target in imgs:
                return path, imgs.index(target)
            groups = [s for s in items if isinstance(s, Group)]
            for gi, grp in enumerate(groups):
                found = search(list(grp.content), path + [gi], False)
                if found:
                    return found
            return None
        return search(list(self.paint.EZFIG_panel.shapes_to_draw), [], True)

    def add_zoom_callout_action(self):
        """Box a region of the selected image, magnify it in a corner inset and
        join them with leader lines (MCP: add_zoom_callout — exact geometry in the
        image's own pixel space, so the leaders land on the box corners)."""
        sel = self.paint.EZFIG_panel.selected_shape
        if isinstance(sel, list) and len(sel) == 1:
            sel = sel[0]
        if not isinstance(sel, Image2D) or sel.isText or sel.filename in (None, '@template@'):
            QMessageBox.information(self, 'Select an image',
                                    'Click one image panel first, then add the zoom callout.')
            return
        loc = self._locate_panel(sel)
        if loc is None:
            QMessageBox.information(self, 'Not supported',
                                    'Zoom callouts go on figure panels (not on insets).')
            return
        group_path, image_index = loc
        pw, ph = [int(round(v)) for v in sel.get_raw_size()]

        frame = QFrame(self)
        grid = QGridLayout(frame)
        spins = {}
        defaults = {'x': pw // 3, 'y': ph // 3, 'width': max(1, pw // 5),
                    'height': max(1, ph // 5)}
        for r, key in enumerate(('x', 'y', 'width', 'height')):
            grid.addWidget(QLabel(f'Region {key} (px):', frame), r, 0)
            sb = QSpinBox(frame)
            sb.setRange(0 if key in ('x', 'y') else 1, pw if key in ('x', 'width') else ph)
            sb.setValue(defaults[key])
            grid.addWidget(sb, r, 1)
            spins[key] = sb
        grid.addWidget(QLabel(f'Image is {pw} x {ph} px.', frame), 4, 0, 1, 2)
        grid.addWidget(QLabel('Inset corner:', frame), 5, 0)
        corner = QComboBox(frame)
        corner.addItems(['top right', 'top left', 'bottom right', 'bottom left'])
        grid.addWidget(corner, 5, 1)
        grid.addWidget(QLabel('Inset width (% of panel):', frame), 6, 0)
        frac = QSpinBox(frame)
        frac.setRange(10, 90)
        frac.setValue(40)
        grid.addWidget(frac, 6, 1)
        grid.addWidget(QLabel('Colour:', frame), 7, 0)
        colour = QComboBox(frame)
        colour.addItems(['yellow', 'white', 'cyan', 'magenta', 'red', 'green', 'black'])
        grid.addWidget(colour, 7, 1)
        grid.addWidget(QLabel('Leader lines:', frame), 8, 0)
        conn = QComboBox(frame)
        conn.addItems(['2', '1', '0'])
        grid.addWidget(conn, 8, 1)

        cd = CustomDialog(title="Add zoom callout",
                          message="Region of interest in image pixels (x, y = top-left corner).",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        x, y = spins['x'].value(), spins['y'].value()
        w = min(spins['width'].value(), pw - x)
        h = min(spins['height'].value(), ph - y)
        if w < 1 or h < 1:
            QMessageBox.warning(self, 'Invalid region', 'The region lies outside the image.')
            return
        from pyfigures.mcp_server import add_zoom_callout
        self._run_mcp_mutation(
            add_zoom_callout, "Zoom callout added.",
            group_path=group_path, image_index=image_index,
            source_x=x, source_y=y, source_w=w, source_h=h,
            parent_width=pw, parent_height=ph,
            inset_corner=corner.currentText(), inset_fraction=frac.value() / 100.0,
            box_color=colour.currentText(), line_color=colour.currentText(),
            connectors=int(conn.currentText()))

    # ------------------------------------------------------------------
    # Arrows and stack views (MCP: add_arrow, add_stack_montage,
    # add_channel_split, add_kymograph, add_orthogonal_views)
    # ------------------------------------------------------------------
    def _selected_image_panel(self, what):
        """(panel, group_path, image_index) of the single selected file-backed
        image panel, or None after telling the user what to select."""
        sel = self.paint.EZFIG_panel.selected_shape
        if isinstance(sel, list) and len(sel) == 1:
            sel = sel[0]
        if not isinstance(sel, Image2D) or sel.isText or not isinstance(sel.filename, str) \
                or sel.filename in ('', '@template@') or not os.path.isfile(sel.filename):
            QMessageBox.information(self, 'Select an image',
                                    f'Click one image panel first, then {what}.')
            return None
        loc = self._locate_panel(sel)
        if loc is None:
            QMessageBox.information(self, 'Not supported',
                                    'This works on figure panels (not on insets).')
            return None
        return sel, loc[0], loc[1]

    def _stack_info_or_warn(self, panel):
        from pyfigures.stack_info import stack_info, StackInfoError
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                return stack_info(panel.filename, getattr(panel, 'serie_to_open', None))
            finally:
                QApplication.restoreOverrideCursor()
        except StackInfoError as e:
            QMessageBox.warning(self, 'Cannot read the stack', str(e))
            return None

    @staticmethod
    def _spin(parent, lo, hi, value, double=False, decimals=3):
        sb = QDoubleSpinBox(parent) if double else QSpinBox(parent)
        if double:
            sb.setDecimals(decimals)
        sb.setRange(lo, hi)
        sb.setValue(value)
        return sb

    def add_arrow_action(self):
        """Arrow whose point lands exactly on a feature of the selected image."""
        found = self._selected_image_panel('add the arrow')
        if not found:
            return
        sel, group_path, image_index = found
        pw, ph = [int(round(v)) for v in sel.get_raw_size()]
        frame = QFrame(self)
        grid = QGridLayout(frame)
        tip_x = self._spin(frame, 0, pw, pw // 2)
        tip_y = self._spin(frame, 0, ph, ph // 2)
        grid.addWidget(QLabel('Tip x (px):', frame), 0, 0)
        grid.addWidget(tip_x, 0, 1)
        grid.addWidget(QLabel('Tip y (px):', frame), 1, 0)
        grid.addWidget(tip_y, 1, 1)
        grid.addWidget(QLabel(f'Image is {pw} x {ph} px; the arrow points AT this pixel.',
                              frame), 2, 0, 1, 2)
        direction = QComboBox(frame)
        direction.addItems(['top left', 'top', 'top right', 'right', 'bottom right',
                            'bottom', 'bottom left', 'left'])
        grid.addWidget(QLabel('Comes from:', frame), 3, 0)
        grid.addWidget(direction, 3, 1)
        length = self._spin(frame, 0, max(pw, ph), 0)
        length.setSpecialValueText('auto')
        grid.addWidget(QLabel('Length (px):', frame), 4, 0)
        grid.addWidget(length, 4, 1)
        colour = QComboBox(frame)
        colour.addItems(['white', 'yellow', 'cyan', 'magenta', 'red', 'green', 'black'])
        grid.addWidget(QLabel('Colour:', frame), 5, 0)
        grid.addWidget(colour, 5, 1)
        head = QComboBox(frame)
        head.addItems(['normal', 'small', 'large'])
        grid.addWidget(QLabel('Head:', frame), 6, 0)
        grid.addWidget(head, 6, 1)
        stroke = self._spin(frame, 0.1, 10, 1.0, double=True, decimals=2)
        grid.addWidget(QLabel('Line width (pt):', frame), 7, 0)
        grid.addWidget(stroke, 7, 1)
        label = QLineEdit('', frame)
        grid.addWidget(QLabel('Label at the tail:', frame), 8, 0)
        grid.addWidget(label, 8, 1)
        cd = CustomDialog(title="Add arrow", message="Point an arrow at a feature.",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        from pyfigures.mcp_server import add_arrow
        kw = dict(group_path=group_path, image_index=image_index,
                  tip_x=tip_x.value(), tip_y=tip_y.value(),
                  from_direction=direction.currentText(), color=colour.currentText(),
                  stroke=stroke.value(), head=head.currentText(),
                  label=label.text().strip() or None)
        if length.value() > 0:
            kw['length'] = float(length.value())
        self._run_mcp_mutation(add_arrow, "Arrow added.", **kw)

    def add_stack_montage_action(self):
        """Opt-in: show several frames of the selected stack as a row with
        time / depth stamps."""
        found = self._selected_image_panel('make the montage')
        if not found:
            return
        sel = found[0]
        info = self._stack_info_or_warn(sel)
        if info is None:
            return
        lead = info['order'][:info['order'].index('h')]
        axes = [(k, n) for k, n in (('t', 'Time'), ('d', 'Z')) if k in lead
                and info['sizes'][k] > 1]
        if not axes:
            QMessageBox.information(self, 'Not a stack',
                                    f"{os.path.basename(sel.filename)} has a single time "
                                    f"point and Z slice (dimensions {info['order']}).")
            return
        frame = QFrame(self)
        grid = QGridLayout(frame)
        axis = QComboBox(frame)
        for k, n in axes:
            axis.addItem(f"{n} ({info['sizes'][k]} frames)", 't' if k == 't' else 'z')
        grid.addWidget(QLabel('Frames along:', frame), 0, 0)
        grid.addWidget(axis, 0, 1)
        frames = QLineEdit('6', frame)
        frames.setToolTip('N = N evenly spaced frames; "all"; "0:20:5" (start:stop:step); '
                          'or a list "0, 4, 9"')
        grid.addWidget(QLabel('Which frames:', frame), 1, 0)
        grid.addWidget(frames, 1, 1)
        columns = self._spin(frame, 0, 100, 0)
        columns.setSpecialValueText('one row')
        grid.addWidget(QLabel('Panels per row:', frame), 2, 0)
        grid.addWidget(columns, 2, 1)
        proj = QComboBox(frame)
        proj.addItems(['max', 'avg', 'min', 'none'])
        grid.addWidget(QLabel('Z projection (time montage):', frame), 3, 0)
        grid.addWidget(proj, 3, 1)
        interval = self._spin(frame, 0, 1e6, float(info.get('interval') or 0), double=True)
        interval.setSpecialValueText('from file / frame numbers')
        grid.addWidget(QLabel('Time per frame:', frame), 4, 0)
        grid.addWidget(interval, 4, 1)
        unit = QLineEdit(info.get('time_unit') or '', frame)
        grid.addWidget(QLabel('Time unit:', frame), 5, 0)
        grid.addWidget(unit, 5, 1)
        stamps = QCheckBox('Stamp each frame (0 min, 2 min…)', frame)
        stamps.setChecked(True)
        grid.addWidget(stamps, 6, 0, 1, 2)
        keep_crop = self._keep_crop_checkbox(frame, sel)
        if keep_crop is not None:
            grid.addWidget(keep_crop, 7, 0, 1, 2)
        cd = CustomDialog(title="Stack montage",
                          message="Adds a new row showing several frames of the stack.",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        spec = frames.text().strip() or None
        if spec and spec.isdigit():
            spec = int(spec)
        ax = axis.currentData()
        kw = dict(stack_path=sel.filename, axis=ax, frames=spec,
                  columns=columns.value() or None, projection=proj.currentText(),
                  stamps=stamps.isChecked(),
                  series=getattr(sel, 'serie_to_open', None))
        if ax == 't' and interval.value() > 0:
            kw['interval'] = interval.value()
            kw['unit'] = unit.text().strip() or None
        if keep_crop is not None and keep_crop.isChecked():
            kw['crop'] = self._panel_crop(sel)
        from pyfigures.mcp_server import add_stack_montage
        self._run_mcp_mutation(add_stack_montage, "Montage added as a new row.", **kw)

    def add_channel_split_action(self):
        """Channel-split row (each channel + merge) from the selected
        multi-channel image, or from single-channel files picked now."""
        sel = self.paint.EZFIG_panel.selected_shape
        if isinstance(sel, list) and len(sel) == 1:
            sel = sel[0]
        stack_path, files, n = None, None, 0
        if isinstance(sel, Image2D) and isinstance(sel.filename, str) \
                and os.path.isfile(sel.filename):
            info = self._stack_info_or_warn(sel)
            if info is None:
                return
            n = info['sizes'].get('c', 1) if 'c' in info['order'] else 1
            if n > 1:
                stack_path = sel.filename
        if stack_path is None:
            picked = openFileNamesDialog(parent_window=self,
                                         extensions="Images (*.tif *.tiff *.png *.jpg);;All Files (*)")
            if not picked:
                return
            files = list(picked) if isinstance(picked, (list, tuple)) else [picked]
            n = len(files)
            if n < 2:
                QMessageBox.information(self, 'Channel split',
                                        'Select a multi-channel image, or pick one file per channel.')
                return
        defaults = {2: ['green', 'magenta'], 3: ['red', 'green', 'blue'],
                    4: ['red', 'green', 'blue', 'gray']}.get(n, ['gray'] * n)
        palette = ['gray', 'red', 'green', 'blue', 'cyan', 'magenta', 'yellow']
        frame = QFrame(self)
        grid = QGridLayout(frame)
        grid.addWidget(QLabel('<b>Name</b>', frame), 0, 0)
        grid.addWidget(QLabel('<b>Colour</b>', frame), 0, 1)
        names, colours = [], []
        for i in range(n):
            ne = QLineEdit(os.path.splitext(os.path.basename(files[i]))[0] if files
                           else f'Ch{i + 1}', frame)
            cb = QComboBox(frame)
            cb.addItems(palette)
            cb.setCurrentText(defaults[i])
            grid.addWidget(ne, i + 1, 0)
            grid.addWidget(cb, i + 1, 1)
            names.append(ne)
            colours.append(cb)
        gray = QCheckBox('Single channels in grayscale (names in colour)', frame)
        gray.setChecked(True)
        merge = QCheckBox('Add the merge', frame)
        merge.setChecked(True)
        grid.addWidget(gray, n + 1, 0, 1, 2)
        grid.addWidget(merge, n + 2, 0, 1, 2)
        keep_crop = self._keep_crop_checkbox(frame, sel) if stack_path else None
        if keep_crop is not None:
            grid.addWidget(keep_crop, n + 3, 0, 1, 2)
        cd = CustomDialog(title="Channel split", message="Adds a new row: each channel, then the merge.",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        from pyfigures.mcp_server import add_channel_split
        kw = dict(names=[e.text().strip() for e in names],
                  colors=[c.currentText() for c in colours],
                  gray=gray.isChecked(), include_merge=merge.isChecked())
        if stack_path:
            kw['stack_path'] = stack_path
            kw['series'] = getattr(sel, 'serie_to_open', None)
        else:
            kw['channel_files'] = files
        if keep_crop is not None and keep_crop.isChecked():
            kw['crop'] = self._panel_crop(sel)
        self._run_mcp_mutation(add_channel_split, "Channel split added as a new row.", **kw)

    @staticmethod
    def _panel_crop(panel):
        """The panel's crop as {side: pixels} (non-zero sides only)."""
        crop = {}
        for side in ('left', 'right', 'top', 'bottom'):
            v = int(round(float(getattr(panel, 'crop_' + side, 0) or 0)))
            if v > 0:
                crop[side] = v
        return crop

    def _keep_crop_checkbox(self, parent, panel):
        """'Keep this panel's crop' option of the split / montage dialogs (e.g.
        text burned into the image's bottom rows), or None if it is not cropped."""
        crop = self._panel_crop(panel)
        if not crop:
            return None
        box = QCheckBox('Crop every new panel like this one ('
                        + ', '.join(f'{k} {v} px' for k, v in crop.items()) + ')', parent)
        box.setChecked(True)
        return box

    def add_kymograph_action(self):
        found = self._selected_image_panel('add the kymograph')
        if not found:
            return
        sel, group_path, image_index = found
        info = self._stack_info_or_warn(sel)
        if info is None:
            return
        if info['sizes'].get('t', 1) < 2:
            QMessageBox.information(self, 'Not a time series',
                                    f"{os.path.basename(sel.filename)} has no time axis.")
            return
        W, H = info['sizes']['w'], info['sizes']['h']
        frame = QFrame(self)
        grid = QGridLayout(frame)
        spins = {}
        for r, (k, lim, v) in enumerate((('x1', W, W // 4), ('y1', H, H // 2),
                                         ('x2', W, 3 * W // 4), ('y2', H, H // 2))):
            spins[k] = self._spin(frame, 0, lim, v)
            grid.addWidget(QLabel(f'{k} (px):', frame), r, 0)
            grid.addWidget(spins[k], r, 1)
        width = self._spin(frame, 1, 51, 3)
        grid.addWidget(QLabel('Line width (px averaged):', frame), 4, 0)
        grid.addWidget(width, 4, 1)
        nch = info['sizes'].get('c', 1)
        channel = self._spin(frame, 0, max(0, nch - 1), 0)
        grid.addWidget(QLabel('Channel:', frame), 5, 0)
        grid.addWidget(channel, 5, 1)
        cd = CustomDialog(title="Kymograph",
                          message=f"Line on the image ({W} x {H} px); time runs downwards.",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        from pyfigures.mcp_server import add_kymograph
        self._run_mcp_mutation(
            add_kymograph, "Kymograph added next to the panel.",
            group_path=group_path, image_index=image_index,
            x1=spins['x1'].value(), y1=spins['y1'].value(),
            x2=spins['x2'].value(), y2=spins['y2'].value(),
            line_width=width.value(), channel=channel.value() if nch > 1 else None)

    def add_orthogonal_views_action(self):
        found = self._selected_image_panel('add orthogonal views')
        if not found:
            return
        sel, group_path, image_index = found
        info = self._stack_info_or_warn(sel)
        if info is None:
            return
        Z = info['sizes'].get('d', 1)
        if Z < 2:
            QMessageBox.information(self, 'Not a Z stack',
                                    f"{os.path.basename(sel.filename)} has no Z axis.")
            return
        W, H = info['sizes']['w'], info['sizes']['h']
        frame = QFrame(self)
        grid = QGridLayout(frame)
        x = self._spin(frame, 0, W - 1, W // 2)
        y = self._spin(frame, 0, H - 1, H // 2)
        z = self._spin(frame, -1, Z - 1, -1)
        z.setSpecialValueText('max projection')
        zs_default = (info['vz'] / info['vx']) if info.get('vz') and info.get('vx') else 1.0
        zs = self._spin(frame, 0.01, 100, zs_default, double=True)
        for r, (lab, w) in enumerate((('Cut at x (px):', x), ('Cut at y (px):', y),
                                      ('XY slice z:', z), ('Z step / pixel size:', zs))):
            grid.addWidget(QLabel(lab, frame), r, 0)
            grid.addWidget(w, r, 1)
        cd = CustomDialog(title="Orthogonal views",
                          message=f"{W} x {H} px, {Z} slices. XY + YZ (right) + XZ (below).",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        from pyfigures.mcp_server import add_orthogonal_views
        self._run_mcp_mutation(
            add_orthogonal_views, "Orthogonal views added next to the panel.",
            group_path=group_path, image_index=image_index, x=x.value(), y=y.value(),
            z=z.value() if z.value() >= 0 else None, z_scale=zs.value())

    # ------------------------------------------------------------------
    # Changed sources, copy style, alt text
    # ------------------------------------------------------------------
    def _warn_changed_sources(self, pyf_path):
        """After opening a saved figure: tell the user if source files changed
        since it was saved (the figure now shows the new versions)."""
        try:
            from pyfigures.source_snapshot import compare, describe
            text = describe(compare(pyf_path))
        except Exception:
            logger.error('source check failed:\n' + traceback.format_exc())
            return
        if text:
            self.statusBar().showMessage('Some source files changed since the figure was saved.',
                                         10000)
            QMessageBox.information(
                self, 'Source files changed',
                text + '\n\nThe figure shows the current files. Saving accepts them as '
                       'the new reference (QC → Check for changed source files).')
        self._offer_to_recompile_latex_panels()

    def _stale_latex_panels(self):
        """Panels compiled from a .tex document that changed since."""
        from pyfigures.latex_document import is_stale
        try:
            _, images = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(
                exclude_images_without_filename=False, include_insets=True)
        except Exception:
            return []
        return [im for im in images if isinstance(getattr(im, 'filename', None), str)
                and is_stale(im.filename)]

    def _offer_to_recompile_latex_panels(self):
        stale = self._stale_latex_panels()
        if not stale:
            return
        answer = QMessageBox.question(
            self, 'LaTeX documents changed',
            f'{len(stale)} panel(s) come from .tex documents that changed since they were '
            'compiled. Recompile them now?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes)
        if answer == QMessageBox.StandardButton.Yes:
            for shape in stale:
                self.recompile_latex_panel(shape, quiet=True)

    def recompile_latex_panel(self, shape, quiet=False):
        """Right-click → Recompile from .tex: compile the panel's .tex document
        again (pyfigures.latex_document) and show the new version in place."""
        from pyfigures import latex_document as LD
        src = LD.source_of(getattr(shape, 'filename', '') or '')
        if not src or not os.path.isfile(src):
            if not quiet:
                QMessageBox.warning(self, 'Cannot recompile',
                                    f'The .tex document of this panel was not found:\n{src}')
            return False
        part = LD.part_of(shape.filename)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            path = LD.document_pdf_path(self.current_file, src, part)
            if os.path.isfile(path):
                os.remove(path)                       # compile again, whatever the reason
            path = LD.make_document_panel(self.current_file, src, part)
        except (OSError, ValueError) as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, 'Cannot compile the .tex document', str(e))
            return False
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self._replace_panel_file(shape, path)
        return True

    def _replace_panel_file(self, shape, path):
        """Show *path* in the panel *shape* instead of its file, at the same
        displayed height, then reflow so every row keeps its width."""
        shown_height = shape.height()
        shape.filename = path
        shape.setFigure(path)
        size = shape.renderer.defaultSize() if getattr(shape, 'renderer', None) is not None else None
        if size is not None and size.width() > 0:
            shape.setWidth(size.width())
            shape.setHeight(size.height())
        if shown_height > 0:
            shape.setToHeight(shown_height)
        self._lazy_size_drift = True
        self._reflow_after_lazy_load()
        self.paint.EZFIG_panel.update_size()
        self.paint.EZFIG_panel.update()
        self._mark_dirty()

    def check_source_changes_action(self):
        """Report source files changed since the last save; offer to re-read
        them now (images are otherwise read when the figure is opened)."""
        from pyfigures.source_snapshot import compare, describe, figure_sources
        if not self.current_file:
            QMessageBox.information(self, 'Save the figure first',
                                    'Changes are tracked from the last save of the figure.')
            return
        try:
            p = self._save_current_to_temp_pyf()
            sources = figure_sources(p)
            res = compare(self.current_file, sources)
        except Exception:
            logger.error('source check failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Check failed', 'Could not check the sources (see log).')
            return
        if not res['recorded']:
            QMessageBox.information(self, 'Changed source files',
                                    'No snapshot yet: it is written the next time you save.')
            return
        text = describe(res)
        if not text:
            QMessageBox.information(self, 'Changed source files',
                                    f"All {res['unchanged']} source files are unchanged since "
                                    f"the figure was saved ({res['saved']}).")
            return
        reply = QMessageBox.question(
            self, 'Changed source files',
            text + '\n\nRe-read the source files now, so the figure shows their current '
                   'versions?', QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.reload_state(p, append=False)
            self.paint.EZFIG_panel.undo_redo_save_required.emit()
            self.statusBar().showMessage('Source files re-read. Save to accept them.')

    def copy_style_action(self):
        """Give the current figure the look of another one (MCP: copy_style)."""
        src = openFileNameDialog(parent_window=self,
                                 extensions="PyFigures (*.pyf);;All Files (*)")
        if not src:
            return
        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        boxes = {}
        for key, text in (('fonts', 'Fonts (figure + letter font)'),
                          ('letters', 'Panel letters (size, weight, colour, corner, case)'),
                          ('scale_bars', 'Scale bars (colour, thickness, corner, label)'),
                          ('spacing', 'Spacing between panels'),
                          ('plots', 'Chart styling (font size, line widths)')):
            cb = QCheckBox(text, frame)
            cb.setChecked(True)
            lay.addWidget(cb)
            boxes[key] = cb
        cd = CustomDialog(title="Copy style",
                          message=f"Apply the style of {os.path.basename(src)} to this figure "
                                  f"(content is not changed):",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        aspects = [k for k, cb in boxes.items() if cb.isChecked()]
        if not aspects:
            return
        from pyfigures.mcp_server import copy_style

        def _apply(p, **kw):
            return copy_style(src, p, **kw)
        self._run_mcp_mutation(_apply, f"Style copied from {os.path.basename(src)}.",
                               aspects=aspects)

    def alt_text_action(self):
        """Draft / edit the figure's alt text (MCP: generate_alt_text, set_alt_text)."""
        import json
        from pyfigures.mcp_server import generate_alt_text, set_alt_text
        from pyfigures.mcp_tools.upkeep import read_alt_text
        if not self.current_file:
            QMessageBox.information(self, 'Save the figure first',
                                    'Save the figure to a .pyf first — the alt text is stored '
                                    'in a sidecar file beside it.')
            return
        stored = read_alt_text(self.current_file)
        try:
            draft = json.loads(generate_alt_text(self._save_current_to_temp_pyf()))
        except Exception:
            logger.error('alt text failed:\n' + traceback.format_exc())
            draft = {'short': '', 'long': ''}
        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        lay.addWidget(QLabel('Short (one sentence):', frame))
        short = QLineEdit((stored or draft).get('short', ''), frame)
        lay.addWidget(short)
        lay.addWidget(QLabel('Full description (edit: it describes the structure, '
                             'add what the panels show):', frame))
        long_edit = QTextEdit(frame)
        long_edit.setPlainText((stored or draft).get('long', ''))
        long_edit.setMinimumSize(560, 240)
        lay.addWidget(long_edit)
        regen = QPushButton('Replace with a fresh draft', frame)
        regen.clicked.connect(lambda *_: (short.setText(draft.get('short', '')),
                                          long_edit.setPlainText(draft.get('long', ''))))
        lay.addWidget(regen)
        cd = CustomDialog(title="Alt text (accessibility)", message="",
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        res = set_alt_text(self.current_file, long_edit.toPlainText(), short.text() or None)
        if res.startswith('ERROR'):
            QMessageBox.warning(self, 'Alt text', res)
            return
        self.statusBar().showMessage('Alt text saved beside the .pyf.')

    def install_latex_action(self, *_):
        """Help → Install LaTeX for PyFigures… (TinyTeX; MCP: install_latex)."""
        from pyfigures.gui.latex_support import install_latex_action
        return install_latex_action(self)

    def add_data_plot_action(self):
        """Pick a CSV + plot options, then add a live data-plot panel
        (MCP: add_data_plot — a scripted, re-rendering panel with auto-stats)."""
        files = openFileNamesDialog(
            parent_window=self,
            extensions="CSV data (*.csv *.tsv *.txt);;All Files (*)")
        if not files:
            return
        csv_path = files[0] if isinstance(files, (list, tuple)) else files

        frame = QFrame(self)
        grid = QGridLayout(frame)
        grid.addWidget(QLabel('Plot type:', frame), 0, 0)
        kind_combo = QComboBox(frame)
        kind_combo.addItems(['bar', 'box', 'violin', 'scatter', 'grouped'])
        grid.addWidget(kind_combo, 0, 1)

        grid.addWidget(QLabel('Error bars:', frame), 1, 0)
        error_combo = QComboBox(frame)
        error_combo.addItems(['sem', 'sd', 'ci95', 'none'])
        grid.addWidget(error_combo, 1, 1)

        grid.addWidget(QLabel('Statistics:', frame), 2, 0)
        stats_combo = QComboBox(frame)
        stats_combo.addItems(['auto', 'parametric', 'nonparametric'])
        stats_combo.setToolTip('auto = pick parametric vs non-parametric by a '
                               'normality check; or force one. Applies to '
                               'bar/box/violin comparisons.')
        grid.addWidget(stats_combo, 2, 1)

        annotate_cb = QCheckBox('Add significance brackets automatically', frame)
        annotate_cb.setChecked(True)
        grid.addWidget(annotate_cb, 3, 0, 1, 2)

        only_sig_cb = QCheckBox('Only significant pairs (hide n.s.)', frame)
        only_sig_cb.setChecked(True)
        grid.addWidget(only_sig_cb, 4, 0, 1, 2)

        grid.addWidget(QLabel('Y-axis label:', frame), 5, 0)
        ylabel_edit = QLineEdit('', frame)
        grid.addWidget(ylabel_edit, 5, 1)

        grid.addWidget(QLabel('Panel label:', frame), 6, 0)
        label_edit = QLineEdit('', frame)
        grid.addWidget(label_edit, 6, 1)

        from batoolset.latex_tools import latex_available
        latex_cb = QCheckBox('Typeset the text with LaTeX (axis labels, ticks, title)', frame)
        latex_cb.setEnabled(latex_available())
        latex_cb.setToolTip('Full LaTeX in the labels, e.g. $D$ (\\si{\\micro\\metre\\squared\\per\\second})'
                            if latex_available() else
                            'Needs a LaTeX installation (TeX Live, MiKTeX or MacTeX)')
        grid.addWidget(latex_cb, 7, 0, 1, 2)
        if not latex_available():
            install_btn = QPushButton('Install LaTeX…', frame)
            install_btn.setToolTip('Download TinyTeX (a small TeX Live, about 75 MB)')

            def _install(*_):
                from pyfigures.gui.latex_support import offer_latex_install
                if offer_latex_install(self, 'LaTeX text in plots needs LaTeX'):
                    latex_cb.setEnabled(True)
                    latex_cb.setChecked(True)
                    latex_cb.setToolTip('')
                    install_btn.hide()
            install_btn.clicked.connect(_install)
            grid.addWidget(install_btn, 8, 0, 1, 2)

        cd = CustomDialog(
            title="Add data plot from CSV",
            message=(f"{os.path.basename(csv_path)} — columns are groups (wide) or "
                     "'group,value' (long); 'grouped' needs 'factorA,factorB,value'."),
            main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return

        from pyfigures.mcp_server import add_data_plot
        self._run_mcp_mutation(
            add_data_plot,
            "Added a data-plot panel — drag it into place.",
            group_path=[],
            csv_path=csv_path,
            kind=kind_combo.currentText(),
            error=error_combo.currentText(),
            annotate_stats=annotate_cb.isChecked(),
            only_significant=only_sig_cb.isChecked(),
            stats_mode=stats_combo.currentText(),
            ylabel=ylabel_edit.text().strip(),
            label=label_edit.text().strip() or None,
            latex=latex_cb.isChecked(),
        )

    # ------------------------------------------------------------------
    # QC / journal tools — thin GUI wrappers over the (tested) MCP logic.
    # The current figure is saved to a temp .pyf, the pure-XML MCP function
    # runs on it, and (for mutating ops) the result is reloaded.
    # ------------------------------------------------------------------
    # Figure-level data the MCP tools keep in files beside the .pyf (caption,
    # statistics). The GUI hands MCP tools a temp copy of the figure, so these
    # must travel with that copy and any new ones must come back.
    _SIDECAR_EXTS = ('.caption.json', '.stats.json', '.alttext.json', '.sources.json', '.target.json')
    # the source snapshot describes the SAVED figure: it goes to the temp copy
    # (so MCP tools can report changes) but never comes back from it
    _SIDECAR_EXTS_BACK = ('.caption.json', '.stats.json', '.alttext.json', '.target.json')

    def _sidecar_base(self):
        """Path prefix (no extension) of the current figure's sidecars: beside
        the saved .pyf, or in a per-window stash while the figure is unsaved."""
        if self.current_file:
            return os.path.splitext(self.current_file)[0]
        stash = getattr(self, '_sidecar_stash_dir', None)
        if not stash or not os.path.isdir(stash):
            import tempfile
            stash = tempfile.mkdtemp(prefix='pyf_sidecars_')
            self._sidecar_stash_dir = stash
        return os.path.join(stash, 'unsaved')

    def _copy_sidecars(self, src_base, dst_base, exts=None):
        """Copy the caption/stats/... sidecars from *src_base* to *dst_base*."""
        import shutil
        if not src_base or not dst_base:
            return
        if os.path.normcase(os.path.abspath(src_base)) == \
                os.path.normcase(os.path.abspath(dst_base)):
            return
        for ext in (exts or self._SIDECAR_EXTS):
            src = src_base + ext
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, dst_base + ext)
                except OSError:
                    logger.error('could not copy sidecar ' + src + ':\n'
                                 + traceback.format_exc())
        if exts is None:
            # the LaTeX-typeset label maths kept next to the figure
            from batoolset.latex_tools import labels_dir_for
            src_dir = labels_dir_for(src_base + '.pyf')
            dst_dir = labels_dir_for(dst_base + '.pyf')
            if os.path.isdir(src_dir) and os.path.normcase(src_dir) != os.path.normcase(dst_dir):
                try:
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
                except OSError:
                    logger.error('could not copy the label maths ' + src_dir + ':\n'
                                 + traceback.format_exc())

    def _save_current_to_temp_pyf(self):
        """Save the current figure (plus its sidecars) to a fresh temp folder for
        an MCP tool. Temp folders are removed by _cleanup_qc_temp_dirs()."""
        import tempfile
        self._cleanup_qc_temp_dirs()
        d = tempfile.mkdtemp(prefix='pyf_qc_')
        self._qc_temp_dirs = getattr(self, '_qc_temp_dirs', []) + [d]
        p = os.path.join(d, 'current.pyf')
        self._save_state_to_file(p)
        self._copy_sidecars(self._sidecar_base(), os.path.splitext(p)[0])
        return p

    def _adopt_sidecars_from(self, temp_pyf):
        """After an MCP mutation: bring the sidecars it wrote/updated back to the
        figure (saved file, or the unsaved-figure stash until the next Save)."""
        self._copy_sidecars(os.path.splitext(temp_pyf)[0], self._sidecar_base(),
                            self._SIDECAR_EXTS_BACK)

    def _discard_sidecar_stash(self):
        """Forget the caption/stats kept for an unsaved figure."""
        import shutil
        stash = getattr(self, '_sidecar_stash_dir', None)
        if stash:
            shutil.rmtree(stash, ignore_errors=True)
        self._sidecar_stash_dir = None

    def _cleanup_qc_temp_dirs(self):
        """Delete the temp folders created for earlier MCP calls. Called before
        each new call (the previous figure copy has been fully read by then) and
        on close."""
        import shutil
        for d in getattr(self, '_qc_temp_dirs', []):
            shutil.rmtree(d, ignore_errors=True)
        self._qc_temp_dirs = []

    def _show_report(self, title, text):
        """Show a read-only, scrollable text report in a modal dialog."""
        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        view = QTextBrowser(frame)
        view.setPlainText(text)
        view.setMinimumSize(560, 420)
        lay.addWidget(view)
        dlg = CustomDialog(title=title, message="", main_widget=frame,
                           options=['Ok'], parent=self)
        dlg.exec_()

    def mcp_history_dialog(self):
        """Show the MCP calls logged for the saved figure, with an 'Undo last
        MCP change' button (pyfigures/history.py — same as the list_history /
        undo_last tools and python -m pyfigures.history)."""
        from pyfigures import history
        path = getattr(self, 'current_file', None)
        if not path or not os.path.isfile(path):
            QMessageBox.information(self, 'MCP call history',
                                    'Save or open a figure first: the history is kept beside the file.')
            return
        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        view = QTextBrowser(frame)
        view.setPlainText(history.describe(path, last=200))
        view.setMinimumSize(640, 420)
        lay.addWidget(view)
        dlg = CustomDialog(title='MCP call history', message=os.path.basename(path),
                           main_widget=frame, options=['Undo last MCP change', 'Close'], parent=self)
        dlg.exec_()
        if getattr(dlg, 'selected_option', None) == 'Undo last MCP change':
            self.undo_last_mcp_change()

    def undo_last_mcp_change(self, force=False):
        """Undo the last change the MCP server made to the saved figure and
        reload it. Unsaved edits in the window are not touched without asking."""
        from pyfigures import history
        path = getattr(self, 'current_file', None)
        if not path or not os.path.isfile(path):
            return None
        if getattr(self, '_dirty', False):
            QMessageBox.warning(self, 'Unsaved changes',
                                'Save or discard the changes in the window first: the undo '
                                'restores the file as the MCP server left it before its last change.')
            return None
        res = history.undo_last(path, 1, force)
        if res.startswith('ERROR') and 'force=True' in res and not force:
            answer = QMessageBox.question(
                self, 'Undo anyway?',
                res[len('ERROR: '):].replace('Pass force=True to restore', 'Restore')
                + '?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return res
            return self.undo_last_mcp_change(force=True)
        if res.startswith('ERROR'):
            QMessageBox.warning(self, 'Nothing undone', res)
            return res
        self.reload_state(path, append=False)
        self.current_file = path
        self._mark_clean()
        self.statusBar().showMessage(res)
        return res

    def _run_mcp_mutation(self, func, success_msg, **kwargs):
        """Run a mutating MCP function on a temp copy, then reload the result."""
        try:
            p = self._save_current_to_temp_pyf()
            res = func(p, **kwargs)
            if isinstance(res, str) and res.startswith('ERROR'):
                QMessageBox.warning(self, 'Could not apply', res)
                return
            self._adopt_sidecars_from(p)
            self.reload_state(p, append=False)
            self.paint.EZFIG_panel.undo_redo_save_required.emit()
            self.statusBar().showMessage(success_msg)
            # done, but the tool has a remark (e.g. a zoom inset hiding its box)
            notes = [ln[len('WARNING: '):] for ln in str(res).splitlines()
                     if ln.startswith('WARNING: ')] if isinstance(res, str) else []
            if notes:
                QMessageBox.information(self, 'Done, with a remark', '\n\n'.join(notes))
        except Exception:
            logger.error('QC action failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Action failed',
                                'The operation failed (see log).')

    def audit_figure_report(self):
        from pyfigures.mcp_server import audit_figure
        try:
            p = self._save_current_to_temp_pyf()
            self._show_report("Figure audit", audit_figure(p))
        except Exception:
            logger.error('audit failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Audit failed', 'Could not audit (see log).')

    def check_journal_compliance_report(self):
        from pyfigures.mcp_server import check_journal_compliance
        dlg = _JournalDialog(self)
        cd = CustomDialog(title="Check journal compliance",
                          message="Choose the target journal / width.",
                          main_widget=dlg, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        try:
            kwargs = dlg.values()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        try:
            p = self._save_current_to_temp_pyf()
            self._show_report("Journal compliance",
                              check_journal_compliance(p, **kwargs))
        except Exception:
            logger.error('compliance failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Check failed', 'Could not check (see log).')

    def check_resolution_report(self):
        from pyfigures.mcp_server import check_resolution
        dlg = _JournalDialog(self)
        cd = CustomDialog(title="Check print resolution",
                          message="Choose the target journal / width.",
                          main_widget=dlg, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        try:
            v = dlg.values()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        res_kwargs = {k: v[k] for k in ('journal', 'column', 'width_mm', 'min_dpi')
                      if k in v}
        try:
            p = self._save_current_to_temp_pyf()
            self._show_report("Print resolution", check_resolution(p, **res_kwargs))
        except Exception:
            logger.error('resolution failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Check failed', 'Could not check (see log).')

    def apply_journal_guidelines_action(self):
        from pyfigures.mcp_server import apply_journal_guidelines
        dlg = _JournalDialog(self, with_apply_options=True)
        cd = CustomDialog(title="Apply journal guidelines",
                          message="This resizes the figure and adjusts fonts / "
                                  "labels to the journal's rules.",
                          main_widget=dlg, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        try:
            v = dlg.values()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        kwargs = {k: v[k] for k in ('journal', 'column', 'width_mm',
                                    'add_panel_labels') if k in v}
        kwargs['min_font_pt'] = v.get('min_font_pt', 7.0)
        self._run_mcp_mutation(apply_journal_guidelines,
                               "Applied journal guidelines.", **kwargs)

    def enforce_min_font_action(self):
        val, ok = QInputDialog.getDouble(
            self, "Enforce minimum font size",
            "Raise every font below this size (pt):", 7.0, 1.0, 72.0, 1)
        if not ok:
            return
        from pyfigures.mcp_server import enforce_min_font_size
        self._run_mcp_mutation(enforce_min_font_size,
                               f"Enforced minimum font size of {val} pt.",
                               min_pt=val)

    def add_scale_bar_all(self):
        from pyfigures.mcp_server import set_scale_bar_all
        dlg = _ScaleBarAllDialog(self)
        cd = CustomDialog(title="Add scale bar to all panels",
                          message="Add/update a scale bar on every panel.",
                          main_widget=dlg, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        try:
            kwargs = dlg.values()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        self._run_mcp_mutation(set_scale_bar_all,
                               "Added a scale bar to all panels.", **kwargs)

    def remap_paths_action(self):
        from pyfigures.mcp_server import remap_paths
        dlg = _RemapPathsDialog(self)
        cd = CustomDialog(title="Remap image paths",
                          message="Rewrite a path prefix on every image filename.",
                          main_widget=dlg, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        try:
            kwargs = dlg.values()
        except ValueError as e:
            QMessageBox.warning(self, 'Invalid input', str(e))
            return
        self._run_mcp_mutation(remap_paths,
                               "Remapped image paths.", **kwargs)

    # --- MCP-parity actions (integrity / ledger / caption / print / fonts) ---
    def check_integrity_action(self):
        """Screen panels for duplicated / cloned images (MCP: check_image_integrity)."""
        from pyfigures.mcp_server import check_image_integrity
        try:
            p = self._save_current_to_temp_pyf()
            self.statusBar().showMessage('Checking image integrity, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            res = check_image_integrity(p)
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('integrity check failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Check failed', 'Could not run the integrity check (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        self._show_report('Image integrity', res)

    def check_scale_consistency_action(self):
        """Flag panels whose displayed physical scale is inconsistent
        (MCP: check_scale_consistency)."""
        from pyfigures.mcp_server import check_scale_consistency
        import json
        try:
            p = self._save_current_to_temp_pyf()
            raw = check_scale_consistency(p)
        except Exception:
            logger.error('scale consistency check failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Check failed',
                                'Could not run the scale-consistency check (see log).')
            return
        if raw.startswith('ERROR') or raw.startswith('No raster'):
            self._show_report('Scale-bar consistency', raw)
            return
        d = json.loads(raw)
        lines = [d.get('summary', ''), '']
        ref = d.get('reference_scale')
        if ref:
            lines.append(f"Reference displayed scale: {ref:.4g} units / on-figure pixel "
                         f"(median)")
            lines.append('')
        for pnl in d.get('panels', []):
            flag = 'ok  ' if pnl['consistent'] else 'FAIL'
            rec = pnl.get('recommended_display_w')
            rec_s = f"  → resize to ~{rec:g}px wide to match" if rec else ""
            lines.append(f"  [{flag}] {pnl['label']} ({pnl['filename']}): "
                         f"scale={pnl['displayed_scale']:.4g}, "
                         f"{pnl['deviation_pct']:g}% from reference{rec_s}")
        missing = d.get('missing_scale', [])
        if missing:
            lines.append('')
            lines.append('No pixel size set (not checked):')
            for m in missing:
                who = m['filename'] if isinstance(m, dict) else m
                lines.append(f"  - {who}")
        self._show_report('Scale-bar consistency', "\n".join(lines))

    def figure_review_action(self):
        """Run all mechanical QC checks and list the reviewer questions
        (MCP: figure_review_brief)."""
        from pyfigures.mcp_server import figure_review_brief
        import json
        try:
            p = self._save_current_to_temp_pyf()
            self.statusBar().showMessage('Running pre-submission checks, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            raw = figure_review_brief(p)
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('figure review failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Review failed',
                                'Could not run the review (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        if raw.startswith('ERROR'):
            self._show_report('Pre-submission review', raw)
            return
        d = json.loads(raw)
        lines = [f"Pre-submission review — {d['figure']}", ""]
        lines.append(f"Caption: {'present' if d['caption_present'] else 'MISSING'}")
        lines.append("")
        lines.append("── Mechanical checks ──")
        for name, val in d['mechanical_checks'].items():
            if isinstance(val, dict):
                summary = val.get('summary') or val.get('note') or ''
                if not summary:
                    # concise fallback from common keys
                    if 'panels_missing_scale_bar' in val:
                        summary = (f"{val.get('n_panels', '?')} panels, "
                                   f"{len(val.get('panels_missing_scale_bar', []))} without a scale bar")
                    elif 'inconsistent_count' in val:
                        summary = f"{val.get('inconsistent_count', 0)} scale-inconsistent panel(s)"
                lines.append(f"  • {name}: {summary}")
            else:
                lines.append(f"  • {name}: {str(val)[:120]}")
        lines.append("")
        lines.append("── Reviewer questions (judge visually) ──")
        for i, q in enumerate(d['visual_rubric'], 1):
            lines.append(f"  {i}. {q}")
        lines.append("")
        lines.append("Tip: also view the figure under colour-blindness "
                     "(Help → Preview figure under colour-blindness…).")
        self._show_report('Pre-submission review', "\n".join(lines))

    def adjustment_ledger_action(self):
        """Show the image-adjustment provenance ledger (MCP: export_adjustment_ledger)."""
        from pyfigures.mcp_server import export_adjustment_ledger
        try:
            p = self._save_current_to_temp_pyf()
            self._show_report('Adjustment provenance ledger', export_adjustment_ledger(p))
        except Exception:
            logger.error('adjustment ledger failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Failed', 'Could not build the ledger (see log).')

    def figure_caption_action(self):
        """Edit the figure caption / legend, stored beside the .pyf (MCP:
        set_figure_caption)."""
        from pyfigures.mcp_server import set_figure_caption, get_figure_caption
        if not self.current_file:
            QMessageBox.information(
                self, 'Save the figure first',
                'Save the figure to a .pyf first — the caption is stored in a '
                'sidecar file beside it.')
            return
        cur_title = cur_caption = ''
        try:
            import json
            res = get_figure_caption(self.current_file)
            if not res.startswith('No figure caption'):
                d = json.loads(res)
                cur_title = d.get('title') or ''
                cur_caption = d.get('caption') or ''
        except Exception:
            pass
        title, ok = QInputDialog.getText(self, 'Figure caption — title',
                                         'Title (optional, e.g. "Figure 1"):', text=cur_title)
        if not ok:
            return
        caption, ok = QInputDialog.getMultiLineText(self, 'Figure caption / legend',
                                                    'Caption text:', cur_caption)
        if not ok:
            return
        try:
            set_figure_caption(self.current_file, caption, title=title or None)
        except Exception:
            logger.error('set caption failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Failed', 'Could not save the caption (see log).')
            return
        self.statusBar().showMessage('Figure caption saved beside the .pyf.')

    def export_print_ready_action(self):
        """Export a high-DPI CMYK/RGB TIFF for print (MCP: export_print_ready)."""
        from pyfigures.mcp_server import export_print_ready
        if not self.paint.EZFIG_panel.shapes_to_draw:
            QMessageBox.information(self, 'Nothing to export', 'Add some panels first.')
            return
        mode, ok = QInputDialog.getItem(self, 'Print-ready TIFF', 'Colour mode:',
                                        ['cmyk', 'rgb'], 0, False)
        if not ok:
            return
        dpi, ok = QInputDialog.getInt(self, 'Print-ready TIFF', 'Resolution (DPI):',
                                      300, 100, 1200, 50)
        if not ok:
            return
        output_file = saveFileDialog(parent_window=self,
                                     extensions="TIFF (*.tif *.tiff);;All Files (*)",
                                     default_ext='.tif')
        if not output_file:
            return
        self.statusBar().showMessage('Exporting print-ready TIFF, please wait...')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            p = self._save_current_to_temp_pyf()
            res = export_print_ready(p, output_file, color_mode=mode, dpi=dpi)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            QMessageBox.warning(self, 'Export failed', 'Could not export:\n' + str(e))
            return
        QApplication.restoreOverrideCursor()
        if isinstance(res, str) and res.startswith('ERROR'):
            self.statusBar().clearMessage()
            QMessageBox.warning(self, 'Export failed', res)
            return
        self.statusBar().showMessage(f'Exported {mode.upper()} TIFF at {dpi} DPI')
        QMessageBox.information(self, 'Print-ready TIFF exported',
                               f'Wrote {os.path.basename(output_file)}  ({mode.upper()}, {dpi} DPI).')

    def fonts_report_action(self):
        """Show the portable-font situation (MCP: list_fonts)."""
        try:
            import json
            from pyfigures.gui.portable_fonts import register_portable_fonts, font_report
            register_portable_fonts(QApplication.instance())
            self._show_report('Fonts (portable / Helvetica)',
                              json.dumps(font_report(), indent=2))
        except Exception:
            logger.error('fonts report failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Failed', 'Could not read the fonts (see log).')

    def preview_color_blindness(self):
        """Render the current figure and show it simulated for a chosen
        colour-vision deficiency (pairs with the pixel colour-blind assistant)."""
        panel = self.paint.EZFIG_panel
        if not panel.shapes_to_draw:
            QMessageBox.information(self, 'Nothing to preview',
                                    'Add some panels to the figure first.')
            return
        from pyfigures.cvd import TYPES, simulate_array
        typ, ok = QInputDialog.getItem(
            self, 'Colour-blindness preview', 'Simulate colour vision:',
            list(TYPES), 1, False)
        if not ok:
            return
        import tempfile
        import numpy as np
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QPixmap, QImage
        from qtpy.QtWidgets import QLabel

        tmp = os.path.join(tempfile.mkdtemp(prefix='pyf_cvd_'), 'fig.png')
        old_get_dpi = panel.get_dpi
        panel.get_dpi = (lambda _d=150: _d)     # avoid the interactive DPI dialog
        try:
            panel.update_size()
            panel.save(tmp)
        except Exception:
            logger.error('CVD render failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Preview failed',
                                'Could not render the figure (see log).')
            return
        finally:
            panel.get_dpi = old_get_dpi

        try:
            from PIL import Image as PILImage
            im = PILImage.open(tmp).convert('RGBA')
            sim = np.ascontiguousarray(simulate_array(np.asarray(im), typ))
            h, w = sim.shape[:2]
            qimg = QImage(sim.tobytes(), w, h, 4 * w, QImage.Format_RGBA8888)
            pix = QPixmap.fromImage(qimg)
        except Exception:
            logger.error('CVD simulation failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Preview failed',
                                'Could not simulate colour blindness (see log).')
            return

        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        lbl = QLabel(frame)
        lbl.setPixmap(pix.scaled(900, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(lbl)
        dlg = CustomDialog(title=f'{typ} preview',
                           message='How the figure looks with this colour-vision '
                                   'deficiency.',
                           main_widget=frame, options=['Ok'], parent=self)
        dlg.exec_()

    def _bind_label_maths(self, pyf_path):
        """Label maths typeset by LaTeX is looked up (and kept) next to the
        figure first (batoolset.latex_tools): it travels with the figure."""
        try:
            from batoolset.latex_tools import bind_figure
            bind_figure(pyf_path if isinstance(pyf_path, str) and pyf_path.lower().endswith('.pyf')
                        and os.path.isfile(pyf_path) else None)
        except Exception:
            pass

    def _restore_lettering(self, gui_params=None):
        """After opening a figure: its own lettering (first letter and on/off),
        not the toolbar's defaults (which re-lettered every opened figure "a,
        b…", and lettered figures built without letters). Saved with the
        figure since 2026-10; for older files (and figures written by recipes
        or the MCP server) it is read from the letters the panels carry."""
        first = getattr(gui_params, 'first_letter', None) if gui_params is not None else None
        auto = getattr(gui_params, 'auto_lettering', None) if gui_params is not None else None
        if first is None or auto is None:
            try:
                _, images = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(
                    exclude_images_without_filename=False, include_insets=False)
            except Exception:
                images = []
            images = [im for im in images if not getattr(im, 'isText', False)]
            letters = [a.getPlainText().strip() for im in images for a in (im.annotations or [])
                       if isinstance(a, TAText2D) and a.is_letter]
            letters = [l for l in letters if len(l) == 1 and l.isalpha()]
            if images:
                if auto is None:
                    auto = bool(letters)
                if first is None and letters:
                    first = min(letters)
        self.letter_line_edit.blockSignals(True)
        self.auto_lettering_checkbox.blockSignals(True)
        try:
            if first:
                self.letter_line_edit.setText(str(first)[:1])
            if auto is not None:
                self.auto_lettering_checkbox.setChecked(bool(auto))
        finally:
            self.letter_line_edit.blockSignals(False)
            self.auto_lettering_checkbox.blockSignals(False)

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
            if elm.isText:  # do not label text labels
                continue
            # as in recipes and the MCP server (_finalize_draft): a montage / channel
            # split is ONE figure panel (lettered on its first member only), and a
            # LUT calibration bar belongs to the panel next to it (opening a recipe
            # figure used to re-letter every frame A, B, C…)
            comment = str(getattr(elm, 'user_comments', '') or '')
            script = str(getattr(elm, 'custom_loading_script', '') or '')
            if (comment.startswith('[series ') and not comment.startswith('[series 1/')) \
                    or 'ColorbarBase(' in script:
                if elm.annotations:
                    for l in [l for l in elm.annotations if isinstance(l, TAText2D) and l.is_letter]:
                        elm.annotations.remove(l)
                continue
            # reuse the existing letter annotation when possible: recreating a
            # QTextDocument-backed TAText2D per image on every refresh is expensive
            existing = None
            if elm.annotations:
                letters_found = [l for l in elm.annotations if isinstance(l, TAText2D) and l.is_letter]
                if shall_add_letter and letters_found:
                    existing = letters_found[0]
                for l in letters_found:
                    if l is not existing:
                        elm.annotations.remove(l)
            if shall_add_letter:
                fg = self._letter_colour_override(elm)
                html = self.serializable_font.get_letter_html(letter, foreground=fg)
                if existing is not None:
                    # update in place, and only touch the document if something changed
                    if getattr(existing, '_letter_source_html', None) != html:
                        existing.setText(html)
                        existing._letter_source_html = html
                    existing.fill_color = self.serializable_font.background
                    placement = self.serializable_font.placement
                    if placement is not None and existing.placement is not placement:
                        existing.placement = placement if isinstance(placement, Position) else Position(placement)
                else:
                    txt_to_add = self.serializable_font.get_TaText2D_with_font(letter, foreground=fg)
                    txt_to_add._letter_source_html = html
                    elm.annotations.insert(0, txt_to_add)
                letter = increment_letter(letter)

    def _letter_colour_override(self, elm):
        """Black letters on chart panels (matplotlib figures / SVGs have a white
        background) when the figure's letter colour is light — otherwise a white
        letter is invisible on a data plot. On a micrograph the colour follows
        the corner the letter sits on, as for the MCP tools / recipes: black on
        a bright corner (bright field), white on a dark one (fluorescence, where
        a black letter is invisible). None = use the figure font colour."""
        fg = getattr(self.serializable_font, 'foreground', None)
        if fg is None:
            return None
        rgb = int(fg) & 0xFFFFFF
        luminance = (0.299 * ((rgb >> 16) & 0xFF) + 0.587 * ((rgb >> 8) & 0xFF)
                     + 0.114 * (rgb & 0xFF))
        light = luminance >= 160
        from qtpy.QtSvg import QSvgRenderer
        img = getattr(elm, 'img', None)
        if isinstance(img, plt.Figure):
            # figures that show image data (channel merge, flip) are dark-friendly
            is_chart = not getattr(img, '_pyfigures_image_panel', False)
        else:
            is_chart = isinstance(getattr(elm, 'renderer', None), QSvgRenderer) \
                and not isinstance(img, np.ndarray)
        if is_chart:
            return 0x000000 if light else None
        fn = getattr(elm, 'filename', None)
        if not isinstance(fn, str) or getattr(elm, 'custom_loading_script', None):
            return None  # merges (fluorescence) and scripted panels keep the font colour
        placement = getattr(self.serializable_font, 'placement', None)
        if isinstance(placement, Position):
            placement = ' '.join(placement.get_position())
        try:
            from pyfigures.mcp_tools.core import corner_brightness
            bright = corner_brightness(fn, str(placement or 'top left'),
                                       (elm.crop_left, elm.crop_right, elm.crop_top, elm.crop_bottom),
                                       getattr(elm, 'LUTs', None))
        except Exception:
            bright = None
        if bright is None:
            return None
        if light and bright > 0.6:
            return 0x000000
        if not light and bright < 0.4:
            return 0xFFFFFF
        return None

    # def remove_all_annotations(self):
    #     print('remove all annotations called')
    #     self.paint.EZFIG_panel.remove_all_annotations()

    def force_silent_spinner_update_in_parent(self, value):
        try:
            self.main_space_spinner.blockSignals(True)
            self.main_space_spinner.setValue(value)
            self.main_space_spinner.blockSignals(False)
        except Exception:
            pass

    def force_update_store(self):
        # print('STORE CONTENT NEEDS BE UPDATED -> ACTION REQUIRED')
        # TODO --> do the list of all images and delete all the ones that are no longer in the store after that
        full_list_of_filenames_to_consolidate, _ = self.paint.EZFIG_panel.get_full_list_ofimages2D_for_consolidation(stuff_to_consolidate=None)
        ImageCentralStore.clean(full_list_of_filenames_to_consolidate)


    def change_lettering_parameters(self):
        # start from the current lettering (it used to always open on the
        # defaults, so Ok silently reset colours/font/position)
        main = AutoLetteringOptions(font=getattr(self, 'serializable_font', None))

        custom_dialog = CustomDialog(title="Auto lettering",
                                     message=None,
                                     main_widget=main, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)

        if custom_dialog.exec_() == QDialog.Accepted:
            self.serializable_font = main.get_serializable_font()
            self.paint.EZFIG_panel.update()
            self.save_state(show_popup=True)

    def export_source_data_action(self):
        """Export a journal-style Source Data bundle for the figure
        (MCP: export_source_data)."""
        from pyfigures.mcp_server import export_source_data
        from qtpy.QtWidgets import QFileDialog
        import json
        parent = QFileDialog.getExistingDirectory(
            self, "Choose a folder to write the source-data bundle into")
        if not parent:
            return
        stem = (os.path.splitext(os.path.basename(self.current_file))[0]
                if self.current_file else "figure")
        out_dir = os.path.join(parent, f"{stem}_SourceData")
        try:
            p = self._save_current_to_temp_pyf()  # carries caption/stats sidecars
            self.statusBar().showMessage('Building source-data bundle, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            res = export_source_data(p, out_dir)
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('source-data export failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Export failed',
                                'Could not build the source-data bundle (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        if isinstance(res, str) and res.startswith('ERROR'):
            QMessageBox.warning(self, 'Export failed', res)
            return
        try:
            d = json.loads(res)
            msg = (f"Source-data bundle written to:\n{d['output_dir']}\n\n"
                   f"{len(d.get('panels', []))} panel(s), "
                   f"{d.get('n_source_files', 0)} source file(s), "
                   f"caption={d.get('caption')}, statistics={d.get('statistics')}, "
                   f"methods={d.get('methods')}.")
        except Exception:
            msg = res
        QMessageBox.information(self, 'Source data exported', msg)

    def draft_figure_action(self):
        """Auto-assemble a first-pass figure from a folder of results
        (MCP: draft_figure), then open it."""
        from pyfigures.mcp_server import draft_figure
        from qtpy.QtWidgets import QFileDialog
        import json
        folder = QFileDialog.getExistingDirectory(
            self, "Choose a folder of images / CSVs to draft a figure from")
        if not folder:
            return

        frame = QFrame(self)
        grid = QGridLayout(frame)
        grid.addWidget(QLabel('Data-plot type:', frame), 0, 0)
        kind_combo = QComboBox(frame)
        kind_combo.addItems(['bar', 'box', 'violin', 'scatter', 'grouped'])
        grid.addWidget(kind_combo, 0, 1)
        grid.addWidget(QLabel('Journal (optional):', frame), 1, 0)
        journal_combo = QComboBox(frame)
        journal_combo.addItems(['(none)'] + _JournalDialog._JOURNALS)
        grid.addWidget(journal_combo, 1, 1)
        grid.addWidget(QLabel('Column:', frame), 2, 0)
        column_combo = QComboBox(frame)
        column_combo.addItems(['single', 'double'])
        grid.addWidget(column_combo, 2, 1)
        grid.addWidget(QLabel('Pixel size (units/px, optional):', frame), 3, 0)
        pxu_edit = QLineEdit('', frame)
        grid.addWidget(pxu_edit, 3, 1)
        grid.addWidget(QLabel('Scale-bar length (units, optional):', frame), 4, 0)
        sb_edit = QLineEdit('', frame)
        grid.addWidget(sb_edit, 4, 1)

        cd = CustomDialog(title="Draft figure from folder",
                          message=(f"{os.path.basename(folder)} — images become a grid, "
                                   "CSVs become data-plot panels."),
                          main_widget=frame, options=['Ok', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return

        kwargs = {"plot_kind": kind_combo.currentText()}
        if journal_combo.currentText() != '(none)':
            kwargs["journal"] = journal_combo.currentText()
            kwargs["column"] = column_combo.currentText()
        try:
            if pxu_edit.text().strip():
                kwargs["px_to_unit"] = float(pxu_edit.text())
            if sb_edit.text().strip():
                kwargs["scale_bar_units"] = float(sb_edit.text())
        except ValueError:
            QMessageBox.warning(self, 'Invalid number',
                                'Pixel size and scale-bar length must be numbers.')
            return

        out = os.path.join(folder, "DraftFigure.pyf")
        try:
            self.statusBar().showMessage('Drafting figure, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            res = draft_figure(folder, out, **kwargs)
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('draft_figure failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Draft failed',
                                'Could not draft the figure (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        if isinstance(res, str) and res.startswith('ERROR'):
            QMessageBox.warning(self, 'Draft failed', res)
            return
        try:
            summary = json.loads(res).get('summary', 'Draft created.')
        except Exception:
            summary = 'Draft created.'
        self.reload_state(out, append=False)
        self.current_file = out
        QMessageBox.information(
            self, 'Figure drafted',
            summary + "\n\nOpened it — drag panels to fine-tune the layout.")

    def build_from_recipe_action(self):
        """Build a figure from a YAML/JSON recipe (MCP: build_figure_from_recipe;
        CLI: python -m pyfigures.recipe build <recipe>), then open it."""
        from pyfigures.recipe import build_figure_from_recipe, RecipeError, RecipeChecksFailed
        recipe = openFileNameDialog(
            parent_window=self,
            extensions="Figure recipes (*.yaml *.yml *.json);;All Files (*)")
        if not recipe:
            return
        recipe = recipe[0] if isinstance(recipe, (list, tuple)) else recipe
        if not self._maybe_save_before_discard('building a figure from a recipe'):
            return
        try:
            self.statusBar().showMessage('Building figure from recipe, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            res = build_figure_from_recipe(recipe)
        except RecipeChecksFailed as e:
            # built and saved, only the checks failed: open it so it can be fixed
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            self.reload_state(e.output, append=False)
            self.current_file = e.output
            self._mark_clean()
            QMessageBox.warning(self, 'Recipe checks failed', str(e))
            return
        except RecipeError as e:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            QMessageBox.warning(self, 'Recipe error', str(e))
            return
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('recipe build failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Build failed', 'Could not build the figure (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        self.reload_state(res['output'], append=False)
        self.current_file = res['output']
        self._mark_clean()
        msg = res['summary']
        if res.get('warnings'):
            msg += "\n\nWarnings:\n- " + "\n- ".join(res['warnings'])
        QMessageBox.information(self, 'Figure built from recipe', msg)

    def search_library_action(self):
        """Index a folder tree of past figures and search them by panel / label /
        caption (MCP: index_figures + search_figures). Opens the chosen figure."""
        from pyfigures.mcp_server import index_figures, search_figures
        from qtpy.QtWidgets import QFileDialog, QListWidget, QInputDialog
        import json
        root = QFileDialog.getExistingDirectory(
            self, "Choose the folder tree of past figures to search")
        if not root:
            return
        query, ok = QInputDialog.getText(
            self, "Search figure library",
            "Keywords (panel filenames, labels, caption):")
        if not ok or not query.strip():
            return
        try:
            self.statusBar().showMessage('Indexing and searching figures, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            idx = json.loads(index_figures(root))
            res = json.loads(search_figures(query.strip(), idx["index"]))
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('library search failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Search failed',
                                'Could not search the library (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        results = res.get("results", [])
        if not results:
            QMessageBox.information(
                self, 'No matches',
                f"No figures matched '{query}' under {os.path.basename(root)}.")
            return

        frame = QFrame(self)
        lay = QVBoxLayout(frame)
        lay.addWidget(QLabel(f"{len(results)} match(es) for '{query}':", frame))
        listw = QListWidget(frame)
        for r in results:
            cap = (r.get("caption_snippet") or "").strip()
            listw.addItem(f"{r['name']}  —  {os.path.dirname(r['path'])}"
                          + (f"\n    {cap}" if cap else ""))
        listw.setMinimumSize(580, 360)
        listw.setCurrentRow(0)
        lay.addWidget(listw)
        cd = CustomDialog(title="Figure library search",
                          message="Select a figure and press Open.",
                          main_widget=frame, options=['Open', 'Cancel'], parent=self)
        if cd.exec_() != QDialog.Accepted:
            return
        row = listw.currentRow()
        if 0 <= row < len(results):
            path = results[row]["path"]
            # like File > Open: offer to save, and start a fresh undo history
            # (Undo used to walk back into the previous figure)
            if not self._maybe_save_before_discard('opening another figure'):
                return
            self.reload_state(path, append=False)
            self.activate_or_reset_undo_redo()
            self.current_file = path
            self._mark_clean()

    def compare_version_action(self):
        """Visually diff the current figure against another .pyf
        (MCP: export_figure_diff). Opens a self-contained HTML in the browser."""
        from pyfigures.mcp_server import export_figure_diff
        import tempfile, webbrowser, json
        other = openFileNameDialog(
            parent_window=self,
            extensions="PyFigures (*.pyf);;All Files (*)")
        if not other:
            return
        other = other[0] if isinstance(other, (list, tuple)) else other
        try:
            p = self._save_current_to_temp_pyf()  # carries caption/stats sidecars
            # kept (not a QC temp dir): the browser tab still shows this file
            out_html = os.path.join(tempfile.mkdtemp(prefix='pyf_diff_'), 'diff.html')
            self.statusBar().showMessage('Building version diff, please wait...')
            QApplication.setOverrideCursor(Qt.WaitCursor)
            # the picked file is treated as the OLD version, current as the NEW
            res = export_figure_diff(other, p, out_html)
        except Exception:
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            logger.error('version compare failed:\n' + traceback.format_exc())
            QMessageBox.warning(self, 'Compare failed',
                                'Could not build the version diff (see log).')
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        if isinstance(res, str) and res.startswith('ERROR'):
            QMessageBox.warning(self, 'Compare failed', res)
            return
        try:
            n = json.loads(res).get('n_changes', '?')
        except Exception:
            n = '?'
        webbrowser.open('file:///' + out_html.replace('\\', '/'))
        QMessageBox.information(
            self, 'Figure comparison',
            f"{n} change(s) between {os.path.basename(other)} (old) and the current "
            f"figure (new).\nOpened the visual diff in your browser.")

    def _ask_download_remote(self, n_remote):
        """Save and Consolidate: also download the figure's remote images? (default: no)"""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle('Remote images')
        box.setText(f'This figure uses {n_remote} remote image(s) (web links, OME-Zarr or OMERO).\n\n'
                    'Download them into the bundle too?')
        box.setInformativeText('No: they stay links (the consolidated figure needs the network, and an '
                               'OMERO login for private images).\nYes: OMERO and OME-Zarr images are saved '
                               'as local OME-Zarr (what the panel shows, at full bit depth), other links as '
                               'the file itself.')
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

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

            # remote images (URLs, OME-Zarr on a server, OMERO links) stay
            # links unless the user asks to download them (default: no)
            download_remote = False
            n_remote = len({f for f in full_list_of_filenames_to_consolidate
                            if isinstance(f, str) and f.lower().startswith(('http://', 'https://'))})
            if n_remote:
                download_remote = self._ask_download_remote(n_remote)

            # full_list_of_filenames_to_consolidate, consolidated_file_list = smartly_consolidate_files_to_reduce_dupes(full_list_of_filenames_to_consolidate,'mock_folder.files')
            full_list_of_filenames_to_consolidate, consolidated_file_list = smartly_consolidate_files_to_reduce_dupes(
                full_list_of_filenames_to_consolidate, save_output_folder, download_remote=download_remote)
            # print('debug1', len(full_list_of_filenames_to_consolidate) == len(consolidated_file_list))
            # print('debug2', len(full_list_of_filenames_to_consolidate), len(consolidated_file_list))

            # for f1, f2 in zip(full_list_of_filenames_to_consolidate, consolidated_file_list):
            #     print(f1, '->', f2)

            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                not_downloaded = consolidate_files2(save_output_folder, full_list_of_filenames_to_consolidate,
                                                    consolidated_file_list, download_remote=download_remote)
            finally:
                QApplication.restoreOverrideCursor()
            if not_downloaded:
                QMessageBox.warning(self, 'Some remote images were not downloaded',
                                    'These images could not be downloaded and stay links:\n\n'
                                    + '\n'.join(f'{url}\n    {err}' for url, err in not_downloaded))

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
            # caption / stats sidecars follow the figure to its consolidated file
            self._copy_sidecars(self._sidecar_base(),
                                os.path.splitext(output_filename)[0])
            # the figure now lives in the consolidated file: Save should target it
            self.current_file = output_filename
            self._mark_clean()

    def open_poster_designer(self):
        # Lazily imported and fully self-contained: the poster module shares no
        # classes, state, or file format with this window / EZFIG_panel.
        from pyfigures.poster.poster_window import PosterWindow
        if not hasattr(self, '_poster_window') or self._poster_window is None:
            self._poster_window = PosterWindow(self)
        self._poster_window.show()
        self._poster_window.raise_()
        self._poster_window.activateWindow()

    def open_mcp_server_dialog(self):
        from pyfigures.gui.mcp_server_dialog import McpServerDialog
        dlg = McpServerDialog(self)
        dlg.exec_()
        return dlg

    def open_album_designer(self):
        # Same window class as the poster designer, in album mode: its own
        # window, so a poster never becomes an album.
        from pyfigures.poster.poster_window import PosterWindow
        if getattr(self, '_album_window', None) is None:
            self._album_window = PosterWindow(self, album=True)
        self._album_window.show()
        self._album_window.raise_()
        self._album_window.activateWindow()

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


    # I need ask all as single or panel




    # @Slot(object)
    # def update_gui(self, split_images):
    #
    #     if split_images is not None:
    #         # print('split_images passed',split_images)
    #         # This method runs in the main thread and safely updates the GUI
    #
    #         # print('testing',self.paint.EZFIG_panel.shapes_to_draw)
    #         self.paint.EZFIG_panel.shapes_to_draw.extend(split_images)
    #         # self.paint.EZFIG_panel.update_size()
    #         # self.paint.EZFIG_panel.update()

    # @Slot(object)
    # def update_gui(self, split_images):
    #     print('Current thread2:', QThread.currentThread())
    #     # Additional debugging information
    #     print('update_gui called')
    #
    #     if split_images is not None:
    #         print('split_images passed:', split_images)
    #
    #         # Check if paint.EZFIG_panel is valid and initialized
    #         if hasattr(self, 'paint') and hasattr(self.paint, 'EZFIG_panel'):
    #             panel = self.paint.EZFIG_panel
    #
    #             if hasattr(panel, 'shapes_to_draw'):
    #                 print('Current shapes_to_draw:', panel.shapes_to_draw)
    #                 # Check if shapes_to_draw is a list
    #                 if isinstance(panel.shapes_to_draw, list):
    #                     # Add debug prints to ensure safe manipulation
    #                     print('Extending shapes_to_draw with split_images')
    #                     panel.shapes_to_draw.extend(split_images)
    #                     print('Updated shapes_to_draw:', panel.shapes_to_draw)
    #                     # this worked --> so where is the pb ???
    #
    #                     # Uncomment to perform GUI updates
    #                     # panel.update_size()
    #                     # panel.update()
    #                 else:
    #                     print('Error: shapes_to_draw is not a list')
    #             else:
    #                 print('Error: EZFIG_panel has no attribute shapes_to_draw')
    #         else:
    #             print('Error: paint or EZFIG_panel not properly initialized')
    #     else:
    #         print('Error: split_images is None')

        # Any additional error handling or cleanup


    # def process_finished(self):
    #     self._please_wait_dialog.hide()
    #     self.worker.deleteLater()
    #     self._thread.quit()
    #     self._thread.wait()
    #     self._thread.deleteLater()
    #     self._thread = None
    #     self.worker = None
    # def process_finished(self):
    #     self._please_wait_dialog.hide()
    #     self.worker.deleteLater()
    #     self.worker = None
    #     self._thread = None

    # def process_finished(self):
    #     self._please_wait_dialog.hide()
    #     if self.worker:
    #         self.worker.deleteLater()
    #         self.worker = None
    #
    #
    # def cleanup_thread(self):
    #     if self._thread:
    #         self._thread.wait()  # Wait for the thread to fully finish
    #         self._thread.deleteLater()
    #         self._thread = None

    # def process_finished(self):
    #     self._please_wait_dialog.hide()

    def tst_function(self):
        #
        # if True:
        #     self.paint.EZFIG_panel.set_space()
        #     return

        # if True:
        #     self.paint.EZFIG_panel.set_luts()

        # if True:
        #     pzfconfig.path_to_last_consolidated_file = random.random()
        #     print('last consolidated path', pzfconfig.path_to_last_consolidated_file)
        #     return

        # do a split of the image by dimensions
        # --> read the first dimension (I could also use that for series)


        # self.force_update_store()




        # self.slow_process()

        # self._please_wait_dialog.hide()




        # Create a QEventLoop
        # Example custom function to run


        # self.worker = Worker(self.slow_process)
        # worker = Worker(self.slow_process)
        # self._thread = QThread()
        # self.worker.moveToThread(self._thread)
        #
        # self._thread.started.connect(self.worker.run)
        # self.worker.result_ready.connect(self.update_gui)
        # # self.worker.finished.connect(self._please_wait_dialog.hide)
        # # self.worker.finished.connect(self._thread.quit)
        # # self.worker.finished.connect(self.worker.deleteLater)
        # # self._thread.finished.connect(self._thread.deleteLater)
        # self.worker.finished.connect(self.process_finished)

        # Connect signals
        # self._thread.started.connect(self.worker.run)
        # self.worker.result_ready.connect(self.update_gui)
        # self.worker.finished.connect(self.process_finished)
        # self.worker.finished.connect(self._thread.quit)
        # self._thread.finished.connect(self._thread.deleteLater)

        # Connect signals
        # self._thread.started.connect(self.worker.run)
        # self.worker.result_ready.connect(self.update_gui)
        # self.worker.finished.connect(self.process_finished)
        # self.worker.finished.connect(self._thread.quit)
        #
        # # Ensure thread is deleted after it has fully finished
        # self._thread.finished.connect(self.cleanup_thread)
        #
        # self._thread.start()
        # worker.signals.result.connect(self.update_gui)
        # worker.signals.finished.connect(self.process_finished)
        #
        # self.threadpool.start(worker)


        # print('Current thread:', QThread.currentThread())

        if False:
            # get all images and get the max nb of channels of all images and then ask for channels
            self.paint.EZFIG_panel.reorganize_as_panel()
            pass

        self._debug_check_of_shapes()

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
                except Exception:
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
            except Exception:
                pass
            try:
                print('getRect', self.paint.EZFIG_panel.selected_shape.getRect())
                print('getRect scale=True', self.paint.EZFIG_panel.selected_shape.getRect(scale=True))
                print('getRect all=True', self.paint.EZFIG_panel.selected_shape.getRect(all=True))
            except Exception:
                pass
            try:
                print('shape size', self.paint.EZFIG_panel.selected_shape.size)
            except Exception:
                pass
        else:
            for shape in self.paint.EZFIG_panel.shapes_to_draw:
                print('sel shape', shape)
                print('type', type(shape))
                print('getRect', shape.getRect())
                try:
                    print('getRect scale=True', shape.getRect(scale=True))
                    print('getRect all=True', shape.getRect(all=True))
                except Exception:
                    pass
                try:
                    print('shape size', shape.size)
                except Exception:
                    pass
        try:
            print('ImageCentralStore.keys()', ImageCentralStore.keys())
        except Exception:
            pass

    def save_pyfigures(self, file='auto'):
        # print('SAVING AS PZF CALLED')
        # Returns True if the figure was written to disk, False if the user
        # cancelled the dialog or nothing was saved (used by the save-before-discard
        # prompt to decide whether it's safe to proceed).

        # where the caption/stats sidecars live right now (old file or the
        # unsaved-figure stash) — they must follow the figure to its new name
        sidecar_base_before = self._sidecar_base()

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
            # an explicit path means "save there" (it used to be ignored and the
            # figure written to current_file instead — or not at all)
            self.current_file = file
            success = True

        if self.current_file and success:
            self._save_state_to_file(self.current_file, popup=f'{self.current_file} Saved')
            self._copy_sidecars(sidecar_base_before,
                                os.path.splitext(self.current_file)[0])
            # snapshot of the source files: the next open reports any that changed
            try:
                from pyfigures.source_snapshot import record as _record_sources
                _record_sources(self.current_file)
            except Exception:
                logger.error('could not record the source snapshot:\n' + traceback.format_exc())
            self._mark_clean()  # figure now matches the file on disk
            return True
        return False

    def export_as_svg(self):
        output_file = saveFileDialog(parent_window=self, extensions="Supported Files (*.svg);;All Files (*)",
                                     default_ext='.svg')
        self._save(output_file)

    def export_as_pdf(self):
        output_file = saveFileDialog(parent_window=self, extensions="Supported Files (*.pdf);;All Files (*)",
                                     default_ext='.pdf')
        self._save(output_file)

    def export_as_png(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="PNG Files (*.png);;All Files (*)",
                                     default_ext='.png')
        self._save(output_file)

    def export_as_tif(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="TIF Files (*.tif *.tiff);;All Files (*)",
                                     default_ext='.tif')
        self._save(output_file)

    def export_as_jpg(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="JPEG Files (*.jpg *.jpeg);;All Files (*)",
                                     default_ext='.jpg')
        self._save(output_file)

    def _save(self, output_file):
        if output_file is not None:
            self.paint.EZFIG_panel.save(output_file)

    def _images_loading(self):
        th = getattr(self, '_pyf_loader_thread', None)
        try:
            running = th is not None and th.isRunning()
        except RuntimeError:
            running = False
        return running or getattr(self, '_pyf_loads_pending', 0) > 0 \
            or bool(getattr(self, '_lazy_img_queue', None)) \
            or bool(getattr(self, '_active_img_loaders', None))

    def wait_for_images(self, timeout=600):
        """Block (keeping the window responsive) until the figure's images have
        finished loading in the background. Exports call this first: a figure
        exported right after opening used to show the panels not loaded yet as
        empty or black. Returns False on timeout."""
        if not self._images_loading():
            return True
        import time as _time
        self.statusBar().showMessage('Waiting for the images to finish loading…')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            t0 = _time.time()
            thread_gone_since = None
            while self._images_loading() and _time.time() - t0 < timeout:
                QApplication.processEvents()
                _time.sleep(0.005)
                th = getattr(self, '_pyf_loader_thread', None)
                try:
                    th_running = th is not None and th.isRunning()
                except RuntimeError:
                    th_running = False
                if getattr(self, '_pyf_loads_pending', 0) and not th_running:
                    # the loader's results are normally handled within a few
                    # event-loop passes; never wait forever on a lost one
                    thread_gone_since = thread_gone_since or _time.time()
                    if _time.time() - thread_gone_since > 5:
                        self._pyf_loads_pending = 0
                else:
                    thread_gone_since = None
            # the last image's refresh/reflow are queued: run them now
            for _ in range(3):
                QApplication.processEvents()
            self._flush_lazy_refresh()
        finally:
            QApplication.restoreOverrideCursor()
        return not self._images_loading()

    def export_as_latex(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="LaTeX overlay (*.pdf_tex);;All Files (*)",
                                     default_ext='.pdf')
        if not output_file:
            return
        # offer to wrap in a figure float with the stored caption, if one exists
        cap = cap_title = None
        if self.current_file:
            try:
                import json
                from pyfigures.mcp_server import get_figure_caption
                res = get_figure_caption(self.current_file)
                if not res.startswith('No figure caption'):
                    d = json.loads(res)
                    stored_cap = d.get('caption') or ''
                    if stored_cap:
                        ans = QMessageBox.question(
                            self, 'Include caption?',
                            'This figure has a stored caption. Wrap the export in a '
                            'LaTeX figure float with \\caption{...}?\n\n'
                            '(No = plain overlay to \\input inside your own float.)',
                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                        if ans == QMessageBox.Yes:
                            cap = stored_cap
                            cap_title = d.get('title') or None
            except Exception:
                pass
        self.statusBar().showMessage('Exporting PDF + LaTeX, please wait...')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            img_path, tex_path = self.paint.EZFIG_panel.save_latex(
                output_file, image_format='pdf', caption=cap, caption_title=cap_title)
        except Exception as e:
            traceback.print_exc()
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            QMessageBox.warning(self, 'LaTeX export failed', 'Could not export:\n' + str(e))
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f'Exported {os.path.basename(img_path)} + {os.path.basename(tex_path)}')
        QMessageBox.information(
            self, 'PDF + LaTeX exported',
            'Wrote:\n  ' + os.path.basename(img_path) + '  (graphics, no text)\n  '
            + os.path.basename(tex_path) + '  (LaTeX text overlay)\n\n'
            'In your document:\n'
            '  \\usepackage{graphicx,color}\n'
            '  \\def\\svgwidth{\\columnwidth}\\input{' + os.path.basename(tex_path) + '}')

    def export_as_pptx(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="PowerPoint (*.pptx);;All Files (*)",
                                     default_ext='.pptx')
        if output_file:
            self._export_editable(output_file, 'pptx')

    def export_as_illustrator(self):
        output_file = saveFileDialog(parent_window=self,
                                     extensions="Adobe Illustrator script (*.jsx);;All Files (*)",
                                     default_ext='.jsx')
        if output_file:
            self._export_editable(output_file, 'jsx')

    def _export_editable(self, output_file, fmt):
        """Editable export (PowerPoint or Illustrator script) of the current figure."""
        from pyfigures.gui.editable_export import capture_scene, write_pptx, write_jsx
        if not self.paint.EZFIG_panel.shapes_to_draw:
            QMessageBox.information(self, 'Nothing to export', 'The figure contains no panels.')
            return
        name = 'PowerPoint' if fmt == 'pptx' else 'Illustrator script'
        self.statusBar().showMessage(f'Exporting {name}, please wait...')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            scene = capture_scene(self.paint.EZFIG_panel, movies=fmt == 'pptx')
            if fmt == 'pptx':
                write_pptx(scene, output_file)
                extra = ''
            else:
                _, assets = write_jsx(scene, output_file)
                extra = ('\n\nKeep the folder ' + os.path.basename(assets) + ' next to it.\n'
                         'In Illustrator: File > Scripts > Other Script…')
        except Exception as e:
            traceback.print_exc()
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            QMessageBox.warning(self, f'{name} export failed', 'Could not export:\n' + str(e))
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f'Exported {os.path.basename(output_file)}')
        QMessageBox.information(self, f'{name} exported', 'Wrote ' + os.path.basename(output_file) + extra)

    def export_as_video(self):
        # only meaningful if the figure actually contains a video / time-stack panel
        if not self.paint.EZFIG_panel._collect_time_stacks():
            QMessageBox.information(self, 'No time-stack to animate',
                                    'This figure has no video or time-stack panel to animate.\n'
                                    'Drop a video (mp4/avi/mkv) or a t-stack image first.')
            return

        output_file = saveFileDialog(parent_window=self,
                                     extensions="Video Files (*.mp4 *.mov *.mkv *.webm *.avi);;All Files (*)",
                                     default_ext='.mp4')
        if not output_file:
            return
        if not output_file.lower().endswith('.avi'):
            # H.264 / VP9 need PyAV; without it the old MPEG-4 codec is written
            from pyfigures.gui.video_support import offer_video_support
            offer_video_support(self, 'h264')

        # how should panels shorter than the longest video behave past their end?
        box = QMessageBox(self)
        box.setWindowTitle('Shorter panels')
        box.setText('Some panels may have fewer frames than the longest video.\n'
                    'What should they show once they run out of frames?')
        freeze_btn = box.addButton('Freeze last frame', QMessageBox.AcceptRole)
        blank_btn = box.addButton('Blank (background) frame', QMessageBox.AcceptRole)
        box.addButton(QMessageBox.Cancel)
        box.exec_()
        clicked = box.clickedButton()
        if clicked not in (freeze_btn, blank_btn):
            return
        frame_mode = 'freeze' if clicked is freeze_btn else 'blank'

        bg_color = (0, 0, 0)
        if frame_mode == 'blank':
            from qtpy.QtWidgets import QColorDialog
            from qtpy.QtGui import QColor
            picked = QColorDialog.getColor(QColor(0, 0, 0), self, 'Background colour for blank frames')
            if picked.isValid():
                bg_color = (picked.red(), picked.green(), picked.blue())

        self.statusBar().showMessage('Rendering video, please wait...')
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            n = self.paint.EZFIG_panel.save_video(output_file, frame_mode=frame_mode, bg_color=bg_color)
        except Exception as e:
            traceback.print_exc()
            QApplication.restoreOverrideCursor()
            self.statusBar().clearMessage()
            QMessageBox.warning(self, 'Video export failed', 'Could not export the video:\n' + str(e))
            return
        QApplication.restoreOverrideCursor()
        self.statusBar().showMessage(f'Exported {n} frame(s) to {os.path.basename(output_file)}')

    def _render_png_without_prompt(self, path, dpi=150):
        """Render the figure to *path* for an internal preview (review HTML,
        comment viewer) at a fixed dpi — no "output DPI" question, which
        made no sense there (and cancelling it left no image to show)."""
        panel = self.paint.EZFIG_panel
        old_get_dpi = panel.get_dpi
        panel.get_dpi = (lambda _d=dpi: _d)
        try:
            panel.save(path)
        finally:
            panel.get_dpi = old_get_dpi

    def export_for_review(self):
        """Render the current figure and package it as a self-contained HTML
        file a reviewer can open in any browser (no install, no network) to
        drop click-to-pin comments on. See pyfigures.gui.review."""
        from pyfigures.gui.review import export_review_html, build_mailto_url, \
            default_review_request_text, reveal_in_file_manager
        import tempfile

        output_file = saveFileDialog(parent_window=self,
                                     extensions="HTML Files (*.html);;All Files (*)",
                                     default_ext='.html')
        if not output_file:
            return

        owner_email, ok = QInputDialog.getText(
            self, "Export for review",
            "Your email (optional — lets each reviewer's \"Send back by email\" "
            "button address the reply straight to you):",
            text=getattr(self, "_review_owner_email", ""))
        if ok:
            self._review_owner_email = owner_email.strip()
        owner_email = getattr(self, "_review_owner_email", "")

        source_name = os.path.splitext(os.path.basename(self.current_file or "figure"))[0]
        tmp_png = os.path.join(tempfile.gettempdir(), f"_pyfigures_review_{os.getpid()}.png")
        try:
            self._render_png_without_prompt(tmp_png)
            export_review_html(tmp_png, output_file, source_name=source_name, owner_email=owner_email)
        finally:
            try:
                os.remove(tmp_png)
            except OSError:
                pass

        reply = QMessageBox.question(
            self, "Exported for review",
            f"Saved {output_file}\n\nOpen an email draft to send it to your reviewer(s) now?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return

        recipients, ok = QInputDialog.getText(
            self, "Send for review", "Reviewer email address(es), comma-separated:")
        if not ok or not recipients.strip():
            return
        subject, body = default_review_request_text(source_name, os.path.basename(output_file))
        url = build_mailto_url(recipients.split(","), subject, body)
        QDesktopServices.openUrl(QUrl(url))
        reveal_in_file_manager(output_file)
        QMessageBox.information(
            self, "Almost done",
            "An email draft should now be open, and the exported file's folder has been "
            f"opened for you — drag {os.path.basename(output_file)} into the email as an "
            "attachment, then hit Send. (PyFigures never sends anything on its own.)")

    def import_review_comments(self):
        """Read back a reviewed HTML file and merge its comments into the
        sidecar review file for the currently open figure."""
        from pyfigures.gui.review import extract_comments, load_sidecar_comments, \
            save_sidecar_comments, merge_comments

        if not self.current_file:
            QMessageBox.warning(self, "No figure open",
                                "Save this figure first so review comments have somewhere to attach to.")
            return
        html_file = openFileNameDialog(parent_window=self,
                                       extensions="HTML Files (*.html);;All Files (*)")
        if not html_file:
            return
        try:
            incoming = extract_comments(html_file)
        except ValueError as e:
            QMessageBox.warning(self, "Import failed", str(e))
            return
        existing = load_sidecar_comments(self.current_file)
        merged = merge_comments(existing, incoming)
        save_sidecar_comments(self.current_file, merged)
        self.view_review_comments()

    def view_review_comments(self):
        """Show the current figure with all pending review comments pinned on it."""
        from pyfigures.gui.review import load_sidecar_comments, save_sidecar_comments, \
            show_review_comments_dialog
        import tempfile

        if not self.current_file:
            QMessageBox.information(self, "No review comments", "This figure has no saved review comments yet.")
            return
        comments = load_sidecar_comments(self.current_file)
        if not comments:
            QMessageBox.information(self, "No review comments", "No review comments have been imported for this figure yet.")
            return
        tmp_png = os.path.join(tempfile.gettempdir(), f"_pyfigures_review_view_{os.getpid()}.png")
        try:
            self._render_png_without_prompt(tmp_png)
            show_review_comments_dialog(self, tmp_png, comments,
                                        on_clear=lambda: save_sidecar_comments(self.current_file, []))
        finally:
            try:
                os.remove(tmp_png)
            except OSError:
                pass


if __name__ == '__main__':
    # with jvm_context():
    # vraiment pas mal --> j'y suis presque...
    import sys
    import threading

    try:
        import batoolset.IJ.ij_reader as ij_reader

        _use_ij_reader = True
    except ImportError:
        ij_reader = None
        _use_ij_reader = False

    if ij_reader is not None and ij_reader._is_fiji_cached():
        # Fiji already cached — init silently in background
        threading.Thread(target=ij_reader.init_ij, daemon=True).start()
    # else: not cached — init will happen lazily on first image open

    app = QApplication(sys.argv)
    try:
        from pyfigures.gui.portable_fonts import register_portable_fonts
        register_portable_fonts(app)
    except Exception:
        pass
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