from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from pyfigures.gui.lutmultiselector import LutWidget
import matplotlib.pyplot as plt
import numpy as np
from batoolset.img import guess_dimensions
from batoolset.strings.tools import reload_string_list, find_letter_before_h
# import pzfconfig # this is to store the path to be used for the consolidated files
from pyfigures.gui.scalebareditor import ScaleBarEditor
from pyfigures.gui.widget_for_inset import InsetWidget
import traceback
from batoolset.draw.shapes.rectangle2d import Rectangle2D
from batoolset.GUI.open import OpenFileOrFolderWidget
from batoolset.pyqt.tools import check_antialiasing, get_shape_after_rotation_and_crop, \
    get_original_shape_from_rect_and_angle, get_centroid, create_dim_slider, clear_layout, select_in_combobox, \
    getCtrlModifier, getCtrlModifierAsString
from batoolset.serialization.tools import clone_object
from pyfigures.gui.customdialog import CustomDialog
import sys
import os
import math
import qtawesome as qta
from functools import partial
from qtpy.QtGui import QPalette, QPainter, QColor, QIcon, QPen,QKeySequence, QMouseEvent,QImage,QTransform
from qtpy.QtSvg import QSvgGenerator
from qtpy.QtWidgets import QMenu, QApplication, QMainWindow, QPushButton, QWidget, QLabel,QCheckBox, QScrollArea,QWidget, \
    QAction, QProgressBar, QDockWidget, QSpinBox, QComboBox, QGridLayout, QDialog, QGroupBox, QDoubleSpinBox, QColorDialog, QVBoxLayout,QFormLayout,QHBoxLayout,QToolButton,QTabWidget,QTextEdit,QShortcut,QLineEdit, QSizePolicy, QMessageBox, QSlider
from batoolset.draw.shapes.Position import Position
from pyfigures.gui.textEditWatcher import TextEditWatcher
from batoolset.draw.shapes.group import Group, set_to_size
from batoolset.GUI.list_gui import ListGUI
from batoolset.draw.shapes.polygon2d import Polygon2D
from batoolset.draw.shapes.line2d import Line2D
from batoolset.draw.shapes.scalebar import ScaleBar
from batoolset.draw.shapes.square2d import Square2D
from batoolset.draw.shapes.ellipse2d import Ellipse2D
from batoolset.draw.shapes.circle2d import Circle2D
from batoolset.draw.shapes.freehand2d import Freehand2D
from batoolset.draw.shapes.rectangle2d import Rectangle2D
from batoolset.draw.shapes.point2d import Point2D
from batoolset.draw.shapes.polyline2d import PolyLine2D
from batoolset.draw.shapes.image2d import Image2D
from qtpy.QtCore import QPointF, QRectF, Qt, QRect, QSize, QPoint, QPointF, QTimer,Signal
from batoolset.draw.shapes.txt2d import TAText2D
from batoolset.figure.alignment import updateBoudingRect, setToHeight, setToWidth2
from pyfigures.gui.simple_text_editor import TextEditor
from batoolset.tools.logger import TA_logger # logging

logger = TA_logger()

__DEBUG__ = False

class VectorialDrawPane2(QWidget):

    FIT_TO_WIDTH = 0
    FIT_TO_HEIGHT = 1
    line_styles = [Qt.SolidLine, Qt.DashLine, Qt.DashDotLine, Qt.DotLine, Qt.DashDotDotLine, Qt.CustomDashLine]

    shapeAdded = Signal() # add a signal that emits when shapes are added
    selectionChanged = Signal() # add a signal that emits when there is a new selection
    shapeChanged = Signal()
    # TODO change parameters
    def __init__(self, parent=None, demo=False, background=None):
        super(QWidget, self).__init__(parent)

        self.ctrl_key = getCtrlModifierAsString()

        self.default_page_width = 512  # TODO change this at some point
        self.default_page_height = 768  # TODO change this at some point
        # color parameters for shape drawing
        self.contour_color = QColor(255, 255, 255)
        self.fill_color = None
        self.opacity = 1
        self.stroke = 0.65
        self.theta = 0
        self.positions = None
        self.shapes = []
        self.currently_drawn_shape = None
        self.shape_to_draw = Rectangle2D # None # Rectangle2D
        self.selected_shape = []
        self.background = background # this will code for the bg image over which we will always draw over --> TODO
        self.rotate_n_crop_polygon = None
        self.crops = [] # this will contain all the crops the user generated so that they can be exported easily!!!
        self.add_text_button = None
        self.filter_out_unwanted_shapes_based_on_distance = True # if set to True the tool will attempt to filter accidental drawings by the user (based on distance between draw points)

        # default scaling parameters # maybe allow users to set them
        self.scale = 1.0
        self.min_scaling_factor = 0.1
        self.max_scaling_factor = 20
        self.zoom_increment = 0.05

        # line style parameters
        self.line_style = None

        # arrowhead parameters
        self.arrowhead_width_scaler = 4
        self.arrowhead_height_scaler = 12
        self.drawing_mode = True
        # KEEP IMPORTANT required to track mouse even when not clicked
        self.setMouseTracking(True)  # KEEP IMPORTANT

        # demo = True
        if demo:
          from pyfigures.gui.keep_tst_images_for_pzf import demo_img
          self.background = demo_img()

        # self.update_size()
        # self.update()


    def set_scale(self, scale):
        # same scale nothing to do
        if scale == self.scale:
            return
        if scale >= self.max_scaling_factor:
            self.scale = self.max_scaling_factor
            logger.warning('Zoom exceeds max_scaling_factor --> ignoring')
        elif scale <= self.min_scaling_factor:
            self.scale = self.min_scaling_factor
            logger.warning('Zoom is below min_scaling_factor --> ignoring')
        else:
            self.scale = scale
        self.update_size()
        self.update()


    def updateBoudingRect(self):
        objects = []
        if self.background:
            objects.append(self.background)
        objects.extend(self.shapes)


        return updateBoudingRect(*objects)

    # pas trop dur en fait
    def scale_to_window(self, window_size, mode=FIT_TO_WIDTH, scroll_size=20):
        if window_size is not None:
            bounds = self.updateBoudingRect() #updateBoudingRect(*self.shapes)
            if mode == self.FIT_TO_WIDTH:
                scaling_to_fit = (window_size.width() - scroll_size) / bounds.width()
            else:
                scaling_to_fit = (window_size.height() - scroll_size) / bounds.height()
            self.set_scale(scaling_to_fit)

    def duplicate(self):
        if self.selected_shape is not None:
            copy = clone_object(self.selected_shape)

            if isinstance(copy, list):
                self.selected_shape = copy
                self.background.annotations.extend(copy)
            else:
                self.selected_shape = [copy]  # do select drawn shape
                self.background.annotations.append(copy)

            self.shapeAdded.emit()
            # print('duplicated copy',type(copy), copy)
            self.selectionChanged.emit()

    def reset_scale(self):
        self.set_scale(1)

    def zoom_in(self):
        self.set_scale(self.scale + self.zoom_increment)

    def zoom_out(self):
        self.set_scale(self.scale - self.zoom_increment)

    def color_picker(self, method_to_set_color):
        try:
            dialog = QColorDialog(self)
            dialog.show()
            result = dialog.exec_()
        except:
            logger.error('TODO here reimplement that')
            result =True

        if result == QDialog.Accepted:
            c = dialog.selectedColor()
            if c.isValid():  # make sure the user did not cancel otherwise ignore # useless with current code
                self.sender().setStyleSheet("background-color: " + str(c.name()))
                self.sender().setText(c.name())
                method_to_set_color(c)
        elif result == QDialog.Rejected:
            pass
        else:
            self.sender().setStyleSheet('background-color: none;')
            self.sender().setText('None')
            method_to_set_color(None)
            # return None

    def change_shape(self):
        sender = self.sender().toolTip().lower()

        if 'square' in sender:
            self.shape_to_draw = Square2D
        elif 'rect' in sender:
            self.shape_to_draw = Rectangle2D
        elif 'elli' in sender:
            self.shape_to_draw = Ellipse2D
        elif 'ircle' in sender:
            self.shape_to_draw = Circle2D
        elif 'point' in sender:
            self.shape_to_draw = Point2D
        elif 'free' in sender or 'hand' in sender:
            self.shape_to_draw = Freehand2D
        elif 'poly' in sender and 'line' in sender:
            self.shape_to_draw = PolyLine2D
        elif 'poly' in sender and 'gon' in sender:
            self.shape_to_draw = Polygon2D
        elif 'line' in sender:
            self.shape_to_draw = Line2D
        elif 'arrow' in sender and not 'ual' in sender:
            self.shape_to_draw = partial(Line2D, arrow=True)
        elif 'arrow' in sender and 'ual' in sender:
            self.shape_to_draw = partial(Line2D, arrow=True, arrow_at_both_ends=True)
        elif 'oating' in sender:
            self.shape_to_draw = partial(TAText2D, text='<font color=#66FF66>Your text here</font>', placement=None)
        elif 'cale' in sender:
            self.shape_to_draw = partial(ScaleBar, bar_width_in_units=100, legend=TAText2D('<font color=#FFFFFF>Double click scale bar to edit</font>'), placement='bottom-right')
        else:
            print(sender, 'Shape not supported yet!!!')
            self.shape_to_draw = None

    def __save_selection_position(self):
        self.positions = None
        if self.selected_shape is None or not self.selected_shape:
            return self.positions
        self.positions = [img.topLeft() for img in self.selected_shape]

    def __restore_selection_position(self):
        if self.selected_shape is None  or not self.selected_shape:
            return
        if self.positions is None:
            return
        for pos in range(len(self.positions)):
            self.selected_shape[pos].setTopLeft(self.positions[pos])

    def paintEvent(self, event):

        # return
        # the paint is done here

        # super().update()

        painter = QPainter(self)
        painter.setOpacity(1)
        visibleRect = None

        # very dirty hack to always draw shapes correctly --> some day understand why

        # below is the code that makes the drawing twice -−> why is that !!!
        if self.background:
            try:
                image = QImage(100, 100, QImage.Format_RGB32)
                painter2 = QPainter(image)
                self.background.draw(painter2)
                painter2.end()
                del painter2
                del image
            except Exception as e:
                traceback.print_exc()
                print('drawing error can be ignored:', str(e))
                pass

        painter.save()
        if self.scale != 1.0:
            painter.scale(self.scale, self.scale)

        if self.background is not None:
            self.background.draw_bg(painter, parent=None, restore_painter_in_the_end=False)
            self.background.draw_annotations(painter, parent=None, restore_painter_in_the_end=True)
        else:
            pass

        if self.rotate_n_crop_polygon:
            painter.save()
            pen = QPen(Qt.cyan,2)
            painter.setPen(pen)
            painter.drawPolygon(self.rotate_n_crop_polygon)
            painter.restore()

        for shape in self.shapes:
            if visibleRect is not None:
                # only draws if in visible rect
                if shape.boundingRect().intersects(QRectF(visibleRect)):
                    sel = shape.draw(painter)
            else:
                sel = shape.draw(painter)

        if self.currently_drawn_shape is not None:
            self.currently_drawn_shape.draw(painter)

        sel = self.create_master_rect()

        # draw a selection on top of everything else
        self.draw_sel(sel,painter)

        painter.restore()
        painter.end()
        del painter

    def draw_sel(self, sel, painter, col=QColor(0xFF0000)):
        if sel is not None and self.shapes:
            pen = QPen(col)
            pen.setWidthF(3)  # makes the sel much more visible --> so really use that!!!
            pen.setStyle(Qt.DashDotLine)
            painter.setPen(pen)  # draw red transparent selection
            painter.setOpacity(1)
            painter.drawRect(sel)

    def group_contains(self, x, y):
        # checks if master rect for group contains click
        # get bounds and create union and compare
        master_rect = self.create_master_rect()
        if master_rect is None:
            return False
        return master_rect.contains(int(x), int(y))

    def create_master_rect(self):
        master_rect = None
        if self.selected_shape:
            for shape in self.selected_shape:
                if master_rect is None:
                    # master_rect = shape.boundingRect()
                    master_rect = shape.getRect(all=True)
                else:
                    # master_rect = master_rect.united(shape.boundingRect())
                    master_rect = master_rect.united(shape.getRect(all=True))
        return master_rect

    def set_rotation(self, theta, ignore=False):
        if theta is not None:
            self.theta = theta
        if ignore:
            return
        if self.selected_shape:
            for shape in self.selected_shape:
                if not isinstance(shape, Group) and not isinstance(shape,Point2D) and not isinstance(shape, Circle2D):
                    shape.theta = self.theta
            self.update()

    def set_opacity(self, opacity, ignore=False):
        if opacity is not None:
            if opacity >= 2:
                opacity /= 100
            if opacity < 0:
                logger.error('opacity must be between 0 and 1 or 0 and 100')
                return
            self.opacity = opacity
        if ignore:
            return
        if self.selected_shape:
            for shape in self.selected_shape:
                if not isinstance(shape, Group):
                    shape.set_opacity(self.opacity)
            self.update()

    def set_stroke(self, stroke, ignore=False):
        if stroke is not None:
            self.stroke = stroke
        if ignore:
            return
        if self.selected_shape:
            for shape in self.selected_shape:
                if not isinstance(shape, Group):
                    shape.stroke = self.stroke
            self.update()

    def set_fill_color(self, fill_color, ignore=False):
        self.fill_color = fill_color
        if self.fill_color:
            if isinstance(self.fill_color, QColor):
                self.fill_color = self.fill_color.rgb()&0xFFFFFF
        if ignore:
            return
        if self.selected_shape:
            for shape in self.selected_shape:
                if not isinstance(shape, Group):
                    shape.fill_color = self.fill_color
            self.update()
            self.shapeChanged.emit()
        else:
            if self.background is not None:
                self.background.fill_color = self.fill_color
                self.update()
                self.shapeChanged.emit()

    def set_contour_color(self, contour_color, ignore=False):
        self.contour_color = contour_color
        if self.contour_color:
            if isinstance(self.contour_color, QColor):
                self.contour_color = self.contour_color.rgb() & 0xFFFFFF
        else:
            self.contour_color=0xFFFFFF # do not allow no color
        if ignore:
            return
        if self.selected_shape:
            for shape in self.selected_shape:
                if not isinstance(shape, Group):
                    shape.color = self.contour_color
            self.update()
            self.shapeChanged.emit()

    def set_arrowhead_size(self, width, height, ignore=False):
        self.arrowhead_width_scaler = width
        self.arrowhead_height_scaler = height
        if ignore:
            return
        if self.selected_shape:
            smthg_changed= False
            for shape in self.selected_shape:
                if isinstance(shape, Line2D):
                    if shape.arrow:
                        shape.arrowhead_width_scaler = self.arrowhead_width_scaler
                        shape.arrowhead_height_scaler = self.arrowhead_height_scaler
                        smthg_changed=True
            if smthg_changed:
                self.update()


    def set_line_style(self, style, ignore=False):
        '''allows lines to be dashed or dotted or have custom pattern

        :param style: a list of numbers or any of the following Qt.SolidLine, Qt.DashLine, Qt.DashDotLine, Qt.DotLine, Qt.DashDotDotLine but not Qt.CustomDashLine, Qt.CustomDashLine is assumed by default if a list is passed in. None is also a valid value that resets the line --> assume plain line
        :return:
        '''

        # TODO add more controls or do it in a more comprehensive way
        if isinstance(style, list):
            if len(style) % 2 != 0:
                logger.error('Dash pattern not of even length --> ignoring, try 1,4 or 1,4,5,4 or alike')
                return
        else:
            if style not in self.line_styles[:-1]:
                logger.error('Unknonw Dash pattern --> ignoring')
                return

        self.line_style = style
        if ignore:
            return
        # if style is a list then assume custom pattern otherwise apply solidline
        if self.selected_shape:
            for shape in self.selected_shape:
                shape.set_line_style(self.line_style)
            self.update()

    # i guess this needs a recode but see later
    def bring_to_front(self):
        # print('bring sel to front')
        if self.selected_shape:
            self.shapes = [e for e in self.shapes if e not in self.selected_shape]
            self.shapes.extend(self.selected_shape)
        self.update()

    def send_to_back(self):
        # print('send to back')
        if self.selected_shape:
            self.shapes = [e for e in self.shapes if e not in self.selected_shape]
            # TODO maybe I should keep the original order in the list, but ok for now and no big deal
            for shape in self.selected_shape:
                self.shapes.insert(0, shape)
        self.update()

    def move_to_origin(self): # TODO --> make this fire an orderChanged like for the list and add a listener -−> that should do the job
        if self.selected_shape:
            for shape in self.selected_shape:
                shape.setTopLeft(QPointF(0,0))  # TODO fix setTopLeft that it always works the same for every shapes and takes point or values here 0,0 does not work for some shapes dunno which
        self.update()

    def erode(self):
        # print('bring sel to front')
        if self.selected_shape:
            for shape in self.selected_shape:
                shape.erode()
        self.update()

    def dilate(self):
        # print('bring sel to front')
        if self.selected_shape:
            for shape in self.selected_shape:
                shape.dilate()
        self.update()

    def remove_selection(self):
        # print('called remove sel', self.selected_shape, self.currently_drawn_shape)
        if self.selected_shape:
            self.shapes = [e for e in self.shapes if e not in self.selected_shape]
            del self.selected_shape
            self.selected_shape = []
            self.selectionChanged.emit()
        del self.currently_drawn_shape
        self.currently_drawn_shape = None
        self.update()

    def mousePressEvent(self, event):
        self.dragged = False
        # self.can_go_deeper = False
        if event.button() == Qt.LeftButton:
            self.drawing = True
            self.lastPoint = event.position() / self.scale
            self.firstPoint = event.position() / self.scale

            shapeFound = False
            if self.currently_drawn_shape is None:
                for shape in reversed(self.shapes):
                    if shape.contains(self.lastPoint) and not (self.selected_shape is None or shape in self.selected_shape):
                        logger.debug('you clicked shape:' + str(shape))

                        if event.modifiers() == getCtrlModifier():
                            if shape not in self.selected_shape:  # avoid doublons
                                self.selected_shape.append(shape)  # add shape to group
                                logger.debug('adding shape to group')
                                # shapeFound = True
                        else:
                            # if selected shape was already this one then browse inside further --> go deeper
                            # print('testing')
                            if not self.group_contains(self.lastPoint.x(), self.lastPoint.y()):
                                # print('going not deeper')
                                self.selected_shape = [shape]
                                self.selectionChanged.emit()
                                logger.debug('only one element is selected')
                                # shapeFound = True
                            else:
                                # self.can_go_deeper = True
                                pass

                        self.__save_selection_position()

                        # update drawing of selection
                        self.update_size()
                        self.update()
                        return
                    # else:
                    #     # print('shape was already selected ...')
                    #     # if self.selected_shape is not None and len(self.selected_shape)==1 and shape in self.selected_shape:
                    #     #     self.can_go_deeper = True
                    #     pass


                if not shapeFound and event.modifiers() == getCtrlModifier():
                    for shape in reversed(self.shapes):
                        if shape.contains(self.lastPoint):
                            if shape in self.selected_shape:  # avoid doublons
                                logger.debug('you clicked again shape:' + str(shape))
                                self.selected_shape.remove(shape)  # add shape to group
                                logger.debug('removing a shape from group')
                                shapeFound = True
                # no shape found --> reset sel
                if not shapeFound and not self.group_contains(self.lastPoint.x(), self.lastPoint.y()):
                    logger.debug('resetting sel')
                    self.selected_shape = []
                    self.selectionChanged.emit()

            # check if a shape is selected and only move that
            if self.drawing_mode and not self.selected_shape and self.currently_drawn_shape is None:
                # do not reset shape if not done drawing...
                if self.shape_to_draw is not None:
                    # here I need to pass in the parameters for color and stroke, etc...
                    parameters = {}
                    if self.stroke is not None:
                        parameters['stroke'] = self.stroke
                    # pass fill color to new object

                    if isinstance(self.fill_color, QColor):
                        parameters['fill_color'] = int(self.fill_color.name().replace('#', ''), 16)
                    else:
                        parameters['fill_color'] = self.fill_color

                    # print(parameters['fill_color'])
                    # pass contour color to new object
                    # if self.contour_color is not None:
                    if isinstance(self.contour_color, QColor):
                        parameters['color'] = int(self.contour_color.name().replace('#', ''), 16)
                    else:
                        if self.contour_color is None:
                            self.contour_color=0xFFFFFF # very dirty hack --> why do I have to do that ????
                        parameters['color'] = self.contour_color # set it even if None
                    # else:
                    #     # allow None color for contour if fill color is set
                    #     if self.fill_color is not None:
                    #         parameters['color'] = None
                    # pass line style parameters to new object
                    if self.line_style is not None:
                        parameters['line_style'] = self.line_style
                    if self.opacity is not None:
                        parameters['opacity'] = self.opacity
                    if self.arrowhead_width_scaler is not None:
                        parameters['arrowhead_width_scaler'] = self.arrowhead_width_scaler
                    if self.arrowhead_height_scaler is not None:
                        parameters['arrowhead_height_scaler'] = self.arrowhead_height_scaler

                    # not a good idea to set angle here...
                    # if self.theta is not None and self.theta != 0:
                    #     parameters['theta'] = self.theta

                    # if no color for contour and filling --> prevent drawing shape and raise a warning
                    if self.fill_color is None and self.contour_color is None :
                        self.currently_drawn_shape = None
                        # show a warning
                        print('no color set for line contour --> nothing to draw1...')
                        return
                    # handle shapes that need a contour color to be drawn
                    elif self.contour_color is None and self.shape_to_draw in [Line2D, PolyLine2D,
                                                                               Freehand2D, TAText2D, ScaleBar]:  # TODO check if freehand is filled or not --> maybe change that the future # , Freehand2D
                        self.currently_drawn_shape = None
                        # show a warning
                        print('no color set for line contour --> nothing to draw2...')
                        return

                    self.currently_drawn_shape = self.shape_to_draw(**parameters)
                else:
                    self.currently_drawn_shape = None

            if self.drawing_mode and not self.selected_shape:
                if self.currently_drawn_shape is not None:
                    # print("here", self.currently_drawn_shape)
                    # print(self.currently_drawn_shape.listVertices())
                    # TODO fix that cause not really nice in fact setTopLeft should only be used to set the origin of the stuff and nothing else here it may be set origin (first point)
                    if not isinstance(self.currently_drawn_shape, Polygon2D):
                        self.currently_drawn_shape.setTopLeft(QPointF(self.lastPoint.x(), self.lastPoint.y()))
                    else:
                        self.currently_drawn_shape.append(QPointF(self.lastPoint.x(), self.lastPoint.y()))

            self.update_size()
            self.update()


    def mouseMoveEvent(self, event):
        self.dragged = True
        if event.buttons() and Qt.LeftButton:
            if self.selected_shape and self.currently_drawn_shape is None:
                logger.debug('moving' + str(self.selected_shape))
                for shape in self.selected_shape:
                    shape.translate(event.position() / self.scale - self.lastPoint)
                self.update_size()
                self.update()

        if self.currently_drawn_shape is not None and not isinstance(self.currently_drawn_shape, (TAText2D, ScaleBar)):
            self.currently_drawn_shape.add(self.firstPoint, self.lastPoint)
            self.update_size()
            self.update()

        self.lastPoint = event.position() / self.scale

    def mouseReleaseEvent(self, event):
        self.dragged=False

        # I probably do not need that anymore
        if event.button() == Qt.LeftButton:
            self.drawing = False
            if self.drawing_mode and self.currently_drawn_shape is not None:
                if not isinstance(self.currently_drawn_shape, (TAText2D, ScaleBar)):
                    self.currently_drawn_shape.add(self.firstPoint, self.lastPoint)
                # see how to do that


                if isinstance(self.currently_drawn_shape, Freehand2D):
                    #     # this closes the freehand shape
                    self.currently_drawn_shape.add(self.lastPoint,
                                                   self.firstPoint)  # should I keep it closed or opened maybe do two buttons and ask for the option by a button
                if isinstance(self.currently_drawn_shape, Freehand2D) or (
                        not isinstance(self.currently_drawn_shape, PolyLine2D) and not isinstance(
                    self.currently_drawn_shape,Polygon2D)):

                    size_ok = self.check_shape_size_before_adding_it()
                    if size_ok:
                        self.shapes.append(self.currently_drawn_shape)
                        self.shapeAdded.emit()
                        self.selected_shape = [self.currently_drawn_shape]  # do select drawn shape
                        self.selectionChanged.emit()

                        if isinstance(self.currently_drawn_shape, (TAText2D, ScaleBar)):
                            # we do not want to add too many of these because this is annoying
                            self.shape_to_draw = None

                        self.currently_drawn_shape = None

                    else:
                        return

                self.update_size()
                self.update()



    def check_shape_size_before_adding_it(self):
        if self.filter_out_unwanted_shapes_based_on_distance:  # TODO maybe allow arrowheads to be drawn and stay small, allow lines only if they are in arrwohed only mode (if so do not allow the body of the li,ne to be drawn)
            rect = self.currently_drawn_shape.getRect()

            # print('checking drawn rect', rect)

            if not isinstance(self.currently_drawn_shape,(Point2D, TAText2D, ScaleBar)) and (abs(rect.width())* self.scale < 40 and abs(rect.height())* self.scale<40):
                logger.warning(str(self.currently_drawn_shape) + '-->' +
                               'distance between first and last clicks too small, drawing is ignored, the software assumes unintended drawing, zoom more (' + self.ctrl_key + ' +) and redraw the shape if wanted')
                self.currently_drawn_shape = None
                self.update()
                # print(distance )
                return False
            return True



    def update_size(self):
        # seems to work but do this properly and handle scale ???
        # shapes = [self.background] # I need append the bg to the list of objects
        # shapes.extend(self.shapes)

        # bounds = updateBoudingRect(*shapes)
        bounds = self.updateBoudingRect()

        # this never changes -−> why is that
        # print('just checking',self.background.get_raw_size(), self.background.boundingRect(), self.background.width(),self.background.height(),bounds)


        if bounds:
            # print('bds3', bounds)
            self.setMinimumSize(int((bounds.width() + bounds.x()) * self.scale),
                                int((bounds.height() + bounds.y()) * self.scale))  # marche
        else:
            self.setMinimumSize(512,512)  # marche

    def mouseDoubleClickEvent(self, event):
        # print(event)
        if self.selected_shape:
            if isinstance(self.selected_shape[0], TAText2D):
                # print('double clicked on a text --> further edit it')
                # do a popup for editing the text --> make it a dialog as the others maybe
                # TODO
                # --> in a way this is simpler!!!!
                text = self.selected_shape[0].getHtmlText()
                editor = TextEditor(self.selected_shape[0], select_all=True)

                custom_dialog = CustomDialog(title="Edit text", message="Do you want to proceed?", main_widget=editor, parent=self, options=['Ok','Cancel'], auto_adjust=True) # that is really very good --> I can do it like that
                # custom_dialog.adjustSize()
                result = custom_dialog.exec_()
                if result:
                    # self.selected_shape[0].sync_text() # make sure the text is synced

                    # print('in there')

                    # in fact here I don't want to have the stuff
                    self.shapeChanged.emit()
                    self.selectionChanged.emit()
                else:
                    self.selected_shape[0].setText(text)

            if isinstance(self.selected_shape[0], ScaleBar):
                scale_bar = self.selected_shape[0]
                clone_of_text = None
                try:
                    clone_of_text = clone_object(scale_bar.legend)
                except:
                    pass
                bar_size = scale_bar.bar_width_in_units
                bar_placement = scale_bar.placement

                editor = ScaleBarEditor(self,scale_bar)

                custom_dialog = CustomDialog(title="Edit ScaleBar", message="Do you want to proceed?", main_widget=editor, parent=self, options=['Ok','Cancel'], auto_adjust=True) # that is really very good --> I can do it like that
                result = custom_dialog.exec_()
                if result:
                    scale = editor.getScaleBar()
                    self.selected_shape[0].__init__(**scale.to_dict())


                    self.update()

                    # try:
                    #     image = QImage(100, 100, QImage.Format_RGB32)
                    #     painter = QPainter(image)
                    #     self.background.draw(painter)
                    #     painter.end()
                    #     del painter
                    # except Exception as e:
                    #     traceback.print_exc()
                    #     print('drawing error can be ignored:', str(e))
                    # pass

                    self.update_size()
                    self.shapeChanged.emit()



                    # self.selectionChanged.emit()
                else:
                    scale_bar.legend = clone_of_text
                    scale_bar.setBarWidth(bar_size)
                    scale_bar.update_bar_at_scale(1.)
                    scale_bar.placement = bar_placement

            # if the user clicks on an inset image2D then offer change settings of inset
            if isinstance(self.selected_shape[0], Image2D):
                editor = InsetWidget(self,self.selected_shape[0])
                custom_dialog = CustomDialog(title="Edit Inset", message="Do you want to proceed?", main_widget=editor, parent=self, options=['Ok','Cancel'], auto_adjust=True) # that is really very good --> I can do it like that
                result = custom_dialog.exec_()
                if result:
                    color = None
                    try:
                        color = editor.get_color().rgb()
                    except:
                        pass
                    fraction = editor.get_percentage()
                    border_size = editor.get_border_size()
                    self.selected_shape[0].border_size = border_size
                    self.selected_shape[0].border_color = color
                    self.selected_shape[0].fraction_of_parent_image_width_if_image_is_inset = fraction

                    # dirty hack to force repositioning of inset
                    # try:
                    #     image = QImage(100, 100, QImage.Format_RGB32)
                    #     painter = QPainter(image)
                    #     self.background.draw(painter)
                    #     painter.end()
                    #     del painter
                    # except Exception as e:
                    #     traceback.print_exc()
                    #     print('drawing error can be ignored:', str(e))
                    # pass

                    # in fact here I don't want to have the stuff
                    self.shapeChanged.emit()
                    self.selectionChanged.emit()

        if isinstance(self.currently_drawn_shape, PolyLine2D) or isinstance(self.currently_drawn_shape, Polygon2D):

            size_ok = self.check_shape_size_before_adding_it()
            if size_ok:
                self.shapes.append(self.currently_drawn_shape)
                self.shapeAdded.emit()
                self.selected_shape = [self.currently_drawn_shape]  # do select drawn shape
                self.selectionChanged.emit()
                self.currently_drawn_shape = None

    # this contains the right click event
    # adds context/right click menu but only in vectorial mode
    def contextMenuEvent(self, event):

        event.ignore()

        if False: # maybe some day add menus there
            # if not self.vdp.active:
            #     return
            cmenu = QMenu(self)
            # newAct = cmenu.addAction("New")
            # opnAct = cmenu.addAction("Open")
            quitAct = cmenu.addAction("Quit")
            action = cmenu.exec_(self.mapToGlobal(event.pos()))
            if action == quitAct:
                # qApp.quit()
                sys.exit(0)

    def cm_to_inch(self, size_in_cm):
        return size_in_cm / 2.54

    def scaling_factor_to_achieve_DPI(self, desired_dpi):
        return desired_dpi / 72

    # TODO maybe get bounding box size in px by measuring the real bounding box this is especially important for raster images so that everything is really saved...
    SVG_INKSCAPE = 96
    SVG_ILLUSTRATOR = 72

    def paint(self, painter):
        painter.save()
        for shape in self.shapes:
            shape.draw(painter)
        painter.restore()

    def getBounds(self):
        # loop over shape to get bounds to be able to draw an image
        bounds = QRectF()
        max_width = 0
        max_height = 0
        for shape in self.shapes:
            rect = shape.boundingRect()
            max_width = max(max_width, rect.x() + rect.width())
            max_height = max(max_height, rect.y() + rect.height())
        bounds.setWidth(max_width)
        bounds.setHeight(max_height)
        return bounds

class MainWindow(QWidget):

    normalization_params_changed = Signal(dict)

    def __init__(self, qt_viewer=None):
        QWidget.__init__(self, parent=None)
        self.ctrl_key = getCtrlModifierAsString()
        self.ignore_changes = False # can be used to ignore GUI inputs without having to disconnect and reconnect them

        self.CURRENT_MODE = True
        self.qt_viewer = qt_viewer

        self.qt_viewer.shapeAdded.connect(self.shape_added)
        self.qt_viewer.shapeChanged.connect(self.shape_changed)
        self.qt_viewer.selectionChanged.connect(self.selectionUpdated)

        # self._qt_window = self
        # self._qt_window.setAttribute(Qt.WA_DeleteOnClose)
        # self._qt_center = QWidget(self._qt_window)
        # self.scrollArea = QScrollArea(self.qt_viewer)
        self.scrollArea = QScrollArea()

        self.scrollArea.setBackgroundRole(QPalette.Dark)

        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setWidget(self.qt_viewer)

        self.ignore_changes = False # this is set to true if value changes should be ignored

        self.dimsliders = [] # will contain all the dimensions that can be edited
        self.channel_boxes = [] # will contain all the channels to be displayed

        if True:
            # Create actions
            self.zoomInAct = QAction("Zoom &In (25%)", self, shortcut="" + self.ctrl_key + "++",
                                     enabled=True, triggered=self.qt_viewer.zoom_in)
            self.zoomOutAct = QAction("Zoom &Out (25%)", self, shortcut="" + self.ctrl_key + "+-",
                                      enabled=True, triggered=self.qt_viewer.zoom_out)
            self.normalSizeAct = QAction("&Normal Size", self, shortcut="" + self.ctrl_key + "+N",
                                         enabled=True, triggered=self.qt_viewer.reset_scale)
            self.fitToWindowAct = QAction("&Fit to Window", self, shortcut="" + self.ctrl_key + "+F",
                                          enabled=True, triggered=self.fitToWindow)
            self.showDrawWidgetAct = QAction("Draw widget", self, enabled=True,
                                             shortcut="", triggered=self.show_draw_widget)

            self.duplicate = QAction("Duplicate", self, shortcut="" + self.ctrl_key + "+D",
                                     enabled=True, triggered=self.qt_viewer.duplicate)
            self.duplicate2 = QAction("Copy/Paste", self, shortcut="" + self.ctrl_key + "+V",
                                     enabled=True, triggered=self.qt_viewer.duplicate)

            # Add actions to main window
            self.addAction(self.zoomInAct)
            self.addAction(self.zoomOutAct)
            self.addAction(self.normalSizeAct)
            self.addAction(self.fitToWindowAct)
            self.addAction(self.showDrawWidgetAct)
            self.addAction(self.duplicate)
            self.addAction(self.duplicate2)

            # Setup hotkeys
            deleteShortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
            deleteShortcut.activated.connect(self.down)

            # test function
            test_shortcut = QShortcut(QKeySequence("" + self.ctrl_key + "+T"), self)
            test_shortcut.activated.connect(self.test_function)

              # add status bar
        if False:
            statusBar = self.statusBar()  # sets an empty status bar --> then can add messages in it
            self.progress = QProgressBar(self)
            self.progress.setGeometry(200, 80, 250, 20)
            statusBar.addWidget(self.progress)

        # allow DND
        if True:
            # KEEP IMPORTANT absolutely required to allow DND on window
            self.setAcceptDrops(True)  # KEEP IMPORTANT

        if False:
            # Create a dock widget
            self.dockWidget = QDockWidget("Dock Widget", self)

            # Create a widget to contain the contents of the dock widget
            dockWidgetContents = QWidget()
            dockWidgetContentsLayout = QVBoxLayout(dockWidgetContents)

            # Add contents to the dock widget
            dockWidgetContentsLayout.addWidget(QLabel("Dock Widget Contents"))

            # Set the contents of the dock widget
            self.dockWidget.setWidget(dockWidgetContents)

            # Add the dock widget to a layout
            mainLayout = QHBoxLayout(self)
            mainLayout.addWidget(self._qt_center)
            mainLayout.addWidget(self.dockWidget)

            # Set the layout as the main layout of the QWidget
            self.setLayout(mainLayout)

        if True:
            # Create a widget to hold the scroll area and the button
            # self.main_widget = QWidget()
            # self.main_layout = QVBoxLayout(self.main_widget) # this line seems useless and can be commneted out
            # self.scroll_area = QScrollArea()
            # self.main_layout.addWidget(self.scroll_area) # this line seems useless and can be commneted out

            # Create a widget to hold the scroll area content
            self.content_widget = QWidget()
            # self.scroll_area.setWidget(self.content_widget)

            self.script_widget = QWidget()
            layout_script = QVBoxLayout(self.script_widget)
            layout_script.addWidget(QLabel('Script:'))
            if False:
                self.script_label = QLabel('Status: <font color=#00FF00>ok</font>')  # maybe I shall allow to select a file there to replace the original
                layout_script.addWidget(self.script_label)
            self.script_text_edit = QTextEdit(self)
            layout_script.addWidget(self.script_text_edit)
            self.execute_script_button = QPushButton('Add and Execute') # TODO --> add a big and strong warning to that
            self.execute_script_button.setFocusPolicy(Qt.NoFocus)
            layout_script.addWidget(self.execute_script_button)
            self.execute_script_button.clicked.connect(self.execute_script)
            layout_script.addWidget(QLabel('Log:'))
            self.script_log = QTextEdit(self)
            self.script_log.setReadOnly(True)
            layout_script.addWidget(self.script_log)

            self.comments_widget= QWidget()
            layout_comments = QVBoxLayout(self.comments_widget)

            self.input_file_widget = OpenFileOrFolderWidget(parent_window=self, add_timer_to_changetext=True,
                                                      show_ok_or_not_icon=True,  # label_text=label_input,
                                                      show_size=True,
                                                      tip_text='Drag and drop file(s)',
                                                      # objectName='open_input_button',
                                                      finalize_text_change_method_overrider=self.finalize_text_change_method_overrider,
                                                      allow_multiple_drop = True,
                                                      is_file=True,
                                                      use_qtextedit=True)  # objectName +'open_input_button'
            layout_comments.addWidget(self.input_file_widget)

            scale_parameters_layout = QHBoxLayout()
            label = QLabel('Pixel to unit conversion factor:<br><i>NB: if 0/unknown assuming 1</i>')
            # label_hint = QLabel('')
            scale_parameters_layout.addWidget(label)

            self.scale_conversion_spinner = QDoubleSpinBox()
            self.scale_conversion_spinner.setDecimals(6) # show 6 decimals after comma --> can be useful
            self.scale_conversion_spinner.setSingleStep(0.01)
            self.scale_conversion_spinner.setRange(0, 1000)
            self.scale_conversion_spinner.setValue(0)
            # Connect the valueChanged signal to the slot
            self.scale_conversion_spinner.valueChanged.connect(self.scale_conversion_spinner_changed)
            scale_parameters_layout.addWidget(self.scale_conversion_spinner)
            layout_comments.addLayout(scale_parameters_layout)

            label = QLabel('User comments:')
            layout_comments.addWidget(label)

            self.comments_text_edit= QTextEdit(self)
            layout_comments.addWidget(self.comments_text_edit)

            # indeed --> put a group here where one can play with these parameters and then see how to save them if there is an error -−> just roll back to orig maybe -−> TODO
            self.image_dimension_browser_toolbox = QGroupBox('Dimensions', objectName='image_dimension_browser_toolbox')
            self.image_dimension_browser_toolbox.setEnabled(False)
            # self.image_dimension_browser_toolbox.setVisible(False)
            self.image_dimension_browser_toolbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.image_dimension_browser_toolbox_layout = QVBoxLayout(self.image_dimension_browser_toolbox)

            self.image_projection_box = QGroupBox('Projection', objectName='image_projection_box')
            self.image_projection_box.setEnabled(True)
            self.image_projection_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            self.image_projection_box_layout = QVBoxLayout(self.image_projection_box)
            self.projection_combo_box = QComboBox()
            self.projection_combo_box.addItem("None", None) # I didn't know I could do that --> that simplifies a lot the stuff!!!
            self.projection_combo_box.addItem("Max", "max")
            self.projection_combo_box.addItem("Min", "min")
            self.projection_combo_box.addItem("Avg", "avg")
            # self.projection_combo_box.addItem("Median", "median") # TODO --> add that later at some point



            self.update_projection() # need load this at the beginning

            self.projection_combo_box.currentIndexChanged.connect(self.projection_changed)

            self.image_projection_box_layout.addWidget(self.projection_combo_box)
            layout_comments.addWidget(self.image_projection_box)

            self.image_normalization_box = QGroupBox('Normalization', objectName='image_normalization_box')
            self.image_normalization_box.setEnabled(True)
            self.image_normalization_box_layout = QFormLayout(self.image_normalization_box)

            # your other code here
            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.setInterval(800)  # delay in milliseconds
            self.timer.timeout.connect(self.update_other_spin_box)
            self.source = None

            # your other code here
            self.timer_dim_slider = QTimer(self)
            self.timer_dim_slider.setSingleShot(True)
            self.timer_dim_slider.setInterval(200)  # delay in milliseconds
            self.timer_dim_slider.timeout.connect(self.slider_dimension_value_changed)


            self.min_max_combo_box = QComboBox()
            # self.min_combo_box.addItem("Auto", "auto")
            self.min_max_combo_box.addItem("Whole Stack (all dims)", "all")
            self.min_max_combo_box.addItem("Displayed Only", "display")
            self.min_max_combo_box.addItem("Custom", "custom")


            self.min_spin_box = QDoubleSpinBox()
            self.min_spin_box.setEnabled(False)
            self.min_spin_box.setRange(0, 2 ** 32-1) # make sure it is always below
            self.min_spin_box.setDecimals(0)
            self.min_spin_box.setValue(0)

            #
            # self.max_combo_box = QComboBox()
            # # self.max_combo_box.addItem("Auto", "auto")
            # self.max_combo_box.addItem("Whole Stack (all dims)", "all")
            # self.max_combo_box.addItem("Displayed Only", "display")
            # self.max_combo_box.addItem("Custom", "custom")


            self.max_spin_box = QDoubleSpinBox()
            self.max_spin_box.setEnabled(False)
            self.max_spin_box.setRange(1, 2 ** 32) # make sure it is awlays above
            self.max_spin_box.setDecimals(0)
            self.max_spin_box.setValue(255)


            self.per_channel_checkbox = QCheckBox("Per Channel")
            self.ignore_hot_spots = QCheckBox("Ignore hot px (<0.001 of the img)")
            # self.ignore_hot_spots.setChecked(True)



            self.image_normalization_box_layout.addRow(QLabel("Min-Max Value Range:"), self.min_max_combo_box)
            self.image_normalization_box_layout.addRow(QLabel("Min Value:"), self.min_spin_box)
            # self.image_normalization_box_layout.addRow(QLabel("Max Value Range:"), self.max_combo_box)
            self.image_normalization_box_layout.addRow(QLabel("Max Value:"), self.max_spin_box)
            self.image_normalization_box_layout.addRow(self.per_channel_checkbox) # TODO -> add and activate this later
            self.image_normalization_box_layout.addRow(self.ignore_hot_spots) # TODO -> add and activate this later

            # self.update_normalization()

            self.min_spin_box.valueChanged.connect(self.on_min_changed)
            self.min_max_combo_box.currentIndexChanged.connect(self.on_min_max_combo_box_changed)
            # self.max_combo_box.currentIndexChanged.connect(self.on_max_combo_box_changed)
            self.max_spin_box.valueChanged.connect(self.on_max_changed)
            self.per_channel_checkbox.toggled.connect(self.on_per_channel_toggled)
            self.ignore_hot_spots.toggled.connect(self.on_ignore_outliers_changed)

            layout_comments.addWidget(self.image_normalization_box)


            # image_dimension_browser_toolbox_layout.addWidget(QLabel('bototo'))

            # self.update_dimension_sliders()

            # horiz_lay = QHBoxLayout()
            # horiz_lay.addWidget(QLabel('Ch'))
            # self.channels =QComboBox()
            # self.channels.addItems(["merge","0", "1", "2"])
            # horiz_lay.addWidget(self.channels)
            # self.channels.currentIndexChanged.connect(self.slider_dimension_value_changed)
            #
            # layout_comments.addLayout(horiz_lay)

            # Create a QHBoxLayout to hold the check boxes
            self.channel_box = QGroupBox("Active Channels")
            tmp_box = QVBoxLayout(self.channel_box)



            self.channel_layout = QHBoxLayout()
            tmp_box.addLayout(self.channel_layout)
            # if None --> activate all channels

            # self.update_channel_layout()
            # self.channel_layout.addWidget(QPushButton('Luts')) --> it is there then removed but why

            another_h_layout = QHBoxLayout()

            button = QPushButton(f"Set LUTs") # this should always be accessible even for single channel images -−> I DON't get why I can't see it --> anyway --> maybe keep it always
            button.setFocusPolicy(Qt.NoFocus)
            another_h_layout.addWidget(button) # why is it not visible ???
            button.clicked.connect(self.set_LUTs)

            button_reset_Luts = QPushButton(f"Reset all LUTs") # this should always be accessible even for single channel images -−> I DON't get why I can't see it --> anyway --> maybe keep it always
            button_reset_Luts.setFocusPolicy(Qt.NoFocus)
            another_h_layout.addWidget(button_reset_Luts)  # why is it not visible ???
            button_reset_Luts.clicked.connect(self.reset_LUTs)

            layout_comments.addWidget( self.channel_box )


            layout_comments.addWidget(self.image_dimension_browser_toolbox)
            tmp_box.addLayout(another_h_layout)


            # add support for dimensions !!!







            # Create a layout for the scroll area content
            content_layout = QGridLayout(self.content_widget)

            # Create a scroll area for the content of the second dock widget
            self.scroll_area2 = QScrollArea()
            self.populate_texts_from_annotations()

            # Adjust scroll area properties
            self.scroll_area2.setWidgetResizable(True)

            # Now we create a dockwidget that will contain a list of all the objects
            self.list = ListGUI(custom_label='<font color=#FF0000>(Re)Order by Drag n Drop</font>/Select/Delete annotations',
                                supported_files=[],
                                default_double_click_behaviour=None, detect_list_order_change=True)
            self.list.list.selectionModel().selectionChanged.connect(self.listSelectionChanged)
            self.list.list.selectionModel().selectionChanged.connect(self.selectionUpdated)
            self.list.list.orderChanged.connect(self.listOrderChanged)
            self.list.deletePressed.connect(self.deletePressedInTheList)

            # Below we will only keep the interesting buttons from the qtoolbar
            actions_to_keep = ['elete']
            # Get a list of all QToolButtons in the toolbar
            tool_buttons = self.list.tb.findChildren(QToolButton)
            # Iterate over the QToolButtons and remove the ones that don't match the patterns in actions_to_keep

            for tool_button in tool_buttons:
                match_found = False
                # Get the associated QAction of the tool_button
                action = tool_button.defaultAction()
                if action is not None:
                    for pattern in actions_to_keep:
                        if pattern in action.text():
                            match_found = True
                            break
                    if not match_found:
                        # Remove the QAction associated with the QToolButton from the toolbar
                        self.list.tb.removeAction(action)
                        # Delete the QToolButton object
                        tool_button.setParent(None) # DEV NOTE KEEP bug fix to allow for delete later to work
                        tool_button.deleteLater()

            # add the crop and rotate widget here
            content_widget3 = QWidget()
            self.scroll_area3 = QScrollArea()
            self.scroll_area3.setWidgetResizable(True)
            rotate_n_crop_layout = QVBoxLayout(content_widget3)
            self.scroll_area3.setWidget(content_widget3)

            self.rotate_toolbox = QGroupBox('Rotate',objectName='rotate_toolbox')
            self.rotate_toolbox.setEnabled(True)
            self.rotate_toolbox.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            rotate_toolbox_layout = QGridLayout(self.rotate_toolbox)
            label = QLabel('Angle (degrees):')
            rotate_toolbox_layout.addWidget(label, 0, 0)
            self.rotate_image_spinbox = QDoubleSpinBox()
            self.rotate_image_spinbox.setSingleStep(1)
            self.rotate_image_spinbox.setValue(0)
            self.rotate_image_spinbox.setRange(-359,359)
            self.rotate_image_spinbox.valueChanged.connect(self.compute_rotation_n_crop_polygon)
            rotate_toolbox_layout.addWidget(self.rotate_image_spinbox, 0, 1)
            # Add a "Reset Angle" button
            reset_angle_button = QPushButton("Reset Angle")
            reset_angle_button.setFocusPolicy(Qt.NoFocus)
            reset_angle_button.clicked.connect(self.reset_angle)
            rotate_toolbox_layout.addWidget(reset_angle_button, 1, 0, 1, 2)

            rotate_n_crop_layout.addWidget(self.rotate_toolbox)

            self.crop_toolbox = QGroupBox('Crop', objectName='crop_toolbox')
            self.crop_toolbox.setEnabled(True)
            crop_toolbox_layout = QGridLayout(self.crop_toolbox)

            label = QLabel('Left:')
            crop_toolbox_layout.addWidget(label, 0, 0)
            self.crop_left_spinbox = QSpinBox()
            self.crop_left_spinbox.setMaximum(100000)
            self.crop_left_spinbox.setSingleStep(1)
            self.crop_left_spinbox.setValue(0)
            self.crop_left_spinbox.valueChanged.connect(self.compute_rotation_n_crop_polygon)
            crop_toolbox_layout.addWidget(self.crop_left_spinbox, 0, 1)

            label = QLabel('Right:')
            crop_toolbox_layout.addWidget(label, 1, 0)
            self.crop_right_spinbox = QSpinBox()
            self.crop_right_spinbox.setMaximum(100000)
            self.crop_right_spinbox.setSingleStep(1)
            self.crop_right_spinbox.setValue(0)
            self.crop_right_spinbox.valueChanged.connect(self.compute_rotation_n_crop_polygon)
            crop_toolbox_layout.addWidget(self.crop_right_spinbox, 1, 1)

            label = QLabel('Top:')
            crop_toolbox_layout.addWidget(label, 2, 0)
            self.crop_top_spinbox = QSpinBox()
            self.crop_top_spinbox.setMaximum(100000)
            self.crop_top_spinbox.setSingleStep(1)
            self.crop_top_spinbox.setValue(0)
            self.crop_top_spinbox.valueChanged.connect(self.compute_rotation_n_crop_polygon)
            crop_toolbox_layout.addWidget(self.crop_top_spinbox, 2, 1)

            label = QLabel('Bottom:')
            crop_toolbox_layout.addWidget(label, 3, 0)
            self.crop_bottom_spinbox = QSpinBox()
            self.crop_bottom_spinbox.setMaximum(100000)
            self.crop_bottom_spinbox.setSingleStep(1)
            self.crop_bottom_spinbox.setValue(0)
            self.crop_bottom_spinbox.valueChanged.connect(self.compute_rotation_n_crop_polygon)
            crop_toolbox_layout.addWidget(self.crop_bottom_spinbox, 3, 1)

            # Add a "Reset Crops" button
            reset_crops_button = QPushButton("Reset Crops")
            reset_crops_button.setFocusPolicy(Qt.NoFocus)
            reset_crops_button.clicked.connect(self.reset_crops)
            crop_toolbox_layout.addWidget(reset_crops_button, 4, 0, 1, 2)

            rotate_n_crop_layout.addWidget(self.crop_toolbox)

            self.AR_display_toolbox = QGroupBox('AR', objectName='AR_display_toolbox')
            self.AR_display_toolbox.setEnabled(True)
            crop_toolbox_layout = QHBoxLayout(self.AR_display_toolbox)
            self.AR_display = QLabel('current AR (w/h): 1.0')
            crop_toolbox_layout.addWidget(self.AR_display)

            rotate_n_crop_layout.addWidget(self.AR_display_toolbox)

            tab_widget = QTabWidget()
            tab_widget.setMaximumWidth(500)

            # Add the dock widgets to the tab widget
            tab_widget.addTab(self.comments_widget, "File Infos + Scale")
            tab_widget.addTab(self.content_widget, "Annotations")
            tab_widget.addTab(self.scroll_area2, "Texts")
            tab_widget.addTab(self.scroll_area3, "Rotate + Crop")
            tab_widget.addTab(self.script_widget, "Script")
            tab_widget.addTab(self.list, "Layers")

            mainLayout = QHBoxLayout(self)
            mainLayout.addWidget(self.scrollArea)
            mainLayout.addWidget(tab_widget)

            self.shapes_toolbox = QGroupBox('Shapes',objectName='shapes_toolbox')
            self.shapes_toolbox.setEnabled(True)

            shapes_toolbox_layout = QGridLayout()

            rectangle = QPushButton()
            rectangle.setFocusPolicy(Qt.NoFocus)
            rectangle.setIcon(qta.icon("mdi.rectangle-outline"))
            rectangle.setToolTip("Rectangle")
            rectangle.clicked.connect(
                self.qt_viewer.change_shape)  # this is how one can pass the button to the function to
            shapes_toolbox_layout.addWidget(rectangle, 0, 0)
            circle = QPushButton()
            circle.setFocusPolicy(Qt.NoFocus)
            circle.setIcon(qta.icon("fa5.circle"))
            circle.setToolTip("Circle")
            circle.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(circle, 0, 1)

            arrow = QPushButton()
            arrow.setFocusPolicy(Qt.NoFocus)
            arrow.setIcon(qta.icon("mdi.arrow-top-right-bottom-left"))
            arrow.setToolTip("Dual Headed Arrow")
            arrow.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(arrow, 0, 2)
            if False:
                accolade = QPushButton()
                # accolade.setEnabled(False)
                accolade.setIcon(qta.icon("ph.brackets-curly-light"))
                accolade.setToolTip("Accolade")
                accolade.clicked.connect(self.qt_viewer.change_shape)
                # content_layout.addWidget(accolade)
                shapes_toolbox_layout.addWidget(accolade, 3, 2)
            text = QPushButton()
            text.setFocusPolicy(Qt.NoFocus)
            text.setIcon(qta.icon("ri.text"))
            text.setToolTip("Floating txt")
            text.clicked.connect(self.qt_viewer.change_shape)
            # content_layout.addWidget(text)
            shapes_toolbox_layout.addWidget(text, 1, 1)

            line = QPushButton()
            line.setFocusPolicy(Qt.NoFocus)
            line.setIcon(qta.icon("ph.line-segment-fill"))
            line.setToolTip("Line")
            line.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(line, 1, 2)

            freehand = QPushButton()
            freehand.setFocusPolicy(Qt.NoFocus)
            freehand.setIcon(qta.icon("mdi6.draw"))
            freehand.setToolTip("hand drawing")
            freehand.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(freehand, 2, 0)

            square = QPushButton()
            square.setFocusPolicy(Qt.NoFocus)
            square.setIcon(qta.icon("mdi6.square-outline"))
            square.setToolTip("square")
            square.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(square, 2, 1)

            polyline = QPushButton()
            polyline.setFocusPolicy(Qt.NoFocus)
            polyline.setIcon(qta.icon("mdi.vector-polyline"))
            polyline.setToolTip("polyline")
            polyline.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(polyline, 2, 2)

            Ellipse = QPushButton()
            Ellipse.setFocusPolicy(Qt.NoFocus)
            Ellipse.setIcon(qta.icon("mdi.ellipse-outline"))
            Ellipse.setToolTip("Ellipse")
            Ellipse.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(Ellipse, 3, 0)

            polygon = QPushButton()
            polygon.setFocusPolicy(Qt.NoFocus)
            polygon.setIcon(qta.icon("mdi.pentagon-outline"))
            polygon.setToolTip("Polygon")
            polygon.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(polygon, 3, 1)

            scale_bar_button = QPushButton("ScaleBar")
            scale_bar_button.setFocusPolicy(Qt.NoFocus)
            scale_bar_button.setToolTip("Scale Bar")
            scale_bar_button.clicked.connect(self.qt_viewer.change_shape)  # replace with your desired function
            shapes_toolbox_layout.addWidget(scale_bar_button, 3, 2)  # adjust the row number as needed

            arrow = QPushButton()
            arrow.setFocusPolicy(Qt.NoFocus)
            arrow.setIcon(qta.icon("mdi.arrow-bottom-right"))
            arrow.setToolTip("Arrow")
            arrow.clicked.connect(self.qt_viewer.change_shape)
            shapes_toolbox_layout.addWidget(arrow, 1, 0)

            if False:
                # not implemented yet
                Edit = QPushButton('Edit selected ROI')
                # Edit.setEnabled(False)
                Edit.setToolTip("Edit selected ROI")
                # content_layout.addWidget(Edit)
                shapes_toolbox_layout.addWidget(Edit, 4, 0, 1, 3)

                changeWidthHeight = QPushButton('width/height')
                # changeWidthHeight.setEnabled(False)
                # content_layout.addWidget(changeWidthHeight)
                shapes_toolbox_layout.addWidget(changeWidthHeight, 5, 0, 1, 3)

            jLabel2 = QLabel('Contour:')
            shapes_toolbox_layout.addWidget(jLabel2, 6, 0)
            self.contourColor = QPushButton()  # new Commons.PaintedButton()
            self.contourColor.setFocusPolicy(Qt.NoFocus)
            self.set_button_color(self.contourColor, self.qt_viewer.contour_color)
            self.contourColor.clicked.connect(partial(self.qt_viewer.color_picker, self.qt_viewer.set_contour_color))
            shapes_toolbox_layout.addWidget(self.contourColor, 6, 1, 1, 2)

            jLabel12 = QLabel('Fill:')
            shapes_toolbox_layout.addWidget(jLabel12, 7, 0)
            self.fillColor = QPushButton()  # new Commons.PaintedButton()
            self.fillColor.setFocusPolicy(Qt.NoFocus)
            self.set_button_color(self.fillColor, self.qt_viewer.fill_color)
            self.fillColor.clicked.connect(partial(self.qt_viewer.color_picker, self.qt_viewer.set_fill_color))
            self.fillColor.clicked.connect(self.set_scroll_area_bg_color)
            self.set_scroll_area_bg_color() # apply the bg color if any
            shapes_toolbox_layout.addWidget(self.fillColor, 7, 1, 1, 1)

            self.removeFillColor = QPushButton('Reset')  # new Commons.PaintedButton()
            self.removeFillColor.setToolTip('Remove background color')
            self.removeFillColor.setFocusPolicy(Qt.NoFocus)
            self.removeFillColor.clicked.connect(self.reset_fill_color)
            shapes_toolbox_layout.addWidget(self.removeFillColor, 7, 2, 1, 1)
            jLabel17 = QLabel('Opacity')
            shapes_toolbox_layout.addWidget(jLabel17, 8, 0)
            self.opacity_spinner = QDoubleSpinBox()
            self.opacity_spinner.setSingleStep(0.05)
            self.opacity_spinner.setRange(0, 1)
            self.opacity_spinner.setValue(1)
            self.opacity_spinner.valueChanged.connect(self.opacity_changed)

            shapes_toolbox_layout.addWidget(self.opacity_spinner, 8, 1, 1, 2)

            jLabel9 = QLabel('Rotation :')
            shapes_toolbox_layout.addWidget(jLabel9, 9, 0)
            self.rotation_spinner = QDoubleSpinBox(objectName='rotation_spinner')
            self.rotation_spinner.setSingleStep(1)
            self.rotation_spinner.setRange(-359, 359)
            self.rotation_spinner.setValue(0)
            self.rotation_spinner.valueChanged.connect(self.rotation_changed)
            # content_layout.addWidget(jSpinner7)
            shapes_toolbox_layout.addWidget(self.rotation_spinner, 9, 1, 1, 2)
            # "COnvert a rectangular ROI to an image inset"
            self.toInset = QPushButton('Rect ROI --> Inset')
            self.toInset.setFocusPolicy(Qt.NoFocus)
            self.toInset.clicked.connect(self.ROI_to_crop_or_inset)
            shapes_toolbox_layout.addWidget(self.toInset, 10, 0)
            self.toCrop = QPushButton('Rect ROI --> Crop')
            self.toCrop.setFocusPolicy(Qt.NoFocus)
            self.toCrop.clicked.connect(self.ROI_to_crop_or_inset)
            shapes_toolbox_layout.addWidget(self.toCrop, 10, 1, 1, 2)

            self.shapes_toolbox.setLayout(shapes_toolbox_layout)
            content_layout.addWidget(self.shapes_toolbox)

            # line style toolbox
            self.line_toolbox = QGroupBox('Line style',objectName='line_toolbox')
            self.line_toolbox.setEnabled(True)

            line_toolbox_layout = QGridLayout()
            jLabel1 = QLabel('Stroke Size:')
            # content_layout.addWidget(jLabel1)
            line_toolbox_layout.addWidget(jLabel1, 0, 0)
            self.line_stroke_size = QDoubleSpinBox(objectName='line_stroke_size')
            # self.line_stroke_size.setRange(0.0, 100.0)
            self.line_stroke_size.setMinimum(0.1)
            self.line_stroke_size.setValue(0.65)
            self.line_stroke_size.setSingleStep(0.05)
            self.line_stroke_size.valueChanged.connect(self.on_line_stroke_size_value_changed)
            line_toolbox_layout.addWidget(self.line_stroke_size, 0, 1)

            jLabel5 = QLabel('Type:')
            line_toolbox_layout.addWidget(jLabel5, 1, 0)
            self.line_dotted_pattern_combo = QComboBox(objectName='self.line_dotted_pattern_combo')
            self.line_dotted_pattern_combo.addItems(["SolidLine", "DashLine", "DashDotLine", "DotLine", "DashDotDotLine", "CustomDashLine"])
            self.line_dotted_pattern_combo.currentTextChanged.connect(self.line_style_changed)

            # content_layout.addWidget(self.line_dotted_pattern_combo)
            line_toolbox_layout.addWidget(self.line_dotted_pattern_combo, 1, 1)
            jLabel6 = QLabel('Custom dash pattern:')
            # content_layout.addWidget(jLabel6)
            line_toolbox_layout.addWidget(jLabel6, 2, 0)
            self.lineEdit = QLineEdit()
            self.lineEdit.setText('1, 4, 5, 4')
            self.lineEdit.setEnabled(False)
            self.lineEdit.textChanged.connect(self.line_style_changed)
            line_toolbox_layout.addWidget(self.lineEdit, 2, 1)
            # add a text change to adapt the pattern after some delay maybe

            self.line_toolbox.setLayout(line_toolbox_layout)
            content_layout.addWidget(self.line_toolbox)

            if True:
                # arrow parameters -−> maybe reactivate some day
                # new group
                self.arrow_toolbox = QGroupBox('Arrow style', objectName='arrow_toolbox')
                # self.arrow_toolbox.setEnabled(False)
                arrow_toolbox_layout = QGridLayout()
                jLabel3 = QLabel('Head w (scale):')
                arrow_toolbox_layout.addWidget(jLabel3, 0, 0)
                # content_layout.addWidget(jLabel3)
                self.arrow_width_scaler = QSpinBox(objectName='self.arrow_width_scaler')
                self.arrow_width_scaler.setValue(4)
                self.arrow_width_scaler.valueChanged.connect(self.arrowhead_width_height_changed)
                arrow_toolbox_layout.addWidget(self.arrow_width_scaler, 0, 1)
                # content_layout.addWidget(self.arrow_width_scaler)
                jLabel10 = QLabel('Head h (scale):')
                # content_layout.addWidget(jLabel10)
                arrow_toolbox_layout.addWidget(jLabel10, 0, 2)
                self.arrow_height_scaler = QSpinBox(objectName='self.arrow_height_scaler')
                self.arrow_height_scaler.setValue(12)
                self.arrow_height_scaler.valueChanged.connect(self.arrowhead_width_height_changed)
                # content_layout.addWidget(self.arrow_height_scaler)
                arrow_toolbox_layout.addWidget(self.arrow_height_scaler, 0, 3)

                if False:
                    # maybe specify arrowhead type here
                    jLabel11 = QLabel('Type:')
                    # content_layout.addWidget(jLabel11)
                    arrow_toolbox_layout.addWidget(jLabel11, 1, 0)
                    jComboBox2 = QComboBox(objectName='jComboBox2')
                    # add single headed arrow option
                    jComboBox2.addItem("Single Headed Arrow →")
                    # add double headed arrow option
                    jComboBox2.addItem("Double Headed Arrow ↔")
                    # content_layout.addWidget(jComboBox2)
                    arrow_toolbox_layout.addWidget(jComboBox2, 1, 1, 1, 3)

                if False:
                    jLabel13 = QLabel('Filling:')
                    # content_layout.addWidget(jLabel13)
                    arrow_toolbox_layout.addWidget(jLabel13, 1, 2)
                    # "Filled", "Outline", "Fancy"
                    jComboBox4 = QComboBox(objectName='jComboBox4')
                    # content_layout.addWidget(jComboBox4)
                    arrow_toolbox_layout.addWidget(jComboBox4, 1, 3)
                self.arrow_toolbox.setLayout(arrow_toolbox_layout)

                if False: # so far inactivate the arrowhead width and height until I set it
                    content_layout.addWidget(self.arrow_toolbox)

            if False:
                # not implemented yet
                self.bracket_toolbox = QGroupBox('Bracket',objectName='bracket_toolbox')
                self.bracket_toolbox.setEnabled(False)

                bracket_toolbox_layout = QGridLayout()

                jLabel4 = QLabel('Bracket Width:')
                # content_layout.addWidget(jLabel4)
                bracket_toolbox_layout.addWidget(jLabel4, 0, 0)
                jSpinner3 = QSpinBox(objectName='jSpinner3')
                # content_layout.addWidget(jSpinner3)
                bracket_toolbox_layout.addWidget(jSpinner3, 0, 1)

                self.bracket_toolbox.setLayout(bracket_toolbox_layout)
                content_layout.addWidget(self.bracket_toolbox)

                # new toolbox
                self.misc_toolbox = QGroupBox('Misc',objectName='misc_toolbox')
                self.misc_toolbox.setEnabled(True)

                misc_toolbox_layout = QGridLayout()

                # other tools
                # jList1 = new javax.swing.JList()
                # content_layout.addWidget(jList1)
                erode = QPushButton('Erode')
                erode.setEnabled(False)
                erode.clicked.connect(self.qt_viewer.erode)
                # content_layout.addWidget(erode)
                misc_toolbox_layout.addWidget(erode, 0, 0)
                dilate = QPushButton('Dilate')
                dilate.setEnabled(False)
                dilate.clicked.connect(self.qt_viewer.dilate)
                # content_layout.addWidget(dilate)
                misc_toolbox_layout.addWidget(dilate, 0, 1)
                reCenter = QPushButton('Move to ori (0,0)')
                reCenter.clicked.connect(self.qt_viewer.move_to_origin)
                misc_toolbox_layout.addWidget(reCenter, 0, 2)

                self.misc_toolbox.setLayout(misc_toolbox_layout)
                content_layout.addWidget(self.misc_toolbox)

            # Adjust scroll area properties
            # self.scroll_area.setWidgetResizable(True)

        # we reload all the parameters of the image
        self.load_background_parameters()
        self.update_dimension_sliders()
        self.update_channel_layout()

        if self.qt_viewer.background:
            self.qt_viewer.background.setTopLeft(0, 0)
            self.qt_viewer.background.set_to_scale(1)
            self.qt_viewer.background.set_rotation(0)
            # I need reset crop when I do that
            self.qt_viewer.background.crop_left=0
            self.qt_viewer.background.crop_right = 0
            self.qt_viewer.background.crop_top = 0
            self.qt_viewer.background.crop_bottom = 0

        self.setMinimumSize(800, 600)
        # self.resize(800, 700)
        # self.setFixedSize(900, 760)
        self.qt_viewer.update_size()
        self.qt_viewer.update()


    def slider_dimension_value_changed_delayed(self):
        self.timer_dim_slider.start()

    def update_channel_layout(self):
        clear_layout(self.channel_layout)
        self.channel_boxes = []
        # Iterate over the channels in the image
        if self.qt_viewer.background and isinstance(self.qt_viewer.background.img, np.ndarray) and 'c' in guess_dimensions(self.qt_viewer.background.img): # if no c we must not do anything with the last channel as this is not a 'c'
            for i in range(self.qt_viewer.background.img.shape[-1]):
                # Create a new QCheckBox for this channel
                check_box = QCheckBox(f"{i}")
                if self.qt_viewer.background.channels and len(self.qt_viewer.background.channels)==self.qt_viewer.background.img.shape[-1]:
                    # we try to reload the previously loaded channels
                    check_box.setChecked(self.qt_viewer.background.channels[i])
                else:
                    check_box.setChecked(True)
                check_box.stateChanged.connect(self.slider_dimension_value_changed)
                # Add the check box to the layout
                self.channel_layout.addWidget(check_box)
                self.channel_boxes.append(check_box)

            # Create a QPushButton instance
            # print('I shall be called') #--> it is called so why is it not visible


            # self.channel_layout.addWidget(QLabel('test'))
            # self.channel_layout.addWidget(QLabel('test2'))

            # self.channel_layout.update()
            # self.channel_box.adjustSize()
            # self.channel_layout.update()
            # print('I shall be called2')
        else:
            # print('cancelled dab')
            pass

    def reset_LUTs(self):
        # print('resetting_luts called ACTION REQUIRED!!!')
        self.qt_viewer.background.LUTs = None
        self.qt_viewer.background.update_qimage()  # we force the qimage to change and display the right LUT --> TODO
        self.qt_viewer.update()

    def set_LUTs(self):
        # print('widget to set the LUTS ACTION REQUIRED')
        old_luts= self.qt_viewer.background.LUTs
        # specified_luts = [None, None, 'DNA']  # simulate existing channels
        # Create a LutWidget instance
        guessed_dims = guess_dimensions(self.qt_viewer.background.img)

        # print('guessed_dims',guessed_dims)
        if guessed_dims and 'c' in guessed_dims:
            lut_widget = LutWidget(nb_channels=self.qt_viewer.background.img.shape[-1], user_specified_luts=old_luts)
        else:
            lut_widget = LutWidget(nb_channels=1, user_specified_luts=old_luts)

        custom_dialog = CustomDialog(title="Edit Look Up Tables (LUTs)", message="Do you want to proceed?", main_widget=lut_widget,
                                     parent=self, options=['Ok', 'Cancel'],
                                     auto_adjust=True)  # that is really very good --> I can do it like that
        if custom_dialog.exec_() == QDialog.Accepted:
            # print('need to recover the image and do things with it')
            # # TODO I need also restore the initial scale of the image --> so I need get it before hand
            # print(custom_dialog.main_widget.qt_viewer.background)  # TODO --> maybe add a method to simplify that ???? because that is a bit heavy
            # print('new luts to apply to the image', lut_widget.getAllLuts())
            self.qt_viewer.background.LUTs = lut_widget.getAllLuts()
            self.qt_viewer.background.update_qimage() # we force the qimage to change and display the right LUT --> TODO
            self.qt_viewer.update()
        else:
            # print('need to reset the changes --> see how to implement that can I simply clone all the shapes and edit the clone or do I need smthg smarter ??? no clue not so easy ')  # need a bit of thinking
            # else keep previous lut and restore them and nothing todo
            self.qt_viewer.background.LUTs = old_luts

    def update_conversion_factor(self):
        # self.ignore_changes = True
        try:
            if self.qt_viewer.background.px_to_unit_conversion_factor:
                try:
                    self.scale_conversion_spinner.setValue(self.qt_viewer.background.px_to_unit_conversion_factor)
                except:
                    print('Setting conversion factor failed --> resetting to 1',
                          self.qt_viewer.background.px_to_unit_conversion_factor)
                    self.scale_conversion_spinner.setValue(0)
            else:
                self.scale_conversion_spinner.setValue(0)
            self.qt_viewer.update()
        except:
            self.scale_conversion_spinner.setValue(0)
        # self.qt_viewer.update()
        # self.ignore_changes = False

    def update_normalization(self):
        # print('update_normalization called --> ACTION REQUIRED!!!')

        self.ignore_changes = True

        if self.qt_viewer.background and self.qt_viewer.background.normalization and isinstance(self.qt_viewer.background.img, np.ndarray):
            self.min_max_combo_box.setCurrentIndex(0)
            try:
                select_in_combobox(self.min_max_combo_box, self.qt_viewer.background.normalization['range'])
            except:
                pass
            # self.max_combo_box.setCurrentIndex(0)
            # try:
            #     select_in_combobox(self.max_combo_box, self.qt_viewer.background.normalization['max'])
            # except:
            #     pass
            try:
                self.max_spin_box.setValue(self.qt_viewer.background.normalization['max_value'])
            except:
                self.max_spin_box.setValue(self.qt_viewer.background.img.max())
            try:
                self.min_spin_box.setValue(self.qt_viewer.background.normalization['min_value'])
            except:
                # self.min_spin_box.setValue(0)
                self.min_spin_box.setValue(self.qt_viewer.background.img.min())
            try:
                self.per_channel_checkbox.setChecked(self.qt_viewer.background.normalization['ignore_hot_spots'])
            except:
                self.per_channel_checkbox.setChecked(False)
            try:
                self.ignore_hot_spots.setChecked(self.qt_viewer.background.normalization['per_channel'])
            except:
                self.ignore_hot_spots.setChecked(False)
        else:
            self.min_max_combo_box.setCurrentIndex(0)
            # self.max_combo_box.setCurrentIndex(0)
            self.max_spin_box.setValue(255)
            self.min_spin_box.setValue(0)
            if isinstance(self.qt_viewer.background.img, np.ndarray):
                self.max_spin_box.setValue(self.qt_viewer.background.img.max())
                self.min_spin_box.setValue(self.qt_viewer.background.img.min()) # shall I put 0 or min ????
                # self.min_spin_box.setValue(0) # shall I put 0 or min ????
            self.per_channel_checkbox.setChecked(False)
            self.ignore_hot_spots.setChecked(False)

        self.ignore_changes = False

    def update_projection(self):
        self.ignore_changes = True
        if self.qt_viewer.background:
            # if isinstance(self.qt_viewer.background.img, np.ndarray):
                if self.qt_viewer.background.projection:
                    idx = self.projection_combo_box.findData(self.qt_viewer.background.projection)
                    if idx>=0:
                        self.projection_combo_box.setCurrentIndex(idx)
                else:
                    self.projection_combo_box.setCurrentIndex(0)


                # print('force update sliders')


        self.ignore_changes = False

    def update_dimension_sliders(self):
        self.dimsliders = []
        # self.channel_boxes = []
        # empty_widget_layout(self.image_dimension_browser_toolbox)
        clear_layout(self.image_dimension_browser_toolbox_layout)
        if self.qt_viewer.background:
            guessed_dims = guess_dimensions(self.qt_viewer.background.img)
        else:
            guessed_dims = None

        # print('dimensions found0', guessed_dims)

        # print('guessed_dims', guessed_dims, self.qt_viewer.background)

        # empty_layout = self.image_dimension_browser_toolbox.layout()

        # print('empty_layout', empty_layout)

        if guessed_dims:

            # print('dimensions found', guessed_dims)

            try_update = False

            # print('current_dimensions',self.qt_viewer.background.dimensions)

            if self.qt_viewer.background.dimensions:

                try:
                    try_update = len(self.qt_viewer.background.dimensions['order']) == len(self.qt_viewer.background.img.shape) and guess_dimensions(self.qt_viewer.background.img) ==self.qt_viewer.background.dimensions['order']
                except:
                    traceback.print_exc()



            # print('try_update',try_update)

            letter_before_h = find_letter_before_h(guessed_dims)

            self.image_dimension_browser_toolbox.setEnabled(True)
            # if hasattr(self.qt_viewer.background.img,'metadata'):
            for ddd, dim in enumerate(guessed_dims):
                if dim == 'h':  # we stop at h, all other dims are taken into account though
                    break

                dimslider_layout, dimslider = create_dim_slider(dimension=dim,
                                                                max_dim=self.qt_viewer.background.img.shape[ddd])

                # recover from it the slider
                # print(type(dimslider.itemAt(1)))
                # print(dimslider.itemAt(1).value())
                # print('dimslider.value()',dimslider.value()) # now connect all the sliders to somthing cool

                if try_update:
                    try:
                            dimslider.setValue(self.qt_viewer.background.dimensions['values'][ddd])
                    except:
                        # traceback.print_exc()
                        pass # just if dim mismatch is there --> no big deal


                dimslider.valueChanged.connect(self.slider_dimension_value_changed_delayed)
                self.dimsliders.append(dimslider)

                if self.projection_combo_box.currentData(): # if there is a projection ignore the slider that is associated to the projected dim --> smarter idea
                    if dim == letter_before_h :
                        # do I wanna fo that --> No --> maybe set to None
                        # print('skipping dimension due to projection', dim)
                        break

                self.image_dimension_browser_toolbox_layout.addLayout(dimslider_layout)

        else:
            self.image_dimension_browser_toolbox.setEnabled(False)
            if self.qt_viewer.background:
                self.qt_viewer.background.dimensions=None


        # self.comments_widget.update()
        if self.projection_combo_box.currentData() and len(self.dimsliders)>1:
            self.image_dimension_browser_toolbox.adjustSize()
        elif not self.projection_combo_box.currentData():
            self.image_dimension_browser_toolbox.adjustSize()
        # self.comments_widget.adjustSize()

    def projection_changed(self):
        if  self.ignore_changes:
            return

        self.update_dimension_sliders()

        # so cool
        # print('Projection changed called -> ACTION REQUIRED!!!')
        # print(self.projection_combo_box.currentText(), self.projection_combo_box.currentData())
        # print(type(self.projection_combo_box.currentData()))
        self.qt_viewer.background.projection = self.projection_combo_box.currentData()
        self.qt_viewer.background.update_qimage()
        self.qt_viewer.update()
        self.qt_viewer.update_size()

        # very good

    def update_spin_boxes(self):
        min_enabled = self.min_max_combo_box.currentData() == "custom"
        self.min_spin_box.setEnabled(min_enabled)
        self.max_spin_box.setEnabled(min_enabled)

    def update_other_spin_box(self):
        if self.source == self.min_spin_box:
            min_value = self.min_spin_box.value()
            if min_value >= self.max_spin_box.value():
                self.max_spin_box.setValue(min_value + 1)
        elif self.source == self.max_spin_box:
            max_value = self.max_spin_box.value()
            if max_value <= self.min_spin_box.value():
                self.min_spin_box.setValue(max_value - 1)
        self.emit_params_changed()

    def on_min_max_combo_box_changed(self, index):
        self.update_spin_boxes()
        self.emit_params_changed()

    # def on_max_combo_box_changed(self, index):
    #     self.update_spin_boxes()
    #     self.emit_params_changed()

    def on_min_changed(self, value):
        self.source = self.min_spin_box
        # if value >= self.max_spin_box.value():
        #     # self.max_spin_box.setValue(value + 1)
        #     self.timer.start()
        # else:
        self.timer.start()

    def on_max_changed(self, value):
        self.source = self.max_spin_box
        # if value <= self.min_spin_box.value():
        #     # self.min_spin_box.setValue(value - 1)
        #     self.timer.start()
        # else:
        self.timer.start()

    def on_ignore_outliers_changed(self):
        self.emit_params_changed()
    def on_per_channel_toggled(self, checked):
        self.emit_params_changed()

    def emit_params_changed(self):
        # print('emit_params_changed called',self.ignore_changes)
        if self.ignore_changes:
            return
        # print('emit_params_changed really entering')
        normalization = {
            "range": self.min_max_combo_box.currentData(),
            "min_value": self.min_spin_box.value(),
            "max_value": self.max_spin_box.value(),
            "per_channel": self.per_channel_checkbox.isChecked(),
            "ignore_hot_spots": self.ignore_hot_spots.isChecked(),
        }
        self.normalization_params_changed.emit(normalization)
        # do format that whole stuff within a single dict
        self.qt_viewer.background.normalization = normalization
        self.qt_viewer.background.update_qimage()
        self.qt_viewer.update()
        self.qt_viewer.update_size()


    def scale_conversion_spinner_changed(self):
        # print('scale changed ACTION REQUIRED --> TODO --> code that', self.scale_conversion_spinner.value())
        try:
            self.qt_viewer.background.px_to_unit_conversion_factor = self.scale_conversion_spinner.value()
            self.qt_viewer.update_size()
            self.qt_viewer.update()
        except:
            traceback.print_exc()
            print('scale could not be applied --> ignoring')

    def slider_dimension_value_changed(self):
        # print('slider value changed -−> ACTION REQUIRED')
        # print(self.sender(), self.sender().objectName(), self.sender().value()) # I coud put name
        # print('list of all sliders', self.dimsliders)

        # besides name I can get the index directly from the stuff so it is easy
        # I need store the dimensions of the image maybe and the initial image dimensions
        # see how to do that, I guess I may need to do some adjustments at some point!!

        # print('self.channel_boxes',self.channel_boxes)

        if  self.channel_boxes:
            self.qt_viewer.background.channels = None if not self.channel_boxes else [box.isChecked() for box in self.channel_boxes]#[iii for iii, box in enumerate(self.channel_boxes) if box.isChecked()]
            # print('len(self.qt_viewer.background.channels)',self.qt_viewer.background.channels)
        else:
            self.qt_viewer.background.channels = None

        # print('channels_state', self.qt_viewer.background.channels)

        all_the_dims = {}
        all_the_dims['order'] = guess_dimensions(self.qt_viewer.background.img)
        dims = []

        # self.channels

        for slider in self.dimsliders:
            if slider.objectName() =='h': # stop at h dimension
                break
            # image_to_display = image_to_display[slider.value()]
            dims.append(slider.value())
            # print('dim --> ', slider.objectName(), slider.value())

        all_the_dims['values']=dims


        self.qt_viewer.background.dimensions=all_the_dims
        self.qt_viewer.background.update_qimage()
        self.qt_viewer.update()
        self.qt_viewer.update_size()
        #
        #
        #
        # print('all_the_dims', all_the_dims)
        #
        # from batoolset.img import toQimage
        #
        # # plt.close('all')
        # # plt.imshow(image_to_display)
        # # then I need reupdate the qimage from that in fact -> should actually be quite easy in fact
        # self.qt_viewer.background.qimage =toQimage(image_to_display)
        # # plt.show()
        #
        # print('image_to_display at the end', image_to_display.shape, 'vs', self.qt_viewer.background.img.shape)
        # # that works super well and I could really get all --> easy TODO

        # self.qt_viewer.update()

        # in fact that will not be too hard to do

        # maybe offer max proj and if so find the dimensions of the stuff
        # maybe proj should be done before or after ???
        # I need to think about it


        # and selection of color channels should also be done --> see how to do that
        # then I will need plenty of sample images
        # can I also open online images





        # see where the projection should be put ??? beacuse brwosing and crawling will complicate things








        # loop over all sliders in the appropriate order and just get what is needed --> TODO
        # all is very easy in fact TODO -−> DO it






        # I will need to update the image and I need to see how TODO that

        # TODO --> do delay only if necessary
        # self.delayed_dimension_preview.stop()
        # self.delayed_dimension_preview.start(600)

        # self.delayed_dimension_preview.timeout.connect

        # if self.delayed_dimension_preview.dis

        # TODO only allow this when the dimension changing is over
        # if the dimension exists --> print it
        # print(self.sender(), self.sender().objectName(), self.sender().value())
        # print(self.sender(), self.sender().objectName())
        # print(sender)
        #
        # try:
        #     # need change just the displayed image
        #     if self.paint.raw_image.metadata['dimensions']:
        #         # change the respective dim
        #         # need all the spinner values to be recovered in fact
        #         # and send the stuff
        #         # print('dimension exists', self.objectName(),'--> changing it')
        #
        #         # need gather all the dimensions --> TODO
        #         dimensions = self.paint.raw_image.metadata['dimensions']
        #         position_h =  dimensions.index('h')
        #         image_to_display = self.paint.raw_image
        #         if position_h!=0:
        #             # loop for all the dimensions before
        #             # print('changing stuff')
        #             for pos_dim in range(0,position_h):
        #                 dim = dimensions[pos_dim]
        #                 value_to_set = self.get_dim_value_by_name(dim)
        #                 if value_to_set == None:
        #                     continue
        #                 else:
        #                     image_to_display = image_to_display[value_to_set]
        #                 # if not dimensions[pos_dim]==self.sender().objectName():
        #                 #     image_to_display = image_to_display[0]
        #                 # else:
        #                 #     image_to_display = image_to_display[self.sender().value()]
        #         self.paint.set_display(image_to_display)
        # except:
        #     traceback.print_exc()

        # try:
        #     meta = None
        #     try:
        #         meta = self.paint.raw_image.metadata
        #     except:
        #         pass
        #     # metadata is required to get the luts properly
        #     self.paint.set_display(self.get_image_to_display_including_all_dims(), metadata=meta)
        # except:
        #     traceback.print_exc()

    def reset_crops(self):
        self.crop_left_spinbox.setValue(0)
        self.crop_right_spinbox.setValue(0)
        self.crop_top_spinbox.setValue(0)
        self.crop_bottom_spinbox.setValue(0)

    def reset_angle(self):
        self.rotate_image_spinbox.setValue(0)

    def load_background_parameters(self):
        if self.qt_viewer.background:
            # print('crops checks', self.qt_viewer.background.theta, self.qt_viewer.background.crop_left,self.qt_viewer.background.crop_right,self.qt_viewer.background.crop_top, self.qt_viewer.background.crop_bottom)
            self.update_annotations_list(lst=self.qt_viewer.background.annotations, update=True, repopulate_list=True,
                                         repopulate_texts=True)
            self.script_text_edit.setText(
                self.qt_viewer.background.custom_loading_script if self.qt_viewer.background.custom_loading_script else '')
            self.comments_text_edit.setText(
                self.qt_viewer.background.user_comments if self.qt_viewer.background.user_comments else '')
            self.input_file_widget.path.setText(
                self.qt_viewer.background.filename if self.qt_viewer.background.filename else '')
            # if self.qt_viewer.background.px_to_unit_conversion_factor:
            #     self.scale_conversion_spinner.setValue(self.qt_viewer.background.px_to_unit_conversion_factor) # update the scale (TODO at some point make sure the values are there)
            if self.qt_viewer.background.theta is not None:
                self.rotate_image_spinbox.setValue(self.qt_viewer.background.theta)
            if self.qt_viewer.background.crop_left is not None:
                self.crop_left_spinbox.setValue(self.qt_viewer.background.crop_left)
            if self.qt_viewer.background.crop_right is not None:
                self.crop_right_spinbox.setValue(self.qt_viewer.background.crop_right)
            if self.qt_viewer.background.crop_top is not None:
                self.crop_top_spinbox.setValue(self.qt_viewer.background.crop_top)
            if self.qt_viewer.background.crop_bottom is not None:
                self.crop_bottom_spinbox.setValue(self.qt_viewer.background.crop_bottom)


            # print('self.qt_viewer.background.px_to_unit_conversion_factor',self.qt_viewer.background.px_to_unit_conversion_factor)
            self.update_conversion_factor()

        # Ideally I should disconnect all the buttons above before doing that but maybe ok for now as it is not a big deal to compute
        self.compute_rotation_n_crop_polygon() # force update the rect

    def finalize_text_change_method_overrider(self):


        # print('finalize_text_change_method_overrider called')
        txt = self.input_file_widget.text()
        if txt:
            if os.path.exists(txt):
                self.input_file_widget.set_icon_ok(True)
            else:
                if not txt.strip().startswith("['") and not txt.strip().endswith("']"):
                    self.input_file_widget.set_icon_ok(False)
                else:
                    # can I label the wong files in red and the good ones in green in the text label ???
                    txt=reload_string_list(txt)
                    txt_output=''
                    failure = False
                    if isinstance(txt, str):
                        failure=True
                    if isinstance(txt, list) and not failure:
                        for file in txt:
                            if not os.path.exists(file):
                                txt_output+=f"<font color=#FF0000>'{file}'</font>,"
                                failure=True
                            else:
                                txt_output+=f"<font color=#00FF00>'{file}'</font>,"
                    if failure:
                        self.input_file_widget.set_icon_ok(False)
                    else:
                        self.input_file_widget.set_icon_ok(True)
                    if txt_output:
                        txt_output=txt_output[:-1]
                        # we temporarily disconnect text change
                        self.input_file_widget.path.blockSignals(True)
                        # we set text
                        self.input_file_widget.path.setHtml('['+txt_output+']')
                        # we reconnect text change
                        self.input_file_widget.path.blockSignals(False)

            # print('finalize_text_change_method_overrider changing bg')

            # print('checking if exists', self.qt_viewer.background)

            if self.qt_viewer.background:
                # print('finalize_text_change_method_overrider changing bg')

                if self.qt_viewer.background.filename == str(txt): # if new name is same as old name --> do not waste time and skip everything
                    # file was not changed --> so no need to reload it a priori -−> break
                    # print('skipping update')
                    return
                self.qt_viewer.background.filename = str(txt)
                self.qt_viewer.background = clone_object(self.qt_viewer.background) # the file was changed so we need rebuild it
                self.qt_viewer.background.get_px_to_unit_conversion_factor_from_metadata()  # try reload px size from file/script
                self.update_conversion_factor()
                self.update_dimension_sliders() # since the file was changed we ened to update the dimension sliders!!!
                self.update_normalization()
                self.update_channel_layout()
                self.update_annotations_list(lst=self.qt_viewer.background.annotations, update=True,
                                             repopulate_list=True,
                                             repopulate_texts=True)  # of course this is just such a big change that I need reload everything
                self.qt_viewer.update_size()
                self.qt_viewer.update()

    def show_warning(self, message):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("Warning")
        msg_box.setText(message)
        msg_box.exec_()

    def ROI_to_crop_or_inset(self):

        if not self.qt_viewer.selected_shape:
            # print('Draw a rectangular ROI and select it before pressing this button')
            self.show_warning("Draw a rectangular ROI and select it before pressing this button")
            return


        if not isinstance(self.qt_viewer.selected_shape[0], Rectangle2D):
            self.show_warning("Draw a rectangular ROI and select it before pressing this button")
            # print('Draw a rectangular ROI and select it before pressing this button')
            return


        to_crop=False
        if self.sender()==self.toCrop:
            to_crop =True

        theta = self.qt_viewer.selected_shape[0].theta
        rect = self.qt_viewer.selected_shape[0].getRect()
        color = self.qt_viewer.selected_shape[0].color

        angle, crop_left, crop_right, crop_top, crop_bottom = get_original_shape_from_rect_and_angle(self.qt_viewer.background.getRect(raw=True),rect, theta)

        clone = clone_object(self.qt_viewer.background)
        if not to_crop:
            clone.border_size=3
            clone.border_color =color

        clone.crop(crop_left, crop_right, crop_top, crop_bottom)

        clone.theta = angle
        clone.annotations = []  # maybe just keep the scale bar but maybe not ???
        clone = clone_object(clone)

        if to_crop:
            # send a message
            # print('crop succesfully added')
            self.qt_viewer.crops.append(clone)
        else:
            self.qt_viewer.background.annotations.append(clone)
            self.update_annotations_list(lst=self.qt_viewer.background.annotations, update=True,
                                         repopulate_list=True,
                                         repopulate_texts=True)
            self.qt_viewer.update_size()
            self.qt_viewer.update()

            # try:
            #     image = QImage(100, 100, QImage.Format_RGB32)
            #     painter = QPainter(image)
            #     self.qt_viewer.background.draw(painter)
            #     painter.end()
            #     del painter
            # except Exception as e:
            #     traceback.print_exc()
            #     print('drawing error can be ignored:', str(e))
            # pass

            # self.qt_viewer.update_size()
            # self.qt_viewer.update()

    def execute_script(self):
        self.qt_viewer.selected_shape = None
        if self.qt_viewer.background:
            warning_dialog = QMessageBox(parent=self)
            warning_dialog.setWindowTitle("Warning")
            warning_dialog.setText("Caution: Executing arbitrary code can pose significant risks, including system damage or data loss. Please ensure you trust the source and understand the implications before proceeding. \n\nAre you certain you want to continue?")
            warning_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            warning_dialog.setDefaultButton(QMessageBox.No)
            warning_dialog.setIcon(QMessageBox.Warning)

            if warning_dialog.exec_() == QMessageBox.Yes:
                self.qt_viewer.background.custom_loading_script = self.script_text_edit.toPlainText()
                self.qt_viewer.background = clone_object(self.qt_viewer.background)# here too --> I may have changed the file so I need to rebuild it # see how I can recover the script errors ???
                self.qt_viewer.background.get_px_to_unit_conversion_factor_from_metadata() # try reload px size from file/script
                self.update_dimension_sliders()  # since the file was changed we ened to update the dimension sliders!!!
                self.update_normalization()
                self.update_channel_layout()
                if self.qt_viewer.background.script_log:
                    self.script_log.setText(self.qt_viewer.background.script_log)
                self.load_background_parameters()
                self.update_annotations_list(lst=self.qt_viewer.background.annotations, update=True, repopulate_list=True,
                                             repopulate_texts=True) # of course this is just such a big change that I need reload everything
                self.qt_viewer.update_size()
                self.qt_viewer.update()

                # if True:
                #     # MEGA TODO --> UNDERSTAND WHY THE INSET IS NOT RESIZED PROPERLY ???
                #     try:
                #         image = QImage(100, 100, QImage.Format_RGB32)
                #         painter = QPainter(image)
                #         self.qt_viewer.background.draw(painter)
                #         painter.end()
                #         del painter
                #     except Exception as e:
                #         traceback.print_exc()
                #         print('drawing error can be ignored:', str(e))
                #     pass
                # self.qt_viewer.update_size() # for some reason the inset image is not updated and needs be clicked again to be placed there --> why is this bug there
                # self.qt_viewer.update()

    def reset_fill_color(self):
        self.qt_viewer.set_fill_color(None, self.ignore_changes)
        self.set_button_color(self.fillColor, None)
        self.set_scroll_area_bg_color() # also reset the bg color if reset


    def rotation_changed(self):
        self.qt_viewer.set_rotation(self.rotation_spinner.value(), self.ignore_changes)

    def opacity_changed(self):
        self.qt_viewer.set_opacity(self.opacity_spinner.value(), self.ignore_changes)

    def arrowhead_width_height_changed(self):
        self.qt_viewer.set_arrowhead_size(self.arrow_width_scaler.value(), self.arrow_height_scaler.value(), self.ignore_changes)

    def line_style_changed(self):
        if isinstance(self.sender(), QComboBox):
            sel = self.sender().currentText()
            idx = self.sender().currentIndex()
            self.lineEdit.setEnabled('ustom' in sel.lower())
        else:
            sel = 'custom'
        if not 'ustom' in sel.lower():
            self.qt_viewer.set_line_style(VectorialDrawPane2.line_styles[idx], self.ignore_changes)
        else:
            try:
                txt = self.lineEdit.text()
                if ',' in txt or ";" in txt:
                    txt = txt.replace(";", ",")
                    my_list = txt.split(",")
                else:
                    my_list = txt.split()
                my_list = [int(e) for e in my_list]

                self.qt_viewer.set_line_style(my_list)
            except:
                logger.warning('invalid custom dash pattern, try something like: "1, 4, 5, 4" without quotess')

    def set_button_color(self, btn, color):
        if color is not None:
            if isinstance(color, int):
                color = QColor.fromRgb(color)
            btn.setStyleSheet("background-color: " + color.name())
            btn.setText(color.name())
        else:
            btn.setStyleSheet('background-color: none;')  # reset style sheet
            btn.setText(str(color))


    def show_draw_widget(self):
        self.dockedWidgetShapes.show()

    def fitToWindow(self):
        self.qt_viewer.scale_to_window(self.scrollArea.size(), mode=0 if self.CURRENT_MODE else 1)

        if self.CURRENT_MODE:
            self.CURRENT_MODE = False
        else:
            self.CURRENT_MODE = True

    def add_new_text(self):
        if __DEBUG__:
            print('add new text to the image --> action required and also need update the stuff and I also need to update this one')
        self.qt_viewer.background.annotations.append(TAText2D('Your text here', placement=Position('top-left')))
        self.update_annotations_list(lst=self.qt_viewer.background.annotations, update=True, repopulate_list=True, repopulate_texts=True)

    def empty_texts_layout(self):
        while self.texts_layout.count():
            item = self.texts_layout.takeAt(0)
            # Delete the widget associated with the item
            if item.widget() is not None:
                item.widget().deleteLater()
            # Delete the item
            del item

    def refresh_texts(self):
        if self.qt_viewer.background and self.text_edit_watcher:
            for txtedit in self.text_edit_watcher.get_associated_texts():
                txtedit.refresh()

    def populate_texts_from_annotations(self):
        try:
            del self.text_edit_watcher
        except:
            pass

        content_widget2 = QWidget()
        texts_layout = QVBoxLayout(content_widget2)
        self.scroll_area2.setWidget(content_widget2)

        if self.qt_viewer.background:
            all_text_editors = []
            for obj in self.qt_viewer.background.annotations:
                if isinstance(obj, TAText2D):
                    txt = TextEditor(obj)
                    texts_layout.addWidget(txt)
                    all_text_editors.append(txt)
            self.add_text_button = QPushButton('Add Text')
            self.add_text_button.setFocusPolicy(Qt.NoFocus)
            self.add_text_button.clicked.connect(self.add_new_text)
            texts_layout.addWidget(self.add_text_button)
            self.text_edit_watcher = TextEditWatcher(all_text_editors, self.on_text_changed)
        else:
            self.text_edit_watcher = None

    def scaleImage(self, factor):
        self.scale += factor
        self.qt_viewer.resize(self.scale * self.qt_viewer.size())
        self.qt_viewer.scale = self.scale

        self.adjustScrollBar(self.scrollArea.horizontalScrollBar(), factor)
        self.adjustScrollBar(self.scrollArea.verticalScrollBar(), factor)

        self.zoomInAct.setEnabled(self.scale < self.max_scaling_factor)
        self.zoomOutAct.setEnabled(self.scale > self.min_scaling_factor)

    def adjustScrollBar(self, scrollBar, factor):
        scrollBar.setValue(int(factor * scrollBar.value()
                               + ((factor - 1) * scrollBar.pageStep() / 2)))

    # allow DND
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.CopyAction)
            event.accept()
        else:
            event.ignore()

    def test_function(self):
        # print('test function activated -−> action required')


        # self.qt_viewer.rotate_n_crop_polygon = get_shape_after_rotation_and_crop(self.qt_viewer.background.getRect(raw=True),
        #                                                                          self.rotate_image_spinbox.value(),
        #                                                                          self.crop_left_spinbox.value(),
        #                                                                          self.crop_right_spinbox.value(),
        #                                                                          self.crop_top_spinbox.value(),
        #                                                                          self.crop_bottom_spinbox.value())
        # self.qt_viewer.update()
        # self.compute_rotation_n_crop_polygon()
        pass

    def compute_rotation_n_crop_polygon(self):
        if self.qt_viewer.background:
            AR,self.qt_viewer.rotate_n_crop_polygon =  get_shape_after_rotation_and_crop(self.qt_viewer.background.getRect(raw=True),self.rotate_image_spinbox.value(), self.crop_left_spinbox.value(),self.crop_right_spinbox.value(), self.crop_top_spinbox.value(),self.crop_bottom_spinbox.value(), return_AR=True)
            #  Nb I shall be able to get the AR from that --> TODO --> think of that probably one of the bounding rects!!!!- -> TODO

            # print('found AR for image',AR)
            self.AR_display.setText(f'current AR (w/h): {AR}')
            self.qt_viewer.update() # ideally draw top bottom, left and right so that the user get the idea

    def down(self):
        if __DEBUG__:
            print(' def down(self):')
        self.qt_viewer.remove_selection()
        self.update_annotations_list(lst=self.qt_viewer.shapes,update=True, repopulate_list=True, repopulate_texts=True)

    def populate_list_from_annotations(self):
        if __DEBUG__:
            print('in populate_list_from_annotations')

        self.list.clearList()
        if self.qt_viewer.background:
            for obj in self.qt_viewer.background.annotations:
                self.list.add_object_to_list_no_check(
                    obj)  # ideally that would be great to add a picture of the element but maybe of for now

    def deletePressedInTheList(self):
        if __DEBUG__:
            print('delete pressed in list detected --> action required')
        self.update_annotations_list(update=True, repopulate_texts=True)

    def listSelectionChanged(self):
        if __DEBUG__:
            print('listSelectionChanged(self):')
        self.qt_viewer.selected_shape = self.list.get_selection(mode='multi')
        self.qt_viewer.update()

    def listOrderChanged(self):
        if __DEBUG__:
            print('list order changed')
        self.update_annotations_list(update=True)

    def update_annotations_list(self, lst=None,update=False, repopulate_list=False, repopulate_texts=False, refresh_texts=True):
        if __DEBUG__:
            print('in update_annotations_list')

        if lst is not None:
            reordered_list = lst
        else:
            reordered_list = self.list.get_full_list()
        # for some reason I need to do that or it does not work !!! -−> is there a better way to keep the lists in sync ?
        if self.qt_viewer.background:
            self.qt_viewer.background.annotations = reordered_list
        self.qt_viewer.shapes = reordered_list
        if update:
            self.qt_viewer.update()
        if repopulate_list:
            self.populate_list_from_annotations()
        if repopulate_texts:
            self.populate_texts_from_annotations()
        if refresh_texts:
            self.refresh_texts()

    def set_scroll_area_bg_color(self):
        """
        Sets the background color of the QScrollArea to the given color.

        Args:
            color (QColor or int): The color to set the background to. This can be a QColor object or an integer representing a color value in the format 0xAARRGGBB.
        """
        if self.qt_viewer.background:
            color = self.qt_viewer.background.fill_color
            if color is None:
                # if color is None, reset the background color to the default value
                # self.scrollArea.setPalette(QPalette())
                self.scrollArea.setStyleSheet("background-color: none;")
                return
            elif isinstance(color, QColor):
                # if color is a QColor object, use it directly
                color_str = color.name()
            elif isinstance(color, int):
                # if color is an integer, convert it to a hex string
                color_str = f"#{color:06x}"
            else:
                raise ValueError("color must be a QColor object or an integer")

            self.scrollArea.setStyleSheet(f"background-color: {color_str};")

    def selectionUpdated(self):
        if __DEBUG__:
            print('selectionUpdated')

        if self.qt_viewer.selected_shape:
            self.ignore_changes = True
            self.set_button_color(self.fillColor, self.qt_viewer.selected_shape[0].fill_color)
            self.qt_viewer.fill_color = self.qt_viewer.selected_shape[0].fill_color

            color = self.qt_viewer.selected_shape[0].color
            if color is None:
                color=0xFFFFFF
            self.set_button_color(self.contourColor, color)

            self.qt_viewer.contour_color = self.qt_viewer.selected_shape[0].color

            # MEGA TODO prevent loop --> setting the value will reapply it to the shape which is useless but probably not such a big deal (but I could disconnect the spinners and reconnect them after...)
            self.opacity_spinner.setValue(self.qt_viewer.selected_shape[0].opacity)
            self.rotation_spinner.setValue(self.qt_viewer.selected_shape[0].theta if self.qt_viewer.selected_shape[0].theta else 0)

            self.line_stroke_size.setValue(self.qt_viewer.selected_shape[0].stroke)
            # below we reload the shape pattern --> not that hard in fact !!!
            dash_dot_pattern = self.qt_viewer.selected_shape[0].line_style
            pen_style_map = {
                Qt.SolidLine: "SolidLine",
                Qt.DashLine: "DashLine",
                Qt.DashDotLine: "DashDotLine",
                Qt.DotLine: "DotLine",
                Qt.DashDotDotLine: "DashDotDotLine",
                'custom': "CustomDashLine"
            }

            # Get the current value of line_style
            current_pattern = dash_dot_pattern

            # If dash_dot_pattern is None, assume a solid line (default value)
            if current_pattern is None:
                current_pattern = Qt.SolidLine

            # Look up the string representation of the current pattern in the dictionary
            try:
                pattern_string = pen_style_map.get(current_pattern, "CustomDashLine")
            except:
                pattern_string = "CustomDashLine"
                self.lineEdit.setText(', '.join(str(x) for x in current_pattern))

            # Get the index of the item in the combo box that corresponds to the current pattern
            index = self.line_dotted_pattern_combo.findText(pattern_string)

            # Set the current index of the combo box to the index of the item that corresponds to the current pattern
            self.line_dotted_pattern_combo.setCurrentIndex(index)

            # if the shape is a line then add to it
            if isinstance(self.qt_viewer.selected_shape[0], Line2D):
                if self.qt_viewer.selected_shape[0].arrow:
                    self.arrow_width_scaler.setValue(self.qt_viewer.selected_shape[0].arrowhead_width_scaler)
                    self.arrow_height_scaler.setValue(self.qt_viewer.selected_shape[0].arrowhead_height_scaler)

        self.ignore_changes = False

    def shape_changed(self):
        if __DEBUG__:
            print('shape changed called --> action required')
        self.refresh_texts()

    def shape_added(self):
        if __DEBUG__:
            print('a shape was added in the viewer pane --> action needs be taken')
            print(len(self.qt_viewer.shapes), len(self.qt_viewer.background.annotations))
        self.update_annotations_list(lst=self.qt_viewer.shapes, update=True, repopulate_list=True, repopulate_texts=True)

    def on_text_changed(self, text_edit):
        if __DEBUG__:
            print(f"Text has changed upper capture in {text_edit}")
        self.qt_viewer.update()

    def on_line_stroke_size_value_changed(self):
        self.qt_viewer.set_stroke(self.line_stroke_size.value(), self.ignore_changes)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    bg = None
    print('#'*20)
    # svg_file2 = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/epithelium.svg', fill_color=0xFF00FF) # not good it appears sheared
    # svg_file2.set_rotation(45)
    # svg_file2 = Image2D('/E/Sample_images/sample_images_denoise_manue/29-1_lif/ON 290119.lif - Series001.tif') # not good it appears sheared
    # svg_file2 = Image2D('/E/Sample_images/sample_images_denoise_manue/29-1_lif/ON 290119.lif - Series003.tif') # not good it appears sheared
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/confocal-series.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/epithelia_examples/image_soichi_folding_wing/model_tests/first.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/organ-of-corti.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/mitosis.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/confocal-series.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/first-instar-brain.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/MAX_organ-of-corti.tif') # really a cool one!!!
    svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/graffiti.tif') # really a cool one!!! -−> the normalization is in rollback mode !! I need to be able to set the LUT of that --> even thuugh there is only one channel
    # svg_file2 = Image2D('/E/Sample_images/epithelia_examples/xenope/macroconfocal/MAX_crb3-1-82ng.tif') # really a cool one!!! # is there a LUT saved in there because if this is the case I do not read it...
    # svg_file2 = Image2D('/E/Sample_images/sample_images_FIJI/mri-stack.tif') # really a cool one!!!
    # svg_file2 = Image2D('/E/Sample_images/sample_images_PA/mini_vide/focused_Series012.png') # --> pb --> that shifts the channels
    # svg_file2 = None

    try:
        print('starting', svg_file2.img.shape) # target −> 'dhwc'
    except:
        pass # svg image no big deal

    # try with a user generated numpy array

    bg = svg_file2
    vdp = VectorialDrawPane2(background=bg)
    main = MainWindow(qt_viewer=vdp)

    # Create and show the custom dialog, passing the MainWindow widget as parent
    custom_dialog = CustomDialog(title="Annotate the image", message="Done with your edits? Press 'Ok' to apply the changes or 'Cancel' to ignore all changes.", main_widget=main, options=['Ok', 'Cancel'])
    if custom_dialog.exec_() == QDialog.Accepted:
        # print('need to recover the image and do things with it')
        # TODO I need also restore the initial scale of the image --> so I need get it before hand
        print(custom_dialog.main_widget.qt_viewer.background) # TODO --> maybe add a method to simplify that ???? because that is a bit heavy
    else:
        print('need to reset the changes --> see how to implement that can I simply clone all the shapes and edit the clone or do I need smthg smarter ??? no clue not so easy ')  # need a bit of thinking
    print('#'*20)