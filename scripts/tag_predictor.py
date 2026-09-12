#!/bin/python3

# import argparse
import enum
from functools import cache
from pathlib import Path
import json
from typing import Any, TypedDict, NotRequired
from collections.abc import Sequence
from types import NoneType
import regex

from nltk.stem.snowball import SnowballStemmer
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.utils.validation import (
    check_X_y,
    check_is_fitted,
    check_array,
)
from sklearn.utils.multiclass import unique_labels
from sklearn.base import clone as sklearn_clone
from sklearn.feature_extraction.text import (
    CountVectorizer,
    TfidfTransformer,
)
from sklearn.pipeline import Pipeline
from sklearn.base import (
    BaseEstimator,
    ClassifierMixin,
    TransformerMixin,
)
import joblib
import warnings
from unidecode import unidecode

from strutils import (
    git_root_folder,
)

# This config file hosts all essential configuration data
CONFIG_FILE = Path.home().joinpath('.auto_sort_unreads_rc.json')
CONFIG = dict()
DATA_DIRECTORY = ''
if CONFIG_FILE.exists():
    CONFIG = json.loads(CONFIG_FILE.read_text())
    DATA_DIRECTORY = CONFIG.get('data_directory')
if not DATA_DIRECTORY:
    DATA_DIRECTORY = input("Please provide the absolute path to a directory to store all the data in: ")
    CONFIG['data_directory'] = DATA_DIRECTORY
    CONFIG_FILE.write_text(json.dumps(CONFIG))
DATA_DIRECTORY = Path(DATA_DIRECTORY)
MODELS_DIRECTORY = DATA_DIRECTORY.joinpath('models')
UNSTEMMING_DICT_PATH = DATA_DIRECTORY.joinpath('unstemming_dictionary.pkl')

STOP_WORDS = set(git_root_folder.joinpath('scripts/stop_words.txt').read_text().split('\n'))
STOP_WORDS.update([w.lower() for w in STOP_WORDS])
stemmer = SnowballStemmer('english')
STOP_WORDS.update([stemmer.stem(word) for word in STOP_WORDS])

NORMALIZED_TEXT_FOLDER = DATA_DIRECTORY.joinpath('normalized_drive_text')
NORMALIZED_DRIVE_FOLDER = '1b1dOGh-fmbOhmwoPEnUgDehpqnQhOJ8Z'

def local_normalized_text_file(drive_file_id):
    name = f"{drive_file_id}.pkl"
    NORMALIZED_TEXT_FOLDER.mkdir(exist_ok=True)
    return NORMALIZED_TEXT_FOLDER.joinpath(name)

def save_normalized_text(drive_file_id, normalized_text):
    normalizedtextfile = local_normalized_text_file(drive_file_id)
    if normalizedtextfile.exists():
        return
    import gdrive_base as gdrive
    mimeType = "application/octet-stream"
    metadata = {
      "mimeType": mimeType,
      "name": normalizedtextfile.name,
      "parents": [NORMALIZED_DRIVE_FOLDER],
    }
    buffer = gdrive.BytesIO()
    joblib.dump(normalized_text, buffer, compress=6)
    media = gdrive.MediaIoBaseUpload(
      buffer,
      mimetype=mimeType,
      resumable=True,
    )
    gdrive._perform_upload(metadata, media, verbose=False)
    with normalizedtextfile.open("wb") as writer:
      writer.write(buffer.getbuffer())
    buffer.close()

def normalize_text(text: str) -> str:
    text = unidecode(text).lower()
    return ' '.join(
        stemmer.stem(word)
        for word in regex.split(r"[^a-z]+", text)
        if len(word) >= 4 and word not in STOP_WORDS
    )

YOUTUBE_DATA_FOLDER = DATA_DIRECTORY.joinpath('youtube_metadata')
if not YOUTUBE_DATA_FOLDER.exists():
    YOUTUBE_DATA_FOLDER.mkdir()

def get_ytdata_for_ids(youtube_ids: dict | list) -> list[dict]:
    ids_to_fetch = []
    for ytid in youtube_ids:
        cachefile = YOUTUBE_DATA_FOLDER.joinpath(f"{ytid}.json")
        if not cachefile.exists():
            ids_to_fetch.append(ytid)
    if ids_to_fetch:
        print(f"Fetching YouTube Data for {len(ids_to_fetch)} urls...")
        import gdrive_base
        snippets = gdrive_base.get_ytvideo_snippets(ids_to_fetch)
        transcripts = gdrive_base.fetch_youtube_transcripts(ids_to_fetch)
        if len(snippets) != len(ids_to_fetch):
            raise ValueError("Didn't get all the snippets?")
        for vid in snippets:
            if transcripts.get(vid['id']):
                vid['transcript'] = transcripts[vid['id']]
            else:
                vid['transcript'] = []
            cachefile = YOUTUBE_DATA_FOLDER.joinpath(f"{vid['id']}.json")
            cachefile.write_text(json.dumps(vid))
    # Yes, a little less efficient to dumps then immediate loads but
    # this is the easiest way to make sure the returned list is in the
    # same order as the argument list while batching the needed fetches
    return [json.loads(
        YOUTUBE_DATA_FOLDER.joinpath(f"{ytid}.json").read_text()
    ) for ytid in youtube_ids]

YT_STOP_LINES = set([
    '',
    'foreign',
    'cheers',
    '[Music]',
])
def flatten_youtube_transcript(transcript:list[dict]):
    """Note: does not normalize!"""
    if transcript == 'disabled':
        return ''
    ret = ' '.join([line['text'] for line in transcript if line['text'] not in YT_STOP_LINES])
    return regex.sub(r'\[.{0,35}\]', '', ret)

def md_stripper(markdown):
    """Very dumb. Just rm links because other
    features are rare in my content"""
    markdown = regex.sub(r'\]\([h/].{3,100}\)', '', markdown)
    return regex.sub(r'\{.{3,60}\}', '', markdown)

def flatten_youtube_metadata(video_data: dict) -> str:
    ret = (video_data['title'] + ' ') * 3
    if video_data.get('description'):
        ret += video_data['description'] + ' '
    if video_data.get('tags'):
        ret += ' '.join(video_data['tags']*5) + ' '
    return ret

def get_normalized_text_for_youtube_vid(video_data: dict) -> str:
    ret = flatten_youtube_metadata(video_data)
    if video_data.get('transcript') and not isinstance(video_data['transcript'], str):
        ret += flatten_youtube_transcript(video_data['transcript'])
    return normalize_text(ret)

class RemoveSparseFeatures(BaseEstimator, TransformerMixin):
    def __init__(self, k=15):
        self.k = k
    
    def __setstate__(self, state):
        # Migrate old attribute names on unpickle
        # TODO: rm this function after deprecating the old model
        if 'sparse_mask' in state and 'sparse_mask_' not in state:
            state['sparse_mask_'] = state.pop('sparse_mask')
        if 'num_features_in' in state and 'n_features_in_' not in state:
            state['n_features_in_'] = state.pop('num_features_in')
        self.__dict__.update(state)

    def fit(self, X, y=None):
        if hasattr(X, "tocsc"):
            # Efficient non-zero count for sparse matrices
            doc_counts = np.diff(X.tocsc().indptr)
        else:
            doc_counts = np.count_nonzero(X, axis=0)

        self.sparse_mask_ = np.asarray(doc_counts >= self.k).ravel()
        self.n_features_in_ = X.shape[1]        
        return self

    def transform(self, X):
        check_is_fitted(self, "sparse_mask_")
        return X[:, self.sparse_mask_]

    def get_feature_names_out(self, input_features=None):
        check_is_fitted(self, "sparse_mask_")
        
        if input_features is None:
            # Fallback names if unknown
            input_features = np.array([f"x{i}" for i in range(self.n_features_in_)])
        else:
            input_features = np.asarray(input_features)
            
        return input_features[self.sparse_mask_]

class ZeroLearningClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, label=None):
        self.label = label
        self.classes_ = []
    def fit(self, X, y=None, sample_weight=None):
        if self.label is None and y and len(y) > 0:
            self.label = y[0]
            self.classes_ = [self.label]
        return self
    def predict(self, X):
        return np.full(shape=(X.shape[0],), fill_value=self.label)
    def explain_yourself(self, *args):
        return f"I'm a leaf node that always predicts '{self.label}'"

class WordCloud(TypedDict):
    tag: str # the tag this is for 
    versus: list[str] # these terms discriminate compared to these tags
    terms: list[str] # the list of terms correlated with this tag

class OBUNodeClassifier(BaseEstimator, ClassifierMixin):
    """
    My custom sklearn classifier for making one step prediction
    
    It takes a base_classifier instance (Logit by default)
    and wraps it in a Pipeline that also does whatever last-minute
    feature selection and normalization we need.
    """
    def __init__(
        self,
        base_classifier:BaseEstimator|None=None,
        min_df=15,
    ) -> None:
        super().__init__()
        self.min_df = min_df
        if isinstance(base_classifier, BaseEstimator):
            self.base_classifier = sklearn_clone(base_classifier)
        else:
            raise ValueError("Need to pass a base classifier to NodeClassifier")

    def fit(self, X, y, sample_weight=None):
        X, y = check_X_y(X, y, accept_sparse=True)
        self.classes_ = unique_labels(y)
        self.N_ = len(y)
        self.pipeline_ = Pipeline(steps=[
            ('filter_rare_words', RemoveSparseFeatures(k=self.min_df)),
            ('tfidf', TfidfTransformer()),
            ('classifier', self.base_classifier)
        ])
        self.pipeline_.fit(X, y, classifier__sample_weight=sample_weight)
        return self

    def get_discriminating_stems_for_tag(self, slug: str, full_vocab_list: Sequence[str], n:int = 20) -> WordCloud:
        ret = WordCloud({
            "tag": slug,
            "versus": [str(tag) for tag in self.classes_ if tag != slug],
            "terms": [],
        })
        if len(self.classes_) > 2:
            coefs = self.base_classifier.coef_[list(self.classes_).index(slug)]
        elif slug == self.classes_[1]:
            coefs = self.base_classifier.coef_[0]
        else:
            coefs = np.negative(self.base_classifier.coef_[0])
        ws = self.pipeline_.named_steps['tfidf'].idf_
        ws = np.max(ws) - ws + np.log(self.min_df+1) # log of the true doc freq
        coefs = coefs * ws # weigh the coefficients by log of how common the term is
        # cannot do *= above as that would modify the actual classifier coef_
        top_indices = np.argsort(coefs)[-n:][::-1]
        filtered_vocab = self.pipeline_.named_steps['filter_rare_words'].get_feature_names_out(full_vocab_list)
        ret['terms'] = [
            term
            for term in filtered_vocab[top_indices]
        ]
        return ret

    def predict(self, X):
        check_is_fitted(self)
        X = check_array(X, accept_sparse=True)
        return self.pipeline_.predict(X)

class TagPredictor:
    """
    Loads a trained classifier from a pkl file and does Classification prediction tasks on text.

    Usage
    -------
    big_classifier = TagPredictor.load(DATA_DIRECTORY.joinpath('models/default.pkl'))
    tags = big_classifier.predict(['Introduction to Buddhism', 'How to Meditate: A Guide to Peace'])
    # tags should now ~= ['buddhism', 'meditation']
    """
    def __init__(
        self,
        vocabulary,
        classifiers: dict[str, ZeroLearningClassifier | OBUNodeClassifier],
    ) -> None:
        self.classes = list(classifiers.keys())
        self.classes.remove('root')
        self.classifiers_ = classifiers
        self.vectorizer_ = CountVectorizer(lowercase=False, vocabulary=vocabulary)
    
    def count_vectorize_texts(self, X, normalized=False) -> csr_matrix:
        if not normalized:
            X = list(map(normalize_text, X))
        res = self.vectorizer_.transform(X)
        assert isinstance(res, csr_matrix)
        return res
    
    def tfidf_vectorize_texts(self, X, normalized=False):
        """Use the root classifier's TFIDF to semantically vectorize an array of texts"""
        X = self.count_vectorize_texts(X, normalized)
        root_classifier = self.classifiers_['root']
        assert isinstance(root_classifier, OBUNodeClassifier)
        pipeline = root_classifier.pipeline_
        X = pipeline.named_steps['filter_rare_words'].transform(X)
        return pipeline.named_steps['tfidf'].transform(X)
    
    def predict(self, X, normalized=False) -> list[str]:
        """Given an array of (normalized?) strings, predict the topics"""
        X = self.count_vectorize_texts(X, normalized)
        prev_prediction = ['']*X.shape[0]
        curr_prediction = ['root']*X.shape[0]
        predicting = True
        while predicting:
            next_prediction = []
            predicting = False
            for i in range(X.shape[0]):
                if prev_prediction[i] == curr_prediction[i]:
                    next_prediction.append(curr_prediction[i])
                else:
                    predicting = True
                    next_prediction.append(self.classifiers_[curr_prediction[i]].predict(X[i,:])[0])
            prev_prediction = curr_prediction
            curr_prediction = next_prediction
        return curr_prediction

    def build_parent_map(self):
        self.parents_ = dict()
        for slug, classifier in self.classifiers_.items():
            if isinstance(classifier, ZeroLearningClassifier):
                continue
            assert isinstance(classifier, OBUNodeClassifier)
            for class_slug in classifier.classes_:
                if class_slug == slug:
                    continue
                self.parents_[class_slug] = slug

    def load_unstem_dict(self):
        if UNSTEMMING_DICT_PATH.exists():
            self.unstem_dict_ = joblib.load(UNSTEMMING_DICT_PATH)
        else:
            self.unstem_dict_ = dict()
    
    def unstem_terms(self, cloud:WordCloud):
        for i, stem in enumerate(cloud['terms']):
            cloud['terms'][i] = self.unstem_dict_.get(stem, stem)

    def get_discriminating_vocab_for_tag(self, slug: str, n:int = 20) -> dict[str, WordCloud | NoneType]:
        """
        
        Returns:
          {
            "parent": {
                "versus": ["other", "tags"],
                "terms": ["larvae", ...]
            },
            "children": None, # for leaf nodes, otherwise another WordCloud
          }
        """
        if not hasattr(self, "parents_"):
            self.build_parent_map()
        if not hasattr(self, "unstem_dict_"):
            self.load_unstem_dict()
        if not hasattr(self, "full_vocab_list_"):
            self.full_vocab_list_ = self.vectorizer_.get_feature_names_out()

        ret: dict[str, WordCloud | None] = dict()
        parent_slug = self.parents_.get(slug)
        if parent_slug and parent_slug in self.classifiers_:
            parent = self.classifiers_[parent_slug]
            assert isinstance(parent, OBUNodeClassifier)
            ret['parent'] = parent.get_discriminating_stems_for_tag(slug, self.full_vocab_list_, n)
            self.unstem_terms(ret['parent'])
        else:
            ret['parent'] = None

        children = self.classifiers_.get(slug)
        if children is None or isinstance(children, ZeroLearningClassifier):
            ret["children"] = None
        else:
            ret['children'] = children.get_discriminating_stems_for_tag(slug, self.full_vocab_list_, n)
            self.unstem_terms(ret['children'])
        return ret

    @classmethod
    @cache
    def load(cls, filepath: Path | str | None=None) -> "TagPredictor":
        """Loads a new instance of TagPredictor from the given save_as'ed .pkl file"""
        if not filepath:
            filepath = MODELS_DIRECTORY.joinpath('default.pkl')
        from sklearn.exceptions import InconsistentVersionWarning  # type: ignore
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
            vocabulary, classifiers = joblib.load(filepath)
        return cls(vocabulary, classifiers)
