# add support for DND along with a list --> copy my other tools
# can a tree make the difference for selecting shapes ???
# TODO add also more menus around it --> TODO in order to handle better the stuff
from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
import traceback
from pyfigures.gui.ezfig import MyWidget
import matplotlib.pyplot as plt
# from batoolset.draw.shapes.vectorgraphics2d import VectorGraphics2D
from batoolset.img import Img
from batoolset.draw.shapes.group import Group, set_to_size
import numpy as np
import random
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtGui import QPalette,QKeySequence
from qtpy.QtWidgets import QScrollArea, QVBoxLayout, QWidget, QToolBar, QStatusBar, QHBoxLayout, QAction,QShortcut
import qtawesome as qta
from batoolset.draw.shapes.image2d import Image2D
# from batoolset.figure.ezfig import MyWidget
from qtpy.QtWidgets import QApplication, QWidget, QLabel
from qtpy.QtCore import QTimer, QRect
from qtpy.QtGui import QFont, QFontMetrics, QColor

class ClickableScrollArea(QScrollArea):
    """
    A subclass of QScrollArea that emits a signal when the mouse is clicked.
    """
    clicked = Signal()

    def mousePressEvent(self, event):
        """
        Reimplemented from QAbstractScrollArea.
        Emits the clicked signal when the mouse is pressed.
        """
        super().mousePressEvent(event)
        self.clicked.emit()

class scrollable_EZFIG(QWidget):

    def __init__(self, custom_paint_panel=None, show_drawing_commands=True, add_status_bar=True):
        super().__init__()
        if custom_paint_panel is None:
            self.EZFIG_panel = MyWidget()
        else:
            self.EZFIG_panel = custom_paint_panel
        layout = QVBoxLayout()
        self.is_width_for_alternating = True
        # same as the other with embed in scroll area
        self.scrollArea = ClickableScrollArea()#QScrollArea()
        self.scrollArea.setBackgroundRole(QPalette.Dark)
        self.scrollArea.setWidget(self.EZFIG_panel)
        self.scrollArea.setWidgetResizable(
            False)  # perfect --> do not change --> that is what I want in fact         # maybe not what I want finally maybe the set geometry is better in fact

        # Connect the clicked signal to a slot that handles the mouse click event
        self.scrollArea.clicked.connect(self.handle_mouse_click_outside_drawing_panel)

        # see how the size is adjusted in paint and do the same here

        # MEGA TODO handle size for this object
        # self.EZFIG_panel.setFixedSize(QSize(300,300)) # in fact it was not showing because the widget object has no size --> see how to make it work better soon

        # do I need that and is this stuff having this object
        # self.EZFIG_panel.scrollArea = self.scrollArea
        layout.addWidget(self.scrollArea)
        self.setLayout(layout)
        if add_status_bar:
            status_bar = QStatusBar()
            layout.addWidget(status_bar)
        # self.EZFIG_panel.statusBar = status_bar
        # if False:
        self.add_shortcuts()
        if show_drawing_commands:
            self.drawing_commands()


        # we add a popup to display the success/failure of the commands
        self.popup_label = QLabel(self)
        # Set a custom stylesheet for the label
        self.popup_label.setStyleSheet("""
                 QLabel {
                     background-color: #33CC33;
                     border-radius: 10px;
                     color: white;
                     padding: 5px;
                 }
             """)
        self.popup_label.setFont(QFont("Arial", 12))
        self.popup_label.hide() # we hide the label by default; we'll show it when show_popup is called


        self.resize(512,512)

    def show_popup(self, text=None):
        # maybe if one is visible --> skip new one
        if not text:
            return
        if text:
            text = f'{text} '
        # while(self.popup_label.isVisible()):
        #     pass
        if self.popup_label.isVisible() and text.strip()=='State Saved': # prefer the other info as it is most important most likely (dirty hack before making this a stack --> prevents override of previous text of texts)
            return


        self.popup_label.setText(text)
        font = self.popup_label.font()
        font_metrics = QFontMetrics(font)
        text_size = font_metrics.size(Qt.TextSingleLine, text)
        label_geometry = QRect(50, 50, text_size.width() + 10, text_size.height() + 10)
        self.popup_label.setGeometry(label_geometry)
        self.popup_label.show()

        # Hide the popup label after 3 seconds
        QTimer.singleShot(3000, self.popup_label.hide)


    def handle_mouse_click_outside_drawing_panel(self):
        """
        A slot that handles the mouse click event.
        """
        # print(f"Mouse click at position")
        self.EZFIG_panel.set_current_selection(None)
        self.EZFIG_panel.update()

    # this guy should handle the shortcuts it can and pass the rest to the other layer
    def add_shortcuts(self):
        # if True:
        #     return
        zoomPlus = QShortcut("Ctrl+Shift+=", self)
        zoomPlus.activated.connect(self.zoomIn)
        zoomPlus.setContext(Qt.ApplicationShortcut)

        # that works and disconnects all
        # zoomPlus.disconnect()

        zoomPlus2 = QShortcut("Ctrl++", self)
        zoomPlus2.activated.connect(self.zoomIn)
        zoomPlus2.setContext(Qt.ApplicationShortcut)

        zoomMinus = QShortcut("Ctrl+Shift+-", self)
        zoomMinus.activated.connect(self.zoomOut)
        zoomMinus.setContext(Qt.ApplicationShortcut)

        zoomMinus2 = QShortcut("Ctrl+-", self)
        zoomMinus2.activated.connect(self.zoomOut)
        zoomMinus2.setContext(Qt.ApplicationShortcut)

        ctrl0 = QShortcut("Ctrl+0", self)
        ctrl0.activated.connect(self.zoom_reset)
        ctrl0.setContext(Qt.ApplicationShortcut)

        if False:
            self.ctrlS = QShortcut("Ctrl+S", self)
            # self.ctrlS.activated.connect(self.EZFIG_panel.save)
            self.ctrlS.setContext(Qt.ApplicationShortcut)

            self.ctrlM = QShortcut("Ctrl+M", self)
            # self.ctrlM.activated.connect(self.EZFIG_panel.ctrl_m_apply)
            self.ctrlM.setContext(Qt.ApplicationShortcut)

            self.shrtM = QShortcut("M", self)
            # self.shrtM.activated.connect(self.EZFIG_panel.m_apply)
            self.shrtM.setContext(Qt.ApplicationShortcut)

            # I can connect to progeny --> makes sense and really easy --> cool
            self.enterShortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
            # self.enterShortcut.activated.connect(self.EZFIG_panel.apply)
            self.enterShortcut.setContext(Qt.ApplicationShortcut)

            self.enterShortcut2 = QShortcut(QKeySequence(Qt.Key_Enter), self)
            # self.enterShortcut2.activated.connect(self.EZFIG_panel.apply)
            self.enterShortcut2.setContext(Qt.ApplicationShortcut)

            # en fait je peux aussi connecter des trucs au descendant --> pas bete et tres facile à faire!!!

            # pkoi ça ne marche pas !!!
            self.shiftEnterShortcut = QShortcut("Shift+Enter", self)
            # self.shiftEnterShortcut.activated.connect(self.EZFIG_panel.shift_apply)
            self.shiftEnterShortcut.setContext(Qt.ApplicationShortcut)
            #
            self.shiftEnterShortcut2 = QShortcut("Shift+Return", self)
            # self.shiftEnterShortcut2.activated.connect(self.EZFIG_panel.shift_apply)
            self.shiftEnterShortcut2.setContext(Qt.ApplicationShortcut)

            self.ctrl_shift_S_grab_screen_shot = QShortcut('Ctrl+Shift+S', self)
            # self.ctrl_shift_S_grab_screen_shot.activated.connect(self.EZFIG_panel.grab_screen_shot)
            self.ctrl_shift_S_grab_screen_shot.setContext(Qt.ApplicationShortcut)

            # peut etre faire un fullscreen shortcut --> can be useful

    def enable_shortcuts(self):
        self.disable_shortcuts()
        # self.ctrlS.activated.connect(self.EZFIG_panel.save)
        # self.ctrlM.activated.connect(self.EZFIG_panel.ctrl_m_apply)
        # self.shrtM.activated.connect(self.EZFIG_panel.m_apply)
        # self.enterShortcut.activated.connect(self.EZFIG_panel.apply)
        # self.enterShortcut2.activated.connect(self.EZFIG_panel.apply)
        # self.shiftEnterShortcut.activated.connect(self.EZFIG_panel.shift_apply)
        # self.shiftEnterShortcut2.activated.connect(self.EZFIG_panel.shift_apply)

    def disable_shortcuts(self):
        # TODO
        try:
            self.ctrlS.disconnect()
        except:
            pass
        # TODO
        try:
            self.ctrlM.disconnect()
        except:
            pass
        try:
            self.shrtM.disconnect()
        except:
            pass
        try:
            self.enterShortcut.disconnect()
        except:
            pass
        try:
            self.enterShortcut2.disconnect()
        except:
            pass
        try:
            self.shiftEnterShortcut.disconnect()
        except:
            pass
        try:
            self.shiftEnterShortcut2.disconnect()
        except:
            pass

    # def enableMouseTracking(self):
    #     self.EZFIG_panel.drawing_enabled = True
    #
    # def disableMouseTracking(self):
    #     self.EZFIG_panel.drawing_enabled = False

    # ça marche --> ajouter fit to width ou fit to height
    def fit_to_width_or_height(self):
        if self.is_width_for_alternating:
            self.fit_to_width()
        else:
            self.fit_to_height()
        self.is_width_for_alternating = not self.is_width_for_alternating

    # almost there but small bugs
    def fit_to_width(self):
        # print('TODO implement that')
        # return
        # if self.EZFIG_panel.image is None:
        #     return
        # self.scrollArea = self.scroll_areas[nb]
        width = self.scrollArea.width() - 2
        width -= self.scrollArea.verticalScrollBar().sizeHint().width()
        # height-=self.scrollArea.horizontalScrollBar().sizeHint().height()
        width_im = self.EZFIG_panel.updateBounds().width()
        scale = width / width_im
        self.scaleImage(scale)

    def fit_to_height(self, nb=0):
        # print('TODO implement that')
        # return
        # paint = self.EZFIG_panels[nb]
        # if self.EZFIG_panel.image is None:
        #     return
        # scrollArea = self.scroll_areas[nb]
        height = self.scrollArea.height() - 2
        height -= self.scrollArea.horizontalScrollBar().sizeHint().height()
        height_im = self.EZFIG_panel.updateBounds().height()
        scale = height / height_im
        self.scaleImage(scale)

    def fit_to_window(self):
        width = self.scrollArea.width() - 2  # required to make sure bars not visible
        height = self.scrollArea.height() - 2

        height_im = self.EZFIG_panel.updateBounds().height()
        width_im = self.EZFIG_panel.updateBounds().width()
        scale = height / height_im
        if width / width_im < scale:
            scale = width / width_im
        self.scaleImage(scale)

    def zoomIn(self):
        # print('TODO implement that')
        # return
        # 10% more each time
        self.scaleImage(
            self.EZFIG_panel.scale + (self.EZFIG_panel.scale * 10.0 / 100.0))  # une hausse de 10% à chaque fois

    def zoomOut(self):
        # print('TODO implement that')
        # return
        # 10% less each time
        self.scaleImage(self.EZFIG_panel.scale - (self.EZFIG_panel.scale * 10.0 / 100.0))

    def zoom_reset(self):
        # print('TODO implement that')
        # return
        # resets zoom
        self.scaleImage(1.0)

    # pb this is redundant with the main GUI and not in sync --> can cause a lot of trouble --> dactivate for now
    def full_screen(self):
        if not self.isFullScreen():
            self.fullscreen.setIcon(qta.icon('mdi.fullscreen-exit'))
            self.fullscreen.setToolTip('Exit full screen')
            self.showFullScreen()
        else:
            self.fullscreen.setIcon(qta.icon('mdi.fullscreen'))
            self.fullscreen.setToolTip('Enter full screen')
            self.setWindowFlags(Qt.Widget)
            self.show()
            self.repaint()

    def scaleImage(self, scale):
        self.EZFIG_panel.set_scale(scale)
        # size = self.EZFIG_panel.updateBounds()
        # size = QSize(int(size.width()), int(size.height()))
        # self.EZFIG_panel.resize(
        #     self.EZFIG_panel.scale * size)  # ça marche set ça qui gère la taille --> c'est ce que je veux
        self.EZFIG_panel.update_size()
        self.EZFIG_panel.update()

    def drawing_commands(self):
        hlayout_of_toolbars = QHBoxLayout()
        hlayout_of_toolbars.setAlignment(Qt.AlignLeft)
        self.tb1 = QToolBar()
        self.tb2 = QToolBar()

        # fa5.save
        save_action = QAction(qta.icon('fa5.save'), 'Save mask', self)
        save_action.triggered.connect(self.EZFIG_panel.updateBounds)
        self.tb2.addAction(save_action)

        # maybe reuse that to show skeleton un peu à la illustrator --> easy to find objects lost below others
        show_hide_mask = QAction(qta.icon('fa.bullseye'), 'Show/hide mask (same as pressing "M")', self)
        # show_hide_mask.triggered.connect(self.EZFIG_panel.m_apply)
        self.tb2.addAction(show_hide_mask)

        apply_drawing = QAction(qta.icon('fa.check'), 'Apply drawing (same as pressing the "Enter" key)',
                                          self)
        # apply_drawing.triggered.connect(self.EZFIG_panel.apply)
        self.tb2.addAction(apply_drawing)

        zoom_plus = QAction(qta.icon('ei.zoom-in'), 'Zoom+', self)
        zoom_plus.triggered.connect(self.zoomIn)
        self.tb1.addAction(zoom_plus)

        zoom_minus = QAction(qta.icon('ei.zoom-out'), 'Zoom-', self)
        zoom_minus.triggered.connect(self.zoomOut)
        self.tb1.addAction(zoom_minus)

        zoom_width_or_height = QAction(qta.icon('mdi.fit-to-page-outline'),
                                                 'Alternates between best fit in width and height', self)
        zoom_width_or_height.triggered.connect(self.fit_to_width_or_height)
        self.tb1.addAction(zoom_width_or_height)

        zoom_0 = QAction(qta.icon('ei.resize-full'), 'Reset zoom', self)
        zoom_0.triggered.connect(self.zoom_reset)
        self.tb1.addAction(zoom_0)

        # redundant with TA full screen and not in sync --> disable for now
        self.fullscreen = QAction(qta.icon('mdi.fullscreen'), 'Full screen', self)
        self.fullscreen.setToolTip('Enter full screen')
        self.fullscreen.triggered.connect(self.full_screen)
        self.tb1.addAction(self.fullscreen)

        # self.layout().addWidget(self.tb1)
        hlayout_of_toolbars.addWidget(self.tb2)
        hlayout_of_toolbars.addWidget(self.tb1)

        self.layout().addLayout(hlayout_of_toolbars)

    def get_selected_channel(self):
        idx = self.channels.currentIndex()
        if idx == 0:
            return None
        else:
            return idx - 1


    def scroll_to_item(self):
        #        # check parent --> this is really not great but no clue why


        """
        Scrolls the view to the given QGraphicsItem item.
        """
        # Get the position of the item in the scene coordinate system
        # item_pos = item.pos()
        #
        # # Map the position of the item to the viewport coordinate system
        # view_pos = self.graphics_view.mapFromScene(item_pos)
        #
        # # Calculate the position of the viewport that allows you to see the item
        # x = view_pos.x() - self.graphics_view.viewport().width() / 2
        # y = view_pos.y() - self.graphics_view.viewport().height() / 2
        #
        # # Set the position of the horizontal and vertical scrollbars
        # self.horizontal_scrollbar.setValue(x)
        # self.vertical_scrollbar.setValue(y)

        # Ensure that the rectangle is visible within the scroll area

        # what if this is a group ??? -->


        if isinstance(self.EZFIG_panel.selected_shape, (Image2D, Group)):
        # if True:


            # I need to update the packing of the image


            # self.EZFIG_panel.set_current_selection(self.EZFIG_panel.selected_shape)

            # self.update()
            # self.EZFIG_panel.update()
            # self.EZFIG_panel.update_size()
            # self.EZFIG_panel.update_text_rows.emit()


            try:
                self.EZFIG_panel.repack_all()
                # print('ensure area visible called -−> ACTION REQUIRED')
                pos = self.EZFIG_panel.selected_shape.getRect(all=True).toRect()



                # print('checking posirion and viewport',pos, self.EZFIG_panel.scale, self.scrollArea.viewport().rect(), self.scrollArea.visibleRegion().boundingRect())
                # self.scrollArea.ensureVisible(int(pos.x()*self.EZFIG_panel.scale), int(pos.y()*self.EZFIG_panel.scale), int(pos.width()*self.EZFIG_panel.scale), int(pos.height()*self.EZFIG_panel.scale))


                self.scroll_to_y_position(int(pos.center().y()*self.EZFIG_panel.scale))


                #
                # self.scrollArea.ensureVisible(int(pos.x()*self.EZFIG_panel.scale), int((pos.y()+pos.height()/2)*self.EZFIG_panel.scale))
                # print('checking posirion and viewport after', pos, self.EZFIG_panel.scale, self.scrollArea.viewport().rect(), self.scrollArea.visibleRegion().boundingRect())

                # self.update()

                # self.scrollArea.ensureVisible(int(pos.x()*self.EZFIG_panel.scale), int(pos.y()*self.EZFIG_panel.scale))
            except:
                traceback.print_exc()
                pass # no big deal if that fails
            # self.EZFIG_panel.update_size()
            # self.EZFIG_panel.update()

    def scroll_to_y_position(self, y_pos: float):
        """
        Scrolls the view vertically to the given y position.
        """
        # Calculate the position of the viewport that allows you to see the y position
        viewport_height = self.scrollArea.viewport().height()
        scroll_bar_value = y_pos * self.EZFIG_panel.scale - viewport_height / 2
        # scroll_bar_value = y_pos

        # Set the position of the vertical scroll bar
        vertical_scroll_bar = self.scrollArea.verticalScrollBar()
        vertical_scroll_bar.setValue(int(scroll_bar_value))




if __name__ == '__main__':
    # TODO add a main method so it can be called directly
    # maybe just show a canvas and give it interesting props --> TODO --> really need fix that too!!!
    import sys
    from qtpy.QtWidgets import QApplication

    # should probably have his own scroll bar embedded somewhere

    app = QApplication(sys.argv)

    w = scrollable_EZFIG()  # ça marche --> permet de mettre des paint panels avec des proprietes particulieres --> assez facile en fait

    if False:
        row1 = group(Image2D('/E/Sample_images/counter/00.png'),
                   Image2D('/E/Sample_images/counter/01.png'))
        # row1.setX(0)
        # row1.setY(0)

        # row1.setToWidth(300)
        set_to_size(row1,300)
    else:
        img1 = Image2D(Img(np.zeros((512, 512)), dimensions='hw'))
        img2 = Image2D(Img(np.zeros((512, 512)), dimensions='hw'))
        img3 = Image2D(Img(np.zeros((512, 512)), dimensions='hw'))
        img4 = Image2D(Img(np.zeros((512, 512)), dimensions='hw'))

        img1 = Image2D(Img(np.zeros((256, 512)), dimensions='hw'))
        img2 = Image2D(Img(np.zeros((512, 512)), dimensions='hw'))
        img3 = Image2D(Img(np.zeros((256, 512)), dimensions='hw'))
        img4 = Image2D(Img(np.zeros((512, 512)), dimensions='hw'))

        t = np.arange(0.0, 2.0, 0.01)
        s = 1 + np.sin(2 * np.pi * t)
        fig, ax = plt.subplots()
        ax.plot(t, s)

        ax.set(xlabel='time (s)', ylabel='voltage (mV)', title=None)
        ax.grid()


        if False:
            # plt.show()
            # fig.savefig("test.png")
            # plt.show()
            # ça marche --> voici deux examples de shapes
            fig = VectorGraphics2D(fig, x=0, y=0, width=20., height=10.)  # could also be used to create empty image with

            svg = VectorGraphics2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/cartman.svg', x=12, y=0,
                                   width=1, height=1, fill_color=0xFFFFFF)  # pb is I can change size if I don't put

        # grp1 = group(img1,img2)
        # grp2 = group(img3, img4, orientation='Y')
        #
        # grp3 = group(grp1, grp2)

        # grp3 = group(img3, fig, space=42, orientation=random.choice(['X','Y']), fill_color=0xFF00FF)
        # grp3 = group(img3,fig, img1,svg, space=3, orientation=random.choice(['X','Y']), fill_color=0xFF00FF)
        # row1 = Group(img3, fig, img1, svg, space=3, orientation=random.choice(['X', 'Y']), fill_color=0xFF00FF)

        # grp3.set_to_size(512)
        # set_to_size(row1, 1024)

    # print(row1.boundingRect())
    w.EZFIG_panel.shapes_to_draw = [row1]
    # w.EZFIG_panel.show()
    # w.EZFIG_panel.updateBounds() # --> it will update the size --> just need to do this in a smarter way but ok in fact
    # so indeed there is a size bug in the size of the row --> need a fix !!!
    w.EZFIG_panel.update_size()
    w.EZFIG_panel.update()
    # ça marche mais tt finalizer
    # that seems to work

    # w.freeze(True)
    # w.freeze(False)
    # w.freeze(True)

    # all is so easy to do this way

    # ça marche --> tres facile a tester
    # --> how can I do a zoom
    # ask whether self scroll or not --> if scrollable

    # mask = w.get_mask()
    #
    # plt.imshow(mask)
    # plt.show()
    print(w.EZFIG_panel.shapes_to_draw)  # --> ça marche en fait

    w.show()
    sys.exit(app.exec_())
