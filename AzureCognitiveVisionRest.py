#########################################
# AZURE COGNITIVE VISION REST FUNCTIONS #
#########################################


# ----------------------------#
# Preliminaries and Libraries #
#-----------------------------#


# Importing the required libraries into the project
import os, io, requests, json, geojson, cv2, glob, xlrd, math, http.client, pyproj
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from decimal import Decimal
import xlsxwriter as xlw
from pandas.io.json import json_normalize
from PIL import Image, ImageDraw, ImageFont
from GPSPhoto import gpsphoto
from datetime import datetime, timedelta
import time
from tqdm import tqdm
from IPython.display import display
from azure.storage.blob import BlockBlobService

# Set maximum number of http requests
http.client._MAXHEADERS = 5000




class AzCognVisionRest(object):
    """Class AzCognVisionRest:
    This class contains a number of functions, methods and processes for ML object classification analysis
    using the Azure Cognitive Services Computer Vision API.

    Global Attributes
        blobAccount: the name of the Azure blob storage account
        blobKey: the API key of the Azure blob storage account
        apiRegion: the azure region of the Azure Cognitive Services Computer Vision API (e.g., 'westus')
        apiKey: the Azure Cognitive Services Computer Vision API key (from azure)
        containerName: the base container name of the Azure blob storage account containing the photosphere images

    Example Class initialization:
        az = AzCognVisionRest(blobAccount, blobKey, apiRegion, apiKey, containerName)
    """

    def __init__(self, blobAccount, blobKey, apiRegion, apiKey, containerName):
        """Function Class Initialization
        Returns an Azure Cognitive Services Computer Vision object (REST API) using a region and key.

        Attributes
            blobAccount: the name of the Azure blob storage account
            blobKey: the API key of the Azure blob storage account
            apiRegion: the azure region of the Azure Cognitive Services Computer Vision API (e.g., 'westus')
            apiKey: the Azure Cognitive Services Computer Vision API key (from azure)
            containerName: the base container name of the Azure blob storage account containing the photosphere images

        Returns
            client: A ComputerVisionAPI object

        Notes
            This function runs on instantiation of class
        """
        # Setup account and key for the Azure blob storage containing the photosphere images
        self.blobAccount = blobAccount
        self.blobKey = blobKey
        self.blobService = BlockBlobService(self.blobAccount, self.blobKey)

        # Setup region and key for the Azure vision client API
        self.apiRegion = apiRegion
        self.subscriptionKey = apiKey
        assert self.subscriptionKey

        # Setup base url for Azure Cognitive Services Computer Vision
        self.visionBaseUrl = 'https://{}.api.cognitive.microsoft.com/vision/v2.0/'.format(self.apiRegion)

        # Setup the global headers configuration
        self.headers = {"Ocp-Apim-Subscription-Key": self.subscriptionKey, "Content-Type": "application/octet-stream"}

        # Setup the Azure blob container name
        self.containerName = containerName
        self.blobBaseUrl = 'https://{}.blob.core.windows.net'.format(self.blobAccount)
        self.blobBaseUrl_photospheres = '{}/{}'.format(self.blobBaseUrl, self.containerName)



    # -----------------------------------------------------------------------#
    # Preliminary data transformation functions (needed for other functions) #
    # -----------------------------------------------------------------------#


    def check_degrees(self, x, y):
        """Checks and obtains degrees based on addition
        This function cycles degrees from 0 to 360 based on mathematical addition.
        Given an initial starting degree (x) we calculate the sum between x and y.
        If x+y exceeds 360, the function resets the value to accomodate radial consistency.

        Arguments
            x: initial (starting) degrees
            y: degrees to be added.

        Output
            sumdeg: returns the sum of degrees between 0 and 360.
        """
        sumdeg = x + y
        if sumdeg > 360:
            sumdeg = sumdeg - 360
        return sumdeg




    def check_cardinality(self, value):
        """Returns a cardinal direction from a dictionary
        This function checks a direction value (in degrees) agains a cardinal direction dictionary
        It returns a cardinal direction class in which the direction value belongs to.

        Arguments
            value: the direction value in degrees.

        Output
            direction: the cardinal direction class label.
        """
        # Defining a cardinal directions dictionary to be used in the next function
        cardinalDictionary = {
            'N0': [0, 5.625], 'NbE': [5.625, 16.875], 'NNE': [16.875, 28.125],
            'NEbN': [28.125, 39.375], 'NE': [39.375, 50.625], 'NEbE': [50.625, 61.875],
            'ENE': [61.875, 73.125], 'EbN': [73.125, 84.375], 'E': [84.375, 95.625],
            'EbS': [95.625, 106.875], 'ESE': [106.875, 118.125], 'SEbE': [118.125, 129.375],
            'SE': [129.375, 140.625], 'SEbS': [140.625, 151.875], 'SSE': [151.875, 163.125],
            'SbE': [163.125, 174.375], 'S': [174.375, 185.625], 'SbW': [185.625, 196.875],
            'SSW': [196.875, 208.125], 'SWbS': [208.125, 219.375], 'SW': [219.375, 230.625],
            'SWbW': [230.625, 241.875], 'WSW': [241.875, 253.125], 'WbS': [253.125, 264.375],
            'W': [264.375, 275.625], 'WbN': [275.625, 286.875], 'WNW': [286.875, 298.125],
            'NWbW': [298.125, 309.375], 'NW': [309.375, 320.625], 'NWbN': [320.625, 331.875],
            'NNW': [331.875, 343.125], 'NbW': [343.125, 354.375], 'N1': [354.375, 360.000001]
            }

        for direction in cardinalDictionary:
            if cardinalDictionary[direction][0] <= round(value, 3) < cardinalDictionary[direction][1]:
                if direction == 'N0' or direction == 'N1':
                    cardinalDir = 'N'
                else:
                    cardinalDir = direction
        return cardinalDir




    def get_dir(self, easting, northing):
        """Calculates direction from State Plane coodinates
        This function calculates the direction (angle in degrees) from Easting and Northing
        coordinates expressed in State Plane, California zone 6 (NAD84)

        Arguments
            easting: Easting coordinate value in NAD84.
            northing: Northing coordinate value in NAD84.

        Output
            degout: direction in degrees (always positive, reverses if negative)
        """
        degout = math.degrees(math.atan2(easting, northing))
        if degout >= 0:
            degout = 180 + degout
        elif degout < 0:
            degout = - degout
        return degout




    def convert_stateplane(self, xin, yin, zin):
        """Converts State Plane coordinates (NAD84) to Lat Lon degrees (WGS84)
        This function converts coordinates from State Plane coordinate system, CA zone 6 (NAD84, espg: 2230)
        to default ESRI and ArcGIS online Lat-Lon degrees (WGS84, espg: 4326)

        Arguments
            xin: Easting coordinates in NAD84
            yin: Northing coordinates in NAD84
            zin: Elevation coordinates in NAD84

        Output
            xout: Longitude coordinates in WGS84
            yout: Latitude coordinates in WGS84
            zout: Elevation coordinates in WGS84
        """
        # Setting preserve_units as True makes sure we preserve the original coordinates in feet.
        inProj = pyproj.Proj(init = 'epsg:2230', preserve_units = True)
        outProj = pyproj.Proj(init = 'epsg:4326')
        xout, yout, zout = pyproj.transform(inProj, outProj, xin, yin, zin)
        return (xout, yout, zout)



    def time_convert(self, imgname, timestamp):
        """Converts image timestamp string to native datetime format
        This function takes as input the string timestamps from metadata and converts them to
        a native datetime format. The results are used in the json formatting where they are
        converted to different strings.

        Arguments
            imgname: the name of the image to be converted
            timestamp: the string timestamp input to be converted

        Output
            dtobject: a datetime object
        """
        namesplit = imgname.split('_')[0]
        YYYY = '20' + namesplit[:2]
        MM = namesplit[2:4]
        DD = namesplit[4:]
        day = timestamp / 86400
        hours = Decimal(str(day))%1 * 86400 / 3600
        minutes = Decimal(str(hours))%1 * 3600 / 60
        seconds = Decimal(str(minutes))%1 * 60
        msecs = Decimal(str(seconds))%1 * 10
        hh = int(hours)
        mm = int(minutes)
        ss = int(seconds)
        s = int(msecs)
        dtobject = datetime(int(YYYY),int(MM),int(DD),int(hh),int(mm),int(ss),100000*int(s))
        return dtobject


    def check_blob_container(self, containerName, create=False, publicAccess='blob'):
        """Check for the presence of a blob container in the account
        This function checks the Azure storage account whether or not a blob container (folder) exists or not.
        If the container exists, the program makes sure the publicAccess is set to the value of the function.
        If the container does not exist, if create=True, then the folder is created and publicAccess is set.
        If the container does not exist, and create=False (default), nothing is done.

        Arguments
            containerName: the name of the blob container (folder) to be checked
            create (=False by default): whether or not to create a new container if it doesn't exist.
            publicAccess (='blob' by default): level of public access to URL ('blob', 'container', etc)

        Returns
            Nothing. Performs operations in Microsoft Azure Storage on the cloud.
        """
        if self.blobService.exists(containerName):
            self.blobService.set_container_acl(containerName, public_access = publicAccess)
            print('Container {} exists. Public Access is set to {}'.format(containerName, publicAccess))
        elif create == True:
            self.blobService.create_container(containerName, public_access = publicAccess)
            assert self.blobService.exists(containerName)
            print('Container {} did not exist. A new container is created with public_access set to {}'.format(containerName, publicAccess))
        else:
            print('Container did not exist. No changes are requested. Program exits.')
        return





    # --------------------------------------
    # Photosphere Image Operation Functions
    # --------------------------------------


    def get_blob_list(self, containerName=None):
        """List all blobs in Azure storage blob
        This function gets a list of all files in an Azure storage blob (by container folder name)

        Arguments
            containerName (optional): 
                if containerName is None: Uses the Azure storage blob container name (from class initialization)
                if containerName is not None: Uses the defined Azure storage blob container

        Output
            blobList: the list of all files in the container
        """
        # List the blobs in the container (from class initialization)
        if containerName is None:
            container = self.containerName
        else:
            container = containerName
        blobList = []
        generator = self.blobService.list_blobs(container)
        for blob in generator:
            blobList.append(blob)
        return blobList




    def get_object_bounds(self, jsonstring):
        """Get detected object bounds from bounding box coordinates
        This function returns bounding coordinates for an object in detected Azure cognitive vision
        json string.

        Arguments
            jsonstring: the json detection response containing the object

        Output
            bounds: the set of bounds expressed in bounding box coordinates (x, y, w, h)
        """
        bounds = []
        nobj = jsonstring['Number_of_Objects']
        for i in range(0, nobj):
            bounds.append({
                'object': jsonstring['Object_{}'.format(i+1)],
                'vertices': [
                    {'x': jsonstring['x{}'.format(i+1)]},
                    {'y': jsonstring['y{}'.format(i+1)]},
                    {'w': jsonstring['w{}'.format(i+1)]},
                    {'h': jsonstring['h{}'.format(i+1)]}
                ]
            })
        return bounds




    def draw_boxes(self, image, bounds):
        """Draws annotation boxes in image
        This function uses the bound coordinates to draw annotation boxes around photosphere images

        Arguments
            image: the photosphere image to be annotated (cardinal)
            bounds: the bounding box coordinates of the detected objects

        Output
            image: the annotated image
        """
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype('arial.ttf', 18)
        for bound in bounds:
            draw.rectangle([
                bound['vertices'][0]['x'],
                bound['vertices'][1]['y'],
                bound['vertices'][0]['x'] + bound['vertices'][2]['w'],
                bound['vertices'][1]['y'] + bound['vertices'][3]['h']
                ], None, 'red')
            draw.text((bound['vertices'][0]['x'] + 5, bound['vertices'][1]['y'] + 5),
                bound['object'], fill = 'red', font = font)
        return image



    def write_jsonfile(self, name, data):
        """Writes detection output into a jsonfile
        This function outputs the processed results of the Azure cognitive vision detection process
        into a json file.

        Arguments
            name: the name of the json file to be saved
            data: the json string response data to be included

        Output
            Nothing, the json file is saved using the name provided
        """
        filename = name + '.json'
        with open(filename, 'w') as fp:
            json.dump(data, fp)
        return





    # ---------------------------------------
    # Feature functions for performing image
    # processing and classification analysis
    # ---------------------------------------



    def update_blob_metadata(self, metadata = 'CameraMetadata.xlsx'):
        """Uploads and updates blob metadata from excel file metadata
        This function will upload and update the blob metadata, based on
        the metadata file stored in image.

        Arguments
            metadatafile: the metadata filename

        Output
            Nothing; performs operation in the blob container
        """
        containerList = self.get_blob_list()
        self.check_blob_container(self.containerName)
        noImg = len(containerList)
        print('Number of blobs in container: {}'.format(noImg))

        if metadata is not None:
            xlMetadata = pd.read_excel(metadata, sheet_name=0)
            for i, img in enumerate(containerList):
                imgName = img.name
                print('\tProcessing image ({} of {}): {}'.format(i+1, noImg, imgName))
                xlMetaImg = xlMetadata.loc[xlMetadata['Filename'] == imgName]
                xlcols = xlMetaImg.iloc[0]

                # Convert the State Plane to Lat-Lon coordinates
                lon, lat, alt = self.convert_stateplane(
                    xlcols['OriginEasting'],
                    xlcols['OriginNorthing'],
                    xlcols['OriginHeight']
                    )

                # Create an empty json string to hold the image metadata
                jsonimg = {}
                jsonimg['Photosphere_Image_Name'] = xlcols['Filename']
                imgdt = self.time_convert(xlcols['Filename'], xlcols['Timestamp'])
                jsonimg['DateTime_display'] = imgdt.strftime('%m/%d/%Y %H:%M:%S.%f').rstrip('0')
                jsonimg['DateTime_string'] = imgdt.strftime('%Y%m%d%H%M%S.%f').rstrip('0')
                jsonimg['Photosphere_Resolution'] = '8000 x 4000'
                jsonimg['Photosphere_URL'] = '{}/{}'.format(self.blobBaseUrl_photospheres, xlcols['Filename'])
                jsonimg['Longitude'] = lon
                jsonimg['Latitude'] = lat
                jsonimg['Altitude'] = alt
                jsonimg['Direction'] = self.get_dir(xlcols['DirectionEasting'],xlcols['DirectionNorthing'])
                jsonimg['Origin_Easting'] = xlcols['OriginEasting']
                jsonimg['Origin_Northing'] = xlcols['OriginNorthing']
                jsonimg['Origin_Height'] = xlcols['OriginHeight']
                jsonimg['Direction_Easting'] = xlcols['DirectionEasting']
                jsonimg['Direction_Northing'] = xlcols['DirectionNorthing']
                jsonimg['Direction_Height'] = xlcols['DirectionHeight']
                jsonimg['Up_Easting'] = xlcols['UpEasting']
                jsonimg['Up_Northing'] = xlcols['UpNorthing']
                jsonimg['Up_Height'] = xlcols['UpHeight']
                jsonimg['Roll'] = xlcols['Roll']
                jsonimg['Pitch'] = xlcols['Pitch']
                jsonimg['Yaw'] = xlcols['Yaw']
                jsonimg['Omega'] = xlcols['Omega']
                jsonimg['Phi'] = xlcols['Phi']
                jsonimg['Kappa'] = xlcols['Kappa']
                metastring = {}
                for key in jsonimg.keys():
                    metastring[key] = str(jsonimg[key])
                self.blobService.set_blob_metadata(self.containerName,imgName, metastring)
                print('\tUpdating metadata in azure blob')
        return




    def process_cardinal_images(self, blob, containerIn, containerOut):
        """Process cardinal images from original photospheres
        This function crops and obtains 8 cardinal images (1000 x 1000) from the original photospheres,
        by cropping a region between 1550 and 2550 pixels, i.e., from (x1 = 0, y1 = 1550) to (x2 = 8000, 
        y2 = 2550) vertically. The function returns a list with 8 cardinal images, from left to right, 
        each image covering a 45 degrees vision span.

        Arguments
            blob: the blob object (photosphere image) to be processed
            containerIn: the name of the blob storage container containing the blob
            containerOut: the name of the blob storage container for the cardinal images to be saved

        Output
            Nothing; the results are processed and saved in containerOut storage blob.
        """
        try:
            imageName = blob.name
            
            # Getting the photosphere image metadata
            metaString = {}
            if self.blobService.get_blob_metadata(containerIn, imageName) is not {}:
                metaString = self.blobService.get_blob_metadata(containerIn, imageName)
                fields = ['Direction', 'Longitude', 'Latitude', 'Altitude', 'Origin_Easting', 'Origin_Northing', 'Origin_Height', 'Direction_Easting', 'Direction_Northing', 'Direction_Height', 'Up_Easting', 'Up_Northing', 'Up_Height', 'Roll', 'Pitch', 'Yaw', 'Omega', 'Phi', 'Kappa']
                for field in fields:
                    metaString[field] = float(metaString[field])

                # Getting the photosphere image from azure blob storage and convert it to bytes
                content = self.blobService.get_blob_to_bytes(containerIn, imageName).content
                img = Image.open(io.BytesIO(content))

                # Creating the areas of the cardinal images
                areas = []
                step = 1000
                for i in range(0, 8000, step):
                    coor = (i, 1550, i+step, 2550)
                    areas.append(coor)

                # This is the loop for the 8 cardinal areas
                for ncard, area in enumerate(areas):
                    cmeta = {}
                    cmeta = metaString
                    cardinalImg = img.crop(area)
                    cardinalArray = io.BytesIO()
                    cardinalImg.save(cardinalArray, format='JPEG')
                    cardinalArray = cardinalArray.getvalue()
                    cardinalDir = self.check_degrees(cmeta['Direction'], 22.5)
                    cardinalDir = self.check_degrees(cardinalDir, ncard * 45.0)
                    cardinalLabel = self.check_cardinality(cardinalDir)
                    cardinalImgName = '{}_{}_{}.jpg'.format(imageName.split('.jpg')[0], ncard + 1, cardinalLabel)
                    cmeta['Cardinal_Image_Name'] = cardinalImgName
                    cmeta['Cardinal_Image_URL'] = '{}/{}/{}'.format(self.blobBaseUrl, containerOut, cardinalImgName)
                    cmeta['Cardinal_Number'] = ncard + 1
                    cmeta['Cardinal_Direction'] = cardinalDir
                    cmeta['Cardinal_Direction_Label'] = cardinalLabel

                    # Set up the Computer Vision analysis parameter
                    url = self.visionBaseUrl + 'analyze'
                    headers = self.headers
                    params = {"visualFeatures": "Categories,Tags,Description,ImageType,Color,Objects"}
                    response = requests.post(url, headers = headers, params = params, data = cardinalArray)
                    response.raise_for_status()
                    responsejson = response.json()
                    if 'captions' in responsejson['description']:
                        if responsejson['description']['captions']:
                            cmeta['Caption'] = responsejson['description']['captions'][0]['text']
                            cmeta['Caption_Confidence'] = responsejson['description']['captions'][0]['confidence']
                    if 'metadata' in responsejson:
                        cmeta['Image_Width'] = responsejson['metadata']['width']
                        cmeta['Image_Height'] = responsejson['metadata']['height']
                        cmeta['Image Format'] = responsejson['metadata']['format']
                    if 'imageType' in responsejson:
                        cmeta['Clip_Art_Type'] = responsejson['imageType']['clipArtType']
                        cmeta['Line_Drawing_Type'] = responsejson['imageType']['lineDrawingType']
                    if 'color' in responsejson:
                        cmeta['Dominant_Color_Foreground'] = responsejson['color']['dominantColorForeground']
                        cmeta['Dominant_Color_Background'] = responsejson['color']['dominantColorBackground']
                        if len(responsejson['color']['dominantColors']) > 1:
                            cmeta['Dominant_Colors'] = ','.join(responsejson['color']['dominantColors'])
                        elif len(responsejson['color']['dominantColors']) == 1:
                            cmeta['Dominant_Colors'] = responsejson['color']['dominantColors'][0]
                        elif responsejson['color']['dominantColors'] is None:
                            cmeta['Dominant_Colors'] = ''
                    if 'categories' in responsejson:
                        lcat = len(responsejson['categories'])
                        cmeta['Number_of_Categories'] = lcat
                        for ncat, obj in enumerate(responsejson['categories']):
                            for cat in obj:
                                catName = 'Category_{}_{}'.format(cat.capitalize(), str(ncat + 1))
                                cmeta[catName] = obj[cat]
                    if 'tags' in responsejson:
                        ltags = len(responsejson['tags'])
                        cmeta['Number_of_Tags'] = ltags
                        for ntag, obj in enumerate(responsejson['tags']):
                            for tag in obj:
                                tagName = 'Tag_{}_{}'.format(tag.capitalize(), str(ntag + 1))
                                cmeta[tagName] = obj[tag]
                    if 'tags' in responsejson['description']:
                        cmeta['Description_Tags'] = ','.join(responsejson['description']['tags'])
                    if 'objects' in responsejson:
                        lobj = len(responsejson['objects'])
                        cmeta['Number_of_Objects'] = lobj
                        for nobj, obj in enumerate(responsejson['objects']):
                            centerX = obj['rectangle']['x'] + (obj['rectangle']['w'] / 2)
                            centerY = obj['rectangle']['y'] + (obj['rectangle']['h'] / 2)
                            centerDir = cardinalDir = 22.5 + (centerX * 0.045)
                            cmeta['Object_{}'.format(nobj + 1)] = obj['object']
                            cmeta['Object_{}_Confidence'.format(nobj + 1)] = obj['confidence']
                            cmeta['Object_{}_Direction'.format(nobj + 1)] = centerDir
                            cmeta['Object_{}_Longitude'.format(nobj + 1)] = 0.00
                            cmeta['Object_{}_Latitude'.format(nobj + 1)] = 0.00
                            cmeta['x{}'.format(nobj + 1)] = obj['rectangle']['x']
                            cmeta['y{}'.format(nobj + 1)] = obj['rectangle']['y']
                            cmeta['w{}'.format(nobj + 1)] = obj['rectangle']['w']
                            cmeta['h{}'.format(nobj + 1)] = obj['rectangle']['h']
                            cmeta['Center_x{}'.format(nobj + 1)] = centerX
                            cmeta['Center_y{}'.format(nobj + 1)] = centerY
                            if 'parent' in obj:
                                lpar = len(obj['parent'])
                                if lpar == 0:
                                    nparents = 0
                                else:
                                    nparents = lpar - 1
                                    k = 1
                                    cmeta['Object_{}_Parent_{}'.format(nobj + 1, k)] = obj['parent']['object']
                                    cmeta['Object_{}_Parent_{}_Confidence'.format(nobj + 1, k)] = obj['parent']['confidence']
                                    if 'parent' in obj['parent']:
                                        k += 1
                                        cmeta['Object_{}_Parent_{}'.format(nobj + 1, k)] = obj['parent']['parent']['object']
                                        cmeta['Object_{}_Parent_{}_Confidence'.format(nobj + 1, k)] = obj['parent']['parent']['confidence']
                                        if 'parent' in obj['parent']['parent']:
                                            k += 1
                                            cmeta['Object_{}_Parent_{}'.format(nobj + 1, k)] = obj['parent']['parent']['parent']['object']
                                            cmeta['Object_{}_Parent_{}_Confidence'.format(nobj + 1, k)] = obj['parent']['parent']['parent']['confidence']
                                            if 'parent' in obj['parent']['parent']['parent']:
                                                k += 1
                                                cmeta['Object_{}_Parent_{}'.format(nobj + 1, k)] = obj['parent']['parent']['parent']['parent']['object']
                                                cmeta['Object_{}_Parent_{}_Confidence'.format(nobj + 1, k)] = obj['parent']['parent']['parent']['parent']['confidence']

                    bounds = self.get_object_bounds(cmeta)
                    taggedImg = self.draw_boxes(cardinalImg, bounds)
                    taggedArray = io.BytesIO()
                    taggedImg.save(taggedArray, format='JPEG')
                    taggedArray = taggedArray.getvalue()

                    cardinalMetaBlob = {}
                    for key in cmeta.keys():
                        cardinalMetaBlob[key] = str(cmeta[key])

                    self.blobService.create_blob_from_bytes(
                        container_name = containerOut,
                        blob_name = cardinalImgName,
                        blob = taggedArray,
                        metadata = cardinalMetaBlob
                        )
            return
        except Exception as ex:
            # Print the exception message
            print(ex.args[0])




    def create_geojson_from_cardinals(self, container):
        """Generates a GeoJSON String from cardinal photosphere image analysis
        This function follows the process_cardinal_images function after the cardinal images are generated,
        their object detection process from Azure cognitive services computer vision is completed, and the 
        cardinal images have been annotated and tagged.

        Arguments
            container: the Azure blob storage container that holds the cardinal images (analyzed)

        Returns
            fcresponse: a GeoJSON Feature Collection containing all GeoJSON features and geopoints with all analyses.
        """
        try:
            featList = []
            self.check_blob_container(container)
            blobList = self.get_blob_list(container)
            
            for blob in tqdm(blobList):
                if self.blobService.get_blob_metadata(container, blob.name) is not {}:
                    metaString = self.blobService.get_blob_metadata(container, blob.name)

                    fieldsFloat = ['Direction', 'Longitude', 'Latitude', 'Altitude', 'Origin_Easting', 'Origin_Northing', 'Origin_Height', 'Direction_Easting', 'Direction_Northing', 'Direction_Height', 'Up_Easting', 'Up_Northing', 'Up_Height', 'Roll', 'Pitch', 'Yaw', 'Omega', 'Phi', 'Kappa', 'Cardinal_Direction', 'Caption_Confidence']
                    for fieldFloat in fieldsFloat:
                        if fieldFloat in metaString:
                            metaString[fieldFloat] = float(metaString[fieldFloat])

                    fieldsInt = ['Cardinal_Number', 'Image_Width', 'Image_Height', 'Number_of_Categories', 'Number_of_Tags', 'Number_of_Objects']
                    for fieldInt in fieldsInt:
                        if fieldInt in metaString:
                            metaString[fieldInt] = int(metaString[fieldInt])

                    if metaString['Number_of_Categories'] >= 1:
                        for i in range(1, metaString['Number_of_Categories'] + 1):
                            metaString['Category_Score_{}'.format(i)] = float(metaString['Category_Score_{}'.format(i)])
                    if metaString['Number_of_Tags'] >= 1:
                        for j in range(1, metaString['Number_of_Tags'] + 1):
                            metaString['Tag_Confidence_{}'.format(j)] = float(metaString['Tag_Confidence_{}'.format(j)])
                    if metaString['Number_of_Objects'] >= 1:
                        for k in range(1, metaString['Number_of_Objects'] + 1):
                            metaString['Object_{}_Confidence'.format(k)] = float(metaString['Object_{}_Confidence'.format(k)])
                            metaString['Object_{}_Direction'.format(k)] = float(metaString['Object_{}_Direction'.format(k)])
                            metaString['Object_{}_Longitude'.format(k)] = float(0.0)
                            metaString['Object_{}_Latitude'.format(k)] = float(0.0)
                            metaString['x{}'.format(k)] = int(metaString['x{}'.format(k)])
                            metaString['y{}'.format(k)] = int(metaString['y{}'.format(k)])
                            metaString['w{}'.format(k)] = int(metaString['w{}'.format(k)])
                            metaString['h{}'.format(k)] = int(metaString['h{}'.format(k)])
                            metaString['Center_x{}'.format(k)] = float(metaString['Center_x{}'.format(k)])
                            metaString['Center_y{}'.format(k)] = float(metaString['Center_y{}'.format(k)])

                    gpoint = geojson.Point((metaString['Longitude'], metaString['Latitude']))
                    gfeature = geojson.Feature(geometry = gpoint, properties = metaString)
                    featList.append(gfeature)
            fcresponse = geojson.FeatureCollection(featList)
            return fcresponse
        except Exception as ex:
            # Print the exception message
            print(ex.args[0])
