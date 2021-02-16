from qgis.utils import iface
from qgis.core import *


def get_vector_names():
    'retrieves names of vector layers in project'
    names = []
    layers = QgsProject.instance().mapLayers().values()
    for layer in layers:
        if isinstance(layer, QgsVectorLayer):
            names.append(layer.name())
    return names


def get_gee_names():
    'retrieves names of gee layers in project'
    names = []
    layers = QgsProject.instance().mapLayers().values()
    for layer in layers:
        if layer.customProperty('ee-object'):
            names.append(layer.name())
    return names


def pan_sharp(image, bands=['B4','B3', 'B2'], panchrom='B8'):
    hsv = image.select(bands).rgbToHsv()
    sharpened = ee.Image.cat([hsv.select('hue'), hsv.select('saturation'), image.select(panchrom)]).hsvToRgb()
    return sharpened


