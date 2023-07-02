import configparser
import cv2
import ntpath
import os
import pandas as pd
from pykml import parser
import rasterio
from rasterio.mask import mask
from shapely import geometry
import shutil


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
            'output_all': 'output/all',
            'output_laplacian': 'output/laplacian',
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
    borderWidth = 1
    width = img.shape[0] - 1 - borderWidth
    height = img.shape[1] - 1- borderWidth
    deadPixels = 0
    if (sum(img[borderWidth,borderWidth]) == 0):
        deadPixels = deadPixels + 1
    if (sum(img[width, borderWidth]) == 0):
        deadPixels = deadPixels + 1
    if (sum(img[borderWidth, height]) == 0):
        deadPixels = deadPixels + 1        
    if (sum(img[width, height]) == 0):
        deadPixels = deadPixels + 1        
    return (deadPixels >= 2)


def splitCoordinates(coordinates):
    try:
        longitude, latitude = coordinates.split(',')
    except:
        longitude, latitude, z = coordinates.split(',')    
    return float(longitude), float(latitude)


def generateTilesForEachGeoTiff(config):
    inputGeotiff = config['DIRECTORY']['input_geotiff']
    inputKml = config['DIRECTORY']['input_kml']
    output_all = config['DIRECTORY']['output_all']
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
                            outputFilepath = os.path.join(output_all, outputFilename)

                            try:
                                saveCroppedGeoTIFF(img, box, outputFilepath)
                                print(coordinates + ' extracted ' + geotiffName)
                            except:
                                print(coordinates + ' not found ' + geotiffName)


def selectTilesByLaplacianVariance(config):
    output_all = config['DIRECTORY']['output_all']
    output_laplacian = config['DIRECTORY']['output_laplacian']
    inputFilepaths = getListOfFiles(output_all)

    df = pd.DataFrame(inputFilepaths, columns=['Filepath'])

    def appendColumnLatitude(row):
        filepath = row['Filepath']
        filename = os.path.splitext(ntpath.basename(filepath))[0]
        return filename[5:12]
    df['Latitude'] = df.apply(appendColumnLatitude, axis=1)
    
    def appendColumnLongitude(row):
        filepath = row['Filepath']
        filename = os.path.splitext(ntpath.basename(filepath))[0]
        return filename[14:21]
    df['Longitude'] = df.apply(appendColumnLongitude, axis=1)
    
    def appendColumnMission(row):
        filepath = row['Filepath']
        filename = os.path.splitext(ntpath.basename(filepath))[0]
        return filename[24:len(filename)-1]
    df['Mission'] = df.apply(appendColumnMission, axis=1)

    def appendLaplacianVariance(row):
        filepath = row['Filepath']
        img = cv2.imread(filepath)
        return cv2.Laplacian(img, cv2.CV_64F).var()
    df['Laplacian'] = df.apply(appendLaplacianVariance, axis=1)

    df_tiles = df.groupby(by=['Latitude', 'Longitude']).aggregate({'Mission': 'count'}).reset_index()    
    for index, row in df_tiles.iterrows():
        # Select all tiles for certain coordinate
        tile_rows = df[(df['Latitude'] == row['Latitude']) & (df['Longitude'] == row['Longitude'])]

        # Copy tile with max laplacian variance
        max_laplacian = max(tile_rows['Laplacian'])
        max_laplacian_rows = tile_rows[(tile_rows['Laplacian'] == max_laplacian)]

        filepath = max_laplacian_rows['Filepath'].iloc[0]
        latitude = max_laplacian_rows['Latitude'].iloc[0]
        longitude = max_laplacian_rows['Longitude'].iloc[0]

        fileName = 'Map ['+ latitude + ', ' + longitude + '].tif'
        outputFilepath = os.path.join(output_laplacian, fileName)
        shutil.copyfile(filepath, outputFilepath)
        print(outputFilepath)


def main():
    config = loadConfigFile()    
    generateTilesForEachGeoTiff(config)
    selectTilesByLaplacianVariance(config)


if __name__ == '__main__':  
    main()

