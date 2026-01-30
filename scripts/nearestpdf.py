#!/bin/python3

from train_tag_predictor import (
  get_trainable_gfiles_from_site,
  save_all_drive_texts,
  NORMALIZED_TEXT_FOLDER,
)
from tag_predictor import TagPredictor
from yaspin import yaspin
import numpy as np
from os import cpu_count
import joblib
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from scipy.sparse import vstack

print("Grabbing latest text pickles...")
save_all_drive_texts(all_files=get_trainable_gfiles_from_site())
print("Latest pickles grabbed")

with yaspin(text="Loading tag predictor..."):
  tag_predictor = TagPredictor.load()
print("Tag Predictor loaded")

print("Loading embeddings...")
picklefiles = sorted(NORMALIZED_TEXT_FOLDER.glob("*.pkl"))
def _load_pickle(f):
    normalized_text = joblib.load(f.open('rb'))
    if not normalized_text:
      normalized_text = ''
    return tag_predictor.tfidf_vectorize_texts([normalized_text], normalized=True)[0]
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

def file_closest_to_string(needle: str) -> tuple[str, float]:
  """Returns the google file id closest to the given string, and its similarity score."""
  needle_embedding = tag_predictor.tfidf_vectorize_texts(
    [needle],
    normalized=False,
  )[0]
  # @ is matrix multiplication, .T is transpose, .toarray() is dense
  # .ravel() ensures 1d the right way
  similarities = (corpus_embeddings @ needle_embedding.T).toarray().ravel()
  best_idx = np.argmax(similarities)
  return picklefiles[best_idx].stem, float(similarities[best_idx])
