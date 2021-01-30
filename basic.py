import ee
from ee_plugin import Map
from .dataset import gee_dataset
from urllib3.exceptions import ProtocolError
from pprint import pprint


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
                raise exc() #useless in further tries, return this error
            return res
        return wrapper

Map.addLayer = exec_til_success(ProtocolError, 3)(Map.addLayer)
ee.Image.getInfo = exec_til_success(ProtocolError, 3)(ee.Image.getInfo)


class PreprocessingEE:
    "Realizes base functions of preparing images for further processing: importing, sorting, filtering, extracting etc"
    def __init__(self, start_date, end_date, limit=10, pallete=['black', 'white']):
        self.start = start_date
        self.end = end_date
        self.limit = limit
        self.pallete = pallete
        self.layers = {}#format: layer name in qgis: {'id': unique id used in import , 'meta': information, can have properties, 'obj': ee.Object

    def import_e(self,image_name, bands, layer_name='gee_data'):
        """Imports collection or single image to the gis with visual parameters,
        Important news: less settings and saving layer information with qgis layer name for furthering computations"""
        if image_name in gee_dataset:
            type_ = gee_dataset[image_name]['type']#we can't know if it's collection or single image, trying to define
            image = type_(image_name)
            if type_ is ee.ImageCollection:
                image = image.limit(self.limit).median()#ee_plugin doesn't support adding image collections
        else:
            image = ee.Image(image_name)#then support only Images(temporaly)
        visParams = {'bands': bands} #    !!! change while refactoring
        info = {layer_name: {
                    'id': image_name, #for fast retreiving bands from dataset
                    'meta': image.getInfo()
                    'obj': image
        }}
        self.layers.update(info)
        Map.addLayer(image, visParams, layer_name, True)
        return image

    def set_limit(self,n):
        self.limit = n

    def set_date_range(self, start=self.start, end=self.end):
        self.start = start
        self.end = end

    def set_pallete(self, pallete):
        self.pallete = pallete