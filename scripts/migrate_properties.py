#!/bin/python3

import sqlite3
from pathlib import Path
import sys

# Add the scripts directory to path to allow imports if needed, 
# though this script is designed to be standalone-ish regarding DB logic.
sys.path.append(str(Path(__file__).parent))



def migrate_db(db_path):
    print(f"Migrating database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Create item_properties table
    print("Creating item_properties table...")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS item_properties (
        file_id TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT,
        PRIMARY KEY (file_id, key)
    );
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_props_key_val ON item_properties (key, value);
    """)

    # 2. Migrate data from drive_items
    print("Migrating properties from drive_items...")
    try:
        cursor.execute("SELECT id, url_property FROM drive_items WHERE url_property IS NOT NULL")
        rows = cursor.fetchall()
        count = 0
        for row in rows:
            cursor.execute(
                "INSERT OR REPLACE INTO item_properties (file_id, key, value) VALUES (?, 'url', ?)",
                (row[0], row[1])
            )
            count += 1
        print(f"Migrated {count} properties from drive_items.")
    except sqlite3.OperationalError as e:
        print(f"Skipping migration from drive_items (column likely missing): {e}")

    # 3. Migrate data from trashed_drive_items
    print("Migrating properties from trashed_drive_items...")
    try:
        cursor.execute("SELECT id, url_property FROM trashed_drive_items WHERE url_property IS NOT NULL")
        rows = cursor.fetchall()
        count = 0
        for row in rows:
            cursor.execute(
                "INSERT OR REPLACE INTO item_properties (file_id, key, value) VALUES (?, 'url', ?)",
                (row[0], row[1])
            )
            count += 1
        print(f"Migrated {count} properties from trashed_drive_items.")
    except sqlite3.OperationalError as e:
        print(f"Skipping migration from trashed_drive_items (column likely missing): {e}")

    # 4. Drop url_property column
    # SQLite doesn't support DROP COLUMN in older versions, but 3.35+ does.
    # The user is on 3.45.1 so this should work.
    print("Dropping url_property column from drive_items...")
    try:
        cursor.execute("ALTER TABLE drive_items DROP COLUMN url_property")
    except sqlite3.OperationalError as e:
        print(f"Error dropping column from drive_items (might already be gone): {e}")

    print("Dropping url_property column from trashed_drive_items...")
    try:
        cursor.execute("ALTER TABLE trashed_drive_items DROP COLUMN url_property")
    except sqlite3.OperationalError as e:
        print(f"Error dropping column from trashed_drive_items (might already be gone): {e}")

    # 5. Drop the old index if it exists
    print("Dropping old index idx_url_prop...")
    cursor.execute("DROP INDEX IF EXISTS idx_url_prop")

    conn.commit()
    
    print("Vacuuming database...")
    cursor.execute("VACUUM")
    
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    # Assuming standard path relative to this script
    db_path = Path(__file__).parent / ".gcache" / "drive.sqlite"
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        exit(1)
    
    migrate_db(db_path)
