#!/bin/python3

from tag_predictor import TagPredictor, normalize_text, DATA_DIRECTORY
from yaspin import yaspin
import numpy as np
import numpy.typing as npt
from os import cpu_count
import io
import joblib
from tqdm.contrib.concurrent import process_map as tqdm_process_map
import functools
from scipy.sparse import vstack
from strutils import prompt

# These parallel arrays contain the global database we match against
# Call `load()` to populate these
corpus_embeddings = None # A numpy matrix
picklefiles = None # an np.array of Path objects
gid_to_idx: dict[str, int]
gid_to_idx = None
google_files: list[dict]
google_files = None
filesizes: list[int]
filesizes = None # The size of the picklefiles

DECISION_HISTORY_FILE = DATA_DIRECTORY.joinpath('similar_file_decisions.pkl')

MIN_PICKLE_SIZE_TO_COMPARE = 400 # bytes. ~1 page of compressed, normalized text
MIN_VOCAB_SIZE_TO_COMPARE = 120 # words. ~1 short page of stemmed text
MAX_FILE_TO_TEXT_RATIO = 3000 # 1 char extracted per this many PDF bytes. Worse than that implies a mostly image PDF

# find_matching_files constants, see below for discussion and use
CONTENT_SIM_WEIGHT = 18
TITLE_SIM_WEIGHT = 10
BASELINE_OFFSET = 19
NORMALIZATION_DIVISOR = -3
MIN_TITLE_SIM = 0.1
MIN_CONTENT_SIM = 0.5

def cache_locally(subdir_name: str):
  def decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
      DIR = DATA_DIRECTORY.joinpath(f'.cache/{subdir_name}')
      CACHE_KEY_FILE = DIR.joinpath('key.pkl')
      CACHE_FILE = DIR.joinpath('value.pkl')

      if DIR.is_dir():
        if CACHE_KEY_FILE.is_file():
          try:
            old_key = joblib.load(CACHE_KEY_FILE)
            if list(old_key) == list(picklefiles) and CACHE_FILE.is_file():
              return joblib.load(CACHE_FILE)
          except Exception:
            pass
      else:
        DIR.mkdir(parents=True)

      ret = func(*args, **kwargs)

      joblib.dump(ret, CACHE_FILE)
      joblib.dump(picklefiles, CACHE_KEY_FILE)
      return ret
    return wrapper
  return decorator

def find_matching_files(work_title: str, authors: str | list[str], file_contents: str) -> list[tuple[dict, float]]:
  """
  Finds Google Drive Files probably matching the described work.

  Uses a small Neural Net to match title and author to possible filenames,
  then uses a vector embedding space to compare file_contents and lastly
  uses a Logistic Classifier to combine those scores into a probability
  estimating the chances that a given PDF on Drive matches the provided info.

  Returns a sorted list of tuples (gfile, p_val)
    p_vals are in the range [0.5, 0.953) This is because
    even exact filename and content matches aren't 100% sure.
    About 1/20 near-exact matches are actually e.g. Volume 1 and 2 or
    a different translation of the same work--and thus not a duplicate!
    That and partial OCR errors, etc mean that, even given the "full text,"
    matching documents is an inexact science!
    While the Logistic curve used in this function is hand-coded, the values
    below were chosen with the benefit of data (and a dash of intuition).
    See https://tinyurl.com/3nex62jv for the scatter plot.

  :param work_title: The Title(: And Subtitle) of the work to search for 
  :type work_title: str
  :param first_author: The name of the work's first author or a `list` of the authors or the authors separated by " and "
  :type first_author: str | list[str]
  :param file_contents: The full text of the work to search for
  :type file_contents: str
  :return: A sorted list of Google File Objects probably matching and their normalized p scores
  :rtype: list[tuple[dict, float]]
  """
  needle_embedding = embed_needle(file_contents)
  if needle_embedding is None:
    return []
  import titlematch
  if picklefiles is None:
    load(False)
  if isinstance(authors, str) and ' and ' in authors:
     authors = authors.split(' and ')
  if authors is None or len(authors) == 0:
     authors = ''
  filenames = [gf['name'] for gf in google_files]
  # the titlematch probability prediction is already parallelized
  # so we can just pass it our filenames array and let it do its thing
  if isinstance(authors, str):
    all_title_sims = np.array(titlematch.probability_filename_matches(
       filenames,
       work_title,
       authors,
    ))
  elif isinstance(authors, list):
    exploded_title_sims = []
    for author in authors:
      exploded_title_sims.append(
        titlematch.probability_filename_matches(
          filenames,
          work_title,
          author,
        )
      )
    exploded_title_sims = np.array(exploded_title_sims)
    all_title_sims = np.max(exploded_title_sims, axis=0) 
  else:
     raise ValueError(f"`author` must be a string or a list of strings")

  # always take the first arg when using `where` to get indexes
  reasonable_indexes = np.where(all_title_sims > MIN_TITLE_SIM)[0]
  if len(reasonable_indexes) == 0:
     return []
  filtered_embeddings = corpus_embeddings[reasonable_indexes]
  title_sims = all_title_sims[reasonable_indexes]
  content_sims = fast_cosine_similarity(filtered_embeddings, needle_embedding)
  z_scores = (CONTENT_SIM_WEIGHT * content_sims) + (TITLE_SIM_WEIGHT * title_sims) - BASELINE_OFFSET
  ret_indexes = np.where(z_scores > 0)[0]
  if len(ret_indexes) == 0:
     return []
  ret_indexes = ret_indexes[np.argsort(z_scores[ret_indexes])[::-1]]
  p_values = 1 / (1 + np.exp(z_scores[ret_indexes] / NORMALIZATION_DIVISOR))
  true_indexes = reasonable_indexes[ret_indexes]
  return [
     (google_files[tidx], p_val)
     for tidx, p_val in zip(true_indexes, p_values)
  ]

def embed_needle(needle: str):
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
  return needle_embedding

def fast_cosine_similarity(matrix, needle_embedding) -> npt.NDArray[np.float64]:
  """Like sklearn's cosine_similarity function but without safety checks
  
  Assumes that matrix and needle are both already normalized, etc"""
  # @ is matrix multiplication, .T is transpose, .toarray() is dense
  # .ravel() ensures 1d the right way round
  return (matrix @ needle_embedding.T).toarray().ravel()

def calculate_all_similarities_to_string(needle: str) -> npt.NDArray[np.float64] | None:
  """
  Returns the cosine similarities of the given string to all documents in the corpus.
  
  Returns:
    npt.NDArray[np.float64] | None: The similarities or None if the string is too short
       This array is parallel to `picklefiles`.
       Use `picklefiles[i].stem` to get the associated Google file id.
  """
  if corpus_embeddings is None:
    load(False)
  needle_embedding = embed_needle(needle)
  if not needle_embedding:
    return None
  return fast_cosine_similarity(corpus_embeddings, needle_embedding)

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
  if similarities is None or len(similarities) == 0:
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

tag_predictor: TagPredictor
tag_predictor = None
with yaspin(text="Loading tag predictor..."):
  tag_predictor = TagPredictor.load()
print("Tag Predictor loaded")
def _load_pickle(f):
    normalized_text = joblib.load(f.open('rb'))
    if not normalized_text:
      normalized_text = ''
    return tag_predictor.tfidf_vectorize_texts([normalized_text], normalized=True)[0]

@cache_locally('load_embeddings')
def _load_embeddings_for_pickles():
  # vstack() ensures this list of arrays becomes a proper matrix
  # Note this takes a couple minutes to load even with 6 workers
  # Therefor the caching logic
  return vstack(list(tqdm_process_map(
    _load_pickle,
    picklefiles,
    max_workers=cpu_count() or 6,
    unit='f',
    chunksize=100,
  )))

@cache_locally('load_filesizes')
def _load_filesizes() -> list[int]:
  # Note this takes a couple minutes to load even with 6 workers
  # Therefor the caching logic
  return [
     len(joblib.load(fp)) for fp in picklefiles
  ]


def load(create_new_pickles=False):
  global corpus_embeddings, picklefiles, filesizes, gid_to_idx, google_files
  from train_tag_predictor import (
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
  corpus_embeddings = _load_embeddings_for_pickles()
  print(f"Loaded {np.shape(corpus_embeddings)[0]} embeddings")
  print("Checking file sizes...")
  row_nnzs = np.diff(corpus_embeddings.indptr)
  # toss out PDF files that have too little text
  large_enough_idxs = np.where(row_nnzs >= MIN_VOCAB_SIZE_TO_COMPARE)[0]
  corpus_embeddings = corpus_embeddings[large_enough_idxs]
  picklefiles = np.array(picklefiles)[large_enough_idxs]
  filesizes = _load_filesizes()
  google_files = [
     gdrive.gcache.get_item(fp.stem) for fp in picklefiles
  ]
  # toss out PDF files that are mostly un-OCRed images
  size_ratios = np.array([
     google_files[idx]['size'] / filesizes[idx]
     for idx, fp in enumerate(picklefiles)
  ])
  good_ratios = np.where(size_ratios <= MAX_FILE_TO_TEXT_RATIO)[0]
  filesizes = np.array(filesizes)[good_ratios]
  corpus_embeddings = corpus_embeddings[good_ratios]
  picklefiles = picklefiles[good_ratios]
  google_files = np.array(google_files)[good_ratios]
  gid_to_idx = {
     fp.stem: idx for idx, fp in enumerate(picklefiles)
  }
  print(f"Trimmed down to {np.shape(corpus_embeddings)[0]} checkable embeddings")

def _calc_sim_chunk(indices):
  start, end = indices
  # Efficiently compute a chunk of the self-similarity matrix
  # Uses global corpus_embeddings via Copy-On-Write (COW) in forked processes
  # Returns a dense chunk (start-end, N)
  return (corpus_embeddings[start:end] @ corpus_embeddings.T).toarray()

@cache_locally('similarity_matrix')
def calculate_similarity_matrix() -> npt.NDArray[np.float64]:
  """
  Calculates the similarity matrix for the corpus.

  Assumes that `corpus_embeddings` is already loaded and normalized.
  
  Returns:
  --------
  An upper-triangular similarity matrix, with the self-similarity (diagonal) scores set to 0.
  """
  print("WARNING: This next step takes several minutes and all your RAM.")
  while not prompt("Have you closed your IDE and Chrome?"):
    print("Then do it!")
  print("Calculating similarity matrix...")
  n_docs = corpus_embeddings.shape[0]
  chunk_size = 1000
  
  chunks = [
      (i, min(i + chunk_size, n_docs))
      for i in range(0, n_docs, chunk_size)
  ]
  
  sim_chunks = tqdm_process_map(
      _calc_sim_chunk,
      chunks,
      max_workers=cpu_count() - 1,
      chunksize=1,
  )
  
  print("Constructing full similarity matrix...")
  # Stack dense chunks into the full (N, N) matrix (~3.7GB)
  full_sim = np.vstack(sim_chunks)
  del sim_chunks
  
  # Keep only upper triangle and zero out diagonal
  full_sim = np.triu(full_sim)
  np.fill_diagonal(full_sim, 0)
  
  return full_sim

def find_close_pairs(similarity_matrix, min_similarity=0.9):
  """
  Finds the pairs of documents that are most similar to each other.
  
  Returns:
  --------
  list of tuples (idx1, idx2, similarity)
  """
  assert min_similarity > 0 and min_similarity <= 1, f"min_similarity must be between 0 and 1, got {min_similarity}"
  matching_idxs = np.where(similarity_matrix >= min_similarity)
  return list(zip(matching_idxs[0], matching_idxs[1], similarity_matrix[matching_idxs]))

if __name__ == "__main__":
  import gdrive_base
  import gdrive
  load(True)
  print("Successfully loaded the latest PDF embeddings!")
  if not prompt("Would you like to review the embeddings for any unweeded duplicates?"):
    print("Okay then :)")
    exit(0)
  print("Loading the similarity matrix...")
  similarity_matrix = calculate_similarity_matrix()
  print("Selecting close neighboring pairs...")
  close_pairs = find_close_pairs(similarity_matrix, min_similarity=0.85)
  del similarity_matrix
  all_decisions = []
  if DECISION_HISTORY_FILE.exists():
    all_decisions = joblib.load(DECISION_HISTORY_FILE)
    assert isinstance(all_decisions, list), "Expected DECISION_HISTORY to be a list"
  distinctions = gdrive.FileDistinctionManager(gdrive.gcache)
  close_pairs = [
    (
      google_files[idx],
      google_files[jdx],
      sim,
    )
    for idx, jdx, sim in close_pairs
    if google_files[idx]['parent_id '] != gdrive.OLD_VERSIONS_FOLDER_ID and 
    google_files[jdx]['parent_id'] != gdrive.OLD_VERSIONS_FOLDER_ID and
    not distinctions.are_distinct(google_files[idx]['id'], google_files[jdx]['id'])
  ]
  folder_slugs = gdrive.load_folder_slugs()
  print(f"Found {len(close_pairs)} close pairs that need review...")
  for gfa, gfb, sim in close_pairs:
      decision = gdrive.is_duplicate_prompt(gfa, gfb, similariy=sim)
      all_decisions.append((decision, gfa, gfb, sim))
      joblib.dump(all_decisions, DECISION_HISTORY_FILE, compress=2)
      if decision == gdrive.ClosePairDecision.THEY_ARE_DISTINCT:
        distinctions.mark_distinct(gfa['id'], gfb['id'])
        continue
      would_have_chosen, reason = gdrive.select_ids_to_keep(
        [gfa, gfb],
        folder_slugs,
      )
      if len(would_have_chosen) == 2:
        print("ERROR: Cannot automatically handle these files as both are public!")
        input("Please handle these files manually and then press enter to continue...")
        continue
      would_have_chosen = would_have_chosen[0]
      if gfa['parent_id'] != gfb['parent_id']:
        if decision == gdrive.ClosePairDecision.FIRST_IS_OLD_VERSION and would_have_chosen == gfa['id']:
          if reason == 'is public':
            print("ERROR: The file you have decided is older is publicly launched! Please handle manually!")
            input("And press enter to continue...")
            continue
          gdrive.gcache.move_file(gfb['id'], gfa['parent_id'], gfb['parents'])
        if decision == gdrive.ClosePairDecision.SECOND_IS_OLD_VERSION and would_have_chosen == gfb['id']:
          if reason == 'is public':
            print("ERROR: The file you've chosen as older is publicly launched!")
            input("Please resolve this manually and then press enter to continue...")
            continue
          gdrive.gcache.move_file(gfa['id'], gfb['parent_id'], gfa['parents'])
      

