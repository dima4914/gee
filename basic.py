import ee
from ee_plugin import Map, utils
from .dataset import gee_dataset
from urllib3.exceptions import ProtocolError
from qgis.utils import iface
from qgis.core import *
from PyQt5 import QtCore, QtWidgets
import datetime as dt
import json
import os
import zipfile
import urllib
import re


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


def exception_as_gui(exc):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                res = func(*args, **kwargs)
            except exc as e:
                QtWidgets.QMessageBox.critical(None, type(e).__name__, str(e))
            else:
                return res
        return wrapper
    return decorator


Map.addLayer = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(Map.addLayer)
ee.Image.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.Image.getInfo)
ee.ImageCollection.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.ImageCollection.getInfo)
ee.FeatureCollection.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.FeatureCollection.getInfo)
ee.FeatureCollection.getDownloadURL = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.FeatureCollection.getDownloadURL)
ee.Dictionary.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.Dictionary.getInfo)
ee.Number.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(ee.Number.getInfo)


class LayerManager:
    def __init__(self):
        self.layers = {}
        self.cache = {}
        iface.projectRead.connect(self.load)
        iface.newProjectCreated.connect(self.clear)

    def subscript_layer(self, layer_name, image, vis={}, qgs_layer=None, info=None):
        if not qgs_layer:
            qgs_layer = utils.get_layer_by_name(layer_name)
        if not info:
            info = image.getInfo()
        if info.get('properties', '') and info['properties'].get('description',''):
            del info['properties']['description'] # for saving memory
        image_name = info.get('id',None)
        res = {
            layer_name: {
                'gee_id': image_name, #for fast retreiving bands from dataset
                'meta': info,
                'obj': image,
                'qgs_layer': qgs_layer,#to manipulate layer with qgis interface
                'vis': vis
            }
        }
        self.layers.update(res)
        return res

    def remove_layer(self, layer_name):
        if layer_name in self.layers:
            self.layers.pop(layer_name)
        else: self.cache.pop(layer_name)

    def __getitem__(self, index):
        if not self.layers.get(index,''):
            if not self.cache.get(index, ''):
                layer = utils.get_layer_by_name(index)
                if layer and layer.customProperty('ee-object'):
                    dp = layer.dataProvider()
                    if hasattr(dp, 'ee_info'):
                        obj = dp.ee_object
                    else:
                        obj = ee.deserializer.fromJSON(layer.customProperty('ee-object'))
                        if type(obj) == ee.ComputedObject:
                            return
                    info = dp.ee_info if hasattr(dp, 'ee_info') else {}
                    vis = json.loads(layer.customProperty('ee-object-vis'))
                    self.subscript_layer(index, obj, vis, layer, info)
                    res = self.layers[index]
                else:
                    message = 'Layer doesn\'t exist or is not EE layer'
                    raise NameError(message)
            else:
                res = self.cache[index]
        else:
            res = self.layers[index]
        return res

    def dump_cache_layer(self, layer_name, obj, vis, meta=None):
        if not meta: meta = obj.getInfo()
        res = {layer_name: {'obj': obj, 'vis': vis, 'meta': meta}}
        self.cache.update(res)
        return res

    def names(self):
        return self.layers.keys()

    def cache_names(self):
        return list(self.cache.keys())

    def vis_params(self, layer_name):
        return self[layer_name]['vis']

    def save(self, save_cache=False, proxy_type=None):
        res = {}
        layers = {}
        if proxy_type:
            for layer in self.layers:
                if isinstance(self.layers[layer]['obj'], proxy_type):
                    layers.update({layer: self.layers[layer].copy()})
        else:
            for layer in self.layers:
                layers.update({layer: self.layers[layer].copy()})
        for layer in layers:
            layers[layer].pop('qgs_layer')
            layers[layer].pop('meta')
            layers[layer]['type'] = layers[layer]['obj'].__class__.__name__
            layers[layer]['obj'] = layers[layer]['obj'].serialize()
        project = QgsProject.instance()
        res.update({'layers': json.dumps(layers)})
        if save_cache:
            cache = {}
            if proxy_type:
                for layer in self.cache:
                    if isinstance(self.cache[layer]['obj'], proxy_type):
                        cache.update({layer: self.cache[layer].copy()})
            else:
                for layer in self.cache:
                    cache.update({layer: self.cache[layer].copy()})
            for layer in cache:
                cache[layer].pop('meta')
                cache[layer]['type'] = cache[layer]['obj'].__class__.__name__
                cache[layer]['obj'] = cache[layer]['obj'].serialize()
            res.update({'cache': json.dumps(cache)})
        project.setCustomVariables(res)
        return project.write()

    def load(self):
        project = QgsProject.instance()
        data = project.customVariables()
        try:
            layers = json.loads(data['layers']) if 'layers' in data else {}
            cache = json.loads(data['cache']) if 'cache' in data else {}
            for layer in layers:
                obj = ee.deserializer.fromJSON(layers[layer]['obj'])
                if type(obj) == ee.ComputedObject:
                    type_ = eval('ee.' + layers[layer]['type'])
                    obj = type_(obj)
                layers[layer]['obj'] = obj
            for layer in cache:
                obj = ee.deserializer.fromJSON(cache[layer]['obj'])
                if type(obj) == ee.ComputedObject:
                    type_ = eval('ee.' + cache[layer]['type'])
                    obj = type_(obj)
                cache[layer]['obj'] = obj
            self.layers = layers
            self.cache = cache
        except RuntimeError:
            pass
        return True

    def enable_project_sync(self, flag):
        if flag:
            iface.projectRead.connect(self.load)
            iface.newProjectCreated.connect(self.clear)
        else:
            iface.projectRead.disconnect(self.load)
            iface.newProjectCreated.disconnect(self.clear)

    def clear(self):
        self.layers = {}
        self.cache = {}


_layers = LayerManager()#shared by several classes, needed to be global but is non-importing


def get_layer_manager():
    return _layers


class PreprocessingEE:
    "Realizes base functions of preparing images for further processing: importing, sorting, filtering, extracting etc"
    def __init__(self, start_date, end_date, limit=10, cloud = 20):
        if isinstance(start_date, dt.date): start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, dt.date): end_date = end_date.strftime('%Y-%m-%d')
        self.start = ee.Date(start_date)
        self.end = ee.Date(end_date)
        self.limit = limit
        self.layers = _layers#format: layer id in qgis: {'id': unique gee id used in import , 'meta': information, can have properties, 'obj': ee.Object
        self.cloud = cloud
        self.vis_params = {}

    @exception_as_gui(ee.ee_exception.EEException)
    def import_e(self,image_name, geometry=None, layer_name='gee_data'):
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
        self.show_and_subscript(image, layer_name)

    def show_and_subscript(self, image, layer_name ='gee_data', info=None):
        if not info: info = image.getInfo()
        torender = image.mosaic() if isinstance(image,ee.ImageCollection) else image
        Map.addLayer(torender, self.vis_params, layer_name, True)#ee_plugin doesn't support adding image collections, can make mosaic instead
        self.layers.subscript_layer(layer_name, image, self.vis_params, info=info)  # here we merge qgis and gee layer information
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

    def set_vis(self, vis):
        self.vis_params = vis


class MapAlgebraEE:
    def __init__(self, exp=''):
        self.layers = _layers
        self.rb_pattern = '(\w+)@(\w+)'
        self.func_pattern = '(\w{3,5})\s?\((\w+)@(\w+)\)'
        self.exp = exp
        self.prefix = 'VV'

    def get_lname_bands(self):
        rb = re.findall(self.rb_pattern, self.exp)
        names =[]
        bands = []
        for i in rb:
            names.append(i[0])
            bands.append(i[1])
        return names, bands

    def retrieve_gee_bands(self):
        names, bands = self.get_lname_bands()
        gee_bands = []
        for i in range(len(names)):
            layer = self.layers[names[i]]
            gee_bands.append(layer['obj'].select(bands[i]))
        return gee_bands

    def apply_raster_func(self):
        fr = re.findall(self.func_pattern, self.exp)
        return fr

    def apply(self):
        'algorithm is to retrieve func, layer name and band; make images and substitute them in exp with prefix-id'
        images = []
        fr = re.findall(self.func_pattern, self.exp)
        s = -1
        for s,i in enumerate(fr):
            gee_obj = self.layers[i[1]]['obj']
            gee_obj = gee_obj.select(i[2])
            if isinstance(gee_obj, ee.ImageCollection): gee_obj = gee_obj.median()
            gee_obj = eval(f'gee_obj.{i[0]}()')
            images.append(gee_obj)
            self.exp = re.sub(self.func_pattern, self.prefix+str(s), self.exp,1)
        br = re.findall(self.rb_pattern, self.exp)
        for name, band in br:
            s+=1
            gee_obj = self.layers[name]['obj']
            gee_obj = gee_obj.select(band)
            if isinstance(gee_obj, ee.ImageCollection): gee_obj = gee_obj.median()
            images.append(gee_obj)
            self.exp = re.sub(self.rb_pattern, self.prefix+str(s), self.exp,1)
        params = {}
        for s,image in enumerate(images):
            params.update({self.prefix+str(s): image})
        res = images[0].expression(self.exp, params)

        return res

    def set_expression(self, exp):
        self.exp = exp


class ExportingEE:
    def __init__(self):
        self.layers = _layers

    @exception_as_gui(ee.ee_exception.EEException)
    def export_e(self,  layer_name, scale, max_pixels=1e9, format_='GeoTIFF', folder = 'GEE_Data',
                 pyramid='mean', geometry=None, dest='drive',verbose=True):
        image = self.layers[layer_name]['obj']
        visParams = self.layers.vis_params(layer_name)
        segments = layer_name.split('/')
        if segments[0] == 'users':
            desc = '_'.join(segments[2:])
        else:
            desc = layer_name.replace('/', '_')
        if isinstance(image, ee.ImageCollection):
            imageRGB = image.map(lambda img: img.visualize(**visParams).copyProperties(img, img.propertyNames())).median()
        else:
            imageRGB = image.visualize(**visParams)
        settings = {
            'image': imageRGB,
            'scale': scale,
            'description': desc,
            'maxPixels': max_pixels
        }
        if geometry: settings.update({'region': geometry})
        if dest == 'asset':
            settings.update({'assetId': folder+'/'+desc,
                             'pyramidingPolicy': {'.default': pyramid}})
            task = ee.batch.Export.image.toAsset(**settings)
        else:
            settings.update({'folder': folder, 'fileFormat': format_,})
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


def qgsfeature_to_gee(feature, crs="EPSG:4326"):
    geom_ee = qgsgeometry_to_gee(feature.geometry(), crs) if feature.hasGeometry() else None
    field_names = feature.fields().names()
    raw_values = feature.attributes()
    values =[]
    for value in raw_values:
        if isinstance(value, QtCore.QVariant):
            value = None
        values.append(value)
    props = dict(zip(field_names, values))
    if 'id' not in field_names:
        props.update({'id': feature.id()})
    return ee.Feature(geom_ee, props)


def qgsvector_to_gee(layer, expression='', limit=0):
    if isinstance(layer, str):
        layer = utils.get_layer_by_name(layer)
    if isinstance(layer, QgsVectorLayer):
        crs = f'EPSG:{layer.sourceCrs().postgisSrid()}'
        collection = []
        request = QgsFeatureRequest()
        if expression:
            request = request.setFilterExpression(expression)
        if limit:
            request.setLimit(limit)
        for feature in layer.getFeatures(request):
            collection.append(qgsfeature_to_gee(feature, crs))
        return ee.FeatureCollection(collection)


def qgsprojection_to_gee(projection):
    wkt = projection.toWkt()
    return ee.Projection(wkt)


def download_geeshp(asset, path, addToCanvas=False):
    path = os.path.abspath(path)
    fc = ee.FeatureCollection(asset)
    url = fc.getDownloadURL('shp')
    task = DownloadTask('download zip with shp', url, path, addToCanvas)
    QgsApplication.taskManager().addTask(task)


class DownloadTask(QgsTask):
    def __init__(self, description, url, path, add):
        super().__init__(description, QgsTask.CanCancel)
        self.exception = None
        self.url = url
        self.path = path
        self.add = add
        self.category = 'SHP downloading'

    def run(self):
        QgsMessageLog.logMessage('Started task "{}"'.format(self.description()), self.category, Qgis.Info)
        try:
            urllib.request.urlretrieve(self.url, self.path)
        except Exception as exc:
            self.exception = exc
            return False
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(f'Task {self.description} succeded',
                                     self.category, Qgis.Success)
            if self.add:
                add_ziplayer(self.path, 'table')
        elif self.exception:
            QgsMessageLog.logMessage(f'Task {self.description} failed: {str(self.exception)}',
                                     self.category, Qgis.Critical)
        else:
            QgsMessageLog.logMessage(f'Task {self.description} failed without exception',
                                     self.category, Qgis.Warning)

    def cancel(self):
        QgsMessageLog.logMessage(f'Terminated: {self.description}', self.category, Qgis.Warning)
        super().cancel()


def add_ziplayer(path, name, shp_name='table.shp'):
    z = zipfile.ZipFile(path, 'r')
    z.extractall()
    shp_path = os.path.split(path)[0] + os.path.sep
    vlayer = QgsVectorLayer(shp_path + shp_name, name, 'ogr')
    if not vlayer.isValid():
        iface.messageBar().pushMessage('Error', 'Cannot load vector layer',
                                       level=Qgis.Critical, duration=10)
    else:
        QgsProject.instance().addMapLayer(vlayer)


def geevector_to_qgs(collection, crs='epsg:4326', addToCanvas=True):
    l = collection.toList(5000)
    l.getInfo = exec_til_success(ProtocolError, NUM_TILL_SUCCESS)(l.getInfo)
    gee_features = l.getInfo()
    first = gee_features[0]
    type_ = first['geometry']['type']
    vlayer = QgsVectorLayer(type_+'?crs='+crs, 'table', 'memory')
    dp = vlayer.dataProvider()
    fields = []
    for field in first['properties']:
        fields.append(QgsField(field, QtCore.QVariant.String, 'text', 20))
    dp.addAttributes(fields)
    vlayer.updateFields()
    features = []
    for f in gee_features:
        fet = QgsFeature()
        coords = f['geometry']['coordinates']
        wkt = to_wkt(type_, coords)
        geom = QgsGeometry.fromWkt(wkt)
        fet.setGeometry(geom)
        fet.setAttributes([str(i) for i in f['properties'].values()])
        features.append(fet)
    dp.addFeatures(features)
    vlayer.updateExtents()

    if addToCanvas:
        if not vlayer.isValid():
            iface.messageBar().pushMessage('Error', 'Cannot load vector layer',
                                           level=Qgis.Critical, duration=10)
        else:
            QgsProject.instance().addMapLayer(vlayer)
    return vlayer


def to_wkt(type_, coords):
    wkt = ''
    if type_ == 'LineString':
        for i in coords[:-1]:
            wkt += ' '.join([str(i[0]), str(i[1])]) + ', '
        wkt += ' '.join([str(coords[-1][0]), str(coords[-1][1])])
        wkt = type_.upper() + ' (' + wkt + ')'
    elif type_ == 'Polygon':
        coords = coords[0]
        for i in coords[:-1]:
            wkt += ' '.join([str(i[0]), str(i[1])]) + ', '
        wkt += ' '.join([str(coords[-1][0]), str(coords[-1][1])])
        wkt = type_.upper() + ' ((' + wkt + '))'
    else:
        wkt = type.upper() + '(' + ' '.join([str(coords[0]), str(coords[1])]) + ')'
    return wkt


def geefeature_to_qgs(feature):
    info = feature.getInfo()
    res = QgsFeature()
    res.setAttributes(list(info['properties'].values()))
    wkt = to_wkt(info['geometry']['type'],info['geometry']['coordinates'])
    res.setGeometry(QgsGeometry.fromWkt(wkt))
    return res


def get_selected_gee(layer, n=1):
    if isinstance(layer, str):
        layer = utils.get_layer_by_name(layer)
    geometry_list = []
    if isinstance(layer,  QgsVectorLayer) and (layer.selectedFeatureCount()>0):
        crs = f'EPSG:{layer.sourceCrs().postgisSrid()}'
        request = QgsFeatureRequest()
        if n: request.setLimit(n)
        for feature in layer.getSelectedFeatures(request):
            geom = feature.geometry()
            gee_object = qgsgeometry_to_gee(geom, crs)
            geometry_list.append(gee_object)
        return geometry_list

