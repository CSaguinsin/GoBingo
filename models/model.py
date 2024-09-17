from googleapiclient.http import MediaFileUpload
import os
import logging
from dotenv import load_dotenv  # Add this import

load_dotenv()  # Load environment variables from .env file

logger = logging.getLogger(__name__)

def create_drive_folder(service, folder_name):
    # Check if the folder already exists
    query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
    response = service.files().list(q=query, fields='files(id)').execute()
    folders = response.get('files', [])

    if folders:
        folder_id = folders[0]['id']
    else:
        # If the folder does not exist, create it
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [os.getenv('GOOGLE_DRIVE_FOLDER_ID')]  # Use environment variable
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')

    return f"https://drive.google.com/drive/folders/{folder_id}"

def upload_file_to_drive(service, file_path, folder_id):
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    logger.info(f"Uploaded file to Google Drive with ID: {file.get('id')}")