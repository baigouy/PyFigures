from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from batoolset.draw.shapes.Position import Position
from batoolset.pyqt.tools import get_html_text_with_font, get_shape_after_rotation_and_crop
import random
from batoolset.serialization.tools import clone_object, object_to_xml, create_object
from batoolset.draw.shapes.group import Group, set_to_size, set_to_width, set_to_height, set_to_width_im2d, \
    set_to_height_im2d, areIndicesOverlapping
from batoolset.draw.shapes.rectangle2d import Rectangle2D
from batoolset.img import Img, guess_dimensions
import traceback
from qtpy.QtGui import QColor, QTextCursor, QTextCharFormat,QKeySequence,QTransform
from qtpy.QtWidgets import QApplication, QStackedWidget, QWidget, QTabWidget, QScrollArea, QVBoxLayout, QPushButton, \
    QGridLayout, QTextBrowser, QFrame, QProgressBar, QGroupBox, QAction, QDialog, QDockWidget, QLabel, QMenu,QShortcut, QCheckBox, QSpinBox, QMainWindow, QToolBar,QComboBox,QMenuBar, QMessageBox,QLineEdit
from qtpy.QtCore import Signal, QEvent, Qt, QRect, QRectF,QTimer
import numpy as np
import matplotlib.pyplot as plt
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
from batoolset.tools.logger import TA_logger # logging

logger = TA_logger()


# store also all scripts here
script_histo_for_channel1_of_an_image='''
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.hist(self.img[...,1], bins=20, edgecolor='black')
ax.set_xlabel('Value') 
ax.set_ylabel('Frequency')
ax.set_title('Histogram of the green channel') 
self.img = fig
'''


def mini_figure(single=False):
    shapes_to_draw = []
    script = """
t = np.arange(0.0, 2.0, 0.01)
s = 1 + np.sin(2 * np.pi * t)
fig, ax = plt.subplots()
print(type(fig))
ax.plot(t, s)
ax.set(xlabel='time (s)', ylabel='voltage (mV)', title=None)
ax.grid()
self.img = fig
"""

    # matplotlib_figure = Image2D(fig)
    matplotlib_figure = Image2D(custom_loading_script=script)
    # without rotation they are all ok --> so I need to do the translation of the rotation - the non rotated
    matplotlib_figure.set_rotation(-45)

    # print('qsdsqdqsdqsdqssqd', matplotlib_figure.theta)
    # print(matplotlib_figure.to_dict()['theta'])
    # print(clone_object(matplotlib_figure).to_dict()['theta']) # after cloning it is lost but why is that
    #

    # does not work because doe not find plt!!!
    script = """
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
self.img = fig
"""

    script_image = """
self.img = Img('/E/Sample_images/sample_images_PA/test2.jpg')
"""

    script = """
# import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
self.img = fig
"""

    # I need to call super so I need to do plenty of things --> I need to split the loader
    # or I need to initiate the stuff earlier --> think of the best strategy
    extended_script = """
import matplotlib.pyplot as plt
plt.close('all')
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
self.img = fig
plt.show()
"""

    custom_code_fig = Image2D(custom_loading_script=script)
    # custom_code_fig = Image2D(width=512, height=512)

    script_plot_csv = """
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read data using pandas
file_path = '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_SF/sample_test_ScientFig/sample_data.txt'
data = pd.read_csv(file_path, sep='\t')

# Replace comma with dot in 'Percentages' and 'Errors' columns
data['Percentages'] = data['Percentages'].str.replace(',', '.').astype(float)
data['Errors'] = data['Errors'].str.replace(',', '.').astype(float)

# Plotting
fig, ax = plt.subplots()

for genotype, group in data.groupby('Genotype'):
    ax.errorbar(group['Polygon Class'], group['Percentages'], yerr=group['Errors'], label=genotype, marker='o')

ax.set_xlabel('Polygon Class')
ax.set_ylabel('Percentages')
ax.set_title('Polygon Class vs Percentages')
ax.legend()
plt.grid(True)

self.img=fig
"""

    # error_image = Image2D(
    #     '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_SF/sample_test_ScientFig/sample_data.txt')  # just an image with no script
    csv_file_for_a_test = Image2D(
        '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_SF/sample_test_ScientFig/sample_data.txt',
        custom_loading_script=script_plot_csv)  # TODO --> at some point offer a loading script --> TODO



    #['/E/Sample_images/sample_images_PA/mini_vide/focused_Series012.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series014.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series015.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series016.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series018.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series019.png']
    multi_csv_files_for_a_test = Image2D(
        "['/E/Sample_images/sample_images_PA/mini_vide/focused_Series012.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series014.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series015.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series016.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series018.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series019.png']",
        custom_loading_script=None)  # TODO --> at some point offer a loading script --> TODO


    if not single:
        fake = Group(multi_csv_files_for_a_test, csv_file_for_a_test, matplotlib_figure,custom_code_fig)
    else:
        fake = Group(csv_file_for_a_test)
    shapes_to_draw.append(fake)
    return shapes_to_draw
def mini_tst_svg_rotation(single=False, rotation=0):


    shapes_to_draw=[]
    svg_file = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/IBDM.svg')
    # svg_file.set_rotation(45)
    # svg_file.crop(left=150)
    # svg_file.crop(right=150)
    # svg_file.crop(bottom=200)
    # svg_file.crop(top=60)

    svg_file2 = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/epithelium.svg')
                        # fill_color=0x000000)  # not good it appears sheared
    # svg_file2.set_rotation(45)

    # why is QRectF wrong for this file ????

    svg_file2.set_rotation(rotation)
    svg_file2.crop(256, 30, 128, 50)



    print('svg_file2.fill_color', svg_file2.fill_color)  # why is this None ???

    same_img = Image2D(
        '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/test.png')  # not good it appears sheared
    inset_tst_for_rotation = Image2D('/E/Sample_images/counter/00.png')
    inset_tst_for_rotation.border_size = 3  # make sure it displays an edge
    same_img.set_rotation(rotation)
    same_img.crop(256, 30, 128, 50)
    same_img.annotations.append(inset_tst_for_rotation)  # add an inset

    if single == 2:
        fake = Group(svg_file2, same_img)
    elif single:
        fake=Group(svg_file2)
    else:
        fake = Group( svg_file, svg_file2, same_img)

    shapes_to_draw.append(fake)
    return shapes_to_draw

def tst_empties_and_templates():
    shapes_to_draw = []
    empty = Image2D(None, width=512, height=256)
    shapes_to_draw.append(empty)
    return shapes_to_draw



def tst_scale_bar():
    shapes_to_draw = []

    # take an image and draw a line onto it then try to add a scale and see how it behaves in comparison
    # I may be able to do it with a script


    script='''
from skimage.draw import rectangle
empty = np.zeros(shape=(256, 512))
start = (128, 128)
extent= (3, 256)

# Get the row and column indices of the pixels within the rectangle
rr, cc = rectangle(start=start, extent=extent)

empty[rr,cc] = 255
self.img = empty
'''

    script2 = '''
from skimage.draw import rectangle
empty = np.zeros(shape=(512, 256))
start = (128, 8)
extent= (3, 240)

# Get the row and column indices of the pixels within the rectangle
rr, cc = rectangle(start=start, extent=extent)

empty[rr,cc] = 255
self.img = empty
'''

    script3 = '''
from skimage.draw import rectangle
empty = np.zeros(shape=(512, 256))
start = (128, 128)
extent= (3, 256)

# Get the row and column indices of the pixels within the rectangle
rr, cc = rectangle(start=start, extent=extent)

empty[rr,cc] = 255
self.img = empty
'''

    image_with_scale = Image2D(custom_loading_script=script)

    choices = [None, '<font color=#FF0000>10µm</font>']
    legend = random.choice(choices)

    # TODO --> add a scale bar to it then clone the image and see how to display it -−> TODO
    image_with_scale.annotations.append(ScaleBar(bar_width_in_units=256, legend=legend, placement='top-right'))
    image_with_scale.annotations.append(ScaleBar(bar_width_in_units=256, legend=legend, placement='center_h-center_v'))
    image_with_scale.annotations.append(ScaleBar(bar_width_in_units=256, legend=choices[0], placement='top-left'))
    image_with_scale.annotations.append(ScaleBar(bar_width_in_units=256, legend=choices[1], placement='bottom-left'))
    image_with_scale.annotations.append(ScaleBar(bar_width_in_units=256, legend=legend, placement='bottom-right'))
    image_with_scale.annotations.append(ScaleBar(bar_width_in_units=256, legend=legend, placement='bottom-right'))

    image_with_rotation = clone_object(image_with_scale)
    image_with_rotation.set_rotation(45)

    image_with_rotation_n_crop = clone_object(image_with_scale)
    image_with_rotation_n_crop.set_rotation(45)
    image_with_rotation_n_crop.crop(40,90,120,33)
    image_with_rotation_n_crop.crop(120,160,120,33)
    # image_with_rotation_n_crop.crop(128,165,64,64)



    image_with_scale2 = Image2D(custom_loading_script=script2)

    choices = [None, '<font color=#FF0000>10µm</font>']
    legend = random.choice(choices)

    # TODO --> add a scale bar to it then clone the image and see how to display it -−> TODO
    image_with_scale2.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='top-right'))
    image_with_scale2.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='center_h-center_v'))
    image_with_scale2.annotations.append(ScaleBar(bar_width_in_units=240, legend=choices[0], placement='top-left'))
    image_with_scale2.annotations.append(ScaleBar(bar_width_in_units=240, legend=choices[1], placement='bottom-left'))
    image_with_scale2.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='bottom-right'))
    image_with_scale2.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='bottom-right'))

    choices = [None, '<font color=#FF0000>10µm</font>']
    legend = random.choice(choices)

    image_with_scale3= Image2D(custom_loading_script=script3)
    # TODO --> add a scale bar to it then clone the image and see how to display it -−> TODO
    image_with_scale3.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='top-right'))
    image_with_scale3.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='center_h-center_v'))
    image_with_scale3.annotations.append(ScaleBar(bar_width_in_units=240, legend=choices[0], placement='top-left'))
    image_with_scale3.annotations.append(ScaleBar(bar_width_in_units=240, legend=choices[1], placement='bottom-left'))
    image_with_scale3.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='bottom-right'))
    image_with_scale3.annotations.append(ScaleBar(bar_width_in_units=240, legend=legend, placement='bottom-right'))

    # image_with_scale.set_rotation(45)
    shapes_to_draw.append(image_with_scale)
    shapes_to_draw.append(image_with_rotation) # --> ok
    shapes_to_draw.append(image_with_rotation_n_crop)
    shapes_to_draw.append(image_with_scale2)
    shapes_to_draw.append(image_with_scale3)

    return shapes_to_draw



def mega_image_tst():
    print('#'*10, mega_image_tst.__name__,'#'*10)

    shapes_to_draw = []

    img0 = Image2D('/E/Sample_images/counter/00.png')
    if False:
        shapes_to_draw.append(Polygon2D(0, 0, 10, 0, 10, 20, 0, 20, 0, 0, color=0x00FF00))
        shapes_to_draw.append(
            Polygon2D(100, 100, 110, 100, 110, 120, 10, 120, 100, 100, color=0x0000FF, fill_color=0x00FFFF,
                      stroke=2))
        shapes_to_draw.append(Line2D(0, 0, 110, 100, color=0xFF0000, stroke=3))
        shapes_to_draw.append(Rect2D(200, 150, 250, 100, stroke=10, fill_color=0xFF0000))
        shapes_to_draw.append(Ellipse2D(0, 50, 600, 200, stroke=3))
        shapes_to_draw.append(Circle2D(150, 300, 30, color=0xFF0000, fill_color=0x00FFFF))
        shapes_to_draw.append(PolyLine2D(10, 10, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        shapes_to_draw.append(PolyLine2D(10, 10, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        shapes_to_draw.append(Point2D(128, 128, color=0xFF0000, fill_color=0x00FFFF, stroke=0.65))
        shapes_to_draw.append(Point2D(128, 128, color=0x00FF00, stroke=0.65))
        shapes_to_draw.append(Point2D(10, 10, color=0x000000, fill_color=0x00FFFF, stroke=3))
        shapes_to_draw.append(Rect2D(0, 0, 512, 512, color=0xFF00FF, stroke=6))
        inset = Image2D('/E/Sample_images/counter/01.png')
        inset2 = Image2D('/E/Sample_images/counter/01.png')
        inset3 = Image2D('/E/Sample_images/counter/01.png')
        scale_bar = ScaleBar(30, '<font color="#FF00FF">10µm</font>')
        scale_bar.setTopLeft(0, 0)
        img0.add_object(scale_bar, Image2D.TOP_LEFT)
        img0.add_object(inset3, Image2D.TOP_LEFT)
        img0.add_object(inset,
                        Image2D.BOTTOM_RIGHT)  # ça marche meme avec des insets mais faudrait controler la taille des trucs... --> TODO
        img0.add_object(TAText2D(text='<font color="#FF0000">bottom right3</font>'), Image2D.BOTTOM_RIGHT)
        img0.setLettering('<font color="red">A</font>')
        img0.annotation.append(Rect2D(88, 88, 200, 200, stroke=3, color=0xFF00FF))
        img0.annotation.append(Ellipse2D(88, 88, 200, 200, stroke=3, color=0x00FF00))
        img0.annotation.append(Circle2D(33, 33, 200, stroke=3, color=0x0000FF))
        img0.annotation.append(Line2D(33, 33, 88, 88, stroke=3, color=0x0000FF))
        img0.annotation.append(Freehand2D(10, 10, 20, 10, 20, 30, 288, 30, color=0xFFFF00, stroke=3))
        img0.annotation.append(Point2D(128, 128, color=0xFFFF00, stroke=6))

    img1 = Image2D('/E/Sample_images/counter/01.png', user_comments='comments added by the user test')

    test_text = '''
        </head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
        <p style="color:#00ff00;"><span style=" color:#ff0000;">toto</span><br />tu<span style=" vertical-align:super;">tu</span></p>
        '''
    test_text2 = '''
                </head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
                <p style="color:#00ff00;"><span style=" color:#0000ff;">tititi</span>
                '''
    test_text3 = '''
                </head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
                <p style="color:#00ff00;"><span style=" color:#00ffff;">tata</span>
                '''

    if True:
        img0.border_size = 3  # make sure it displays an edge
        img1.annotations.append(img0)  # add an inset
        # img1.setLettering(TAText2D(text=test_text))
        img1.annotations.append(TAText2D(text=test_text, placement='top-left'))
        parent = img1.getRect(raw=True)
        parent = QRectF(0, 0, parent.width(), parent.height())
        img1.annotations.append(
            Rectangle2D(0, 0, parent.width(), parent.height(), stroke=4, color=0xFF0000, fill_color=0xFF0000,
                        opacity=0.4))  # that helps to see the error so that I can better fix it

        img1.annotations.append(TAText2D(text='<font color=#FFFFFF>test<br>vert</font>', placement='top-left',
                                         text_orientation='Y'))  # test of vertical orientation for text
        img1.annotations.append(TAText2D(text='<font color=#FFFFFF>test<br>vert2</font>', placement='top-left',
                                         text_orientation='-Y'))  # test of vertical orientation for text
        img1.annotations.append(TAText2D(text='<font color=#FFFFFF>test horizontal</font>',
                                         placement='top-left'))  # test of vertical orientation for text

        img1.annotations.append(TAText2D(text=test_text2, placement='top-left'))
        img1.annotations.append(TAText2D(text=test_text3, placement='top-left'))

        img1.annotations.append(TAText2D(text=test_text, placement='bottom-right'))
        img1.annotations.append(TAText2D(text=test_text2, placement='bottom-right'))
        img1.annotations.append(TAText2D(text=test_text3, placement='bottom-right'))

        img1.annotations.append(TAText2D(text=test_text, placement='bottom-left'))
        img1.annotations.append(TAText2D(text=test_text2, placement='bottom-left'))

        img1.annotations.append(TAText2D(text=test_text, placement='top-right'))
        img1.annotations.append(TAText2D(text=test_text2, placement='top-right'))

        img1.annotations.append(TAText2D(text=test_text, placement='center_h-center_v'))
        img1.annotations.append(TAText2D(text=test_text2, placement='center_h-center_v'))

        # print('TADAM',img1.width()/2., img1.height()/2.)
        img1.annotations.append(Line2D(0, 0, img1.width() / 2, img1.height() / 2, stroke=3, color=0xFF00FF))
        img1.annotations.append(Rectangle2D(128, 128, 64, 128, stroke=3, color=0xFF00FF))
        img1.annotations.append(Point2D(img1.width() / 2, img1.height() / 2, stroke=6, color=0xFF00FF))
        img1.annotations.append(
            Ellipse2D(img1.width() / 2 - img1.width() / 8, img1.height() / 2 - img1.height() / 12, img1.width() / 4,
                      img1.height() / 6, stroke=3, color=0xFF00FF))
        img1.annotations.append(
            Circle2D(img1.width() / 2 - img1.width() / 10, img1.height() / 2 - img1.height() / 10, img1.width() / 5,
                     stroke=3, color=0xFF00FF))
        img1.annotations.append(
            Polygon2D(100, 100, 110, 100, 110, 120, 10, 120, 100, 100, color=0x0000FF, fill_color=0x00FFFF,
                      stroke=2))
        img1.annotations.append(PolyLine2D(10, 16, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        img1.annotations.append(PolyLine2D(10, 16, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        img1.annotations.append(Square2D(72.5, 151.5, 30, stroke=3))
        # img1.annotations.append(Freehand2D(10, 10, 20, 10, 20, 30, 288, 30, color=0xFFFF00, stroke=3))
        img1.annotations.append(
            Freehand2D(75, 25, 116.50, 50, 116.50, 100, 75, 125, 33.50, 100, 33.50, 50, color=0xFFFF00,
                       stroke=3))  # a beautiful hexagon !!!

        # try a floating text
        img1.annotations.append(TAText2D(text='<font color="#FF0000">top left by coords</font>'))
        img1.annotations.append(TAText2D(text='<font color="#FF0000">top left by coords2 vert</font>',
                                         text_orientation='Y'))  # vertical
        img1.annotations.append(TAText2D(x=img1.width() / 2, y=img1.height() / 2,
                                         text='<font color="#FFFF00">free floating text</font>'))  # NB THIS IS NOT CLONED PROPERLY
        img1.annotations.append(TAText2D(x=img1.width() / 2, y=img1.height() / 2,
                                         text='<font color="#FFFF00">free floating text2 vert</font>',
                                         text_orientation='Y'))  # NB THIS IS NOT CLONED PROPERLY
        img1.annotations.append(
            ScaleBar(30, '<font color="#FF00FF">10µm</font>'))  # default scale bar placement is bottom right
        img1.annotations.append(ScaleBar(30, '<font color="#FF00FF">right µm</font>',
                                         placement='top-right'))  # here I specify the bar to be top right specifically

    # img1.annotations.append(TAText2D(text=test_text, position='top-right'))
    # img1.annotations.append(TAText2D(text=test_text, position='bottom-right'))
    # img1.annotations.append(TAText2D(text=test_text, position='bottom-left'))
    # img1.annotations.append(TAText2D(text=test_text, position='center_h-center_v'))
    # img1.annotations.append(TAText2D(text=test_text, position='left-center_v')) # contradictory because both are verticla
    # img1.annotations.append(TAText2D(text=test_text, position='right-center_v')) # contradictory because both are verticla
    # img1.annotations.append(TAText2D(text=test_text, position='center_v')) # center_v is ok
    # img1.annotations.append(TAText2D(text=test_text, position='bottom')) # center_v is ok
    # img1.annotations.append(TAText2D(text=test_text, position='bottom-center_h'))

    # background-color: orange;
    # span div et p donnent la meme chose par contre c'est sur deux lignes
    # display:inline; float:left # to display as the same line .... --> does that work html to svg
    # https://stackoverflow.com/questions/10451445/two-div-blocks-on-same-line --> same line for two divs
    img2 = Image2D('/E/Sample_images/counter/02.png', user_comments='this is a test of your system\nnew line')
    print('titeuf before', img2.getRect(), img2.getRect(scale=True), img2.getRect(all=True))
    # crop is functional again but again a packing error
    # img2.crop(left=60)
    # img2.crop(right=30)
    # img2.crop(bottom=90)
    # img2.crop(top=60)
    img2.crop(7, 112, 34, 30)
    print('titeuf after', img2.getRect(), img2.getRect(scale=True), img2.getRect(all=True))
    print('AR', img2.getAR(), img2.getAR(invert=True))  # AR is now ok
    img2.scale = 0.5
    print('titeuf after', img2.getRect(), img2.getRect(scale=True), img2.getRect(all=True))
    print('titeuf after2', img2.width(), img2.height(), img2.width(scale=True), img2.height(scale=True),
          img2.width(all=True), img2.height(all=True))
    print('AR', img2.getAR(), img2.getAR(invert=True))  # AR is now ok

    img3 = Image2D('/E/Sample_images/counter/03.png')

    img3.annotations.append(TAText2D('center_h center_v', placement='center_h center_v', fill_color=0xFFFFFF))
    img3.annotations.append(TAText2D('top left', placement='top left', fill_color=0xFFFFFF))
    img3.annotations.append(TAText2D('bottom left', placement='bottom left', fill_color=0xFFFFFF))
    img3.annotations.append(TAText2D('top right', placement='top right', fill_color=0xFFFFFF))
    img3.annotations.append(TAText2D('bottom right', placement='bottom right', fill_color=0xFFFFFF))

    img4 = Image2D('/E/Sample_images/counter/04.png')
    img5 = Image2D('/E/Sample_images/counter/05.png')
    img6 = Image2D('/E/Sample_images/counter/06.png')
    img7 = Image2D('/E/Sample_images/counter/07.png')
    img8 = Image2D('/E/Sample_images/counter/08.png')
    # img8.annotation.append(Rect2D(60, 60, 100, 100, stroke=20, color=0xFF00FF)) # this is what messes everything
    img9 = Image2D('/E/Sample_images/counter/09.png')
    img10 = Image2D('/E/Sample_images/counter/10.png')
    img9extra = Image2D('/E/Sample_images/counter/09.png')
    img10extra = Image2D('/E/Sample_images/counter/10.png')

    t = np.arange(0.0, 2.0, 0.01)
    s = 1 + np.sin(2 * np.pi * t)
    fig, ax = plt.subplots()
    ax.plot(t, s)
    ax.set(xlabel='time (s)', ylabel='voltage (mV)', title='About as simple as it gets, folks')
    ax.grid()

    # graph2d = VectorGraphics2D(fig)
    # graph2d.crop(all=20)  # not great neither
    # vectorGraphics = VectorGraphics2D('/E/Sample_images/sample_images_svg/cartman.svg')
    # vectorGraphics.crop(left=10, right=30, top=10, bottom=10)
    # animatedVectorGraphics = VectorGraphics2D('/E/Sample_images/sample_images_svg/animated.svg')
    # animatedVectorGraphics.crop(left=30)  # , top=20, bottom=20
    # row1 = Row(img0, img1, img2, graph2d,animatedVectorGraphics)  # , graph2d, animatedVectorGraphics  # , img6, #, nCols=3, nRows=2 #le animated marche mais faut dragger le bord de l'image mais pas mal qd meme
    # col1 = Column(img4, img5, img6, vectorGraphics)  # , vectorGraphics# , img6, img6, nCols=3, nRows=2,

    # all seems to  work except the vector graphics --> handle that later then

    row2 = Group(img8, img9)
    col2 = Group(img3, img7, img10, orientation='Y')
    empty2 = Image2D(None, width=512, height=256)  # just to test if empty images can be entered
    row1 = Group(img1, img2,col2)  # , graph2d, animatedVectorGraphics  # , img6, #, nCols=3, nRows=2 #le animated marche mais faut dragger le bord de l'image mais pas mal qd meme
    col1 = Group(img4, img5, img6, row2, empty2, orientation='Y',space=6)  # , vectorGraphics# , img6, img6, nCols=3, nRows=2,

    # grp = Group(col1, row1, orientation=random.choice(['X', 'Y'])) # It does not work it is not

    # c'est bon tt marche maintenant gérer le truc magique du DND et des fusions

    # col1 /= col2

    # row2.setLettering('<font color="#FFFFFF">a</font>')
    # row1 /= row2
    # col1.setToHeight(512)  # creates big bugs now
    # row1.setToWidth(512)
    # row1.set_P1(128,128)

    set_to_width(row1, 512)

    # print('tabula', row1.width(), row1.getRect(), img2.getRect(all=True))
    # set_to_size(col1, 512)
    # set_to_size(grp, 512)

    # print(grp.getRect(scale=True))

    svg_file = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/IBDM.svg')
    svg_file.set_rotation(45)
    # svg_file.crop(left=150)
    # svg_file.crop(right=150)
    # svg_file.crop(bottom=200)
    # svg_file.crop(top=60)

    svg_file2 = Image2D('/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/epithelium.svg',
                        fill_color=0x000000)  # not good it appears sheared
    svg_file2.set_rotation(45)
    svg_file2.crop(256, 30, 128, 50)

    print('svg_file2.fill_color', svg_file2.fill_color)  # why is this None ???

    same_img = Image2D(
        '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_svg/test.png')  # not good it appears sheared
    inset_tst_for_rotation = Image2D('/E/Sample_images/counter/00.png')
    inset_tst_for_rotation.border_size = 3  # make sure it displays an edge
    same_img.set_rotation(45)
    same_img.crop(256,30,128,50)
    same_img.annotations.append(inset_tst_for_rotation)  # add an inset

    empty = Image2D(None, width=512, height=256)
    print(empty.width(), empty.height())

    script = """
t = np.arange(0.0, 2.0, 0.01)
s = 1 + np.sin(2 * np.pi * t)
fig, ax = plt.subplots()
print(type(fig))
ax.plot(t, s)
ax.set(xlabel='time (s)', ylabel='voltage (mV)', title=None)
ax.grid()
self.img = fig
        """

    # matplotlib_figure = Image2D(fig)
    matplotlib_figure = Image2D(custom_loading_script=script)
    # without rotation they are all ok --> so I need to do the translation of the rotation - the non rotated
    matplotlib_figure.set_rotation(-45)

    # print('qsdsqdqsdqsdqssqd', matplotlib_figure.theta)
    # print(matplotlib_figure.to_dict()['theta'])
    # print(clone_object(matplotlib_figure).to_dict()['theta']) # after cloning it is lost but why is that
    #

    # does not work because doe not find plt!!!
    script = """
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
self.img = fig
        """

    script_image = """
self.img = Img('/E/Sample_images/sample_images_PA/test2.jpg')
        """

    script = """
# import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
self.img = fig
        """

    # I need to call super so I need to do plenty of things --> I need to split the loader
    # or I need to initiate the stuff earlier --> think of the best strategy
    extended_script = """
import matplotlib.pyplot as plt
plt.close('all')
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
self.img = fig
plt.show()
        """

    custom_code_fig = Image2D(custom_loading_script=script)
    # custom_code_fig = Image2D(width=512, height=512)

    script_plot_csv = """
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# Read data using pandas
file_path = '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_SF/sample_test_ScientFig/sample_data.txt'
data = pd.read_csv(file_path, sep='\t')

# Replace comma with dot in 'Percentages' and 'Errors' columns
data['Percentages'] = data['Percentages'].str.replace(',', '.').astype(float)
data['Errors'] = data['Errors'].str.replace(',', '.').astype(float)

# Plotting
fig, ax = plt.subplots()

for genotype, group in data.groupby('Genotype'):
    ax.errorbar(group['Polygon Class'], group['Percentages'], yerr=group['Errors'], label=genotype, marker='o')

ax.set_xlabel('Polygon Class')
ax.set_ylabel('Percentages')
ax.set_title('Polygon Class vs Percentages')
ax.legend()
plt.grid(True)

self.img=fig
"""

    error_image = Image2D(
        '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_SF/sample_test_ScientFig/sample_data.txt')  # just an image with no script
    csv_file_for_a_test = Image2D(
        '/E/Sample_images/EZF_SF_scientifig_EZFig/sample_images_SF/sample_test_ScientFig/sample_data.txt',
        custom_loading_script=script_plot_csv)  # TODO --> at some point offer a loading script --> TODO

    multi_csv_files_for_a_test = Image2D(
        "['/E/Sample_images/sample_images_PA/mini_vide/focused_Series012.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series014.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series015.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series016.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series018.png','/E/Sample_images/sample_images_PA/mini_vide/focused_Series019.png']",
        custom_loading_script=None)  # TODO --> at some point offer a loading script --> TODO

    fake = Group(error_image, csv_file_for_a_test, multi_csv_files_for_a_test, svg_file, svg_file2, same_img, empty, matplotlib_figure,
                 custom_code_fig)
    shapes_to_draw.append(fake)

    # now we add an empty text row
    # test = Group(TAText2D('first'), TAText2D('second'), TAText2D('Third<br>Dual')) # not working because it has no size and cannot be done
    tmp1 = Image2D(width=512, height=512, annotations=[
        TAText2D('first', placement='center_h center_v', text_orientation='Y', range=[0, 0], fill_color=0xFFFFFF)],
                   isText=True)
    # tmp1.annotations.append(TAText2D('first', placement='center_h center_v', text_orientation='Y'))
    tmp2 = Image2D(width=512, height=512, annotations=[
        TAText2D('second', placement='center_h center_v', text_orientation='-Y', range=[1, 1],
                 fill_color=0xFFFFFF)], isText=True)
    # tmp2.annotations.append(TAText2D('second', placement='center_h center_v', text_orientation='-Y')) # there is a bug with -X orientation --> not bad and almost ok
    tmp3 = Image2D(width=512, height=256, annotations=[
        TAText2D('Third<br>Dual', placement='center_h center_v', range=[2, 2], fill_color=0xFFFFFF)], isText=True)
    tmp4 = Image2D(width=512, height=256, annotations=[
        TAText2D('fifth', placement='center_h center_v', text_orientation='-X', range=[3, 3], fill_color=0xFFFFFF)],
                   isText=True)  # there is a bug with -X orientation --> not bad and almost ok
    tmp5 = Image2D(width=512, height=256, annotations=[
        TAText2D('Fouth<br>Dual', placement='center_h center_v', text_orientation='X', range=[4, 4],
                 fill_color=0xFFFFFF)], isText=True)  # not ok
    tmp6 = Image2D(width=512, height=256, annotations=[
        TAText2D('Fouth<br>Dual', placement='center_h center_v', range=[5, 5], fill_color=0xFFFFFF)],
                   isText=True)  # ok

    # print('tmp3.getAR()',tmp3.getAR())

    # print(tmp1.getRect())
    # print(tmp2.getRect())
    # print(tmp3.getRect())

    # print(tmp1.getAR())
    # print(tmp2.getAR())
    # print(tmp3.getAR())

    # add a text and handle it

    # tmp3.annotations.append(TAText2D('Third<br>Dual', placement='center_h center_v'))
    test = Group(tmp1, tmp2, tmp3, tmp4, tmp5, tmp6, isText='below')  # this stuff is all empty but why

    text_orientation = random.choice([None, 'X', '-X', 'Y',
                                      '-Y'])  # ok so not a bug --> just me wanting that to be done this way but that perturbed me!!! --> keep this in mind
    # text_orientation = 'Y'

    # print('current text_orientation', text_orientation)
    tmp7 = Image2D(width=512, height=256, annotations=[
        TAText2D('Top<br>Left', placement='top left', text_orientation=text_orientation, fill_color=0xFFFFFF)],
                   isText=True)  # ok

    tmp8 = Image2D(width=512, height=256, annotations=[
        TAText2D('Top<br>Right', placement='top Right', text_orientation=text_orientation, fill_color=0xFFFFFF)],
                   isText=True)  # ok
    tmp9 = Image2D(width=512, height=256, annotations=[
        TAText2D('Bottom<br>Left', placement='bottom left', text_orientation=text_orientation,
                 fill_color=0xFFFFFF)], isText=True)  # ok
    tmp10 = Image2D(width=512, height=256, annotations=[
        TAText2D('Bottom<br>right', placement='bottom right', text_orientation=text_orientation,
                 fill_color=0xFFFFFF)], isText=True)  # ok
    tmp11 = Image2D(width=512, height=256, annotations=[
        TAText2D('Center', placement='center_h, center_v', text_orientation=text_orientation, fill_color=0xFFFFFF)],
                    isText=True)  # ok

    # all the positionings are now perfect

    test_text_positioning = Group(tmp7, tmp8, tmp9, tmp10, tmp11)

    shapes_to_draw.append(test_text_positioning)

    shapes_to_draw.append(test)
    # print('test.isText', test.isText)

    # vert_text_only = Group(clone_object(tmp1), clone_object(tmp2), clone_object(tmp3), isText=True, orientation='Y')

    vert_text_only = clone_object(test)
    vert_text_only.orientation = 'Y'
    vert_text_only.update()

    # print('vert_text_only.isText', vert_text_only.isText)
    # shapes_to_draw.append(vert_text_only) # MEGA TODO --> there is a bug there the vert object creates a crash directly --> can I apply a fix ??? --> causes a massive crash

    shapes_to_draw.append(row1)


    # MEGA TODO THERE IS A PRINT SOMEWHERE THERE -−> NEED A FIX
    test_unrotated_uncropped = clone_object(img1)
    test_rotated_uncropped = clone_object(test_unrotated_uncropped)
    test_rotated_uncropped.set_rotation(42)
    test_rotated_cropped = clone_object(test_unrotated_uncropped)
    # print('bee') #
    test_rotated_cropped.set_rotation(42)
    # test_rotated_cropped.crop(30,40,60,80)
    test_rotated_cropped.crop(60, 30, 0, 0)

    test_unrotated_cropped = clone_object(test_unrotated_uncropped)
    test_unrotated_cropped.crop(30, 40, 60, 80)

    group_rotation_n_crop = Group(test_unrotated_uncropped, test_rotated_uncropped, test_rotated_cropped,
                                  test_unrotated_cropped)

    shapes_to_draw.append(group_rotation_n_crop)

    row1_clone = clone_object(row1)
    row1_clone.content[0].set_rotation(42)  # rotate the first image --> this can be very useful for debug!!!

    # if random.random()<0.5:
    # I still have a crop bug --> need a fix
    if True:
        # row1_clone.content[0].crop(85,68,16,30) # rotate the first image --> this can be very useful for debug!!!
        # row1_clone.content[0].crop(3,11,8,199) # rotate the first image --> this can be very useful for debug!!!
        row1_clone.content[0].crop(30, 40, 60,
                                   80)  # rotate the first image --> this can be very useful for debug!!!
    else:
        row1_clone.content[0].crop(None, None, None, None)
        # no crop !!!

    # row1_clone.content[0].crop(85, 0,0,0) # --> indeed that show that there is a big scale error

    row1_clone.content[1].set_rotation(42)
    row1_clone.content[1].crop(155, 104, 96, 152)

    # row1_clone.content[1].crop(None, None, None,None)

    row1_clone.content.insert(0, clone_object(tmp1))
    tmp16 = Image2D(width=512, height=512, annotations=[TAText2D('inner', placement='center_h center_v')],
                    isText=True)
    # tmp16.annotations.append(TAText2D('inner', placement='center_h center_v')) # there is a bug with this one ??? --> see how I can do that??? # if I put text orientation X this creates an error
    row1_clone.content.insert(2, tmp16)

    # row1_clone.content[-1].content.append(clone_object(tmp16)) # NB THE NESTED STUFF FUCKS IT ALL −−> JUST SIMPLIFY ALL OF MY CODE ANYWAY I DON'T NEED SMTHG SO SIMPLE
    row1_clone.content.append(clone_object(tmp2))
    row1_clone.update()


    # print('#'*40)
    # print(object_to_xml(tmp2)) # the object seems ok but its clone is not --> why is that
    # print('-'*20)
    # print(type(tmp2)) # the object seems ok but its clone is not --> why is that
    # print(type(tmp2).__name__) # the object seems ok but its clone is not --> why is that
    # # print(tmp2.__name__) # the object seems ok but its clone is not --> why is that
    # print('#' * 40)
    #
    # print('BUG IS IN CLONING', type(clone_object(tmp2)), type(tmp2),clone_object(tmp2))
    #
    # # here there are small errors
    #
    # # the first and last is an empty list --> why is that --> the cloning of temp2 failed
    #
    # print('TEST CURRENT_STUFF',row1_clone.__repr__(), row1_clone)

    row1_clone.set_to_size(row1_clone.size)



    # that works but will that work with nested stuff I am not sure --> see how I could do that

    shapes_to_draw.append(row1_clone)

    col1_clone = clone_object(col1)
    col1_clone.content.insert(0, clone_object(tmp1))
    col1_clone.content.insert(2, clone_object(tmp16))
    col1_clone.content.append(clone_object(tmp2))
    shapes_to_draw.append(col1_clone)
    col1_clone.update()
    shapes_to_draw.append(col1)

    shapes_to_draw.append(img10extra)  # just an image alone to see if it can be combined
    shapes_to_draw.append(img9extra)  # just an image alone to see if it can be combined

    # see how I can handle scale and alike

    # shapes_to_draw.append(grp)
    # img4.setLettering('<font color="#0000FF">Z</font>')  # ça marche mais voir comment faire en fait
    # shapes_to_draw.append(Square2D(300, 260, 250, stroke=3))

    # for shape in shapes_to_draw: # this is now done by default !!! --> TODO
    #     shape.translate(50,50) # hack not to overlap with ruler

    if False:
        print(row2.content)
        print(col1.content)
        col1.remove(img8, img9)
        # print(row2.content)
        # print(row2.content)
        # col1.remove(img9)
        print(row2.content)
        print(col1.content)
        # row2.remove(img8)
        # print(row2.content)

        if False:
            sys.exit(0)

            print(col1.content)
            col1.remove(img4)
            print(col1.content)
            print(col1.isEmpty())
            # col1.remove(img5)
            # col1.remove(img6)
            # col1.remove(row2)
            col1.remove(img5, img6, row2)
            print(col1.content)
            print(col1.isEmpty())
            print(img4, row2, img6)
            sys.exit(0)

    # first implement the magic selection going inner an object
    # not bad --> it shows a copy of the rects --> that could be used to do a preview --> finalize that
    # see how complex this would be
    # could do the same with all possible shapes for source and target --> TODO
    # detect all the possibilities
    # print(type(row1))  # --> a column --> clone it with rects
    # really need implement cloning anyway
    # for iii,rect in enumerate(row1):
    #     print(rect) # -> ce truc est un rect2D --> just need to clone it
    #     # print(type(rect), isinstance(rect, Rect2D)) # -- > ok --> seems to work
    #     rect_copy = Rect2D(rect.boundingRect()) # ça marche --> ça cree une copy du rect # and update the colors when
    #     rect_copy.fill_color = 0xFF0000
    #     rect_copy.translate(25,25)
    #     shapes_to_draw.append(rect_copy)
    #     # if iii==3:
    #     break

    # does that work ??? --> is my error an error of scaling ???

    # I need implement the cloning from inside
    # images_bounds = []
    # for rect in col1:
    #     print(rect) # -> ce truc est un rect2D --> just need to clone it
    #     # print(type(rect), isinstance(rect, Rect2D)) # -- > ok --> seems to work
    #     # --> not ok because keeps the original rect dimension, not taking into account the scaling --> just get bounds and duplictae
    #     rect_copy = Rect2D(rect.boundingRect()) # ça marche --> ça cree une copy du rect # and update the colors when
    #     # rect_copy = rect_copy*rect.scaling # --> marche pas --> would need to clone the stuff
    #     rect_copy.fill_color = 0x00FF00
    #     rect_copy.translate(25,25)
    #     shapes_to_draw.append(rect_copy)
    # images_bounds.append(rect_copy)
    # marche pas car scaling non preservé --> voir comment faire en fait
    # cree un clone de la classe mais un peu complexe en fait --> car
    # clone_rect_type = type(col1)
    # new_clone_with_rect = clone_rect_type(*images_bounds)
    # new_clone_with_rect.setX(col1.x())
    # new_clone_with_rect.setY(col1.y())
    # new_clone_with_rect.setWidth(col1.width())
    # new_clone_with_rect.setHeight(col1.height())
    #
    # shapes_to_draw.append(new_clone_with_rect)
    # put a + and add a rect to it maybe
    # see
    print('-' * 10, mega_image_tst.__name__, '-' * 10)
    return shapes_to_draw


def tst_stacks_n_sizes():
    shapes_to_draw = []
    # np.ndarray tests

    # no it is not a bug they cannot be copied --> replace them by a script

    img0 = Image2D(custom_loading_script='self.img=np.zeros(shape=(256, 512), dtype=int)')  # image should be hwc # an empty image created directly by the user
    img1 = Image2D(custom_loading_script='self.img=np.zeros(shape=(128, 512, 3),dtype=np.uint8)')  # image should be hwc # an empty image created directly by the user
    template = Image2D(filename='@template@')
    grp = Group(img0, img1, template)
    shapes_to_draw.append(grp)

    # TODO test some images from imageJ maybe also with channels and alike and compare
    img2 = Image2D('/E/Sample_images/epithelia_examples/full_wing_multi/late_stages/FocStich_RGB195.png')
    img3 = Image2D('/E/Sample_images/epithelia_examples/xenope/macroconfocal/MAX_crb3-1-82ng.tif')  # NB this stuff is converted to RGB although the LUTs are not the same -> do my best to read the real LUTs if possible --> should not be too hard --> do that at loading and offer the user an easy way to do that
    grp2 = Group(img2, img3)
    shapes_to_draw.append(grp2)



    # TODO test some images from imageJ maybe also with channels and alike and compare
    img4 = Image2D('/E/Sample_images/epithelia_examples/wings_megasize/Stitched_101129_PW_19h00-34h00_DEcadGFP_t05.png')
    img5 = Image2D('/E/Sample_images/sample_images_FIJI/bat-cochlea-volume.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike

    # print(img3.getRect(raw=True), 'vssssusus',img3.get_raw_size())

    img6 = Image2D('/E/Sample_images/sample_images_FIJI/bat-cochlea-renderings.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike

    # print(img6.getRect(raw=True), 'img6 vssssusus', img6.get_raw_size())

    img7 = Image2D('/E/Sample_images/sample_images_FIJI/first-instar-brain.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike
    img8 = Image2D('/E/Sample_images/sample_images_FIJI/mitosis.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike
    grp3 = Group(img4, img5, img6, img7, img8)
    shapes_to_draw.append(grp3)

    img9 = Image2D(
        '/E/Sample_images/sample_images_FIJI/new-lenna.jpg')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike
    img10 = Image2D('/E/Sample_images/sample_images_FIJI/organ-of-corti.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike
    img11 = Image2D('/E/Sample_images/sample_images_FIJI/MAX_organ-of-corti.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike # really handle all the channels --> TODO

    grp4 = Group(img9, img10, img11)
    shapes_to_draw.append(grp4)

    img12 = Image2D('/E/Sample_images/sample_images_FIJI/Rat_Hippocampal_Neuron.tif')  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike # really handle all the channels --> TODO
    img14 = Image2D('/E/Sample_images/sample_images_FIJI/confocal-series.tif', dimensions={'order':'dhwc','values':[16]})  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike  # this is a 3D image just to see how it is read # -> very good reads the first image --> maybe a script can make it read the next or alike
    img15 = Image2D('/E/Sample_images/sample_images_FIJI/FluorescentCells.tif')  # this seems to be perfectly well-read
    img16 = Image2D('/E/Sample_images/sample_images_FIJI/mri-stack.tif',dimensions={'order':'dhw','values':[16]})  # this seems to be perfectly well read
    img17 = Image2D('/E/Sample_images/sample_images_FIJI/mri-stack.tif',dimensions={'order':'dhwc','values':[16]})  # this seems to be perfectly well read

    # the last one is wrong

    grp5 = Group(img12, img14, img15, img16,img17)
    shapes_to_draw.append(grp5)

    img18 = Image2D('/E/Sample_images/sample_images_FIJI/150707_WTstack.lsm', projection='max')
    img19 = Image2D('/E/Sample_images/sample_images_FIJI/AuPbSn40.jpg')
    img20 = Image2D('/E/Sample_images/sample_images_FIJI/graffiti.tif')
    grp6 = Group(img18, img19, img20)
    shapes_to_draw.append(grp6)
    # TODO -> check also all in /E/Sample_images/sample_images_FIJI

    return shapes_to_draw


def get_complex_tst_image():
    img0 = Image2D('/E/Sample_images/counter/00.png')

    img1 = Image2D('/E/Sample_images/counter/01.png', user_comments='comments added by the user test')

    test_text = '''
          </head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
          <p style="color:#00ff00;"><span style=" color:#ff0000;">toto</span><br />tu<span style=" vertical-align:super;">tu</span></p>
          '''
    test_text2 = '''
                  </head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
                  <p style="color:#00ff00;"><span style=" color:#0000ff;">tititi</span>
                  '''
    test_text3 = '''
                  </head><body style=" font-family:'Comic Sans MS'; font-size:22pt; font-weight:400; font-style:normal;">
                  <p style="color:#00ff00;"><span style=" color:#00ffff;">tata</span>
                  '''

    if True:
        img0.border_size = 3  # make sure it displays an edge
        img1.annotations.append(img0)  # add an inset
        # img1.setLettering(TAText2D(text=test_text))
        img1.annotations.append(TAText2D(text=test_text, placement='top-left'))
        parent = img1.getRect(raw=True)
        parent = QRectF(0, 0, parent.width(), parent.height())
        img1.annotations.append(
            Rectangle2D(0, 0, parent.width(), parent.height(), stroke=4, color=0xFF0000, fill_color=0xFF0000,
                        opacity=0.4))  # that helps to see the error so that I can better fix it

        img1.annotations.append(TAText2D(text='<font color=#FFFFFF>test<br>vert</font>', placement='top-left',
                                         text_orientation='Y'))  # test of vertical orientation for text
        img1.annotations.append(TAText2D(text='<font color=#FFFFFF>test<br>vert2</font>', placement='top-left',
                                         text_orientation='-Y'))  # test of vertical orientation for text
        img1.annotations.append(TAText2D(text='<font color=#FFFFFF>test horizontal</font>',
                                         placement='top-left'))  # test of vertical orientation for text

        img1.annotations.append(TAText2D(text=test_text2, placement='top-left'))
        img1.annotations.append(TAText2D(text=test_text3, placement='top-left'))

        img1.annotations.append(TAText2D(text=test_text, placement='bottom-right'))
        img1.annotations.append(TAText2D(text=test_text2, placement='bottom-right'))
        img1.annotations.append(TAText2D(text=test_text3, placement='bottom-right'))

        img1.annotations.append(TAText2D(text=test_text, placement='bottom-left'))
        img1.annotations.append(TAText2D(text=test_text2, placement='bottom-left'))

        img1.annotations.append(TAText2D(text=test_text, placement='top-right'))
        img1.annotations.append(TAText2D(text=test_text2, placement='top-right'))

        img1.annotations.append(TAText2D(text=test_text, placement='center_h-center_v'))
        img1.annotations.append(TAText2D(text=test_text2, placement='center_h-center_v'))

        # print('TADAM',img1.width()/2., img1.height()/2.)
        img1.annotations.append(Line2D(0, 0, img1.width() / 2, img1.height() / 2, stroke=3, color=0xFF00FF))
        img1.annotations.append(Rectangle2D(128, 128, 64, 128, stroke=3, color=0xFF00FF))
        img1.annotations.append(Point2D(img1.width() / 2, img1.height() / 2, stroke=6, color=0xFF00FF))
        img1.annotations.append(
            Ellipse2D(img1.width() / 2 - img1.width() / 8, img1.height() / 2 - img1.height() / 12, img1.width() / 4,
                      img1.height() / 6, stroke=3, color=0xFF00FF))
        img1.annotations.append(
            Circle2D(img1.width() / 2 - img1.width() / 10, img1.height() / 2 - img1.height() / 10, img1.width() / 5,
                     stroke=3, color=0xFF00FF))
        img1.annotations.append(
            Polygon2D(100, 100, 110, 100, 110, 120, 10, 120, 100, 100, color=0x0000FF, fill_color=0x00FFFF,
                      stroke=2))
        img1.annotations.append(PolyLine2D(10, 16, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        img1.annotations.append(PolyLine2D(10, 16, 20, 10, 20, 30, 40, 30, color=0xFF0000, stroke=2))
        img1.annotations.append(Square2D(72.5, 151.5, 30, stroke=3))
        # img1.annotations.append(Freehand2D(10, 10, 20, 10, 20, 30, 288, 30, color=0xFFFF00, stroke=3))
        img1.annotations.append(
            Freehand2D(75, 25, 116.50, 50, 116.50, 100, 75, 125, 33.50, 100, 33.50, 50, color=0xFFFF00,
                       stroke=3))  # a beautiful hexagon !!!

        # try a floating text
        img1.annotations.append(TAText2D(text='<font color="#FF0000">top left by coords</font>'))
        img1.annotations.append(TAText2D(text='<font color="#FF0000">top left by coords2 vert</font>',
                                         text_orientation='Y'))  # vertical
        img1.annotations.append(TAText2D(x=img1.width() / 2, y=img1.height() / 2,
                                         text='<font color="#FFFF00">free floating text</font>'))  # NB THIS IS NOT CLONED PROPERLY
        img1.annotations.append(TAText2D(x=img1.width() / 2, y=img1.height() / 2,
                                         text='<font color="#FFFF00">free floating text2 vert</font>',
                                         text_orientation='Y'))  # NB THIS IS NOT CLONED PROPERLY
        img1.annotations.append(
            ScaleBar(30, '<font color="#FF00FF">10µm</font>'))  # default scale bar placement is bottom right
        img1.annotations.append(ScaleBar(30, '<font color="#FF00FF">right µm</font>',
                                         placement='top-right'))  # here I specify the bar to be top right specifically

    img1.set_rotation(42)
    # img1.crop(60, 30, 0,
    #           0)  # environ 10, 25 --> see why that is --> so even left and right alone give x and y translation -−> this is most likely due to the rotation
    # img1.crop(60, 60, 0,
    #           0)  # environ 10, 25 --> see why that is --> so even left and right alone give x and y translation -−> this is most likely due to the rotation
    # img1.crop(0, 60, 0,
    #           0)  # environ 10, 25 --> see why that is --> so even left and right alone give x and y translation -−> this is most likely due to the rotation
    # img1.crop(60, 0, 0,
    #           0)  # environ 10, 25 --> see why that is --> so even left and right alone give x and y translation -−> this is most likely due to the rotation
    img1.crop(30, 40, 60, 80)  # extra correction 15 et -9
    return img1


def channel_n_lut_test():

    # do a mini test for channels and luts
    # the idea is just to have one or two channeled images just to see how this will look
    shapes_to_draw = []
    # do the same for all images and all channels

    images_to_test = ['/E/Sample_images/sample_images_me_for_demo/PD_images_from_cellimagelibrary.org_be_carefull_not_all_PD/stack/35481_orig.tif',
                      # '/E/Sample_images/sample_images_FIJI/Blend_Final.IPL', # fails to read but why ???
                      '/E/Sample_images/sample_images_FIJI/colocsample1b.lsm',
                      '/E/Sample_images/sample_images_quickfigure/all chan in order.zvi',
                      '/E/Sample_images/sample_images_FIJI/2chZT.lsm',
                      '/E/Sample_images/sample_images_FIJI/Celegans-5pc-17timepoints.tif',
                      '/E/Sample_images/sample_images_FIJI/confocal-series.tif',
                      '/E/Sample_images/sample_images_FIJI/MAX_organ-of-corti.tif',
                      '/E/Sample_images/sample_images_FIJI/organ-of-corti.tif',
                      '/E/Sample_images/sample_images_FIJI/mitosis.tif',
                      '/E/Sample_images/sample_images_FIJI/Rat_Hippocampal_Neuron.tif',
                      '/E/Sample_images/sample_images_FIJI/mri-stack.tif',
                      ]

    for iii,image in enumerate(images_to_test):
        try:
            chan_image = Image2D(image)
            if iii == 0:
                # I just rotate it so that I can apply all of this
                chan_image.set_rotation(42)
                chan_image.crop_left = 32
                chan_image.crop_right = 32
                chan_image.fill_color=0xFF0000

            # chan_image = Image2D('/E/Sample_images/sample_images_quickfigure/all chan in order.tif') # somehow zvi got broken for unknown reason

            if 'c' in guess_dimensions(chan_image.img):
                for ch in range(chan_image.img.shape[-1]):
                    chan_image.annotations.append(TAText2D(text=f'<font color=red>ch{ch}   {chan_image.img[...,ch].min()} {chan_image.img[...,ch].max()}</font>', placement='top-left'))

            chan_image.annotations.append(TAText2D(text=f'<font color=green>global   {chan_image.img.min()} {chan_image.img.max()}</font>', placement='center_v-left'))
            shapes_to_draw.append(chan_image)

        # tst = Img('/E/Sample_images/sample_images_quickfigure/all chan in order.zvi')
        # print(tst.metadata) # quite good and would be perfect if I could get the LUT...

        # not ok all luts are green but I'm almost there


        except:
            traceback.print_exc()
    # sys.exit(0)

    return shapes_to_draw


def mini_test(return_image_directly=False):
    shapes_to_draw = []

    img1 = get_complex_tst_image()

    # img1.crop(60, 0, 0, 0)  # --> environ 20 et 40

    # img1.set_rotation(90)
    # img1.crop(60, 0, 0, 0) #scale  0.4765625 # --> environ 60 et 60 --> somehow related to bounding rect --> understand why that is!!!
    # img1.crop(90, 0, 0, 0)  # 0.41796875000000006--> environ 110, 110 --> try understand it maybe scale matters --> it may be proportional to the rect -−> I will manage now I know !!!!
    # # img1.crop(0, 90, 0, 0)  # --> environ -110, -110 --> try understand it maybe scale matters --> so indeed they have two opposite signs --> so a subtraction would do the job
    #
    #
    # img1.crop(0, 0, 0, 90) # --> 75,-75
    # img1.crop(0, 0, 90, 0) # --> -75,75  --> 0.59375
    # # img1.crop(60, 60, 30, 30) # --> 0
    # #
    # img1.crop(60, 0, 90, 0) # --> -30, 160 scale 0.4765625
    # img1.crop(60, 60, 90, 0) # --> -125 125 scale =0.359375
    # img1.crop(60, 60, 0, 90) # --> 125 -125 scale =0.359375

    # try to understand this or recode the other

    tmp = get_shape_after_rotation_and_crop(img1.getRect(raw=True), img1.theta, img1.crop_left, img1.crop_right,
                                            img1.crop_top, img1.crop_bottom)

    #
    # print('in da test')
    # print('orig rect', img1.getRect(raw=True))
    # print('rotated', tmp.boundingRect())
    # tmp2 = get_shape_after_rotation_and_crop(img1.getRect(raw=True), img1.theta, 0,0,0,0)
    # print('in da test')
    # print('rotated2', tmp2.boundingRect())

    print('~' * 60)

    trafo = QTransform()
    orig_rect = img1.getRect(raw=True)

    trafo.translate(orig_rect.center().x(), orig_rect.center().y())
    trafo.rotate(img1.theta)
    trafo.translate(-orig_rect.center().y(), -orig_rect.center().y())

    rotated_orig = trafo.mapToPolygon(orig_rect.toRect())
    print(rotated_orig.boundingRect())

    # PyQt6.QtCore.QRect(-79, 0, 304, 146)

    rotated_cropped = QRectF(rotated_orig.boundingRect())
    rotated_cropped = QRectF(rotated_cropped.x() - img1.crop_left, rotated_cropped.y() - img1.crop_top,
                             rotated_cropped.width() - img1.crop_left - img1.crop_right,
                             rotated_cropped.height() - img1.crop_top - img1.crop_bottom)

    print('rotated_cropped', rotated_cropped)

    trafo2 = QTransform()
    trafo2.translate(rotated_cropped.center().x(), rotated_cropped.center().y())
    trafo2.rotate(-img1.theta)
    trafo2.translate(-rotated_cropped.center().y(), -rotated_cropped.center().y())

    rotated_cropped_back = trafo2.mapToPolygon(rotated_cropped.toRect())

    print('rotated_cropped_back', rotated_cropped_back.boundingRect())

    print(QRectF(rotated_cropped_back.boundingRect()).center() - rotated_cropped.center())
    print(QRectF(rotated_cropped_back.boundingRect()).center() - orig_rect.center())
    print(rotated_cropped.center() - orig_rect.center())

    print(rotated_cropped_back.boundingRect().center(), QRectF(rotated_cropped_back.boundingRect()).center())

    print('~' * 60)

    # it is totally dependent on the scale and it seems largely predictible --> it probably depends on size of the image or on its AR -−> maybe test it!!!

    if return_image_directly:
        return img1

    # img1.crop(60, 60, 0, 0)  # --> 0,0
    # get the size of the shape when rotated ??? --> TODO

    grp = Group(img1)

    shapes_to_draw.append(grp)

    return shapes_to_draw


def demo_img():
    path_to_counter = '/E/Sample_images/counter/'  # path_to_counter + '/'
    img0 = Image2D(path_to_counter + '/00.png')
    img0.set_to_scale(0.5)
    img0.setTopLeft(120, 60)



    inset = Image2D(path_to_counter + '/01.png')

    scale_bar = ScaleBar(30, '<font color="#FF00FF">10µm</font>', placement=Position('top-right'))
    img0.annotations.append(scale_bar)  # , Image2D.TOP_LEFT)
    img0.annotations.append(
        inset)  # Image2D.BOTTOM_RIGHT)  # ça marche meme avec des insets mais faudrait controler la taille des trucs... --> TODO
    img0.annotations.append(TAText2D(text='<font color="#FF0000">bottom-right3</font>',
                                     placement=Position('bottom-right')))  # , Image2D.BOTTOM_RIGHT)
    img0.annotations.append(TAText2D(text='<font color="#00FF00">top-right1</font>', placement=Position(
        'top-right')))  # , Image2D.BOTTOM_RIGHT) -−> this one is not properly placed --> NO IT IS OK IT IS JUST THAT I HAD TOO MANY INSETS AND SO THE STUFF LIED OUTSIDE OF THE SHAPE -−> THIS WAS THE OPTIMAL ALIGNMENT AND NOT A BUG !!!
    img0.annotations.append(TAText2D(text='<font color="#FF00FF">bottom-left1</font>',
                                     placement=Position('bottom-left')))  # , Image2D.BOTTOM_RIGHT)
    img0.annotations.append(TAText2D(text='<font color="#FF0000">top-left</font>',
                                     placement=Position('top-left')))  # , Image2D.BOTTOM_RIGHT)
    img0.annotations.append(
        TAText2D(text='multi<BR>line<BR>top-left text', placement=Position('top-left')))  # , Image2D.BOTTOM_RIGHT)
    img0.annotations.append(TAText2D(text='<font color="#00FF00">top-left4</font>', placement=Position('top-left'),
                                     fill_color=0xFF00FF))  # , Image2D.BOTTOM_RIGHT)
    img0.annotations.append(TAText2D(text='<font color="#FFF0F0">bottom-center_h2</font>',
                                     placement=Position('bottom-center_h')))  # , Image2D.BOTTOM_RIGHT)
    img0.annotations.append(TAText2D(text='<font color="#00000F">left-center_v3</font>',
                                     placement=Position('left-center_v')))  # , Image2D.BOTTOM_RIGHT)

    img0.annotations.append(Rectangle2D(88, 88, 200, 200, stroke=0.65, color=0xFF00FF))
    img0.annotations.append(Ellipse2D(88, 88, 200, 200, stroke=1, color=0x00FF00))
    img0.annotations.append(Circle2D(33, 33, 200, stroke=2, color=0x0000FF))
    img0.annotations.append(Line2D(33, 33, 88, 88, stroke=3, color=0x0000FF))
    img0.annotations.append(Line2D(66, 66, 176, 176, stroke=3, color=0xFF00FF, arrow=True))
    img0.annotations.append(
        Line2D(66, 66, 176, 176, stroke=3, color=0x00FFFF, arrow=False))  # just to see the tip of the arrow
    img0.annotations.append(Freehand2D(10, 10, 20, 10, 20, 30, 288, 30, color=0xFFFF00, stroke=4))
    img0.annotations.append(PolyLine2D(100, 100, 200, 100, 200, 300, 288, 300, color=0xFFFF00, stroke=6))
    img0.annotations.append(Point2D(128, 128, color=0xFFFF00, stroke=5))
    return img0

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    # tst_test()
    sys.exit(0)