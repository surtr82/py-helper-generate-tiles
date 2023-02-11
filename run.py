import configparser
import cv2
import ntpath
import os
from pykml import parser
import rasterio
from rasterio.mask import mask
from shapely import geometry


def loadConfigFile(filepath='config.ini'):
    createConfigFile(filepath)
    config = configparser.ConfigParser()
    config.read(filepath)
    return(config)


def createConfigFile(filepath):
    if (not os.path.isfile(filepath)):
        config = configparser.ConfigParser()
        config['DIRECTORY'] = {
            'input_geotiff': 'input/geotiff',
            'input_kml': 'input/kml',
            'output': 'output',
            'outputSuffix': 'Map'}
        config['TILE'] = {
            'extend_latitude': '0.00435',
            'extend_longitude': '0.0055'}
        with open(filepath, 'w') as configfile:
            config.write(configfile)


def getListOfFiles(directory):
    listOfFiles = os.listdir(directory)
    allFiles = list()
    for entry in listOfFiles:
        fullPath = os.path.join(directory, entry)
        if os.path.isdir(fullPath):
            allFiles = allFiles + getListOfFiles(fullPath)
        else:
            allFiles.append(fullPath)
    return allFiles


def saveImageAsGeoTIFF(img, transform, metadata, crs, outputFilepath):
    metadata.update({'driver': 'GTiff',
                     'height': img.shape[1],
                     'width': img.shape[2],
                     'transform': transform,
                     'crs': crs})
    with rasterio.open(outputFilepath, 'w', **metadata) as dest:
        dest.write(img)
    removeDeadImage(outputFilepath)


def saveCroppedGeoTIFF(img, box, fileName):
    crop, cropTransform = mask(img, [box], crop=True)
    saveImageAsGeoTIFF(crop,
                       cropTransform,
                       img.meta,
                       img.crs,
                       fileName)


def removeDeadImage(filePath):
    if (isDeadImage(filePath)):
        os.remove(filePath)


def isDeadImage(filePath):
    img = cv2.imread(filePath)
    width = img.shape[0] - 1
    height = img.shape[1] - 1
    pixelsum = sum(img[0,0]) + sum(img[width, 0])  + sum(img[0, height]) + sum(img[width, height])
    return (pixelsum == 0)


def splitCoordinates(coordinates):
    try:
        longitude, latitude = coordinates.split(',')
    except:
        longitude, latitude, z = coordinates.split(',')    
    return float(longitude), float(latitude)


def main():
    config = loadConfigFile()    
    inputGeotiff = config['DIRECTORY']['input_geotiff']
    inputKml = config['DIRECTORY']['input_kml']
    output = config['DIRECTORY']['output']
    outputSuffix = config['DIRECTORY']['outputSuffix']
    extendLatitude = float(config['TILE']['extend_latitude'])
    extendLongitude = float(config['TILE']['extend_longitude'])

    geotiffsFilepaths = getListOfFiles(inputGeotiff)
    for geotiffsFilepath in geotiffsFilepaths:
        if geotiffsFilepath.endswith('.tif'):
            geotiffName = '[' + os.path.splitext(ntpath.basename(geotiffsFilepath))[0] + ']'
            img = rasterio.open(geotiffsFilepath)

            kmlFilepaths = getListOfFiles(inputKml)
            for kmlFilepath in kmlFilepaths:
                if kmlFilepath.endswith('.kml'):
   
                    with open(kmlFilepath, encoding='Latin') as kmlFile:
                        doc = parser.parse(kmlFile).getroot()

                        for placemark in doc.Document.Folder.Placemark:
                            longitude, latitude = splitCoordinates(placemark.Point.coordinates.text)
                            corner1 = (longitude - (extendLongitude / 2), latitude - (extendLatitude / 2))
                            corner2 = (longitude + (extendLongitude / 2), latitude + (extendLatitude / 2))
                            box = geometry.box(corner1[0], corner1[1], corner2[0], corner2[1])

                            coordinates = '[{:.4f}'.format(latitude) + ', ' + '{:.4f}'.format(longitude) + ']'

                            outputFilename = outputSuffix + ' ' + coordinates + ' ' + geotiffName + '.tif'
                            outputFilepath = os.path.join(output, outputFilename)

                            try:
                                saveCroppedGeoTIFF(img, box, outputFilepath)
                                print(coordinates + ' extracted ' + geotiffName)
                            except:
                                print(coordinates + ' not found ' + geotiffName)


if __name__ == '__main__':  
    main()

