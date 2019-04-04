# ML Vision Photospheres Classification
This is a Visual Studio Solution containing python classes, functions and operations applying Machine Learning Vision classification on 360&deg; photosphere images.

## Azure Cognitive Vision REST Functions
---
All the REST functions below are contained on a class object 

***class AzCognVisionRest(object)***
```Class AzCognVisionRest:
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
 ```



### Preliminary data transformation functions (needed for other functions)

> The following set of functions are called from other functions and parts of the class code. They perform transformations, data checks, and conversions needed for the image processing functions.

Function| Description | Arguments | Output
---|---|---|---
**check_degrees(x,y)** <br/> *Checks and obtains degrees based on addition.* | This function cycles degrees from 0&deg; to 360&deg; based on mathematical addition. Given an initial starting degree (x), we calculate the sum between x and y. If x + y exceeds 360&deg;, the function resets the value to accomodate radial consistency. | *x*: initial (starting) degrees.<br/>*y*: degrees to be added. | *sumdeg*: returns the sum of degrees between 0 and 360&deg;
**check_cardinality(value)** <br/> *Returns a cardinal direction from a dictionary* | This function checks a direction value (in degrees, &deg;) against a cardinal direction dictionary. It returns a cardinal direction class in which the direction values belongs to. | *value*: the direction value in degrees, &deg; | *direction*: the cardinal direction class label.
**get_dir(easting, northing)** <br/> *Calculates direction from State Plane coordinates* | This function calculates the direction (angle, in degrees &deg;) from Easting and Northing coordinates expressed in State Plane, California zone 6 (NAD84). | *easting*: Easting coordinate value in NAD84. <br/> *northing*: Northing coordinate value in NAD84. | *degout*: direction in degrees (always positive, reverses if negative).
**convert_stateplane(xin,yin,zin)** <br/> *Converts State Plane coodrinates (NAD84) to Lat-Lon degrees (WGS84)* | This function converts coordinates from State Plane Coordinate System, California Zone 6 (NAD84, espg:2230) to default ESRI and ArcGIS online Lat-Lon degrees (WGS84, espg:4326) | *xin*: Easting coordinates in NAD84 <br/> *yin*: Northing coordinates in NAD84 <br/> *zin*: Elevation coordinates in NAD84. | *xout*: Longitude coordinates in WGS84 <br/> *yout*: Latitude coordinates in WGS84 <br/> *zout*: Elevation coordinates in WGS84.
**time_convert(imgname, timestamp)** <br/> *Converts image timestamp string (epoch) to native datetime format* | This function takes as input the string timestamps from photosphere metadata and converts them to a native datetime format. The results are used in the JSON formatting where they are converted to different strings. | *imgname*: the name of the image to be converted<br/> *timestamp*: the string timestamp input to be converted | *dtobject*: a datetime object.




### Photosphere Image Operations

> The following set of functions are performed at the photosphere image level. These functions support primary image processing operations and are used to obtain image data, draw bounding boxes, and write JSON strings to file.

Function| Description | Arguments | Output
---|---|---|---
**get_blob_list(containerName)** <br/> *Lists all blobs in Azure blob storage* | This function obtains a list of all files (images) in the Azure blob storage account (by blob container folder name). | *containerName*: The Azure blob storage container name (from class initialization). | *blobList*: the list of all files in the container.
**get_object_bounds(jsonstring)** <br/> *Get detected object bounds from bounding box coordinates* | This function returns bounding box coordinates for an object in detected Azure cognitive services computer vision JSON string. | *jsonstring*: the JSON detection response containing the object. | *bounds*: the set of bounds expressed in bounding box coordinates (x, y, w, h).
**draw_boxes(image, bounds)** <br/> *Draws annotation boxes in image* | This function uses the bound coordinates to draw annotation boxes areound photosphere images. | *image*: the photosphere image to be annotated (cardinal) <br/> *bounds*: the bounding box coordinates of the detected objects. | *image*: the annotated image.
**write_jsonfile(name, data)** <br/> *Writes detection output string into a JSON file* | This function outputs the processed results of the Azure cognitive services computer vision detection process, into a JSON (or a GeoJSON) file. | *name*: the name of the JSON file to be saved (without the extension) <br/> *data*: the JSON string response data to be included in its content | Nothing, the JSON file is saved using the name and content provided as inputs.


### Feature functions

> The following set of feature functions are used for performing image processing and classification analysis.

Function| Description | Arguments | Output
---|---|---|---
**update_blob_metadata(container, metadatafile='CameraMetadata.xlsx)** <br/> *Uploads and updates blob metadata from excel file metadata* | This function will upload and update the blob metadata, based on a provided metadata file stored containing metadata values for each blob image. | *container*: the blob container containing all blob images for which the metadata are to be obtained <br/> *metadatafile (optional)*: the metadata filename (the default name is 'CameraMetadata.xlsx', and is used if argument is omitted) | Nothing; Performs operation in the blob container directly.
**process_cardinal_images(blob, containerIn, containerOut)** <br/> *Process cardinal images from original photospheres* | This function crops and obtains 8 cardinal images (1000 x 1000) from the original photospheres, by cropping a region between 1550 and 2550 pixels, i.e., from (*x<sub>1</sub> = 0, y<sub>1</sub> = 1550*) to (*x<sub>2</sub> = 8000, y<sub>2</sub> = 2550*), vertically. The function returns a list with 8 cardinal images, from left to right, each image covering a 45&deg; vision span. | *blob*: the blob object (photosphere image) to be processed. <br/> *containerIn*: the name of the blob storage container containing the blob. <br/> *containerOut*: the name of the blob storage container for the cardinal images to be saved. | Nothing; the results are processed and saved in the 'ContainerOut' storage blob.
**create_geojson_from_cardinals(container)** <br/> *Generates a GeoJSON String from cardinal photosphere image analysis* | This function follows the process_cardinal_images function after the cardinal images are generated, their object detection process from Azure cognitive services computer vision is completed, and the  cardinal images have been annotated and tagged. | *container*: the Azure blob storage container that holds the cardinal images (analyzed) | *fcresponse*: a GeoJSON Feature Collection containing all GeoJSON features and geopoints with all analyses.




