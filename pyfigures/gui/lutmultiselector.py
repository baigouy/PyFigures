# in fact there will just be two possibilities --> either default/acquisition or a chosen LUT
from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from batoolset.luts.lut_minimal_test import list_available_luts, PaletteCreator
from batoolset.pyqts.tools import get_items_of_combo, createPixmapFromLUT
import numpy as np
from qtpy.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QComboBox, QLabel
from qtpy.QtGui import QPixmap, QImage,QIcon
from qtpy.QtCore import Qt

class LutWidget(QWidget):

    def __init__(self, nb_channels, parent=None, user_specified_luts=None):
        super().__init__(parent)

        self.all_LUTs = []
        # self.image = image
        self.nb_channels=nb_channels

        # Create a vertical layout for the QWidget
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.available_luts = list_available_luts()
        self.lutcreator = PaletteCreator()

        # Create a QGroupBox for each channel in the image
        for ch in range(nb_channels):

            # Create a QGroupBox instance
            channel_box = QGroupBox(f"Channel {ch}")

            # Create a horizontal layout for the QGroupBox
            channel_layout = QVBoxLayout()

            # Create a QComboBox instance to select the LUT for the current channel
            lut_combo = QComboBox()
            lut_combo.addItem('Default/Acquisition')

            for lll,lut in enumerate(self.available_luts):  # Skip the first LUT as it's 'Default/Acquisition'
                if lll == 0:
                    # lut_combo.addItem(QIcon(None), lut)
                    continue
                lut_combo.addItem(lut)

            # we try to reload previous LUT if it exists
            if user_specified_luts and len(user_specified_luts) == self.nb_channels and user_specified_luts[ch]:
                for iii, pos in enumerate(get_items_of_combo(lut_combo)):
                    if pos.lower().strip() == user_specified_luts[ch].lower().strip():
                        lut_combo.setCurrentIndex(iii)
                        break

            lut_combo.currentIndexChanged.connect(lambda idx, combo=lut_combo: self.updateLabel(combo))

            self.all_LUTs.append(lut_combo)
            channel_layout.addWidget(lut_combo)

            # Set the layout for the QGroupBox
            channel_box.setLayout(channel_layout)

            # Add the QGroupBox to the layout
            layout.addWidget(channel_box)

        preview_box = QGroupBox(f"Preview")
        preview_box_layout = QVBoxLayout()
        self.label = QLabel()
        self.label.setFixedSize(256,32)
        preview_box_layout.addWidget(self.label)
        preview_box.setLayout(preview_box_layout)
        layout.addWidget(preview_box)

    def updateLabel(self, combo):
        # Get the icon and text of the current item
        # icon = combo.itemIcon(combo.currentIndex())
        # Display the text and icon in the label
        lut = combo.currentText()
        if not 'cquisi' in lut:
            # Create a dictionary to store LUT images
            lut_list = self.lutcreator.list
            lut_array = self.lutcreator.create3(lut_list[lut])
            lut_img = createPixmapFromLUT(lut_array, height=32, length=256)
        else:
            lut_img = QPixmap()
        self.label.setPixmap(lut_img)


    def getAllLuts(self):
        all_luts = [lut.currentText() if not 'cquisi' in lut.currentText() else None for lut in self.all_LUTs ]
        return all_luts

if __name__ == '__main__':
    import numpy as np
    from qtpy.QtWidgets import QApplication

    # Create a sample image with shape (512, 512, 3)
    image = np.random.randint(0, 256, size=(512, 512, 3), dtype=np.uint8)

    # Create a QApplication instance
    app = QApplication([])

    specified_luts = [None, None, 'DNA'] # simulate existing channels
    # Create a LutWidget instance
    lut_widget = LutWidget(nb_channels=image.shape[-1], user_specified_luts=specified_luts)

    # try to reload the channels

    # Show the LutWidget instance
    lut_widget.show()

    print(lut_widget.getAllLuts())

    # Run the QApplication event loop
    app.exec_()
