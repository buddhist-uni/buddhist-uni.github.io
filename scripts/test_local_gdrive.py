import pytest
import tempfile
import os
from unittest import mock

import local_gdrive

@pytest.fixture
def temp_db_path():
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        db_path = tf.name
    yield db_path
    os.remove(db_path)

def test_drive_cache_init(temp_db_path):
    with local_gdrive.DriveCache(temp_db_path) as cache:
        assert cache.conn is not None
        assert cache.cursor is not None

def test_upsert_item_and_get(temp_db_path):
    with local_gdrive.DriveCache(temp_db_path) as cache:
        item = {
            'id': '123',
            'version': 1,
            'name': 'test_file.txt',
            'mimeType': 'text/plain',
            'parents': ['folder1'],
            'modifiedTime': '2023-01-01T00:00:00Z',
            'size': 100,
            'trashed': False,
            'owner': 1,
            'md5Checksum': 'md5',
        }
        cache.upsert_item(item)
        fetched = cache.get_item('123')
        assert fetched is not None
        assert fetched['name'] == 'test_file.txt'
        assert fetched['mimeType'] == 'text/plain'
        assert fetched['parents'] == ['folder1']

def test_upsert_shortcut(temp_db_path):
    with local_gdrive.DriveCache(temp_db_path) as cache:
        item = {
            'id': 'shortcut123',
            'version': 1,
            'name': 'shortcut_file',
            'mimeType': 'application/vnd.google-apps.shortcut',
            'shortcutDetails': {
                'targetId': 'real123',
                'targetMimeType': 'text/plain'
            },
            'parents': ['folder1'],
            'modifiedTime': '2023-01-01T00:00:00Z',
            'size': 0,
            'trashed': False,
            'owner': 1,
        }
        cache.upsert_item(item)
        fetched = cache.get_item('shortcut123')
        assert fetched is not None
        assert fetched['mimeType'] == 'application/vnd.google-apps.shortcut'
        assert 'shortcutDetails' in fetched
        assert fetched['shortcutDetails']['targetId'] == 'real123'
        assert fetched['shortcutDetails']['targetMimeType'] == 'text/plain'

def test_get_subfolders(temp_db_path):
    with local_gdrive.DriveCache(temp_db_path) as cache:
        folder = {
            'id': 'folder123',
            'version': 1,
            'name': 'Subfolder',
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': ['root1'],
            'modifiedTime': '2023-01-01T00:00:00Z',
            'size': 0,
            'trashed': False,
            'owner': 1,
        }
        cache.upsert_item(folder)
        subfolders = cache.get_subfolders('root1')
        assert len(subfolders) == 1
        assert subfolders[0]['id'] == 'folder123'

@mock.patch('gdrive_base.trash_drive_file')
def test_trash_file(mock_trash, temp_db_path):
    with local_gdrive.DriveCache(temp_db_path) as cache:
        item = {
            'id': 'file_to_trash',
            'version': 1,
            'name': 'trash.txt',
            'mimeType': 'text/plain',
            'parents': ['folder1'],
            'modifiedTime': '2023-01-01T00:00:00Z',
            'size': 100,
            'trashed': False,
            'owner': 1,
        }
        cache.upsert_item(item)
        assert cache.get_item('file_to_trash') is not None
        
        cache.trash_file('file_to_trash')
        
        mock_trash.assert_called_once_with('file_to_trash')
        assert cache.get_item('file_to_trash') is None
        assert cache.get_trashed_item('file_to_trash') is not None
