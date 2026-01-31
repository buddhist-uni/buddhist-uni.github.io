#!/bin/python3

from tag_predictor import TagPredictor
from yaspin import yaspin
import numpy as np
from os import cpu_count
import joblib
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from scipy.sparse import vstack

corpus_embeddings = None
picklefiles = None

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

  needle_embedding = tag_predictor.tfidf_vectorize_texts(
    [needle],
    normalized=False,
  )[0]
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

def load(create_new_pickles=True):
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
  picklefiles = sorted(f for f in NORMALIZED_TEXT_FOLDER.glob("*.pkl") if f.stem in expected_ids)
  print(f"Pickles grabbed for {len(picklefiles)} pdf files")

  print("Loading embeddings...")
  # vstack() ensures this list of arrays becomes a proper matrix
  # Note this takes a couple minutes to load even with 6 workers
  # Don't import this file willy-nilly!
  corpus_embeddings = vstack(list(tqdm_process_map(
    _load_pickle,
    picklefiles,
    max_workers=cpu_count() or 6,
    unit='f',
    chunksize=50,
  )))
  nonzero_idxs = np.diff(corpus_embeddings.indptr).nonzero()[0]
  corpus_embeddings = corpus_embeddings[nonzero_idxs]
  picklefiles = np.array(picklefiles)[nonzero_idxs]
  print(f"Loaded {np.shape(corpus_embeddings)[0]} embeddings")

