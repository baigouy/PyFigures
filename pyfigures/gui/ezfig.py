# what should I now do --> implement the fusion visually with mini images --> keep the unique ID of the object and get its AR and get its --> that would be great and let the user decide
# would need draw the hints over the image --> label cells with a unique ID --> see how I can do that
# TODO implement a visual cropper with a rect that one can draw over the image --> should be easy to do and is also very useful...
# maybe from objects --> label parents by their order in the list and label progeny with the nb of the progeny and so recursively if it contains more than one progeny --> not so easy todo
# how to do the preview or just copy rects that has the shape of the object and create a preview rapidly
# or for the labels --> do a duplicate of a row or a column but then link the images --> or link it to cols or row --> think about it --> not that easy for left panels especially if they should span sevral rows
# if an image is selected --> offer a swap
# if the same type of object is selected --> offer a swap
# otherwise offer / or _ --> easy to explain with text by the way if I can label the objects
# TODO create a list of content that is either a normal list or a browsable list or a tree --> maybe useful and easy to handle -> can also do the drag and drop at this level because all three levels are there --> this is another idea
# TODO --> think about it and decide
# could also give colors to objects/images --> label them with a color and show fusion based on colors --> the color can be derived from the hash (for exemple using the hash as a seed for random)
# think about retrotranslation of things
# for big objects --> put name on the center of it for small objects --> see how to do
# otherwise do and allow cancel and redo --> need clone all objects for that but can be useful (but a lot of mem especiallt with stacks)... or need save them and reload them --> can also be slow and painful
# get the rects and color them all
# --> fairly easy cause can get them iterably the rect --> and clone the object with just a clone of rects of the same --> then apply to that
# --> think about it can I fake it ? so that I don't have to really reload the image --> probably not
# think of How I can do the preview --> the colored rects are cool --> they could behave the same as images 2D but just have a color --> in a way i could also use them with empty sutff
# try get a simple version of the image with rects --> TODO --> just need the rects of the shape and not the intermediate ones --> could make sense
# TODO --> start to add the various options

# TODO --> faire des cloneurs

# try
# all is fairly good already but need improve plots a lot, if possible I guess yes --> can easily make things in a complex way
# finalize all
# almost there --> à tester
# move to front/send to back --> TODO

# TODO --> need remove object from their parent
# also needs check if object is contained in a parent and need find the parent if so
# only take objects that are in the list in fact

# done --> mouse click can handle zoom
# next step is what now???

# TODO if escape is pressed then I should remove the selection --> set it to none --> important
# TODO add a scrollbar around it and also allow to zoom --> pretty much a clone of the paint function --> TODO
# TODO handle menus with right click
# TODO add shortcuts and define a small GUI that would handle things in a much simpler way!!!
# if image is not 2D --> ask what to do with it in order to make it 2D and maybe return the corresponding script for the image
# --> maybe it's a good idea
# à tester
# aussi permettre des right clicks pr avoir pleins d'options et peut etre montrer le content d'un panel
# maybe also faire une queue
# maybe faire un organize qui se base sur du texte pour organiser les images
# par exemple pack les images ligne par ligne
# eg:
# test1.tif test2.tif test3.tif --> creates a row with three images
# test1.tif\ntest2.tif\ntest3.tif --> creates a column with those 3 images
# if just the word ROW --> open a dialog to pick images
# also support plots and themes --> TODO
# maybe distinguish deco from other things, e.g. original strings can be always kept and the edited ones can be kept too --> avoid permanently losing data
# TODO define my own save format and add a menu --> would be super useful
# either do this in this GUI or in another --> think about it ???

# TODO mix this with VectorialDrawPane2 to get the best of the two worlds then remove one of them and all other clones such as VectorialDrawPane (take care it's used in epyseg...')

# finir GUI ou pas ??? et aussi permettre de changer forme
# essayer de tout pythonizer au max pr eviter pbs
# voir comment permettre des rotations de formes comme dans EZF et aussi des rotations d'images

# TODO faire un GUI et aussi exporter les images dans ipython --> TODO
# faire un menu etc...
# faire que l'on puisse montrer ou non le menu de telle sorte que l'object puisse aussi servir de viewer en fait je dois déjà avoir ça je pense --> juste faire de la copie et autoriser le DND

# vector graphics ont l'air de marcher mais faudrait vraiment checker ça en détail
# essayer plus de trucs

# ça remarche enfin ça change bcp de choses mais au moins c'est plus constant maintenant et les object sont moins complexes et facilement dessinables sans translation si besoin --> plus facil ea gérer
# maintenant faire pareil avec les vectorial stuff --> TODO



# TODO en fait pr que le svg marche il faut faire un scaling de tout sinon ça ne marche pas --> des pbs d'alignement --> reflechir à pkoi...

# scale bar seems ok but need careful check somewhere

# TODO check scale bar length but may be ok or a small scaling factor somewhere --> if so need fix it
# TODO MEGA BIG bug in scale when change DPI --> need be fixed somewhere --> need a scale parameter in imaghes and see how to implement it and it needs to propagate to the scale bar --> see how

# allow to draw change size of objects etc...
# and ask if in free floating mode or in packed mode --> TODO
# add a scale bar etc...
# see how to handle fonts and have a default font unless changed by the user --> TODO otherwise apply style
# TODO maybe detect if selected a letter and allow edit it in fact that may be doable with the selection --> can further loop inside --> that may even make things simpler to ues and handle
# TODO add support for rotation, etc ... --> get inspiration from other stuff
# should I allow infinite texts or just as in the other --> maybe just as in the other
# TODO allow to create a label bar from two objects --> must span all of these objects --> good idea and simple to implement and to do and dimension should be the common one or ignore it
# need font support ???
# how can I change font from a formatted text already --> create a doc and change font in it but what about special chars --> is there a way to ignore ??? --> think about it...

# TODO allow the GUI to load locally under jupyter as napari does (unfortunately will not work on colab though...) but still useful
# allow cropping rotation or shear of the image --> TODO
# see how easy it is

# TODO add support for scale bars allow saving or serialization --> how can I do that ??? save as a series of commands so that it can always be recreated from scratch from source image, allow export as SVF or various formats with DPI scaling ???
# todo CAN I use css to change font and apply style would be so much simpler and better than current stuff...
# TODO check saving is really saving a svg object --> TODO

# see what else do I need and what I can do
# see what I have in the stuff
# should I allow a table like stuff ??? I think it's not useful as they can be
# do a ROI stuff --> allow to draw annotations on the image
# allow lettering outside --> see how ?
from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from pyfigures.gui.lutmultiselector import LutWidget
from pyfigures.gui.spaceselector import SpaceSelectorWidget
from pyfigures.gui.asingleoraspanel import AsSingleOrPanel
from pyfigures.gui.dimchooser import DimensionChooser
from batoolset.pyqts.pleasewaitdialog import PleaseWaitDialog
from builtins import Exception
from pyfigures.gui.fontselectorgui import FontSelector
from batoolset.drawings.shapes.rectangle2d import Rectangle2D
from pyfigures.gui.bg_color_selection import BackgroundColorPicker
from pyfigures.gui.panelcreationwidget import PanelCreator
from batoolset.dims.tools import scaling_factor_to_achieve_DPI
from batoolset.img import guess_dimensions
from batoolset.pyqts.tools import distance, getCtrlModifier
from pyfigures.gui.group_builder_GUI import PanelOrRow
from pyfigures.gui.emptyimagedialog import EmptyImageParametersWidget
from pyfigures.gui.simple_text_editor import TextEditor
from batoolset.serializations.tools import deserialize_to_dict
from batoolset.serializations.tools import object_to_xml, create_object, clone_object
import os
from functools import partial
from batoolset.lists.tools import is_iterable, move_right, move_left, swap_items, flatten_iterable, \
    find_first_object_of_type, find_all_objects_of_type, divide_list_into_sublists
from batoolset.GUI.customdialog import CustomDialog
from batoolset.drawings.shapes.group import Group, set_to_size, get_parent_of_obj, set_to_width
import sys
import numpy as np
import traceback
import copy # used to clone class instances
from qtpy.QtCore import QSize, QRect, QRectF, QPoint, QPointF, Qt, QSizeF, Signal, QTimer,QObject,QEvent
from qtpy.QtSvg import QSvgGenerator
from qtpy.QtWidgets import QMenu, QDialog,QWidget,QApplication, QVBoxLayout, QPushButton,QScrollArea,QLabel,QInputDialog, QMessageBox,QSpinBox
from qtpy.QtGui import QBrush, QPen, QColor, QTransform,QPainter, QColor,QFontMetrics,QImage,QPdfWriter,QPageSize,QTextCursor, QFont, QTextCharFormat, QRegion
from batoolset.drawings.shapes.freehand2d import Freehand2D
from batoolset.drawings.shapes.scalebar import ScaleBar
from batoolset.drawings.shapes.polygon2d import Polygon2D
from batoolset.drawings.shapes.line2d import Line2D
from batoolset.drawings.shapes.rect2d import Rect2D
from batoolset.drawings.shapes.square2d import Square2D
from batoolset.drawings.shapes.ellipse2d import Ellipse2D
from batoolset.drawings.shapes.circle2d import Circle2D
from batoolset.drawings.shapes.point2d import Point2D
from batoolset.drawings.shapes.polyline2d import PolyLine2D
from batoolset.drawings.shapes.image2d import Image2D
from batoolset.figure.alignment import packX, pack2, align2, align_positions
# from batoolset.figure.column import Column
from batoolset.drawings.shapes.txt2d import TAText2D
from batoolset.figure.fig_tools import  get_master_bounds2 #get_master_bounds,
# from batoolset.figure.row import Row
import os.path
from pyfigures.gui.annotation_editor_former_000_TOP_vectorial2 import VectorialDrawPane2, MainWindow
from batoolset.tools.logger import TA_logger  # logging

# en fait pas mal et faire autour un GUI avec un menu qui contient ça
# voir dans TA comment j'ai fait ça...

# can I use that to plot with TA the vectors on the image --> in a way that's a bit redundant compared to the quiver of matplotlib, but there are a lot of things that are hard to handle in matloplib and it's not vectorial...

logger = TA_logger()

__DEBUG_SELECTION__ = False


def _finish_svg(svg_path, collector=None):
    """The written SVG: vector panels embedded from their own source
    (*collector*, svg_embed), and real font families (svg_painter)."""
    from pyfigures.gui.svg_painter import real_font_families
    try:
        with open(svg_path, encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return
    new = text
    if collector is not None:
        new = collector.embed(new)
    new = real_font_families(new)
    if new != text:
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(new)


# can I use this also to render offline a drawing on an image --> try it maybe
# how do I know the size of this stuff ??? --> need update its size according to its content and probably the zoom --> TODO

class MyWidget(QWidget):
    # NB all signals are gathered in: finalize_and_update(self): # gather all the possible signals in there

    selectionChanged = Signal()  # add a signal that emits when there is a new selection
    informative_message_required = Signal(str) # this is called when a message is required
    undo_redo_save_required = Signal() # this is called when a change has been made to the figure and a save is required
    update_text_rows = Signal() # this is called when a change has been made to the figure and a save is required
    focus_required = Signal() # is called when the GUI should autoscroll to a position --> TODO
    update_letters_required = Signal()
    force_update_size_of_parent = Signal(object) #  should be called every time the parent must be set to the desired GUI size # the object here is the parent that should be draw at desired width --> TODO
    open_lettering_parameters = Signal() #  should be called when the user requests to change the parameters
    # templatify_figure = Signal(object) # send back to parents stuff that needs to be converted to templates
    force_update_store = Signal()#this forces the store to update its content by removing useless files
    force_silent_spinner_update_in_parent = Signal(int)#this forces the store to update its content by removing useless files

    modes = ['auto','custom'] # auto positioning or custom positioning # TODO ideally automaticamlly set at 50 50 to avoid overlap with rulers if they are there in auto mode
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self._please_wait_dialog = PleaseWaitDialog(self)

        self.shapes_to_draw = []
        self._help_arrow_x = None   # cached x for the empty-canvas hint arrow
        self.lastPoint = None
        self.firstPoint = None
        # self.resizable = resizable
        self.is_sticky = False
        self._stored_shape_n_its_coords = {}
        self.initial_position = None # coords of the shape to restore upon no action
        self.ACTIVATE_RULER = True # show rulers in the image
        self.dragging = False
        self.mode = MyWidget.modes[0]
        self.space=3. # default space between images
        # figure-wide background (0xRRGGBB) behind the panels and the gaps
        # between them; None = transparent (PNG/TIFF) or white (JPG)
        self.page_background = None
        self.contextMenu = QMenu(self)
        self._EXTRA_PADDING = 50 # extra padding to place a ruler or alike
        # self.freeze = False # somehow I failed at freezing shape changes --> no clue why
        # panel2 | panel
        # panel2 | panel # for swapping panels
        # panel | panel2

        # Create a QTimer object
        self.timer = QTimer(self)

        # Set the timeout interval to 1000 milliseconds (1 second)
        self.timer.setInterval(800)

        # Connect the timeout signal to the emit_undo_redo_save_required method
        self.timer.timeout.connect(self.emit_undo_redo_save_required)


        # panel << img3

        # ça ne marche pas pkoi

        # img3 >> panel # does not work --> need implement it in my image2D

        # panel >> img3

        # cannot be dragged --> is it because self.is_set
        # row.packX()
        # row.packY() # ça marche mais finaliser le truc pr que ça soit encore plus simple à gerer
        # img.setP1(10,10) #translate it --> cool
        # self.shapes_to_draw.append(img1)
        # self.shapes_to_draw.append(img2)
        # self.shapes_to_draw.append(img3)
        self.scale = 1.
        self.selected_shape = None
        self.bounds = None
        self._layout_dirty = True # force lettering+repack on first paint

        self.update_size()
        self.update()


        # if True:
        #     # add right click options
        #     self.contextMenuEvent()

    def set_scale(self, scale):
        if scale < 0.01:
            scale = 0.01
        if scale > 50:
            scale = 50
        self.scale = scale

    def invalidate_layout(self):
        """Mark the figure model as changed: the next paint will re-letter and repack.
        Paints caused by scrolling/exposure alone skip that work entirely."""
        self._layout_dirty = True

    def update(self, *args, **kwargs):
        # every explicit repaint request in this codebase follows a model change,
        # so treat it as a layout invalidation; Qt-driven expose/scroll repaints
        # do not come through here and stay cheap
        self._layout_dirty = True
        # Many signals are connected straight to update() (textChanged(str),
        # stateChanged(int), toggled(bool), ...) and pass their value along;
        # QWidget.update() rejects those (TypeError inside a slot), so only a
        # real region/rect/4-int form is forwarded.
        if args and not (len(args) == 4 and all(isinstance(a, int) and not isinstance(a, bool) for a in args)) \
                and not isinstance(args[0], (QRect, QRegion)):
            args = ()
        super().update(*args, **kwargs)

    def contextMenuEvent(self, event): # DEV NOTE KEEP: MEGA IMPORTANT THIS IS VERY IMPORTANT TO ALLOW RIGHT CLICK TO REACH THE MOUSE RELEASE OTHERWISE IT NEVER DOES SO AND SO MY MENU UPDATE IS NOT THE ONE I WANT
        # Override to prevent context menu from appearing
        event.ignore()

    # a right click menu
    # TODO --> do a more realistic menu
    # def contextMenuEvent(self, event):
    #     if self.contextMenu:
    #         if self.contextMenu.actions():
    #             # self.contextMenu = QMenu(self)
    #             # newAct = self.contextMenu.addAction("New")
    #             # openAct = self.contextMenu.addAction("Open")
    #             # quitAct = self.contextMenu.addAction("Quit")
    #             # move_to_front = self.contextMenu.addAction("Move To Front")
    #             # copy_ = contextMenu.addAction("Duplicate") # ça ne marche pas
    #             # send_to_back = self.contextMenu.addAction("Send To Back")
    #             action = self.contextMenu.exec_(self.mapToGlobal(event.pos()))
    #             # if action == quitAct:
    #             #     self.close()
    #
    #             # print('action called', action)
    #             # if action == move_to_front:
    #             #     self.move_to_front()
    #             # if action == send_to_back:
    #             #     self.send_to_back()
    #
    #             # marche pas --> il faut hardcoder la copie comme dans java --> TODO
    #             # if action == copy_:
    #             #     self.copy()
    #             # ça marche --> est-ce que je peux recupérer l'object sous la souris ??? pr faire des actions differentes en fonction
    #             # maybe offer different options for different levels in the same menu --> gain of time and no need for cycling the selection
    #         else:
    #             # print('the menu is empty')
    #             pass
    #             # raise Exception('why is menu empty?')

    def repack_all(self):
        # Remove empty groups (can appear after label operations)
        self.shapes_to_draw = [s for s in self.shapes_to_draw
                               if not (hasattr(s, 'content') and len(s.content) == 0)]
        if self.shapes_to_draw:
            self.shapes_to_draw[0].setTopLeft(self._EXTRA_PADDING, self._EXTRA_PADDING)
            align2(align_positions[2], *self.shapes_to_draw)
            pack2(self.space, 'Y', False, *self.shapes_to_draw)
            # Align label rows with their image groups — done here so positions are always final.
            # Don't rely on isText direction value: the user can move label rows, making it stale.
            # Instead, look at both neighbors and pick the adjacent non-label image group.
            for i, s in enumerate(self.shapes_to_draw):
                if not getattr(s, 'isText', False) or not hasattr(s, 'content'):
                    continue
                grp = None
                for grp_idx in (i - 1, i + 1):
                    if 0 <= grp_idx < len(self.shapes_to_draw):
                        candidate = self.shapes_to_draw[grp_idx]
                        if not getattr(candidate, 'isText', False) and hasattr(candidate, 'content'):
                            grp = candidate
                            break
                if grp is None:
                    continue
                non_text = [e for e in grp.content if not getattr(e, 'isText', False)]
                if not non_text:
                    continue
                # Place each label directly at the x position of its corresponding image.
                # This handles side labels anywhere in the group (left edge, between images, right edge).
                labels = list(s.content)
                for j, lbl in enumerate(labels):
                    if j < len(non_text):
                        img = non_text[j]
                        try:
                            lbl.setWidth(img.width(all=True))
                            lbl.set_to_scale(1)
                            lbl.setTopLeft(img.x(), lbl.y())
                        except Exception:
                            import traceback; traceback.print_exc()
                s.update_bounds()
        self.update_size()

    def _compute_help_arrow_x(self):
        """Compute and cache the x position of the Help menu button in this widget's coords.
        Must be called outside paintEvent to avoid Wayland global-coord call restrictions."""
        try:
            main_win = self.window()
            if hasattr(main_win, 'menuBar') and main_win.menuBar is not None:
                mb = main_win.menuBar
                actions = mb.actions()
                if actions:
                    help_rect = mb.actionGeometry(actions[-1])
                    center_global = mb.mapToGlobal(
                        QPoint(help_rect.center().x(), 0))
                    self._help_arrow_x = self.mapFromGlobal(center_global).x()
                    return
        except Exception:
            pass
        self._help_arrow_x = max(self.width() - 60, 0)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._compute_help_arrow_x)

    def paintEvent(self, event):
        # lettering + repacking only run when the model actually changed
        # (_layout_dirty); expose/scroll/hover repaints just redraw
        if self._layout_dirty and not self.dragging:
            self.update_letters_required.emit() # force update letters before drawing anything
        # if self.freeze:
        #     return

        painter = QPainter(self)
        # paint_something(painter)
        # with QPainterTracker(painter):

        painter.save()

        # current_clip_rect = painter.clipBoundingRect()

        # handles zoom
        if self.scale != 1:
            painter.scale(self.scale, self.scale)

        # print('I am inside paintevent and rescaling all', not self.dragging, self.mode,  self.mode == MyWidget.modes[0])
        if not self.dragging and self._layout_dirty:
            if self.mode == MyWidget.modes[0]: # by default
                # print('I am inside paintevent and rescaling all')
                self.repack_all()
            self._layout_dirty = False

        # only draw shapes intersecting the exposed region (big win when scrolled);
        # margin absorbs borders/annotations that slightly overflow the shape rect
        exposed = None
        try:
            exposed = QRectF(event.rect())
            if self.scale != 1:
                exposed = QRectF(exposed.x() / self.scale, exposed.y() / self.scale,
                                 exposed.width() / self.scale, exposed.height() / self.scale)
            exposed = exposed.adjusted(-100, -100, 100, 100)
        except Exception:
            exposed = None

        self._paint_page_background(painter)
        for shape in self.shapes_to_draw:
            if exposed is not None:
                try:
                    if not exposed.intersects(shape.getRect(all=True)):
                        continue
                except Exception:
                    pass
            shape.draw(painter) # BUG SOMEHOW THIS SETS A CLIP RECT THAT IS NOT RESET AND SO SELECTION AND STUFF ALIKE CANNOT BE PAINTED !!! --> BIG PB --> NEED CLEAN THE CODE --> BUG FIXED IT WAS DUE TO too late painter.save IN IMAGE2D !!!

        # painter.setClipRect(QRect()) # I need reset the clip rect
        # painter.setClipRect(None) # I need reset the clip rect
        # painter.setClipRect(current_clip_rect) # I need reset the clip rect
        # painter.setClipRect(QRect(0,0,int(self.width()), int(self.height()))) # dirty fix for clip rect error --> I artificially resize the whole stuff to the full image
        # painter.restore()
        # painter.save()
        if self.ACTIVATE_RULER:
            # print('self.width() dabula', self.width(), self.width()/self.scale)


            # print('inside ruler', self.width(), self.height())

            # TODO --> maybe convert the ruler into a cm unit !!!

            # draw a ruler in X
            # painter = QPainter(self)
            # painter.setRenderHint(QPainter.Antialiasing)

            pen = QPen(QColor(Qt.gray).lighter(150), 2, Qt.SolidLine)
            painter.setPen(pen)

            # quite good but maybe takes too much space and is not in cm or in inches --> maybe I need a fix --> think of that and fix that

            EXTRA_SPACE_FOR_RULER = self._EXTRA_PADDING
            SKIP_ZERO=False
            # Draw the ruler lines


            # ticks are drawn from the padding on, so they stop one padding before
            # the edge, and a label that would be cut by the edge is not drawn
            # (the last one used to be clipped, e.g. "5" for 500)
            fm = painter.fontMetrics()
            visible_w = self.width() / self.scale
            visible_h = self.height() / self.scale
            for i in range(0, int(visible_w), 10):
                if SKIP_ZERO and i == 0:
                    continue
                if i % 50 == 0: # we only keep the main ticks
                    label = str(i)
                    x = EXTRA_SPACE_FOR_RULER + i
                    half = fm.horizontalAdvance(label) / 2
                    if x + half > visible_w:
                        break
                    painter.drawLine(x, 15, x, 0)
                    painter.drawText(int(x - half), 30, label)  # centred on its tick

            for i in range(0, int(visible_h), 10):
                if SKIP_ZERO and i==0:
                    continue
                if i % 50 == 0:
                    y = EXTRA_SPACE_FOR_RULER + i
                    if y + fm.ascent() / 2 > visible_h:
                        break
                    painter.drawLine(0, y, 10, y)
                    painter.drawText(12, int(y + fm.ascent() / 2 - 1), str(i))
                # elif i % 10 == 0:
                #     painter.drawLine(0, i, 30, i)
                # else:
                #     painter.drawLine(0, i, 20, i)

        # if there is a selection always draw it last so that it is always visible (this is important especially when dragged otherwise that is a bit hard to handle)
        # in fact we don't want to see the stuff on top because it may mask the drop target
        # if self.selected_shape is not None:
        #     try:
        #         self.selected_shape.draw(painter)
        #     except:
        #         pass
        self.draw_selection(painter) # but draw its selection so that it will be visible for the user

        if isinstance(self.bounds, QRectF):
            painter.save()
            # how can I get the bounds ???


            drawing_bounds = self.updateBounds()

            if drawing_bounds.width() > self.bounds.width() or drawing_bounds.height() > self.bounds.height():
                painter.setPen(QPen(QColor(255,0,0),3))
            else:
                painter.setPen(QPen(QColor(0, 255, 0), 0.65))
            painter.setOpacity(0.3)
            painter.drawRect(self.bounds)
            painter.restore()


        painter.restore()

        # Empty-canvas hint — shown when no images have been loaded yet
        if not self.shapes_to_draw:
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            hint_color = QColor(200, 30, 30)  # red
            painter.setPen(hint_color)

            # Use cached arrow_x (computed in showEvent to avoid Wayland issues)
            arrow_x = self._help_arrow_x if self._help_arrow_x is not None \
                else max(self.width() - 60, 0)

            # Arrow pointing up toward Help menu
            arrow_font = QFont(painter.font())
            arrow_font.setPointSize(22)
            painter.setFont(arrow_font)
            painter.drawText(QRect(arrow_x - 20, 6, 40, 34),
                             Qt.AlignHCenter | Qt.AlignVCenter, '↑')

            label_font = QFont(painter.font())
            label_font.setPointSize(9)
            painter.setFont(label_font)
            painter.drawText(QRect(arrow_x - 90, 42, 180, 20),
                             Qt.AlignHCenter | Qt.AlignVCenter,
                             'Help  →  Interactive Tutorials')

            # Centred main hint
            body_font = QFont(painter.font())
            body_font.setPointSize(11)
            painter.setFont(body_font)
            body_rect = QRect(0, self.height() // 2 - 40, self.width(), 80)
            painter.drawText(body_rect,
                             Qt.AlignHCenter | Qt.AlignVCenter | Qt.TextWordWrap,
                             'Drop image files here to get started')
            painter.restore()

        painter.end()


    def _get_rect(self, shape):
        rect = None
        # the rect is this one
        # in some cases I need to have access to the original object size --> need keep it but the best is that bounds mimic current object shape
        if isinstance(shape, QRectF):
            # this is a rect2D --> I can therefore easily draw it --> TODO
            try:
                rect = shape.getRect(all=True)
            except Exception:
                rect = shape
        else:
            if isinstance(shape, list):
                # print('master rect')
                rect = get_master_bounds2(shape)  # why do I need that ???
        return rect
    # TODO --> see how to do that ???
    # the other possibility is to draw from within the object --> can be draw its skeleton by the way --> would allow to handle more shapes
    # see how I can handle selection groups --> see how I was doing in EZF by the way because it was really working well!!
    def draw_selection(self, painter):
        if self.selected_shape is not None:
            # could also color according to shapes

            rect = self._get_rect(self.selected_shape)
            # print(rect)
            if rect is not None:


                if True and self.dragging:
                    for shape in self.shapes_to_draw:
                        # if shape == self.selected_shape:
                        #     continue
                        try:
                            shape.draw_inner_layout_selection(painter=painter)
                        except Exception:
                            pass
                    # now draw the rect of all other shapes to help the user see where he will dnd stuff --> easier
                    # TODO need implement a draw sel that draws the skeleton of all the images --> can be useful to visualize the drag
                    # this will be the rect of the bounds -−> TODO

                if True:
                    pen = QPen(QColor(255, 0, 255))  # orange
                    pen.setWidthF(6)
                    painter.setPen(pen)
                    # painter.setBrush(QBrush(QColor(0)))
                    # find a way to write the text a bit below

                    # Draw Empty in the center of the rectangle (the shape has no image so it cannot be incorporated)
                    try:
                        text = self.selected_shape.__repr__()
                    except Exception:
                        text = 'Multi'
                    font = painter.font()  # Use the current font or set a custom font if desired

                    # Calculate the text's center position within the rectangle
                    font_metrics = QFontMetrics(font)
                    text_width = font_metrics.width(text)
                    text_height = font_metrics.height()
                    text_x = rect.x() + rect.width() / 2. - text_width / 2.
                    text_y = rect.y() + rect.height() / 2. + text_height / 2.

                    # Draw the text in the middle of the rectangle
                    # painter.drawRect()



                    # try:
                    painter.drawText(int(text_x), int(text_y), text)
                    # except:
                    #     print('failed text', text)
                    #     traceback.print_exc()

                pen = QPen(QColor(255, 255, 0), 3)
                painter.setPen(pen)
                painter.drawRect(rect)
            else:
                print('shape not supported yet for drawing selection')


    def get_dpi(self):
        # TODO --> maybe integrate this directly within the save window so that it is not a two step process --> but ok for now
        # Create a list of valid DPI values
        dpi_values = ['72', '150', '300', '600']
        # Ask the user for the desired DPI
        # desired_dpi, ok = QInputDialog.getInt(self, "Input DPI", "Enter the desired DPI:", 300, 1, 1000)
        desired_dpi, ok = QInputDialog.getItem(self, "output DPI", "Select the desired output DPI:", dpi_values, 2)
        if not ok:
            # Cancel cancels the export (it used to re-open this prompt forever,
            # so an export could not be abandoned)
            return None
        try:
            desired_dpi = int(desired_dpi)
        except Exception:
            desired_dpi = None
        if desired_dpi and desired_dpi > 0:
            return desired_dpi
        QMessageBox.warning(self, "Invalid Input", "Please enter a valid DPI value.")
        return None

    # TODO maybe get bounding box size in px by measuring the real bounding box this is especially important for raster images so that everything is really saved...
    SVG_INKSCAPE = 96
    SVG_ILLUSTRATOR = 72

    def wait_for_pending_images(self):
        """Exports first wait for images still loading in the background (in
        the GUI), so no panel is exported before its pixels are there."""
        window = self.window()
        if window is not self and hasattr(window, 'wait_for_images'):
            window.wait_for_images()

    def save(self, path, filetype=None, title=None, description=None, svg_dpi=SVG_INKSCAPE, crop=None):
        """*crop* (.qpic only): (left, top, right, bottom) fractions of the
        figure clipped away in the recording. Replaying a QPicture also
        replays its clip-state changes, which would undo a clip set around it."""
        if path is None or not isinstance(path, str):
            logger.error('please provide a valide path to save the image "' + str(path) + '"')
            return
        self.wait_for_pending_images()
        if filetype is None:
            if path.lower().endswith('.svg'):
                filetype = 'svg'
            elif path.lower().endswith('.pdf'):
                filetype = 'pdf'
            elif path.lower().endswith('.qpic'):
                filetype = 'qpic'
            else:
                filetype = os.path.splitext(path)[1]
        # dpi = 72  # 300 # inkscape 96 ? check for illustrator --> check

        picture = None
        if filetype == 'qpic':
            # the paint commands themselves (QPicture), replayed by the poster
            # designer into its PDF: text stays text (Qt's SVG renderer turns
            # it into outlines), images keep their resolution, clips are kept.
            # 1 unit = 1 pt, like the PDF/SVG exports.
            import math
            from qtpy.QtGui import QPicture
            bounds = self.updateBounds()
            picture = QPicture()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            painter = QPainter(picture)
            if crop is not None:
                left, top, right, bottom = (float(v) for v in crop)
                w = float(bounds.width())
                h = float(bounds.height())
                painter.setClipRect(QRectF(left * w, top * h, (1 - left - right) * w, (1 - top - bottom) * h))
            painter.translate(-bounds.x(), -bounds.y())
        elif filetype in ['svg','pdf']:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QApplication.processEvents()
            # The page is the figure itself, at its true physical size: canvas
            # units are points, so 1 unit = 1 pt at 72 dpi. (A fixed A4 page at
            # 96 dpi used to shrink every figure to 75 % — a 183 mm Nature
            # column came out 137 mm — and cut off anything beyond the page.)
            # *svg_dpi* is kept for compatibility and no longer changes the size.
            import math
            from qtpy.QtCore import QSizeF, QMarginsF, QRectF
            bounds = self.updateBounds()
            fig_w = max(1.0, float(bounds.width()))
            fig_h = max(1.0, float(bounds.height()))
            if filetype == 'svg':
                generator = QSvgGenerator()
                generator.setFileName(path)
                generator.setSize(QSize(int(math.ceil(fig_w)), int(math.ceil(fig_h))))
                generator.setViewBox(QRectF(0, 0, fig_w, fig_h))
            else:
                from qtpy.QtGui import QPageLayout
                generator = QPdfWriter(path)
                # whole points, rounded up (Qt rounds page sizes; never clip)
                generator.setPageSize(QPageSize(QSizeF(math.ceil(fig_w), math.ceil(fig_h)), QPageSize.Unit.Point, '',
                                                QPageSize.SizeMatchPolicy.ExactMatch))
                generator.setPageMargins(QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)

            if title is not None and isinstance(title, str):
                generator.setTitle(title)
            if description is not None and isinstance(description, str):
                generator.setDescription(description)
            generator.setResolution(72)

            if filetype == 'svg':
                # Qt's SVG engine ignores drawImage source rects: crop ourselves
                from pyfigures.gui.svg_painter import CroppingPainter
                painter = CroppingPainter(generator)
            else:
                painter = QPainter(generator)
            painter.translate(-bounds.x(), -bounds.y())

            # print(generator.title(), generator.heightMM(), generator.height(), generator.widthMM(),
            #       generator.resolution(), generator.description(), generator.logicalDpiX())
        else:
            # scaling_factor_dpi = 1
            dpi = self.get_dpi()
            if dpi is None:
                return False            # export cancelled: nothing written
            scaling_factor_dpi = scaling_factor_to_achieve_DPI(dpi)
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QApplication.processEvents()

            # in fact take actual page size ??? multiplied by factor
            # just take real image size instead

            # image = QImage(QSize(self.cm_to_inch(21) * dpi * scaling_factor_dpi, self.cm_to_inch(29.7) * dpi * scaling_factor_dpi), QImage.Format_RGBA8888) # minor change to support alpha # QImage.Format_RGB32)

            # NB THE FOLLOWING LINES CREATE A WEIRD ERROR WITH WEIRD PIXELS DRAWN some sort of lines NO CLUE WHY
            img_bounds = self.updateBounds()

            image = QImage(
                QSize(int(round((img_bounds.width() * scaling_factor_dpi))), int(round((img_bounds.height() * scaling_factor_dpi)))),
                QImage.Format_RGBA8888)  # minor change to support alpha # QImage.Format_RGB32)
            # print('size at dpi',QSize(img_bounds.width() * scaling_factor_dpi, img_bounds.height()* scaling_factor_dpi))
            # QSize(self.cm_to_inch(0.02646 * img_bounds.width())
            # self.cm_to_inch(0.02646 * img_bounds.height())
            # need convert pixels to inches
            # is there a rounding error

            # force white bg for non jpg
            try:
                # print(filetype.lower())
                # the tif and png file formats support alpha
                if not filetype.lower() == '.png' and not filetype.lower() == '.tif' and not filetype.lower() == '.tiff':
                    image.fill(QColor.fromRgbF(1, 1, 1))
                else:
                    # image.fill(QColor.fromRgbF(1, 1, 1, alpha=1))
                    # image.fill(QColor.fromRgbF(1, 1, 1, alpha=1))
                    # TODO KEEP in fact image need BE FILLED WITH TRANSPARENT OTHERWISE GETS WEIRD DRAWING ERRORS
                    # TODO KEEP SEE https://stackoverflow.com/questions/13464627/qt-empty-transparent-qimage-has-noise
                    # image.fill(qRgba(0, 0, 0, 0))
                    image.fill(QColor.fromRgbF(0, 0, 0, 0))
            except Exception:
                pass
            painter = QPainter(image)  # see what happens in case of rounding of pixels
            # start at the figure's own top-left corner, which is not always
            # the default margin (free-canvas figures can start anywhere)
            painter.translate(-img_bounds.x() * scaling_factor_dpi, -img_bounds.y() * scaling_factor_dpi)
            # painter.begin()
            painter.scale(scaling_factor_dpi, scaling_factor_dpi)

        # painter.setRenderHint(QPainter.HighQualityAntialiasing)  # to improve rendering quality
        # painter.setRenderHint(Qt.AA_UseHighQualityAntialiasing)  # to improve rendering quality
        # painter.setRenderHint(QPainter.Antialiasing) # or SmoothPixmapTransform # to improve rendering quality
        painter.setRenderHint(QPainter.SmoothPixmapTransform) # or SmoothPixmapTransform # to improve rendering quality
        painter.setRenderHint(QPainter.Antialiasing) # or SmoothPixmapTransform # to improve rendering quality
        # painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        fig_images = []
        import contextlib
        from batoolset.drawings import svg_embed
        # SVG: vector panels are embedded from their own SVG source (text and
        # clip paths kept), see batoolset.drawings.svg_embed
        embedding = svg_embed.collecting() if filetype == 'svg' else contextlib.nullcontext()
        try:
            all_shapes = flatten_iterable(self.shapes_to_draw)
            fig_images = [s for s in all_shapes if hasattr(s, 'enter_export_mode')]
            for img in fig_images:
                img.enter_export_mode()
            with embedding as collector:
                self.paint(painter)
                painter.end()
            if filetype == 'svg':
                # QSvgGenerator keeps its file open until it is deleted
                painter = None
                generator = None
                _finish_svg(path, collector)
            if picture is not None:
                if not picture.save(path):
                    raise OSError(f'could not write {path}')
                # QPicture does not save a bounding rect (it recomputes the
                # drawn extent): the figure's size, and the picture's own dpi
                # (replaying scales by device dpi / picture dpi), go beside it
                import json
                with open(path + '.json', 'w', encoding='utf-8') as f:
                    json.dump({'width_pt': float(bounds.width()), 'height_pt': float(bounds.height()),
                               'picture_dpi': picture.logicalDpiX()}, f)
            elif filetype not in ['svg', 'pdf']:
                # record the export resolution in the file (it said 96 DPI, so a
                # 300 DPI export looked 3x too large to journals and layout
                # programs). Set only now: the image's DPI also sizes the text
                # while painting.
                dots_per_meter = int(round(dpi / 0.0254))
                image.setDotsPerMeterX(dots_per_meter)
                image.setDotsPerMeterY(dots_per_meter)
                # Try Qt-native save first (requires pyqt6-plugins for TIF support).
                # Fall back to tifffile for TIF/TIFF if the Qt plugin is unavailable.
                if not image.save(path) and filetype.lower() in {'.tif', '.tiff'}:
                    try:
                        import tifffile
                        import numpy as np
                        ptr = image.bits()
                        n_bytes = image.height() * image.width() * 4
                        ptr.setsize(n_bytes)
                        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(
                            image.height(), image.width(), 4)
                        tifffile.imwrite(path, arr, resolution=(dpi, dpi), resolutionunit='INCH')
                    except Exception:
                        traceback.print_exc()
        finally:
            for img in fig_images:
                img.exit_export_mode()
            QApplication.restoreOverrideCursor()
            QApplication.processEvents()

    def _collect_time_stacks(self):
        """Return [(image2d, dim_string, t_count)] for every panel backed by a
        time-stack (a 't' axis), across groups. Empty if the figure has no video."""
        from batoolset.img import guess_dimensions
        import numpy as np
        stacks = []
        for s in flatten_iterable(self.shapes_to_draw):
            img = getattr(s, 'img', None)
            if not isinstance(img, np.ndarray):
                continue
            dims = guess_dimensions(img)
            if dims and 't' in dims:
                stacks.append((s, dims, img.shape[dims.index('t')]))
        return stacks

    @staticmethod
    def _video_fps(shapes, default=25.0):
        """Frame rate of the first of *shapes* whose image records one, else *default*."""
        for s in shapes:
            meta = getattr(getattr(s, 'img', None), 'metadata', None)
            if meta and meta.get('fps'):
                return float(meta['fps'])
        return default

    @staticmethod
    def _show_stack_frame(s, dims, frame_idx):
        """Make the time-stack panel *s* (axes *dims*) show frame *frame_idx*
        (the first index of any other extra axis, no projection)."""
        lead = dims[:dims.index('h')]  # extra dims before H, e.g. 't' or 'td'
        s.projection = None
        s.dimensions = {'order': dims, 'values': [frame_idx if L == 't' else 0 for L in lead]}
        s.update_qimage()

    def _render_current_frame_to_array(self, size, scaling_factor_dpi, bg_color):
        """Render the figure at its current per-panel frame state into an
        (H, W, 3) uint8 RGB array. Mirrors the raster branch of save()."""
        import numpy as np
        image = QImage(size, QImage.Format_RGBA8888)
        image.fill(QColor(*bg_color))  # opaque background (videos have no alpha)
        painter = QPainter(image)
        bounds = self.updateBounds()
        painter.translate(-bounds.x() * scaling_factor_dpi,
                          -bounds.y() * scaling_factor_dpi)
        painter.scale(scaling_factor_dpi, scaling_factor_dpi)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)      # also forces the display cache to be bypassed
        painter.setRenderHint(QPainter.TextAntialiasing)
        fig_images = [s for s in flatten_iterable(self.shapes_to_draw) if hasattr(s, 'enter_export_mode')]
        try:
            for im in fig_images:
                im.enter_export_mode()
            self.paint(painter)
        finally:
            painter.end()
            for im in fig_images:
                im.exit_export_mode()
        ptr = image.bits()
        try:
            ptr.setsize(image.sizeInBytes())
        except Exception:
            ptr.setsize(image.byteCount())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(image.height(), image.width(), 4)
        return np.ascontiguousarray(arr[..., :3])  # RGB

    def save_video(self, path, fps=None, frame_mode='freeze', bg_color=(0, 0, 0), dpi=72, progress_cb=None):
        """Export the figure as a movie by sweeping the time axis across all
        video / time-stack panels.

        frame_mode: 'freeze' → panels shorter than the longest hold their last
        frame; 'blank' → they show a solid *bg_color* frame once exhausted.
        *dpi* fixes the output resolution (72 = native 1:1 pixels; no interactive
        prompt — unlike still-image export videos render at screen resolution).
        Returns the number of frames written, or 0 if the figure has no time-stack.
        Static (non-video) panels are drawn identically in every frame.
        """
        self.wait_for_pending_images()
        from batoolset.img import write_video
        import numpy as np

        stacks = self._collect_time_stacks()
        if not stacks:
            return 0
        n_frames = max(tc for _, _, tc in stacks)

        if fps is None:
            fps = self._video_fps([s for s, _, _ in stacks])

        # fixed canvas size (layout is identical across frames); no DPI prompt for video
        scaling_factor_dpi = scaling_factor_to_achieve_DPI(dpi)
        img_bounds = self.updateBounds()
        w = int(round(img_bounds.width() * scaling_factor_dpi))
        h = int(round(img_bounds.height() * scaling_factor_dpi))
        w -= w % 2  # even dimensions keep every codec happy
        h -= h % 2
        size = QSize(max(2, w), max(2, h))

        # remember and restore each panel's frame/projection state
        originals = [(s, getattr(s, 'dimensions', None), getattr(s, 'projection', None)) for s, _, _ in stacks]
        frames = []
        try:
            for i in range(n_frames):
                for (s, dims, tc) in stacks:
                    blank = frame_mode == 'blank' and i >= tc
                    frame_idx = i if i < tc else tc - 1
                    self._show_stack_frame(s, dims, frame_idx)
                    if blank and s.qimage is not None:
                        solid = QImage(s.qimage.size(), s.qimage.format())
                        solid.fill(QColor(*bg_color))
                        s.qimage = solid
                frames.append(self._render_current_frame_to_array(size, scaling_factor_dpi, bg_color))
                if progress_cb is not None:
                    progress_cb(i + 1, n_frames)
        finally:
            for (s, orig_dims, orig_proj) in originals:
                s.dimensions = orig_dims
                s.projection = orig_proj
                s.update_qimage()
            self.update()

        write_video(np.stack(frames, axis=0), path, fps=fps, dimensions='thwc')
        return n_frames

    # make it sticky and allow restore or not on drag failed and depending on the mode used
    def sticky(self, mode):
        if not self.is_sticky:
            return
        if mode == 'INIT':
            # store coords of objects and reintegrate them
            self._stored_shape_n_its_coords = {}
            if self.selected_shape is not None:
                if isinstance(self.selected_shape, list):
                    for shp in self.selected_shape:
                        self._stored_shape_n_its_coords[shp] = shp.topLeft()
                else:
                    # cannot be added because unhashable... -> how can I do that
                    self._stored_shape_n_its_coords[self.selected_shape] = self.selected_shape.topLeft()
        else:
            # restore coords
            if self._stored_shape_n_its_coords:
                # restore coords of selection
                for shp, pos in self._stored_shape_n_its_coords.items():
                    shp.setTopLeft(pos)
                # update
                self.update()
                self.update_size()
        # print('bob')

    def _paint_page_background(self, painter):
        """Fill the figure's area (all panels + the gaps between them) with the
        figure background colour, if one is set."""
        bg = getattr(self, 'page_background', None)
        if bg is None or not self.shapes_to_draw:
            return
        rect = QRectF()
        for shape in self.shapes_to_draw:
            try:
                rect = rect.united(shape.getRect(all=True))
            except Exception:
                traceback.print_exc()
        if not rect.isEmpty():
            painter.fillRect(rect, QColor(int(bg) & 0xFFFFFF))

    def paint(self, painter):
        painter.save()
        self._paint_page_background(painter)
        for shape in self.shapes_to_draw:
            shape.draw(painter)
        painter.restore()

    # ------------------------------------------------------------------
    # LaTeX ("PDF + LaTeX") export — Inkscape-style: graphics as a vector
    # image with the text overlaid by LaTeX, so labels use the document's
    # fonts and real math ($\alpha$, subscripts, equations). Popular with
    # physicists. The graphics export contains no text; the .*_tex file is
    # \input into the paper and typesets the labels on top.
    # ------------------------------------------------------------------

    def _all_text_annotations(self):
        """Collect every TAText2D label across the figure (annotations on images,
        recursing through groups, plus any standalone text)."""
        from batoolset.drawings.shapes.txt2d import TAText2D
        out = []

        def rec(node):
            content = getattr(node, 'content', None)
            if content:
                for c in content:
                    rec(c)
            anns = getattr(node, 'annotations', None)
            if anns:
                for a in anns:
                    if isinstance(a, TAText2D):
                        out.append(a)
                        continue
                    # scale-bar legends are typeset by LaTeX too
                    legend = getattr(a, 'legend', None)
                    if isinstance(legend, TAText2D):
                        out.append(legend)
            if isinstance(node, TAText2D):
                out.append(node)

        for s in self.shapes_to_draw:
            rec(s)
        return out

    @staticmethod
    def _latex_escape(seg):
        repl = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '#': r'\#',
                '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
                '^': r'\textasciicircum{}', '$': r'\$'}
        return ''.join(repl.get(ch, ch) for ch in seg)

    @classmethod
    def _label_text_to_latex(cls, text):
        """Convert a run of plain text to LaTeX, preserving $...$ math verbatim
        and escaping LaTeX specials everywhere else. Unbalanced $ → treat as
        plain. Soft/hard line breaks inside a run become \\\\."""
        text = text.replace('\r\n', '\n').replace(' ', '\n').replace('\n', r' \\ ')
        if text.count('$') % 2 != 0:
            return cls._latex_escape(text)
        parts = text.split('$')
        out = []
        for i, p in enumerate(parts):
            out.append('$' + p + '$' if i % 2 == 1 else cls._latex_escape(p))
        return ''.join(out)

    @staticmethod
    def _qt_enum(owner, *names):
        """Resolve a Qt enum value across PyQt5/PyQt6 (scoped vs unscoped)."""
        for n in names:
            cur = owner
            ok = True
            for part in n.split('.'):
                cur = getattr(cur, part, None)
                if cur is None:
                    ok = False
                    break
            if ok:
                return cur
        return None

    @classmethod
    def _run_to_latex(cls, text, fmt):
        """LaTeX for one text fragment, wrapping its char format: super/subscript,
        italic, underline, bold and per-run colour (nested innermost→outermost)."""
        from qtpy.QtGui import QFont, QTextCharFormat
        from qtpy.QtCore import Qt
        inner = cls._label_text_to_latex(text)

        SUP = cls._qt_enum(QTextCharFormat, 'VerticalAlignment.AlignSuperScript',
                           'AlignSuperScript')
        SUB = cls._qt_enum(QTextCharFormat, 'VerticalAlignment.AlignSubScript',
                           'AlignSubScript')
        va = fmt.verticalAlignment()
        if SUP is not None and va == SUP:
            inner = r'\textsuperscript{' + inner + '}'
        elif SUB is not None and va == SUB:
            inner = r'\textsubscript{' + inner + '}'

        if fmt.fontItalic():
            inner = r'\textit{' + inner + '}'
        if fmt.fontUnderline():
            inner = r'\underline{' + inner + '}'
        bold_w = cls._qt_enum(QFont, 'Weight.Bold', 'Bold') or 75
        if fmt.fontWeight() >= bold_w:
            inner = r'\textbf{' + inner + '}'

        brush = fmt.foreground()
        no_brush = cls._qt_enum(Qt, 'BrushStyle.NoBrush', 'NoBrush')
        has_col = True
        try:
            has_col = brush.style() != no_brush
        except Exception:
            pass
        if has_col:
            c = brush.color()
            r, g, b = c.redF(), c.greenF(), c.blueF()
            if (round(r, 3), round(g, 3), round(b, 3)) != (0.0, 0.0, 0.0):
                inner = f'\\textcolor[rgb]{{{r:.3f},{g:.3f},{b:.3f}}}{{{inner}}}'
        return inner

    @classmethod
    def _annotation_to_latex(cls, ann):
        """Walk a label's QTextDocument and emit LaTeX preserving inline rich
        formatting (bold/italic/underline/super/subscript/per-run colour) and
        paragraph breaks. Multi-line labels are wrapped in a left \\shortstack.
        Returns '' for an empty label. Falls back to plain-text on any error."""
        doc = getattr(ann, 'doc', None)
        if doc is None:
            return ''
        try:
            lines = []
            block = doc.begin()
            while block.isValid():
                runs = []
                it = block.begin()
                while not it.atEnd():
                    frag = it.fragment()
                    if frag.isValid():
                        txt = frag.text()
                        if txt:
                            runs.append(cls._run_to_latex(txt, frag.charFormat()))
                    it += 1
                lines.append(''.join(runs))
                if block == doc.lastBlock():
                    break
                block = block.next()
            while lines and lines[-1].strip() == '':
                lines.pop()
            if not any(l.strip() for l in lines):
                return ''
            if len(lines) > 1:
                return r'\shortstack[l]{' + r' \\ '.join(lines) + '}'
            return lines[0]
        except Exception:
            try:
                return cls._label_text_to_latex(doc.toPlainText().strip())
            except Exception:
                return ''

    def save_latex(self, path, image_format='pdf', caption=None, caption_title=None):
        """Export as 'PDF + LaTeX': a vector graphics file with no text plus an
        \\input-able .<fmt>_tex overlay that typesets the labels via LaTeX.

        In the paper::  \\def\\svgwidth{\\columnwidth}\\input{figure.pdf_tex}
        (requires \\usepackage{graphicx,color}). Returns (graphics_path, tex_path).

        If *caption* is given (plain text, e.g. from the .caption.json sidecar),
        the picture is wrapped in a ``figure`` float and a ``\\caption{...}`` is
        emitted below it (LaTeX auto-numbers "Figure N:"). *caption_title*, if
        given, is prepended in bold — ``\\caption{\\textbf{Title.} caption}``.
        Without a caption the output stays a bare picture group (unchanged).
        """
        import os as _os
        self.wait_for_pending_images()
        stem = _os.path.splitext(path)[0]
        image_format = image_format.lower().lstrip('.')
        img_path = f"{stem}.{image_format}"
        tex_path = f"{img_path}_tex"

        anns = self._all_text_annotations()
        # hide text so the graphics file carries none; positions are still resolved
        # during the render (draw_annotations places each label before drawing it)
        for a in anns:
            a._latex_hide = True
        try:
            self.save(img_path)
        finally:
            for a in anns:
                a._latex_hide = False

        bounds = self.updateBounds()
        W = float(bounds.width()) or 1.0
        H = float(bounds.height()) or 1.0
        X0 = float(bounds.x())
        Y0 = float(bounds.y())
        h_ratio = H / W
        img_name = _os.path.basename(img_path)

        puts = []
        for a in anns:
            # full inline fidelity: bold/italic/underline/super-subscript/colour
            latex = self._annotation_to_latex(a)
            if not latex:
                continue
            if getattr(a, 'is_letter', False) and r'\textbf{' not in latex:
                latex = r'\textbf{' + latex + '}'
            x = (a.x() - X0) / W
            y = (H - (a.y() - Y0)) / W  # picture y is measured from the bottom
            puts.append(
                f"    \\put({x:.4f},{y:.4f}){{"
                f"\\makebox(0,0)[lt]{{\\smash{{{latex}}}}}}}%"
            )

        tex = (
            "%% PyFigures 'PDF + LaTeX' export.\n"
            f"%% Include in your document with:  \\def\\svgwidth{{\\columnwidth}}\\input{{{img_name}_tex}}\n"
            "%% Requires: \\usepackage{graphicx,color}\n"
            "\\begingroup%\n"
            "  \\makeatletter%\n"
            "  \\providecommand\\color[2][]{%\n"
            "    \\GenericError{(pyfigures) \\space\\space\\space\\@spaces}{Package color/xcolor not loaded}{}{}%\n"
            "    \\renewcommand\\color[2][]{}%\n"
            "  }%\n"
            "  \\providecommand\\rotatebox[2]{#2}%\n"
            "  \\ifx\\svgwidth\\undefined%\n"
            f"    \\setlength{{\\unitlength}}{{{W:.4f}bp}}%\n"
            "  \\else%\n"
            "    \\setlength{\\unitlength}{\\svgwidth}%\n"
            "  \\fi%\n"
            "  \\global\\let\\svgwidth\\undefined%\n"
            "  \\makeatother%\n"
            f"  \\begin{{picture}}(1,{h_ratio:.4f})%\n"
            f"    \\put(0,0){{\\includegraphics[width=\\unitlength,page=1]{{{img_name}}}}}%\n"
            + ("\n".join(puts) + "\n" if puts else "")
            + "  \\end{picture}%\n"
            "\\endgroup%\n"
        )
        if caption:
            cap = self._latex_escape(caption.replace('\r\n', '\n').strip())
            if caption_title:
                cap = r'\textbf{' + self._latex_escape(caption_title.strip()) + '} ' + cap
            tex = (
                "%% Requires additionally: \\usepackage{graphicx,color} inside a document.\n"
                "\\begin{figure}[htbp]%\n"
                "  \\centering%\n"
                + tex
                + f"  \\caption{{{cap}}}%\n"
                "\\end{figure}%\n"
            )
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(tex)
        return img_path, tex_path

    def update_size(self, mouse_pos=None):
        # if not self.resizable:
        #     return
        bounds = self.updateBounds()


        # if there is a selected shape I also need to further extend the drawing to outside of the selection or at least to the mouse position
        # print(bounds)
        extra_size = 100 # 2
        try:
            size = QSize(int((bounds.x()+bounds.width() + extra_size)*self.scale), int((bounds.y()+bounds.height()  + extra_size)*self.scale))
        except Exception:
            # print('NO CLUE WHY I SHOULD DO THAT --> MOST LIKELY REQUIRES A FIX !!!', self.scale, bounds) # the bug is there --< the scale tends to be infinite for vertical text
            # size = QSize(int(bounds.width() + extra_size), int(bounds.height() + extra_size))
            size = QSize(30000,30000)

        if self.bounds:
            size = QSize(int(max((self.bounds.width() + extra_size)*self.scale, size.width())),int(max((self.bounds.height() + extra_size)*self.scale, size.height())))

        if size.width()<500 or size.height()<500:
            # we set a minimum canvas/ruler size to avoid issues
            size =QSize(max(size.width(),500),max(size.height(),500))


        if mouse_pos is not None:
            # MEGA TODO do that better with the bounds of the selection if provided --> because that is the only reallly clean way of doing that --> THIS IS NOT PERFECT BUT MUCH BETTER ALREADY AND SUFFICIENT FOR NOW I COULD ALSO PASS A SHAPE INSTEAD OF MOUSE POS OR A LIST OF SHAPES AND UPDATE THE SIZE ACCORDINGLY BASED ON THE BOUNDINGS OF THE SHAPE
            if mouse_pos.x()>size.width():
                size.setWidth(int(mouse_pos.x()+self._EXTRA_PADDING))
            if mouse_pos.y()>size.height():
                size.setHeight(int(mouse_pos.y()+self._EXTRA_PADDING))

        self.resize(size)

    # in fact upon
    # do not override this because it's needed actually
    def updateBounds(self):
        return get_master_bounds2(self.shapes_to_draw)
        # # loop over shape to get bounds to be able to draw an image
        # bounds = QRectF()
        # max_width = 0
        # max_height = 0
        # for shape in self.shapes_to_draw:
        #    rect = shape.boundingRect()
        #    max_width = max(max_width, rect.x()+rect.width())
        #    max_height = max(max_height, rect.y()+rect.height())
        # bounds.setWidth(max_width)
        # bounds.setHeight(max_height)
        #
        #
        # # print(bounds.width())
        # # width = self.image.size().width()
        # # height = self.image.size().height()
        # # top = self.geometry().x()
        # # left = self.geometry().y()
        # # self.setGeometry(top, left, width*self.scale, height*self.scale)
        # # self.setGeometry(top, left, max_width*self.scale, max_height*self.scale)
        #
        # # looks like I have a big bug
        # # en fait la geom c'est nul vaudrait mieux changer la size ???
        # # or maybe put it as fixed size --> think about it but no big deal
        # # but need also implement scale
        #
        # # in fact whenever I add an element to it I need to call this function --> so I need to go through a function and not access the set of objects directly
        # # self.setGeometry(top, left, max_width*10, max_height*10) # TODO implement scale # very dirty hack but allows to have the complete image be drawn --> see the proper way to do that but I guess I should fit the max of the scrollarea visible region or content and set it to that # VERY DIRTY BUT OK FOR NOW MEGA TODO IMPROVE THAT
        # # self.setMinimumWidth(max_width)
        # # self.setMinimumWidth(max_height)
        #
        # # how can I update this when the user is scrolling or changing the panel size
        # # maybe the size of this stuff should be that of scrollarea if visible region is bigger --> TODO
        #
        # # becomes 0 --> why ???
        # # print(top, left, left-max_width, top-max_height)
        # # print(self.geometry())
        #
        # # need also connect it to the scrollable --> TODO
        #
        # return bounds

    # def is_ctrl_modifier(self):
    #     modifier = self.get_modifier()
    #     # if modifiers == (getCtrlModifier() |
    #     #               Qt.ShiftModifier):
    #     # if modifiers == Qt.ShiftModifier:
    #     if modifier == getCtrlModifier() or modifier == Qt.MetaModifier:
    #         return True
    #     return False

    # def get_modifier(self):
    #     modifiers = QApplication.keyboardModifiers()
    #     return modifiers

    def can_swap(self, obj1, obj2, parent_of_obj1=None, parent_of_obj2=None):
        # Check if both objects are of the same type
        if type(obj1) != type(obj2): # in fcat that makes things simpler because within the same object they can easily be exchanged
            return False

        # Check if the two objects are not the same
        if obj1 == obj2:
            return False

        # if parent_of_obj1 is None:
        #     parent_of_obj1 = get_parent_of_obj(obj1, self.shapes_to_draw)
        # if parent_of_obj2 is None:
        #     parent_of_obj2 = get_parent_of_obj(obj2, self.shapes_to_draw)

        # print('parents', parent_of_obj1, parent_of_obj2)

        # Check if both objects have the same parent
        # if parent_of_obj1 != parent_of_obj2:
        #     return False

        # If all checks pass, the objects can be swapped
        return True

    # def append(self, item1, item2):
    #     print('append called with', item1, item2)

    def extend(self, item1, item2):
        # print('extend called with', item1, item2)

        # if isinstance(self.selected_shape, Group) or isinstance(self.selected_shape, Image2D):
        # print('====dragged object is a group -−> offer swap with another group or add to another group')
        # print('group of sel', top_parent_of_sel, 'group of dest', top_parent_of_drop_target)

        # will only work for group (and not image2D or alike) otherwise will need to create a shape -−> MEGA TODO
        item2.extend(item1)

        # we remove the drawn shape from all
        # that is working --> the hard stuff is that I need to remove properly the stuff from parent except there and also from main list
        try:
            self.shapes_to_draw.remove(item1)
        except Exception:
            pass
        # remove selected shape from all but the drop target
        if True:
            for shape in self.shapes_to_draw:
                try:
                    if shape == item1:
                        continue
                    if shape == item2:
                        continue
                    shape.remove(item1)
                    # TODO --> update shape
                    shape.update()
                except Exception:
                    pass
        self.selected_shape = None  # reset sel

        item2.update()
        self.force_update_size_of_parent.emit(item2)
        self.update_letters_required.emit()
        self.update_text_rows.emit()
        self.undo_redo_save_required.emit()



        self.update()
        self.update_size()

    def swap(self, item1, item2, immediate_parent_of_sel, top_parent_of_sel, top_parent_of_drop_target):
        # print('SWAP'*20)
        # print('swap called with', item1, '-', item2, immediate_parent_of_sel, top_parent_of_sel, top_parent_of_drop_target) # un groupe et un groupe et une image
        # print('top parents', top_parent_of_sel, '-', top_parent_of_drop_target) # there is sometimes a bug in the parents --> I must have made a mistake

        # --> indeed it is when swap 2 images is called --> do i have a bug

        # top parents Image2D-0x7f3c4a8d3f40-10.png - Image2D-0x7f3c4a8d3f40-10.png -−> how can both parents be the same whereas I do not drag the same thing -−> it seems to coincide with swap two images
        # swap called with Image2D-0x7f3c4a8d3df0-09.png - Image2D-0x7f3c4a8d3f40-10.png
        # print('immediate parent of sel', immediate_parent_of_sel)

        # immediate_parent_of_sel = get_parent_of_obj(self.selected_shape, top_parent_of_sel)
        # now loop to get all the parents of top_parent_of_drop_target
        # if is_iterable(item2):
        #     for itm in item2:
        #         print('immediate parents of drop', get_parent_of_obj(itm, top_parent_of_drop_target))
        # else:
        #     print('immediate parents of drop', get_parent_of_obj(item2, top_parent_of_drop_target))

        # now I have all the players so I just have to do the swap:

        # very good I now have all the players so just make sure to make something meaningful with that
        # if parent is None that means the object is itself a top parent --> which I may need to use
        # shall I pop up a second window too or not ???
        # think about it!!!

        # see how I can offer swaps

        # if isinstance(item1, Image2D) and isinstance(item2, Image2D)
        # if both are top parents --> offer direct swap then update
        if (item2 == top_parent_of_drop_target or len(item2)==1 and item2[0]==top_parent_of_drop_target) and item1 == top_parent_of_sel:

            # print('inside swapping 1')
            # directly swap from the main list
            idx1 = self.shapes_to_draw.index(top_parent_of_sel)
            idx2 = self.shapes_to_draw.index(top_parent_of_drop_target)
            swap_items(self.shapes_to_draw, idx1, idx2)
        elif item2 == top_parent_of_drop_target  and item1==top_parent_of_sel:
            # print('inside swapping 2')
            idx1 = self.shapes_to_draw.index(top_parent_of_sel)
            idx2 = self.shapes_to_draw.index(top_parent_of_drop_target)
            swap_items(self.shapes_to_draw, idx1, idx2)
        elif is_iterable(item2) and item2[0] == top_parent_of_drop_target and item1 == top_parent_of_sel: # dirty trick to swap two rows --> best is to create all the possible combintaions right at the start
            # print('inside swapping 3')
            idx1 = self.shapes_to_draw.index(top_parent_of_sel)
            idx2 = self.shapes_to_draw.index(top_parent_of_drop_target)
            swap_items(self.shapes_to_draw, idx1, idx2)
        # elif top_parent_of_sel == top_parent_of_drop_target and isinstance(top_parent_of_sel, Group):
        #     idx1 = top_parent_of_sel.content.index(item1)
        #     idx2 = top_parent_of_sel.content.index(item2)
        #     swap_items(top_parent_of_sel.content, idx1, idx2)
        else:
            # print('swap failed', item1, '-', item2, immediate_parent_of_sel, top_parent_of_sel, top_parent_of_drop_target)
            self.informative_message_required.emit('swap failed' +str(item1)+ '-'+str(item2)+ ' '+ str(immediate_parent_of_sel) +' '+ str(top_parent_of_sel) +' '+ str(top_parent_of_drop_target))

            # see all the possible swaps

        # I need to detect and offer all the possible swaps

        self.set_current_selection(None)
        self.update_size()
        self.update()

        # print('TODO IMPLEMENT SWAP IN A SIMPLER MANNER ') # just by getting the top parent of various shapes involved
        # print('END-SWAP' * 10)
        # now try to determine the swap possibility precisely
        # this is an internal stuff --> so determine the two involved elements

        # see which items can be swapped and proceed

        # do it generic --> in fact I need to find the parent and top parent of the involved stuff and to preform the swap and then to update the parent then to update all
        # TODO

        if False:
             # old code --> too complex --> fix

            full_list_of_encounters = list(all_encounters_in_shape_below_mouse)

            print('TADADAD', full_list_of_encounters, all_encounters_in_shape_below_mouse)

            try:
                all_encounters_in_shape_below_mouse.remove(self.selected_shape)
            except Exception:
                pass
            try:
                all_encounters_in_shape_below_mouse.remove(top_parent_of_sel)
            except Exception:
                pass
            print('offer swapping', self.selected_shape, 'with', all_encounters_in_shape_below_mouse)
            # get just the two and implement it --> see how to implement swap

            found_image_for_swap = None

            if all_encounters_in_shape_below_mouse:
                for elm in all_encounters_in_shape_below_mouse:
                    # if type(elm)==type()
                    print('offer swap ', self.selected_shape, 'with', elm)
                    found_image_for_swap = elm

            if found_image_for_swap is not None:

                # this is super hard --> start with additions

                print('proceed to swapping of ', self.selected_shape, 'and', found_image_for_swap)

                # this is really tough in fact because it swaps images and in some cases it may be necessary to swap an image with a group --> I should at least offer it
                # --> see how to do that --> maybe get all the possible lists not the first encounter only and offer all possibilities !!! --> TODO

                lst1 = self.get_direct_parent_containing_element(full_list_of_encounters, self.selected_shape)
                lst2 = self.get_direct_parent_containing_element(full_list_of_encounters, found_image_for_swap)

                print('final lists', lst1, lst2, 'vs', full_list_of_encounters)

                if lst1 and lst2:

                    if len(lst1) == 1:
                        lst1 = lst1[0]
                    if len(lst2) == 1:
                        lst2 = lst2[0]

                    if isinstance(lst1, Image2D):
                        lst1 = [lst1]
                    if isinstance(lst2, Image2D):
                        lst2 = [lst2]

                    topleft1 = self.selected_shape.topLeft()
                    topleft2 = found_image_for_swap.topLeft()
                    self.selected_shape.setTopLeft(topleft2)
                    found_image_for_swap.setTopLeft(topleft1)

                    print('before', top_parent_of_sel.content)
                    # if this is directly an image2D that will not work
                    idx1 = lst1.index(self.selected_shape)
                    idx2 = lst2.index(found_image_for_swap)
                    # temp = self.selected_shape
                    lst1[idx1] = found_image_for_swap
                    lst2[idx2] = self.selected_shape

                    print('after', top_parent_of_sel.content)

                    # MEGA TODO FIX BUG OF IMAGE OUTSIDE A GROUP THAT IS DIRECTLY ADDED TO THE SHAPE AND I ALSO NEED TO REMOVE IT

                top_parent_of_sel.update()
                self.update_size()
                self.update()

    def duplicate(self, selection=None):

        # print('I am called', selection)

        if selection is None or selection is False:
            selection = self.selected_shape


        # print(' now sel', selection)

        if selection:
            # TODO -−> do a clone of all
            # --> go through xml copy of the stuff then do
            # print('CTrl+D called ACTION REQUIRED !!!')
            copies = []
            sel = selection

            if not isinstance(sel, list):
                sel = [sel]

            # print('inside sel')

            for elm in sel:
                copies.append(clone_object(elm))
                # self.shapes_to_draw.append(elm)
                self.force_update_size_of_parent.emit(copies[-1])
                # self.update()

            self.shapes_to_draw.extend(copies)
            # self.update_size()
            self.update()

            self.set_current_selection(copies[-1])

            self.update_letters_required.emit()
            self.update_text_rows.emit()
            self.focus_required.emit()
            self.set_current_selection(copies[-1]) # somehow removing sel is required otherwise weird move

            self.update_size()
            self.update() # for unclear reason the dual update is required in duplication
            self.undo_redo_save_required.emit()


            self.informative_message_required.emit("Duplication successful")
        else:
            self.informative_message_required.emit("<font color=#FF0000>Please select something you want to copy/duplicate</font>")

    def add(self, item1, item2):
        # print('add add with', item1, item2)

        # if isinstance(self.selected_shape, Group) or isinstance(self.selected_shape, Image2D):
        #     print('====dragged object is a group -−> offer swap with another group or add to another group')
            # print('group of sel', top_parent_of_sel, 'group of dest', top_parent_of_drop_target)

            # will only work for group (and not image2D or alike) otherwise will need to create a shape -−> MEGA TODO
            item2.add(item1)

            # we remove the drawn shape from all
            # that is working --> the hard stuff is that I need to remove properly the stuff from parent except there and also from main list
            try:
                self.shapes_to_draw.remove(item1)
            except Exception:
                pass


            # remove selected shape from all but the drop target
            if True:
                for shape in self.shapes_to_draw:
                    try:
                        if shape == item1:
                            continue
                        if shape == item2:
                            continue
                        shape.remove(item1)
                        # TODO --> update shape
                        shape.update()
                    except Exception:
                        pass


            self.selected_shape = None  # reset sel

            item2.update()
            self.force_update_size_of_parent.emit(item2)
            self.update_letters_required.emit()
            self.update_text_rows.emit()
            self.undo_redo_save_required.emit()

            self.update()
            self.update_size()

    def _create_group_with(self, item1, item2, orientation='X'):
        # see when I create a new group and when I simply add to the existing row -> if a single image is added then just append
        # if item1 is a group and has the same orientation as desired --> just add to it -−> TODO


        current_space_of_new_group = 3
        # hack in order not to create subgroups if they are not necessary  # this makes it redundant to have add or extend to a group then
        content_merge = []
        if isinstance(item1, Group) and item1.orientation == orientation and item1.space == current_space_of_new_group: # if rows to merge have same orientation and space then dissociate them and regroup them (that should work as the user intends in most cases)
            content_merge.extend(item1.content)
        else:
            content_merge.append(item1)
        if isinstance(item2, Group) and item2.orientation == orientation and item2.space == current_space_of_new_group:
            content_merge.extend(item2.content)
        else:
            content_merge.append(item2)

        # new_grp = Group(item1, item2, orientation=orientation)
        new_grp = Group(*content_merge, orientation=orientation)

        # Remember where to drop the new group: at the position of the drop target
        # (item1) so the merged row/column stays where the user dropped it instead
        # of jumping to the end of the figure. Captured BEFORE any removal.
        original_order = list(self.shapes_to_draw)
        ref = item1 if item1 in original_order else (item2 if item2 in original_order else None)

        self.set_current_selection(None)
        try:
            self.shapes_to_draw.remove(item1)
        except Exception:
            pass
        try:
            self.shapes_to_draw.remove(item2)
        except Exception:
            pass
        try:
            top_parent = self.get_top_parent_of_shape(item1)
            if top_parent is not None:
                top_parent.remove(item1)
                top_parent.update()
        except Exception:
            pass
        try:
            top_parent = self.get_top_parent_of_shape(item2)
            if top_parent is not None:
                top_parent.remove(item2)
                top_parent.update()
        except Exception:
            pass

        # marche presque mais faut que je focus dessus et que je la mette à la bonne taille
        # if single image shall I unpack it ??? --> maybe yes TODO
        if ref is not None:
            # insert at the slot the drop target occupied, relative to the shapes
            # that are still on the canvas (handles the dragged item being before
            # or after the target)
            ref_pos = original_order.index(ref)
            insert_index = sum(1 for s in self.shapes_to_draw
                               if s in original_order and original_order.index(s) < ref_pos)
            self.shapes_to_draw.insert(insert_index, new_grp)
        else:
            self.shapes_to_draw.append(new_grp)  # and I need to remove both items from any potential parent
        self.update()
        self.update_size()

        self.force_update_size_of_parent.emit(new_grp)
        self.set_current_selection(new_grp)
        self.focus_required.emit()

        self.update_letters_required.emit()
        self.set_current_selection(new_grp)
        self.undo_redo_save_required.emit()

    def create_row_with(self, item1, item2):
        # print('create_row_with add with', item1, item2, 'TODO IMPLEMENT THAT --> # TODO --> call the parent Combine horizontally (Row)') # -−> see how to do I could pass the parent in init and call the method or copy the code of the parent here ??? -−> at least try to gather all the functions to make it simpler to use!
        self._create_group_with(item1, item2, orientation='X')

    def create_col_with(self, item1, item2):
        # print('create_col_with add with', item1, item2, ' --> # TODO --> call the parent Combine vertically (Col)') # TODO --> do implement it because not so easy
        self._create_group_with(item1, item2, orientation='Y')

    def extrude(self, item1, top_parent_of_sel):
        # print('extrude with', item1, top_parent_of_sel)

        if top_parent_of_sel != item1:
            top_parent_of_sel.remove(item1)
            self.shapes_to_draw.append(item1)
            # I need update both shapes maybe to a given size --> see how I can do that and do that

            # try:
            #     set_to_size(top_parent_of_sel, top_parent_of_sel.width() if top_parent_of_sel.orientation=='X' else top_parent_of_sel.height())
            # except:
            #     print('just for info for now, comment that lines in the future')
            #     traceback.print_exc()
            #     print('just for info for now, comment that lines in the future')
            #     pass
            # self.update_size()

            # I would need a packing in Y to do things properly depending on the mode

            # TODO --> THERE IS A BIG BUG --> SIZE OF SOME ELEMENTS IS INCORRECT

            if top_parent_of_sel.isEmpty():
                self.shapes_to_draw.remove(top_parent_of_sel)
                top_parent_of_sel = None


            self.force_update_size_of_parent.emit(item1)
            if top_parent_of_sel:
                self.force_update_size_of_parent.emit(top_parent_of_sel)

            self.update_size()
            self.update()  # somehow size or bounds is completely nuts here -−> try to see why

            self.set_current_selection(item1)

            self.update_letters_required.emit()
            self.update_text_rows.emit()
            self.undo_redo_save_required.emit()
            self.set_current_selection(item1)
            self.focus_required.emit()

    def image_context_menu(self,menu=None, event=None):

        is_left_click=True
        if event is not None:
            if event.button()==Qt.RightButton:
                is_left_click=False

        if menu is None:
            self.contextMenu = QMenu(self)
            ignore = self.contextMenu.addAction("Ignore")
            # Add a separator


            if not is_left_click:
                self.contextMenu.addSeparator()

                duplicate = self.contextMenu.addAction("Duplicate Selection")
                duplicate.triggered.connect(self.duplicate)


                if isinstance(self.selected_shape, Image2D) and not is_left_click:
                    # if self.selected_shape.isText:
                    #
                    # else:
                        self.contextMenu.addSeparator()
                        edit_image = self.contextMenu.addAction("Edit Image") # do same as mouse double click
                        edit_image.triggered.connect(lambda:self.update_image_annotations(image2d=self.selected_shape))


        else:
            self.contextMenu = menu
            if isinstance(self.selected_shape, Image2D) and not is_left_click:
                # if self.selected_shape.isText:
                #
                # else:
                self.contextMenu.addSeparator()
                edit_image = self.contextMenu.addAction("Edit Image")  # do same as mouse double click
                edit_image.triggered.connect(lambda: self.update_image_annotations(image2d=self.selected_shape))

        if not is_left_click:
            bool_has_parent = False
            guessed_dims = guess_dimensions(self.selected_shape.img)
            if guessed_dims and 'c' in guessed_dims and self.selected_shape.img.shape[-1] > 1:
                self.contextMenu.addSeparator()
                channel_split_gray = self.contextMenu.addAction("Channel split (Gray mode)")
                channel_split_gray.triggered.connect(lambda: self.split_channels(mode='gray'))
                # not very useful for two channel ones except that it does create a magenta green image
                channel_split_mg = self.contextMenu.addAction("Channel split (Magenta/Green mode)")
                channel_split_mg.triggered.connect(lambda: self.split_channels(mode='magenta'))
                bool_has_parent = True

            extra_dims = self.selected_shape.get_extra_dimensions(handle_proj=True)
            if isinstance(self.selected_shape, Image2D) and isinstance(
                self.selected_shape.img, np.ndarray) and extra_dims:
                if not bool_has_parent:
                    self.contextMenu.addSeparator()
                dim_split = self.contextMenu.addAction("Split by a dimension")
                dim_split.triggered.connect(self.run_split)

        # self.add_reset_menu()

        # self.contextMenu.addSeparator()
    def run_split(self):
        self._please_wait_dialog.show()
        QTimer.singleShot(100, lambda:self.run_slow_process(self.slow_process)) # very dirty but functional way of making the slow process dialog appear

    def slow_process(self):
        # split the image selected by the first dimension
        # print('dabu',isinstance(self.paint.EZFIG_panel.selected_shape.img, np.ndarray))

        # extra_dims = self.paint.EZFIG_panel.selected_shape.get_extra_dimensions(handle_proj=True)

        # print('bobjsdnfsndb')

        extra_dims = self.selected_shape.get_extra_dimensions(handle_proj=True)
        if extra_dims:
            guessed_dimensions = guess_dimensions(self.selected_shape.img)
            # target_dims = str(guessed_dimensions)
            if len(extra_dims) > 1:
                dim_chooser = DimensionChooser(extra_dims)

                custom_dialog = CustomDialog(title="Choose a split dimension",
                                             message=None,
                                             # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                             main_widget=dim_chooser, options=['Ok', 'Cancel'], parent=self,
                                             auto_adjust=True)
                if custom_dialog.exec_() == QDialog.Accepted:

                    letter = dim_chooser.get_current_dimension()

                    # self.paint.EZFIG_panel.shapes_to_draw.extend(split_images)
                    # self.paint.EZFIG_panel.update_letters_required.emit()

                else:
                    # nothing to do --> break
                    return
            else:
                letter = extra_dims[0]

            # letter = guessed_dimensions[0]

            size_of_dimension = self.selected_shape.img.shape[
                extra_dims.index(letter)]
            asop = AsSingleOrPanel(self, num_widgets=size_of_dimension)

            custom_dialog = CustomDialog(title="Select output layout",
                                         message=None,
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=asop, options=['Ok', 'Cancel'], parent=self,
                                         auto_adjust=True)

            if custom_dialog.exec_() != QDialog.Accepted:
                return

            split_images = []

            # can offer a split by all of these dims

            # print('size_of_dimension', size_of_dimension)

            for ddd in range(size_of_dimension):
                # clone the image and just change the parameter of the position all the rest can be kept as is
                clone = clone_object(self.selected_shape)

                hacked_dims = clone.dimensions

                # print('initial hacked_dims', hacked_dims)

                if isinstance(hacked_dims, dict):
                    idx = hacked_dims['order'].index(letter)
                    hacked_dims['values'][idx] = ddd
                else:
                    hacked_dims = {}
                    hacked_dims['order'] = guessed_dimensions
                    idx = hacked_dims['order'].index(letter)
                    values = [0 for _ in extra_dims]
                    values[idx] = ddd
                    hacked_dims['values'] = values

                # print('hacked_dims', hacked_dims)

                clone.dimensions = hacked_dims
                clone.update_qimage()

                split_images.append(clone)

            if asop.is_checkbox_selected():
                # print('(inside)', self)
                # this crashes the soft but no clue why though
                # self.shapes_to_draw.extend(split_images)


                for elm in split_images:
                    self.shapes_to_draw.append(elm)
                    self.force_update_size_of_parent.emit(elm)

                # offer the creation of a panel

                try:
                    self.set_current_selection(split_images[-1])
                    self.focus_required.emit()
                except Exception:
                    traceback.print_exc()
                    pass
                self.update_size()
                self.update()
                self.undo_redo_save_required.emit()

            else:
                # print('need build a panel')
                values = asop.panel_creator.get_values()
                self._create_panel_directly(split_images, values['num_rows'], values['num_cols'],
                                                              values['add_empty_images'], values['order'])
                # try:
                #     self.set_current_selection(split_images[-1])
                #     self.focus_required.emit()
                # except:
                #     traceback.print_exc()
                #     pass

            del split_images


    def run_slow_process(self, func):
        try:
            func()
        finally:
            self._please_wait_dialog.hide()

    def split_channels(self, mode='gray'):
        if isinstance(self.selected_shape,
                      Image2D):  # in theory the checks are useless because they have already been done before but probably still ok
            # offer split into Gray Channel split
            # offer Color-blind channel split
            # add also a

            # check if has channels otherwise ignore
            guessed_dims = guess_dimensions(self.selected_shape.img)
            if 'c' in guessed_dims and self.selected_shape.img.shape[-1] > 1:
                channels = [False for _ in range(self.selected_shape.img.shape[-1])]
                panel_clone = []
                if not 'ray' in mode:
                    luts = [None for _ in channels]
                    for ch in range(0, self.selected_shape.img.shape[-1], 2):
                        copy_channels = list(channels)
                        copy_channels[ch] = True
                        luts[ch] = 'MAGENTA'
                        try:
                            copy_channels[ch + 1] = True
                            luts[ch + 1] = 'GREEN'
                        except Exception:
                            # we are out of bonds this is expected --> forget about that!!!
                            pass
                        clone = clone_object(self.selected_shape,
                                             overrides={'channels': copy_channels, 'LUTs': luts})
                        panel_clone.append(clone)
                else:
                    for ch in range(self.selected_shape.img.shape[
                                        -1]):  # clone and only check one channel then keep all the rest intact and remove of not the LUT
                        copy_channels = list(channels)
                        copy_channels[ch] = True
                        clone = clone_object(self.selected_shape,
                                             overrides={'channels': copy_channels})
                        panel_clone.append(clone)
                panel_clone.append(clone_object(self.selected_shape))
                final_split = Group(*panel_clone, orientation='X')
                self.shapes_to_draw.append(final_split)
                self.set_current_selection(final_split)
                # , size = self.size_spinbox.value()
                self.force_update_size_of_parent.emit(final_split)

                self.focus_required.emit()
                self.update_text_rows.emit()
                self.update_letters_required.emit()

                self.set_current_selection(None)
                self.update()
                self.update_size()
                self.undo_redo_save_required.emit()

        # print('called there')

    def templatify(self, object=None, update=True):
        if object is None:
            return
        # self.templatify_figure.emit(object)
        if isinstance(object, Image2D):
            if object.filename is None:
                return
            object.filename='@template@'
            rect = object.getRect(raw=True)
            object.img = QRectF(0,0, rect.width(), rect.height())
            object.__init__(**object.to_dict())
            if object.annotations:
                for elm in reversed(object.annotations):
                    if isinstance(elm, Image2D):
                        object.annotations.remove(elm)

            if update:
                self.update()
                self.update_size()
                self.undo_redo_save_required.emit()
        else:
            # if isinstance(object, Group):
                _, full_list_of_images = self.get_full_list_ofimages2D_for_consolidation(stuff_to_consolidate=object,  include_insets=False)
                for img in full_list_of_images:
                    self.templatify(object=img, update=False)
                self.update()
                self.update_size()
                self.undo_redo_save_required.emit()


    def remove_stuff(self, type_of_stuff):
        if isinstance(self.selected_shape, Image2D):
            self._remove_stuff(self.selected_shape, type_of_stuff)
            self.finalize_and_update()
        else:
            # if isinstance(object, Group):
            _, full_list_of_images = self.get_full_list_ofimages2D_for_consolidation(stuff_to_consolidate=self.selected_shape,
                                                                                     include_insets=False, exclude_images_without_filename=False)
            for img in full_list_of_images:
                self._remove_stuff(img, type_of_stuff)
            self.finalize_and_update()

    def set_text_font_all_but_letter(self):
        # self.templatify_figure.emit(object)

        ft_dialog = FontSelector()
        custom_dialog = CustomDialog(title="Select a Font",
                                         message=None,
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=ft_dialog, options=['Ok', 'Cancel'], parent=self,
                                         auto_adjust=True)
        # if pass --> ignore
        if custom_dialog.exec_() == QDialog.Accepted:
            font= ft_dialog.get_font()
        else:
            return

        if isinstance(self.selected_shape, Image2D):
            self._set_font(self.selected_shape, font)
            self.finalize_and_update()
        else:
            # if isinstance(object, Group):
            _, full_list_of_images = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)
            for img in full_list_of_images:
                self._set_font(img, font)
            self.finalize_and_update()
            
    def set_text_bg_all_but_letter(self):
        # self.templatify_figure.emit(object)

        bg_dialog = BackgroundColorPicker(self)
        custom_dialog = CustomDialog(title="Select a background color",
                                     message=None,
                                     # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                     main_widget=bg_dialog, options=['Ok', 'Cancel'], parent=self,
                                     auto_adjust=True)
        # if pass --> ignore
        if custom_dialog.exec_() == QDialog.Accepted:
            bg = bg_dialog.get_color()
        else:
            return

        if isinstance(self.selected_shape, Image2D):
            self._set_text_bg(self.selected_shape, bg)
            self.finalize_and_update()
        else:
            # if isinstance(object, Group):
            _, full_list_of_images = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)
            for img in full_list_of_images:
                self._set_text_bg(img, bg)
            self.finalize_and_update()

    def remove_all_annotations(self):
            # self.templatify_figure.emit(object)
        if isinstance(self.selected_shape, Image2D):
            self._remove_annotations(self.selected_shape)
            self.finalize_and_update()
        else:
            # if isinstance(object, Group):
            _, full_list_of_images = self.get_full_list_ofimages2D_for_consolidation(stuff_to_consolidate=self.selected_shape,
                                                                                     include_insets=False, exclude_images_without_filename=False)
            for img in full_list_of_images:
                self._remove_annotations(img)
            self.finalize_and_update()

    def _set_text_bg(self,img, bg):
        if not isinstance(img, Image2D):
            return

        if img.annotations:
            for annot in img.annotations:
                if isinstance(annot, TAText2D):
                    if not annot.is_letter:
                        annot.fill_color = bg
    def _set_font(self,img, font):
        if not isinstance(img, Image2D):
            return
        if font is None:
            return

        if img.annotations:
            for annot in img.annotations:
                if isinstance(annot, TAText2D):
                    if not annot.is_letter:

                        # do not overwrite default bold or italic

                        # print('text font to be changed', annot, font)
                        # Create a QTextEdit widget and set its document
                        # text_edit = QTextEdit()
                        doc = annot.doc

                        # Insert some text into the document
                        cursor = QTextCursor(doc)

                        # Select all the text in the document
                        cursor.select(QTextCursor.Document)
                        char_format = QTextCharFormat()
                        # if False:
                        char_format.setFont(font)
                        # else:
                        #     char_format.setFont(clean_font)

                        cursor.mergeCharFormat(char_format)







    def _remove_stuff(self, img, type_of_stuff):



        if not isinstance(img, Image2D):
            return
        if img.isText:
            return


        if isinstance(type_of_stuff, list):
            print('removing in stuff')
            stuff=[]
            for typ in type_of_stuff:
                print('removing stuff', typ)
                tmp = find_all_objects_of_type(img.annotations, typ)
                if tmp:
                    stuff.extend(tmp)


            # we prevent removal of stuff that inherit from recatngle2D...
            stuff = [st for st in stuff if not type(st) in [ScaleBar, Image2D,TAText2D]]
        else:
            stuff = find_all_objects_of_type(img.annotations, type_of_stuff)



        if type_of_stuff == TAText2D:
            if stuff:
                if isinstance(stuff[0], TAText2D) and stuff[0].is_letter:
                    del stuff[0]

        if stuff and img.annotations:
            img.annotations = [elm for elm in img.annotations if not elm in stuff]


    def _remove_annotations(self, img):
        if not isinstance(img, Image2D):
            return
        if img.isText:
            return
        # insets = find_all_objects_of_type(img.annotations, Image2D)
        # scale_bars = find_all_objects_of_type(img.annotations, ScaleBar)
        letter = None
        try:
            letter = img.annotations[0]
            if isinstance(letter, TAText2D) and letter.is_letter:
                pass
            else:
                letter = None
        except Exception:

            pass
        img.annotations = []
        if letter is not None:
            img.annotations.append(letter)
        # if insets:
        #     img.annotations.extend(insets)
        # if scale_bars:
        #     img.annotations.extend(scale_bars)





    def internal_DND_context_menu(self, event=None, immediate_parent_of_sel=None, all_shapes_below=None, first_encounter_below=None, drop_target=None, all_encounters_in_shape_below_mouse=None, all_encounters_of_sel_shape_below_mouse=None, top_parent_of_sel=None,top_parent_of_drop_target=None):
        if False:
            print('debugging ',event, immediate_parent_of_sel, self.selected_shape, all_shapes_below, first_encounter_below,drop_target, all_encounters_in_shape_below_mouse, all_encounters_of_sel_shape_below_mouse, top_parent_of_sel, top_parent_of_drop_target)

        is_left_click = True
        if event is not None:
            if event.button()==Qt.RightButton:
                is_left_click = False

        # print('left click detected', is_left_click)

        self.reset_position()

        self.contextMenu = QMenu(self)

        # No selection — minimal menu
        if not self.selected_shape:
            self.contextMenu.addSection("Canvas")
            add_empty = self.contextMenu.addAction("Add Empty Image")
            add_empty.triggered.connect(self.on_add_empty_image_clicked)
            self.contextMenu.addSeparator()
            self.contextMenu.addAction("Ignore")
            self._run_context_menu_at_click(event)
            return None

        # ══════════════════════════════════════════════════════════════
        # RIGHT-CLICK: structured sections
        # ══════════════════════════════════════════════════════════════
        if not is_left_click:

            # ── Edit ─────────────────────────────────────────────────
            self.contextMenu.addSection("Edit")
            if isinstance(self.selected_shape, Image2D):
                if self.selected_shape.isText:
                    edit_text = self.contextMenu.addAction("Edit text")
                    edit_text.triggered.connect(lambda: self.update_image_annotations(self.selected_shape))
                else:
                    edit_image = self.contextMenu.addAction("Edit Image")
                    edit_image.triggered.connect(lambda: self.update_image_annotations(image2d=self.selected_shape))
                    from pyfigures.equations import is_equation
                    gui = self.window()
                    if is_equation(getattr(self.selected_shape, 'filename', None)) \
                            and hasattr(gui, 'edit_equation'):
                        _eq_shape = self.selected_shape
                        edit_eq = self.contextMenu.addAction("Edit equation…")
                        edit_eq.triggered.connect(lambda: gui.edit_equation(_eq_shape))
                    from pyfigures.latex_document import source_of, is_latex_code
                    if is_latex_code(getattr(self.selected_shape, 'custom_loading_script', None)) \
                            and hasattr(gui, 'edit_latex_code'):
                        _code_shape = self.selected_shape
                        edit_code = self.contextMenu.addAction("Edit LaTeX code…")
                        edit_code.triggered.connect(lambda: gui.edit_latex_code(_code_shape))
                    _fn = getattr(self.selected_shape, 'filename', None)
                    if isinstance(_fn, str) and source_of(_fn) and hasattr(gui, 'recompile_latex_panel'):
                        _doc_shape = self.selected_shape
                        recompile = self.contextMenu.addAction("Recompile from .tex")
                        recompile.setToolTip(source_of(_fn))
                        recompile.triggered.connect(lambda: gui.recompile_latex_panel(_doc_shape))
            if isinstance(top_parent_of_sel, Group) and top_parent_of_sel.isText:
                edit_text_row = self.contextMenu.addAction("Edit text row")
                edit_text_row.triggered.connect(lambda: self.edit_text_row_content(top_parent_of_sel))
                if self.check_if_context_menu_is_empty():
                    return None
                self._run_context_menu_at_click(event)
                return None
            if isinstance(self.selected_shape, Group):
                edit_grp = self.contextMenu.addAction("Edit Group (orientation/space)")
                edit_grp.triggered.connect(self.update_group_layout)

            # ── Selection ────────────────────────────────────────────
            self.contextMenu.addSection("Selection")
            add_empty = self.contextMenu.addAction("Add Empty Image")
            add_empty.triggered.connect(self.on_add_empty_image_clicked)
            duplicate = self.contextMenu.addAction("Duplicate Selection")
            duplicate.triggered.connect(partial(self.duplicate, self.selected_shape))
            convert_to_template = self.contextMenu.addAction("Convert to template")
            convert_to_template.triggered.connect(lambda: self.templatify(self.selected_shape))
            # Extrude (remove from parent group)
            _can_extrude = False
            if isinstance(self.selected_shape, (Group, list)):
                _can_extrude = True
                if isinstance(self.selected_shape, list):
                    _can_extrude = bool(find_first_object_of_type(self.selected_shape, Group))
                    if not _can_extrude:
                        for _elm in self.selected_shape:
                            _tp = self.get_top_parent_of_shape(_elm)
                            if _tp is not None and _tp != _elm:
                                _can_extrude = True
                                break
            elif isinstance(self.selected_shape, Image2D) and not self.selected_shape.isText:
                _tp = self.get_top_parent_of_shape(self.selected_shape)
                _can_extrude = _tp is not None and _tp != self.selected_shape
            if _can_extrude:
                extrude_act = self.contextMenu.addAction("Extrude (remove from group)")
                extrude_act.triggered.connect(self.all_as_single)

            # ── Arrange ──────────────────────────────────────────────
            self.contextMenu.addSection("Arrange")
            if isinstance(self.selected_shape, list):
                convert_sel_to_row = self.contextMenu.addAction("↔  To row")
                convert_sel_to_row.triggered.connect(lambda: self._add_as_new_group(self.selected_shape, orientation='X', remove_from_parents=True))
                convert_sel_to_col = self.contextMenu.addAction("↕  To column")
                convert_sel_to_col.triggered.connect(lambda: self._add_as_new_group(self.selected_shape, orientation='Y', remove_from_parents=True))
                convert_sel_to_panel = self.contextMenu.addAction("▦  To panel")
                convert_sel_to_panel.triggered.connect(lambda: self._create_panel_real(self.selected_shape))
            reorganize_sel_as_panel = self.contextMenu.addAction("Reshape to panel (if possible)")
            reorganize_sel_as_panel.triggered.connect(self.reorganize_as_panel)
            if not isinstance(self.selected_shape, Image2D):
                change_space_action = self.contextMenu.addAction("Change space between elements")
                change_space_action.triggered.connect(self.set_space)
            # Label operations — detect target (Group or standalone Image2D)
            _label_target = None
            _standalone_image = False
            if isinstance(self.selected_shape, Group) and not self.selected_shape.isText:
                _label_target = self.selected_shape
            elif isinstance(self.selected_shape, Image2D) and not self.selected_shape.isText:
                if isinstance(top_parent_of_sel, Group) and not top_parent_of_sel.isText:
                    _label_target = top_parent_of_sel   # image inside a group
                elif top_parent_of_sel is self.selected_shape:
                    _label_target = self.selected_shape  # standalone image on canvas
                    _standalone_image = True
            if _label_target is not None:
                _has_row_labels = _label_target in self.shapes_to_draw
                _has_side_labels = True
                if _has_row_labels or _has_side_labels:
                    lbl_menu = self.contextMenu.addMenu("Add labels ▶")
                    def _with_target(fn, _t=_label_target):
                        def _call():
                            orig = self.selected_shape
                            self.selected_shape = _t
                            fn()
                            if self.selected_shape is _t:  # only restore if fn didn't change selection
                                self.selected_shape = orig
                        return _call
                    if _has_row_labels:
                        add_text_row_above = lbl_menu.addAction("Above the row")
                        add_text_row_above.triggered.connect(_with_target(lambda: self.associate_text_row(sensitivity='below')))
                        add_text_row_below = lbl_menu.addAction("Below the row")
                        add_text_row_below.triggered.connect(_with_target(lambda: self.associate_text_row(sensitivity='above')))
                    if _has_side_labels:
                        if _has_row_labels:
                            lbl_menu.addSeparator()
                        add_text_label_first = lbl_menu.addAction("Left / top of row/col")
                        add_text_label_first.triggered.connect(_with_target(self.add_text_label_first))
                        add_text_label_last = lbl_menu.addAction("Right / bottom of row/col")
                        add_text_label_last.triggered.connect(_with_target(self.add_text_label_last))

            # ── Split ▶ (submenu, Image2D with channels/extra dims only) ─
            if isinstance(self.selected_shape, Image2D) and not self.selected_shape.isText:
                _guessed = guess_dimensions(self.selected_shape.img)
                _has_channels = _guessed and 'c' in _guessed and self.selected_shape.img.shape[-1] > 1
                _extra_dims = self.selected_shape.get_extra_dimensions(handle_proj=True)
                if _has_channels or _extra_dims:
                    split_menu = self.contextMenu.addMenu("Split ▶")
                    if _has_channels:
                        ch_gray = split_menu.addAction("Channel split (Gray mode)")
                        ch_gray.triggered.connect(lambda: self.split_channels(mode='gray'))
                        ch_mg = split_menu.addAction("Channel split (Magenta/Green mode)")
                        ch_mg.triggered.connect(lambda: self.split_channels(mode='magenta'))
                    if _extra_dims:
                        dim_split = split_menu.addAction("Split by a dimension")
                        dim_split.triggered.connect(self.run_split)

            if self.shapes_to_draw:
                # ── Remove annotations ▶ (submenu) ───────────────────
                rm_menu = self.contextMenu.addMenu("Remove annotations ▶")
                rm_all_annots = rm_menu.addAction("Remove all (ROIs, scale bars, texts, …)")
                rm_all_annots.triggered.connect(self.remove_all_annotations)
                rm_menu.addSeparator()
                rm_all_scale = rm_menu.addAction("Scale bars")
                rm_all_scale.triggered.connect(lambda: self.remove_stuff(type_of_stuff=ScaleBar))
                rm_all_texts = rm_menu.addAction("Texts")
                rm_all_texts.triggered.connect(lambda: self.remove_stuff(type_of_stuff=TAText2D))
                rm_all_ROIs = rm_menu.addAction("ROIs")
                rm_all_ROIs.triggered.connect(lambda: self.remove_stuff(
                    type_of_stuff=[Circle2D, Ellipse2D, Freehand2D, Line2D, Point2D, Polygon2D, PolyLine2D,
                                   Rectangle2D, Square2D]))
                rm_all_insets = rm_menu.addAction("Insets")
                rm_all_insets.triggered.connect(lambda: self.remove_stuff(type_of_stuff=Image2D))

                # ── Crop & size ▶ (submenu) ───────────────────────────
                crop_menu = self.contextMenu.addMenu("Crop & size ▶")
                crop_menu.addSection("Match first image")
                all_same_wh = crop_menu.addAction("Force same width and height")
                all_same_wh.triggered.connect(self.same_width_and_height)
                all_same_ar = crop_menu.addAction("Force same aspect ratio")
                all_same_ar.triggered.connect(self.same_AR_as_first)
                all_same_cr = crop_menu.addAction("Force same crop, rotation and bg")
                all_same_cr.triggered.connect(self.same_crop_and_rotation_as_first)
                crop_menu.addSection("Reset")
                reset_crop_n_rot = crop_menu.addAction("Reset crop and rotation")
                reset_crop_n_rot.triggered.connect(lambda: self.reset_crop_and_rotation(crop=True, rotation=True))
                reset_crop = crop_menu.addAction("Reset crop only")
                reset_crop.triggered.connect(lambda: self.reset_crop_and_rotation(crop=True, rotation=False))
                reset_rot = crop_menu.addAction("Reset rotation only")
                reset_rot.triggered.connect(lambda: self.reset_crop_and_rotation(crop=False, rotation=True))

                # ── Appearance ▶ (LUTs + Background, submenu) ─────────
                appear_menu = self.contextMenu.addMenu("Appearance ▶")
                appear_menu.addSection("Look-up tables")
                set_luts = appear_menu.addAction("Set LUT(s)")
                set_luts.triggered.connect(lambda: self.set_luts(force_reset=False))
                reset_luts = appear_menu.addAction("Reset LUT(s)")
                reset_luts.triggered.connect(lambda: self.set_luts(force_reset=True))
                appear_menu.addSection("Background")
                set_bg = appear_menu.addAction("Set background")
                set_bg.triggered.connect(lambda: self.set_bg(bg='picker'))
                reset_bg = appear_menu.addAction("Reset background")
                reset_bg.triggered.connect(lambda: self.set_bg(bg=None))

                # ── Text & lettering ▶ (submenu) ──────────────────────
                txt_menu = self.contextMenu.addMenu("Text & lettering ▶")
                set_font = txt_menu.addAction("Change font (non-Letter text)")
                set_font.triggered.connect(self.set_text_font_all_but_letter)
                set_bg_txt = txt_menu.addAction("Change background (non-Letter text)")
                set_bg_txt.triggered.connect(self.set_text_bg_all_but_letter)
                txt_menu.addSeparator()
                change_lettering = txt_menu.addAction("Change lettering parameters")
                change_lettering.triggered.connect(self.change_lettering_parameters)

            # ── Cancel ───────────────────────────────────────────────
            self.contextMenu.addSeparator()
            self.contextMenu.addAction("Ignore")

            if self.check_if_context_menu_is_empty():
                return None
            self._run_context_menu_at_click(event)
            return None

        # ══════════════════════════════════════════════════════════════
        # LEFT-CLICK DRAG: original logic preserved below
        # ══════════════════════════════════════════════════════════════
        if self.selected_shape and drop_target is None:

            if top_parent_of_sel and not self.selected_shape==top_parent_of_sel and is_left_click:
                # Add a separator
                self.contextMenu.addSeparator()
                add_as_new_row = self.contextMenu.addAction("Extrude")
                add_as_new_row.triggered.connect(partial(self.extrude, self.selected_shape, top_parent_of_sel))

            # print('self.dragging inside dabu', self.dragging)
            if self.check_if_context_menu_is_empty():  # if menu is empty skip this because it is all useless
                return None
            # something was selected and there is a drop target --> we execute the menu straight away
            self._run_context_menu_at_click(event)
            return

        if drop_target is None and self.selected_shape in self.shapes_to_draw:
            # print('rejected because 1')

            self.reset_position()
            self.update()



            return None

        if drop_target is None and all_shapes_below is not None and not all_shapes_below:
            # print('rejected because 2')
            # self.reset_position()
            # self.update()
            # return None
            pass

        else:

            # print('in there ggsggagag dabu2', drop_target, all_shapes_below, self.selected_shape)


            if drop_target and all_shapes_below:
                # print('entering 4')
                # depending on the parameters I should offer swap and I could even do it by directly passing the stuff that should be swapped

                if False: # this seems useless now that I fixed various errors
                    if drop_target.contains(self.selected_shape):
                        # print('rejected 10')
                        self.reset_position()
                        self.update()
                        return None

                # add_as_new_row =  self.contextMenu.addAction("Add as new Row")
                # add_as_new_row.triggered.connect(self.raise_exception)
                tmp = all_encounters_in_shape_below_mouse[:]

                try:
                    tmp.remove(top_parent_of_sel)
                except Exception:
                    pass
                try:
                    tmp.remove(self.selected_shape)
                except Exception:
                    pass

                # print('content of tmp', tmp, 'vs sel', self.selected_shape)

                if len(tmp)==0:




                    if self.selected_shape != drop_target and isinstance(self.selected_shape, Image2D) and isinstance(drop_target, Image2D) and is_left_click:
                        self.contextMenu.addSeparator()
                        # create_row = self.contextMenu.addAction("Create a row with sel and drop")
                        create_row = self.contextMenu.addAction("To row")
                        create_row.triggered.connect(partial(self.create_row_with, drop_target,self.selected_shape))

                        # create_col = self.contextMenu.addAction("Create a row with sel and drop")
                        create_col = self.contextMenu.addAction("To column")
                        create_col.triggered.connect(partial(self.create_col_with, drop_target,self.selected_shape))
                        # maybe offer add or alike and if they have no parent

                        self.contextMenu.addSeparator()
                        swap2images = self.contextMenu.addAction("Swap")
                        swap2images.triggered.connect(partial(self.swap, self.selected_shape, drop_target, immediate_parent_of_sel, top_parent_of_sel, top_parent_of_drop_target))
                    else:

                    # if all_encounters_in_shape_below_mouse[-1] == self.selected_shape:
                    #     print('rejected because 5')
                    #     print('droped on itslef --> ignore')


                        self.reset_position()
                        self.update()
                        if self.check_if_context_menu_is_empty():  # if menu is empty skip this because it is all useless
                            return None
                        self._run_context_menu_at_click(event)  # in fact there are still stuff to be done

                        return None
                else:
                    # if self.selected_shape in

                    if isinstance(self.selected_shape, Image2D) and isinstance(tmp[0], Group) and not tmp[0].contains(self.selected_shape) and is_left_click:


                        if self.selected_shape == tmp[-1]:
                            # print('rejected because only self dragging is possble')
                            self.reset_position()
                            self.update()
                            return None

                        # print('MENU HERE IS CHANGED', self.selected_shape, tmp, tmp[0], tmp[-1], self.selected_shape == tmp[-1])

                        self.contextMenu.addSeparator()
                        append = self.contextMenu.addAction("Add to group (keep dragged shape layout)")
                        append.triggered.connect(partial(self.add, self.selected_shape, tmp[0]))
                        extend = self.contextMenu.addAction("Add to group (don't keep dragged shape layout)")
                        extend.triggered.connect(partial(self.extend, self.selected_shape, tmp[0]))

                        self.contextMenu.addSeparator()
                        # add_to_grp2 = self.contextMenu.addAction("Create new row with sel and drop target as columns")
                        add_to_grp2 = self.contextMenu.addAction("To row")
                        add_to_grp2.triggered.connect(partial(self.create_row_with, tmp[0],self.selected_shape))
                        # add_to_grp3 = self.contextMenu.addAction("Create new col with sel and drop target as rows")
                        add_to_grp3 = self.contextMenu.addAction("To column")
                        add_to_grp3.triggered.connect(partial(self.create_col_with, tmp[0],self.selected_shape))

                        if self.selected_shape == top_parent_of_sel and drop_target == top_parent_of_drop_target: # if an object is there then offer swap
                            self.contextMenu.addSeparator()
                            swap3 = self.contextMenu.addAction("Swap")
                            swap3.triggered.connect(partial(self.swap, self.selected_shape, drop_target, immediate_parent_of_sel,
                                        top_parent_of_sel, top_parent_of_drop_target))
                    elif isinstance(self.selected_shape, Group) and isinstance(tmp[0], Image2D) and not self.selected_shape.contains(tmp[0]):
                        # same as above but kinda inveretd
                        if self.selected_shape == tmp[-1]:  # do I need to keep that ???
                            # print('rejected because only self dragging is possble')
                            self.reset_position()
                            self.update()
                            return None
                        self.contextMenu.addSeparator()
                        append = self.contextMenu.addAction("Add to group")
                        append.triggered.connect(partial(self.add, tmp[0],self.selected_shape))
                        # extend = self.contextMenu.addAction("Add to group (don't keep dragged shape layout)")
                        # extend.triggered.connect(partial(self.extend,tmp[0], self.selected_shape))

                        self.contextMenu.addSeparator()
                        # add_to_grp2 = self.contextMenu.addAction("Create new row with sel and drop target as columns")
                        add_to_grp2 = self.contextMenu.addAction("To row")
                        add_to_grp2.triggered.connect(partial(self.create_row_with, tmp[0],self.selected_shape))
                        # add_to_grp3 = self.contextMenu.addAction("Create new col with sel and drop target as rows")
                        add_to_grp3 = self.contextMenu.addAction("To column")
                        add_to_grp3.triggered.connect(partial(self.create_col_with, tmp[0],self.selected_shape))

                        if self.selected_shape == top_parent_of_sel and drop_target == top_parent_of_drop_target: # if an object is there then offer swap
                            self.contextMenu.addSeparator()
                            swap3 = self.contextMenu.addAction("Swap")
                            swap3.triggered.connect(partial(self.swap, self.selected_shape, drop_target, immediate_parent_of_sel,
                                        top_parent_of_sel, top_parent_of_drop_target))
                    else:
                        can_swap = self.can_swap(self.selected_shape, tmp[0])
                        # print('can_swap', can_swap)

                        if not can_swap:
                        #
                        # # print('testing',self.selected_shape == all_encounters_of_sel_shape_below_mouse[0],  self.selected_shape.contains(tmp[0]))
                        # if self.selected_shape == all_encounters_of_sel_shape_below_mouse[0] and not tmp[0].contains(self.selected_shape) and not self.selected_shape.contains(tmp[0]):
                        # # accepted pos7 [Image2D-0x7f57a033b5a0-10.png] Group-2-0x7f578dcce260 [Group-2-0x7f578dcce260, Image2D-0x7f57a033b5a0-10.png]
                        # # if drop_target.contains(self.selected_shape):
                        #
                        #     # in some case I should still maybe offer swap or alike -−> I probably filter too much
                        #
                        #     if tmp[0]!=self.selected_shape and not tmp[0].contains(self.selected_shape):
                        #         do_new_stuff = self.contextMenu.addAction("swap I guess or do more")
                        #         do_new_stuff.triggered.connect(self.raise_exception)
                        #     else:
                        #         print('rejected 10')

                                # print('rejected because cannot swap')
                                self._run_context_menu_at_click(event) # still there are operations that need be done
                                self.reset_position()
                                self.update()
                                return None
                        # print('accepted pos7', tmp, self.selected_shape, all_encounters_of_sel_shape_below_mouse)# there is a bug here
                        if is_left_click:
                            if top_parent_of_sel == top_parent_of_drop_target and isinstance(top_parent_of_sel, Group):
                                self.informative_message_required.emit('Use keyboard arrows to rearrange elements within a group')
                            else:
                                self.contextMenu.addSeparator()
                                do_new_stuff = self.contextMenu.addAction("Swap")
                                do_new_stuff.triggered.connect(partial(self.swap, self.selected_shape, tmp, immediate_parent_of_sel, top_parent_of_sel, top_parent_of_drop_target))

                        if isinstance(tmp[0], Image2D) and isinstance(self.selected_shape, Image2D) and tmp[0] in self.shapes_to_draw and self.selected_shape in self.shapes_to_draw:
                            self.contextMenu.addSeparator()
                            # add_to_grp2 = self.contextMenu.addAction("Create new row with sel and drop target as columns")
                            add_to_grp2 = self.contextMenu.addAction("To row")
                            add_to_grp2.triggered.connect(partial(self.create_row_with, tmp[0],self.selected_shape))
                            # add_to_grp3 = self.contextMenu.addAction("Create new col with sel and drop target as rows")
                            add_to_grp3 = self.contextMenu.addAction("To column")
                            add_to_grp3.triggered.connect(partial(self.create_col_with, tmp[0],self.selected_shape))

                        if isinstance(tmp[0], Group) and isinstance(self.selected_shape, (Group, Image2D)) and is_left_click:
                            self.contextMenu.addSeparator()
                            add_to_grp = self.contextMenu.addAction("Add to group (keep dragged shape layout)")
                            add_to_grp.triggered.connect(partial(self.add, self.selected_shape, tmp[0])) # very good --> I can do that with partials so I can implement the whole logic

                            add_to_grp4 = self.contextMenu.addAction("Add to group (don't keep dragged shape layout)")
                            add_to_grp4.triggered.connect(partial(self.extend, self.selected_shape, tmp[0]))  # very good --> I can do that with partials so I can implement the whole logic

                            self.contextMenu.addSeparator()
                            # add_to_grp2 = self.contextMenu.addAction("Create new row with sel and drop target as columns")
                            add_to_grp2 = self.contextMenu.addAction("To row")
                            add_to_grp2.triggered.connect(partial(self.create_row_with, tmp[0],self.selected_shape))
                            # add_to_grp3 = self.contextMenu.addAction("Create new col with sel and drop target as rows")
                            add_to_grp3 = self.contextMenu.addAction("To column")
                            add_to_grp3.triggered.connect(partial(self.create_col_with, tmp[0],self.selected_shape))

                        # if isinstance(tmp[0], (Group, Image2D)) and isinstance(self.selected_shape, Group):
                        #     self.contextMenu.addSeparator()
                        #     # add_to_grp2 = self.contextMenu.addAction("Create new row with sel and drop target as columns")
                        #     add_to_grp2 = self.contextMenu.addAction("To row")
                        #     add_to_grp2.triggered.connect(partial(self.create_row_with, self.selected_shape, tmp[0]))
                        #     # add_to_grp3 = self.contextMenu.addAction("Create new col with sel and drop target as rows")
                        #     add_to_grp3 = self.contextMenu.addAction("To column")
                        #     add_to_grp3.triggered.connect(partial(self.create_col_with, self.selected_shape, tmp[0]))
            else:
                # print('accepted pos6')
                if is_left_click:
                    add_as_new_row = self.contextMenu.addAction("Add as new Row/Extrude from group")
                    add_as_new_row.triggered.connect(partial(self.extrude,self.selected_shape, top_parent_of_sel))

        # go = self.contextMenu.addAction("go")

        # if drop_target is None and not all_shapes_below and all_encounters_in_shape_below_mouse:
        #     print('entering 5')
        #     if all_encounters_in_shape_below_mouse[0] == self.selected_shape:
        #         print('rejected because 5')
        #         self.reset_position()
        #         self.update()
        #         return None
        # TODO --> add plenty of actions there and decide how to proceed and how to handle them!!!
        # shall I implement a swap

        if self.check_if_context_menu_is_empty(): # if menu is empty skip this because it is all useless
            return None

        self._run_context_menu_at_click(event)

    def change_lettering_parameters(self):
        self.open_lettering_parameters.emit()

    def check_if_context_menu_is_empty(self):
        try:

            if not self.contextMenu.actions():
                return True

            len_actions = len(self.contextMenu.actions())
            # print('in thare ',len_actions)

            if len_actions<=1:
                if self.contextMenu.actions()[0].text()=="Ignore":
                    return True
        except Exception:
            traceback.print_exc()
        return False
        # for action in self.contextMenu.actions():
        #     if action.text() == "Ignore":
        #         num_ignore_actions += 1
        # if num_ignore_actions == 1:
        #     return True
        # else:
        #     return False

    # def add_reset_menu(self):
    #     self.contextMenu.addSeparator()
    #
    #     reset_crop_n_rot = self.contextMenu.addAction("Reset crop and rotation")
    #     reset_crop_n_rot.triggered.connect(lambda: self.reset_crop_and_rotation(crop=True, rotation=True))
    #
    #     reset_crop = self.contextMenu.addAction("Reset crop")
    #     reset_crop.triggered.connect(lambda: self.reset_crop_and_rotation(crop=True, rotation=False))
    #
    #     reset_rot = self.contextMenu.addAction("Reset rotation")
    #     reset_rot.triggered.connect(lambda: self.reset_crop_and_rotation(crop=False, rotation=True))
    #
    #     self.contextMenu.addSeparator()
    #     set_bg_action = self.contextMenu.addAction("Set background")
    #     set_bg_action.triggered.connect(lambda:self.set_bg(bg='picker'))
    #
    #     reset_bg_action = self.contextMenu.addAction("Reset background")
    #     reset_bg_action.triggered.connect(lambda:self.set_bg(bg=None))




    def _add_as_new_group(self, lst, orientation='X', remove_from_parents=False):
        lst = [elm for elm in lst if not(isinstance(elm, Group) and elm.isText)]

        if lst is not None:
            if remove_from_parents:
                for elm in lst:
                    try:
                        self.shapes_to_draw.remove(elm)
                    except Exception:
                        pass

                for shape in self.shapes_to_draw:
                    for elm in lst:
                        try:
                            shape.remove(elm)
                        except Exception:
                            pass
                    try:
                        if shape.isEmpty():
                            self.shapes_to_draw.remove(shape)
                    except Exception:
                        pass

            grp = Group(*lst, orientation=orientation)
            self.shapes_to_draw.append(grp)

            # grp.update()
            self.update()
            self.update_size()

            self.force_update_size_of_parent.emit(grp)
            self.force_update_size_of_parent.emit(grp)
            self.set_current_selection(grp)
            self.update_letters_required.emit()
            self.update_text_rows.emit()
            self.focus_required.emit()
            self.set_current_selection(grp)
            self.undo_redo_save_required.emit()


    def remove_all(self, lst):

        # print('testing stuff to remove',lst)

        if isinstance(lst, list):
            if self.shapes_to_draw:
                for shape in reversed(self.shapes_to_draw):
                    for elm in lst:
                    # if self.shapes_to_draw:
                            try:
                                # print('trying to remove', elm, 'from', shape)
                                shape.remove(elm)
                                # print('remove successful')
                            except Exception:
                                pass
            for elm in lst:
                try:
                    self.shapes_to_draw.remove(elm)
                except Exception:
                    pass

        self.remove_all_empty_groups()


    def same_width_and_height(self):
        # I can do the same with AR because it is super easy

        # TODO --> I should only filter images

        # print('debugging same width and height')
        # loop over selection and force them to be all same with and height I just need the non scaled version of the stuff but with crop and rotation though!!!

        #
        # tmp = self.selected_shape
        #
        # if isinstance(tmp, Group):
        #     tmp = list(self.selected_shape.content)

        tmp = self.selected_shape

        if isinstance(tmp, Image2D):
            tmp = [tmp]
        else:
            _, tmp = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)


        if isinstance(tmp, list) and tmp: # or maybe I could do that for a single group too
            min_h = 10000000
            min_w = 10000000
            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                rect = elm.getRect(all=True)
                try:
                    min_h = min(min_h, rect.height()*elm.scale)
                    min_w = min(min_w, rect.width()*elm.scale)
                except Exception:
                    min_h = min(min_h, rect.height())
                    min_w = min(min_w, rect.width())
            # print('found ', min_h, min_w)
            # print('end debugging same width and height')

            # now recursively crop top and bottom to reach the same size for all images
            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                rect = elm.getRect(all=True)
                if rect.width()*elm.scale>min_w:
                    # rect = elm.getRect(all=True)
                    while  elm.getRect(all=True).width()*elm.scale>min_w:
                        elm.crop_left+=1
                        if elm.getRect(all=True).width()*elm.scale==min_w:
                            break
                        elm.crop_right += 1

            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                rect = elm.getRect(all=True)
                if rect.height()*elm.scale > min_h:
                    # rect = elm.getRect(all=True)
                    while elm.getRect(all=True).height()*elm.scale>min_h:
                        elm.crop_top+=1
                        if elm.getRect(all=True).height()*elm.scale==min_h:
                            break
                        elm.crop_bottom += 1

            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                self.force_update_size_of_parent.emit(elm)

            # TODO if this is a group I need resize the parent individually too
            for elm in tmp:

                top_parent = self.get_top_parent_of_shape(elm)
                if top_parent:
                    if isinstance(top_parent, (Image2D, Group)) and elm.isText:
                        continue
                    self.force_update_size_of_parent.emit(top_parent)
            # totoitoroetpierptoie

            #
            # self.update_size()
            # self.update()
            self.finalize_and_update()

        # try to force all images to that now

    def same_AR_as_first(self):

        # do this only if list and all images

        # I can do the same with AR because it is super easy

        # TODO --> I should only filter images

        # print('debugging same AR')
        # loop over selection and force them to be all same with and height I just need the non scaled version of the stuff but with crop and rotation though!!!
        # tmp = self.selected_shape
        #
        # if isinstance(tmp, Group):
        #     tmp = list(self.selected_shape.content)

        tmp = self.selected_shape

        if isinstance(tmp, Image2D):
            tmp = [tmp]
        else:
            _, tmp = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)


        if isinstance(tmp, list) and tmp:
        # if isinstance(self.selected_shape, list):  # or maybe I could do that for a single group too
            AR =None
            for elm in tmp:
                if isinstance(elm, Image2D) and elm.isText:
                    continue
                rect = elm.getRect(all=True)
                if AR is None:
                    AR = rect.width()/rect.height()
                    break


            # to fit the desired AR I need crop in the other dimension -−> TODO


            # now recursively crop top and bottom to reach the same size for all images
            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                rect = elm.getRect(all=True)
                cur_AR =  rect.width()/rect.height()

                tol= 5e-4 # if too low --> there can be a bug that prevents
                if abs(cur_AR - AR)>tol:
                    # print('abs(cur_AR - AR)', abs(cur_AR - AR), elm)
                    if cur_AR> AR:
                        while abs(cur_AR - AR)>tol:




                            # if cur_AR<AR:
                            #     break

                            # print('inside 2 abs(cur_AR - AR)', abs(cur_AR - AR), cur_AR, AR, abs(cur_AR - AR)>tol, abs(cur_AR - AR) <= tol)
                            elm.crop_left += 1
                            rect = elm.getRect(all=True)
                            cur_AR = rect.width()/rect.height()
                            if abs(cur_AR - AR) <= tol:
                                break
                            if cur_AR - AR < 0:
                                break
                            elm.crop_right += 1
                            rect = elm.getRect(all=True)
                            cur_AR = rect.width() / rect.height()
                            if abs(cur_AR - AR) <= tol:
                                break
                            if cur_AR - AR < 0:
                                break


                            # count+=1
                            # if count>=100:
                            #     break

                    else:
                        while abs(cur_AR - AR) > tol:
                            # if cur_AR>AR:
                            #     break



                            # print('inside 1 abs(cur_AR - AR)', abs(cur_AR - AR), cur_AR, AR, abs(cur_AR - AR)>tol, abs(cur_AR - AR) <= tol)
                            elm.crop_top += 1
                            rect = elm.getRect(all=True)
                            cur_AR = rect.width() / rect.height()
                            if abs(cur_AR - AR) <= tol:
                                break
                            if cur_AR - AR > 0:
                                break
                            elm.crop_bottom += 1
                            rect = elm.getRect(all=True)
                            cur_AR = rect.width() / rect.height()
                            if abs(cur_AR - AR) <= tol:
                                break
                            if cur_AR - AR > 0:
                                break

                        # rect = elm.getRect(all=True)
                else:
                    # print('skipping', elm)
                    pass


            # for elm in self.paint.EZFIG_panel.selected_shape:
            #     rect = elm.getRect(all=True)
            #     if rect.height() * elm.scale > min_h:
            #         # rect = elm.getRect(all=True)
            #         while elm.getRect(all=True).height() * elm.scale > min_h:
            #             elm.crop_top += 1
            #             if elm.getRect(all=True).height() * elm.scale == min_h:
            #                 break
            #             elm.crop_bottom += 1

            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                self.force_update_size_of_parent.emit(elm)
                rect = elm.getRect(all=True)
                cur_AR = rect.width() / rect.height()
                w, h = elm.get_raw_size()

                # print('teste',cur_AR-AR, abs(cur_AR-AR)<tol)
                # print(cur_AR, 'vs',  w/h, 'vs2', AR)

            # TODO if this is a group I need resize the parent individually too
            for elm in tmp:
                top_parent = self.get_top_parent_of_shape(elm)
                if top_parent is not None:
                    if isinstance(top_parent, (Image2D, Group)) and elm.isText:
                        continue
                    self.force_update_size_of_parent.emit(top_parent)
            # totoitoroetpierptoie

            #
            # self.update_size()
            # self.update()
            self.finalize_and_update()

    def same_crop_and_rotation_as_first(self):

        # do this only if list and all images

        # I can do the same with AR because it is super easy

        # TODO --> I should only filter images

        # print('debugging same AR')
        # loop over selection and force them to be all same with and height I just need the non scaled version of the stuff but with crop and rotation though!!!
        # tmp = self.selected_shape
        #
        # if isinstance(tmp, Group):
        #     tmp = list(self.selected_shape.content)

        tmp = self.selected_shape

        if isinstance(tmp, Image2D):
            tmp = [tmp]
        else:
            _, tmp = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)


        if isinstance(tmp, list) and tmp:
            # if isinstance(self.selected_shape, list):  # or maybe I could do that for a single group too
            crop_left = None
            crop_right = None
            crop_top = None
            crop_bottom = None
            theta = None
            fill_color= None
            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                if crop_left is None:
                    crop_left = elm.crop_left
                    crop_right = elm.crop_right
                    crop_top = elm.crop_top
                    crop_bottom = elm.crop_bottom
                    theta = elm.theta
                    fill_color = elm.fill_color
                else:
                    elm.crop_left=crop_left
                    elm.crop_right=crop_right
                    elm.crop_top=crop_top
                    elm.crop_bottom=crop_bottom
                    elm.theta=theta
                    elm.fill_color = fill_color


            # to fit the desired AR I need crop in the other dimension -−> TODO


            # now recursively crop top and bottom to reach the same size for all images
            for elm in tmp:
                if isinstance(elm, (Image2D, Group)) and elm.isText:
                    continue
                self.force_update_size_of_parent.emit(elm)

            # TODO if this is a group I need resize the parent individually too
            for elm in tmp:
                top_parent = self.get_top_parent_of_shape(elm)
                if top_parent is not None:
                    if isinstance(top_parent, (Image2D, Group)) and elm.isText:
                        continue
                    self.force_update_size_of_parent.emit(top_parent)

            self.finalize_and_update()

    def finalize_and_update(self): # gather all the possible signals in there
        self.update_letters_required.emit()
        self.update_text_rows.emit()
        self.set_current_selection(self.selected_shape)
        self.update_text_rows.emit()
        self.update_size()
        self.update()
        self.undo_redo_save_required.emit()


    def set_space(self):
        
        # i need to get all the groups and their progeny from the selection

        selected_groups = self.get_groups_from_sel(ignore_text_grps=True)

        if selected_groups:

            # print('list of selected groups', selected_groups)

            space_selector = SpaceSelectorWidget()
            custom_dialog = CustomDialog(title="Change space", message="Do you want to proceed?",
                                         main_widget=space_selector,
                                         parent=self, options=['Ok', 'Cancel'],
                                         auto_adjust=True)  # that is really very good --> I can do it like that

            if custom_dialog.exec_() != QDialog.Accepted:
                return

            # get the state of the checkbox
            apply_to_page = space_selector.is_apply_to_page_checked()
            # get the value of the spin box
            space = space_selector.get_space_value()

            grps_to_update = []

            for grp in selected_groups:
                grp.space = space
                grp.update()

                # if grp in self.shapes_to_draw:
                #     self.force_update_size_of_parent.emit(grp)
                top_parent = self.get_top_parent_of_shape(grp)
                if top_parent is not None:
                    grps_to_update.append(top_parent)

            if grps_to_update:
                grps_to_update = list(set(grps_to_update))
                for elm in grps_to_update:
                    self.force_update_size_of_parent.emit(elm)

            # print('apply_to_page,value',apply_to_page,space)


            # I need force update the main page spinner without updating it --> TODO -−> I need a change emitter
            if apply_to_page:
                self.space = space
                self.force_silent_spinner_update_in_parent.emit(space)

            self.finalize_and_update()


    def get_groups_from_sel(self, ignore_text_grps=True):
        tmp = self.selected_shape

        if tmp is None:
            tmp = list(self.shapes_to_draw)

        if isinstance(tmp, Group):
            tmp = tmp.get_nested_groups()
        elif isinstance(tmp, list):
            all_groups = []
            for elm in tmp:
                if isinstance(elm, Group):
                    all_groups.extend(elm.get_nested_groups())
            tmp = all_groups
        else:
            return []

        if ignore_text_grps:
            tmp = [elm for elm in tmp if not elm.isText]


        return tmp


        

    def get_images_from_sel(self):
        tmp = self.selected_shape

        if isinstance(tmp, Image2D):
            tmp = [tmp]
        else:
            _, tmp = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)
        return tmp

    def set_luts(self, force_reset=False):
        # MEGA TODO --> THIS CAN BE VERY SLOW SO TRY TO ADD A PROGRESSBAR THERE

        tmp = self.get_images_from_sel()

        # if isinstance(tmp, Group):
        #     tmp = list(self.selected_shape.content)
        # elif isinstance(tmp, Image2D):
        #     tmp = [tmp]



        if isinstance(tmp, list) and tmp:
            # open a window to set the bg --> TODO

            max_channels = 0
            for elm in tmp:
                cur_nb_channels = elm.get_nb_channels()
                max_channels = max(max_channels, cur_nb_channels)
                # print('channels', cur_nb_channels, max_channels)

            # then for each image I can select the stuff to have

            # now I need to open a Lut window then to
            if not max_channels:
                # print('no channels --> quitting immediately')

                return

            luts = None
            if not force_reset:
                # images have channels --> so we are going to apply a LUT to them
                lut_widget = LutWidget(nb_channels=max_channels)
                custom_dialog = CustomDialog(title="Edit Look Up Tables (LUTs)", message="Do you want to proceed?",
                                             main_widget=lut_widget,
                                             parent=self, options=['Ok', 'Cancel'],
                                             auto_adjust=True)  # that is really very good --> I can do it like that

                if custom_dialog.exec_() == QDialog.Accepted:
                    # print now we need to apply the Luts to all or to reset the luts for all!!!
                    luts = lut_widget.getAllLuts()

                else:
                    return

            # print('finally_in_there', luts)

            for elm in tmp:
                # if cur_nb_channels or force_reset:
                    if force_reset:
                        if elm.LUTs is not None:
                            elm.LUTs = luts
                            elm.update_qimage()  # we force the qimage to change and display the right LUT --> TODO
                    else:
                        # print('applying lut')
                        cur_nb_channels = elm.get_nb_channels()
                        if cur_nb_channels:
                            elm.LUTs = luts[:cur_nb_channels]
                            elm.update_qimage()  # we force the qimage to change and display the right LUT --> TODO
                            self._match_split_colours(elm)

            self.finalize_and_update()

    def _match_split_colours(self, merge):
        """The merge of a channel split got new LUTs: its single channels' name
        labels (or tints) follow, as set_lut does over MCP."""
        from batoolset.drawings.shapes.group import get_parent_of_obj
        from batoolset.drawings.shapes.txt2d import TAText2D
        from pyfigures.mcp_tools.stacks import split_colour_updates
        if not merge.LUTs or 'channel split of' not in str(getattr(merge, 'user_comments', '') or ''):
            return
        content = get_parent_of_obj(merge, self.shapes_to_draw)
        if not content:
            return
        panels = [p for p in content if hasattr(p, 'LUTs')]

        def labels_of(p):
            return [a for a in (getattr(p, 'annotations', None) or []) if isinstance(a, TAText2D)]

        siblings = [(getattr(p, 'user_comments', ''), p.LUTs, [t.getHtmlText() for t in labels_of(p)])
                    for p in panels]
        for k, new_luts, labels, _what in split_colour_updates(merge.user_comments, merge.LUTs, siblings):
            panel = panels[k]
            if new_luts is not None:
                panel.LUTs = new_luts
                panel.update_qimage()
            texts = labels_of(panel)
            for j, html in labels.items():
                texts[j].setText(html)

            # if bg is not None:
            #     bg_dialog = BackgroundColorPicker(self)
            #     custom_dialog = CustomDialog(title="Select a background color",
            #                                  message=None,
            #                                  # main_widget=main, options=['Ok', 'Cancel'], parent=self)
            #                                  main_widget=bg_dialog, options=['Ok', 'Cancel'], parent=self,
            #                                  auto_adjust=True)
            #     # if pass --> ignore
            #     if custom_dialog.exec_() == QDialog.Accepted:
            #         bg = bg_dialog.get_color()
            #     else:
            #         return
            #
            # for elm in tmp:
            #     if not elm.isText:
            #         elm.fill_color = bg
            #
            # self.finalize_and_update()

    def set_bg(self, bg=None):
        tmp = self.selected_shape

        if isinstance(tmp, Image2D):
            tmp = [tmp]
        else:
            _, tmp = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)

        # if isinstance(tmp, Group):
        #     tmp = list(self.selected_shape.content)
        # elif isinstance(tmp, Image2D):
        #     tmp = [tmp]

        if isinstance(tmp, list) and tmp:
            # open a window to set the bg --> TODO

            if bg is not None:
                bg_dialog = BackgroundColorPicker(self)
                custom_dialog = CustomDialog(title="Select a background color",
                                             message=None,
                                             # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                             main_widget=bg_dialog, options=['Ok', 'Cancel'], parent=self,
                                             auto_adjust=True)
                # if pass --> ignore
                if custom_dialog.exec_() == QDialog.Accepted:
                    bg = bg_dialog.get_color()
                else:
                    return


            # TODO --> I need the recursive for that and only for images --> changed the code

            for elm in tmp:
                if not elm.isText:
                    elm.fill_color = bg

            # now recursively crop top and bottom to reach the same size for all images
            # for elm in tmp:
            #     self.force_update_size_of_parent.emit(elm)
            #
            # # TODO if this is a group I need resize the parent individually too
            # for elm in tmp:
            #     top_parent = self.get_top_parent_of_shape(elm)
            #     if top_parent is not None:
            #         self.force_update_size_of_parent.emit(top_parent)

            self.finalize_and_update()

    def reset_crop_and_rotation(self, crop=True, rotation=True):
        # tmp = self.selected_shape
        #
        # if isinstance(tmp, Group):
        #     tmp = list(self.selected_shape.content)
        # elif isinstance(tmp, Image2D):
        #     tmp=[tmp]
        tmp = self.selected_shape

        if isinstance(tmp, Image2D):
            tmp = [tmp]
        else:
            _, tmp = self.get_full_list_ofimages2D_for_consolidation(
                stuff_to_consolidate=self.selected_shape,
                include_insets=False, exclude_images_without_filename=False)

        if isinstance(tmp, list) and tmp:
            # print('resetting crop n rot', tmp)

            crop_left = 0
            crop_right = 0
            crop_top = 0
            crop_bottom = 0
            theta = 0
            for elm in tmp:
                if crop:
                    # print('in crop')
                    elm.crop_left=crop_left
                    elm.crop_right=crop_right
                    elm.crop_top=crop_top
                    elm.crop_bottom=crop_bottom
                if rotation:
                    # print('in rot')
                    elm.theta=theta

            # now recursively crop top and bottom to reach the same size for all images
            for elm in tmp:
                self.force_update_size_of_parent.emit(elm)

            # TODO if this is a group I need resize the parent individually too
            for elm in tmp:
                top_parent = self.get_top_parent_of_shape(elm)
                if top_parent is not None:
                    self.force_update_size_of_parent.emit(top_parent)

            self.finalize_and_update()


    def get_stuff(self):
        if isinstance(self.selected_shape, Group) and not self.selected_shape.isText:
            stuff_to_split = list(
                self.selected_shape.content)  # this is mandatory otherwise the list evolves with time --> really need to copy it
            # print('success')
        else:
            # print('failure')
            # return
            stuff_to_split = []
            if isinstance(self.selected_shape, list):
                # loop over the list and ignore all the Image2D
                for elm in self.selected_shape:
                    if isinstance(elm, Group) and not elm.isText:
                        stuff_to_split.extend(elm.content)
                    else:
                        # prevent useless dissociation because they are already in the main list
                        top_parent = self.get_top_parent_of_shape(elm)
                        if top_parent is not None and top_parent != elm:
                            stuff_to_split.append(elm)
            else:
                stuff_to_split = [self.selected_shape]

            # print('@'*20)
        if not isinstance(stuff_to_split, list):
            stuff_to_split = [stuff_to_split]

        return stuff_to_split


    def all_as_single(self):
        # if stuff_to_split is None:
        #     return

        stuff_to_split = self.get_stuff()
        # stuff_to_split = [stuff for stuff in stuff_to_split if not stuff.isText]


        # we clean to remove all texts from that

        # print('checking', self.selected_shape == self.shapes_to_draw[0], self.shapes_to_draw[0].content)
        # print('stuff_to_split before', stuff_to_split)
        # loop over that and
        self.remove_all(stuff_to_split)



        # print('stuff_to_split after',stuff_to_split)
        # print('checking before self.shapes_to_draw',self.shapes_to_draw)

        self.remove_all_empty_groups()

        # print('checking after self.shapes_to_draw', self.shapes_to_draw)



        # print('stuff_to_split',stuff_to_split)

        for elm in stuff_to_split:
            # do not allow split of texts maybe ???
            self.shapes_to_draw.append(elm)
            self.force_update_size_of_parent.emit(elm)

        # print('checking after2 self.shapes_to_draw', self.shapes_to_draw)
        self.remove_all_empty_groups()

        # print('checking after3 self.shapes_to_draw', self.shapes_to_draw)

        # try:
        #     print('content in there',self.shapes_to_draw[0].content)
        # except:
        #     pass

        self.update()
        self.update_size()
        # print('@' * 20)
        self.update_letters_required.emit()
        self.update_text_rows.emit()
        self.focus_required.emit()
        self.set_current_selection(None)
        self.undo_redo_save_required.emit()


    def reorganize_as_panel(self):
        stuff_to_split = self.get_stuff()

        # here I will have the stuff

        # now I need to get the list of these things

        # print('stuff_to_split', stuff_to_split)
        if not stuff_to_split and isinstance(self.selected_shape, list):
            stuff_to_split = self.selected_shape
        # print('stuff_to_split2', stuff_to_split)

        if stuff_to_split is not None and len(stuff_to_split)>1:
            panel_creator = PanelCreator(self, len(stuff_to_split))
            custom_dialog = CustomDialog(title="Reorganize as a panel",
                                         message=None,
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=panel_creator, options=['Ok', 'Cancel'], parent=self,
                                         auto_adjust=True)

            if custom_dialog.exec_() != QDialog.Accepted:
                return
        else:
            return

        values = panel_creator.get_values()



        # stuff_to_split = [stuff for stuff in stuff_to_split if not stuff.isText]

        # we clean to remove all texts from that

        # print('checking', self.selected_shape == self.shapes_to_draw[0], self.shapes_to_draw[0].content)
        # print('stuff_to_split before', stuff_to_split)
        # loop over that and
        self.remove_all(stuff_to_split)

        # print('stuff_to_split after',stuff_to_split)
        # print('checking before self.shapes_to_draw',self.shapes_to_draw)

        self.remove_all_empty_groups()

        # print('checking after self.shapes_to_draw', self.shapes_to_draw)

        # print('stuff_to_split',stuff_to_split)

        # for elm in stuff_to_split:
        #     # do not allow split of texts maybe ???
        #     self.shapes_to_draw.append(elm)
        #     self.force_update_size_of_parent.emit(elm)

        self._create_panel_directly(stuff_to_split, values['num_rows'], values['num_cols'],
                                    values['add_empty_images'], values['order'])


        # print('checking after2 self.shapes_to_draw', self.shapes_to_draw)
        self.remove_all_empty_groups()

        # print('checking after3 self.shapes_to_draw', self.shapes_to_draw)

        # try:
        #     print('content in there',self.shapes_to_draw[0].content)
        # except:
        #     pass

        # self.update()
        # self.update_size()
        # # print('@' * 20)
        # self.update_letters_required.emit()
        # self.update_text_rows.emit()
        # self.focus_required.emit()
        # self.set_current_selection(None)
        # self.undo_redo_save_required.emit()

        # self.undo_redo_save_required.emit()

    def _create_panel_real(self, lst):
        # nb if not a string then I need to remove it from all the parents --> TODO


        # for elm in lst:
        #     if isinstance(elm, Group) and elm.isText:
        #         self.informative_message_required.emit('Please do not include text rows/labels')
        #         return



        lst = [elm for elm in lst if (isinstance(elm, str) or not elm.isText)]
        # lst = [elm for elm in lst if not elm.isText]
        # if not lst:
        #     return



        panel_dialog = PanelCreator(self, len(lst))

        custom_dialog = CustomDialog(title="Panel",
                                     message=None,
                                     # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                     main_widget=panel_dialog, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)
        if custom_dialog.exec_() == QDialog.Accepted:

            # print('effectcive sel reset2', self.selected_shape)
            values = panel_dialog.get_values()
            self._create_panel_directly(lst,values['num_rows'], values['num_cols'],values['add_empty_images'], values['order'])

    def _create_panel_directly(self, lst, rows, cols,add_empty_images, order):
        self.remove_all(lst)  # if this is text this will be ignored but if these are real images it will work!!!
        # print('values for generation', values) #{'num_rows': 2, 'num_cols': 3, 'add_empty_checkbox_visible': False, 'missing_elements': 0, 'order': 'X'}
        # missing_elements = values['missing_elements']
        # print('add_empty_images',add_empty_images)
        if order == 'X':
            sublists = divide_list_into_sublists(lst, rows, cols)

            # print('sublists',sublists)
            # print(len(sublists))

            for sublist in sublists:
                tmp = Group(*sublist, size=512, orientation=order,
                            add_empty_images_instead_of_None=add_empty_images)
                if tmp.isEmpty():  # if only empty it cannot find the size --> so better skip it
                    continue
                if len(tmp)==1:
                    tmp = tmp.content[0]
                self.shapes_to_draw.append(tmp)
                self.force_update_size_of_parent.emit(tmp)

            self.set_current_selection(tmp)
        else:
            sublists = divide_list_into_sublists(lst, cols, rows)
            groups = []
            for sublist in sublists:
                tmp = Group(*sublist, orientation=order,
                            add_empty_images_instead_of_None=add_empty_images)
                # self.paint.EZFIG_panel.shapes_to_draw.append(tmp)
                groups.append(tmp)

            # I need hack that maybe or post fix it !!!

            # for ggg,elm in enumerate(groups):
            #     print('elm.isEmpty()',elm.isEmpty())
            #     if elm.isEmpty():
            #         previous = groups[ggg-1]
            #         w,h = previous.content[-1].get_raw_size()
            #         size = len(previous)
            #
            #         print(size)
            #         for i in range(size):
            #             print('adding an image',w,h)
            #             elm.content.append(Image2D(width=w, height=h))
            #             elm.update()

            groups = [grp for grp in groups if not grp.isEmpty()]
            groups = [grp.content[0] if len(grp)==1 else grp for grp in groups] # unpack groups that just contain one image

            # print(groups)

            final_grp = Group(*groups, size=512, orientation='X')
            self.shapes_to_draw.append(final_grp)
            self.set_current_selection(final_grp)
            self.force_update_size_of_parent.emit(final_grp)

        self.update()
        self.update_size()
        self.update_letters_required.emit()
        self.update_text_rows.emit()
        self.focus_required.emit()

        # print('resetting sel')

        self.set_current_selection(None)
        # print('effectcive sel reset', self.selected_shape)
        self.update()
        self.update_size()

        self.undo_redo_save_required.emit()

    def _run_context_menu_at_click(self, event=None):
        if event is not None:
            # Map the position of the drop event to global coordinates
            global_pos = self.mapToGlobal(event.pos())
            # Open the context menu at the mapped position
            action = self.contextMenu.exec_(global_pos)
            return action

    def raise_exception(self):
        try:
            raise Exception('NOT IMPLEMENTED YET2 −−> TODO')
        except Exception:
            traceback.print_exc()

    # TODO detect also ctrl + click
    # the other possibility is to use a different shortcut for going inside the object or double  click to further edit it --> would allow to ease selection and then when done the stuff is over
    # or do the same as previously because that works and allows a lot of things to be done

    # --> ok
    # if None --> either it is last or
    def get_inner_at_coord(self, shape_to_screen, last_click):
        if not shape_to_screen.contains(last_click):
            return None
        try:
            # object is not iterable --> skip and move to next
            some_object_iterator = iter(shape_to_screen)
        except TypeError as te:
            # we have reached a non iterable object --> this is therefore the last level object --> ignore
            return shape_to_screen
        # if object is in object --> need iter it too --> see how I can do that
        # implement the clones
        # try new tracking algo
        for shp in shape_to_screen:
            # can I use intersect to be sure the ovelap is ok
            # if not shp.boundingRect().intersects(current_sel.boundingRect()):
            if not shp.boundingRect().contains(last_click):
                continue
            if shp.boundingRect().contains(last_click):
                # c'est ici il faut retourner seulement si
                # need further check this
                return shp
        # nothing found --> return None
        return None


    # il y a un big bug --> surtout quand image is big --> ci dessous c'est faux
    # def get_all_inner_objects_at_position(self, shape_to_screen, last_click):
    #     shapes_and_progeny = [shape_to_screen]
    #     if not self.is_iterable(shape_to_screen):
    #         return shapes_and_progeny
    #     else:
    #         inner = shape_to_screen
    #         while True:
    #             if not self.is_iterable(inner):
    #                 return shapes_and_progeny
    #             else:
    #                 inner = self.get_first_encounter_at_click(inner, last_click)
    #                 shapes_and_progeny.append(inner)
    #     return shapes_and_progeny


    def get_first_encounter_at_click(self, shape_to_screen, last_click):
        for shape in shape_to_screen:
            if not isinstance(shape, QPointF): # a point has no bounding rect
                if shape.boundingRect().contains(last_click.x(), last_click.y()):
                        return shape
        return None

    # I somehow need check if the object contains the object --> because can be a problem for overlaping shapes --> see how to handle that

    # def get_progeny(self):
    #
    # def shape_contains_another(self, shape_to_check, cur_sel):
    #     # if current selection is not contained in shape, then
    #
    #     return False
    #
    # def get_inner_object_at(self, shape_to_screen, last_click):
    #     try:
    #         # object is not iterable --> skip and move to next
    #         some_object_iterator = iter(shape_to_screen)
    #     except TypeError as te:
    #         # we have reached a non iterable object --> this is therefore the last level object --> ignore
    #         return shape_to_screen
    #     for shp in shape_to_screen:
    #
    #
    #
    def is_iterable(self, shape_to_screen):
        try:
            # object is not iterable --> skip and move to next
            some_object_iterator = iter(shape_to_screen)
            return True
        except TypeError as te:
            # we have reached a non iterable object --> this is therefore the last level object --> ignore
            return False
        return False

    def get_full_list_ofimages2D_for_consolidation(self, stuff_to_consolidate=None,exclude_images_without_filename=True, include_insets=True):
        # maybe I need a further filtering to only keep the non text images --> TODO

        if stuff_to_consolidate is None:
            full_list_of_images = flatten_iterable(self.shapes_to_draw)
        else:
            if isinstance(stuff_to_consolidate, Image2D):
                full_list_of_images = [stuff_to_consolidate]
            else:
                full_list_of_images = flatten_iterable(stuff_to_consolidate)
        if include_insets:
            insets = []
            for elm in full_list_of_images:
                if elm.annotations:
                    insets.extend(find_all_objects_of_type(elm.annotations, Image2D))
            full_list_of_images.extend(insets)
        if exclude_images_without_filename:
            full_list_of_images = [img for img in full_list_of_images if
                               img.filename]  # only keep the images that have a filename
        full_list_of_filenames_to_consolidate = [file.filename for file in full_list_of_images]

        return full_list_of_filenames_to_consolidate, full_list_of_images

    # def get_full_list_of_filenames_for_consolidation(self):


    # simpler way is to get all possible inners and act according to result

    # need find the level of an object and go deeper!!!
    # try if parent --> maybe while is parent --> take the object
    # alternatively match all possible objects below and if this is the last level then skip...
    def get_inner_shape(self, shape_to_screen, current_sel, last_click):
        if not shape_to_screen.boundingRect().intersects(current_sel.boundingRect()):
            return None
        # need find if object is lower level
        lower_level_object = shape_to_screen
        while True:
            old_object = lower_level_object
            lower_level_object = self.get_inner_at_coord(lower_level_object, last_click)
            if old_object == lower_level_object:
                return lower_level_object
            # nothing below --> ignore
            if lower_level_object is None:
                # nothing found --> need move to the next object
                return None
            if lower_level_object == current_sel:
                lower_level_object = self.get_inner_at_coord(lower_level_object, last_click)
                # the current selected object is the selected object --> need select the parent
                # if lower_level_object == current_sel:
                    # try going deeper or return current object
                if lower_level_object is None:
                    # the object has never been found!!! --> return None --> the new object is not a child of the current sel
                    return None
                else:
                    # need check if object is contained in object and if so
                    return lower_level_object
            else:
                # if not parent need check if object is contained otherwise return the parent
                # we found a potential click --> as long as object is not found in then keep it
                # if object is not contained in lower_object then return object otherwise go deeper the last level where the object it
                # if object is at a lower level then loop
                check_deeper = lower_level_object
                while True:
                    old_chck = check_deeper
                    check_deeper = self.get_inner_at_coord(check_deeper, last_click)
                    if check_deeper == current_sel:
                        return self.get_inner_at_coord(check_deeper, last_click)
                    if check_deeper is None:
                        break
                    if old_chck == check_deeper:
                        # return lower_level_object
                        break

                return lower_level_object

        # ça a l'air de marcher --> check if something was dragged before or not
        # try:
        #     # object is not iterable --> skip and move to next
        #     some_object_iterator = iter(shape_to_screen)
        # except TypeError as te:
        #     return None
        # # if object is in object --> need iter it too --> see how I can do that
        # # implement the clones
        # # try new tracking algo
        # for shp in shape_to_screen:
        #     # can I use intersect to be sure the ovelap is ok
        #     # if not shp.boundingRect().intersects(current_sel.boundingRect()):
        #     if not shp.boundingRect().contains(last_click):
        #         continue
        #     if shp.boundingRect().contains(last_click):
        #         # c'est ici il faut retourner seulement si
        #         # need further check this
        #         bckup_shp = shp
        #
        #         return shp
        # # nothing found --> return None
        return None
        # can be done recursively from outside --> how to always find the level below an object or parent if lowest level
        # if objects are equal --> try go deeper else still need make sure if it is a subset or


    def _generate_text_row_content(self, text_row=None):
        parent_widget = QWidget()  # The parent widget
        parent_layout = QVBoxLayout(parent_widget)  # The layout of the parent widget

        scroll_area2 = QScrollArea()
        content_widget2 = QWidget()
        self.texts_layout = QVBoxLayout(content_widget2)
        scroll_area2.setWidget(content_widget2)
        scroll_area2.setWidgetResizable(True)

        warning_lab = QLabel('<Font color=#FF0000>Please add items in ascending order and ensure they do not overlap ("Begin" and "End" variables)<br><br>If there are too many items close this window and delete the unnecessary ones<br><br>NB: first image has index 0</Font>')
        self.texts_layout.addWidget(warning_lab)
        add_text_button = QPushButton('Add Text')
        add_text_button.clicked.connect(self.add_new_text) # TODO implement that too
        self.texts_layout.addWidget(add_text_button)
        self.all_text_editors = []
        for obj in text_row:
            if isinstance(obj, Image2D) and obj.isText and isinstance(obj.annotations[0], TAText2D):
                txt = TextEditor(obj.annotations[0], show_range=True)
                self.texts_layout.addWidget(txt)
                self.all_text_editors.append(txt)

        parent_layout.addWidget(scroll_area2)
        return parent_widget

    def add_new_text(self):
        # print('TODO -−> ACTION REQUIRED NEED ADD NEW TEXT')

        try:
            last_text_idx = self.all_text_editors[-1].associated_text.range[-1]+1

            # print('success', last_text_idx)
        except Exception:
            traceback.print_exc()
            last_text_idx = 0

        txt = TextEditor(associated_text=TAText2D('', placement='center_h center_v', range=[last_text_idx, last_text_idx]), show_range=True)
        # self.texts_layout.insertWidget(-2,txt) # DEV NOTE KEEP MEGA TODO trick to put it before in order not to have to rebuild the whole stuff -> CAN DO THE same for the annot editor

        # print('testing', txt.associated_text.range)

        # get the last index from

        self.texts_layout.addWidget(txt) # the above somehow does not seem to work...
        self.all_text_editors.append(txt)


    def edit_text_row_content(self, text_row=None):

        if text_row is None or isinstance(text_row, bool):
            if isinstance(self.selected_shape, Group) and self.selected_shape.isText:
                text_row = self.selected_shape
            else:
                return


        # if any is not a text then do not allow edit

        for txt in text_row:
            if not (isinstance(txt, Image2D) and txt.isText):
                # print(' invalid text row --> Skipping better not edit it and marking it as non label row')
                text_row.isText = False
                return

        all_clones = [clone_object(txt.annotations[0]) for txt in text_row if (isinstance(txt, Image2D) and txt.isText)]

        main =self._generate_text_row_content(text_row)
        custom_dialog = CustomDialog(title="Edit labels",
                                     message="Done with your edits? Press 'Ok' to apply the changes or 'Cancel' to ignore all changes.",
                                     # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                     main_widget=main, options=['Ok', 'Cancel'], parent=self)

        if custom_dialog.exec_() == QDialog.Accepted:
            # here I will need to add new images
            for zzz,txt in enumerate(self.all_text_editors):
                try:
                    text_row[zzz].annotations[0] = txt.associated_text
                except Exception:
                    traceback.print_exc()
                    # print('txt.associated_text here',txt.associated_text)

                    text_row.content.append(Image2D(width=512, height=512, annotations=[txt.associated_text], isText=True)) # all extras are added like that
            text_row.update()

            # print('text_row after',text_row)
            self.update_text_rows.emit()
            self.undo_redo_save_required.emit()
        else:
            for zzz,txt in enumerate(text_row):
                if not (isinstance(txt, Image2D) and txt.isText):
                    continue
                txt.annotations[0]=all_clones[zzz]



            # print("Yes clicked")
        #
        #
        #     top_parent = self.get_top_parent_of_shape(image2d)
        #
        #     if top_parent:
        #         immediate_parent = get_parent_of_obj(image2d, top_parent)
        #         if isinstance(immediate_parent, Group):
        #             print('Replacing image in parent')
        #             immediate_parent.replace(image2d, clone)
        #             top_parent.update()
        #         else:
        #             print('replacing image failed', immediate_parent, clone)
        #     else:
        #         self.shapes_to_draw[self.shapes_to_draw.index(image2d)] = clone
        #         print('Replacing image in main shapes')
        #     self.set_current_selection(clone)  # now the clone is the selection so I need to update it
        #     self.undo_redo_save_required.emit()  # smthg was changed --> save is required for undo or redo
        # else:
        #     # image2d = clone
        #     print(
        #         'need to reset the changes --> see how to implement that can I simply clone all the shapes and edit the clone or do I need smthg smarter ??? no clue not so easy --> action required')  # need a bit of thinking
            pass

    def mouseDoubleClickEvent(self, event):

        # print('double clik', event)
        # print('#'*20)
        # self.freeze =True
        if event.button() == Qt.LeftButton:  # Check if left mouse button is double-clicked
            # a double click was detected --> find the corresponding image of interest and edit its annotations

            # cool --> upon double click always edit the current image --> makes everything so simpler also make a right click maybe to edit the image
            # print("Double-click detected!")
            self.double_click = event.position()

            # self.reset_position()


            point = QPointF(float(int(self.double_click.x() / self.scale)), float(int(self.double_click.y() / self.scale)))

            # no it's not going down enough







            for shape in reversed(self.shapes_to_draw):
                if shape.contains(point):



                    # cur_shape = shape

                    # print('NEO CHECK checked shape', shape)
                    all_shape = self.get_all_encounters_ordered_below_mouse_for_a_given_shape(shape, point,
                                                                                  append_shape_to_screen=True) # somehow if I have below the mouse a Qrect then it doesn't work

                    # print('all_shape TADAM', all_shape)

                    if all_shape:

                        # if there is a group with is text in the stuff then allow edit of all the layers

                        text_row = find_first_object_of_type(all_shape, Group)

                        # print('inside double click2',text_row)
                        # if text_row is None:
                        #     return
                        if text_row is not  None and text_row.isText and not (isinstance(self.selected_shape,Image2D) and self.selected_shape.isText): # we found a text row so we are going to edit its content based on double click
                            # print('editing text row --> TODO')
                            # now I need to od the code to edit the text row --> TODO

                            self.edit_text_row_content(text_row=text_row)


                            return


                        image2d = find_first_object_of_type(all_shape, Image2D)



                        # self.set_current_selection(image2d)
                        if image2d is None:
                            return


                        self.update_image_annotations(image2d=image2d)
        # self.freeze = False
                    #
                    # try:
                    #     while is_iterable(shape):
                    #
                    #         print('NEO CHECK2 checked shape', shape)
                    #         # cur_shape = shape
                    #         for elm in shape:
                    #             print('NEO CHECK3 checked shape', elm)
                    #             if elm.contains(point):
                    #                 # cur_shape = elm
                    #                 shape = elm
                    #                 self.set_current_selection(shape)
                    #
                    #                 from personal.annotation_editor_former_000_TOP_vectorial2 import VectorialDrawPane2, MainWindow
                    #                 # I do not even need to select the image I can directly edit it
                    #                 vdp = VectorialDrawPane2(background=shape)
                    #                 main = MainWindow(qt_viewer=vdp)
                    #                 # main =QWidget()
                    #
                    #                 # Create and show the custom dialog, passing the MainWindow widget as parent
                    #                 custom_dialog = CustomDialog(title="Annotate the image",
                    #                                              message="Done with your edits? Press 'Ok' to apply the changes or 'Cancel' to ignore all changes.",
                    #                                              main_widget=main, options=['Ok', 'Cancel'], parent=self)
                    #                 if custom_dialog.exec_() == QDialog.Accepted:
                    #                     # print("Yes clicked")
                    #                     print('need to recover the image and do things with it --> action required')
                    #                     # TODO I need also restore the initial scale of the image --> so I need get it before hand
                    #                     print(
                    #                         custom_dialog.main_widget.qt_viewer.background)  # TODO --> maybe add a method to simplify that ???? because that is a bit heavy
                    #                 else:
                    #                     print('need to reset the changes --> see how to implement that can I simply clone all the shapes and edit the clone or do I need smthg smarter ??? no clue not so easy --> action required')  # need a bit of thinking
                    #
                    #                 break
                    # except:
                    #     pass
                    #
                    # return


            # scroll in shape until I get the corresponding image -−> TODO
        # super().mouseDoubleClickEvent(event)

    def update_image_annotations(self, image2d=None):

        # print('I AM INSIDE update_image_annotations')

        if image2d is None or isinstance(image2d, bool):
            if isinstance(self.selected_shape, Image2D):
                image2d = self.selected_shape
            else:
                return
        # self.freeze = True

        # clone = Dolly(image2d).get_cloned_object() # TODO I need to implement the cloning but that is not so easy beacuse all interanl stuff should also be cloned which is not easy −> this will take a lot of time

        # xml_string = object_to_xml(image2d)
        #
        #
        #
        # # properties = deserialize_to_dict(xml_string)
        # # if 'filename' in properties:
        # #     properties['args'] = properties['filename']
        # # clone = Image2D(**properties)
        # clone = create_object(Image2D.__name__, deserialize_to_dict(xml_string))
        #
        #
        # print('#' * 40)
        # print(xml_string)
        # if xml_string != object_to_xml(clone):
        #     print('-'*40)
        #     print(object_to_xml(clone))
        #     print(clone.__dict__)
        # print('Image', clone.img)
        # print('#' * 40)




        if not image2d.isText:
            # print('I am in the image annotation editor I should do that')

            clone = clone_object(image2d)

            # can I manually generate an image that is roughly similar excecpt for the rect -−> think of that -−> not that simple --> ok for now

            # we store the key parameters of the image
            topleft_before = image2d.topLeft()
            scale_before = image2d.scale
            rotation_before = image2d.theta
            # I do not even need to select the image I can directly edit it
            vdp = VectorialDrawPane2(background=clone)

            # def reload_background_parameters(self):


            main = MainWindow(qt_viewer=vdp)

            # we reaload the parameters
            if clone.user_comments:
                main.comments_text_edit.setText(clone.user_comments)

            if clone.custom_loading_script:
                main.script_text_edit.setText(clone.custom_loading_script)
            # main =QWidget()

            # Create and show the custom dialog, passing the MainWindow widget as parent
            custom_dialog = CustomDialog(title="Annotate the image",
                                         message="Done with your edits? Press 'Ok' to apply the changes or 'Cancel' to ignore all changes.",
                                         # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                         main_widget=main, options=['Ok','Cancel'], parent=self, auto_adjust=False)

            if custom_dialog.exec_() == QDialog.Accepted:
                # print("Yes clicked")
                # print('need to recover the image and do things with it --> action required')
                # TODO I need also restore the initial scale of the image --> so I need get it before hand
                # print(custom_dialog.main_widget.qt_viewer.background)  # TODO --> maybe add a method to simplify that ???? because that is a bit heavy

                clone = custom_dialog.main_widget.qt_viewer.background # that is why it was not working !!!
                # need replace the image2D by its clone
                clone.set_to_scale(scale_before)
                clone.setTopLeft(topleft_before)
                # clone.set_rotation(rotation_before)

                clone.set_rotation(main.rotate_image_spinbox.value())
                clone.crop(main.crop_left_spinbox.value(),main.crop_right_spinbox.value(),main.crop_top_spinbox.value(),main.crop_bottom_spinbox.value())

                clone.user_comments = main.comments_text_edit.toPlainText() # we reload the user comments

                top_parent = self.get_top_parent_of_shape(image2d)

                if top_parent:
                    immediate_parent = get_parent_of_obj(image2d, top_parent)
                    if isinstance(immediate_parent, Group):
                        # print('Replacing image in parent')
                        immediate_parent.replace(image2d, clone)
                        top_parent.update()
                        self.force_update_size_of_parent.emit(top_parent)
                    else:
                        self.shapes_to_draw[self.shapes_to_draw.index(image2d)]= clone
                        self.force_update_size_of_parent.emit(clone)
                        # print('Replacing image in main shapes')
                        # print('replacing image failed', immediate_parent, clone)
                else:
                    self.shapes_to_draw[self.shapes_to_draw.index(image2d)] = clone
                    self.force_update_size_of_parent.emit(clone)
                    # print('Replacing image in main shapes')

                if main.qt_viewer.crops:
                    # the image has crops --> add a new group with all the user crops to the image
                    self.shapes_to_draw.append(Group(*main.qt_viewer.crops))
                    # put a message here (
                    self.informative_message_required.emit('Crops have been added at the bottom of the figure') # this does not show up because the message is not a stack so the save message overrides it which is not good
                    self.force_update_size_of_parent.emit(self.shapes_to_draw[-1])

                # print('NB I PROBABLY NEED SOME SIZE UPDATE THERE TOO!!!')



                self.update_letters_required.emit()
                self.update_text_rows.emit()
                # there seems to be a packing error here
                self.set_current_selection(None) # now the clone is the selection so I need to update it
                # this is required to really update the inset --> TODO
                self.update_size()
                self.update()
                
                self.undo_redo_save_required.emit() # smthg was changed --> save is required for undo or redo
            else:
                # image2d = clone
                # print('need to reset the changes --> see how to implement that can I simply clone all the shapes and edit the clone or do I need smthg smarter ??? no clue not so easy --> action required')  # need a bit of thinking
                pass
        else:
            top_parent = self.get_top_parent_of_shape(image2d)
            # just edit the text of the image
            text_to_Edit = clone_object(image2d.annotations[0])
            # print('double clicked on a text --> further edit it')
            # do a popup for editing the text --> make it a dialog as the others maybe
            # TODO
            # --> in a way this is simpler!!!!



            # print('text_to_Edit', text_to_Edit)

            editor = TextEditor(text_to_Edit, show_range=isinstance(top_parent, Group) and top_parent.isText)

            # print('placement before', text_to_Edit.placement)

            custom_dialog = CustomDialog(title="Edit text", message="Do you want to proceed?", main_widget=editor,
                                         parent=self, options=['Ok', 'Cancel'],
                                         auto_adjust=True)  # that is really very good --> I can do it like that
            # custom_dialog.adjustSize()
            result = custom_dialog.exec_()
            if result:
                image2d.annotations[0]=text_to_Edit

                # print('placement after', image2d.annotations[0].placement)
                # self.selected_shape[0].sync_text() # make sure the text is synced
                # print('in there')

                # in fact here I don't want to have the stuff
                # self.shapeChanged.emit()
                # self.selectionChanged.emit()
                # nothing special TODO --> just pass...


                if top_parent:
                    try:
                        top_parent.update()
                    except Exception:
                        pass

                self.update_text_rows.emit()
                self.set_current_selection(None)  # now the clone is the selection so I need to update it
                self.undo_redo_save_required.emit()
            # else:
            #
            #         # rejected -> restore default text
            #         # in fact this is more complex because if the user has changed
            #         # text_to_Edit.setText(text)
            #         pass

        # MEGA TODO --> somehow some fig shape changes are applied after that --> ideally I should freeze them or really clone the image so that I can edit it and do things in a smart way -−> MAYBE IT IS TIME TO IMPLEMENT CLONING OF ALL BUT THE IMAGE??? --> this bug also changes the shape and size of the group which is a big pb for the update medthod -−> I should get the size before that and reapply it -−> see how to do that but still ok for now
        # we store the key altered parameters of the image

        # in theory that should suffice but it does not seem to be the case --> no clue why -> I get it it is because the parent updates the shape meanwhile I edit this one and since I change the scale of it and its position, I cannot do anythiong

        # I can also force the top parent to reshape itslef to its initial size

        # i need get the top parent and update it


        # somehow this creates a bug --> I need to see why that is and how I can fix it in plenty of case I would also have to reedit the parent

        # self.freeze = False
        return

    def set_current_selection(self, shape):
        # if self.selected_shape == shape: # avoid doing this too many times
        #     return
        self.selected_shape = shape
        self.initial_position = None
        if shape is not None:
            if not isinstance(shape, list):
                self.initial_position = shape.topLeft()
            else:
                self.initial_position = []
                for shp in shape:
                    if shp is not None:
                        self.initial_position.append(shp.topLeft())
        self.selectionChanged.emit() # fire a selection changed

        if False:
            print('selected shape', self.selected_shape)
            try:
                print('dims', QRectF(self.selected_shape.getRect(all=True)))
                try:
                    # just for debug
                    print('dims', QRectF(self.selected_shape.boundingRect()))
                except Exception:
                    print('dims', self.selected_shape)
                    pass
            except Exception:
                try:
                    for shp in self.selected_shape:
                        print('dims', QRectF(shp.getRect(all=True)))
                        try:
                            # just for debug
                            print('dims', QRectF(shp.boundingRect()))
                        except Exception:
                            print('dims', shp)
                            pass
                except Exception:
                    pass

    def mousePressEvent(self, event):
        # CURRENTLY IT RESETS THE SELECTION AT THE END OF THE LOOP THAT IS NOT BAD (because if I had no free space I could not get rid of selection which is not good)!!! --> MAYBE KEEP IT LIKE THAT
        # c'est un peu confusant on a l'impression que la sel ne marche pas !!!
        # self.freeze = False
        self.dragging = False
        self.drawing = False
        self.firstPoint = event.position()
        self.lastPoint = event.position()
        self.lastPoint.setX(int(self.lastPoint.x() / self.scale))
        self.lastPoint.setY(int(self.lastPoint.y() / self.scale))
        point = QPointF(float(self.lastPoint.x()), float(self.lastPoint.y()))
        if event.button() == Qt.LeftButton:
            # print('before', self.selected_shape)
            # check if a shape is selected and only move that
            if event.modifiers() == Qt.ShiftModifier and self.selected_shape is not None:
                # range selection

                try:
                    # print('shift modifier selected')

                    # the idea here would be to select a range as in Excel/Calc

                    first_encounter = self.get_first_encounter_below_point(point)


                    # print('shift first_encounter',first_encounter, self.selected_shape)



                    # I then need to select the top parent of selected shape if not a list already and get its index then get the last index and select the whole range in between



                    top_parent = self.get_top_parent_of_shape(self.selected_shape)

                    # print('shift top_parent', top_parent)



                    range_bound2 = self.shapes_to_draw.index(first_encounter)
                    if top_parent is not None:
                        range_bound1 = self.shapes_to_draw.index(top_parent)
                    else:
                        range_bound1 = range_bound2
                    # else:
                    #     max_dist_range = 0
                    #     if isinstance(self.selected_shape, list):
                    #         for elm in self.selected_shape:
                    #             top_parent = self.get_top_parent_of_shape(elm)
                    #             if top_parent is not None:
                    #                 idx = self.shapes_to_draw.index(top_parent)
                    #                 if abs(idx-range_bound2)>max_dist_range:


                    # print('shift range', range_bound1, range_bound2)

                    self.selected_shape = list(self.shapes_to_draw[min(range_bound1,range_bound2): max(range_bound1, range_bound2)+1])

                    # print('shift updated selection', self.selected_shape)
                    if isinstance(self.selected_shape, list) and len(self.selected_shape)==1:
                        self.selected_shape=self.selected_shape[0]
                    self.set_current_selection(self.selected_shape)


                except Exception:
                    # no big deal if it fails
                    traceback.print_exc()
                    pass








            elif event.modifiers() == getCtrlModifier():
                # shape = None
                first_encounter = self.get_first_encounter_below_point(point)
                if first_encounter:
                    shapes_below_mouse = self.get_all_encounters_ordered_below_mouse_for_a_given_shape(first_encounter, point, append_shape_to_screen=True)

                    # print('shapes_below_mouse', shapes_below_mouse)
                    if shapes_below_mouse:
                        # print('in there 2233')
                        if self.selected_shape:
                            # print('in there 2233b')
                            tmp = self.selected_shape
                            if isinstance(self.selected_shape, list):
                                tmp = self.selected_shape[0]
                            # print('in there 2233c')
                            try:
                                shapes_below_mouse.remove(self.selected_shape)
                            except Exception:
                                pass
                            shape = find_first_object_of_type(shapes_below_mouse, type(tmp))
                            # print('in there 2233d')
                        else:
                            shape =self.selected_shape
                        if True:
                    # for shape in reversed(self.shapes_to_draw):
                    #     # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
                    #     if shape.contains(point):
                    #         # if shape not in self.selected_shape:  # avoid doublons
                    #             # self.selected_shape.append(shape)  # add shape to group
                    #             # if not isinstance(self.selected_shape, list):
                    #             #     self.selected_shape = [self.selected_shape]
                    #             print('self.selected_shape before append',self.selected_shape)
                                self.append_to_selection(shape)

                                # print('self.append_to_selection', self.selected_shape) # ÇA MARCHE ÇA AJOUTE ET DESAJOUTE --> ERREUR EST AILLEURS

                                self.set_current_selection(self.selected_shape)
                                logger.debug('adding shape to group')
                                # break

                # do it in a smarter way to allow only sel of the same type in the case of multi selection
            else:
                for shape in reversed(self.shapes_to_draw):
                    # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
                    if shape.contains(point):
                        self.drawing = True
                        break

            # we reset selection if mouse is not in the selected shape
            if self.selected_shape is not None and not isinstance(self.selected_shape, list) and (not self.selected_shape.contains(point) and not event.modifiers() == getCtrlModifier()):
                # print('resetting sel in there')
                self.set_current_selection(None)
                self.update()
            elif self.selected_shape is not None and isinstance(self.selected_shape, list) and not event.modifiers() == getCtrlModifier():
                # print('resetting sel in there 2')
                found = False
                for shp in  self.selected_shape:
                    if shp.contains(point):
                        found = True
                        break
                if not found:
                    self.set_current_selection(None)
                    self.update()

        elif event.button() == Qt.RightButton:

            # print('in right click press', self.selected_shape)

            # if no selection then create one not sure I should do that because it defavors the empty stuff --> think about it


            if self.selected_shape is None:
                self.selected_shape = self.get_shape_at_coord(point)
                self.set_current_selection(self.selected_shape)

                # print('in right click press', self.selected_shape)

                self.update()

            try:
                if not self.selected_shape.contains(point):
                    self.selected_shape = self.get_shape_at_coord(point)
                    self.set_current_selection(self.selected_shape)

                    # print('in right click press', self.selected_shape)

                    self.update()
            except Exception:
                pass

    # nb shall I get selection based on scale --> probably yes --> TODO implement that
    # def mousePressEvent(self, event):
    #     self.dragging = False
    #     if event.button() == Qt.LeftButton:
    #         self.drawing = True
    #         self.lastPoint = event.position()
    #         self.lastPoint.setX(int(self.lastPoint.x() / self.scale))
    #         self.lastPoint.setY(int(self.lastPoint.y() / self.scale))
    #
    #         # print('before', self.selected_shape)
    #         # check if a shape is selected and only move that
    #         for shape in reversed(self.shapes_to_draw):
    #             point = QPointF(float(self.lastPoint.x()), float(self.lastPoint.y()))
    #             # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
    #             if shape.contains(point):
    #
    #
    #
    #             # if shape.contains(self.lastPoint):
    #                 # logger.debug('you clicked shape:' + str(shape))
    #                 if self.selected_shape is None or not self.is_ctrl_modifier():
    #                     # selection has not changed --> ignoring changes
    #                     if isinstance(self.selected_shape, list) and shape in self.selected_shape:
    #                         return
    #                     if isinstance(self.selected_shape, list):
    #                         # check that click is not in master rect of selection
    #                         if get_master_bounds2(self.selected_shape).contains(self.lastPoint):
    #                             return
    #                     # check if an object is in
    #                     elements_below_click = self.get_all_inner_objects_at_position(shape, self.lastPoint)
    #                     print('elements_below_click',elements_below_click)
    #                     if elements_below_click and self.selected_shape in elements_below_click: # or if is inside --> need pool it out
    #                         # try:
    #                         #     some_object_iterator = iter(shape)
    #                         # except TypeError as te:
    #                         #     continue
    #                         # go deeper
    #                         print('going deeper in shape crappy still')
    #                         # for elm in shape:
    #                         #     # if shape is itslef iterable I need check further in until can't go deeper and then stop --> see how to do that --> do that in a nested way
    #                         #     # only do things if the shapes overlap otherwise skip
    #                         #     # if inner is selected need make it sticky
    #                         #     if elm.boundingRect().contains(self.lastPoint):
    #                         #         shape = elm # in fcat this is selection
    #                         #         self.selected_shape = shape # when I select it is moved but why is that so...
    #                         #         return # must not allow fusion when shape is contained within
    #
    #                         # or maybe use double click to go deeper --> would simplify a lot my code in fact !!! and makes total sense in fact --> see how that is implemented
    #
    #                         # print('$'*20, )
    #                         # selection = [type(obj) for obj in elements_below_click]
    #                         # print(selection)
    #
    #                         if self.selected_shape in elements_below_click:
    #                             idx = elements_below_click.index(self.selected_shape)
    #                             if idx == len(elements_below_click)-1:
    #                                 self.selected_shape = elements_below_click[0]  # when I select it is moved but why is that so...
    #                                 return
    #                             else:
    #                                 self.selected_shape =elements_below_click[idx+1]
    #                                 return
    #
    #                         # inner_shape = self.get_inner_shape(shape, self.selected_shape, self.lastPoint)
    #                         # print('#' * 20, type(shape), type(self.selected_shape), type(inner_shape))
    #                         # if inner_shape is not None:
    #                         #     self.selected_shape = inner_shape  # when I select it is moved but why is that so...
    #                         #     return # must not allow fusion when shape is contained within
    #
    #                         # if there is overlap need deep check
    #                         # easy to check if in if they have overlapping rects and also with
    #
    #                         # if sh
    #
    #                         # try:
    #                         #     some_object_iterator = iter(shape)
    #                         # except TypeError as te:
    #                         #     # print(shape, 'is not iterable')
    #                         #     # if object is not iterable --> need loop again
    #                         #     self.selected_shape = shape
    #
    #                     else:
    #                         self.selected_shape = shape
    #                     self.sticky('INIT')
    #                     return
    #                 else:
    #                     # print('in here')
    #                     self.append_to_selection(shape)
    #                     print(self.selected_shape)
    #                     self.sticky('INIT')
    #                     return

    def append_to_selection(self, shape):
        if shape is None:
            return
        if isinstance(self.selected_shape, list):
            # do not add the shape more than once to avoid weird issues
            if shape not in self.selected_shape:
                self.selected_shape.append(shape)
            else:
                self.selected_shape.remove(shape)
                if not self.selected_shape:
                    self.selected_shape = None
                elif len(self.selected_shape) == 1:
                    # back to a single shape, not a one-item multi-selection
                    self.selected_shape = self.selected_shape[0]
        else:
            if shape == self.selected_shape:
                self.selected_shape = None
                return
            self.selected_shape = [self.selected_shape, shape]
            while None in self.selected_shape:
                self.selected_shape.remove(None)
            if len(self.selected_shape)==1:
                self.selected_shape = self.selected_shape[0]

        # self.selected_shape = list(set(self.selected_shape)) # remove dupes

    def remove_sel(self):
        self.reset_position()
        update_required = self.selected_shape is not None
        self.selected_shape = None
        if update_required:
            self.update()

    def remove_all_empty_groups(self):
        if self.shapes_to_draw:
            for elm in reversed(self.shapes_to_draw):
                try:
                    if elm.isEmpty():
                        self.shapes_to_draw.remove(elm)
                except Exception:
                    pass

    def delete_selection(self):
        # print('TODO --> IMPLEMENT DELETE SEL') # -−> need update the drawing
        # get top parent and remove sel from it
        if self.selected_shape:
           if not isinstance(self.selected_shape, list):
               top_parent = self.get_top_parent_of_shape(self.selected_shape)
               try:
                   self.shapes_to_draw.remove(self.selected_shape)
               except Exception:
                   pass
               try:
                   top_parent.remove(self.selected_shape)
               except Exception:
                   pass
               if top_parent is not None and top_parent!=self.selected_shape:
                   top_parent.update()
               self.remove_all_empty_groups()
               self.selected_shape =None
               self.set_current_selection(None)
               self.update()
               self.update_size()

               # TODO also need to check if some things are empty and remove them if they are
           else:
               # print('#' * 25)
               # print('TODO --> IMPLEMENT DELETE SEL MULTI', self.selected_shape)

               for elm in self.selected_shape:
                   top_parent = self.get_top_parent_of_shape(elm)
                   # print('found top parent of',top_parent, 'shape', elm, 'vs',top_parent.content)
                   try:
                       self.shapes_to_draw.remove(elm)
                   except Exception:
                       pass
                   try:
                       top_parent.remove(elm)
                   except Exception:
                       pass
                   # print(top_parent == elm)
                   if top_parent is not None and top_parent != elm:
                       top_parent.update()
               self.remove_all_empty_groups()
               self.selected_shape = None
               self.set_current_selection(None)
               self.update()
               # print('#'*30)
               self.update_size()
           self.update_text_rows.emit()
           self.undo_redo_save_required.emit() # something was changed so it needs to be rebuilt
           self.force_update_store.emit()

    # def space_bar_pressed(self):
    #     print('TODO --> IMPLEMENT space bar press')  # -−> need update the drawing
    #     print('#'*20)
    #     print('__DEBUG__')
    #     print('self.selected_shape',self.selected_shape)
    #     print('self.shapes_to_draw',self.shapes_to_draw)
    #
    #     if self.shapes_to_draw:
    #         for shape in self.shapes_to_draw:
    #             try:
    #                 print(shape, shape.getRect(), shape.getRect(all=True))
    #             except:
    #                 pass
    #             try:
    #                 print(shape.content)
    #             except:
    #                 pass
    #     print('END __DEBUG__')
    #     print('-' * 20)

    def up_pressed(self):





        if self.selected_shape is None:
            return



        # print('UP PRESSED to implement')
        # print(self.selected_shape)
        top_parent = self.get_top_parent_of_shape(self.selected_shape)
        # print(top_parent)
        # now do the dynamic of the stuff
        # self.focus_required.emit()  # why that does not work

        if isinstance(self.selected_shape, Image2D) and self.selected_shape.isText and top_parent and top_parent.isText and top_parent!=self.selected_shape:
            return

        if top_parent:
            if top_parent == self.selected_shape:
                tmp = self.selected_shape
                if not isinstance(self.selected_shape, list):
                    tmp = [tmp]
                # indices = [i for i, x in enumerate(elm.content) if x in elements]
                indices = [self.shapes_to_draw.index(shape) for shape in tmp if shape in self.shapes_to_draw]
                self.shapes_to_draw = move_left(self.shapes_to_draw, indices)  # get indices
                # self.update()
                # self.update_text_rows.emit()
                # self.focus_required.emit()  # why that does not work
                try:
                    self.selected_shape.update()
                except Exception:
                    pass
                self.force_update_size_of_parent.emit(self.selected_shape)
                # self.set_current_selection(None)  # force update of its coords
                self.set_current_selection(self.selected_shape)  # force update of its coords
                # self.update_size()
            else:
                # print(top_parent)
                # now do the dynamic of the stuff
                top_parent.move_left(self.selected_shape)
                top_parent.update()
                self.force_update_size_of_parent.emit(top_parent)
                # self.update()
                # self.update_size()
                # self.update_text_rows.emit()
                # self.focus_required.emit()  # why that does not work
                # self.set_current_selection(None)  # force update of its coords
                self.set_current_selection(self.selected_shape)  # force update of its coords
            # Reset the timer to ensure that it starts counting from zero
            self.timer.stop()
            self.timer.start()

        self.focus_required.emit() # why that does not work
        self.update_text_rows.emit()


    def down_pressed(self):
        if self.selected_shape is None:
            return
            # print('DOWN PRESSED to implement')
        # print(self.selected_shape)
        top_parent = self.get_top_parent_of_shape(self.selected_shape) # the pb is that it does not always finds them # if several parents -−> allow something else
        # print(top_parent)
        # self.focus_required.emit()  # why that does not work

        if isinstance(self.selected_shape, Image2D) and self.selected_shape.isText and top_parent and top_parent.isText and top_parent!=self.selected_shape:
            return

        if top_parent:
            if top_parent == self.selected_shape:
                tmp = self.selected_shape
                if not isinstance(self.selected_shape, list):
                    tmp = [tmp]
                # indices = [i for i, x in enumerate(elm.content) if x in elements]
                indices = [self.shapes_to_draw.index(shape) for shape in tmp if shape in self.shapes_to_draw]
                self.shapes_to_draw = move_right(self.shapes_to_draw, indices)  # get indices
                # self.update()
                # self.update_text_rows.emit()
                # self.focus_required.emit()  # why that does not work
                #
                # self.update_size()
                try:
                    self.selected_shape.update()
                except Exception:
                    pass
                self.force_update_size_of_parent.emit(self.selected_shape)
                # self.set_current_selection(None)  # force update of its coords
                self.set_current_selection(self.selected_shape)  # force update of its coords
            else:
                # print(top_parent)
                # now do the dynamic of the stuff

                    top_parent.move_right(self.selected_shape)
                    top_parent.update()
                    self.force_update_size_of_parent.emit(top_parent)
                    # self.update()
                    # self.update_size()
                    # self.update_text_rows.emit()
                    # self.focus_required.emit()  # why that does not work
                    # self.set_current_selection(None)  # force update of its coords
                    self.set_current_selection(self.selected_shape)  # force update of its coords
                # Reset the timer to ensure that it starts counting from zero

            self.timer.stop()
            self.timer.start()

        self.focus_required.emit()
        self.update_text_rows.emit()

    def emit_undo_redo_save_required(self):
        # Emit the undo_redo_save_required signal
        self.undo_redo_save_required.emit()
        self.set_current_selection(self.selected_shape)  # force update of its coords
        self.timer.stop()

    def left_pressed(self):
        self.up_pressed()

    def right_pressed(self):
        self.down_pressed()

    def mouseMoveEvent(self, event):
        if self.selected_shape is None and self.drawing:
            point = event.position()
            point.setX(self.lastPoint.x() / self.scale)
            point.setY(self.lastPoint.y() / self.scale)
            # print('null shape')
            for shape in reversed(self.shapes_to_draw):
                # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
                if shape.contains(point):
                    # all_shapes_below_the_mouse_at_drop.append(shape)
                    self.set_current_selection(shape)
                    # self.selected_shape = shape
                    break
        # almost there

        # print('in mouse move event', event,  event.button() == Qt.LeftButton, event.button())

        if self.selected_shape is not None and (event.buttons() & Qt.LeftButton): # DEV NOTE --> keep --> this is because the mouse move does not detect buttons just mouse move so event.button() returns MouseButton.NoButton this allows to restrict DND to only left click!!!
            # print('dragging')
            self.dragging = True
            trans = event.position()
            trans.setX(trans.x() / self.scale)
            trans.setY(trans.y() / self.scale)
            if isinstance(self.selected_shape, list):
                for element in self.selected_shape:
                    element.translate(trans - self.lastPoint)
            else:
                # self.selected_shape.translate(trans.x() - self.lastPoint.x(),trans.y() - self.lastPoint.y()) # dirty hack to handle the stuff !!!
                try:
                    self.selected_shape.translate(trans- self.lastPoint) # dirty hack to handle the stuff !!!
                except Exception:
                    traceback.print_exc()
            # need update bounds of the panel
            # self.updateBounds()

            self.update_size(trans) # maybe also I need to make sure that the select

        self.lastPoint = event.position()
        self.lastPoint.setX(self.lastPoint.x() / self.scale)
        self.lastPoint.setY(self.lastPoint.y() / self.scale)

        # print('updating')
        self.update()

    def get_shape_at_coord(self, coords, ignore_cur_sel=True):
        # this makes sure the returned object is in the list
        # need remove both objects from the list and return one new object instead
        if isinstance(coords, QPoint):
            coords = QPointF(float(coords.x()), float(coords.y()))
        for shape in reversed(self.shapes_to_draw):
            if shape.contains(coords):
            # if shape.contains(coords.x(),coords.y()):
            # if shape.contains(float(coords.x()), float(coords.y())):
            # if shape.contains(coords):
                if ignore_cur_sel and (shape == self.selected_shape or (
                        isinstance(self.selected_shape, list) and shape in self.selected_shape)):
                    continue
                else:
                    return shape

    def reset_position(self):
        # print('in there', self.initial_position)
        if self.selected_shape is not None and self.initial_position is not None:
            if not isinstance(self.initial_position, list):
                self.selected_shape.setTopLeft(self.initial_position)
                # self.initial_position = None
            else:
                for iii,pos in enumerate(self.initial_position):
                    self.selected_shape[iii].setTopLeft(pos)
                # self.initial_position = None

    def get_all_shapes_below_point(self, point):
        all_shapes_below_the_mouse_at_drop = []

        for shape in reversed(self.shapes_to_draw):
            # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
            if shape.contains(point):
                all_shapes_below_the_mouse_at_drop.append(shape)

        if not all_shapes_below_the_mouse_at_drop:
            return None
        return all_shapes_below_the_mouse_at_drop

    def get_first_encounter_below_point(self,point):
        for shape in reversed(self.shapes_to_draw):
            # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
            if shape.contains(point):
                return shape
        return None

    def get_first_encounter_below_point_that_is_not_dragged_shape(self, point):
        for shape in reversed(self.shapes_to_draw):
            if shape == self.selected_shape:
                continue
            # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):
            if shape.contains(point):
                return shape
        return None

    def get_direct_parent_containing_element(self, encounters_below_mouse, element_to_find, return_all_encounters=True):
        # in fact one of the elements below the mouse is the parent of element_to_find -−> find it and then use it
        all_encounters = []
        for elm in encounters_below_mouse:
            if element_to_find == elm:
                continue
            if element_to_find in elm:
                if not return_all_encounters:
                    return elm
                else:
                    all_encounters.append(elm)
        return all_encounters

    # can I make a list version that allows for swapping
    def get_all_encounters_ordered_below_mouse_for_a_given_shape(self, shape_to_screen, point, append_shape_to_screen=True):
        if shape_to_screen is None:
            return None
        element_below_point = []
        if append_shape_to_screen:
            element_below_point.append(shape_to_screen)
        try:
            while is_iterable(shape_to_screen):
                # print('dabu',shape_to_screen)
                # cur_shape = shape
                nothing_found=True # to prevent infinite loop but maybe there is a better strategy!
                for elm in shape_to_screen:

                    # the contains of vectorial objects does not work !!! --> see how to do!!!
                    if elm.contains(point):
                        # cur_shape = elm
                        shape_to_screen = elm
                        # self.set_current_selection(shape)
                        element_below_point.append(shape_to_screen)
                        # break
                        nothing_found=False
                if nothing_found:
                    break
        except Exception:
            pass
        if not element_below_point:
            return None
        return element_below_point

    def get_top_parent_of_shape(self, shape_to_check):
        # if is_iterable(shape_to_check):
        if shape_to_check is None:
            return None

        if shape_to_check in self.shapes_to_draw:
            # shape in main list
            return shape_to_check
        # print('checking', shape_to_check)
        for shape in self.shapes_to_draw:
            # if shape == shape_to_check:
            #     # print('equals shape', shape, shape_to_check, shape==shape_to_check)
            #     return shape_to_check
            if shape.contains(shape_to_check):
                # print('shape contained', shape, shape_to_check, shape==shape_to_check, shape.contains(shape_to_check))
                return shape
        return None

    def group_context_menu(self, menu=None, event=None):

        is_left_click=True
        if event is not None:
            if event.button()==Qt.RightButton:
                is_left_click=False

        if menu is None:
            self.contextMenu = QMenu(self)
            ignore = self.contextMenu.addAction("Ignore")

            if not is_left_click:
                # Add a separator
                self.contextMenu.addSeparator()

                duplicate = self.contextMenu.addAction("Duplicate Selection")
                duplicate.triggered.connect(self.duplicate)

        else:
            self.contextMenu = menu

        if not is_left_click:
            # Add a separator
            self.contextMenu.addSeparator()
            edit = self.contextMenu.addAction("Edit Group (orientation/space)")
            edit.triggered.connect(self.update_group_layout)

            # Add a separator
            self.contextMenu.addSeparator()
            add_empty = self.contextMenu.addAction("Add Empty image to the group")
            add_empty.triggered.connect(self.on_add_empty_image_clicked)


        if self.selected_shape in self.shapes_to_draw and not is_left_click:
            # Add a separator
            self.contextMenu.addSeparator()

            add_text_row_above = self.contextMenu.addAction("Add text labels above the row")
            add_text_row_above.triggered.connect(lambda: self.associate_text_row(sensitivity='below'))

            add_text_row_below = self.contextMenu.addAction("Add text labels below the row")
            add_text_row_below.triggered.connect(lambda: self.associate_text_row(sensitivity='above'))

        if isinstance(self.selected_shape, Group) and not self.selected_shape.isText and not is_left_click:

            # print('testing', self.selected_shape.isText)
            # Add a separator
            self.contextMenu.addSeparator()

            add_text_label_first = self.contextMenu.addAction("Add text label left/top of row/col")
            add_text_label_first.triggered.connect(self.add_text_label_first)

            add_text_label_last = self.contextMenu.addAction("Add text label right/bottom of row/col")
            add_text_label_last.triggered.connect(self.add_text_label_last)


    def add_text_label(self, index=0):
        if isinstance(self.selected_shape, Image2D):
            # Standalone image: wrap it in a new X-oriented group with the label
            txt = Image2D(width=512, height=256, annotations=[
                TAText2D(f'double click to edit', placement='center_h center_v', range=None, text_orientation='-Y')],
                isText=True)
            if index >= 0:
                new_grp = Group(txt, self.selected_shape, orientation='X', space=self.space)
            else:
                new_grp = Group(self.selected_shape, txt, orientation='X', space=self.space)
            idx = self.shapes_to_draw.index(self.selected_shape)
            self.shapes_to_draw[idx] = new_grp
            self.force_update_size_of_parent.emit(new_grp)
            self.set_current_selection(new_grp)
            self.update()
            self.update_size()
            self.update_letters_required.emit()
            self.update_text_rows.emit()
            self.undo_redo_save_required.emit()

        elif isinstance(self.selected_shape, Group):

            orientation = self.selected_shape.orientation
            txt = Image2D(width=512, height=256, annotations=[
                    TAText2D(f'double click to edit', placement='center_h center_v', range=None, text_orientation='-Y' if orientation == 'X' else 'X')],
                                                              isText=True)

            # print('init orientation', orientation, '-Y' if orientation == 'X' else 'X')
            if index>=0:
                self.selected_shape.content.insert(index,txt)
            else:
                self.selected_shape.content.append( txt)

            self.selected_shape.update()

            top_parent = self.get_top_parent_of_shape(self.selected_shape)

            if top_parent:
                top_parent.update()
                self.force_update_size_of_parent.emit(top_parent)

            self.update()
            self.update_size()
            self.update_text_rows.emit()
            self.undo_redo_save_required.emit()

    def add_text_label_first(self):
        self.add_text_label(index=0)

    def add_text_label_last(self):
        self.add_text_label(index=-1)
    def associate_text_row(self, sensitivity='below'):
        # self.selected_shape

        # print('associate text called --> ACTION REQUIRED')
        # print(self.selected_shape, sensitivity)

        # can only be done with parent shape --> if not parent --> do not put this --> maybe do not even put that then

        # if self.selected_shape in self.shapes_to_draw:
        labels = []

        if isinstance(self.selected_shape, Image2D):
            # Standalone image: create a single label
            labels.append(Image2D(width=512, height=256, annotations=[TAText2D(f'double click to edit', placement='center_h center_v', range=[0, 0])], isText=True))
        else:
            orientation = self.selected_shape.orientation
            non_text_idx = 0
            for elm in self.selected_shape:
                if elm.isText:  # skip side labels — only label actual images/groups
                    continue
                labels.append(Image2D(width=512, height=256, annotations=[TAText2D(f'double click to edit', placement='center_h center_v', range=[non_text_idx, non_text_idx])], isText=True))
                non_text_idx += 1
                if orientation == 'Y': # only add one label if stuff below is y direction ???
                    break

        if not labels:
            return
        txt_row = Group(*labels, isText=sensitivity)

        idx = self.shapes_to_draw.index(self.selected_shape)

        if 'low' in sensitivity:
            self.shapes_to_draw.insert(idx, txt_row)
        else:
            try:
                self.shapes_to_draw.insert(idx+1, txt_row)
            except Exception:
                self.shapes_to_draw.append(txt_row)

        self.update()
        self.update_size()
        self.update_text_rows.emit()
        self.undo_redo_save_required.emit()



        #
        #
        #     print('this will work')
        # else:
        #     print('this will NOT work!!!')



    def update_group_layout(self):
        main = PanelOrRow(self.selected_shape, hide_size=True)
        custom_dialog = CustomDialog(title="Row Or Column",
                                     message=None,
                                     # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                     main_widget=main, options=['Ok', 'Cancel'], parent=self, auto_adjust=True)
        if custom_dialog.exec_() == QDialog.Accepted:
            orientation, _, space = main.get_parameters()



            if self.selected_shape.orientation == orientation and self.selected_shape.space == space:
                # nothing to be done
                # print('same as current settings -> ignoring group change')
                return

            # print('é' * 32)
            # print(self.selected_shape.orientation, orientation)
            # print(self.selected_shape.size)
            # print(self.selected_shape.getRect())
            # print('é' * 32)
            #
            # if self.selected_shape.orientation != orientation:
            #     if orientation==Y
            #     self.selected_shape.size =


            self.selected_shape.orientation = orientation
            self.selected_shape.space = space
            self.selected_shape.update()
            # I need to set it to a given size


            set_to_width(self.selected_shape, self.selected_shape.size)

            top_parent = self.get_top_parent_of_shape(self.selected_shape)
            if top_parent:
                # top_parent.update()
                # set_to_width(top_parent, top_parent.size)
                self.force_update_size_of_parent.emit(top_parent)

            # self.selected_shape = None
            self.update_size()
            self.update()


            self.update_text_rows.emit()
            self.undo_redo_save_required.emit()

            # no clue why but this is mandatory to reset the selection -> keep it like that maybe
            self.set_current_selection(None)
            # self.selectionChanged.emit()
            # self.selectionUpdated()


    # def add_as_new_row(self, shape_to_extrude, top_parent_of_that_shape):
    #     print('ADD AS NEW ROW/EXTRUDE CALLED -> ACTION REQUIRED',shape_to_extrude, top_parent_of_that_shape )
    #
    #     if top_parent_of_that_shape != shape_to_extrude:
    #         top_parent_of_that_shape.remove(shape_to_extrude)
    #         top_parent_of_that_shape.update()
    #
    #     self.shapes_to_draw.append(shape_to_extrude)
    #
    #     self.update()
    #     self.update_size()

    def raise_exception(self):
        try:
            raise Exception('NOT IMPLEMENTED YET −−> TODO')
        except Exception:
            traceback.print_exc()


    def duplicate_sel(self):
        self.duplicate(self.selected_shape)

    def on_add_empty_image_clicked(self):
        # Create an ImageParametersWidget
        main = EmptyImageParametersWidget() # TODO --> maybe offer associate a script to the image there
        custom_dialog = CustomDialog(title="Add empty image", message=None,
                                     # main_widget=main, options=['Ok', 'Cancel'], parent=self)
                                     main_widget=main, options=['Ok','Cancel'], parent=self, auto_adjust=True)
        if custom_dialog.exec_() == QDialog.Accepted:
            # print('add empty image --> TODO --> implement that --> ACTION REQUIRED')

            width, height = main.get_parameters()
            empty_img = Image2D(None, width=width, height=height)
            if isinstance(self.selected_shape, Group):
                self.selected_shape.content.append(empty_img)
                top_parent = self.get_top_parent_of_shape(self.selected_shape)
                if top_parent is not None:
                    self.set_current_selection(top_parent)
                else:
                    self.set_current_selection(self.selected_shape)
            else:
                self.shapes_to_draw.append(empty_img)
                self.set_current_selection(self.shapes_to_draw[-1])

            self.update()
            self.update_letters_required.emit()
            self.update_text_rows.emit()
            self.focus_required.emit()
            self.force_update_size_of_parent.emit(self.selected_shape)
            self.update()
            self.undo_redo_save_required.emit()


            # make it add an empty image --> should be easy


    # def default_context_menu(self, menu=None):
    #     if menu is None:
    #         self.contextMenu = QMenu(self)
    #         ignore = self.addAction("Ignore")  # no need for ignore here because the user wanted this
    #     else:
    #         self.contextMenu = menu
        #
        # add_empty = self.contextMenu.addAction("Add Empty Image")
        # add_empty.triggered.connect(self.on_add_empty_image_clicked)

        # maybe do a menu for the images such as edit

    # def add_image_from_an_external_source_context_menu(self, menu=None):
    #     if menu is None:
    #         self.contextMenu = QMenu(self)
    #         ignore = self.contextMenu.addAction("Ignore")
    #     else:
    #         self.contextMenu = menu
    #
    #     # add_at_the_end.triggered.connect(self.add_image)
    #
    #     # Add a separator
    #     self.contextMenu.addSeparator()
    #
    #     add_at_the_end = self.addAction("Add as a new row/col at the end of the figure")
    #     add_at_the_end.triggered.connect(self.add_image)
    #
    #     if self.selected_shape:
    #         if not isinstance(self.selected_shape, list):
    #             if isinstance(self.selected_shape, Group):
    #                 add_to_selected_group = self.contextMenu.addAction("Add to selected group")
    #                 add_to_selected_group.triggered.connect(self.raise_exception)
    #             if isinstance(self.selected_shape, Image2D):
    #                 if len(self.list) == 1:
    #                     replace_selected_image = self.contextMenu.addAction(
    #                         "Replace selected image with dropped image")
    #                     replace_selected_image.triggered.connect(self.raise_exception)
    #
    #             # TODO --> maybe add other behaviours --> maybe see with the other users how to do that
    #             # Connect the triggered signal to a lambda function that raises an exception
    #             # add_to_selected_group.triggered.connect(lambda:raise Exception('An error occurred'))
    #



    def get_all_shapes_involved_in_DND_process_by_mouse_position(self,event,point=None):

        if point is None:

            # print('redefining position')

            lastPoint = event.position()




            lastPoint.setX(int(lastPoint.x() / self.scale))
            lastPoint.setY(int(lastPoint.y() / self.scale))

            point = QPointF(float(lastPoint.x()), float(lastPoint.y()))


        if isinstance(point, QPoint):
            point = QPointF(point)




        # print('neo stuff5', point)
        # by combining all of these I should be able to do any possible actions -−> I would have to ask what to do ???

        # maybe when dragging give an id to each element possible combinations (see how to ask what to do)
        all_shapes_below = self.get_all_shapes_below_point(point)
        first_encounter_below = self.get_first_encounter_below_point(point)
        drop_target = self.get_first_encounter_below_point_that_is_not_dragged_shape(point)
        # first_encounter_that_is_not_dragged_shape = self.get_first_encounter_that_is_not_dragged_shape( drop_target)
        # print('first_encounter_that_is_not_dragged_shape', first_encounter_that_is_not_dragged_shape)
        all_encounters_in_shape_below_mouse = self.get_all_encounters_ordered_below_mouse_for_a_given_shape(drop_target,
                                                                                                            point,
                                                                                                            append_shape_to_screen=True)

        all_encounters_of_sel_shape_below_mouse = self.get_all_encounters_ordered_below_mouse_for_a_given_shape(
            self.selected_shape, point, append_shape_to_screen=True)

        top_parent_of_sel = self.get_top_parent_of_shape(self.selected_shape)

        immediate_parent_of_sel = get_parent_of_obj(self.selected_shape, top_parent_of_sel)

        top_parent_of_drop_target = self.get_top_parent_of_shape(drop_target)

        if __DEBUG_SELECTION__:
            print('*' * 30)
            print('-->self.selected_shape', self.selected_shape)
            print('-->all_shapes_below', all_shapes_below)
            print('-->first_encounter_below', first_encounter_below)
            print('-->drop_target', drop_target)
            print('-->all_encounters_in_shape_below_mouse', all_encounters_in_shape_below_mouse)
            print('-->all_encounters_of_sel_shape_below_mouse', all_encounters_of_sel_shape_below_mouse)
            print('-->top_parent_of_sel', top_parent_of_sel, self.selected_shape)
            print('-->immediate_parent_of_sel', immediate_parent_of_sel)
            print('-->top_parent_of_drop_target', top_parent_of_drop_target)
            print('top_parent_of_sel==top_parent_of_drop_target', top_parent_of_sel == top_parent_of_drop_target,
                  top_parent_of_drop_target)
            try:
                print('content of top_parent_of_sel', top_parent_of_sel.content)
            except Exception:
                pass
            try:
                print('content of top_parent_of_drop_target', top_parent_of_drop_target.content)
            except Exception:
                pass
            print('#' * 30)

        return all_shapes_below, first_encounter_below, drop_target, all_encounters_in_shape_below_mouse, all_encounters_of_sel_shape_below_mouse, top_parent_of_sel, immediate_parent_of_sel, top_parent_of_drop_target



    def update_context_menu_according_to_selection(self, event,point=None):

        all_shapes_below, first_encounter_below, drop_target, all_encounters_in_shape_below_mouse, all_encounters_of_sel_shape_below_mouse, top_parent_of_sel, immediate_parent_of_sel, top_parent_of_drop_target = self.get_all_shapes_involved_in_DND_process_by_mouse_position(event, point=point)

        self.contextMenu = QMenu(self)

        # there is a bug there

        # if self.selected_shape is not None:  # do not allow complex dnd and combination when multi selection is on
        if True: #self.selected_shape is not None:  # do not allow complex dnd and combination when multi selection is on
            # print('neo stuff6')
            # action = None
            action = self.internal_DND_context_menu(event, immediate_parent_of_sel, all_shapes_below,
                                                    first_encounter_below, drop_target,
                                                    all_encounters_in_shape_below_mouse,
                                                    all_encounters_of_sel_shape_below_mouse, top_parent_of_sel,
                                                    top_parent_of_drop_target)
            # if drop_target is not None:
            #     if self.selected_shape:
            #         action = self.internal_DND_context_menu(event)
            # elif drop_target is None and self.selected_shape not in self.shapes_to_draw:
            #     action = self.internal_DND_context_menu(event)

            if action is not None and not action.text().lower() == 'ignore':
                pass
                self.undo_redo_save_required.emit()
                self.update_text_rows.emit()
                # do I need to store stuff possibly yes

            else:
                self.reset_position()
                self.update_size()
            # print('-' * 30)



    def mouseReleaseEvent(self, event):
        # self.selected_shape = None # we don't want to do that




        # right click does not reach that --> check mousepressed

        # TODO reset if nothing is done
        # if self.freeze:
        #     return




        if False:
            print('%'*40)
            print('entering mouse release')


            if event.button():
                if event.button() == Qt.LeftButton:
                    print('left click')
                else:
                    print('right click')


            print('self.selected_shape beginning',self.selected_shape)

        if event.button():
            self.contextMenu = QMenu(self) # we need to reset the context menu otherwise the results may be completely wrong





            self.lastPoint = event.position()
            self.lastPoint.setX(int(self.lastPoint.x() / self.scale))
            self.lastPoint.setY(int(self.lastPoint.y() / self.scale))

            point = QPointF(float(self.lastPoint.x()), float(self.lastPoint.y()))



            # print('dragging', self.lastPoint, sqqsqsdqsd)



        # firt we need to handle the selection then we'll see what we do !!!
        if event.button() == Qt.LeftButton:
            # print('mouse left click')
            # assuming drop --> check all the main objects it cna be dropped onto

            # all shapes below mouse at drop
            # print('mouse released with sel', self.selected_shape)

            if self.dragging:
                # print('RESETTING POSITION')

                # self.dragging = False
                # all_shapes_below_the_mouse_at_drop = self.get_all_shapes_below_point(point)

                # when I drag I should always draw the selection last so that it always appears even if not first

                # depending on the input type I may need to
                # self.reset_position()
                # self.update_size()
                # self.selected_shape =None # somehow this helps
                pass
            else:
                # print('SELECTING A NEW SHAPE AFTER!!!')
                if self.selected_shape is not None and not isinstance(self.selected_shape,
                                                                      list) and self.selected_shape.contains(
                        point):  # should be done only if not dragging
                    if not self.dragging:

                        # do I REALLY NEED THAT ????

                        # print('going deeper2')
                        if is_iterable(self.selected_shape):
                            # if self.selected_shape == cur_sel:
                            # need go deeper
                            for elm in self.selected_shape:
                                if elm.contains(point):
                                    # self.selected_shape = elm
                                    # print('selected shape', self.selected_shape)
                                    self.reset_position()
                                    self.set_current_selection(elm)
                                    # self.reset_position()
                                    self.update_size()
                                    self.update()
                                    break

                    # print('neo stuff2')

                else:
                    # print('SELECTING A NEW SHAPE AFTER2!!!')
                    # if all_shapes_below_the_mouse_at_drop:
                    #     # self.selected_shape=
                    #     self.set_current_selection(all_shapes_below_the_mouse_at_drop[0])
                    # print('neo stuff3')
                    if self.drawing:
                        # print('neo stuff4')
                        self.drawing = False
                        for shape in reversed(self.shapes_to_draw):
                            # if shape.contains(int(self.lastPoint.x()), int(self.lastPoint.y())):

                            # if self.selected_shape in cur_sel:  # nb I need infinite recursion here otherwise that will fail
                            #     if is_iterable(self.selected_shape):
                            #         for elm in self.selected_shape:
                            #             # self.selected_shape = elm
                            #             self.set_current_selection(elm)
                            #             return

                            if shape.contains(point):
                                # print('NEO SELECTED SHAPE', shape)

                                cur_sel = shape

                                self.reset_position()
                                self.set_current_selection(cur_sel)
                                self.update_size()
                                self.update()
                                break
            # print('before', self.selected_shape)
            # check if a shape is selected and only move that

            # print('action', action, action.text())

            # if event.button() == Qt.LeftButton:
            if True:
                # we are filtering events by distance
                dist = distance(self.firstPoint, event.position())

                # if dist < 20:
                #     print('too small distance --> ignoring')
                #     print('distance', dist)
                #     self.reset_position()
                #     self.update_size()
                #     self.update()
                #     return

            # print('self.selected_shape',self.selected_shape)
            if self.dragging and not isinstance(self.selected_shape, list) and dist>20:
                # print('neo stuff 5 bis')
                self.update_context_menu_according_to_selection(event,point)
            else:


                # print('neo stuff7', self.selected_shape, self.dragging, self.dragging and not isinstance(self.selected_shape, list))
                # is that even True ???
                # print('TODO WARN THAT THERE IS NO DND POSSIBLE WITH MULTIPLE SELECTION (-−> OR IMPLEMENT IT IN THE FUTURE BUT THAT WILL BE VERY HARD TODO)')
                # if multi drag and not doing anything with it then do that
                self.reset_position()
                # self.set_current_selection(cur_sel)
                self.update_size()
                self.update()

            # print('neo stuff8')
            self.reset_position()
            # depending on dropped shape --> allow or not an action to occur!!!
            # see also how to handle plots --> TODO
            self.update_size()
            # self.drawing = False
            self.update()
            # self.dragging = False

        else:
            # why is self.selected shape not reset
            # print('right click pressed',type(self.selected_shape), self.selected_shape)
            pass

        self.drawing = False
        self.dragging = False

        if event.button() != Qt.LeftButton:
            if self.contextMenu:
                if not self.contextMenu.actions():
                    # print('entering update_context_menu_according_to_selection')
                    # print('neo stuff 18')
                    self.update_context_menu_according_to_selection(event,point)
                    # print('empty here --> there is a pb')

        if False:
            print('quitting mouse release')
            print('%' * 40)

    def is_image_type(self, object):
        if isinstance(object, Group):
            return True
        # if isinstance(object, Column):
        #     return True
        if isinstance(object, Image2D):
            return True
        return False

    # this is ok but I may need to add buttons for it too...
    def send_to_back(self):
        if self.selected_shape is None:
            return
        if isinstance(self.selected_shape,list):
            for sel in self.selected_shape:
                # need change order in the list
                self.shapes_to_draw.remove(sel)
                self.shapes_to_draw.insert(0,sel)
        else:
            self.shapes_to_draw.remove(self.selected_shape)
            self.shapes_to_draw.insert(0, self.selected_shape)
        self.update()

    def move_to_front(self):
        if self.selected_shape is None:
            return
        if isinstance(self.selected_shape,list):
            for sel in self.selected_shape:
                # need change order in the list
                self.shapes_to_draw.remove(sel)
                self.shapes_to_draw.append(sel)
        else:
            self.shapes_to_draw.remove(self.selected_shape)
            self.shapes_to_draw.append(self.selected_shape)
        self.update()

    # ne marche pas --> faut tout hardcoder je pense
    # https://stackoverflow.com/questions/56542287/attempt-to-pickle-unknown-type-while-creating-a-deepcopy
    # https://stackoverflow.com/questions/10618956/copy-deepcopy-raises-typeerror-on-objects-with-self-defined-new-method/10622689#10622689
    def copy(self):
        if self.selected_shape is None:
            return
        if isinstance(self.selected_shape, list):
            for sel in self.selected_shape:
                cp = copy.deepcopy(sel)
                cp.translate(25, 25)
                self.shapes_to_draw.append(cp)
        else:
            # NB deep copy does not seem to work...
            cp = copy.deepcopy(self.selected_shape)
            cp.translate(25,25)
            self.shapes_to_draw.append(cp)
        self.update()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = MyWidget()

    # there seem to be errors --> need really check slowly !!!
    # reimplement selections in a smarter fashion

    demo = True
    if demo:
        shapes_to_draw = []

        # TODO I NEED TO REIMPLEMENT THAT PROPERLY SO THAT IT FITS IN SIZE

        # shapes_to_draw.append(Polygon2D(0, 0, 10, 0, 10, 20, 0, 20, 0, 0, color=0x00FF00))
        # shapes_to_draw.append(
        #     Polygon2D(100, 100, 110, 100, 110, 120, 10, 120, 100, 100, color=0x0000FF, fill_color=0x00FFFF,
        #               stroke=2))
        # shapes_to_draw.append(Line2D(0, 0, 110, 100, color=0xFF0000, stroke=3))
        # shapes_to_draw.append(Rect2D(200, 150, 250, 100, stroke=10, fill_color=0xFF0000))
        # shapes_to_draw.append(Ellipse2D(0, 50, 600, 200, stroke=3))
        # shapes_to_draw.append(Circle2D(150, 300, 30, color=0xFF0000, fill_color=0x00FFFF))
        # shapes_to_draw.append(PolyLine2D(10, 10, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        # shapes_to_draw.append(PolyLine2D(10, 10, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        # shapes_to_draw.append(Point2D(128, 128, color=0xFF0000, fill_color=0x00FFFF, stroke=0.65))
        # shapes_to_draw.append(Point2D(128, 128, color=0x00FF00, stroke=0.65))
        # shapes_to_draw.append(Point2D(10, 10, color=0x000000, fill_color=0x00FFFF, stroke=3))

        # shapes_to_draw.append(Rect2D(0, 0, 512, 512, color=0xFF00FF, stroke=6))
        img0 = Image2D('/E/Sample_images/counter/00.png')

        inset = Image2D('/E/Sample_images/counter/01.png')
        inset2 = Image2D('/E/Sample_images/counter/01.png')
        inset3 = Image2D('/E/Sample_images/counter/01.png')
        # inset.setToHeight(32)
        # check inset

        # scale_bar = ScaleBar(30, '<font color="#FF00FF">10µm</font>')
        # scale_bar.setTopLeft(0, 0)


        # scale_bar.set_scale(self.get_scale())
        # # scale_bar.setTopLeft(self.get_P1().x()+extra_space, self.get_P1().y()+extra_space)

        # can I add things to an image in a smart way

        # img0.add_object(scale_bar, Image2D.TOP_LEFT)
        # scale_bar0 = ScaleBar(30, '<font color="#FF00FF">10µm</font>')
        # scale_bar0.setTopLeft(0, 0)
        # img0.add_object(scale_bar0, Image2D.TOP_LEFT)
        # img0.add_object(inset3, Image2D.TOP_LEFT)

        # all seems fine and could even add insets to it --> not so hard I guess
        # check

        # see how to handle insets --> in a way they can be classical images and one should just determine what proportion of the parent image width they should occupy -->
        # need a boolean or need set fraction of orig --> jut one variable
        # maybe also need draw a square around it of a given size --> see how to do that ???

        # img0.add_object(TAText2D(text='<font color="#FF0000">top right</font>'), Image2D.TOP_RIGHT)
        # img0.add_object(TAText2D(text='<font color="#FF0000">top right2</font>'), Image2D.TOP_RIGHT)
        # img0.add_object(TAText2D(text='<font color="#FF0000">top right3</font>'), Image2D.TOP_RIGHT)

        # img0.add_object(inset,                        Image2D.BOTTOM_RIGHT)  # ça marche meme avec des insets mais faudrait controler la taille des trucs... --> TODO
        # img0.add_object(inset2, Image2D.BOTTOM_RIGHT)  # ça marche meme avec des insets mais faudrait controler la taille des trucs... --> TODO
        # img0.add_object(TAText2D(text='<font color="#FF0000">bottom right</font>'), Image2D.BOTTOM_RIGHT)
        # img0.add_object(TAText2D(text='<font color="#FF0000">bottom right2</font>'), Image2D.BOTTOM_RIGHT)
        # img0.add_object(TAText2D(text='<font color="#FF0000">bottom right3</font>'), Image2D.BOTTOM_RIGHT)

        # ask whether a border should be drawn for the inset or not ??? and ask for its width...

        # ça a l'air de marcher mais voir comment faire pour gérer

        # img0.add_object(TAText2D(text='<font color="#FF0000">bottom left1</font>'), Image2D.BOTTOM_LEFT)
        # img0.add_object(TAText2D(text='<font color="#FF0000">bottom left2</font>'), Image2D.BOTTOM_LEFT)
        # img0.add_object(TAText2D(text='<font color="#FF0000">bottom left3</font>'), Image2D.BOTTOM_LEFT)

        # seems to work --> just finalize things up...

        # img0 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # size is not always respected and that is gonna be a pb but probably size would be ok for journals as they would not want more than 14 pt size ????

        # ci dessous la font size marche mais je comprend rien ... pkoi ça marche et l'autre marche pas les " et ' ou \' ont l'air clef...
        # in fact does not work font is super small
        # img0.setLetter(TAText2D(text='<font face="Comic Sans Ms" size=\'12\' color=yellow ><font size=`\'12\'>this is a <br>test</font></font>'))
        # img0.setLetter(TAText2D(text='<font face="Comic Sans Ms" color=yellow ><font size=12 >this is a <br>test</font></font>'))
        # img0.setLetter(TAText2D("<p style='font-size: large; font-color: yellow;'><b>Serial Number:</b></p> "))
        # a l'air de marcher mais à tester
        # img0.setLetter(TAText2D('<html><body><p><font face="verdana" color="yellow" size="2000">font_face = "verdana"font_color = "green"font_size = 3</font></html>'))

        # try that https://www.learnpyqt.com/examples/megasolid-idiom-rich-text-editor/
        # img0.setLetter(TAText2D(text='<html><font face="times" size=3 color=yellow>test</font></html>'))
        # img0.setLetter(TAText2D(text="<p style='font-size: 12pt; font-style: italic; font-weight: bold; color: yellow; text-align: center;'> <u>Don't miss it</u></p><p style='font-size: 12pt; font-style: italic; font-weight: bold; color: yellow; text-align: center;'> <u>Don't miss it</u></p>"))

        # this is really a one liner but a bit complex to do I find
        # chaque format different doit etre dans un span different --> facile
        # ça marche mais voir comment faire ça
        # img0.setLettering(TAText2D(
        #     text='<p style="text-align:left;color: yellow">This text is left aligned <span style="float:right;font-style: italic;font-size: 8pt;"> This text is right aligned </span><span style="float:right;font-size: 4pt;color:red"> This text is another text </span></p>'))
        # img0.setLettering('<font color="red">A</font>')
        # letter
        # img0.annotation.append(Rect2D(88, 88, 200, 200, stroke=3, color=0xFF00FF))
        # img0.annotation.append(Ellipse2D(88, 88, 200, 200, stroke=3, color=0x00FF00))
        # img0.annotation.append(Circle2D(33, 33, 200, stroke=3, color=0x0000FF))
        # img0.annotation.append(Line2D(33, 33, 88, 88, stroke=3, color=0x0000FF))
        # img0.annotation.append(Freehand2D(10, 10, 20, 10, 20, 30, 288, 30, color=0xFFFF00, stroke=3))
        # img0.annotation.append(PolyLine2D(10, 10, 20, 10, 20, 30, 288, 30, color=0xFFFF00, stroke=3))
        # img0.annotation.append(Point2D(128, 128, color=0xFFFF00, stroke=6))
        # everything seems to work but do check

        img1 = Image2D('/E/Sample_images/counter/01.png')
        # img1 = Image2D('D:/dataset1/unseen/focused_Series012.png')
        # img1.setLetter(TAText2D(text="<font face='Comic Sans Ms' size=16 color='blue' >this is a <br>test</font>"))
        # ça ça marche vraiment en fait --> use css to write my text instead of that

        # ça ça a l'air de marcher --> pas trop mal en fait du coup
        # ça a l'air de marcher maintenant --> could use that and do a converter for ezfig ???
        # img1.setLetter(TAText2D(text="<span style='font-size: 12pt; font-style: italic; font-weight: bold; color: yellow; paddind: 20px; text-align: center;'> <u>Don't miss it</u></span><span style='font-size: 4pt; font-style: italic; font-weight: bold; color: #00FF00; paddind: 3px; text-align: right;'> <u>test2</u></span>"))

        # TODO need remove <meta name="qrichtext" content="1" /> from the stuff otherwise alignment is not ok... TODO --> should I offer a change to that ??? maybe not
        test_text = '''
        </style></head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
        <p style="color:#00ff00;"><span style=" color:#ff0000;">toto</span><br />tu<span style=" vertical-align:super;">tu</span></p>
        '''
        # img1.setLettering(TAText2D(text=test_text))

        # background-color: orange;
        # span div et p donnent la meme chose par contre c'est sur deux lignes
        # display:inline; float:left # to display as the same line .... --> does that work html to svg
        # https://stackoverflow.com/questions/10451445/two-div-blocks-on-same-line --> same line for two divs

        img2 = Image2D('/E/Sample_images/counter/02.png')

        # crop is functional again but again a packing error
        img2.crop(left=60)
        img2.crop(right=30)
        img2.crop(bottom=90)
        img2.crop(top=60)
        # img2.crop(all=0) # reset crop
        # img2.crop(top=0) # reset crop --> seems ok
        # now seems ok --> see how to do that with figures/vector graphics ...
        # img2.crop(right=60)
        # img2.crop(bottom=60)
        img3 = Image2D('/E/Sample_images/counter/03.png')
        img4 = Image2D('/E/Sample_images/counter/04.png')
        img5 = Image2D('/E/Sample_images/counter/05.png')
        img6 = Image2D('/E/Sample_images/counter/06.png')
        img7 = Image2D('/E/Sample_images/counter/07.png')
        img8 = Image2D('/E/Sample_images/counter/08.png')

        # reference point is the original image and stroke should be constant irrespective of zoom --> most likely need the scaling factor too there
        # reference size is also the underlying original image --> TODO
        # img8.annotation.append(Line2D(0, 0, 110, 100, color=0xFF0000, stroke=3))
        # img8.annotation.append(Rect2D(60, 60, 100, 100, stroke=20, color=0xFF00FF))
        # need make the scale rese
        # img8.annotation.append(Ellipse2D(0, 50, 600, 200, stroke=3))

        img9 = Image2D('/E/Sample_images/counter/09.png')
        img10 = Image2D('/E/Sample_images/counter/10.png')
        # Data for plotting
        import numpy as np
        import matplotlib.pyplot as plt

        t = np.arange(0.0, 2.0, 0.01)
        s = 1 + np.sin(2 * np.pi * t)

        fig, ax = plt.subplots()
        ax.plot(t, s)

        ax.set(xlabel='time (s)', ylabel='voltage (mV)', title='About as simple as it gets, folks')
        ax.grid()

        # plt.show()
        # fig.savefig("test.png")
        # plt.show()
        # ça marche --> voici deux examples de shapes

        # first graph test --> TODO improve that
        graph2d = Image2D(fig)
        graph2d.crop(all=20)  # not great neither

        vectorGraphics = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/cartman.svg')

        # nb cropping marche en raster mais pas en svg output --> besoin de faire un masque d'ecretage --> pourrait aussi dessiner un rectangle de la meme taille de facon à le faire

        # TODO KEEP unfortunately cropping does not work when saved as svg but works when saved as raster...
        vectorGraphics.crop(left=10, right=30, top=10, bottom=10)
        animatedVectorGraphics = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/animated.svg')

        # bug cause shears the stuff --> would need crop the other dimension too to maintain AR
        animatedVectorGraphics.crop(left=30)  # , top=20, bottom=20


        # TODO -−> check the code but more slowly

        # self.shapes_to_draw.append(graph2d)

        # img10 = Image2D('/E/Sample_images/counter/10.png')
        # img2 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img3 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img4 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img5 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img6 = Image2D('D:/dataset1/unseen/focused_Series012.png')
        # img7 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img8 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img9 = Image2D('D:/dataset1/unseen/100708_png06.png')
        # img10 = Image2D('D:/dataset1/unseen/focused_Series012.png')

        # is row really different from a panel ??? probably not that different
        # row = img1 + img2

        # self.shapes_to_draw.append(row)
        # self.shapes_to_draw.append(row)

        # pkoi ça creerait pas plutot un panel
        # au lieu de creer une row faut creer des trucs
        # row2 = img4 + img5
        # fig = row / row2
        # fig = col(row, row2, width=512)# ça c'est ok
        # self.shapes_to_draw.append(fig)

        # TODO add image swapping and other changes and also implement sticky pos --> just need store initial pos

        # print(len(row))
        # for img in row:
        #     print(img.boundingRect())

        # fig.setToWidth(512) # bug is really here I do miss something but what and why

        # print('rows', len(fig))
        # for r in fig:
        #     print('bounding rect', r.boundingRect())
        #     print('cols in row', len(r))

        # self.shapes_to_draw.append(fig)

        # peut etre si rien n'est mis juste faire une row avec un panel
        row1 = Group(img0, img1, img2, graph2d,
                     animatedVectorGraphics)  # , graph2d, animatedVectorGraphics  # , img6, #, nCols=3, nRows=2 #le animated marche mais faut dragger le bord de l'image mais pas mal qd meme
        # see how I should handle size of graphs but I'm almost there

        # marche pas en fait car un truc ne prend pas en charge les figs
        # ça marche donc en fait tt peut etre un panel en fait


        # try adding a matplotlib plot there
        # Data for plotting


        col1 = Group(img4, img5, img6, vectorGraphics, orientation='Y')  # , vectorGraphics# , img6, img6, nCols=3, nRows=2,
        col2 = Group(img3, img7, img10, orientation='Y')
        #
        # col1.setLettering('<font color="#FFFFFF">A</font>')

        # col1+=col2
        # col1 /= col2
        # col1+=img3

        # print('mega begin', panel2.nCols, panel2.nRows, panel2.orientation, len(panel2.images), type(panel2), panel2.boundingRect())
        # print('mega begin', len(col1.images), type(col1), col1.boundingRect())

        # ok need increment and need see how to change the font of the stuff and bg color and fg color --> TODO but ok for now
        row2 = Group(img8, img9)
        # row2.setLettering('<font color="#FFFFFF">a</font>')

        # row1+=row2
        # row1 /= row2
        # row1+= img7

        # all seems fine now

        # panel = Panel(img0)# , img1, img2, img3)  # , img6, #, nCols=3, nRows=2

        # # marche pas en fait car un truc ne prend pas en charge les figs
        #
        # # ça marche donc en fait tt peut etre un panel en fait
        #
        # panel2 = Panel(img4, img5)  # ,

        # panel2.setToWidth(256)
        # panel3.setToWidth(256)
        # panel.setToWidth(256)

        # print(type(col1))

        # tt marche
        # should I put align top left or right...
        # should I put align top left or right...

        set_to_size(col1,512)  # creates big bugs now
        # panel3.setToWidth(512)
        # row1.setToWidth(512)
        set_to_size(row1, 512)  # creates big bugs now

        # c'est ici qu'il y a un pb de taille --> à fixer en fait --> TODO
        print('size row1', row1)

        # row1.setLettering('<font color="#FF00FF">B</font>')
        # row1.setLettering(' ') # remove letters
        # row1.setToWidth(1024)
        # ça a l'air de marcher...

        # it now seems ok
        # from batoolset.figure.alignment import alignRight, alignLeft, alignTop, alignBottom, alignCenterH, alignCenterV

        # alignLeft(row1, col1)
        # alignRight(row1, col1)
        # alignTop(row1, col1)
        # alignBottom(row1, col1)
        # alignCenterH(row1, col1)
        # alignCenterV(row1, col1)

        # can I add self to any of the stuff --> check --> if plus --> adds if divide --> stack it --> good idea and quite simple

        # fig = col(panel,panel2,panel3)

        # panel2+=panel
        # print(type(panel2))

        # panel2.setToHeight(512)
        # panel2.setToWidth(512)

        # all seems fine now --> see how I can fix things

        # panel2+=panel3 # bug here cause does not resize the panel properly
        # print('mega final', panel2.nCols, panel2.nRows, panel2.orientation, len(panel2.images), type(panel2), panel2.boundingRect(), panel.boundingRect())
        # print('mega final', len(col1.images), type(col1), col1.boundingRect(), row1.boundingRect())

        # on dirait que tt marche

        # maintenant ça marche mais reessayer qd meme
        # panel2.setToWidth(256) # seems still a very modest bug somewhere incompressible height and therefore ratio is complex to calculate for width with current stuff --> see how I can do --> should I ignore incompressible within stuff --> most likely yes... and should set its width and height irrespective of that
        # panel2.setToWidth(512) # seems still a very modest bug somewhere incompressible height and therefore ratio is complex to calculate for width with current stuff --> see how I can do --> should I ignore incompressible within stuff --> most likely yes... and should set its width and height irrespective of that

        # panel2.setToHeight(1024) #marche pas --> à fixer
        # panel2.setToHeight(128) # marche pas --> faut craiment le coder en fait --> voir comment je peux faire ça

        # marche pas non plus en fait --> bug qq part
        # panel2.setToHeight(82.65128578548527) # marche pas --> faut craiment le coder en fait --> voir comment je peux faire ça

        # panel += img7
        # panel -= img0
        # panel -= img1
        # panel -= img10
        # self.shapes_to_draw.append(panel)
        # panel2.setTopLeft(256, 300)

        # panel2.setTopLeft(512,0)
        # panel3.setTopLeft(1024, 0)
        # self.shapes_to_draw.append(panel2)

        empty = Image2D(None,width=512, height=256)
        print(empty.width(), empty.height())
        shapes_to_draw.append(empty)

        shapes_to_draw.append(row1)
        shapes_to_draw.append(col1)


        # big bug marche pas
        # packX(3, None, *[img0, img1, img2])  # ça marche presque de nouveau

        # print(img0.boundingRect(), img1.boundingRect(), img2.boundingRect())
        #
        # self.shapes_to_draw.append(img0)
        # self.shapes_to_draw.append(img1)
        # self.shapes_to_draw.append(img2)

        # img4.setLettering('<font color="#0000FF">Z</font>')  # ça marche mais voir comment faire en fait
        # self.shapes_to_draw.append(fig)

        # test of an empty image


        # shapes_to_draw.append(Square2D(300, 260, 250, stroke=3))
        widget.shapes_to_draw = shapes_to_draw





    widget.show()

    # all seems to work now --> just finalize things
    # maybe do a panel and allow cols and rows and also allow same size because in some cases people may want that --> offer an option that is fill and
    # TO SAVE AS SVG

    if False:
        # if True:
        widget.save('/E/Sample_images/sample_images_svg/out2.svg')
        # TODO make it also paint to a raster just to see what it gives

        # TO SAVE AS RASTER --> quite good
        # Tif, jpg and png are supported --> this is more than enouch for now
        # self.paintToFile('/E/Sample_images/sample_images_svg/out2.png')
        # self.paintToFile('/E/Sample_images/sample_images_svg/out2.tif')
        # widget.save('/E/Sample_images/sample_images_svg/out2.jpg')
        # widget.save('/E/Sample_images/sample_images_svg/out2.png')
        widget.save('/E/Sample_images/sample_images_svg/out2.jpg')
        widget.save('/E/Sample_images/sample_images_svg/out2.png')
        widget.save('/E/Sample_images/sample_images_svg/out2.tif')  # now has noise
        # first save is ok then gets weird lines

    # --> vraiment pas mal mais voir si je peux tt faire et pkoi si slow

    sys.exit(app.exec_())
