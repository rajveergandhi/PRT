import arcpy
import os

class rasterTypeFactory():
    def __init__(self): #not reqd by API - can be used by pyDeveloper to declare and initialise class members
        self.Description = "Factory for available raster types"

    def getRasterTypesInfo(self):
        return [
                {
                  'rasterTypeName': 'pyLS8',
                  'builderName': 'LS8Builder',
                  'description': 'supports landsat 8 metadata files',
                  'supportsOrthorectification': False,
                  'supportsSeamline': False,
                  'supportsStereo': False,
                  'enableClipToFootprint': True,
                  'rasterProduct': True,
                  'allowSimplification': True,
                  'dataSourceType': 1,
                  'dataSourceFilter':'*_mtl_python.txt',
                  'crawlerName':'LS8Crawler',
                  'supportedProductTypes': 'Level1:Level1;L1G;L1T|Surface Reflectance:Surface Reflectance:VARIANT_FALSE',
                  'productDefinitionName': 'Landsat8',
                  'productDefinitionDisplayName': 'pythonLandsat8',
                  'processingTemplates' :  [
                                              {
                                                'name': 'Multispectral',
                                                'enabled':True,
                                                'outputDatasetTag':'MS',
                                                'primaryInputDatasetTag':'MS',
                                                'productTemplate':True,
                                                'functionTemplate':'stretch_ms.rft.xml'
                                              },
                                              {
                                                'name': 'Panchromatic',
                                                'enabled':False,
                                                'outputDatasetTag':'Pan',
                                                'primaryInputDatasetTag':'Pan',
                                                'productTemplate':True,
                                                'functionTemplate': 'stretch_pan.rft.xml'
                                              },
                                              {
                                                'name': 'Pansharpen',
                                                'enabled':False,
                                                'outputDatasetTag':'Pansharpened',
                                                'primaryInputDatasetTag':'MS',
                                                'productTemplate':True,
                                                'functionTemplate': 'stretch_psh.rft.xml'
                                              }    
                                            ],
                  'bandProperties': [
                                      {
                                        'bandName' : 'CoastalAerosol',
                                        'bandIndex': 0,
                                        'wavelengthMin':430.0,
                                        'wavelengthMax':450.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Blue',
                                        'bandIndex': 1,
                                        'wavelengthMin':450.0,
                                        'wavelengthMax':510.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Green',
                                        'bandIndex': 2,
                                        'wavelengthMin':530.0,
                                        'wavelengthMax':590.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Red',
                                        'bandIndex': 3,
                                        'wavelengthMin':640.0,
                                        'wavelengthMax':670.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'NearInfrared',
                                        'bandIndex': 4,
                                        'wavelengthMin':850.0,
                                        'wavelengthMax':880.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'ShortWaveInfrared_1',
                                        'bandIndex': 5,
                                        'wavelengthMin':1570.0,
                                        'wavelengthMax':1650.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'ShortWaveInfrared_2',
                                        'bandIndex': 6,
                                        'wavelengthMin':2110.0,
                                        'wavelengthMax':2290.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Cirrus',
                                        'bandIndex': 7,
                                        'wavelengthMin':1360.0,
                                        'wavelengthMax':1380.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Panchromatic',
                                        'bandIndex': 0,
                                        'wavelengthMin':500.0,
                                        'wavelengthMax':680.0,
                                        'datasetTag':'Pan'
                                      }
                                    ],
                  'auxiliaryFields':[
                                        {
                                          'fieldName': 'testField1',
                                          'fieldType': 3,
                                          'fieldAlias': 'test Field1',
                                          'fieldPrecision': 2
                                        },
                                        {
                                          'fieldName': 'testField2',
                                          'fieldType': 4,
                                          'fieldAlias': 'test Field2',
                                          'fieldLength': 4
                                        }
                                    ]
                }
        ]
     
class LS8Builder(): 
    def __init__(self): #not reqd by API - can be used by pyDeveloper to declare and initialise class members
        self.name = "RasterDatasetBuilder" 

    def canBuild(self, datasetPath):
        #open the mtl.txt file, look for specific identifier...return true if search is successful, else return false
        f = open(datasetPath, 'r')
        metadata = f.read()
        if "LANDSAT_8" in metadata :
            return True

        return False

    def readMetFile(self, datasetPath): #helper function - not reqd by API
        f = open(datasetPath, 'r')
        metFileProperties = {} #Dict
        for line in f: #Iterates through every line in the file
            if "=" in line: 
                l = line.split("=") #Seperate by "=" and put into a dict
                metFileProperties[l[0].strip()] = l[1].strip().replace('"','')  #First word is key, second word is value

        f.close()
        return metFileProperties 

        
    def build(self, fileItemURI):
        datasetPath = fileItemURI.get('filePath')
        tag = fileItemURI.get('tag')
        
        metFileProperties = self.readMetFile(datasetPath)

        ulx = metFileProperties['CORNER_UL_PROJECTION_X_PRODUCT']
        uly = metFileProperties['CORNER_UL_PROJECTION_Y_PRODUCT']
        urx = metFileProperties['CORNER_UR_PROJECTION_X_PRODUCT']
        ury = metFileProperties['CORNER_UR_PROJECTION_Y_PRODUCT']
        lrx = metFileProperties['CORNER_LR_PROJECTION_X_PRODUCT']
        lry = metFileProperties['CORNER_LR_PROJECTION_Y_PRODUCT']
        llx = metFileProperties['CORNER_LL_PROJECTION_X_PRODUCT']
        lly = metFileProperties['CORNER_LL_PROJECTION_Y_PRODUCT']
        coordinates = [[float(ulx), float(uly)], [float(urx), float(ury)], [float(lrx), float(lry)], [float(llx), float(lly)]]

        dirPath = os.path.split(datasetPath)[0]
        description = arcpy.Describe(os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_1']))
        srs = description.SpatialReference
        g = arcpy.Geometry("Polygon", arcpy.Array([arcpy.Point(*cordn) for cordn in coordinates]), srs, False, False)

        msBuilderItem = {}
        panBuilderItem = {}
        
        if ('MS' in tag):
            msBuilderItem = {
                           'itemURI': {
                                        'filePath':fileItemURI.get('filePath'),
                                        'displayName': fileItemURI.get('displayName'),
                                        'tag': 'MS',
                                        'groupName': fileItemURI.get('groupName')
                                        },
                           'raster': {
                                        'rasterFunction': '{"rasterFunction": "CompositeBand","rasterFunctionArguments": {"Rasters":["Raster1", "Raster2", "Raster3", "Raster4", "Raster5", "Raster6", "Raster7", "Raster8"]}}',
                                        'Raster1': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_1']),
                                        'Raster2': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_2']),
                                        'Raster3': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_3']),
                                        'Raster4': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_4']),
                                        'Raster5': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_5']),
                                        'Raster6': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_6']),
                                        'Raster7': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_7']),
                                        'Raster8': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_9'])
                                     },
                           'spatialReference': srs,
                           'footprint': g,
                           'variables' : {
                                            'defaultMaximumInput': 65535,
                                            'defaultGamma': 1
                                          },
                           'keyProperties': {
                                              'sensorName': 'Landsat 8',
                                              'sunElevation': metFileProperties['SUN_ELEVATION'],
                                              'sunAzimuth': metFileProperties['SUN_AZIMUTH'],
                                              'cloudCover': metFileProperties['CLOUD_COVER'],
                                              'productName': metFileProperties['DATA_TYPE'],
                                              'testField1': 1.2654,
                                              'testField2': 'abcd',
                                              'bandProperties': [
                                                                    {
                                                                      'bandName': 'CoastalAerosol',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'Blue',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'Green',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'Red',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'NearInfrared',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'ShortWaveInfrared_1',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'ShortWaveInfrared_2',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    },
                                                                    {
                                                                      'bandName': 'Cirrus',
                                                                      'reflectanceGain':  0.000020,
                                                                      'reflectanceBias': -0.100000
                                                                    }
                                                                  ]
                                            },
                          }

        if ('Pan' in tag):
            panBuilderItem = {
                           'itemURI': {
                                        'filePath':fileItemURI.get('filePath'),
                                        'displayName': fileItemURI.get('displayName'),
                                        'tag': 'Pan',
                                        'groupName': fileItemURI.get('groupName')
                                        },
                           'raster': {'Raster1': os.path.join(dirPath, metFileProperties['FILE_NAME_BAND_8'])},
                           'spatialReference': srs, 
                           'footprint': g,
                           'variables' : {
                                          'defaultMaximumInput': 65535,
                                          'defaultGamma': 1,
                                         },
                            'keyProperties': {
                                              'sensorName': 'Landsat 8',
                                              'sunElevation':metFileProperties['SUN_ELEVATION'],
                                              'sunAzimuth': metFileProperties['SUN_AZIMUTH'],
                                              'cloudCover': metFileProperties['CLOUD_COVER'],
                                              'productName': metFileProperties['DATA_TYPE'],
                                              'testField1': 0.59,
                                              'testField2': 'efgh',
                                              'bandProperties': [
                                                                    {
                                                                        'bandName': 'Panchromatic',
                                                                        'reflectanceGain':  0.000020,
                                                                        'reflectanceBias': -0.100000
                                                                    }
                                                                ] 
                                             },                     
                          }

        builderItemsList = list()
        if (bool(msBuilderItem)):
            builderItemsList.append(msBuilderItem)
        if (bool(panBuilderItem)):
            builderItemsList.append(panBuilderItem)

        return builderItemsList


class LS8Crawler():
    def __init__(self, **crawlerProperties):
        self.paths = crawlerProperties['paths']
        self.tags = ['MS', 'Pan']
        self.tagsIterator = iter(self.tags)
        self.pathsIterator = iter(self.paths)
        self.curPath = self.pathsIterator.next()

    def __iter__(self):
        return self

    def next(self):
        try:
            curTag = self.tagsIterator.next()
        except StopIteration:
            try:
                self.curPath = self.pathsIterator.next()
                self.tagsIterator = iter(self.tags)
                curTag = self.tagsIterator.next()
            except StopIteration:
                return None
            
        return {
                'filePath': self.curPath,
                'displayName': os.path.basename(self.curPath),
                'tag': curTag,
                'groupName': os.path.splitext(os.path.basename(self.curPath))[0],
                'productName':'L1G'
                }
