
##################################################
# Azure Cognitive Vision ArcGIS Online Functions #
##################################################


# ----------------------------
# Preliminaries and Libraries
# ----------------------------

# Import the required libraries for the project
import os, io, geojson, json, http.client, requests, getpass, time
from datetime import datetime
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
from azure.storage.blob import BlockBlobService
from PIL import Image
from tqdm import tqdm
from ipywidgets import widgets
from IPython.display import display
http.client._MAXHEADERS = 5000

computer = os.environ['COMPUTERNAME']
if computer == "SRVYGS046C":
    prjPath = r"C:\Users\OCPWAlexandridisK\source\repos\ktalexan\ML-Vision-Photospheres"
elif computer == "DRK01":
    prjPath = r"C:\Users\ktale\source\repos\ktalexan\ML-Vision-Photospheres"
os.chdir(prjPath)


# -------------------------------------------------------
# Set global defaults and account access for the project
# -------------------------------------------------------

# Azure Blob Storage

# Setup account information for the Azure Blob Storage containing the photosphere cardinal (tagged) images.
# The images were generated from the previous process in the 'AzureCognitiveVisionRest.py' file.

# Setup account and key for the Azure blob storage containing the photosphere images
with open('credentialsAzure.json') as f:
    azcred = json.load(f)
    account_name = azcred['account']
    account_key = azcred['key']

blobService = BlockBlobService(account_name, account_key)
blobBaseUri = 'https://{}.blob.core.windows.net'.format(account_name)



def get_blob_list(containerName):
    """Lists the blobs in the container
    This function generates a list of blobs (images) that exist within an Azure Blob Storage container.

    Arguments
        containerName: the name of the Azure Blob Storage Container

    Output
        blobList: the list of blobs in the container
    """
    container = containerName
    blobList = []
    generator = blobService.list_blobs(container)
    for blob in generator:
        blobList.append(blob)
    return blobList

# Generate the blob image list for the 'cardinal' storage container
blobList = get_blob_list('cardinal')


# ArcGIS Online

# Get the account and token information for the ArcGIS online account.
with open('credentialsArcGIS.json') as f:
    credAGO = json.load(f)
    userArcGIS = credAGO['username']
    pswArcGIS = credAGO['password']

gis = GIS('https://www.arcgis.com', userArcGIS, pswArcGIS)

tokenURL = 'https://www.arcgis.com/sharing/rest/generateToken'
params = {'f': 'pjson', 'username': userArcGIS, 'password': pswArcGIS, 'referer': 'https://www.arcgis.com', 'expiration': str(525600)}
response = requests.post(tokenURL, data = params, verify = True)
token = response.json()['token']
5261750
me = gis.users.me
print("User: {}".format(me.username))

user_groups = me.groups
print('\nUser {} is a member of {} groups:'.format(me.username, str(len(user_groups))))
for i, group in enumerate(user_groups):
    print('\t[{}]: {}'.format(i, group.title))

# Obtain a list of folders for the user
myfolders = me.folders
print('\nUser {} has {} folders:'.format(me.username, str(len(myfolders))))
for i, folder in enumerate(myfolders):
    print('\t[{}]: {}'.format(i, folder['title']))

# Get the properties of the 'AzCognVision' folder
for i, folder in enumerate(myfolders):
    if folder['title'] == 'AzCognVision':
        print('\nProperties of {} folder:'.format(folder['title']))
        for attr in folder:
            if attr == 'created':
                dt = datetime.fromtimestamp(folder[attr] / 1e3)
                created = datetime.strftime(dt, '%m/%d/%Y %I:%M%p')
                print('\t{}: {}'.format(attr, created))
            else:
                print('\t{}: {}'.format(attr, folder[attr]))


# Set the 'AzCognitiveVision' as the working folder
workingfolder = [folder for folder in myfolders if folder['title'] == 'AzCognVision'][0]
print('\nMy working ArcGIS folder is: {}'.format(workingfolder['title']))

# List all the items in the working folder
myitems = me.items(folder = workingfolder)
print('\tItems in my working folder:')
for i, item in enumerate(myitems):
    print('\t\t[{}]: {} ({})'.format(i, item['title'], item['type']))


# ----------------------------------------------------------
# Processing cardinal images in ArcGIS online feature layer
# ----------------------------------------------------------

# Select the feature layer collection (flc) containing the GeoJSON analysis results
gis.content.search('Azure Cognitive Vision Cardinal Photospheres', 'Feature Layer')

acvflc = gis.content.search('Azure Cognitive Vision Cardinal Photospheres', 'Feature Layer')[0]
acvflc

# Update properties (if needed)
thumb = 'thumbs/GeoJSON2.png'
item_properties = {
    'title': 'Azure Cognitive Vision Cardinal Photospheres',
    'snippet': 'Azure Cognitive Vision Feature Collection for Tagged Cardinal Photosphere Images',
    'description': '<div style="text-align:Left;"><div><div><p><span>This layer contains image analysis results from </span><span style="font-weight:bold;"><font color="#008000">Azure Cognitive Services Computer Vision</font> </span><span>API run, for the </span><span style="font-weight:bold;"><font color="#b22222">tagged cardinal images (8 directions, 1000x1000)</font> </span><span>image parts from photospheres. The layer includes (embeds) the tagged (annotated) images as attachments.</span></p></div></div></div>',
    'licenseInfo': 'This is a test dataset only. Should not be used in production settings.',
    'accessInformation': 'This is a test dataset with programming under development. If you have any questions, contact Dr. Kostas Alexandridis for further details: Kostas.Alexandridis@ocpw.ocgov.com, (714) 967-0826'
    }
acvflc.update(item_properties, thumbnail = thumb)


# Get individual layer(s)
acvfl = acvflc.layers[0]
acvfl

type(acvfl)

# Update the layer's capabilities (if needed)
# first, check it's capabilities
acvfl.properties.capabilities
# if the capabilities are not 'Create,Delete,Query,Update,Editing' then enable the capabilities below
update_dict = {'capabilities': 'Create,Delete,Query,Update,Editing,Extract'}
acvfl.manager.update_definition(update_dict)



# Function adding attachments from blob images.
def add_lyr_attachments_from_blob(container, layer):
    """Adding attachments to ArcGIS feature layer from Azure blob images
    This function:
        1. Gets the blob list (images) from a blob storage container in Azure.
        2. For each of the blobs in the blob list, it obtains the image, and saves it
            temporarily in the notebook's project directory. The reason for this is that
            the Python API for adding attachments in a feature (hosted) layer only takes
            filepath as an argument.
        3. Performs a matching query, i.e., matching the cardinal image name from the
            blob list with the feature (hosted) layer's record containing the image name,
            and returning the ObjectId for that layer's table.
        4. Finally, it uploads and adds the temporarily saved image as an attachment to
            the record with the obtained ObjectId (OID).

    Arguments
        container: the name of the Azure blob storage container.
        layer: the hosted feature layer in ArcGIS online

    Output
        Nothing. Just adds the blob images as attachments to the hosted ArcGIS online
        feature layer.
    """
    blobList = get_blob_list(container)
    noblobs = len(blobList)
    for blob in tqdm(blobList):
        blobName = blob.name
        content = blobService.get_blob_to_bytes(container, blobName).content
        img = Image.open(io.BytesIO(content))
        img.save(blobName, 'JPEG')
        query = layer.query(where = "Cardinal_Image_Name LIKE '{}'".format(blobName), out_fields = 'ObjectId')
        oid = query.features[0].attributes['ObjectId']
        layer.attachments.add(oid, blobName)
        os.remove(blobName)


# When the 'add_lyr_attachments_from_blob' function is executed, it adds all 3,232 cardinal images
# as an attachment to the GeoJSON-based feature layer hosted in ArcGIS online.


# If needed, all attachments can be deleted

# Let's query the data now
acvfset = acvfl.query()
# display the feature set as a panda data frame
acvfset.sdf.head()

# Getting the features of the layer
acvfeat = acvfset.features
acvfeat[0].attributes['ObjectId']


# Creating a copy of the features for updating
rev_acvfeat = acvfeat

# Define the base URL for the feature layer
baseUrl = acvfl.url
# Use the objectId (OID) and the attributeId (AID) to create a URL link for each attached image
for i, feat in enumerate(tqdm(rev_acvfeat)):
    oid = feat.attributes['ObjectId']
    aid = acvfl.attachments.get_list(oid=oid)[0]['id']
    newUrl = '{}/{}/attachments/{}?token={}'.format(baseUrl, str(oid), str(aid), token)
    rev_acvfeat[i].attributes['Picture'] = newUrl
    newfeat = rev_acvfeat[i]
    update_result = acvfl.edit_features(updates = [newfeat])
    update_result

# Check if the attachments were added
rev_acvfeat[0].attributes['Picture']
rev_acvfeat[3231].attributes['Picture']

# Check the results of the edit operations
acvfl_edited = acvfl.query()
acvfl_edited.sdf.head()
acvfl_edited.features[0].attributes['ImageUrl']

test = rev_acvfeat[0]
test.attributes['ImageUrl']
oid = test.attributes['ObjectId']
aid = acvfl.attachments.get_list(oid=oid)[0]['id']
newUrl = '{}/{}/attachments/{}?token={}'.format(baseUrl, str(oid), str(aid), token)
test.attributes['ImageUrl'] = newUrl
update_result = acvfl.edit_features(updates = [test])
update_result

[field for fields in acvfset.fields if field.name == 'Picture']


item_properties = {
    'title': 'Azure Cognitive Vision Cardinal Photospheres Feature Collection',
    'tags': 'test, Azure Cognitive Vision, Machine Learning, Photospheres',
    'snippet': 'Azure Cognitive Vision Feature Collection for Tagged Cardinal Photosphere Images',
    'description': '<div style="text-align:Left;"><div><div><p><span>This layer contains image analysis results from </span><span style="font-weight:bold;"><font color="#008000">Azure Cognitive Services Computer Vision</font> </span><span>API run, for the </span><span style="font-weight:bold;"><font color="#b22222">tagged cardinal images (8 directions, 1000x1000)</font> </span><span>image parts from photospheres. The layer includes (embeds) the tagged (annotated) images as attachments.</span></p></div></div></div>',
    'licenseInfo': 'This is a test dataset only. Should not be used in production settings.',
    'accessInformation': 'This is a test dataset with programming under development. If you have any questions, contact Dr. Kostas Alexandridis for further details: Kostas.Alexandridis@ocpw.ocgov.com, (714) 967-0826',
    'type': 'GeoJson'
    }

item_file = 'cardinalFeatureCollection2.json'


cardinalfc = gis.content.add(item_properties, data=item_file, folder='AzCognVision')
cardinalfl = cardinalfc.publish()