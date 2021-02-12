# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GEEManagerDialog
                                 A QGIS plugin
 This plugin implements user-friendly interface (GUI) to make access to Goggle Earth Engine server easier
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-12-31
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Dima Okunev
        email                : dima@
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os
import sys

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from .dataset import gee_dataset
from .basic import *
import webbrowser

#from .geeGUI_dialog_base import Ui_GEEManagerDialogBase as FORM_CLASS

#sys.path.append(os.path.dirname(__file__))
# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'geeGUI_dialog_base.ui'))
KERNEL_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'kernelGUI.ui'))
DOWNLOAD_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'downloadGUI.ui'))
EXPORT_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'exportGUI.ui'))


def set_radio_group(radio1, radio2, func):
    buttonGroup = QtWidgets.QButtonGroup()
    buttonGroup.addButton(radio1, 1)
    buttonGroup.addButton(radio2, 2)
    buttonGroup.buttonClicked.connect(func)
    return buttonGroup


class KernelDialog(QtWidgets.QWidget, KERNEL_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(KernelDialog, self).__init__(parent)
        self.setupUi(self)


class DownloadDialog(QtWidgets.QWidget, DOWNLOAD_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(DownloadDialog, self).__init__(parent)
        self.setupUi(self)
        datasets = gee_dataset.keys()
        self.datasets.addItems(datasets)
        self.datasets.editTextChanged.connect(self.on_dataset_selected)
        self.manager = PreprocessingEE('','')
        self.bands = [self.B1, self.B2, self.B3]
        self.on_dataset_selected(tuple(datasets)[0])

        self.num_bands = 3
        self.bandButtonGroup = set_radio_group(self.radio1, self.radio3, self.set_number_of_bands)
        self.loadButton.clicked.connect(self.load)

    def set_number_of_bands(self, obj):
        id = self.bandButtonGroup.id(obj)
        if id==1:
            self.bands[0].setEnabled(True)
            for band in self.bands[1:]:
                band.setDisabled(True)
            self.num_bands = 1
        elif id ==2:
            for band in self.bands:
                band.setEnabled(True)
            self.num_bands = 3

    def clear(self):
        for band in self.bands:
            band.clear()
        self.desc.clear()

    def on_dataset_selected(self, text):
        self.clear()
        if text in gee_dataset:
            data = gee_dataset[text]
            for band in self.bands:
                band.addItems(data['bands'])
            self.desc.setText(data['desc'])

    def load(self):
        start_date = self.dateStart.date().toPyDate()
        end_date = self.dateEnd.date().toPyDate()
        cloud = self.cloudBox.value()
        limit = self.limitBox.value()
        dataset = self.datasets.currentText()
        name = self.layerName.text()

        max_ = self.maxBox.value()
        min_ = self.minBox.value()
        bands = []
        for i in range(self.num_bands):
            bands.append(self.bands[i].currentText())
        visParams = {'bands': bands}
        if max_ and min_:
            visParams.update({'max': max_, 'min': min_})
        self.manager.set_date_range(start_date, end_date)
        self.manager.set_cloud(cloud)
        self.manager.set_limit(limit)
        self.manager.set_vis(visParams)
        geom = get_selected_gee()
        if geom: geom = geom[0]
        self.manager.import_e(dataset, geom, name)


class ExportDialog(QtWidgets.QWidget, EXPORT_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ExportDialog, self).__init__(parent)
        self.setupUi(self)
        self.exportButton.clicked.connect(self.on_export)
        self.manager = ExportingEE()
        self.exportButtonGroup = set_radio_group(self.driveRadio, self.assetRadio, self.toggle_mode)
        self.exportButtonGroup.buttonClicked.emit(self.driveRadio)
        self.toCE.clicked.connect(lambda: webbrowser.open('https://code.earthengine.google.com/',
                                                          new=2))
        self.mode = 'drive'

    def on_layers_update(self):
        self.layerBox.clear()
        self.layerBox.addItems(self.manager.layers.names())

    def toggle_mode(self, obj):
        id = self.exportButtonGroup.id(obj)
        if id==1:
            self.pyramidBox.hide()
            self.asset_label.hide()
            self.mode = 'drive'
        elif id==2:
            self.pyramidBox.show()
            self.asset_label.show()
            self.mode = 'asset'

    def on_export(self):
        layer = self.layerBox.currentText()
        scale = self.scaleBox.value()
        pix = float(self.pixBox.text())
        folder = self.folder.text()
        pyramid = self.pyramidBox.currentText()
        geom = get_selected_gee()
        if geom: geom = geom[0]
        self.manager.export_e(layer, scale, pix, folder=folder, pyramid=pyramid, geometry=geom, dest=self.mode)


class GEEManagerDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(GEEManagerDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        self.export = ExportDialog()
        self.panels = {
            '  Download dataset': DownloadDialog(),
            '  Apply kernels': KernelDialog(),
            '  Estimate indices': DownloadDialog(),
            '  Export': self.export,
            '  Settings': ExportDialog()
        }
        self.stackLayout = QtWidgets.QStackedLayout()
        self.base_window.setLayout(self.stackLayout)
        for i in self.panels:
            self.stackLayout.addWidget(self.panels[i])
        self.stackLayout.setCurrentIndex(0)
        self.menu.itemClicked.connect(self.turn_panel)

    def turn_panel(self, x):
        self.stackLayout.setCurrentWidget(self.panels[x.text()])
        self.update_layers_info()

    def update_layers_info(self):
        "syncronize information about changing layers between all panels"
        self.export.on_layers_update()

