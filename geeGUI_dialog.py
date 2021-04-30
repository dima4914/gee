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
from .utils import *
import webbrowser
from .panels import OperForm

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
SETTINGS_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'settingsGUI.ui'))


def set_radio_group(*radios, func=None):
    buttonGroup = QtWidgets.QButtonGroup()
    for s,radio in enumerate(radios):
        buttonGroup.addButton(radio, s+1)
    if func:
        buttonGroup.buttonClicked.connect(func)
    return buttonGroup


class KernelDialog(QtWidgets.QWidget, KERNEL_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(KernelDialog, self).__init__(parent)
        self.setupUi(self)
        self.funcs = [self.cos, self.sin, self.tan, self.log10,self.acos, self.asin, self.atan, self.log,
                 self.cosh, self.sinh, self.tanh, self.abs_, self.min_, self.max_, self.floor, self.ceil]
        self.operands = [self.plus, self.mul, self.pow, self.mod, self.minus, self.div,
                    self.lte, self.gte, self.lt, self.gt, self.eq, self.neq,
                    self.and_, self.or_, self.nor, self.not_, self.ternar]
        self.braces = [self.sc, self.sce]
        self.buttons = QtWidgets.QButtonGroup()
        self.buttons.setExclusive(False)
        for s, button in enumerate(self.funcs+self.operands+self.braces):
            self.buttons.addButton(button, s)
        self.buttons.buttonClicked.connect(self.insertText)
        self.manager = MapAlgebraEE()
        self.model = QtCore.QStringListModel([], parent=self)
        self.init_bands_list()
        self.bandList.doubleClicked.connect(self.on_band_clicked)
        self.estimateButton.clicked.connect(self.estimate)

    def insertText(self, obj):
        text = obj.text()
        id = self.buttons.id(obj)
        border = len(self.funcs)
        if  id in range(border):
            text=' '+ text+ '('
        elif id in range(border, len(self.operands)+border):
            text = ' ' + text+ ' '
        self.rasterExpression.insertPlainText(text)

    def init_bands_list(self):
        items = []
        gee_names = get_gee_names()
        for name in gee_names+self.manager.layers.cache_names():
            layer = self.manager.layers[name]
            if not layer: continue
            obj = layer['obj']
            if isinstance(obj, ee.Image):
                bands = [band['id'] for band in layer['meta']['bands']]
            else:
                bands = [band['id'] for band in layer['meta']['features'][0]['bands']]
            for b in bands:
                items.append(f'{name}@{b}')
        self.model = QtCore.QStringListModel(items, parent=self)
        self.bandList.setModel(self.model)

    def on_band_clicked(self, index):
        text  = index.data()
        self.rasterExpression.insertPlainText(text)

    def estimate(self):
        self.manager.set_expression(self.rasterExpression.toPlainText())
        res = self.manager.apply()
        layer_name = self.layerName.text()
        max = self.maxBox.value()
        min = self.minBox.value()
        vis = {}
        if max: vis.update({'max': max})
        if min: vis.update({'min': min})
        palette = self.palette.text()
        if palette: vis.update({'palette': ['white', palette]})
        if self.addButton.isChecked():
            pr = PreprocessingEE('','')
            pr.set_vis(vis)
            pr.show_and_subscript(res, layer_name)
        else:
            self.manager.layers.dump_cache_layer(layer_name, res, vis)


class OperationDialog(OperForm):
    def __init__(self, parent=None):
        """Constructor."""
        super(OperationDialog, self).__init__(parent)
        self.setupUi()
        self.manager = PreprocessingEE('','')
        func1 = lambda x: self.clipping.setFixedSize(60,15) if x else self.clipping.setFixedSize(200,60)
        func2 = lambda x: self.painting.setFixedSize(480,15) if x else self.painting.setFixedSize(480,180)
        func3 = lambda x: self.reducing.setFixedSize(480,15) if x else self.reducing.setFixedSize(480,180)
        self.clipping.collapsedStateChanged.connect(func1)
        self.painting.collapsedStateChanged.connect(func2)
        self.reducing.collapsedStateChanged.connect(func3)
        self.clipWarning.hide()
        self.paintGroup = set_radio_group(self.paintRadio, self.blendRadio, func=self.toggle_paint_mode)
        self.opaqGroup = set_radio_group(self.strokeRadio, self.opaqueRadio)
        self.reduceGroup = set_radio_group(self.bandsRadio, self.region, self.neighborhood, func=self.toggle_reduce_mode)
        self.reduceGroup.buttonClicked.emit(self.bandsRadio)

        self.clipCollection.clicked.connect(self.on_clip) #it is button
        self.paintButton.clicked.connect(self.on_paint)
        self.reduceButton.clicked.connect(self.on_reduce)

        self.init_combos()

    def init_combos(self):
        self.geeLayer.clear()
        self.vectorLayer.clear()
        active_gee = [name for name in get_gee_names() if self.manager.layers[name]]
        self.geeLayer.addItems(active_gee+self.manager.layers.cache_names())
        self.vectorLayer.addItems(get_vector_names())

    @exception_as_gui((GeometryNotFoundError, VectorNotFoundError))
    def get_selected_collection(self):
        if self.useSelected.isChecked():
            geometry = get_selected_gee(self.vectorLayer.currentText(), 0)
            if not geometry:
                raise GeometryNotFoundError('Features are not selected in the current vector layer')
            collection = [ee.Feature(geom, None) for geom in geometry]
            collection = ee.FeatureCollection(collection)
        else:
            collection = qgsvector_to_gee(self.vectorLayer.currentText())
            if not collection: raise VectorNotFoundError('Current vector layer is not valid')
        return collection

    def on_clip(self):
        gee_layer = self.manager.layers[self.geeLayer.currentText()]
        image = gee_layer['obj']
        self.manager.set_vis(gee_layer['vis'])
        collection = self.get_selected_collection()
        if isinstance(image, ee.Image):
            res = image.clipToCollection(collection)
        else:
            res = image.map(lambda img: img.clipToCollection(collection))
        name = self.layer_name.text()
        if name: self.geeLayer.addItem(name)
        if self.addCheck.isChecked():
            self.manager.show_and_subscript(res, name, gee_layer['meta'])
        else:
            self.manager.layers.dump_cache_layer(name, res, gee_layer['vis'], gee_layer['meta'])

    def toggle_paint_mode(self, obj):
        id = self.paintGroup.id(obj)
        if id == 1:
            self.opacitySlide.setDisabled(True)
            self.palette.setDisabled(True)
        else:
            self.opacitySlide.setEnabled(True)
            self.palette.setEnabled(True)

    def on_paint(self):
        gee_layer = self.manager.layers[self.geeLayer.currentText()]
        image = gee_layer['obj']
        collection = self.get_selected_collection()
        property = self.property.text()
        args = [1] if not property else [property]

        max = self.maxBox.value()
        min = self.minBox.value()
        visParams = {}
        vis = {}
        if max: visParams.update({'max': max})
        if min: visParams.update({'min': min})

        if self.paintRadio.isChecked():
            vis = gee_layer['vis']
            vis.update(visParams)
            self.manager.set_vis(vis)
            if self.strokeRadio.isChecked():
                args.append(2)
                if isinstance(image, ee.ImageCollection):
                    res = image.map(lambda img: img.paint(collection, *args))
                else:
                    res = image.paint(collection, *args)
            else:
                if isinstance(image,ee.ImageCollection):
                    res = image.map(lambda img: img.paint(collection, args[0]).paint(collection, 0, 2))
                else:
                    res = image.paint(collection, args[0]).paint(collection, 0, 2)
        else:
            empty = ee.Image().byte()
            palette = self.palette.text()
            opacity = self.opacitySlide.value()/100
            visParams.update({'opacity': opacity})
            if palette: visParams.update({'palette': ['000000', palette]})
            if self.strokeRadio.isChecked():
                args.append(2)
                empty = empty.paint(collection, *args)
            else:
                empty = empty.paint(collection, args[0]).paint(collection, 0, 2)
            empty = empty.visualize(**visParams)
            if isinstance(image, ee.ImageCollection):
                image = image.map(lambda img: img.visualize(**gee_layer['vis']))
                res = image.map(lambda img: img.blend(empty))
            else:
                image = image.visualize(**gee_layer['vis'])
                res = image.blend(empty)
        name = self.layer_name.text()
        if name: self.geeLayer.addItem(name)
        if self.addCheck.isChecked():
            self.manager.show_and_subscript(res, name)
        else:
            self.manager.layers.dump_cache_layer(name, res, vis)

    def toggle_reduce_mode(self, obj):
        id = self.reduceGroup.id(obj)
        if id == 1:
            self.scaleBox.setDisabled(True)
            self.kernelRadius.setDisabled(True)
            self.pixBox.setDisabled(True)
            self.kernelType.setDisabled(True)
        elif id == 2:
            self.scaleBox.setEnabled(True)
            self.kernelRadius.setDisabled(True)
            self.pixBox.setEnabled(True)
            self.kernelType.setDisabled(True)
        else:
            self.scaleBox.setDisabled(True)
            self.pixBox.setDisabled(True)
            self.kernelRadius.setEnabled(True)
            self.kernelType.setEnabled(True)

    #@exception_as_gui(TypeError)
    def on_reduce(self):
        reducerType = self.typeBox.currentText()
        gee_name = self.geeLayer.currentText()
        reducer = eval(f'ee.Reducer.{reducerType}()')
        gee_layer = self.manager.layers[gee_name]
        image = gee_layer['obj']
        vis = {}
        vis.update(gee_layer['vis'])
        if self.bandsRadio.isChecked():
            res = image.reduce(reducer)
            if isinstance(image, ee.ImageCollection):
                bands = [band+'_'+reducerType for band in vis['bands']]
                print(bands)
            else:
                bands = [reducerType]
            geom = get_selected_gee(self.vectorLayer.currentText())
            params = {'scale':1000, 'maxPixels': 1e12}
            if geom: params.update({'geometry': geom[0]})
            max = res.reduceRegion(ee.Reducer.max(), **params)
            min = res.reduceRegion(ee.Reducer.min(), **params)
            if isinstance(image, ee.Image):
                max = ee.Number(max.get(bands[0]))
                min = ee.Number(min.get(bands[0]))
            else:
                if geom:
                    max = max.values().sort().getNumber(-1)
                    min = min.values().sort().getNumber(0)
            if geom: vis.update({'max': max.getInfo(), 'min': min.getInfo()})
            vis.update({'bands': bands})
        elif self.region.isChecked():
            scale = self.scaleBox.value()
            maxPix = float(self.pixBox.text())
            geom = get_selected_gee(self.vectorLayer.currentText())
            if not geom: raise GeometryNotFoundError('Feature is not selected in the current vector layer')
            else: geom = geom[0]
            if isinstance(image, ee.ImageCollection):
                raise TypeError('Cannot reduce collection, too many data for output')
            else:
                res = image.reduceRegion(reducer, geom, scale, maxPixels=maxPix).getInfo()#dictionary
                string = ''
                for key in res:
                    string += key + ': ' + str(res[key]) + '\n'
                QtWidgets.QMessageBox.information(self, f'Applied {reducerType} reducer to {gee_name}', string)
                return
        else:
            kernel = eval(f'ee.Kernel.{self.kernelType.currentText()}({self.kernelRadius.value()})')
            if isinstance(image, ee.ImageCollection):
                res = image.map(lambda img: img.reduceNeighborhood(reducer, kernel))
            else:
                res = image.reduceNeighborhood(reducer, kernel)
            bands = [band + '_' + reducerType for band in vis['bands']]
            vis.update({'bands': bands})
        name = self.layer_name.text()
        if name: self.geeLayer.addItem(name)
        self.manager.set_vis(vis)
        if self.addCheck.isChecked():
            self.manager.show_and_subscript(res, name)
        else:
            self.manager.layers.dump_cache_layer(name, res, vis)


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
        self.bandButtonGroup = set_radio_group(self.radio1, self.radio3, func=self.set_number_of_bands)
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
        geom = get_selected_gee(iface.activeLayer())
        if geom: geom = geom[0]
        self.manager.import_e(dataset, geom, name)


class ExportDialog(QtWidgets.QWidget, EXPORT_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(ExportDialog, self).__init__(parent)
        self.setupUi(self)
        self.exportButton.clicked.connect(self.on_export)
        self.manager = ExportingEE()
        self.exportButtonGroup = set_radio_group(self.driveRadio, self.assetRadio, func=self.toggle_mode)
        self.exportButtonGroup.buttonClicked.emit(self.driveRadio)
        self.toCE.clicked.connect(lambda: webbrowser.open('https://code.earthengine.google.com/',
                                                          new=2))
        self.mode = 'drive'

    def on_layers_update(self):
        self.layerBox.clear()
        active_gee = [name for name in get_gee_names() if self.manager.layers[name]]
        self.layerBox.addItems(active_gee+self.manager.layers.cache_names())

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
        geom = get_selected_gee(iface.activeLayer())
        if geom: geom = geom[0]
        self.manager.export_e(layer, scale, pix, folder=folder, pyramid=pyramid, geometry=geom, dest=self.mode)


class SettingsDialog(QtWidgets.QWidget, SETTINGS_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(SettingsDialog, self).__init__(parent)
        self.setupUi(self)
        self.saveButton.clicked.connect(self.saveLayers)
        for i, data in enumerate([None, ee.Image, ee.ImageCollection]):
            self.proxyType.setItemData(i, data)

    def saveLayers(self):
        proxy_type = self.proxyType.itemData(self.proxyType.currentIndex())
        lm = get_layer_manager()
        if lm.save(self.cacheOn.isChecked(), proxy_type):
            iface.messageBar().pushMessage('Done', 'Layers data was succesfully saved into project',
                                           level=Qgis.Success, duration=5)
        else:
            iface.messageBar().pushMessage('Error', 'Failed to save layers data, probable serialization can\'t be done',
                                           level=Qgis.Critical, duration=5)


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
        self.map_algebra = KernelDialog()
        self.operations = OperationDialog()
        self.panels = {
            '  Download dataset': DownloadDialog(),
            '  Map algebra': self.map_algebra,
            '  Operations': self.operations,
            '  Export': self.export,
            '  Settings': SettingsDialog()
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
        self.map_algebra.init_bands_list()
        self.operations.init_combos()

