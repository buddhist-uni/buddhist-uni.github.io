#!/bin/python3

import requests
import sqlite3
import json
from pathlib import Path
import threading

# Maybe a better place to put this mutual dependency?
from local_gdrive import locked

IDENTIFIERS_FIELD_TYPES = [
  "CORE_ID",
  "OAI_ID",
  "DOI",
  "ARXIV_ID",
]

class CoreAPIWorksCache:
  """
  Manages a SQLite DB for "works" fetched from the Cambridge CORE API
  https://core.ac.uk/

  This class can be used as a context manager:
  with CoreAPICache('my_cache.db') as cache:
      items = cache.sql_query(MY_QUERY)
  but it can also be used manually, just don't forget to call
  cache.close()
  when you're done :)

  Note that this class is thread-safe, so feel free to use in
  a multithreaded downloader.
  """

  def __init__(self, db_path: str | Path):
    """
    Connects to the SQLite DB at `db_path`
    """
    self.db_path = Path(db_path)
    self.conn = sqlite3.connect(db_path, check_same_thread=False)
    self._lock = threading.RLock()
    self.conn.row_factory = sqlite3.Row
    self.cursor = self.conn.cursor()
    self._create_tables()
  
  def _create_tables(self):
    create_tracking_table_sql = """
      CREATE TABLE IF NOT EXISTS tracking_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL UNIQUE,
        last_updated TEXT
      );
    """

    create_works_table_sql = """
      CREATE TABLE IF NOT EXISTS works (
        id TEXT PRIMARY KEY NOT NULL,     -- CORE's own ID
        title TEXT NOT NULL,
        created_date TEXT NOT NULL,       -- CORE added Date
        updated_date TEXT NOT NULL,       -- CORE updated Date
        data_provider INTEGER NOT NULL,   -- First provider id
        additional_data_providers TEXT,   -- json if more than one
        abstract TEXT,
        authors TEXT,                     -- json, as from API
        citation_count INTEGER,
        contributors TEXT,                -- json, as from API
        document_type TEXT,      -- from API, almost useless
        download_url TEXT,
        full_text TEXT,
        published_date TEXT,              -- might not have the exact date
        publisher TEXT,
        -- End CORE fields, below are my fields
        downloaded_timestamp INTEGER      -- negative means failed
      );
    """

    # Get these mostly from the `identifiers` field on the work
    # but also throw in the sourceFulltextUrls as type `SOURCE_URL`
    create_identifiers_table_sql = """
      CREATE TABLE IF NOT EXISTS identifiers (
        id TEXT PRIMARY KEY NOT NULL,     -- could two types overlap?
        work_id TEXT NOT NULL,
        id_type TEXT NOT NULL,
        FOREIGN KEY(work_id) REFERENCES works(id)
      );
    """
    create_id_table_index_sql = """
      CREATE INDEX IF NOT EXISTS idx_work_id ON identifiers(work_id);
    """

    create_journals_join_table_sql = """
      CREATE TABLE IF NOT EXISTS journals_works (
        work_id TEXT NOT NULL,
        journal_id TEXT NOT NULL,  -- ISSN
        FOREIGN KEY(work_id) REFERENCES works(id)
      );
    """
    create_journal_works_indexes_sql = """
      CREATE INDEX IF NOT EXISTS idx_work_journal ON journals_works(work_id);
      CREATE INDEX IF NOT EXISTS idx_journal_work ON journals_works(journal_id);
    """

    self.cursor.execute(create_tracking_table_sql)
    self.cursor.execute(create_works_table_sql)
    self.cursor.execute(create_identifiers_table_sql)
    self.cursor.execute(create_id_table_index_sql)
    self.cursor.execute(create_journals_join_table_sql)
    self.cursor.executescript(create_journal_works_indexes_sql)
    self.conn.commit()

  @locked
  def get_source_urls_for_work_id(self, work_id: str | int):
    self.cursor.execute("SELECT id FROM identifiers WHERE work_id = ? AND id_type = 'SOURCE_URL'", (work_id,))
    rows = self.cursor.fetchall()
    return [row['id'] for row in rows]

  @locked
  def upsert_work_from_api(self, api_obj: dict):
    data_provider = api_obj['dataProviders'][0]['id']
    additional_data_providers = None
    if len(api_obj['dataProviders']) > 1:
      additional_data_providers = json.dumps([
        p['id'] for p in api_obj['dataProviders'][1:]
      ])
    sql = f"""
      INSERT INTO works (id, title, created_date, updated_date, data_provider, additional_data_providers, abstract, authors, citation_count, contributors, document_type, download_url, full_text, published_date, publisher)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        title = excluded.title,
        updated_date = excluded.updated_date,
        data_provider = excluded.data_provider,
        additional_data_providers = excluded.additional_data_providers,
        abstract = excluded.abstract,
        authors = excluded.authors,
        citation_count = excluded.citation_count,
        contributors = excluded.contributors,
        document_type = excluded.document_type,
        download_url = excluded.download_url,
        full_text = excluded.full_text,
        published_date = excluded.published_date,
        publisher = excluded.publisher
      WHERE excluded.updated_date > works.updated_date;
    """
    self.cursor.execute(sql, (api_obj['id'], api_obj['title'], api_obj['createdDate'], api_obj['updatedDate'], data_provider, additional_data_providers, api_obj['abstract'], json.dumps(api_obj['authors']), api_obj['citationCount'], json.dumps(api_obj['contributors']), api_obj.get('documentType'), api_obj['downloadUrl'], api_obj['fullText'], api_obj['publishedDate'], api_obj['publisher']))

    for ID_TYPE in IDENTIFIERS_FIELD_TYPES:
      ids_of_type = [identif['identifier'] for identif in api_obj['identifiers'] if identif['type'] == ID_TYPE]
      self.cursor.execute("DELETE FROM identifiers WHERE work_id = ? AND id_type = ?;", (api_obj['id'], ID_TYPE))
      for ident in ids_of_type:
        self.cursor.execute("INSERT INTO identifiers (id, work_id, id_type) VALUES (?, ?, ?)", (ident, api_obj['id'], ID_TYPE))
    
    existing_source_urls = self.get_source_urls_for_work_id(api_obj['id'])
    missing_source_urls = set(api_obj['sourceFulltextUrls']) - set(existing_source_urls)
    for source_url in missing_source_urls:
      self.cursor.execute("INSERT INTO identifiers (id, work_id, id_type) VALUES (?, ?, 'SOURCE_URL')", (source_url, api_obj['id'], ))

    self.cursor.execute("DELETE FROM journals_works WHERE work_id = ?", (api_obj['id'],))
    for journal in api_obj['journals']:
      for issn in journal['identifiers']:
        self.cursor.execute("INSERT INTO journals_works (work_id, journal_id) VALUES (?, ?)", (api_obj['id'], issn, ))

    self.conn.commit()
  
  @locked
  def close(self):
    if self.conn:
      self.conn.commit()
      self.conn.close()
      self.conn = None
  
  # Context manager functions
  def __enter__(self):
    return self
  def __exit__(self, exc_type, exc_value, traceback):
    self.close()