from datetime import datetime
import io
import logging
import os
import sys
from typing import List, Dict

import google.auth
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from toki_storage.storage_service import StorageService


logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger()

RAW_DATA_BUCKET = os.getenv("RAW_DATA_BUCKET", "stp_profiles_data_bucket-dev")
ROOT_FOLDER_ID = os.getenv("ROOT_FOLDER_ID", "1yTXAy3AIDGH42TSQz8t_DS5d1HpR3ygH")
FOLDER_TYPE = 'application/vnd.google-apps.folder'
FILE_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
creds = None
bucket = None
STORAGE_SERVICE = None


def download_stp_profiles(request):
    now = str(datetime.now().year)
    stp_folder_name = f"STP-profile-weights-{now}"
    stp_target_folder = get_stp_weights_folder(stp_folder_name)
    if stp_target_folder is not None:
        folder_list = list_xlsx_items_gdrive(stp_target_folder, FOLDER_TYPE)
        for folder_info in folder_list:
            erp_folder_name = folder_info["name"]
            erp_folder_id = folder_info["id"]
            files_list = list_xlsx_items_gdrive(erp_folder_id, FILE_TYPE)
            for single_file in files_list:
                download_data_dict = download_bytesio_gdrive(single_file)
                upload_gsc(download_data_dict, now, erp_folder_name)
    return "function run complete"


def get_credentials() -> Credentials:
    """Get credentials from env service account"""
    scopes = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/devstorage.read_write']
    global creds

    if creds is None:
        creds, _ = google.auth.default()

        if hasattr(creds, 'with_scopes'):
            creds = creds.with_scopes(scopes)
        else:
            creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)

    return creds


def get_bucket():
    """gets storage bucket"""
    global bucket

    if bucket is None:
        bucket = get_storage_service().get_bucket(RAW_DATA_BUCKET)

    return bucket


def get_stp_weights_folder(stp_folder_name: str) -> str:
    '''Function requires target folder id to get the stp profile weights folder subfolders'''
    page_token = None
    service = build('drive', 'v3', credentials=get_credentials())
    folderquery = f"'{ROOT_FOLDER_ID}' in parents"
    child = service.files().list(
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        q=folderquery, pageToken=page_token,
        fields='nextPageToken, files(id, name)').execute()
    for sub_folders in child['files']:
        if sub_folders['name'] == stp_folder_name:
            return sub_folders['id']
    logging.error(f'no folder named {stp_folder_name}')
    return None


def list_xlsx_items_gdrive(target_folder: str, target_type: str) -> List[Dict]:
    '''Function requires target folder id to get the target folder files of certain type'''
    page_token = None
    items_list = []
    folderquery = f"'{target_folder}' in parents and mimeType='{target_type}'"
    service = build('drive', 'v3', credentials=get_credentials())
    child = service.files().list(
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        q=folderquery, pageToken=page_token,
        fields='nextPageToken, files(id, name)').execute()
    for item_info in child['files']:
        items_list.append(item_info)
    return items_list


def download_bytesio_gdrive(single_file: Dict) -> Dict:
    '''Function requires list of file id's to get the bytesio data from them'''
    service = build('drive', 'v3', credentials=get_credentials())
    request = service.files().get_media(fileId=single_file['id'])
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    download_file = {"name": single_file['name'], "bytes": fh.getvalue()}
    return download_file


def upload_gsc(download_file: Dict, upload_year: str, erp_name: str) -> None:
    """Gets the bytes io data and filenames and stores them in gcs"""
    drive_file_name = download_file['name']
    file_name = drive_file_name.replace("-", "_").replace("__", "_")
    file_path = f'{upload_year}/{erp_name}/'

    get_storage_service().upload(RAW_DATA_BUCKET, file_path + file_name, download_file['bytes'])

    logging.info(f"{file_name} uploaded")


def get_storage_service():
    global STORAGE_SERVICE

    if STORAGE_SERVICE is None:
        STORAGE_SERVICE = StorageService()

    return STORAGE_SERVICE
