#!/bin/python3

from tag_predictor import TagPredictor, normalize_text, DATA_DIRECTORY
from yaspin import yaspin
import numpy as np
from os import cpu_count
import io
from pathlib import Path
import joblib
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from scipy.sparse import vstack

corpus_embeddings = None
picklefiles = None

MIN_PICKLE_SIZE_TO_COMPARE = 400 # bytes. ~1 page of compressed, normalized text
MIN_VOCAB_SIZE_TO_COMPARE = 120 # words. ~1 short page of stemmed text

def file_closest_to_string(needle: str) -> tuple[str, float]:
  """Returns the google file id closest to the given string, and its similarity score.
  
  Returns:
    tuple[str, float]: (google file id, similarity score)

  The similarity score is cosine similarity [0, 1] in our TFIDF vector space.
    Theoretical modeling shows that a good threshold balancing TPR and TNR for considering
    a document to be the same as another is somewhere between 0.935 and 0.965.
    In practice, anything higher than 0.90 is suspect and some duplicates will be as low as 0.85.
    But many duplicates have similarity >0.99, so feel free to set the threshold
    according to your tolerance for false positives vs false negatives.
  NOTE: due to floating point errors, similarity scores are sometimes >= 1.0, so
    if you're transforming to log p space, you must add an epsilon.
  """
  if corpus_embeddings is None:
    raise Exception("Call load() first")
  
  stemmed_needle = normalize_text(needle)
  temp_buffer = io.BytesIO()
  # Use compression as a measure of entropy.
  # Some PDFs that parse wrong repeat the same few words over and over.
  joblib.dump(stemmed_needle, temp_buffer, compress=6)
  if temp_buffer.tell() < MIN_PICKLE_SIZE_TO_COMPARE:
    return (None, 0) # We don't look for similarities to tiny files

  needle_embedding = tag_predictor.tfidf_vectorize_texts(
    [stemmed_needle],
    normalized=True,
  )[0]
  # If this document doesn't have enough words in our vocabularly
  # don't bother trying to compare it.
  if needle_embedding.nnz < MIN_VOCAB_SIZE_TO_COMPARE:
    return (None, 0)
  # @ is matrix multiplication, .T is transpose, .toarray() is dense
  # .ravel() ensures 1d the right way
  similarities = (corpus_embeddings @ needle_embedding.T).toarray().ravel()
  best_idx = np.argmax(similarities)
  return picklefiles[best_idx].stem, float(similarities[best_idx])

# We have to load the tag_predictor outside of `load` so that
# tqdm_process_map can use it in _load_pickle. New processes load this module from "scratch"
# and don't have access to the "local" tag_predictor variable in the parent's `load`.
tag_predictor = None
with yaspin(text="Loading tag predictor..."):
  tag_predictor = TagPredictor.load()
print("Tag Predictor loaded")
def _load_pickle(f):
    normalized_text = joblib.load(f.open('rb'))
    if not normalized_text:
      normalized_text = ''
    return tag_predictor.tfidf_vectorize_texts([normalized_text], normalized=True)[0]

def _load_embeddings_for_pickles(pickles: list[Path]):
  # TODO support partial caching?
  DIR = DATA_DIRECTORY.joinpath('.cache/load_embeddings')
  cache_key = pickles
  CACHE_KEY_FILE = DIR.joinpath('key.pkl')
  CACHE_FILE = DIR.joinpath('value.pkl')
  if DIR.is_dir():
    if CACHE_KEY_FILE.is_file():
      old_key = joblib.load(CACHE_KEY_FILE)
      if old_key == cache_key and CACHE_FILE.is_file():
        return joblib.load(CACHE_FILE)
  else:
    DIR.mkdir(parents=True)
  # vstack() ensures this list of arrays becomes a proper matrix
  # Note this takes a couple minutes to load even with 6 workers
  # Therefor the caching logic
  ret = vstack(list(tqdm_process_map(
    _load_pickle,
    pickles,
    max_workers=cpu_count() or 6,
    unit='f',
    chunksize=100,
  )))
  # Make sure we commit the value to file before the key
  joblib.dump(ret, CACHE_FILE)
  joblib.dump(cache_key, CACHE_KEY_FILE)
  return ret


def load(create_new_pickles=False):
  global corpus_embeddings, picklefiles
  from train_tag_predictor import (
    get_trainable_gfiles_from_site,
    save_all_drive_texts,
    NORMALIZED_TEXT_FOLDER,
  )
  import gdrive
  print("Grabbing latest text pickles...")
  all_pdf_files = gdrive.gcache.sql_query(
    "owner = 1 AND mime_type = ? AND shortcut_target IS NULL",
    ('application/pdf',),
  )
  if create_new_pickles:
    save_all_drive_texts(all_files=all_pdf_files)
  expected_ids = {f['id'] for f in all_pdf_files}
  picklefiles = sorted(f for f in NORMALIZED_TEXT_FOLDER.glob("*.pkl") if f.stem in expected_ids and f.stat().st_size >= MIN_PICKLE_SIZE_TO_COMPARE)
  print(f"Pickles grabbed for {len(picklefiles)} pdf files")

  print("Loading embeddings...")
  corpus_embeddings = _load_embeddings_for_pickles(picklefiles)
  row_nnzs = np.diff(corpus_embeddings.indptr)
  large_enough_idxs = np.where(row_nnzs >= MIN_VOCAB_SIZE_TO_COMPARE)[0]
  corpus_embeddings = corpus_embeddings[large_enough_idxs]
  picklefiles = np.array(picklefiles)[large_enough_idxs]
  print(f"Loaded {np.shape(corpus_embeddings)[0]} embeddings")

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity

def find_nearest_neighbors():
  """
  Finds the nearest neighbor for each document in the corpus sparse matrix.
  
  Returns:
  --------
  nearest_indices : np.ndarray
    Array of shape (n_documents,) with the index of the nearest neighbor for each document
  nearest_similarities : np.ndarray
    Array of shape (n_documents,) with the cosine similarity to the nearest neighbor
  """
  n_docs = corpus_embeddings.shape[0]
  
  # Initialize arrays to store results
  nearest_indices = np.zeros(n_docs, dtype=np.int32)
  nearest_similarities = np.zeros(n_docs, dtype=np.float64)
  
  # Process in batches to manage memory
  batch_size = 1000  # Adjust based on available memory
  
  for i in range(0, n_docs, batch_size):
    end_idx = min(i + batch_size, n_docs)
    batch = corpus_embeddings[i:end_idx]
    
    # Compute cosine similarity between batch and all documents
    similarities = cosine_similarity(batch, corpus_embeddings)
    
    # For each document in the batch
    for j in range(similarities.shape[0]):
      doc_idx = i + j
      
      # Set diagonal to -1 to exclude self-similarity
      similarities[j, doc_idx] = -1
      
      # Find the maximum similarity (nearest neighbor)
      nearest_idx = np.argmax(similarities[j])
      nearest_sim = similarities[j, nearest_idx]
      
      nearest_indices[doc_idx] = nearest_idx
      nearest_similarities[doc_idx] = nearest_sim
    
    print(f"Processed {end_idx}/{n_docs} documents")
  
  return nearest_indices, nearest_similarities

if __name__ == "__main__":
  load(False)
  print("Finding nearest neighbors...")
  nearest_indices, nearest_similarities = find_nearest_neighbors()
  import ipdb; ipdb.set_trace()

