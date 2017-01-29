import os
import arcpy
import glob
import fnmatch

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
                  'rasterTypeName': 'Kazakhstan',
                  'builderName': 'KazakhstanBuilder',
                  'description': 'Class that reads metadata from Kazakhstan metadata files',
                  'supportsOrthorectification': True,
                  'supportsSeamline': False,
                  'supportsStereo': False,
                  'enableClipToFootprint': True,
                  'isRasterProduct': True,
                  'dataSourceType': enumDataSourceType.dataSourceTypeFile | enumDataSourceType.dataSourceTypeFolder,
                  'dataSourceFilter':'*.dim',
                  'crawlerName':'KazakhstanCrawler',
                  'supportedProductTypes': 'Level1:L1C;L1B',
                  'productDefinitionName' : 'Kazakhstan_4BANDS',
                  'processingTemplates' :  [
                                      {
                                        'name': 'Multispectral',
                                        'enabled': True,
                                        'outputDatasetTag':'MS',
                                        'primaryInputDatasetTag':'MS',
                                        'isProductTemplate': True,
                                        'functionTemplate': 'stretch_ms.rft.xml'
                                      },
                                      {
                                        'name': 'Panchromatic',
                                        'enabled': True,
                                        'outputDatasetTag':'Pan',
                                        'primaryInputDatasetTag':'Pan',
                                        'isProductTemplate': True,
                                        'functionTemplate': 'stretch_pan.rft.xml'
                                      },
                                    ],
                  'bandProperties': [
                                      {
                                        'bandName' : 'Blue',
                                        'bandIndex': 3,
                                        'wavelengthMin':448.0,
                                        'wavelengthMax':517.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Green',
                                        'bandIndex': 2,
                                        'wavelengthMin':527.0,
                                        'wavelengthMax':606.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Red',
                                        'bandIndex': 1,
                                        'wavelengthMin':630.0,
                                        'wavelengthMax':691.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'NearInfrared',
                                        'bandIndex': 0,
                                        'wavelengthMin':776.0,
                                        'wavelengthMax':898.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Panchromatic',
                                        'bandIndex': 0,
                                        'wavelengthMin':520.0,
                                        'wavelengthMax':898.0,
                                        'datasetTag':'Pan'
                                      }
                                    ],
                  'fields': [productType_auxField]
                }
        ]



class Utilties():

    def IsKazakhstan(self, path):
        isKazakhstan = False
        f = open(path)
        s = f.read()
        if '<MISSION>DZZ-HR' in s:
            isKazakhstan = True

        tags = list()
        if isKazakhstan:
            tree = ET.parse(path)

            numBands = 0
            for nBands in tree.findall('Raster_Dimensions/NBANDS'):
                if nBands is not None:
                    numBands = int(nBands.text)

            if numBands == 1:
                tags.append('Pan')

            if numBands >= 3:
                tags.append('MS')

        f.close()

        retVal = {'isKazakhstan' : iskazakhstan,
                  'tags' : tags,
                  'path' : path
                  }
        return retVal

    def getTags(self, path):
        #get tags by parsing the dim file
        self.tags = list()
        tree = ET.parse(path)
        numBands = 0
        for nBands in tree.findall('Raster_Dimensions/NBANDS'):
            if nBands is not None:
                numBands = int(nBands.text)
                if numBands == 1:
                    self.tags.append('Pan')
                if numBands >= 3:
                    self.tags.append('MS')
        return self.tags

    def getProductName(self, path):
        #get product type
        tree = ET.parse(path)
        for self.productName in tree.findall('Production/PRODUCT_TYPE'):
          return self.productName.text


#############################################################################################
#############################################################################################
###
###     Kazakhstan builder class
###
#############################################################################################
#############################################################################################
class KazakhstanBuilder():

    def __init__(self, **kwargs):
        self.SensorName = 'Kazakhstan'
        self.utilities = Utilties()

    def canBuild(self, datasetPath):

        isKazakhstan = self.utilities.isKazakhstan(datasetPath)

        canBuild = isKazakhstan['isKazakhstan']

        #open the datasetPath and check if it contains the string Kazakhstan
        return canBuild

    def build(self, itemURI):
        #open the file that is part of the itemURI dictionary
        path = itemURI['path']
        dirName = os.path.dirname(path)
        tags = itemURI['tag']

        #the metadata file is a XML file
        tree = ET.parse(path)

        numBands = 0
        for nBands in tree.findall('Raster_Dimensions/NBANDS'):
            if nBands is not None:
                numBands = int(nBands.text)

        buildMS = False
        if 'MS' in tags:
            if numBands >= 3:
                buildMS = True

        buildPan = False
        if 'Pan' in tags:
            if numBands == 1:
                buildPan = True

        #rpcPath = dirName + os.sep + "RPC.xml"
        #rpcTree = ET.parse(rpcPath)

        # Horizontal CS
        srsWKT = 0
        for cs in tree.findall('Coordinate_Reference_System/Horizontal_CS'):
            csCode = cs.find('HORIZONTAL_CS_CODE').text
            espg, espgCode = csCode.split(':')
            espgCode = int(espgCode)

        # Dataset path
        fileName = None
        for c in tree.findall('Data_Access/Data_File_List/DATA_FILE_PATH'):
            fileName = c.text

        if fileName is None:
            print ("path not found")
            return None

        fullPath = os.path.join(os.path.dirname(path), fileName)

        # dataset frame - footprint; this is a list of Vertex coordinates
        coords_list = list()
        vertex_array = arcpy.Array()
        for all_vertex in tree.findall('Dataset_Frame'):
            checkVertex = all_vertex.find('VERTEX')
            if checkVertex is not None:
                for vertex in checkVertex:
                    coord = list()
                    frame_x = float(vertex.find('FRAME_X').text)
                    frame_y = float(vertex.find('FRAME_Y').text)
                    coord.append(frame_x)
                    coord.append(frame_y)
                    coords_list.append(coord)
                    vertex_array.add(arcpy.Point(frame_x, frame_y))

        #get geometry object for the footprint
        footprint_geometry = arcpy.Polygon(vertex_array)

        metadata = {}

        acquisitionDate = None
        acquisitionTime = None

        # Sun elevation, azimuth etc
        for img_metadata in tree.findall('Dataset_Sources/Source_Information/Scene_Source'):

            sunElevation = img_metadata.find('SUN_ELEVATION')
            if sunElevation is not None:
                metadata['sunElevation'] = float(img_metadata.find('SUN_ELEVATION').text)

            sunAzimuth = img_metadata.find('SUN_AZIMUTH')
            if sunAzimuth is not None:
                metadata['sunAzimuth'] = float(img_metadata.find('SUN_AZIMUTH').text)

            acquisitionDate = img_metadata.find('IMAGING_DATE')
            if acquisitionDate is not None:
                metadata['acquisitionDate'] = img_metadata.find('IMAGING_DATE').text

            acquisitionTime = img_metadata.find('IMAGING_TIME')
            if acquisitionTime is not None:
                metadata['acquisitionTime'] = img_metadata.find('IMAGING_TIME').text

            viewingAngleAlongTrack = img_metadata.find('VIEWING_ANGLE_ALONG_TRACK')
            if viewingAngle is not None:
                metadata['viewingAngleAlongTrack'] = float(img_metadata.find('VIEWING_ANGLE_ALONG_TRACK').text)

            viewingAngleAcrossTrack = img_metadata.find('VIEWING_ANGLE_ACROSS_TRACK')
            if viewingAngleAcrossTrack is not None:
                metadata['viewingAngleAcrossTrack'] = float(img_metadata.find('VIEWING_ANGLE_ACROSS_TRACK').text)

            theoreticalResolution = img_metadata.find('THEORETICAL_RESOLUTION')
            if theoreticalResolution is not None:
                metadata['theoreticalResolution'] = float(img_metadata.find('THEORETICAL_RESOLUTION').text)

            Instrument = img_metadata.find('INSTRUMENT')
            if Instrument is not None:
                metadata['Instrument'] = img_metadata.find('INSTRUMENT').text

        metadata['SensorName'] = self.SensorName
        #metadata['bandProperties'] = bandProperties
        metadata['ProductType'] = self.utilities.getProductName(path)

        tagName = None
        if numBands == 1:
            tagName = 'Pan'
        else:
            tagName = "MS"

        # Assemble everything into a dictionary
        builtItem = {}
        builtItem['spatialReference'] = espgCode
        builtItem['raster'] = { 'Raster1' : fullPath }
        builtItem['footprint'] = footprint_geometry
        builtItem['keyProperties'] = metadata
        builtItem['itemURI'] = { 'tag' : tagName }

        builtItemsList = list()
        builtItemsList.append(builtItem)
        return builtItemsList

#############################################################################################
#############################################################################################
###
###     Kazakhstan Crawlerclass
###
#############################################################################################
#############################################################################################
class KazakhstanCrawler():

    def __init__(self, **crawlerProperties):

        self.utils = Utilties()
        global mygenerator

        #function to get the *.dim files as we go
        def createGenerator(pathList, recurse, filter):
            for i in pathList:
                if os.path.isdir(i):
                    if recurse:
                        for root, dirs, files in (os.walk(i)):
                            for file in (files):
                                if file.endswith(".DIM" or ".dim"):
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
            self.filter = '*.dim'
        try:
            mygenerator = createGenerator(self.paths, self.recurse, self.filter)
            self.curPath2 = next(mygenerator)

        except StopIteration:
            return None

        self.currentTagIndex = 0

        #get the list of tags from the *.dim file using XML parsing
        self.tags = self.utils.getTags(self.curPath2)
        self.tagsIterator = iter(self.tags)

    def __iter__(self):
        return self

    def next(self):
        try:
            curTag = self.tagsIterator.next()
        except StopIteration:
            try:
                self.curPath2 = next(mygenerator)
                self.tags = self.utils.getTags(self.curPath2)
                self.tagsIterator = iter(self.tags)
                curTag = self.tagsIterator.next()
            except StopIteration:
                return None

        if self.tags is not None:
            if self.currentTagIndex < len(self.tags):
                uri = {
												'path': self.curPath2,
												'displayName': os.path.basename(self.curPath2),
												'tag': curTag,
												'groupName': os.path.split(os.path.dirname(self.curPath2))[1],
												'productName':self.utils.getProductName(self.curPath2),
											}
            self.currentTagIndex = self.currentTagIndex + 1
            if self.currentTagIndex == len(self.tags):
                    self.currentTagIndex = 0
        #return URI dictionary to Builder
        return uri
