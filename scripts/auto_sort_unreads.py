#!/bin/python3

import argparse
import math
from pathlib import Path
import json
import regex
import random
import hashlib

import numpy as np
from numpy.typing import ArrayLike
from nltk.stem.snowball import SnowballStemmer
from scipy import sparse
from sklearn.feature_extraction.text import (
    TfidfTransformer,
    CountVectorizer,
)
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.base import (
    BaseEstimator,
    ClassifierMixin,
    TransformerMixin,
)
from sklearn.utils.validation import (
    check_X_y,
    check_is_fitted,
    check_array,
)
from sklearn.utils.multiclass import unique_labels
import joblib
from tqdm import tqdm
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from unidecode import unidecode

from strutils import (
    git_root_folder,
    prompt,
)
import website
from website import ContentFile
import gdrive
from pdfutils import readpdf
from epubutils import read_epub

DATA_DIRECTORY = Path('/media/khbh/Data/autosort/')
disk_memorizor = joblib.Memory(DATA_DIRECTORY.joinpath('.cache'))

website.load()
DRIVE_FOLDERS = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
PUBLIC_FOLDER_FOR_PRIVATE = {
    gdrive.folderlink_to_id(pair['private']): gdrive.folderlink_to_id(pair['public'])
    for pair in DRIVE_FOLDERS.values() if pair['private'] and pair['public']
}
SLUG_FOR_PRIVATE_FOLDERID = {
    gdrive.folderlink_to_id(DRIVE_FOLDERS[slug]['private']): slug
    for slug in DRIVE_FOLDERS if DRIVE_FOLDERS[slug]['private']
}
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

def get_all_trainable_drive_folders() -> dict[str,list[str]]:
    """Returns a dict mapping tag-like slug to the gdrive folder IDs to use for it.
    
    In the normal case, this will map, e.g.
        "buddha" => [<Buddha>, <Unread (Buddha)>, <Archive (Buddha)>]
    There will be ambiguous cases.
    These will be prompted for and the answers cached."""
    buddhism_folder = gdrive.folderlink_to_id(DRIVE_FOLDERS['buddhism']['private'])
    world_folder = gdrive.folderlink_to_id(DRIVE_FOLDERS['world']['private'])
    ret = _get_trainable_drive_folders(buddhism_folder, {})
    return _get_trainable_drive_folders(world_folder, ret)

ORGANIZATIONAL_SUBFOLDERS_FILE = DATA_DIRECTORY.joinpath('organizational_subfolders.json')
ORGANIZATIONAL_SUBFOLDERS = []
if ORGANIZATIONAL_SUBFOLDERS_FILE.exists():
    ORGANIZATIONAL_SUBFOLDERS = json.loads(ORGANIZATIONAL_SUBFOLDERS_FILE.read_text())
SUBFOLDERS_IGNORE_FILE = DATA_DIRECTORY.joinpath('ignored_subfolders.json')
IGNORE_SUBFOLDERS = []
if SUBFOLDERS_IGNORE_FILE.exists():
    IGNORE_SUBFOLDERS = json.loads(SUBFOLDERS_IGNORE_FILE.read_text())

def _get_trainable_drive_folders(this_folder:str, ret:dict[str,list[str]]) -> dict[str,list[str]]:
    slug = SLUG_FOR_PRIVATE_FOLDERID[this_folder]
    ret[slug] = [this_folder]
    subfolders = gdrive.get_subfolders(this_folder)
    for subfolder in subfolders:
        if subfolder['id'] in IGNORE_SUBFOLDERS:
            continue
        name = subfolder['name']
        if 'unread' in name.lower() or 'archive' in name.lower() or subfolder['id'] in ORGANIZATIONAL_SUBFOLDERS:
            ret[slug].append(subfolder['id'])
            continue
        if subfolder['id'] not in SLUG_FOR_PRIVATE_FOLDERID:
            print(f"Folder {slug}/\"{subfolder['name']}\" isn't in the hierarchy.")
            new_slug = input("Add it as slug (blank for no): ")
            if new_slug:
                public_folder = input("Public folder link: ").split('?')[0]
                gdrive.add_tracked_folder(new_slug, public_folder, gdrive.FOLDER_LINK_PREFIX+subfolder['id'])
                SLUG_FOR_PRIVATE_FOLDERID[subfolder['id']] = new_slug
            else:
                if prompt(f"Consider this folder a part of {slug}? (y=merge, n=ignore) "):
                    ORGANIZATIONAL_SUBFOLDERS.append(subfolder['id'])
                    ORGANIZATIONAL_SUBFOLDERS_FILE.write_text(json.dumps(ORGANIZATIONAL_SUBFOLDERS))
                    ret[slug].append(subfolder['id'])
                else:
                    IGNORE_SUBFOLDERS.append(subfolder['id'])
                    SUBFOLDERS_IGNORE_FILE.write_text(json.dumps(IGNORE_SUBFOLDERS))
                    ret[slug].append(subfolder['id'])
                continue
        ret = _get_trainable_drive_folders(subfolder['id'], ret)
    return ret

def get_drive_folder_heirarchy() -> dict[str, dict[str, list[str]]]:
    """returns a mapping from slug to {'ancestors': [], 'children': [], 'descendants': []}"""
    root_folder = gdrive.folderlink_to_id(DRIVE_FOLDERS['root']['private'])
    
    drive_map = dict()
    return _get_drive_folder_heirarchy(root_folder, [], drive_map)

def _get_drive_folder_heirarchy(this_folder_id:str, ancestors: list[str], drive_map: dict[str, dict]):
    this_folder = {
        'ancestors': ancestors,
        'children': [],
        'descendants': [],
    }
    drive_map[SLUG_FOR_PRIVATE_FOLDERID[this_folder_id]] = this_folder
    this_folder_slug = SLUG_FOR_PRIVATE_FOLDERID[this_folder_id]
    all_children = gdrive.get_subfolders(this_folder_id)
    for child_folder in all_children:
        child_id = child_folder['id']
        child_slug = SLUG_FOR_PRIVATE_FOLDERID.get(child_id)
        if not child_slug:
            continue
        this_folder['children'].append(child_slug)
        this_folder['descendants'].append(child_slug)
        for daddy in ancestors:
            drive_map[daddy]['descendants'].append(child_slug)
        drive_map = _get_drive_folder_heirarchy(
            child_id,
            ancestors+[this_folder_slug],
            drive_map,
        )
    return drive_map

FILE_FIELDS = 'id,name,shortcutDetails,size,mimeType,properties'
TRAINABLE_MIMETYPES = set([
    'application/pdf',
    'application/epub+zip',
    'application/vnd.google-apps.document',
])

def get_all_trainable_files_in_folders(trainable_folders, verbose=False) -> list[dict]:
    """Cached list of PDFs in folders (follows file links)

    Args:
        trainable_folders: either a dict of lists or a flat list of folders
    
    Returns: a list of Google Drive JSON objects
    """
    ret = []
    if isinstance(trainable_folders, dict):
        if isinstance(next(iter(trainable_folders.values())), list):
            trainable_folders = [item for sublist in trainable_folders.values() for item in sublist]
        else:
            trainable_folders = list(trainable_folders.values())
    wrapper = lambda a: a
    print("Getting all trainable files from drive...")
    if not verbose:
        wrapper = tqdm
    for folderid in wrapper(trainable_folders):
        files = _get_trainable_files_in_folder(folderid, verbose)
        for file in files:
            file['size'] = int(file.get('size', 0))
            file['parent'] = folderid
        ret.extend(files)
    return ret

@disk_memorizor.cache(
    cache_validation_callback=joblib.expires_after(days=14),
    ignore=['verbose'],
    verbose=0,
)
def _get_trainable_files_in_folder(folderid, verbose):
    ret = []
    if verbose:
        print(f"Finding trainable files in {folderid}...")
        f_t = 0
    query = " and ".join([
        f"'{folderid}' in parents",
        "("+" or ".join([
            f"mimeType='{t}'" for t in
            TRAINABLE_MIMETYPES | set(['application/vnd.google-apps.shortcut'])
        ])+")",
        "trashed=false",
    ])
    shortcutIds = set()
    for file in gdrive.all_files_matching(query, FILE_FIELDS):
        if file['mimeType'] in TRAINABLE_MIMETYPES:
            ret.append(file)
            if verbose:
                f_t += 1
        elif file['mimeType'] == 'application/vnd.google-apps.shortcut':
            if file['shortcutDetails']['targetMimeType'] in TRAINABLE_MIMETYPES:
                shortcutIds.add(file['shortcutDetails']['targetId'])
        else:
            raise TypeError(f"GDrive returned a file of unexpected mimeType {file['mimeType']}")
    if verbose:
        print(f"  Found {f_t} files directly in the folder")
        print(f"  and {len(shortcutIds)} shortcuts")
        f_t = 0
    if len(shortcutIds) == 0:
        return ret
    publicfolder = PUBLIC_FOLDER_FOR_PRIVATE.get(folderid)
    if publicfolder:
        if verbose:
            print("  Looking for the shortcut targets in the public folder...")
        query = " and ".join([
            f"'{publicfolder}' in parents",
            "("+" or ".join([
                f"mimeType='{t}'"
                for t in TRAINABLE_MIMETYPES
            ])+")",
        ])
        for file in gdrive.all_files_matching(query, FILE_FIELDS):
            if file['id'] in shortcutIds:
                shortcutIds.remove(file['id'])
                ret.append(file)
                if verbose:
                    f_t += 1
        if verbose:
            print(f"  Found {f_t} targets there")
    elif verbose:
        print("  no public folder known to check for the shortcuts")
    if verbose:
        print(f"  Had to load {len(shortcutIds)} targets individually")
    return ret + gdrive.batch_get_files_by_id(list(shortcutIds), FILE_FIELDS)

def get_folder_to_tag_mapping(trainable_folders=None):
    """Given a parent id, what tag does this file belong to?"""
    if not trainable_folders:
        trainable_folders = get_all_trainable_drive_folders()
    return {
        folder: tag
        for tag in trainable_folders.keys()
        for folder in trainable_folders[tag]
    }

@disk_memorizor.cache(
    cache_validation_callback=joblib.expires_after(days=14),
    verbose=0,
)
def get_trainable_gfiles_from_site():
    exclude = get_all_trainable_files_in_folders(get_all_trainable_drive_folders())
    exclude = {f['id'] for f in exclude}
    additionals = []
    for content in website.content:
        if content.category == 'av':
            continue
        dlinks = content.get('drive_links', [])
        for i in range(len(dlinks)):
            dlink = dlinks[i]
            format = content.formats[i]
            if format not in ['epub', 'pdf']:
                continue
            gid = gdrive.link_to_id(dlink)
            if gid and gid not in exclude:
                additionals.append(gid)
    print(f"Fetching {len(additionals)} addition Google Files from the webiste...")
    additionals = gdrive.batch_get_files_by_id(additionals, FILE_FIELDS)
    ret = []
    for f in additionals:
        if f['mimeType'] not in TRAINABLE_MIMETYPES:
            continue
        f['size'] = int(f['size'])
        f['parent'] = '1Ih3PRUKLHaWzVvoVVkCRuaCzbsjreQXa'
        ret.append(f)
    return ret


PDF_TEXT_FOLDER = DATA_DIRECTORY.joinpath('rawpdftext')
if not PDF_TEXT_FOLDER.exists():
    PDF_TEXT_FOLDER.mkdir()
EPUB_TEXT_FOLDER = DATA_DIRECTORY.joinpath('rawepubtext')
if not EPUB_TEXT_FOLDER.exists():
    EPUB_TEXT_FOLDER.mkdir()
NORMALIZED_TEXT_FOLDER = DATA_DIRECTORY.joinpath('normalized_drive_text')
if not NORMALIZED_TEXT_FOLDER.exists():
    NORMALIZED_TEXT_FOLDER.mkdir()

def save_pdf_text_for_drive_file(drivefile: dict, overwrite=False, in_memory_filesize_limit=50000000):
    _save_text_for_drive_file(
        drivefile,
        overwrite,
        in_memory_filesize_limit,
        PDF_TEXT_FOLDER,
        'pdf',
        readpdf,
    )

def save_epub_text_for_drive_file(drivefile: dict, overwrite=False):
    _save_text_for_drive_file(
        drivefile,
        overwrite,
        0,
        EPUB_TEXT_FOLDER,
        'epub',
        read_epub,
    )

def _save_text_for_drive_file(
    drivefile: dict,
    overwrite: bool,
    in_memory_filesize_limit: int,
    text_folder: Path,
    extension: str,
    reader_func: callable,
):
    name = f"{drivefile['id']}.txt"
    incompletenormalizedtextfile = NORMALIZED_TEXT_FOLDER.joinpath(f"{name}.incomplete")
    completenormalizedtextfile = NORMALIZED_TEXT_FOLDER.joinpath(name)
    incompleterawtextfile = text_folder.joinpath(f"{name}.incomplete")
    completerawtextfile = text_folder.joinpath(name)
    if (not overwrite) and completenormalizedtextfile.exists():
        return
    try:
        if not completerawtextfile.exists():
            name = f"{drivefile['id']}.{extension}"
            incomplete_orig_file = text_folder.joinpath(f"{name}.incomplete")
            complete_orig_file = text_folder.joinpath(name)
            pdffile = None
            if not complete_orig_file.exists():
                if int(drivefile['size']) < in_memory_filesize_limit:
                    pdffile = gdrive.get_file_contents(drivefile['id'], verbose=False)
                else:
                    gdrive.download_file(drivefile['id'], incomplete_orig_file, verbose=False)
                    incomplete_orig_file.rename(complete_orig_file)
            if not pdffile:
                pdffile = complete_orig_file
            incompleterawtextfile.write_text(reader_func(pdffile))
            incompleterawtextfile.rename(completerawtextfile)
        incompletenormalizedtextfile.write_text(normalize_text(completerawtextfile.read_text()))
        incompletenormalizedtextfile.replace(completenormalizedtextfile)
    except Exception as e:
        print(f"Warning! There was an error downloading and parsing {drivefile['id']}:")
        print(e)
        completenormalizedtextfile.touch() # mark as no data

def save_all_drive_texts(parallelism=6, sample_size=None, min_size=0, max_size=150000000, folders=None, all_files=None):
    """If sample_size is None, goes from smaller to larger files,
    otherwise a random sample is chosen
    
    If this task is interupted, simply `rm *.incomplete`
    """
    if not folders:
        folders = get_all_trainable_drive_folders()
    if not all_files:
        all_files = get_all_trainable_files_in_folders(folders)
        all_files += get_trainable_gfiles_from_site()
    all_files = [
        file for file in all_files if
        file['mimeType'] in ['application/pdf', 'application/epub+zip'] and
        file['size'] <= max_size and
        file['size'] >= min_size and
        (not NORMALIZED_TEXT_FOLDER.joinpath(f"{file['id']}.txt").exists())
    ]
    if len(all_files) == 0:
        return
    if sample_size and sample_size<len(all_files):
        all_files = random.sample(all_files, sample_size)
    else:
        random.shuffle(all_files)
    pdf_files = [file for file in all_files if file['mimeType'] == 'application/pdf']
    epub_files = [file for file in all_files if file['mimeType'] == 'application/epub+zip']
    del all_files
    if len(pdf_files) > 0:
        print(f"Downloading {len(pdf_files)} pdfs and extracting their text...")
        tqdm_process_map(
            save_pdf_text_for_drive_file,
            pdf_files,
            max_workers=parallelism,
        )
    if len(epub_files) > 0:
        print(f"Downloading {len(epub_files)} epubs and extracting their text...")
        tqdm_process_map(
            save_epub_text_for_drive_file,
            epub_files,
            max_workers=parallelism,
        )


class DataPoint():
    def __init__(
        self,
        title=None,
        content=None,
        tag=None,
        confidence=1.0,
    ) -> None:
        self.title = title or ''
        self.content = content or ''
        self.tag = tag
        self.confidence = confidence
    def get_normalized_title(self):
        return self.title
    def get_normalized_content(self):
        if not self.content:
            return ''
        return self.content + 4 * (' ' + self.title)
    def get_tag(self):
        return self.tag
    def get_confidence(self):
        return self.confidence
    def set_title_vector(self, title_vector):
        self.title_vector = title_vector
    def set_content_vector(self, content_vector):
        self.content_vector = content_vector
    def get_title_vector(self):
        return self.title_vector
    def get_content_vector(self):
        return self.content_vector

class DataSource:
    def __init__(self) -> None:
        self.data = []
        self.folders = get_all_trainable_drive_folders()
    
    def load_data(self):
        raise NotImplementedError()

    def get_all_datapoints(self) -> list[DataPoint]:
        if not self.data:
           self.load_data()
        return self.data

    def tags_for_wc(self, wc: ContentFile) -> list[tuple]:
        if wc.course in self.folders:
            tags = [(wc.course, 2.5)]
        else:
            tags = []
        for t in wc.get('tags',[]):
            if t in self.folders:
                tags.append((t, 1))
        return tags

    def add_datapoints(self, title: str, content: str, tags: list[tuple], confidence=1.0, normalize=True):
        if len(tags) == 0 or not (title or content):
            return
        weight = sum([t[1] for t in tags])
        if weight * confidence <= 0:
            return
        weight = confidence / weight
        if normalize:
            title = normalize_text(title)
            content = normalize_text(content)
        for tag in tags:
            self.data.append(
                DataPoint(
                    title=title,
                    content=content,
                    tag=tag[0],
                    confidence=weight*tag[1],
                )
            )

class WebsiteDataSource(DataSource):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    def load_data(self):
        print("Loading website DataPoints...")
        for tag in tqdm(website.tags):
            self.add_datapoints(
                title=tag.content + (" " + tag.title) * 4,
                content='',
                tags=[tag.slug],
                confidence=10,
            )
        for wc in tqdm(website.content):
            self.add_datapoints(
                title=wc.title,
                content=wc.content,
                tags=self.tags_for_wc(wc),
            )

class GoogleDriveFilesDataSource(DataSource):
    def __init__(
        self,
        unread_confidence=0.2,
        use_site_tags=True,
        download_threads=6,
        download_max_size=3000000,
    ) -> None:
        super().__init__()
        self.use_site_tags = use_site_tags
        self.unread_confidence = unread_confidence
        self.download_max_size = download_max_size
        self.download_threads = download_threads

    def load_data(self):
        tag_for_folder = get_folder_to_tag_mapping(trainable_folders=self.folders)
        all_files = get_all_trainable_files_in_folders(self.folders)
        content_for_gdid = {}
        if self.use_site_tags:
            all_files += get_trainable_gfiles_from_site()
            content_for_gdid = {
                gdrive.link_to_id(link): content
                for content in website.content
                for link in content.get('drive_links',[])
            }
        save_all_drive_texts(
            folders=self.folders,
            all_files=all_files,
            max_size=self.download_max_size,
            parallelism=self.download_threads,
        )
        print("Building Google Drive DataPoints...")
        for file in tqdm(all_files):
            content = ''
            if file['id'] in content_for_gdid:
                wc = content_for_gdid[file['id']]
                tags = self.tags_for_wc(wc)
            else:
                tags = [(tag_for_folder[file['parent']], 1)]
            if not tags:
                continue
            fp = NORMALIZED_TEXT_FOLDER.joinpath(f"{file['id']}.txt")
            if fp.exists():
                content = fp.read_text()
            title = normalize_text(file['name'])
            self.add_datapoints(
                title,
                content,
                tags,
                confidence=1.0 \
                    if self.folders[tags[0][0]][0] == file['parent'] \
                    else self.unread_confidence,
                normalize=False,
            )

"""BEGIN SKLEARN CODE"""

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
    def fit(self, X, y=None, sample_weight=None):
        if self.label is None and y:
            self.label = y[0]
        self.classes_ = [self.label]
        return self
    def predict(self, X):
        return np.full(shape=(X.shape[0],), fill_value=self.label)

class OBUNodeClassifier(BaseEstimator, ClassifierMixin):
    """My custom sklearn classifier for making one step prediction"""
    def __init__(
        self,
        classifierclass=LogisticRegression,
        min_df=15,
    ) -> None:
        super().__init__()
        self.min_df = min_df
        self.classifierclass = classifierclass

    def fit(self, X, y, sample_weight=None):
        X, y = check_X_y(X, y, accept_sparse=True)
        self.classes_ = unique_labels(y)
        self.pipeline_ = Pipeline(steps=[
            ('filter_rare_words', RemoveSparseFeatures(k=self.min_df)),
            ('tfidf', TfidfTransformer()),
            ('classifier', self.classifierclass())
        ])
        self.pipeline_.fit(X, y, classifier__sample_weight=sample_weight)
        return self

    def predict(self, X):
        check_is_fitted(self)
        X = check_array(X, accept_sparse=True)
        return self.pipeline_.predict(X)        

def build_vectorizer(X_raw: list[str], stop_words: list[str], min_df: int) -> CountVectorizer:
    hasher = hashlib.md5(usedforsecurity=False)
    for s in X_raw:
        hasher.update(s.encode())
    for s in stop_words:
        hasher.update(s.encode())
    hasher.update(str(min_df).encode())
    hashval = hasher.hexdigest()
    vocabfile = DATA_DIRECTORY.joinpath('vocab_cache')
    vocabfile.mkdir(exist_ok=True)
    vocabfile = vocabfile.joinpath(hashval+'.pkl')
    if vocabfile.exists():
        print("  CountVectorizer cache hit")
        return CountVectorizer(
            lowercase=False,
            vocabulary=joblib.load(vocabfile),
        )
    print("  CountVectorizer cache miss (loading)...")
    ret = CountVectorizer(
        lowercase=False, # already lowered
        stop_words=stop_words,
        min_df=min_df,
    )
    ret.fit(X_raw)
    joblib.dump(ret.vocabulary_, vocabfile, compress=2)
    return ret

class OBUTopicClassifier:
    """Class for bridging my world and the sklearn world"""
    def __init__(
        self,
        data_sources: list[DataSource],
        min_df=15, # filter vocab rarer than this
        min_points: int = 50, # tags with less than this many data points will be filtered out
    ) -> None:
        self.data_sources = data_sources
        self.min_points = min_points
        self.min_df = min_df
    
    def train(self):
        """The big main function"""
        self._load_data()
        self._count_words()
        print("Making the folder heirarchy...")
        self.drive_map = get_drive_folder_heirarchy()
        to_train = ['root']
        self.classifiers_ = dict()
        while len(to_train) > 0:
          slug = to_train.pop()
          if slug in self.classifiers_:
            continue
          classifier = self.train_node(slug)
          self.classifiers_[slug] = classifier
          to_train.extend(list(classifier.classes_))
        return self

    def _load_data(self):
        self.all_the_data_ = []
        for datasource in self.data_sources:
            self.all_the_data_.extend(datasource.get_all_datapoints())
        print("Sorting the datapoints...")
        self.all_the_data_.sort(key=lambda a: a.get_normalized_content())
    
    def _count_words(self):
        print("Counting all the words across the entire dataset...")
        X_raw = []
        for datapoint in self.all_the_data_:
            X_raw.append(datapoint.get_normalized_title())
            X_raw.append(datapoint.get_normalized_content())
        self.vectorizer_ = build_vectorizer(
            X_raw,
            sorted([w for w in STOP_WORDS if w]),
            self.min_df,
        )
        X_raw = self.vectorizer_.transform(X_raw)
        for i in range(0, int(X_raw.shape[0]), 2):
            t_v, c_v = X_raw[i:i+2]
            self.all_the_data_[int(i/2)].set_title_vector(t_v)
            self.all_the_data_[int(i/2)].set_content_vector(c_v)

    def _training_data_from_datapoints(
        self,
        data_points,
    ) -> tuple[list]:
        """Returns (X, w) from a list of DataPoints"""
        x = []
        w = []
        for datapoint in data_points:
            title = datapoint.get_title_vector()
            content = datapoint.get_content_vector()
            confidence = datapoint.get_confidence()
            if title.nnz > 0:
                x.append(title)
                w.append(confidence * math.log(1+title.nnz))
            if content.nnz > 0:
                x.append(content)
                w.append(confidence * math.log(1+content.nnz))
        return (x, w)

    def train_node(self, tag:str) -> BaseEstimator:
        print(f"Training '{tag}' classifier...")
        relevant_tags = set([tag] + self.drive_map[tag]['ancestors'])
        X, w = self._training_data_from_datapoints(
            (dp for dp in self.all_the_data_ if dp.get_tag() in relevant_tags)
        )
        y = [tag] * len(w)
        child_count = 0
        for child in self.drive_map[tag]['children']:
            relevant_tags = set([child] + self.drive_map[child]['descendants'])
            child_X, child_w = self._training_data_from_datapoints(
                (dp for dp in self.all_the_data_ if dp.get_tag() in relevant_tags)
            )
            X.extend(child_X)
            w.extend(child_w)
            if len(child_w) >= self.min_points:
                y.extend([child] * len(child_w))
                child_count += 1
            else:
                y.extend([tag] * len(child_w))
        if child_count > 0:
            node_classifier = OBUNodeClassifier(min_df=self.min_df)
        else:
            node_classifier = ZeroLearningClassifier(label=tag)
        X = sparse.vstack(X)
        return node_classifier.fit(X, y, sample_weight=w)

    def predict(self, X, normalized=False) -> ArrayLike:
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

if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        prog="python3 auto_sort_unreads.py",
    )
    argument_parser.parse_args()
    # TODO
    big_classifier = OBUTopicClassifier(data_sources=[GoogleDriveFilesDataSource()]).train()
