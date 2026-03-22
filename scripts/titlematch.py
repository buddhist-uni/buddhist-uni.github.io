#!/bin/python3

from gdrive_base import DRIVE_LINK, link_to_id
import website
from yaspin import yaspin
import pickle
import re
import joblib
import random
from rapidfuzz import fuzz
from itertools import chain
from sklearn.neural_network import MLPClassifier
from typing import Iterable
from functools import cache

parentheses = re.compile(r'\s*[\(\[][^)]*[\)\]]')
CLASSIFIER_FILE = 'titlematch.classifier'
classifier: MLPClassifier
classifier = None

def probability_filename_matches(
    filename: str | Iterable[str],
    work_title: str | Iterable[str],
    first_author: str | Iterable[str],
) -> float | list[float]:
  """Returns the match probability between `filename`(s) and the work(s)
  
  At most one of (title, author) and (filename) can be Iterable.
  It won't fill a whole 2D matrix
  
  Returns:
    0 -> 1 P(match)
      The optimal cutoff for Balanced Accuracy (=87.3%) is 0.6629"""
  assert type(work_title) == type(first_author), "work_title and first_author must be the same type"
  if isinstance(work_title, str) and isinstance(filename, str):
    parsed_name = split_file_name(filename)
    features = extract_feature_vector_for_item_parsed_name_pair(
      work_title,
      first_author,
      parsed_name,
    )
    return float(classifier.predict_proba([features])[0][1])
  if isinstance(filename, str):
    parsed_name = split_file_name(filename)
    features = []
    for title, author in zip(work_title, first_author):
      features.append(extract_feature_vector_for_item_parsed_name_pair(
        title,
        author,
        parsed_name,
      ))
    return [float(ps[1]) for ps in classifier.predict_proba(features)]
  if isinstance(first_author, str):
    features = []
    for fname in filename:
      features.append(extract_feature_vector_for_item_parsed_name_pair(
        work_title,
        first_author,
        split_file_name(fname),
      ))
    return [float(ps[1]) for ps in classifier.predict_proba(features)]
  raise ValueError("Unknown type combination")

@cache
def split_file_name(filename: str) -> tuple[str, str, str]:
  """Returns guessed (title, subtitle, author) strings
  Based on the naive assumption of a "Title_ Subtitle - Author.pdf" name
  """
  ret = ['','','']
  if filename.lower().endswith('.pdf'):
    filename = filename[:-4]
  filename =  parentheses.sub('', filename)
  filename = filename.replace('_-_', ' - ')
  if ' - ' in filename:
    auth_split = filename.split(' - ')
    ret[2] = auth_split[-1]
    # treat multiple ' - 's as :s that became _s
    filename = '_ '.join(auth_split[:-1])
  filename = filename.replace(': ', '_ ')
  if '_ ' in filename:
    ret[0] = filename.split('_ ')[0]
    ret[1] = filename[len(ret[0])+2:]
  else:
    ret[0] = filename
  return tuple(ret)

def extract_feature_vector_for_item_parsed_name_pair(
  true_title: str,
  first_author: str,
  split_file_name: tuple[str, str, str], # from above
) -> tuple[float, int, int, float, int, int, float, int]:
  assert split_file_name[0], f"No title in {split_file_name}"
  if ': ' in true_title:
    title = true_title.split(': ')
    subtitle = ': '.join(title[1:])
    title = title[0]
    if split_file_name[1]:
      return (
        fuzz.partial_ratio(split_file_name[0], title),
        len(split_file_name[0]),
        len(title),
        fuzz.partial_ratio(split_file_name[1], subtitle),
        len(split_file_name[1]),
        len(subtitle),
        fuzz.token_sort_ratio(split_file_name[2], first_author),
        len(split_file_name[2]),
      )
    return (
      fuzz.partial_ratio(split_file_name[0], title),
      len(split_file_name[0]),
      len(title),
      fuzz.partial_ratio(split_file_name[0], subtitle),
      len(split_file_name[0]),
      len(subtitle),
      fuzz.token_sort_ratio(split_file_name[2], first_author),
      len(split_file_name[2]),
    )
  # else there is no : in the true_title
  if split_file_name[1]:
    # But this file thinks there should be a subtitle
    return (
      fuzz.partial_ratio(split_file_name[0], true_title),
      len(split_file_name[0]),
      len(true_title),
      fuzz.partial_ratio(split_file_name[1], true_title),
      len(split_file_name[1]),
      0,
      fuzz.token_sort_ratio(split_file_name[2], first_author),
      len(split_file_name[2]),
    )
  # else no subtitle and not expecting one either
  return (
    fuzz.partial_ratio(split_file_name[0], true_title),
    len(split_file_name[0]),
    len(true_title),
    100.0, # '' == '' Perfect match!
    0,
    0,
    fuzz.token_sort_ratio(split_file_name[2], first_author),
    len(split_file_name[2]),
  )


if __name__ == "__main__":
  print("Welcome to the titlematch.py trainer")
  from gdrive import gcache, gcache_folder
  from sklearn.model_selection import GridSearchCV
  import heapq
  from tqdm import tqdm

  with yaspin(text="Loading website..."):
    website.load()
  print("Website loaded")

  disk_memorizor = joblib.Memory(gcache_folder, verbose=0)

  website_content_with_pdfs = [
    c for c in website.content if
    c.formats[0] == 'pdf' and c.get('drive_links')
    and str(c.drive_links[0]).startswith(DRIVE_LINK.split('{}')[0]) and
    c.get('authors')
  ]
  print(f"Found {len(website_content_with_pdfs)} content items with PDFs")
  drive_file_names = []
  for item in website_content_with_pdfs:
    drive_id = link_to_id(item['drive_links'][0])
    drive_file = gcache.get_item(drive_id)
    assert drive_file is not None, f"No file found in gcache for {DRIVE_LINK.format(drive_id)}"
    assert drive_file['name'].lower().endswith('.pdf'), f"File is called 'pdf' by the website: {DRIVE_LINK.format(drive_id)}"
    assert drive_file['name'] not in drive_file_names, f"Multiple files found with name = \"{drive_file['name']}\""
    drive_file_names.append(drive_file['name'])

  print("Loading the full feature vector matrix...")

  @disk_memorizor.cache()
  def build_full_feature_vector_matrix_for_items(
      content_paths: list[str],
      drive_file_names: list[str],
  ):  
    parsed_file_names = [split_file_name(fn) for fn in drive_file_names]
    # expand from possibly-pickled IDs 
    website_content = {
      c.content_path: c for c in website.content
    }
    website_content = [
      website_content[cpath] for cpath in content_paths
    ]
    ret = []
    print("Building the full training data feature matrix...", flush=True)
    for item in tqdm(website_content, unit='i'):
      row = []
      for parsed_name in parsed_file_names:
        row.append(
          extract_feature_vector_for_item_parsed_name_pair(
            item.title,
            website.normalized_author_name(item.authors[0]),
            parsed_name,
          )
        )
      ret.append(row)
    return ret

  full_feature_vector_matrix = build_full_feature_vector_matrix_for_items(
    [c.content_path for c in website_content_with_pdfs], # squish to IDs for pickling
    drive_file_names,
  )
  print("Selecting samples for X and y...")
  y = []
  X = []
  for row_i, row in enumerate(full_feature_vector_matrix):
    X.append(row[row_i]) # self-similarity features
    y.append(1) # I am myself
    # Now to find a few negative examples (don't just append all)
    # We pick randomly among the highest title, subtitle, and author scores
    # Along with three others completely at random
    highest_titles = []
    highest_title_score = 0
    highest_subtitles = []
    highest_subtitle_score = 0
    highest_authors = []
    highest_author_score = 0
    for col_j, col in chain(enumerate(row[:row_i]), enumerate(row[row_i+1:], start=row_i+1)):
      if col[0] == highest_title_score:
        highest_titles.append(col_j)
      if col[0] > highest_title_score:
        highest_title_score = col[0]
        highest_titles = [col_j]
      if col[3] == highest_subtitle_score:
        highest_subtitles.append(col_j)
      if col[3] > highest_subtitle_score:
        highest_subtitle_score = col[3]
        highest_subtitles = [col_j]
      if col[6] == highest_author_score:
        highest_authors.append(col_j)
      if col[6] > highest_author_score:
        highest_author_score = col[6]
        highest_authors = [col_j]
    to_take = set()
    to_take.add(random.choice(highest_titles))
    random.shuffle(highest_subtitles)
    random.shuffle(highest_authors)
    while len(highest_subtitles) or len(highest_authors):
      if len(highest_subtitles):
        choice = highest_subtitles.pop()
        if choice not in to_take:
          to_take.add(choice)
          highest_subtitles = []
      if len(highest_authors):
        choice = highest_authors.pop()
        if choice not in to_take:
          to_take.add(choice)
          highest_authors = []
    while len(to_take) < 10:
      choice = random.randrange(0, len(row))
      if choice != row_i:
        to_take.add(choice)
    for take_it in to_take:
      X.append(row[take_it])
      y.append(0)
  del full_feature_vector_matrix
  print("Add a bunch of tricky negatives...")
  all_pdf_filenames = set([
    f['name'] for f in 
    gcache.sql_query(
      "owner = 1 AND mime_type = ? AND shortcut_target IS NULL",
      ('application/pdf',),
    )
  ])

  random.shuffle(website.content)
  
  @disk_memorizor.cache(cache_validation_callback=joblib.expires_after(days=14))
  def find_hard_av_examples():
    ret = []
    for item in tqdm(website.content):
      if item.category != 'av' or 'pdf' in item.formats or not item.get('authors'):
        continue
      all_vecs = [extract_feature_vector_for_item_parsed_name_pair(
          item.title,
          website.normalized_author_name(item.authors[0]),
          split_file_name(filename),
        ) for filename in all_pdf_filenames]
      for feature_vec in heapq.nlargest(
        5,
        all_vecs,
      ):
        ret.append(feature_vec)
        all_vecs.remove(feature_vec)
      for vec in all_vecs:
        if random.random() < 0.01:
          ret.append(vec)
    return ret

  for feature_vec in find_hard_av_examples():
    X.append(feature_vec)
    y.append(0)

  print("Finding optimal model and params...")
  from sklearn.base import clone
  classifier = MLPClassifier(
    max_iter=300,
  )
  param_grid = {'hidden_layer_sizes': [
    (32, 16, 8, 8),
    (32, 16, 16, ),
  ]}
  classifier = GridSearchCV(
    classifier,
    param_grid=param_grid,
    cv=5,
    scoring='roc_auc',
    n_jobs=8,
  ).fit(X, y)
  
  print(f"Best params: {classifier.best_params_}")
  print(f"Best score: {classifier.best_score_}")
  
  print("Fetching additional negative examples based on first run mistakes...")
  for item in tqdm(website.content):
    if item.category != 'av' or 'pdf' in item.formats or not item.get('authors'):
      continue
    all_vecs = [extract_feature_vector_for_item_parsed_name_pair(
        item.title,
        website.normalized_author_name(item.authors[0]),
        split_file_name(filename),
      ) for filename in all_pdf_filenames]
    all_scores = classifier.predict_proba(all_vecs)
    score_vecs = [(score[1],) + vec for score, vec in zip(all_scores, all_vecs)]
    del all_scores
    del all_vecs
    for score_vec in heapq.nlargest(200, score_vecs):
      if score_vec[0] < 0.3:
        break
      to_add = tuple(list(score_vec)[1:])
      if to_add not in X:
        X.append(to_add)
        y.append(0)
  print("Training the final classifier...")
  classifier = clone(classifier.best_estimator_)
  classifier.set_params(
    max_iter=1000,
    verbose=True,
  )
  classifier.fit(X, y)
  pickle.dump(classifier, open(CLASSIFIER_FILE, 'wb'))
  print(f"Done training! Now testing...")
  del X
  del y
  website_content_with_pdfs
  av_content = [c for c in website.content if
    c.category == 'av' and
    'pdf' not in c.formats and
    c.get('authors')
  ]
  article_scores = []
  av_scores = []
  print("Scoring content with PDFs...")
  for c in tqdm(website_content_with_pdfs):
    article_scores.append(max(probability_filename_matches(
      all_pdf_filenames,
      c.title,
      website.normalized_author_name(c.authors[0]),
    )))
  print("Scoring AV content without PDFs...")
  for c in tqdm(av_content):
    av_scores.append(max(probability_filename_matches(
      all_pdf_filenames,
      c.title,
      website.normalized_author_name(c.authors[0]),
    )))
  import numpy as np
  y_scores = np.concatenate([article_scores, av_scores])
  y_true = np.concatenate([
      np.ones(len(website_content_with_pdfs)), # we should ideally find all these
      np.zeros(len(av_content)), # we should ideally not find any of these
  ])
  from sklearn.metrics import roc_curve
  fpr, tpr, roc_thresholds = roc_curve(y_true, y_scores)
  j_scores = tpr - fpr
  best_idx = np.argmax(j_scores)
  best_threshold_roc = roc_thresholds[best_idx]
  print(f"Optimal threshhold = {best_threshold_roc:.4f} (with a Balanced Accuracy of {(j_scores[best_idx]+1)*50:.2f}%)")

else: # if this was imported from elsewhere, load the classifier
  with yaspin(text="Loading titlematch classifier..."):
    classifier = pickle.load(open(CLASSIFIER_FILE, 'rb'))
