import os
import arcpy

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET


class enumDataSourceType():
    dataSourceTypeUnknown = 0
    dataSourceTypeFile = 1
    dataSourceTypeFolder = 2

class RasterTypeFactory():

    def getRasterTypesInfo(self):
        instrument_auxField = arcpy.Field()
        instrument_auxField.name = 'Instrument'
        instrument_auxField.aliasName = 'Instrument'
        instrument_auxField.length = 50
        instrument_auxField.type = 'String'

        return [
                {
                  'rasterTypeName': 'DEIMOS-1',
                  'builderName': 'DeimosBuilder',
                  'description': 'Class that reads metadata from DEIMOS metadata files',
                  'supportsOrthorectification': False,
                  'enableClipToFootprint': True,
                  'isRasterProduct': True,
                  'dataSourceType': enumDataSourceType.dataSourceTypeFile | enumDataSourceType.dataSourceTypeFolder,
                  'dataSourceFilter':'*.dim',
                  'productDefinitionName' : 'DEIMOS1_3BANDS',
                  'processingTemplates' :  [
                                      {
                                        'name': 'PseudoColor',
                                        'enabled':True,
                                        'outputDatasetTag':'MS',
                                        'primaryInputDatasetTag':'MS',
                                        'isProductTemplate':True,
                                        'functionTemplate':'PseudoColor.rft.xml'
                                      },
                                      {
                                        'name': 'Multispectral',
                                        'enabled':False,
                                        'outputDatasetTag':'MS',
                                        'primaryInputDatasetTag':'MS',
                                        'isProductTemplate':True,
                                        'functionTemplate': 'stretch_ms.rft.xml'
                                      }
                                    ],
                  'bandProperties': [
                                      {
                                        'bandName' : 'Green',
                                        'bandIndex': 0,
                                        'wavelengthMin':520.0,
                                        'wavelengthMax':600.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'Red',
                                        'bandIndex': 1,
                                        'wavelengthMin':630.0,
                                        'wavelengthMax':690.0,
                                        'datasetTag':'MS'
                                      },
                                      {
                                        'bandName' : 'NearInfrared',
                                        'bandIndex': 2,
                                        'wavelengthMin':770.0,
                                        'wavelengthMax':900.0,
                                        'datasetTag':'MS'
                                      }
                                    ],
                  'fields': [instrument_auxField]
                }
        ]


#############################################################################################
#############################################################################################
###
###     DEIMOS builder class
###
#############################################################################################
#############################################################################################
class DeimosBuilder():

    def __init__(self, **kwargs):
        self.SensorName = 'DEIMOS-1'

    def canBuild(self, datasetPath):

        canBuild = False

        #open the datasetPath and check if it contains the string Deimos
        f = open(datasetPath)
        s = f.read()
        if '<MISSION>DEIMOS' in s:
            if '<MISSION_INDEX>1' in s:
                canBuild = True

        f.close()
        return canBuild

    def build(self, itemURI):
        #open the file that is part of the itemURI dictionary
        filePath = itemURI['path']

        #the metadata file is a XML file
        tree = ET.parse(filePath)

        # Horizontal CS
        epsgCode = 0
        for c in tree.findall('Coordinate_Reference_System/Horizontal_CS/HORIZONTAL_CS_CODE'):
            print c.text
            epsgCode = long(c.text.split(':')[1])

        SRS = None
        if epsgCode > 0:
            SRS = arcpy.SpatialReference(epsgCode)

        # Dataset path
        fileName = None
        for c in tree.findall('Data_Access/Data_File/DATA_FILE_PATH'):
            fileName = c.attrib['href']

        if fileName is None:
            print "FilePath not found"
            return None

        fullPath = os.path.join(os.path.dirname(filePath), fileName)

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

        footprint_geometry = arcpy.Polygon(vertex_array, SRS)

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
            metadata['sunElevation'] = float(img_metadata.find('SUN_ELEVATION').text)
            metadata['sunAzimuth'] = float(img_metadata.find('SUN_AZIMUTH').text)
            acquisitionDate = img_metadata.find('IMAGING_DATE').text
            acquisitionTime = img_metadata.find('IMAGING_TIME').text
            metadata['viewingAngle'] = float(img_metadata.find('VIEWING_ANGLE').text)
            metadata['incidenceAngle'] = float(img_metadata.find('INCIDENCE_ANGLE').text)
            metadata['Instrument'] = img_metadata.find('INSTRUMENT').text

        # Sensor elevation, azimuth
        for quality_assessment in tree.findall('Dataset_Sources/Source_Information/Quality_Assessment'):
            for quality_param in quality_assessment:
                quality_code = quality_param.find('QUALITY_PARAMETER_CODE')
                if quality_code is not None:
                    code = quality_code.text
                    quality_value = float(quality_param.find('QUALITY_PARAMETER_VALUE').text)
                    if 'SENSOR_AZIMUTH' in code:
                        metadata['sensorAzimuth'] = quality_value
                    elif 'SENSOR_ELEVATION' in code:
                        metadata['sensorElevation'] = quality_value

        if acquisitionDate is not None:
            if acquisitionTime is not None:
                acquisitionDate = acquisitionDate + 'T' + acquisitionTime

            metadata['acquisitionDate'] = acquisitionDate

        metadata['SensorName'] = self.SensorName
        metadata['bandProperties'] = bandProperties
        for productName in tree.findall('Production/PRODUCT_TYPE'):
            if productName is not None:
                metadata['ProductType'] = productName.text

        # Assemble everything into a dictionary
        builtItem = {}
        builtItem['spatialReference'] = SRS
        builtItem['raster'] = { 'Raster1' : fullPath }
        builtItem['footprint'] = footprint_geometry
        builtItem['keyProperties'] = metadata
        builtItem['itemURI'] = { 'tag' : 'MS' }

        builtItemsList = list()
        builtItemsList.append(builtItem)
        return builtItemsList

