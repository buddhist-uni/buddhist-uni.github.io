#!/bin/python3

# import argparse
from pathlib import Path
import json
import regex

from nltk.stem.snowball import SnowballStemmer
import numpy as np
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

STOP_WORDS = set(git_root_folder.joinpath('scripts/stop_words.txt').read_text().split('\n'))
STOP_WORDS.update([w.lower() for w in STOP_WORDS])
stemmer = SnowballStemmer('english')
STOP_WORDS.update([stemmer.stem(word) for word in STOP_WORDS])

def normalize_text(text: str) -> str:
    text = unidecode(text).lower()
    text = (
        stemmer.stem(word)
        for word in regex.split(r"[^a-z]+", text)
        if len(word) >= 4 and word not in STOP_WORDS
    )
    return ' '.join(text)


class RemoveSparseFeatures(BaseEstimator, TransformerMixin):
    def __init__(self, k=15):
        self.k = k

    def fit(self, X, y=None):
        self.num_features_in = X.shape[1]
        self.sparse_mask = np.where(np.sum(X != 0, axis=0) >= self.k)[1]
        self.num_features_out = self.sparse_mask.shape[0]
        return self

    def transform(self, X):
        if hasattr(self, 'sparse_mask'):
            return X[:, self.sparse_mask]
        else:
            raise ValueError("The transformer has not been fitted yet.")


class ZeroLearningClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, label=None):
        self.label = label
        self.classes_ = []
    def fit(self, X, y=None, sample_weight=None):
        if self.label is None and len(y) > 0:
            self.label = y[0]
            self.classes_ = [self.label]
        return self
    def predict(self, X):
        return np.full(shape=(X.shape[0],), fill_value=self.label)
    def explain_yourself(self, *args):
        return f"I'm a leaf node that always predicts '{self.label}'"

class OBUNodeClassifier(BaseEstimator, ClassifierMixin):
    """
    My custom sklearn classifier for making one step prediction
    
    It takes a base_classifier instance (Logit by default)
    and wraps it in a Pipeline that also does whatever last-minute
    feature selection and normalization we need.
    """
    def __init__(
        self,
        base_classifier:BaseEstimator=None,
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

    def predict(self, X):
        check_is_fitted(self)
        X = check_array(X, accept_sparse=True)
        return self.pipeline_.predict(X)

class TagPredictor:
    """
    Loads a trained classifier from a pkl file and does Classification prediction tasks on text.

    Usage
    -------
    big_classifier = OBUTopicClassifier.load(DATA_DIRECTORY.joinpath('models/default.pkl'))
    tags = big_classifier.predict(['Introduction to Buddhism', 'How to Meditate: A Guide to Peace'])
    # tags should now ~= ['buddhism', 'meditation']
    """
    def __init__(
        self,
        vocabulary,
        classifiers: dict[str, BaseEstimator],
    ) -> None:
        self.classifiers_ = classifiers
        self.vectorizer_ = CountVectorizer(lowercase=False, vocabulary=vocabulary)
    
    def predict(self, X, normalized=False) -> list[str]:
        """Given an array of (normalized?) strings, predict the topics"""
        if not normalized:
            X = list(map(normalize_text, X))
        X = self.vectorizer_.transform(X)
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

    @classmethod
    def load(cls, filepath: Path | str=None):
        """Loads a new instance of OBUTopicClassifier from the given save_as'ed .pkl file"""
        if not filepath:
            filepath = MODELS_DIRECTORY.joinpath('default.pkl')
        vocabulary, classifiers = joblib.load(filepath)
        return cls(vocabulary, classifiers)
