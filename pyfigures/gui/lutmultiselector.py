# in fact there will just be two possibiolities --> either default/acquisition or a chosen LUT

from batoolset.settings.global_settings import set_UI # set the UI to qtpy
set_UI()
from batoolset.luts.lut_minimal_test import list_available_luts, PaletteCreator
from batoolset.pyqt.tools import get_items_of_combo
import numpy as np
from qtpy.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QComboBox, QLabel
from qtpy.QtGui import QPixmap, QImage
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

        # Create a QGroupBox for each channel in the image
        # for ch in range(image.shape[-1]):
        for ch in range(nb_channels):

            # Create a QGroupBox instance
            channel_box = QGroupBox(f"Channel {ch}")

            # Create a horizontal layout for the QGroupBox
            channel_layout = QVBoxLayout()

            # Create a QLabel instance to display the channel image
            # channel_label = QLabel()
            # channel_label.setPixmap(QPixmap.fromImage(QImage(image[:,:,ch], image.shape[0], image.shape[1], QImage.Format_Grayscale8)))
            # channel_layout.addWidget(channel_label)
            # Convert the channel data to a bytes object
            if False:
                channel_data = image[:, :, ch].tobytes()

                # Create a QImage instance from the bytes object
                channel_image = QImage(channel_data, image.shape[1], image.shape[0], QImage.Format_Grayscale8)

                # Create a QLabel instance to display the channel image
                channel_label = QLabel()
                channel_label.setPixmap(QPixmap.fromImage(channel_image))
                channel_layout.addWidget(channel_label)

            # Create a QComboBox instance to select the LUT for the current channel
            lut_combo = QComboBox()
            lut_combo.addItem('Default/Acquisition')
            # lut_combo.addItem('None')
            available_luts = list_available_luts()
            for lll,lut in enumerate(available_luts):
                if lll==0:
                    continue
                lut_combo.addItem(lut)
            # lut_combo.currentTextChanged.connect(lambda lut=lut_combo.currentText(), ch=ch: self.set_lut(lut, ch, channel_label))
            # print('ch',ch)

            # we try to reload previous LUT if it exists
            if user_specified_luts and len(user_specified_luts)==self.nb_channels and user_specified_luts[ch]:
                    for iii, pos in enumerate(get_items_of_combo(lut_combo)):
                        if pos.lower().strip() == user_specified_luts[ch].lower().strip():
                            lut_combo.setCurrentIndex(iii)
                            break

            # lut_combo.currentTextChanged.connect(lambda lut=lut_combo.currentText(), ch=ch: self.set_lut(lut, ch)) # that works
            self.all_LUTs.append(lut_combo)
            channel_layout.addWidget(lut_combo)

            # Set the layout for the QGroupBox
            channel_box.setLayout(channel_layout)

            # Add the QGroupBox to the layout
            layout.addWidget(channel_box)



    # I need to add None and default or system/user/acquisition settings

    # see what to do if none
    # if it is contained in the list --> then just write the name and if it is not contained then store the whole LUT as base64

    def getAllLuts(self):
        all_luts = [lut.currentText() if not 'cquisi' in lut.currentText() else None for lut in self.all_LUTs ]
        return all_luts

    # def set_lut(self, lut, ch):
    #     print('#'*10)
    #
    #     lutcreator = PaletteCreator()
    #     luts_lst = lutcreator.list
    #     # lut = lutcreator.create3(luts[lut])
    #     if lut in luts_lst:
    #         palette = lutcreator.create3(luts_lst[
    #                                          lut])  # if LUT is from a string --> try save that, otherwise serialize the whole array in the sortest possible way
    #         palette = np.asarray(palette)
    #         print(palette.shape)
    #
    #     # try:
    #     #     # palette = lutcreator.create3(luts[0])
    #     #
    #     # except:
    #     #     palette = lutcreator.create3(luts_lst[
    #     #                                      "GRAY"])  # if LUT is from a string --> try save that, otherwise serialize the whole array in the sortest possible way
    #     else:
    #         print('unsupported LUT', lut)
    #
    #
    #
    #     # now try to get the LUT
    #
    #     # Get the LUT values for the current LUT name
    #     # lut_values = get_lut_values(lut)
    #     #
    #     # # Apply the LUT to the current channel
    #     # channel = self.image[...,ch]
    #     # channel = lut_values[channel]
    #     #
    #     # # Update the channel image in the QLabel
    #     # channel_image = QImage(channel.astype(np.uint8), self.image.shape[0], self.image.shape[1], QImage.Format_Grayscale8)
    #     # channel_label.setPixmap(QPixmap.fromImage(channel_image))
    #     print(lut, ch)
    #
    #
    #     print(self.getAllLuts())


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
