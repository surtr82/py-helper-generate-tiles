import configparser
import ntpath
import os
from PIL import Image
from pykml import parser
import time
import urllib.request


def loadConfigFile(filepath='config.ini'):
    createConfigFile(filepath)
    config = configparser.ConfigParser()
    config.read(filepath)
    return(config)


def createConfigFile(filepath):
    if (not os.path.isfile(filepath)):
        config = configparser.ConfigParser()
        config['DIRECTORY'] = {
            'input_kml': 'input/kml',
            'temp': 'temp',
            'output': 'output',
            'outputSuffix': 'Map'}
        config['API'] = {
            'key': '*** ENTER YOUR PERSONAL KEY ***',
            'zoom': '16'}
        config['TILE'] = {
            'width': '256',
            'height': '256',
            'logo-height': '50'}
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


def splitCoordinates(coordinates):
    try:
        longitude, latitude = coordinates.split(',')
    except:
        longitude, latitude, z = coordinates.split(',')    
    return float(longitude), float(latitude)


class urlBuilder:
    def __init__(self, key, lat, lon, zoom, width, height):
        self._key = key
        self._lat = lat
        self._lon = lon
        self._zoom = zoom
        self._width = width
        self._height = height

    def __str__(self):
        serializedObject = str(self._lat) + ", " + str(self._lon)
        return serializedObject
        

class bingMapUrlBuilder(urlBuilder):
    def __init__(self, key, lat, lon, zoom, width, height, maptype="Aerial"):
        urlBuilder.__init__(self, key, lat, lon, zoom, width, height)
        self._endpoint = "https://dev.virtualearth.net/REST/v1/Imagery/Map/"
        self._maptype = maptype

    def __str__(self):
        serializedObject = urlBuilder.__str__(self) 
        return serializedObject
    
    def getUrl(self):
        url = self._endpoint \
            + "/" + self._maptype \
            + "/" + str(self._lat) + ',' + str(self._lon) \
            + "/" + str(self._zoom) \
            + "?mapSize=" + str(self._width) + "," + str(self._height) \
            + "&key=" + self._key
        return url


class tileGenerator:
    def __init__(self, tempFilepath, outputFilepath, attemptsOnException = 5, waitBetweenAttempts = 10, silentMode = False):
        self.tempFilepath = tempFilepath
        self.outputFilepath = outputFilepath
        self._attemptsOnException = attemptsOnException
        self._waitBetweenAttempts = waitBetweenAttempts
        self._silentMode = silentMode

    def __str__(self):
        serializedObject = "Destination: " + self.outputFilepath
        return serializedObject        

    def request(self, url, tempFilepath, outputFilepath):
        if os.path.exists(tempFilepath):
            os.remove(tempFilepath)

        if os.path.exists(outputFilepath):
            os.remove(outputFilepath)

        attempts = 0
        while attempts < self._attemptsOnException:
            try:
                if not self._silentMode:
                    fileName = os.path.splitext(ntpath.basename(outputFilepath))[0]
                    print("Request " + fileName)    

                urllib.request.urlretrieve(url, tempFilepath)
                os.rename(tempFilepath, outputFilepath)
                break
            except:
                if not self._silentMode:
                    print("Error, waiting " + str(self._waitBetweenAttempts) + "s.")    

                attempts += 1
                time.sleep(self._waitBetweenAttempts)


def downloadBingMap(key, lat, lon, zoom, width, height, tempFilepath, outputFilepath):
    if not os.path.exists(outputFilepath):
        url = bingMapUrlBuilder(key, lat, lon, zoom, width, height).getUrl()
        gen = tileGenerator(tempFilepath, outputFilepath)
        gen.request(url, tempFilepath, outputFilepath)    


def cropLogo(outputFilepath, width, height, logoHeight):
    img = Image.open(outputFilepath)
    img_cropped = img.crop((1, (logoHeight/2), width, height-(logoHeight/2)))
    img_cropped.save(outputFilepath)


def main():
    config = loadConfigFile()    
    inputKml = config['DIRECTORY']['input_kml']
    temp = config['DIRECTORY']['temp']
    output = config['DIRECTORY']['output']
    outputSuffix = config['DIRECTORY']['outputSuffix']
    key = config['API']['key'] 
    zoom = int(config['API']['zoom']) 
    width = int(config['TILE']['width'])
    height = int(config['TILE']['height'])
    logoHeight = int(config['TILE']['logo-height'])
    height = height+logoHeight

    kmlFilepaths = getListOfFiles(inputKml)
    for kmlFilepath in kmlFilepaths:
        if kmlFilepath.endswith('.kml'):

            with open(kmlFilepath, encoding='Latin') as kmlFile:
                doc = parser.parse(kmlFile).getroot()

                for placemark in doc.Document.Folder.Placemark:
                    longitude, latitude = splitCoordinates(placemark.Point.coordinates.text)

                    coordinates = '[{:.4f}'.format(latitude) + ', ' + '{:.4f}'.format(longitude) + ']'

                    outputFilename = outputSuffix + ' ' + coordinates + '.png'
                    tempFilepath = os.path.join(temp, outputFilename)                    
                    outputFilepath = os.path.join(output, outputFilename)
           
                    downloadBingMap(key, latitude, longitude, zoom, width, height, tempFilepath, outputFilepath)
                    cropLogo(outputFilepath, width, height, logoHeight)


if __name__ == '__main__':  
    main()
