import os
import arcpy
import glob

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
        instrument_auxField = arcpy.Field()
        instrument_auxField.name = 'Instrument'
        instrument_auxField.aliasName = 'Instrument'
        instrument_auxField.type = 'String'
        instrument_auxField.length = 50

        return [
                {
                  'rasterTypeName': 'DEIMOS-2',
                  'builderName': 'DeimosBuilder',
                  'description': 'Class that reads metadata from DEIMOS metadata files',
                  'supportsOrthorectification': False,
                  'enableClipToFootprint': True,
                  'isRasterProduct': True,
                  'dataSourceType': enumDataSourceType.dataSourceTypeFile | enumDataSourceType.dataSourceTypeFolder,
                  'dataSourceFilter':'*.dim',
                  'crawlerName':'Deimos2Crawler',
                  'supportedProductTypes': 'Level1:L1C;L1B',
                  'productDefinitionName' : 'DEIMOS2_4BANDS',
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
                                        'enabled': False,
                                        'outputDatasetTag':'Pan',
                                        'primaryInputDatasetTag':'Pan',
                                        'isProductTemplate': True,
                                        'functionTemplate': 'stretch_pan.rft.xml'
                                      },
                                      {
                                        'name': 'Pansharpen',
                                        'enabled': False,
                                        'outputDatasetTag':'Pansharpened',
                                        'primaryInputDatasetTag':'MS',
                                        'isProductTemplate': True,
                                        'functionTemplate': 'stretch_psh.rft.xml'
                                      },
                                      {
                                        'name': 'All Bands',
                                        'enabled': False,
                                        'isProductTemplate': False,
                                        'functionTemplate': 'stretch_allbands.rft.xml'
                                      }
                                    ],
                  'bandProperties': [
                                      {
                                        'bandName' : 'Blue',
                                        'bandIndex': 3,
                                        'wavelengthMin':466.0,
                                        'wavelengthMax':525.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Green',
                                        'bandIndex': 2,
                                        'wavelengthMin':532.0,
                                        'wavelengthMax':599.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Red',
                                        'bandIndex': 1,
                                        'wavelengthMin':640.0,
                                        'wavelengthMax':697.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'NearInfrared',
                                        'bandIndex': 0,
                                        'wavelengthMin':770.0,
                                        'wavelengthMax':892.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Panchromatic',
                                        'bandIndex': 0,
                                        'wavelengthMin':560.0,
                                        'wavelengthMax':900.0,
                                        'datasetTag':'Pan'
                                      }
                                    ],
                  'fields': [instrument_auxField]
                }
        ]



class Utilties():

    def isDeimos2(self, path):
        # Check if file is DEIMOS-2 metadata file and get tags if so.
        isDeimos2 = False
        f = open(path)
        s = f.read()
        if '<MISSION>Deimos 2' in s:
            isDeimos2 = True

        if isDeimos2:
            tags = getTags(path)
        f.close()

        retVal = {'isDeimos2' : isDeimos2,
                  'tags' : tags,
                  'path' : path
                  }
        return retVal

    def getTags(self, path):
        # Get tags by parsing the dim file
        tags = list()
        tree = ET.parse(path)
        numBands = 0
        for nBands in tree.findall('Raster_Dimensions/NBANDS'):
            if nBands is not None:
                numBands = int(nBands.text)
                if numBands == 1:
                    tags.append('Pan')
                if numBands >= 3:
                    tags.append('MS')
        return tags

    def getProductName(self, path):
        # Get product type
        tree = ET.parse(path)
        for productName in tree.findall('Production/PRODUCT_TYPE'):
          return productName.text


#############################################################################################
#############################################################################################
###
###     DEIMOS builder class
###
#############################################################################################
#############################################################################################
class DeimosBuilder():

    def __init__(self, **kwargs):
        self.SensorName = 'DEIMOS-2'
        self.utilities = Utilties()

    def canBuild(self, datasetPath):
         # Open the datasetPath and check if the metadata file contains the string Deimos
        isDeimos = self.utilities.isDeimos2(datasetPath)
        canBuild = isDeimos['isDeimos2']

        return canBuild

    def build(self, itemURI):
        # ItemURI dictionary passed from crawler containing path, tag, display name, group name, product type
        path = itemURI['path']
        tag = itemURI['tag']

        # The metadata file is a XML file
        tree = ET.parse(path)

        buildMS = False
        if 'MS' in tag:
            tagName = 'MS'
            buildMS = True

        buildPan = False
        if 'Pan' in tag:
            tagName = 'Pan'
            buildPan = True

        # Horizontal CS (can also be a arcpy.SpatialReference object, ESPG code or path to a PRJ file)
        srsWKT = 0
        for c in tree.findall('Coordinate_Reference_System/PROJECTION'):
            srsWKT = c.text

        # Dataset path
        fileName = None
        for c in tree.findall('Data_Access/Data_File/DATA_FILE_PATH'):
            fileName = c.attrib['href']
        if fileName is None:
            print ("path not found")
            return None
        fullPath = os.path.join(os.path.dirname(path), fileName)

        # Dataset frame - footprint; this is a list of Vertex coordinates
        vertex_array = arcpy.Array()
        for all_vertex in tree.findall('Dataset_Frame'):
            for vertex in all_vertex:
                frame_x = float(vertex.find('FRAME_X').text)
                frame_y = float(vertex.find('FRAME_Y').text)
                vertex_array.add(arcpy.Point(frame_x, frame_y))
        # Get geometry object for the footprint
        footprint_geometry = arcpy.Polygon(vertex_array)

        # Metadata Information
        bandProperties = list()
        # Band info(part of metadata) - gain, bias etc
        for img_interpretation in tree.findall('Image_Interpretation'):
            for band_info in img_interpretation:
                bandProperty = {}
                if band_info.find('BAND_DESCRIPTION').text == 'NIR':
                    bandProperty['bandName'] = 'NearInfrared'
                elif band_info.find('BAND_DESCRIPTION').text == 'PAN':
                    bandProperty['bandName'] = 'Panchromatic'
                else:
                    bandProperty['bandName'] = band_info.find('BAND_DESCRIPTION').text
                band_num = int(band_info.find('BAND_INDEX').text)
                bandProperty['RadianceGain'] = float(band_info.find('PHYSICAL_GAIN').text)
                bandProperty['RadianceBias'] = float(band_info.find('PHYSICAL_BIAS').text)
                bandProperty['unit'] = band_info.find('PHYSICAL_UNIT').text
                bandProperties.append(bandProperty)

        # Other metadata information (Sun elevation, azimuth etc)
        metadata = {}
        acquisitionDate = None
        acquisitionTime = None
        for img_metadata in tree.findall('Dataset_Sources/Source_Information/Scene_Source'):
            sunElevation = img_metadata.find('SUN_ELEVATION')
            if sunElevation is not None:
                metadata['sunElevation'] = float(img_metadata.find('SUN_ELEVATION').text)
            acquisitionDate = img_metadata.find('IMAGING_DATE')
            if acquisitionDate is not None:
                metadata['acquisitionDate'] = img_metadata.find('IMAGING_DATE').text
            viewingAngle = img_metadata.find('SENSOR_VIEWING')
            if viewingAngle is not None:
                metadata['viewingAngle'] = float(img_metadata.find('SENSOR_VIEWING').text)
            Instrument = img_metadata.find('INSTRUMENT')
            if Instrument is not None:
                metadata['Instrument'] = img_metadata.find('INSTRUMENT').text
        metadata['SensorName'] = self.SensorName
        metadata['bandProperties'] = bandProperties
        metadata['ProductType'] = self.utilities.getProductName(path)

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
###     DEIMOS Crawlerclass
###
#############################################################################################
#############################################################################################
class Deimos2Crawler():

    def __init__(self, **crawlerProperties):

        self.utils = Utilties()

        # Generator to get the *.dim files as we go
        def createGenerator(pathList, recurse, filter):
            for path in pathList:
                if os.path.isdir(path):
                    if recurse:
                        for root, dirs, files in (os.walk(path)):
                            for file in (files):
                                if file.endswith(".dim"):
                                    filename = os.path.join(root, file)
                                    yield filename
                    else:
                        filter_to_scan = path + os.path.sep + filter
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
            self.pathGenerator = createGenerator(self.paths, self.recurse, self.filter)
            self.curPath = next(self.pathGenerator)

        except StopIteration:
            return None

        # Get the list of tags from the *.dim file using XML parsing
        self.tags = self.utils.getTags(self.curPath)
        self.tagsIterator = iter(self.tags)

    def __iter__(self):
        return self

    def next(self):
        try:
            curTag = self.tagsIterator.next()
        except StopIteration:
            try:
                self.curPath = next(self.pathGenerator)
                self.tags = self.utils.getTags(self.curPath)
                self.tagsIterator = iter(self.tags)
                curTag = self.tagsIterator.next()
            except StopIteration:
                return None

        uri = {
			    'path': self.curPath,
				'displayName': os.path.basename(self.curPath),
				'tag': curTag,
				'groupName': os.path.split(os.path.dirname(self.curPath))[1],
				'productName':self.utils.getProductName(self.curPath),
		}
        # Return URI dictionary to Builder
        return uri
