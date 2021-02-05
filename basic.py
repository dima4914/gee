import ee
from ee_plugin import Map
from .dataset import gee_dataset
from urllib3.exceptions import ProtocolError
from qgis.utils import iface
from qgis.core import *
from PyQt5 import QtCore, QtWidgets
import datetime as dt
import json

NUM_TILL_SUCCESS = 3

def exec_til_success(exc, n):
    "executes [func that raises exc] n times till success or outputs fail"
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(n):
                try:
                    res = func(*args, **kwargs)
                except exc:
                    pass
                else: break
            else:
                raise exc(f'Aborted after {n} tries') #useless in further tries, return this error
            return res
        return wrapper
    return decorator


def exception_as_gui(func):
    def wrapper(*args, **kwargs):
        try:
            res = func(*args, **kwargs)
        except ee.ee_exception.EEException as exc:
            QtWidgets.QMessageBox.critical(None, type(exc).__name__, str(exc))
        else:
            return res
    return wrapper


Map.addLayer = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(Map.addLayer)
ee.Image.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.Image.getInfo)
ee.ImageCollection.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.ImageCollection.getInfo)


class LayerManager:
    def __init__(self):
        self.layers = {}

    def subscript_layer(self, image_name, layer_name, image, info=None):
        qgs_layer = iface.activeLayer()
        if not info:
            info = image.getInfo()
        del info['properties']['description']
        res = {
            layer_name: {
                'gee_id': image_name, #for fast retreiving bands from dataset
                'meta': info,
                'obj': image,
                'qgs_layer': qgs_layer #to manipulate layer with qgis interface
            }
        }
        self.layers.update(res)
        return res

    def remove_layer(self, layer_name):
        self.layers.pop(layer_name)

    def __getitem__(self, index):
        return self.layers[index]

    def names(self):
        return self.layers.keys()

_layers = LayerManager()#shared by several classes, needed to be global but is non-importing


class PreprocessingEE:
    "Realizes base functions of preparing images for further processing: importing, sorting, filtering, extracting etc"
    def __init__(self, start_date, end_date, limit=10, cloud = 20, palette=['black', 'white']):
        if isinstance(start_date, dt.date): start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, dt.date): end_date = end_date.strftime('%Y-%m-%d')
        self.start = ee.Date(start_date)
        self.end = ee.Date(end_date)
        self.limit = limit
        self.palette = palette
        self.layers = _layers#format: layer id in qgis: {'id': unique gee id used in import , 'meta': information, can have properties, 'obj': ee.Object
        self.cloud = cloud

    @exception_as_gui
    def import_e(self,image_name, bands, geometry=None, layer_name='gee_data'):
        """Imports collection or single image to the gis with visual parameters,
        Important news: less settings and saving layer information with qgis layer name for furthering computations"""
        if image_name in gee_dataset:
            type_ = gee_dataset[image_name]['type']#we can't know if it's collection or single image, trying to define
            image = type_(image_name)
            if type_ is ee.ImageCollection:
                if geometry:
                    image = image.filterBounds(geometry)
                image = self.process_clouding(image).filterDate(self.start, self.end)
                if self.limit: image = image.limit(self.limit)
        else:
            image = ee.Image(image_name)#then support only Images(temporaly)
        info = image.getInfo()
        visParams = {'bands': bands} #    !!! change while refactoring
        if len(bands) == 1: visParams.update({'palette': self.palette})
        Map.addLayer(image.mosaic(), visParams, layer_name, True)#ee_plugin doesn't support adding image collections, can make mosaic instead
        self.layers.subscript_layer(image_name, layer_name, image, info)  # here we merge qgis and gee layer information
        return image

    def search_property(self, info, base='CLOUD'):
        "make a guess that base is in name of property satisfy it's meaning"
        meta = info['features'][0]['properties']
        for attr in meta:
            if base.lower() in attr.lower():
                return attr


    def process_clouding(self, collection, info=None, name=None):
        "filter by cloudiness, if name of property is not given, then try to find it itself"
        if not info:
            info = collection.limit(2).getInfo()
        if name:
            return collection.filter(ee.Filter.lte(name, self.cloud))#.sort(name)  ops, gee doesn't visualize rasters sorted
                                                                    #that way even in the code editor
        attr = self.search_property(info)
        if attr:
            return collection.filter(ee.Filter.lte(attr, self.cloud))#.sort(attr)

    def set_limit(self,n):
        self.limit = n

    def set_cloud(self, cloud):
        self.cloud = cloud

    def set_date_range(self, start=None, end=None):
        if isinstance(start, dt.date): start = start.strftime('%Y-%m-%d')
        if isinstance(end, dt.date): end = end.strftime('%Y-%m-%d')
        self.start = ee.Date(start) if start else self.start
        self.end = ee.Date(end) if end else self.end

    def set_pallete(self, pallete):
        self.pallete = pallete


class ExportingEE:
    def __init__(self):
        self.layers = _layers

    def export_e(self, layer_name, scale, max_pixels=1e9, format_='GeoTIFF', folder = 'GEE_Data', geometry=None, verbose=True):
        image = self.layers[layer_name]['obj']
        if isinstance(image, ee.ImageCollection): image=image.median()
        settings = {
            'image': image,
            'scale': scale,
            'description': layer_name.replace('/', '_'),
            'fileFormat': format_,
            'folder': folder,
            'maxPixels': max_pixels
        }
        if geometry: settings.update({'region': geometry})
        task = ee.batch.Export.image.toDrive(**settings)
        task.start = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(task.start)
        task.start()
        if verbose:
            self.thread = StatusThread(task)
            self.thread.status_changed.connect(self.show_status, QtCore.Qt.QueuedConnection)
            self.thread.start()

    def show_status(self, state, body):
        level = {
            'READY': Qgis.Info,
            'RUNNING': Qgis.Info,
            'COMPLETED': Qgis.Success,
            'FAILED': Qgis.Critical
        }
        iface.messageBar().pushMessage(state, body,
                                       level=level[state], duration=10)


class StatusThread(QtCore.QThread):
    status_changed = QtCore.pyqtSignal(str,str)

    def __init__(self, task, parent=None):
        QtCore.QThread.__init__(self,parent)
        self.task = task

    def run(self):
        self.task.status = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(self.task.status)
        state = 'UNSUBMITTED'
        while True:
            info = self.task.status()
            if state != info['state']:
                state = info['state']
                string = f"{info['task_type']}, {info.get('destination_uris','')}"\
                        f"{info.get('error_message', '')} name: {info['description']}"
                self.status_changed.emit(state, string)
                if state in ['COMPLETED', 'FAILED']: break
            self.sleep(10)


def qgsgeometry_to_gee(geom, crs="EPSG:4326"):
    info = json.loads(geom.asJson())
    coords = info['coordinates']
    gee_object = eval(f"ee.Geometry.{info['type']}({coords}, '{crs}')")
    return gee_object


def get_selected_gee(n=1):
    layer = iface.activeLayer()
    geometry_list = []
    if isinstance(layer,  QgsVectorLayer) and (layer.selectedFeatureCount()>0):
        crs = f'EPSG:{layer.sourceCrs().postgisSrid()}'
        request = QgsFeatureRequest()
        request.setLimit(n)
        for feature in layer.getSelectedFeatures(request):
            geom = feature.geometry()
            gee_object = qgsgeometry_to_gee(geom, crs)
            geometry_list.append(gee_object)
        return geometry_list

