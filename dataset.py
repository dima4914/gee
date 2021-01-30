import ee


def generate_bands(pattern, num, rjust = 2):
    bands = []
    for i in range(1,num+1):
        bands.append(pattern+str(i).rjust(rjust,'0'))
    return bands


ASTER = generate_bands('B', 14)
ASTER[2] = 'B3N'

SENTINEL2_1C = generate_bands('B', 12)
SENTINEL2_1C.insert(8, 'B8A')
SENTINEL2_1C = SENTINEL2_1C + ['QA10', 'QA20', 'QA60']

LANDSAT7_TIER1 = generate_bands('B', 8, 1) + ['BQA']
LANDSAT7_TIER1[5] = 'B6_VCID_1'
LANDSAT7_TIER1.insert(6, 'B6_VCID_2')


gee_dataset = {
    'ASTER/AST_L1T_003': {
        'desc': 'ASTER is a multispectral imager that was launched on board NASA\'s Terra spacecraft in December,\
         1999. ASTER can collect data in 14 spectral bands from the visible to the thermal infrared.',
        'bands': ASTER,
        'type': ee.ImageCollection

    },
    'CGIAR/SRTM90_V4': {
        'desc': 'SRTM digital elevation dataset was originally produced to provide consistent,\
         high-quality elevation data at near global scope',
        'bands': ['elevation'],
        'type': ee.Image
    },
    "COPERNICUS/Landcover/100m/Proba-V-C3/Global": {
        'desc': 'CGLS is earmarked as a component of the Land service to operate a multi-purpose service component\
         that provides a series of bio-geophysical products on the status and evolution of land surface at global scale',
        'bands': ["discrete_classification",
                  "discrete_classification-proba",
                  "bare-coverfraction",
                  "urban-coverfraction",
                  "crops-coverfraction",
                  "grass-coverfraction",
                  "moss-coverfraction",
                  "water-permanent-coverfraction",
                  "water-seasonal-coverfraction",
                  "shrub-coverfraction",
                  "snow-coverfraction",
                  "tree-coverfraction",
                  "forest_type",
                  "data-density-indicator",
                  "change-confidence"],
        'type': ee.Image
    },
    "COPERNICUS/S2": {
        'desc': 'Sentinel-2 is a wide-swath, high-resolution, multi-spectral imaging mission supporting\
         Copernicus Land Monitoring studies, including the monitoring of vegetation, soil and water cover,\
          as well as observation of inland waterways and coastal areas',
        'bands': SENTINEL2_1C,
        'type': ee.ImageCollection
    },
    'COPERNICUS/S2_SR': {
        'desc': 'Sentinel-2 is a wide-swath, high-resolution, multi-spectral imaging mission supporting\
         Copernicus Land Monitoring studies, including the monitoring of vegetation, soil and water cover,\
          as well as observation of inland waterways and coastal areas.',
        'bands': SENTINEL2_1C + ["AOT", "WVP", "SCL", "TCI_R", "TCI_G", "TCI_B", "MSK_CLDPRB", "MSK_SNWPRB"],
        'type': ee.ImageCollection
    },
    'JRC/GSW1_0/GlobalSurfaceWater': {
        'desc': 'This dataset contains maps of the location and temporal\
        distribution of surface water from 1984 to 2015 and provides\
        statistics on the extent and change of those water surfaces',
        'bands': ["occurrence", "change_abs", "change_norm", "seasonality", "recurrence",
                  "transition", "max_extent"],
        'type': ee.Image
    },
    "LANDSAT/LC08/C01/T1": {
        'desc': 'Landsat 8 Collection 1 Tier 1 DN values, representing scaled, calibrated at-sensor radiance',
        'bands': generate_bands('B', 11, 1) + ['BQA'],
        'type':  ee.ImageCollection
    },
    "LANDSAT/LE07/C01/T1": {
        'desc': 'Landsat 7 Collection 1 Tier 1 DN values, representing scaled, calibrated at-sensor radiance',
        'bands': LANDSAT7_TIER1,
        'type': ee.ImageCollection
    },
    "LANDSAT/LM05/C01/T1": {
        'desc': 'Landsat 5 MSS Collection 1 Tier 1 DN values, representing scaled, calibrated at-sensor radiance',
        'bands': generate_bands('B', 4, 1) + ['BQA'],
        'type': ee.ImageCollection
    },
    "NASA/MEASURES/GFCC/TC/v3": {
        'desc': 'The Landsat Vegetation Continuous Fields (VCF) tree cover layers contain estimates of the\
         percentage of horizontal ground in each 30-m pixel covered by woody vegetation greater than 5 meters in height',
        'bands': ['tree_canopy_cover', 'uncertainty', 'source_index'],
        'type': ee.ImageCollection
    },
    "NOAA/NGDC/ETOPO1": {
        'desc': 'ETOPO1 is a 1 arc-minute global relief model of Earth\'s surface\
         that integrates land topography and ocean bathymetry',
        'bands': ['bedrock', 'ice_surface'],
        'type': ee.Image
    },
    "UMD/hansen/global_forest_change_2019_v1_7": {
        'desc': 'Results from time-series analysis of Landsat images in characterizing global forest extent and change',
        'bands': ['treecover2000',
                  'loss',
                  'gain',
                  'first_b30',
                  'first_b40',
                  'first_b50',
                  'first_b70',
                  'last_b30',
                  'last_b40',
                  'last_b50',
                  'last_b70',
                  'datamask',
                  'lossyear'],
        'type': ee.Image
    },
    "USGS/GTOPO30": {
        'desc': 'GTOPO30 is a global digital elevation model (DEM) with a horizontal grid spacing of 30 arc seconds',
        'bands': ['elevation'],
        'type': ee.Image
    }
}
