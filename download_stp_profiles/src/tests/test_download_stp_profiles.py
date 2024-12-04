import os
import unittest
from unittest.mock import patch

from main import download_stp_profiles


class TestDownloadStpProfiles(unittest.TestCase):
    """
    Testing download_stp_profiles_function

    Assumptions:
     - STP folder should exist
     - check if stp folder name gets to list_xlsx_items_gdrive function
     - check if erp folder name gets to list_xlsx_items_gdrive function
     - check if download_bytesio_gdrive get to upload_gsc function



    Test cases:
     - if stp folder name doesn't exist
       -> none of the functions should be called
    """
    stp_folder_name = "STP-profile-weights-2023"
    stp_file_name = "2023_G0_EP_15min.xlsx"
    google_folder_type = 'application/vnd.google-apps.folder'
    google_file_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    bytestring = os.urandom(32)

    def setUp(self):
        self.expected_file_list = [{"name": self.stp_file_name, "id": self.stp_file_name}]
        self.expected_download_bytes = {"name": self.stp_file_name, "bytes": self.bytestring}

    @patch("main.get_stp_weights_folder")
    @patch("main.list_xlsx_items_gdrive")
    @patch("main.download_bytesio_gdrive")
    @patch("main.upload_gsc")
    def test_if_none_folder(self,
                            mock_upload_gsc,
                            mock_download_bytesio_gdrive,
                            mock_list_xlsx_items_gdrive,
                            mock_get_stp_weights_folder):
        """test return value is none that functions are not called"""
        mock_get_stp_weights_folder.return_value = None
        result = download_stp_profiles("")
        self.assertEqual(0, mock_upload_gsc.call_count)
        self.assertEqual(0, mock_download_bytesio_gdrive.call_count)
        self.assertEqual(0, mock_list_xlsx_items_gdrive.call_count)
        self.assertEqual("function run complete", result)

    @patch("main.download_bytesio_gdrive")
    @patch("main.upload_gsc")
    @patch("main.list_xlsx_items_gdrive")
    @patch("main.get_stp_weights_folder")
    def test_if_weights_folder_gets_to_list_folders(self,
                                                    mock_get_stp_weights_folder,
                                                    mock_list_xlsx_items_gdrive,
                                                    *args):
        """test if folder id and folder mime type gets to the function list_xlsx_items_gdrive on 1st call"""
        _ = args
        mock_get_stp_weights_folder.return_value = self.stp_folder_name
        download_stp_profiles("")
        list_xlsx_call_args = mock_list_xlsx_items_gdrive.call_args
        self.assertEqual(self.stp_folder_name, list_xlsx_call_args[0][0])
        self.assertEqual(self.google_folder_type, list_xlsx_call_args[0][1])

    @patch("main.download_bytesio_gdrive")
    @patch("main.upload_gsc")
    @patch("main.list_xlsx_items_gdrive")
    @patch("main.get_stp_weights_folder")
    def test_if_list_folder_gets_to_list_folders(self,
                                                 mock_get_stp_weights_folder,
                                                 mock_list_xlsx_items_gdrive,
                                                 *args):
        """test if file id and file mime type gets to the function list_xlsx_items_gdrive on 2nd call"""
        _ = args
        mock_get_stp_weights_folder.return_value = self.stp_folder_name
        mock_list_xlsx_items_gdrive.return_value = self.expected_file_list
        download_stp_profiles("")
        list_xlsx_call_args = mock_list_xlsx_items_gdrive.call_args_list[1]
        self.assertEqual(self.stp_file_name, list_xlsx_call_args[0][0])
        self.assertEqual(self.google_file_type, list_xlsx_call_args[0][1])

    @patch("main.list_xlsx_items_gdrive")
    @patch("main.get_stp_weights_folder")
    @patch("main.download_bytesio_gdrive")
    @patch("main.upload_gsc")
    def test_if_bytesio_get_to_upload_gcs(self,
                                          mock_upload_gsc,
                                          mock_download_bytesio_gdrive,
                                          mock_get_stp_weights_folder,
                                          mock_list_xlsx_items_gdrive):
        """check if download_bytesio_gdrive get to upload_gsc function"""
        mock_get_stp_weights_folder.return_value = self.stp_folder_name
        mock_list_xlsx_items_gdrive.return_value = self.expected_file_list
        mock_download_bytesio_gdrive.return_value = self.expected_download_bytes
        download_stp_profiles("")
        upload_gcs_args = mock_upload_gsc.call_args
        self.assertEqual(self.expected_download_bytes, upload_gcs_args[0][0])
