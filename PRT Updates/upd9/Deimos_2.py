import os
import arcpy
import glob
import csv

try:
  import xml.etree.cElementTree as ET
except ImportError:
  import xml.etree.ElementTree as ET


class enumDataSourceType():
  dataSourceTypeUnknown = 0
  dataSourceTypeFile = 1
  dataSourceTypeFolder = 2

class RasterTypeFactory():
  
  def __init__(self):
    self.debugMode = False

  def getRasterTypesInfo(self):
    self.instrument_auxField = arcpy.Field()
    self.instrument_auxField.name = 'Instrument'
    self.instrument_auxField.aliasName = 'Instrument'
    self.instrument_auxField.type = 'String'
    self.instrument_auxField.length = 50

    return [
            {
              'rasterTypeName': 'DEIMOS-2',
              'builderName': 'DeimosBuilder',
              'description': 'Supports reading of DEIMOS-2 Level 1B and Level 1C product metadata files',
              'supportsOrthorectification': False,
              'enableClipToFootprint': True,
              'isRasterProduct': True,
              'dataSourceType': enumDataSourceType.dataSourceTypeFile | enumDataSourceType.dataSourceTypeFolder,
              'dataSourceFilter':'*.dim',
              'crawlerName':'Deimos2Crawler',
              'supportedURIFilters': [
                                      {
                                        'name': 'Level1',
                                        'allowedProducts': ['L1C', 'L1B'],
                                        'supportsOrthorectification': False,
                                        'supportedTemplates': ['Multispectral', 'Panchromatic', 'Pansharpen', 'All Bands']
                                      }
                                     ],
              'productDefinitionName' : 'DEIMOS2_4BANDS',
              'processingTemplates' : [
                                        {
                                          'name': 'Multispectral',
                                          'enabled': True,
                                          'outputDatasetTag':'MS',
                                          'primaryInputDatasetTag':'MS',
                                          'isProductTemplate': True,
                                          'functionTemplate': 'D2_stretch_ms.rft.xml'
                                        },
                                        {
                                          'name': 'Panchromatic',
                                          'enabled': False,
                                          'outputDatasetTag':'Pan',
                                          'primaryInputDatasetTag':'Pan',
                                          'isProductTemplate': True,
                                          'functionTemplate': 'D2_stretch_pan.rft.xml'
                                        },
                                        {
                                          'name': 'Pansharpen',
                                          'enabled': False,
                                          'outputDatasetTag':'Pansharpened',
                                          'primaryInputDatasetTag':'MS',
                                          'isProductTemplate': True,
                                          'functionTemplate': 'D2_stretch_psh.rft.xml'
                                        },
                                        {
                                          'name': 'All Bands',
                                          'enabled': False,
                                          'isProductTemplate': False,
                                          'functionTemplate': 'D2_stretch_allbands.rft.xml'
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
              'fields': [self.instrument_auxField]
            }
           ]


#############################################################################################
#############################################################################################
###
###     Utility functions used by the Builder and Crawler classes
###
#############################################################################################
#############################################################################################
class Utilities():

  def isDeimos2(self, path):
    isD2 = False
    f = open(path)
    s = f.read()
    if '<MISSION>Deimos 2' in s:
      isD2 = True
    f.close()
    return isD2

  def __getTagsFromTree(self, tree):
    tags = list()
    numBands = 0
    for nBands in tree.findall('Raster_Dimensions/NBANDS'):
      if nBands is not None:
        numBands = int(nBands.text)
        if numBands == 1:
          tags.append('Pan')
        if numBands >= 3:
          tags.append('MS')
    return tags

  def getTags(self, path):
    try:
      # Get tags by parsing the dim file
      tree = ET.parse(path)
      tags = self.__getTagsFromTree(tree)
      return tags
    except ParseError as e:
      print ("Parse error {0}:".format(e.code))
      return None
      
  def getProductName(self, tree):
    productName = tree.find('Production/PRODUCT_TYPE')
    if productName is not None:
      return productName.text
    return None

  def getProductNameFromFile(self, path):
    try:
      # Get product type
      tree = ET.parse(path)
      productName = self.getProductName(tree)
      return productName
    except ParseError as e:
      print ("Exception while parsing {0}\n{1}".format(path, e.code))
    return None

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
    self.utilities = Utilities()

  #######################################
  ### The 'canBuild' function
  #######################################
  def canBuild(self, datasetPath):
    # Open the datasetPath and check if the metadata file contains the string Deimos
    canBuild = self.utilities.isDeimos2(datasetPath)
    return canBuild

  #######################################
  ### The 'build' function
  #######################################
  def build(self, itemURI):

    # Make sure that the itemURI dictionary contains items
    if len(itemURI) <= 0:
      return None

    try:

      # ItemURI dictionary passed from crawler containing path, tag, display name, group name, product type
      path = None
      if 'path' in itemURI:
        path = itemURI['path']
      else:
        return None

      # The metadata file is a XML file
      tree = ET.parse(path)

      # Horizontal CS (can also be a arcpy.SpatialReference object, ESPG code, path to a PRJ file or a WKT string)
      srsWKT = 0
      projectionNode = tree.find('Coordinate_Reference_System/PROJECTION')
      if projectionNode is None:
        projectionNode = tree.find('Dataset_Sources/Source_Information/Coordinate_Reference_System/Projection_OGCWKT')

      if projectionNode is not None:
        srsWKT = projectionNode.text

      # Dataset path
      fileName = None
      filePathNode = tree.find('Data_Access/Data_File/DATA_FILE_PATH')
      if filePathNode is not None:
        fileName = filePathNode.attrib['href']

      if fileName is None:
        print ("path not found")
        return None

      fullPath = os.path.join(os.path.dirname(path), fileName)

      # Dataset frame - footprint; this is a list of Vertex coordinates
      vertex_array = arcpy.Array()
      all_vertex = tree.find('Dataset_Frame')
      if all_vertex is not None:
        for vertex in all_vertex:
          x_vertex = vertex.find('FRAME_X')
          y_vertex = vertex.find('FRAME_Y')
          if x_vertex is not None and y_vertex is not None:
            frame_x = float(x_vertex.text)
            frame_y = float(y_vertex.text)
            vertex_array.add(arcpy.Point(frame_x, frame_y))

      # Get geometry object for the footprint; the SRS of the footprint
      # can also be passed if it is different to the SRS read from the metadata;
      # by default, the footprint geometry is assumed to be in the SRS of the metadata 
      footprint_geometry = arcpy.Polygon(vertex_array)

      # Metadata Information
      bandProperties = list()

      # Band info(part of metadata) - gain, bias etc
      img_interpretation = tree.find('Image_Interpretation')
      if img_interpretation is not None:
        for band_info in img_interpretation:
          bandProperty = {}
          if band_info.find('BAND_DESCRIPTION').text == 'NIR':
            bandProperty['bandName'] = 'NearInfrared'
          elif band_info.find('BAND_DESCRIPTION').text == 'PAN':
            bandProperty['bandName'] = 'Panchromatic'
          else:
            bandProperty['bandName'] = band_info.find('BAND_DESCRIPTION').text

          band_num = 0 
          band_index = band_info.find('BAND_INDEX')
          if band_index is not None:
            band_num = int(band_index.text)

          gain = band_info.find('PHYSICAL_GAIN')
          if gain is not None:
            bandProperty['RadianceGain'] = float(gain.text)

          bias = band_info.find('PHYSICAL_BIAS')
          if bias is not None:
            bandProperty['RadianceBias'] = float(bias.text)

          unit = band_info.find('PHYSICAL_UNIT')
          if unit is not None:
            bandProperty['unit'] = unit.text

          bandProperties.append(bandProperty)

      # Other metadata information (Sun elevation, azimuth etc)
      metadata = {}
      acquisitionDate = None
      acquisitionTime = None
      img_metadata = tree.find('Dataset_Sources/Source_Information/Scene_Source')
      if img_metadata is not None:
        # Get the Sun Elevation
        sunElevation = img_metadata.find('SUN_ELEVATION')
        if sunElevation is not None:
          metadata['SunElevation'] = float(sunElevation.text)
      
        # Get the acquisition date of the scene
        acquisitionDate = img_metadata.find('IMAGING_DATE')
        if acquisitionDate is not None:
          metadata['AcquisitionDate'] = acquisitionDate.text
      
        # retrieve the view angle; this is the angle off Nadir view
        viewingAngle = img_metadata.find('SENSOR_VIEWING')
        if viewingAngle is None:
          viewingAngle = img_metadata.find('VIEWING_ANGLE')

        if viewingAngle is not None:
          metadata['OffNadir'] = float(viewingAngle.text)
      
        instrument = img_metadata.find('INSTRUMENT')
        if instrument is not None:
          metadata['Instrument'] = instrument.text
            
        # Get the Sun Azimuth
        sunAzimuth = img_metadata.find('SUN_AZIMUTH')
        if sunAzimuth is not None:
          metadata['SunAzimuth'] = float(sunElevation.text)

        # Get the Sun Distance
        sunDistance = img_metadata.find('EARTH_SUN_DISTANCE')
        if sunDistance is not None:
          metadata['SunDistance'] = float(sunDistance.text)

      metadata['SensorName'] = self.SensorName
      metadata['bandProperties'] = bandProperties
      metadata['ProductType'] = self.utilities.getProductName(tree)

      #define a dictionary of variables
      variables = {}
      variables['DefaultMaximumInput'] = 1023
      variables['DefaultGamma'] = 1

      # Assemble everything into an outgoing dictionary
      builtItem = {}
      builtItem['spatialReference'] = srsWKT
      builtItem['raster'] = { 'Raster1' : fullPath }
      builtItem['footprint'] = footprint_geometry
      builtItem['keyProperties'] = metadata
      builtItem['variables'] = variables
      builtItem['itemURI'] = itemURI

      builtItemsList = list()
      builtItemsList.append(builtItem)
      return builtItemsList
    
    except:
      return None

#############################################################################################
#############################################################################################
###
###     DEIMOS Crawlerclass
###
#############################################################################################
#############################################################################################
class Deimos2Crawler():

  def __init__(self, **crawlerProperties):
    self.utils = Utilities()
    self.paths = crawlerProperties['paths']
    self.recurse = crawlerProperties['recurse']
    self.filter = crawlerProperties['filter']
    if self.filter is (None or ""):
      self.filter = '*.dim'

    try:
      self.pathGenerator = self.createGenerator()
      self.curPath = next(self.pathGenerator)

    except StopIteration:
      return None

    # Get the list of tags from the *.dim file using XML parsing
    self.tags = self.utils.getTags(self.curPath)
    self.tagsIterator = iter(self.tags)

  def createGenerator(self):
    for path in self.paths:
        if os.path.isdir(path):
            if self.recurse:
                for root, dirs, files in (os.walk(path)):
                    for file in (files):
                        if file.endswith(".dim"):
                            filename = os.path.join(root, file)
                            yield filename
            else:
                filter_to_scan = path + os.path.sep + self.filter
                for filename in glob.glob(filter_to_scan):
                    yield filename

        elif path.endswith(".csv"):
            with open(path, 'rb') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    yield row['raster']

        else:
            yield path

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
            'productName':self.utils.getProductNameFromFile(self.curPath)
          }

    # Return URI dictionary to Builder
    return uri
