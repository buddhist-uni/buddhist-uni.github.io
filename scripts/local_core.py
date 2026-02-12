#!/bin/python3

import requests
import sqlite3
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import threading
from time import sleep
from enum import IntEnum
from language_detection import LANGUAGE_DETECTOR, Language

# Maybe a better place to put this mutual dependency?
from local_gdrive import locked

TOKEN_PATH = Path('~/core-api.key').expanduser()
TOKEN = 'Bearer ' + TOKEN_PATH.read_text().strip()

# Recheck every half year at most
# absurdly, CORE API uses milliseconds for all its timestamps
# so in this file we just go with that
DOI_RECHECK_INTERVAL = 183 * 24 * 60 * 60 * 1000

IDENTIFIERS_FIELD_TYPES = [
  "CORE_ID",
  "OAI_ID",
  "DOI",
  "ARXIV_ID",
]

class TrackingQueryStatus(IntEnum):
  UNTESTED = 0
  INVALID = 1
  PAUSED = 2
  TRACKING = 3


def call_api(subpath: str, params: dict, retries=3):
  url = "https://api.core.ac.uk/v3/" + subpath
  try:
    response = requests.get(
      url,
      headers={
        'Authorization': TOKEN,
      },
      params=params,
    )
  except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as err:
    if retries > 0:
      print("CORE API response got cut off. Retrying in 4 seconds...")
      sleep(4)
      return call_api(subpath, params, retries=retries-1)
    else:
      raise err
  match response.status_code:
    case 200:
      return response.json()
    case 429:
      wait_until_stamp = response.headers['x-ratelimit-retry-after']
      wait_until = datetime.strptime(wait_until_stamp, '%Y-%m-%dT%H:%M:%S%z')
      now = datetime.now(wait_until.tzinfo)
      seconds_until = (wait_until - now).total_seconds()
      wait_interval = seconds_until + 2 # Add 2 seconds to be polite
      print(f"CORE API Rate limit hit. Waiting for {wait_interval:.1f} seconds...")
      sleep(wait_interval)
      # Don't count this as a retry as the API has asked us to wait
      return call_api(subpath, params, retries=retries)
    case 500:
      resp = response.json()
      if 'capacity' in resp.get('message', ''):
        if retries > 0:
          print("CORE API overloaded at the moment...waiting 6 secs and trying again...")
          sleep(6)
          return call_api(subpath, params, retries=retries-1)
        else:
          raise ConnectionRefusedError("CORE API overloaded right now. Try again later")
      raise NotImplementedError(f"Unknown 500 response: {resp.get('message', '')}")
    case 504:
      raise ValueError(f"Malformed request {params} to {subpath}")
    case _:
      raise NotImplementedError(f"Unknown status code {response.status_code}:\n\n{response.text}")

def api_timestring_to_timestamp(ts: str | None) -> int | None:
  """The API returns timestamps as ISO-ish strings but requests them as ms timestamps"""
  if not ts:
    return None
  dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
  dt = dt.replace(tzinfo=timezone.utc)
  return int(dt.timestamp() * 1000)

def current_timestamp() -> int:
  dt = datetime.now(timezone.utc)
  return int(dt.timestamp() * 1000)

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

  def __init__(self, db_path: str | Path, page_size=20):
    """
    Connects to the SQLite DB at `db_path`
    """
    assert page_size == int(page_size), "Page size must be an int"
    assert page_size > 0, "Page size must be positive"
    self.page_size = page_size
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
        up_to INTEGER, -- updated date of the latest work in epochal ms
        status INTEGER NOT NULL
      );
    """

    create_works_table_sql = """
      CREATE TABLE IF NOT EXISTS works (
        id TEXT PRIMARY KEY NOT NULL,     -- CORE's own ID
        title TEXT NOT NULL,
        created_date INTEGER NOT NULL,    -- CORE added Date
        updated_date INTEGER NOT NULL,    -- CORE updated Date
        data_provider INTEGER NOT NULL,   -- First provider id
        additional_data_providers TEXT,   -- json if more than one
        abstract TEXT,
        authors TEXT,                     -- json, as from API
        citation_count INTEGER,
        contributors TEXT,                -- json, as from API
        document_type TEXT,               -- from API, almost useless
        download_url TEXT,
        full_text TEXT,
        published_date INTEGER,           -- in ms lol
        publisher TEXT,
        -- End CORE fields, below are my fields
        downloaded_date INTEGER,          -- negative means failed
        en_confidence REAL                -- 0 to 1 that the work is in English
      );
    """

    # Get these mostly from the `identifiers` field on the work
    # but also throw in the sourceFulltextUrls as type `SOURCE_URL`
    create_identifiers_table_sql = """
      CREATE TABLE IF NOT EXISTS identifiers (
        id TEXT NOT NULL, -- sadly not unique. Sometimes different "works" have the same OAI_ID
        work_id TEXT NOT NULL,
        id_type TEXT NOT NULL,
        FOREIGN KEY(work_id) REFERENCES works(id),
        PRIMARY KEY (work_id, id)
      );
    """
    create_id_table_indexes_sql = """
      CREATE INDEX IF NOT EXISTS idx_work_id ON identifiers(work_id);
      CREATE INDEX IF NOT EXISTS idx_id_id ON identifiers(id);
    """

    create_unfound_dois_table_sql = """
      CREATE TABLE IF NOT EXISTS unfound_dois (
        doi TEXT PRIMARY KEY NOT NULL,
        checked_date INTEGER
      );
    """

    create_journals_join_table_sql = """
      CREATE TABLE IF NOT EXISTS journals_works (
        work_id TEXT NOT NULL,
        journal_id TEXT NOT NULL,  -- ISSN
        FOREIGN KEY(work_id) REFERENCES works(id),
        PRIMARY KEY (work_id, journal_id)
      );
    """
    create_journal_works_indexes_sql = """
      CREATE INDEX IF NOT EXISTS idx_work_journal ON journals_works(work_id);
      CREATE INDEX IF NOT EXISTS idx_journal_work ON journals_works(journal_id);
    """

    create_query_works_join_table_sql = """
      CREATE TABLE IF NOT EXISTS query_works (
        query_id INTEGER NOT NULL,
        work_id TEXT NOT NULL,
        FOREIGN KEY(work_id) REFERENCES works(id),
        FOREIGN KEY(query_id) REFERENCES tracking_queries(id),
        PRIMARY KEY (query_id, work_id) ON CONFLICT IGNORE
      );
    """

    self.cursor.execute(create_tracking_table_sql)
    self.cursor.execute(create_works_table_sql)
    self.cursor.execute(create_identifiers_table_sql)
    self.cursor.executescript(create_id_table_indexes_sql)
    self.cursor.execute(create_journals_join_table_sql)
    self.cursor.executescript(create_journal_works_indexes_sql)
    self.cursor.execute(create_query_works_join_table_sql)
    self.cursor.execute(create_unfound_dois_table_sql)
    self.conn.commit()

  @locked
  def get_source_urls_for_work_id(self, work_id: str | int):
    self.cursor.execute("SELECT id FROM identifiers WHERE work_id = ? AND id_type = 'SOURCE_URL'", (work_id,))
    rows = self.cursor.fetchall()
    return [row['id'] for row in rows]

  @locked
  def upsert_work_from_api(self, api_obj: dict, tracking_query_id: int | None=None):
    data_provider = api_obj['dataProviders'][0]['id']
    additional_data_providers = None
    if len(api_obj['dataProviders']) > 1:
      additional_data_providers = json.dumps([
        p['id'] for p in api_obj['dataProviders'][1:]
      ])
    updated_time = api_timestring_to_timestamp(api_obj['updatedDate'])
    en_conf = LANGUAGE_DETECTOR.compute_language_confidence(
      f"{api_obj['fullText'] or ''} {api_obj['title'] or ''} {api_obj['abstract'] or ''}",
      Language.ENGLISH,
    )
    sql = f"""
      INSERT INTO works (id, title, created_date, updated_date, data_provider, additional_data_providers, abstract, authors, citation_count, contributors, document_type, download_url, full_text, published_date, publisher, en_confidence)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        publisher = excluded.publisher,
        en_confidence = excluded.en_confidence
      WHERE excluded.updated_date > works.updated_date;
    """
    self.cursor.execute(sql, (
      api_obj['id'],
      api_obj['title'],
      api_timestring_to_timestamp(api_obj['createdDate']),
      updated_time,
      data_provider,
      additional_data_providers,
      api_obj['abstract'],
      json.dumps(api_obj['authors']),
      api_obj['citationCount'],
      json.dumps(api_obj['contributors']),
      api_obj.get('documentType'),
      api_obj['downloadUrl'],
      api_obj['fullText'],
      api_timestring_to_timestamp(api_obj.get('publishedDate')),
      api_obj['publisher'],
      en_conf,
    ))

    for ID_TYPE in IDENTIFIERS_FIELD_TYPES:
      ids_of_type = [identif['identifier'] for identif in api_obj['identifiers'] if identif['type'] == ID_TYPE]
      self.cursor.execute("DELETE FROM identifiers WHERE work_id = ? AND id_type = ?;", (api_obj['id'], ID_TYPE))
      for ident in ids_of_type:
        self.cursor.execute("INSERT INTO identifiers (id, work_id, id_type) VALUES (?, ?, ?)", (ident, api_obj['id'], ID_TYPE))
        if ID_TYPE == "DOI":
          self.cursor.execute("DELETE FROM unfound_dois WHERE doi = ?", (ident, ))
    
    existing_source_urls = self.get_source_urls_for_work_id(api_obj['id'])
    missing_source_urls = set(api_obj['sourceFulltextUrls']) - set(existing_source_urls)
    for source_url in missing_source_urls:
      self.cursor.execute("INSERT INTO identifiers (id, work_id, id_type) VALUES (?, ?, 'SOURCE_URL')", (source_url, api_obj['id'], ))

    self.cursor.execute("DELETE FROM journals_works WHERE work_id = ?", (api_obj['id'],))
    for journal in api_obj['journals']:
      for raw_id in journal['identifiers']:
        issn = str(raw_id).replace('issn:', '').strip()
        assert re.match(r'^[0-9]{4}-[0-9]{3}[0-9Xx]$', issn), f"Invalid ISSN: {issn}"
        self.cursor.execute(
          "INSERT OR IGNORE INTO journals_works (work_id, journal_id) VALUES (?, ?)",
          (api_obj['id'], issn, ),
        )

    if tracking_query_id:
      # Associate this work with this query and bump the query's up_to date
      self.cursor.execute("INSERT INTO query_works (query_id, work_id) VALUES (?, ?)", (tracking_query_id, api_obj['id'], ))
      self.cursor.execute("UPDATE tracking_queries SET up_to = ? WHERE id = ? AND (up_to IS NULL OR up_to < ?)", (updated_time, tracking_query_id, updated_time, ))
    
    self.conn.commit()
  
  @locked
  def register_query(self, query: str):
    """returns the id of the query, adding it to the DB if necessary"""
    assert "updatedDate" not in query, "Leave the updatedDate to me"
    try:
      self.cursor.execute("INSERT INTO tracking_queries (query, status) VALUES (?, ?)", (query, TrackingQueryStatus.UNTESTED, ))
    except sqlite3.IntegrityError:
      self.conn.rollback()
      self.cursor.execute("SELECT id FROM tracking_queries WHERE query = ?", (query,))
      row = self.cursor.fetchone()
      return row['id']
    ret = self.cursor.lastrowid
    self.conn.commit()
    return ret
  
  @locked
  def get_query(self, query_id: int) -> dict:
    self.cursor.execute("SELECT * FROM tracking_queries WHERE id = ?", (query_id, ))
    return dict(self.cursor.fetchone())

  @locked
  def set_query_status(self, query_id: int, query_status: int):
    self.cursor.execute(
      "UPDATE tracking_queries SET status = ? WHERE id = ?",
      (query_status, query_id, )
    )
    self.conn.commit()
  
  def load_another_page_from_query(self, query_id: int) -> int:
    """Calls the API with the registered work search query.

    Returns the number of works added"""
    query_obj = self.get_query(query_id)
    query_str = query_obj['query']
    if query_obj['status'] == TrackingQueryStatus.INVALID:
      raise ValueError(f"Cannot fetch invalid query: {query_str}")
    if query_obj['up_to']:
      query_str = f"({query_str}) AND updatedDate>{query_obj['up_to']}"
    print(f"Pulling works matching: {query_str}")
    try:
      one_page = call_api(
        'search/works',
        {
          'q': query_str,
          'limit': self.page_size,
          'sort': 'updatedDate:asc',
        },
      )
    except ValueError as err:
      self.set_query_status(query_id, TrackingQueryStatus.INVALID)
      raise err
    print(f"  got {len(one_page['results'])} / {one_page['totalHits']} for \"{query_str}\"")
    if query_obj['status'] == TrackingQueryStatus.UNTESTED:
      self.set_query_status(query_id, TrackingQueryStatus.PAUSED)
    ret = 0
    for result in one_page['results']:
      self.upsert_work_from_api(result, tracking_query_id=query_id)
      ret += 1
    # After inserting that page, we have to double check that we got all
    # of the works with updatedDate exactly = to the new "up_to"
    # otherwise, when we go to get the next page, we'll drop some works
    new_up_to = max(
      api_timestring_to_timestamp(
        result['updatedDate']
      ) for result in one_page['results']
    )
    seen_works = set(
      result['id'] for result in one_page['results']
    )
    query_str = f"({query_obj['query']}) AND updatedDate:{new_up_to}"
    print(f"Pulling works matching: {query_str}")
    boundary_page = call_api(
      'search/works',
      {
        'q': query_str,
        'limit': self.page_size,
      },
      retries=15, # be really persistent about this one
    )
    seen = set()
    additional = set()
    assert boundary_page['totalHits'] <= self.page_size, f"Got a page boundary with {boundary_page['totalHits']} hits but out page size is only {self.page_size}"
    for result in boundary_page['results']:
      if result['id'] in seen_works:
        seen.add(result['id'])
        continue
      self.upsert_work_from_api(result, tracking_query_id=query_id)
      additional.add(result['id'])
    expected_to_see = set(
      result['id'] for result in one_page['results']
      if api_timestring_to_timestamp(result['updatedDate']) == new_up_to
    )
    assert expected_to_see == seen, f"Boundary query saw {seen} repeats while {expected_to_see} were expected"
    if len(additional) > 0:
      print(f"  got {len(additional)} additional hits with the exact boundary updatedDate")
      return ret + len(additional)
    print("  got no additional works at the boundary updatedDate")
    return ret

  @locked
  def get_locally_from_doi(self, doi: str) -> dict | None:
    """If we have the work for this doi locally already, returns it, else None"""
    self.cursor.execute(
      "SELECT works.* FROM works JOIN identifiers ON works.id = identifiers.work_id WHERE identifiers.id = ? AND identifiers.id_type = 'DOI'",
      (doi, )
    )
    ret = [dict(row) for row in self.cursor.fetchall()]
    if len(ret) == 1:
      return ret[0]
    # First dedupe by finding the one(s) with full_text
    if len(ret) > 1:
      filtered = [row for row in ret if row['full_text']]
      if len(filtered) == 1:
        return filtered[0]
      if len(filtered) > 0:
        ret = filtered
    # Then by download_url
    if len(ret) > 1:
      filtered = [row for row in ret if row['download_url']]
      if len(filtered) == 1:
        return filtered[0]
      if len(filtered) > 0:
        ret = filtered
    # If we still have multiple works,
    # use a combination of citations and english score to pick one
    # Using lower ids as the tie breaker
    if len(ret) > 1:
      ret.sort(key=lambda r: r['id'])
      ret.sort(
        key=lambda r: 2*(r['en_confidence'] or 0)+(r['citation_count'] or 0),
        reverse=True,
      )
      return ret[0]
    return None

  def bulk_get_by_doi(self, dois: list[str], max_per_batch: int = 0, verbose: bool = False) -> list[dict | None]:
    """Attempts to find the works with the given DOIs, calling the API in batches if necessary
    
    Args:
      dois: list of DOIs to look up
      max_per_batch: maximum number of DOIs to look up per batch, defaults to self.page_size
      verbose: whether to print verbose output
    
    Returns:
      list of works corresponding to the input DOIs (in the same order)
    """
    if max_per_batch == 0:
      max_per_batch = self.page_size
    results: list[dict | None] = [None] * len(dois)
    # doi -> list of indices in the input list that need this DOI
    #  a list because the doi could appear in the input multiple times
    to_fetch: dict[str, list[int]] = {}
    
    now = current_timestamp()
    
    for i, doi in enumerate(dois):
      work = self.get_locally_from_doi(doi)
      if work:
        results[i] = work
        if verbose:
          print(f"  Found DOI:{doi} locally")
        continue
      
      # Check if we recently tried and failed to find this DOI
      with self._lock:
        self.cursor.execute("SELECT checked_date FROM unfound_dois WHERE doi = ?", (doi,))
        row = self.cursor.fetchone()
      
      if row:
        if row['checked_date'] + DOI_RECHECK_INTERVAL > now:
          if verbose:
            print(f"  Skipping DOI:{doi} (checked recently)")
          continue # leave results[i] as None
      
      if doi not in to_fetch:
        to_fetch[doi] = []
      to_fetch[doi].append(i)
    
    if not to_fetch:
      return results

    unique_dois_to_fetch = list(to_fetch.keys())
    for i in range(0, len(unique_dois_to_fetch), max_per_batch):
      batch = unique_dois_to_fetch[i : i + max_per_batch]
      # Construct OR query to consolidate calls and respect rate limits
      query = " OR ".join(f'doi:"{doi}"' for doi in batch)
      if verbose:
        print(f"  Querying API for {len(batch)} DOIs")
      resp = call_api(
        'search/works',
        {
          'q': query,
          'limit': 2*max_per_batch, # Just in case there are duplicates
        },
      )
      
      for result in resp['results']:
        self.upsert_work_from_api(result)
        if verbose:
          print(f"  Found DOI:{result['doi']} on the server")
      
      # For each DOI in our batch, check if we found it (via the DB lookup)
      for doi in batch:
        work = self.get_locally_from_doi(doi)
        if work:
          for idx in to_fetch[doi]:
            results[idx] = work
        else:
          # Still not found after API call, mark as unfound to avoid re-checking too soon
          with self._lock:
            self.cursor.execute(
              """INSERT INTO unfound_dois (doi, checked_date)
              VALUES (?, ?)
              ON CONFLICT(doi) DO UPDATE SET
              checked_date = excluded.checked_date;""",
              (doi, now, )
            )
            self.conn.commit()
          if verbose:
            print(f"  Didn't find DOI:{doi}")
            
    return results
  
  @locked
  def get_local_works_for_query(self, query_id: int) -> list[dict]:
    self.cursor.execute(
      "SELECT works.* FROM works JOIN query_works ON query_works.work_id = works.id WHERE query_works.query_id = ?",
      (query_id, )
    )
    return [dict(row) for row in self.cursor.fetchall()]
  
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
