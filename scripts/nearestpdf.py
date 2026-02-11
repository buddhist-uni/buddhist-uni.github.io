#!/bin/python3

from tag_predictor import TagPredictor, normalize_text, DATA_DIRECTORY
from yaspin import yaspin
import numpy as np
import numpy.typing as npt
from sklearn.metrics.pairwise import cosine_similarity
from os import cpu_count
import io
from pathlib import Path
import joblib
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from scipy.sparse import vstack

corpus_embeddings = None
picklefiles = None
filesizes = None

MIN_PICKLE_SIZE_TO_COMPARE = 400 # bytes. ~1 page of compressed, normalized text
MIN_VOCAB_SIZE_TO_COMPARE = 120 # words. ~1 short page of stemmed text
MAX_FILE_TO_TEXT_RATIO = 3000 # 1 char extracted per this many PDF bytes. Worse than that implies a mostly image PDF

def calculate_all_similarities_to_string(needle: str) -> npt.NDArray[np.float64] | None:
  """
  Returns the cosine similarities of the given string to all documents in the corpus.
  
  Returns:
    npt.NDArray[np.float64] | None: The similarities or None if the string is too short
       This array is parallel to `picklefiles`.
       Use `picklefiles[i].stem` to get the associated Google file id.
  """
  if corpus_embeddings is None:
    raise Exception("Call load() first")
  
  stemmed_needle = normalize_text(needle)
  temp_buffer = io.BytesIO()
  # Use compression as a measure of entropy.
  # Some PDFs that parse wrong repeat the same few words over and over.
  joblib.dump(stemmed_needle, temp_buffer, compress=6)
  if temp_buffer.tell() < MIN_PICKLE_SIZE_TO_COMPARE:
    return None # We don't look for similarities to tiny files

  needle_embedding = tag_predictor.tfidf_vectorize_texts(
    [stemmed_needle],
    normalized=True,
  )[0]
  # If this document doesn't have enough words in our vocabularly
  # don't bother trying to compare it.
  if needle_embedding.nnz < MIN_VOCAB_SIZE_TO_COMPARE:
    return None
  # @ is matrix multiplication, .T is transpose, .toarray() is dense
  # .ravel() ensures 1d the right way
  return (corpus_embeddings @ needle_embedding.T).toarray().ravel()

def file_closest_to_string(needle: str) -> tuple[str, float]:
  """Returns the google file id closest to the given string, and its similarity score.
  
  Returns:
    tuple[str, float]: (google file id, similarity score) or ('', 0) if none

  The similarity score is cosine similarity [0, 1] in our TFIDF vector space.
    Theoretical modeling shows that a good threshold balancing TPR and TNR for considering
    a document to be the same as another is somewhere between 0.945 and 0.965.
    In practice, anything higher than 0.90 is suspect and some duplicates will be as low as 0.85.
    But many duplicates have similarity >0.99, so feel free to set the threshold
    according to your tolerance for false positives vs false negatives.
  NOTE: due to floating point errors, similarity scores are sometimes >= 1.0, so
    if you're transforming to log p space, you must add an epsilon.
  """
  similarities = calculate_all_similarities_to_string(needle)
  if not similarities:
     return ('', 0)
  best_idx = np.argmax(similarities)
  return picklefiles[best_idx].stem, float(similarities[best_idx])

def n_closest_files_to_string(needle: str, n_ret: int) -> list[tuple[str, float]]:
  """Returns the `n_ret` top files closest to the given string, and their similarity scores.
  
  Returns:
    list[tuple[str, float]]: list of (google file id, similarity score) pairs
    sorted by similarity score in descending order
  """
  similarities = calculate_all_similarities_to_string(needle)
  if similarities is None or len(similarities) == 0:
    return []
  
  n = min(n_ret, len(similarities))
  if n <= 0:
    return []

  # np.argpartition is O(N) and moves the largest n elements to the end.
  # We use -n to get the n largest elements.
  top_idxs = np.argpartition(similarities, -n)[-n:]
  
  # Then we sort only those n elements in descending order.
  sorted_top_idxs = top_idxs[np.argsort(similarities[top_idxs])[::-1]]
  
  return [
    (picklefiles[i].stem, float(similarities[i]))
    for i in sorted_top_idxs
  ]

def all_files_within(needle: str, min_similarity: float) -> list[tuple[str, float]]:
  """returns a list of all files with a similarity score above the given threshold
  
  Returns:
    list[tuple[str, float]]: list of (google file id, similarity score) pairs
    sorted by similarity score in descending order
  """
  assert min_similarity >= 0 and min_similarity <= 1, f"min_similarity must be between 0 and 1, got {min_similarity}"
  similarities = calculate_all_similarities_to_string(needle)
  if similarities is None or len(similarities) == 0:
    return []
  
  # Efficiently find indices where similarity >= threshold
  matching_idxs = np.where(similarities >= min_similarity)[0]
  
  if len(matching_idxs) == 0:
    return []
    
  # Sort only those matches
  sorted_matching_idxs = matching_idxs[np.argsort(similarities[matching_idxs])[::-1]]
  
  return [
    (picklefiles[i].stem, float(similarities[i]))
    for i in sorted_matching_idxs
  ]

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

def _load_filesizes():
  DIR = DATA_DIRECTORY.joinpath('.cache/load_filesizes')
  cache_key = picklefiles
  CACHE_KEY_FILE = DIR.joinpath('key.pkl')
  CACHE_FILE = DIR.joinpath('value.pkl')
  if DIR.is_dir():
    if CACHE_KEY_FILE.is_file():
      old_key = joblib.load(CACHE_KEY_FILE)
      if list(old_key) == list(cache_key) and CACHE_FILE.is_file():
        return joblib.load(CACHE_FILE)
  else:
    DIR.mkdir(parents=True)
  # vstack() ensures this list of arrays becomes a proper matrix
  # Note this takes a couple minutes to load even with 6 workers
  # Therefor the caching logic
  ret = [
     len(joblib.load(fp)) for fp in picklefiles
  ]
  # Make sure we commit the value to file before the key
  joblib.dump(ret, CACHE_FILE)
  joblib.dump(cache_key, CACHE_KEY_FILE)
  return ret


def load(create_new_pickles=False):
  global corpus_embeddings, picklefiles, filesizes
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
  print(f"Loaded {np.shape(corpus_embeddings)[0]} embeddings")
  print("Checking file sizes...")
  row_nnzs = np.diff(corpus_embeddings.indptr)
  # toss out PDF files that have too little text
  large_enough_idxs = np.where(row_nnzs >= MIN_VOCAB_SIZE_TO_COMPARE)[0]
  corpus_embeddings = corpus_embeddings[large_enough_idxs]
  picklefiles = np.array(picklefiles)[large_enough_idxs]
  filesizes = _load_filesizes()
  # toss out PDF files that are mostly un-OCRed images
  size_ratios = np.array([
     gdrive.gcache.get_item(fp.stem)['size'] / filesizes[idx]
     for idx, fp in enumerate(picklefiles)
  ])
  good_ratios = np.where(size_ratios <= MAX_FILE_TO_TEXT_RATIO)[0]
  filesizes = np.array(filesizes)[good_ratios]
  corpus_embeddings = corpus_embeddings[good_ratios]
  picklefiles = picklefiles[good_ratios]
  print(f"Trimmed down to {np.shape(corpus_embeddings)[0]} checkable embeddings")


def _find_nearest_neighbors_batch(indices):
  start_idx, end_idx = indices
  batch = corpus_embeddings[start_idx:end_idx]
  # Compute cosine similarity
  similarities = cosine_similarity(batch, corpus_embeddings)
  
  # Mask self-similarity
  # For the k-th document in the batch (index k), its global index is start_idx + k
  # We want to set similarities[k, start_idx + k] = -1
  rows = np.arange(similarities.shape[0])
  cols = np.arange(start_idx, end_idx)
  similarities[rows, cols] = -1
  
  # Find nearest neighbors
  nearest_indices = np.argmax(similarities, axis=1)
  nearest_similarities = similarities[rows, nearest_indices]
  
  return nearest_indices, nearest_similarities

def find_nearest_neighbors() -> tuple[np.ndarray, np.ndarray]:
  """
  Finds the nearest neighbor for each document in the corpus sparse matrix.
  
  Returns:
  --------
  nearest_indices : np.ndarray
    Array of shape (n_documents,) with the index of the nearest neighbor for each document
  nearest_similarities : np.ndarray
    Array of shape (n_documents,) with the cosine similarity to the nearest neighbor
  """
  DIR = DATA_DIRECTORY.joinpath('.cache/nearest_neighbors')
  CACHE_KEY_FILE = DIR.joinpath('key.pkl')
  CACHE_FILE = DIR.joinpath('value.pkl')
  if DIR.is_dir():
    if CACHE_KEY_FILE.is_file():
      old_key = joblib.load(CACHE_KEY_FILE)
      if list(old_key) == list(picklefiles) and CACHE_FILE.is_file():
        return joblib.load(CACHE_FILE)
  else:
    DIR.mkdir(parents=True)
  
  n_docs = corpus_embeddings.shape[0]
  num_workers = min(cpu_count() or 1, 5) # 5 is as many workers as I have RAM for...
  N_BATCHES = min(int(n_docs / 20), 500)
  
  # Split into batches
  split_indices = np.linspace(0, n_docs, N_BATCHES + 1, dtype=int)
  batches = []
  for i in range(len(split_indices) - 1):
      s, e = split_indices[i], split_indices[i+1]
      if s < e:
          batches.append((s, e))
  
  # Note: this takes >20 mins to load
  results = tqdm_process_map(
      _find_nearest_neighbors_batch,
      batches,
      max_workers=num_workers,
      chunksize=1
  )
  
  # Aggregate results
  all_indices = []
  all_sims = []
  for indices, sims in results:
      all_indices.append(indices)
      all_sims.append(sims)
      
  ret = (np.concatenate(all_indices), np.concatenate(all_sims), )
  joblib.dump(ret, CACHE_FILE)
  joblib.dump(picklefiles, CACHE_KEY_FILE)
  return ret

def is_duplicate_prompt(idx):
  import gdrive
  from strutils import system_open, radio_dial
  gfa = picklefiles[idx].stem
  jdx = nearest_indices[idx]
  gfb = picklefiles[jdx].stem
  fa = gdrive.gcache.get_item(gfa)
  fb = gdrive.gcache.get_item(gfb)
  if fa['parent_id'] == '1LBHbz_2prpqqrb_TQxRhuqNTrU9CIZga':
      return 'old a'
  if fb['parent_id'] == '1LBHbz_2prpqqrb_TQxRhuqNTrU9CIZga':
      return 'old b'
  pa = gdrive.gcache.get_item(fa['parent_id'])
  pb = gdrive.gcache.get_item(fb['parent_id'])
  def _print_file(gfile, gparent):
    print(f"\"{gfile['name']}\" in \"{gparent['name']}\" {gdrive.DRIVE_LINK.format(gparent['id'])}")
  _print_file(fa, pa)
  print(f"  was found to be {nearest_similarities[idx]} similar to")
  _print_file(fb, pb)
  while True:
    options = ["Open both", "A is old version", "B is old version", "Exact dupe", "Different files"]
    match radio_dial(options):
      case 0:
          system_open(gdrive.DRIVE_LINK.format(gfa))
          system_open(gdrive.DRIVE_LINK.format(gfb))
      case 1:
          return 'old a'
      case 2:
          return 'old b'
      case 3:
          return 'either'
      case 4:
          return False

if __name__ == "__main__":
  load(False)
  import gdrive
  print("Loading nearest neighbors...")
  nearest_indices, nearest_similarities = find_nearest_neighbors()
  gid_to_idx = {
     fp.stem: idx for idx, fp in enumerate(picklefiles)
  }
  size_similarities = [
     abs(filesizes[idx] - filesizes[jdx])/max(filesizes[idx], filesizes[jdx])
     for idx, jdx in enumerate(nearest_indices)
  ]
  import matplotlib.pyplot as plt
  DECISIONS_FILE = DATA_DIRECTORY.joinpath('decisions.pkl')
  if DECISIONS_FILE.is_file():
     decisions = joblib.load(DECISIONS_FILE)
  else:
     decisions = dict()
  for idx in range(len(nearest_indices)):
       if nearest_similarities[idx] < 0.96:
           continue
       if nearest_similarities[idx] > 1:
           continue
       jdx = nearest_indices[idx]
       key = (picklefiles[idx].stem, picklefiles[jdx].stem, )
       if jdx < idx or key in decisions:
           continue
       decisions[key] = is_duplicate_prompt(idx)
       joblib.dump(decisions, DECISIONS_FILE)
       print(f"So far made {len(decisions)} decisions")
       if len(decisions) % 10 == 0:
           stacked = [
             [nearest_similarities[gid_to_idx[gf[0]]] for (gf, dec) in decisions.items() if
              (str(dec) == 'either') == target[0] and
              # make sure that the pair we decided on is still considered a nearest pair
              gf[0] in gid_to_idx and gf[1] in gid_to_idx and nearest_indices[gid_to_idx[gf[0]]] == gid_to_idx[gf[1]]
              # also split by how close they are in size
              and target[1] == (size_similarities[gid_to_idx[gf[0]]] < 0.1)
             ]
             for target in [(False,True), (False,False), (True,True), (True,False)] # the stacked choices
           ]
           plt.hist(stacked, stacked=True, bins=int(len(decisions)/10), color=['red','orange','blue','purple'])
           plt.show()

