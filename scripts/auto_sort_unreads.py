#!/bin/python3

import regex
from functools import cache
import numpy as np
import gensim.downloader
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import SVC

from strutils import git_root_folder
import website

website.load()

@cache
def latent_model():
    # Use a 50-dimensional topic space trained on en.wikipedia
    # This model has a number of limitations, especially that it is En only
    # but, still, reducing the dimensionality to 50 should give us a nice
    # balance of expressiveness to learn on limited data
    return gensim.downloader.load("glove-wiki-gigaword-50")

simple_seps = regex.compile('[\W\s_]+')
STOP_WORDS = set(git_root_folder.joinpath('scripts/stop_words.txt').read_text().split('\n'))
STOP_WORDS.update([w.lower() for w in STOP_WORDS])
def simple_tokenize(s):
    ret = simple_seps.split(s)
    return [w for w in ret if not w.isnumeric() and w not in STOP_WORDS]

def tokenized_website_entries_for_tags(tags, categories=None):
    ret = {}
    tags = set(tags)
    for t in tags:
        ret[t] = []
        tag = website.tags.get(t)
        if tag:
            text = tag.title + " " + tag.content
            ret[t].append(simple_tokenize(text))
    for c in website.content:
        if categories and c.category not in categories:
            continue
        text = c.title + ' ' + c.content
        if c.course in tags:
            ret[c.course].append(simple_tokenize(text))
            continue
        if not c.tags:
            continue
        tags_intersection = tags & set(c.tags)
        if len(tags_intersection) == 1:
            ret[next(iter(tags_intersection))].append(simple_tokenize(text))
        # else not sure what to do. Add this title under multiple tags?
    return ret

def project_into_semantic_space(tokenized_titles_by_tag):
    x = []
    y = []
    for tag in tokenized_titles_by_tag:
        for title in tokenized_titles_by_tag[tag]:
            title_bag = [w.lower() for w in set(title)]
            try:
                vector = latent_model().get_mean_vector(title_bag)
            except ValueError:
                print("  Warning: Discarding a work with an empty (all-numeric?) title")
                continue
            if np.sum(np.square(vector)) == 0:
                print("  Warning: No embedding found for "+title_bag.__str__()+". Discarding this datapoint!")
                continue
            x.append(vector)
            y.append(tag)
    return (x, y)

def train_predictor_on_semantic_space(x, y):
    # For predictions in semantic spaces you want to use
    # a Support Vector Machine Classifier (or SVC for short)
    # as these are built to learn regions of vector spaces.
    # We've using the OvR Multiclass strategy here because:
    #   - Grouping the "rest" together leverages limited
    #     data better during training than One vs One Class.
    #   - It scales better to a large number of classes
    #   - It's easier to extract multiple class
    #     predictions (via model.decision_function(x) > 0)
    #
    # The theoretical advantage of OVR(SVC) was confirmed
    #   against kNN, Ridge, and LinearSVC via Cross
    #   Validation. In tests on our data, SVC variants
    #   always outperformed other models, with the OVR
    #   strat slightly outperforming Linear and OVO SVC.
    return OneVsRestClassifier(SVC(kernel='rbf')).fit(x,y)
