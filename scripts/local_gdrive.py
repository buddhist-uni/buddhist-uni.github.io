#!/bin/python3

import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

import gdrive_base

from yaspin import yaspin
from tqdm import tqdm

from datetime import datetime, timezone

def UTC_NOW():
    now_utc = datetime.now(timezone.utc)
    return now_utc.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

# Fields as named in the API that we fetch
FILE_FIELDS_ARRAY = [
    'id',
    'version',
    'name',
    'originalFilename',
    'parents',
    'mimeType',
    'owners',
    'properties',
    'trashed',
    'modifiedTime',
    'md5Checksum',
    'size',
    'shortcutDetails',
]
FILE_FIELDS = ','.join(FILE_FIELDS_ARRAY)

class DriveCache:
    """
    Manages a local SQLite cache for Google Drive file/folder metadata.

    This class is designed to be used as a context manager:
    items = gdrive_base.all_files_matching(query, FILE_FIELDS)
    with DriveCache("my_cache.db") as cache:
        cache.upsert_batch(items)
    but it can also be used manually:
    cache = DriveCache("my_cache.db")
    cache.upsert_item(data)
    cache.close() # Don't forget to close when you're done!

    Note that this is not thread-safe for writes.
    Use a unique context for each individual write from within a thread.
    SQLite itself should ensure the file is locked for each write.
    """

    def __init__(self, db_path: str | Path):
        """
        Connects to the SQLite database.
        
        Args:
            db_path: The file path for the SQLite database.
        """
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        # Return rows as dictionary-like objects
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._create_table()
    
    def _create_table(self):
        """Creates the 'drive_items' table if it doesn't exist."""

        create_metadata_table_sql = """
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY NOT NULL,
            value TEXT
        );
        """

        create_users_table_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        );
        """

        # Schema suitable for both active and trashed items
        items_schema = """
            id TEXT PRIMARY KEY NOT NULL,  -- Google Drive's file/folder ID
            version INTEGER NOT NULL,      -- Trust this for data freshness
            name TEXT NOT NULL,
            original_name TEXT,
            mime_type TEXT NOT NULL,       -- For shortcuts, the target's mime_type (use shortcutTarget IS NOT NULL to identify shortcuts)
            parent_id TEXT,                -- The ID of the parent folder
            modified_time TEXT NOT NULL,   -- ISO 8601 string
            size INTEGER,                  -- bytes on disk (if any)
            url_property TEXT,             -- The 'url' property if any
            owner INTEGER REFERENCES users(id),
            md5_checksum TEXT,
            shortcut_target TEXT           -- id of another drive_item if this item is a shortcut
        """

        create_drive_items_sql = f"CREATE TABLE IF NOT EXISTS drive_items ({items_schema});"
        create_trashed_items_sql = f"CREATE TABLE IF NOT EXISTS trashed_drive_items ({items_schema});"
        
        # Index all the cols we like to select by
        create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_mime_type
        ON drive_items (mime_type);
        CREATE INDEX IF NOT EXISTS idx_parent_id 
        ON drive_items (parent_id);
        CREATE INDEX IF NOT EXISTS idx_md5
        ON drive_items (md5_checksum);
        CREATE INDEX IF NOT EXISTS idx_url_prop
        ON drive_items (url_property);
        CREATE INDEX IF NOT EXISTS idx_shortcuts
        ON drive_items (shortcut_target);
        CREATE INDEX IF NOT EXISTS idx_users
        ON users (email);

        -- Special index to fix missing PK on existing trashed_drive_items tables
        -- that were created with 'CREATE TABLE AS SELECT' (which drops constraints)
        CREATE UNIQUE INDEX IF NOT EXISTS idx_trashed_id ON trashed_drive_items (id);
        """
        
        self.cursor.execute(create_metadata_table_sql)
        self.cursor.execute(create_users_table_sql)
        self.cursor.execute(create_drive_items_sql)
        self.cursor.execute(create_trashed_items_sql)
        self.cursor.executescript(create_index_sql)
        self.conn.commit()

    def upsert_item(self, item_data: Dict[str, Any]):
        """
        Inserts or updates a single file/folder item in the cache.
        Expects 'item_data' to be a dictionary similar to the
        
        Args:
            item_data: A dictionary containing item metadata.
        """
        try:
            self._upsert_item(item_data)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error upserting item {item_data.get('id')}: {e}")
    

    def _upsert_user(self, user: Dict[str, str]) -> Optional[int]:
        if not user or 'emailAddress' not in user:
            return None

        email = user['emailAddress']
        self.cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = self.cursor.fetchone()
        if row:
            return row['id']

        self.cursor.execute("INSERT INTO users (display_name, email) VALUES (?, ?)", 
                          (user.get('displayName', ''), email))
        return self.cursor.lastrowid
    
    def get_user(self, user_id: int):
        self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = self.cursor.fetchone()
        return row

    def _upsert_item(self, item_data: Dict[str, Any]):
        try:
            # 'parents' is a list, often just one item. 
            # Root folder might not have a 'parents' key.
            parent_id = item_data.get('parents', [None])[0]
            if isinstance(item_data.get('owner'), int):
                owner_id = item_data['owner'] # trust own of our own
            else:
                owner = item_data.get('owners', [{}])[0]
                owner_id = self._upsert_user(owner)
            size = item_data.get('size', 0)
            url_property = item_data.get('properties', {}).get('url', None)
            mime_type = item_data['mimeType']
            shortcut = item_data.get('shortcutDetails')
            if shortcut:
                mime_type = shortcut['targetMimeType']
                shortcut = shortcut['targetId']
            
            table = 'drive_items'
            if item_data['trashed']:
                table = 'trashed_drive_items'
                self.cursor.execute("DELETE FROM drive_items WHERE id = ? ;", (item_data['id'],))
            else:
                self.cursor.execute("DELETE FROM trashed_drive_items WHERE id = ? ;", (item_data['id'],))

            sql = f"""
            INSERT INTO {table} (id, version, name, original_name, mime_type, parent_id, modified_time, size, url_property, owner, md5_checksum, shortcut_target)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                version = excluded.version,
                name = excluded.name,
                mime_type = excluded.mime_type,
                parent_id = excluded.parent_id,
                modified_time = excluded.modified_time,
                size = excluded.size,
                url_property = excluded.url_property,
                owner = excluded.owner,
                md5_checksum = excluded.md5_checksum,
                shortcut_target = excluded.shortcut_target
                WHERE excluded.version > {table}.version;
            """
            self.cursor.execute(sql, (item_data['id'], item_data['version'], item_data['name'], item_data.get('originalFilename', None), mime_type, parent_id, item_data['modifiedTime'], size, url_property, owner_id, item_data.get('md5Checksum', None), shortcut))
        except KeyError as e:
            print(f"Missing expected key {e} in item data: {item_data}")

    def upsert_batch(self, items_data: List[Dict[str, Any]]):
        """
        Efficiently inserts or updates a list of items in a single transaction.
        
        Args:
            items_data: A list of item metadata dictionaries.
        """
        try:
            for item_data in items_data:
                self._upsert_item(item_data)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"SQLite error upserting item {item_data.get('id')}: {e}")


    def refill_all_data(self):
        """Drops all tables, and populates the DB with a completely fresh copy of data from GDrive."""
        print("Dropping all data and reloading the GDrive Cache from scratch...")
        self.cursor.execute("DELETE FROM drive_items")
        self.cursor.execute("DELETE FROM trashed_drive_items")
        self.cursor.execute("DELETE FROM metadata")
        all_files = gdrive_base.all_files_matching("'me' in owners and trashed=false", FILE_FIELDS)
        for file in tqdm(all_files, desc="Fetching all my files", unit=" files"):
            self._upsert_item(file)
        all_files = gdrive_base.all_files_matching("not 'me' in owners and trashed=false", FILE_FIELDS)
        for file in tqdm(all_files, desc="Fetching all shared files", unit=" files"):
            self._upsert_item(file)
        changes_page = gdrive_base.session().changes().getStartPageToken().execute()
        self.cursor.execute("INSERT INTO metadata (key, value) VALUES ('changes.pageToken', ?)", (changes_page['startPageToken'],))
        self.conn.commit()
        print("Done filling the GDrive cache!")
    

    def update(self):
        """Performs a full update of the data in the cache."""
        changes_page = self.cursor.execute("SELECT * FROM metadata WHERE key = 'changes.pageToken'").fetchone()
        if not changes_page:
            return self.refill_all_data()
        original_changes_page = changes_page['value']
        with yaspin(text="Pulling latest data from GDrive...") as ys:
            changes_page = changes_page['value']
            file_ids_to_fetch = set()
            file_ids_removed = set()
            while True:
                changelist = gdrive_base.session().changes().list(includeRemoved=True, restrictToMyDrive=False, pageToken=changes_page, pageSize=1000).execute()
                for change in changelist['changes']:
                    if change['removed']:
                        file_ids_removed.add(change['fileId'])
                    else:
                        file_ids_to_fetch.add(change['fileId'])
                if 'nextPageToken' in changelist: # nextPageToken signals there is more to fetch
                    changes_page = changelist['nextPageToken']
                    continue
                changes_page = changelist['newStartPageToken'] # newStartPageToken says come back later for more
                break
        if len(file_ids_removed):
            for fileId in tqdm(file_ids_removed, desc="Trashing gone files"):
                self._move_to_trash(fileId)
        file_ids_to_fetch = list(file_ids_to_fetch - file_ids_removed)
        if len(file_ids_to_fetch):
            all_items = gdrive_base.batch_get_files_by_id(file_ids_to_fetch, FILE_FIELDS)
            for item in tqdm(all_items, total=len(file_ids_to_fetch), desc="Fetching updated files"):
                self._upsert_item(item)
        if original_changes_page != changes_page:
            with yaspin(text="Saving GDrive Cache..."):
                self.cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('changes.pageToken', ?)", (changes_page,))
                self.conn.commit()
            print("Done updating GDrive cache!")

    ######
    # Cache read functions
    ######
    
    def row_dict_to_api_dict(self, table_row: Dict[str, Any]) -> Dict[str, Any]:
        """Takes a 'SELECT * FROM drive_items' row as a dict and converts it
        back to the Google Drive API structure"""
        ret = table_row.copy()
        if ret.get('md5_checksum'):
            ret['md5Checksum'] = ret['md5_checksum']
        del ret['md5_checksum']
        if ret.get('original_name'):
            ret['originalFilename'] = ret['original_name']
        del ret['original_name']
        ret['mimeType'] = ret['mime_type']
        del ret['mime_type']
        ret['modifiedTime'] = ret['modified_time']
        del ret['modified_time']
        ret['parents'] = [ret['parent_id']]
        # del table_row['parent_id'] # keep this one for convenience
        if ret.get('url_property'):
            ret['properties'] = {
                'url': ret['url_property']
            }
        del ret['url_property']
        if ret.get('shortcut_target'):
            ret['shortcutDetails'] = {
                'targetId': ret['shortcut_target'],
                'targetMimeType': ret['mimeType'],
            }
            ret['mimeType'] = 'application/vnd.google-apps.shortcut'
        del ret['shortcut_target']
        if ret.get('owner'):
            owner = self.get_user(ret['owner'])
            if owner:
                ret['owners'] = [{
                    'displayName': owner['display_name'],
                    'email': owner['email'],
                    'kind': 'drive#user',
                    'me': True if owner['id'] == 1 else False,
                }]
        del ret['owner']
        return ret
    

    def get_item(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single item by its Google Drive ID.
        
        Args:
            file_id: The ID of the file/folder.
            
        Returns:
            A dictionary of the item's data or None if not found.
        """
        self.cursor.execute("SELECT * FROM drive_items WHERE id = ?", (file_id,))
        row = self.cursor.fetchone()
        return self.row_dict_to_api_dict(dict(row)) if row else None
    
    def get_items_with_md5(self, md5: str) -> List[Dict[str, Any]]:
        """
        Retrieves all items with a specific MD5 checksum.
        
        Args:
            md5: The MD5 checksum to search for.
            
        Returns:
            A list of dictionaries, where each is an item with the specified MD5 checksum.
        """
        self.cursor.execute("SELECT * FROM drive_items WHERE md5_checksum = ?", (md5,))
        rows = self.cursor.fetchall()
        return [self.row_dict_to_api_dict(dict(row)) for row in rows]

    def get_children(self, parent_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all direct children (files and folders) of a given parent ID.
        
        Args:
            parent_id: The ID of the parent folder.
            
        Returns:
            A list of dictionaries, where each is a child item.
        """
        self.cursor.execute("SELECT * FROM drive_items WHERE parent_id = ?", (parent_id,))
        rows = self.cursor.fetchall()
        return [self.row_dict_to_api_dict(dict(row)) for row in rows]


    def get_subfolders(self, parent_id: str, include_shortcuts=True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM drive_items WHERE parent_id = ? AND mime_type = ?"
        if not include_shortcuts:
            query += " AND shortcut_target IS NULL"
        self.cursor.execute(
            query,
            (parent_id,'application/vnd.google-apps.folder',)
        )
        rows = self.cursor.fetchall()
        rows = [dict(row) for row in rows]
        if include_shortcuts:
            for row in rows:
                if row['shortcut_target']:
                    row['id'] = row['shortcut_target']
                    row['shortcut_target'] = None
        return [self.row_dict_to_api_dict(row) for row in rows]


    def search_by_name_containing(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches for items by name (case-insensitive).
        
        Args:
            query: The search string (e.g., "report").
            
        Returns:
            A list of matching items.
        """
        sql = "SELECT * FROM drive_items WHERE name LIKE ?"
        params = (f"%{query}%",)
        self.cursor.execute(sql, params)
        rows = self.cursor.fetchall()
        return [self.row_dict_to_api_dict(dict(row)) for row in rows]


    def files_exactly_named(self, name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all files and folders with the exact name.
        
        Args:
            name: The exact name of the file/folder.
            
        Returns:
            A list of dictionaries, where each is a file/folder item.
        """
        sql = "SELECT * FROM drive_items WHERE name = ?"
        params = (name,)
        self.cursor.execute(sql, params)
        rows = self.cursor.fetchall()
        return [self.row_dict_to_api_dict(dict(row)) for row in rows]

    ########
    # Write-through Functions
    ########

    def trash_file(self, file_id: str):
        """Actually performs the tashing and updates the cache"""
        gdrive_base.trash_drive_file(file_id)
        self._move_to_trash(file_id)
        self.conn.commit()

    def _move_to_trash(self, file_id: str):
        self.cursor.execute("INSERT INTO trashed_drive_items SELECT * FROM drive_items WHERE id = ?", (file_id,))
        self.cursor.execute("DELETE FROM drive_items WHERE id = ?", (file_id,))

    def move_file(self, file_id: str, folder: str):
        folder = gdrive_base.folderlink_to_id(folder) if folder.startswith("http") else folder
        self.cursor.execute("SELECT * FROM drive_items WHERE id = ?", (folder, ))
        folder_data = self.cursor.fetchone()
        if not folder_data or folder_data['mime_type'] != 'application/vnd.google-apps.folder':
            raise ValueError(f"Folder {folder} not found in cache.")
        gdrive_base.move_drive_file(file_id, folder)
        self.cursor.execute("UPDATE drive_items SET parent_id = ? WHERE id = ?", (folder, file_id))
        self.conn.commit()
    
    def create_folder(self, folder_name: str, parent_id: str) -> str:
        """Creates a new folder with the name and parent and rets the new id"""
        if parent_id.startswith('http'):
            parent_id = gdrive_base.folderlink_to_id(parent_id)
        now = UTC_NOW()
        new_folder_id = gdrive_base.create_folder(folder_name, parent_id)
        self.upsert_item({
            'id': new_folder_id,
            'name': folder_name,
            'parents': [parent_id],
            'size': 0,
            'mimeType': 'application/vnd.google-apps.folder',
            'version': 0,
            'modifiedTime': now,
            'owner': 1,
        })
        return new_folder_id

    ######
    # Connection management
    ######

    def close(self):
        """Commits changes and closes the database connection."""
        if self.conn:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Context manager exit. Ensures connection is closed."""
        self.close()
