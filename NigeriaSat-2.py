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
                  'rasterTypeName': 'NigeriaSat-2',
                  'builderName': 'NigeriaSat2Builder',
                  'description': 'Class that reads metadata from NigeriaSat metadata files',
                  'supportsOrthorectification': True,
                  'supportsSeamline': False,
                  'supportsStereo': False,
                  'enableClipToFootprint': True,
                  'isRasterProduct': True,
                  'dataSourceType': enumDataSourceType.dataSourceTypeFile | enumDataSourceType.dataSourceTypeFolder,
                  'dataSourceFilter':'*.dim',
                  'crawlerName':'NigeriaSat2Crawler',
                  'supportedProductTypes': 'Level1:L1C;L1B',
                  'productDefinitionName' : 'NigeriaSat2_4BANDS',
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

    def IsNigeriaSat2(self, path):
        isNigeriaSat2 = False
        f = open(path)
        s = f.read()
        if '<MISSION>NIGERIASAT' in s:
            isNigeriaSat2 = True

        tags = list()
        if isNigeriaSat2:
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

        retVal = {'isNigeriaSat2' : isNigeriaSat2,
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
###     NigeriaSat builder class
###
#############################################################################################
#############################################################################################
class NigeriaSat2Builder():

    def __init__(self, **kwargs):
        self.SensorName = 'NigeriaSat2'
        self.utilities = Utilties()

    def canBuild(self, datasetPath):

        isNigeriaSat2 = self.utilities.isNigeriaSat2(datasetPath)

        canBuild = isNigeriaSat2['isNigeriaSat2']

        #open the datasetPath and check if it contains the string NIGERIASAT
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
        for c in tree.findall('Coordinate_Reference_System/PROJECTION'):
            #print c.text
            srsWKT = c.text

        # Dataset path
        fileName = None
        for c in tree.findall('Data_Access/Data_File/DATA_FILE_PATH'):
            fileName = c.attrib['href']

        if fileName is None:
            print ("path not found")
            return None

        fullPath = os.path.join(os.path.dirname(path), fileName)

        # dataset frame - footprint; this is a list of Vertex coordinates
        coords_list = list()
        vertex_array = arcpy.Array()
        for all_vertex in tree.findall('Dataset_Frame'):
            for vertex in all_vertex:
                coord = list()
                frame_x = float(vertex.find('FRAME_X').text)
                frame_y = float(vertex.find('FRAME_Y').text)
                coord.append(frame_x)
                coord.append(frame_y)
                coords_list.append(coord)
                vertex_array.add(arcpy.Point(frame_x, frame_y))

        #get geometry object for the footprint
        footprint_geometry = arcpy.Polygon(vertex_array)

        bandProperties = list()

        # Band info - gain, bias etc
        for img_interpretation in tree.findall('Image_Interpretation'):
            for band_info in img_interpretation:
                bandProperty = {}
                if band_info.find('BAND_DESCRIPTION').text == 'NIR':
                    bandProperty['bandName'] = 'NearInfrared'
                else:
                    bandProperty['bandName'] = band_info.find('BAND_DESCRIPTION').text

                band_num = int(band_info.find('BAND_INDEX').text)
                bandProperty['RadianceGain'] = float(band_info.find('PHYSICAL_GAIN').text)
                bandProperty['RadianceBias'] = float(band_info.find('PHYSICAL_BIAS').text)
                bandProperty['unit'] = band_info.find('PHYSICAL_UNIT').text
                bandProperties.append(bandProperty)

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

            viewingAngle = img_metadata.find('VIEWING_ANGLE')
            if viewingAngle is not None:
                metadata['viewingAngle'] = float(img_metadata.find('VIEWING_ANGLE').text)

            incidenceAngle = img_metadata.find('INCIDENCE_ANGLE')
            if incidenceAngle is not None:
                metadata['incidenceAngle'] = float(img_metadata.find('INCIDENCE_ANGLE').text)

            theoreticalResolution = img_metadata.find('THEORETICAL_RESOLUTION')
            if theoreticalResolution is not None:
                metadata['theoreticalResolution'] = float(img_metadata.find('THEORETICAL_RESOLUTION').text)

            Instrument = img_metadata.find('INSTRUMENT')
            if Instrument is not None:
                metadata['Instrument'] = img_metadata.find('INSTRUMENT').text

        metadata['SensorName'] = self.SensorName
        metadata['bandProperties'] = bandProperties
        metadata['ProductType'] = self.utilities.getProductName(path)

        tagName = None
        if numBands == 1:
            tagName = 'Pan'
        else:
            tagName = "MS"

        # Assemble everything into a dictionary
        builtItem = {}
        builtItem['spatialReference'] = srsWKT
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
###     NigeriaSat Crawlerclass
###
#############################################################################################
#############################################################################################
class NigeriaSat2Crawler():

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
                                if file.endswith(".dim"):
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
