import os
import arcpy
import glob
import fnmatch
import json

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

class enumDataSourceType():
    dataSourceTypeUnknown = 0
    dataSourceTypeFile = 1
    dataSourceTypeFolder = 2

class rasterTypeFactory():

    def getRasterTypesInfo(self):
        productType_auxField = arcpy.Field()
        productType_auxField.name = 'ProductType'
        productType_auxField.aliasName = 'Product Type'
        productType_auxField.type = 'String'
        productType_auxField.length = 50

        return [
                {
                  'rasterTypeName': 'PlanetLabs',
                  'builderName': 'PlanetLabsBuilder',
                  'description': 'Class that reads metadata from PlanetLabs metadata files',
                  'supportsOrthorectification': True,
                  'supportsSeamline': False,
                  'supportsStereo': False,
                  'enableClipToFootprint': True,
                  'isRasterProduct': True,
                  'dataSourceType': enumDataSourceType.dataSourceTypeFile | enumDataSourceType.dataSourceTypeFolder,
                  'dataSourceFilter':'*.json',
                  'crawlerName':'PlanetLabsCrawler',
                  'supportedProductTypes': 'Level1:L1C;L1B',
                  'productDefinitionName' : 'PlanetLabs_3BANDS',
                  'processingTemplates' :  [
                                      {
                                        'name': 'Multispectral',
                                        'enabled': True,
                                        'outputDatasetTag':'MS',
                                        'primaryInputDatasetTag':'MS',
                                        'isProductTemplate': True,
                                        'functionTemplate': 'stretch_ms.rft.xml'
                                      },
                                    ],
                  'bandProperties': [
                                      {
                                        'bandName' : 'Blue',
                                        'bandIndex': 3,
                                        'wavelengthMin':420.0,
                                        'wavelengthMax':530.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Green',
                                        'bandIndex': 2,
                                        'wavelengthMin':500.0,
                                        'wavelengthMax':590.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Red',
                                        'bandIndex': 1,
                                        'wavelengthMin':610.0,
                                        'wavelengthMax':700.0,
                                        'datasetTag':'MS'
                                      },
                                    ],
                  'fields': [productType_auxField]
                }
        ]



class Utilties():

    def IsPlanetLabs(self, path):
        isPlanetLabs = True
        f.close()
        retVal = {'isPlanetLabs' : isPlanetLabs,
                  'tags' : ['MS'],
                  'path' : path
                  }
        return retVal

    def getProductName(self, path):
        readPath = os.path.dirname(path)
        for root, dirs, files in (os.walk(readPath)):
            for file in (files):
                if file.endswith(".tif"):
                    if "_unrectified" in str(file):
                        return "unrectified"
                    elif "_visual" in str(file):
                        return "visual"
                    else:
                        return "analytic"

#############################################################################################
#############################################################################################
###
###     PlanetLabs builder class
###
#############################################################################################
#############################################################################################
class PlanetLabsBuilder():

    def __init__(self, **kwargs):
        self.SensorName = 'PlanetLabs'
        self.utilities = Utilties()

    def canBuild(self, datasetPath):
        isPlanetLabs = self.utilities.isPlanetLabs(datasetPath)
        canBuild = isPlanetLabs['isPlanetLabs']
        return canBuild

    def build(self, itemURI):
        path = itemURI['path']
        tags = itemURI['tag']

        with open(path) as json_data:
            d = json.load(json_data)
            
            rpcPath = str(os.path.join(os.path.dirname(path), (str(d['id']) + "_rpc" + ".txt")))
            readRPC = open(rpcPath, "r")

            #root = ET.Element("GeodataTransform", {"xsi:type": 'typens:RPCXform', "xmlns:xsi": 'http://www.w3.org/2001/XMLSchema-instance', "xmlns:xs": 'http://www.w3.org/2001/XMLSchema', "xmlns:typens": 'http://www.esri.com/schemas/ArcGIS/10.5'})
            #geo = ET.SubElement(root, "GeodataXform", {"xsi:type":'typens:RPCXform'})
            #rpc = ET.SubElement(root, "RPC", {"xsi:type":'typens:ArrayOfDouble'})
            
            dataXform = '{"GeodataTransforms":[{"geodataTransform" : "RPC","geodataTransformArguments":{"coeff":['
          
            for line in readRPC.readlines():
               data = line.split(":")
               dataXform = dataXform + data[1] + ","
               #ET.SubElement(rpc, "double").text = data[1]


            dataXformString = dataXform[:-1]
            dataXformString = dataXformString + "]}}]}"
            
            #tree = ET.ElementTree(root)
            #tree.write(str(os.path.join(os.path.dirname(path), (str(d['id']) + "_geoDataTransform" + ".xml"))))
            #geoTransformData = str(os.path.join(os.path.dirname(path), (str(d['id']) + "_geoDataTransform" + ".xml")))

            fileName = str(d['id']) + "_" + self.utilities.getProductName(path) + ".tif"
            fullPath = str(os.path.join(os.path.dirname(path), fileName))

            desc = arcpy.Describe(fullPath)
            SR = desc.spatialReference
            srName = str(SR.name)
            if srName == "Unknown":
                espgCode = 4326
            else:
                espgCode = 3857

            coords_list = list()
            vertex_array = arcpy.Array()
            for all_vertex in d['geometry']['coordinates']:
                for vertex in all_vertex:
                    vertex_array.add(arcpy.Point(vertex[0], vertex[1]))
            footprint_geometry = arcpy.Polygon(vertex_array)

            camProperties = list()
            camProperty = {}
            camProperty['bit_depth'] = d['properties']['camera']['bit_depth']
            camProperty['colorMode'] = str(d['properties']['camera']['color_mode'])
            camProperty['exposure_time'] = d['properties']['camera']['exposure_time']
            camProperty['gain'] = d['properties']['camera']['gain']
            camProperty['tdi_pulses'] = d['properties']['camera']['tdi_pulses']
            camProperties.append(camProperty)

            metadata = {}
            DateTime = d['properties']['acquired']
            metadata['acquisitionDate'] = str(DateTime.split("T")[0])
            metadata['acquisitionTime'] = str(DateTime.split("T")[1])
            metadata['sunElevation'] = d['properties']['sun']['altitude']
            metadata['sunAzimuth'] = d['properties']['sun']['azimuth']
            metadata['SensorName'] = self.SensorName
            metadata['bandProperties'] = camProperties
            metadata['ProductType'] = self.utilities.getProductName(path)

            #rpc_file = open("C:\\TEMP\\PlanetLabs\\rpc.xml", 'r')
            #rpc_file = open(geoTransformData, 'r')
            #rpc_file = open('C:\\TEMP\\PlanetLabs\\rpcxform.txt', 'r')
            #rpc_text = rpc_file.read()

            builtItem = {}
            builtItem['spatialReference'] = espgCode
            builtItem['raster'] = { 'Raster1' : fullPath }
            builtItem['footprint'] = footprint_geometry
            builtItem['keyProperties'] = metadata
            builtItem['itemURI'] = { 'tag' : 'MS' }
            builtItem['geodataXform'] = dataXformString

            builtItemsList = list()
            builtItemsList.append(builtItem)
            return builtItemsList

#############################################################################################
#############################################################################################
###
###     PlanetLabs Crawlerclass
###
#############################################################################################
#############################################################################################
class PlanetLabsCrawler():

    def __init__(self, **crawlerProperties):

        self.utils = Utilties()
        global mygenerator

        def createGenerator(pathList, recurse, filter):
            for i in pathList:
                if os.path.isdir(i):
                    if recurse:
                        for root, dirs, files in (os.walk(i)):
                            for file in (files):
                                if file.endswith(".json"):
                                    filename = os.path.join(root, file)
                                    yield filename
                    else:
                        filter_to_scan = i + os.path.sep + filter
                        for filename in glob.glob(filter_to_scan):
                            yield filename
                else:
                    yield i

        self.paths = crawlerProperties['paths']
        self.recurse = crawlerProperties['recurse']
        self.filter = crawlerProperties['filter']
        if self.filter is (None or ""):
            self.filter = '*.json'
        try:
            mygenerator = createGenerator(self.paths, self.recurse, self.filter)
            self.curPath2 = next(mygenerator)

        except StopIteration:
            return None

        self.tags = ['MS']
        self.tagsIterator = iter(self.tags)

    def __iter__(self):
        return self

    def next(self):
        try:
            curTag = self.tagsIterator.next()
        except StopIteration:
            try:
                self.curPath2 = next(mygenerator)
                self.tags = ['MS']
                self.tagsIterator = iter(self.tags)
                curTag = self.tagsIterator.next()
            except StopIteration:
                return None

        if self.tags is not None:
            uri = {
			        'path': self.curPath2,
				    'displayName': os.path.basename(self.curPath2),
					'tag': curTag,
					'groupName': os.path.split(os.path.dirname(self.curPath2))[1],
					'productName':self.utils.getProductName(self.curPath2),
			}
        return uri
