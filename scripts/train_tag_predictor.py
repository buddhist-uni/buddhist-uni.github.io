#!/bin/python3

import argparse
import math
from pathlib import Path
import json
import random
import hashlib
from functools import cache
from textwrap import dedent

import numpy as np
from numpy.typing import ArrayLike
from scipy import sparse
from sklearn.feature_extraction.text import (
    CountVectorizer,
)
from sklearn.svm import LinearSVC
from sklearn.base import BaseEstimator

import joblib
from tqdm import tqdm, trange
from tqdm.contrib.concurrent import process_map as tqdm_process_map
from unidecode import unidecode

from strutils import (
    prompt,
)
import website
from website import ContentFile
import gdrive_base
import gdrive
from pdfutils import readpdf
from epubutils import read_epub
import tag_predictor
from tag_predictor import (
    normalize_text,
    save_normalized_text,
    DATA_DIRECTORY,
    NORMALIZED_TEXT_FOLDER,
    NORMALIZED_DRIVE_FOLDER,
    MODELS_DIRECTORY,
    TagPredictor,
    STOP_WORDS,
    flatten_youtube_metadata,
    flatten_youtube_transcript,
    get_normalized_text_for_youtube_vid,
    md_stripper,
    get_ytdata_for_ids,
)

disk_memorizor = joblib.Memory(DATA_DIRECTORY.joinpath('.cache'))

DRIVE_FOLDERS = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
PUBLIC_FOLDER_FOR_PRIVATE = {
    gdrive_base.folderlink_to_id(pair['private']): gdrive_base.folderlink_to_id(pair['public'])
    for pair in DRIVE_FOLDERS.values() if pair['private'] and pair['public']
}
SLUG_FOR_PRIVATE_FOLDERID = {
    gdrive_base.folderlink_to_id(DRIVE_FOLDERS[slug]['private']): slug
    for slug in DRIVE_FOLDERS if DRIVE_FOLDERS[slug]['private']
}
CANON_TAGS = set(['an', 'sn', 'mn', 'dn', 'dhp', 'snp', 'khp', 'ea', 'da', 'ma', 'sa', 'ud', 'iti', 'snp', 'thag', 'thig'])

COURSE_TAG_WEIGHT = 2.5

@cache
def get_all_trainable_drive_folders() -> dict[str,list[str]]:
    """Returns a dict mapping tag-like slug to the gdrive folder IDs to use for it.
    
    In the normal case, this will map, e.g.
        "buddha" => [<Buddha>, <Unread (Buddha)>, <Archive (Buddha)>]
    There will be ambiguous cases.
    These will be prompted for and the answers cached."""
    buddhism_folder = gdrive_base.folderlink_to_id(DRIVE_FOLDERS['buddhism']['private'])
    world_folder = gdrive_base.folderlink_to_id(DRIVE_FOLDERS['world']['private'])
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
RUN_RECENTLY = True

def _get_trainable_drive_folders(this_folder:str, ret:dict[str,list[str]]) -> dict[str,list[str]]:
    slug = SLUG_FOR_PRIVATE_FOLDERID[this_folder]
    ret[slug] = [this_folder]
    subfolders = gdrive.gcache.get_subfolders(this_folder, include_shortcuts=False)
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
                gdrive.add_tracked_folder(new_slug, public_folder, gdrive_base.FOLDER_LINK_PREFIX+subfolder['id'])
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

@cache
def get_drive_folder_heirarchy() -> dict[str, dict[str, list[str]]]:
    """returns a mapping from slug to {'ancestors': [], 'children': [], 'descendants': []}"""
    root_folder = gdrive_base.folderlink_to_id(DRIVE_FOLDERS['root']['private'])
    
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
    all_children = gdrive.gcache.get_subfolders(this_folder_id, include_shortcuts=False)
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

@cache
def get_all_trainable_files_in_folders(verbose=False) -> list[dict]:
    """Cached list of PDFs in folders (follows file links)

    Args:
        trainable_folders: either a dict of lists or a flat list of folders
    
    Returns: a list of Google Drive JSON objects
    """
    ret = []
    trainable_folders = get_all_trainable_drive_folders()
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
    query = " AND ".join([
        f"parent_id='{folderid}'",
        "("+" OR ".join([
            f"mime_type='{t}'" for t in
            TRAINABLE_MIMETYPES
        ])+")",
    ])
    shortcutIds = set()
    for file in gdrive.gcache.sql_query(query, tuple()):
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
        query = " AND ".join([
            f"parent_id='{publicfolder}'",
            "("+" OR ".join([
                f"mime_type='{t}'"
                for t in TRAINABLE_MIMETYPES
            ])+")",
        ])
        for file in gdrive.gcache.sql_query(query, tuple()):
            if file['mimeType'] == 'application/vnd.google-apps.shortcut':
                shortcutIds.add(file['shortcutDetails']['targetId'])
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
    return ret + gdrive.gcache.get_items(list(shortcutIds))

def get_folder_to_tag_mapping():
    """Given a parent id, what tag does this file belong to?"""
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
    exclude = get_all_trainable_files_in_folders()
    website.load()
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
            gid = gdrive_base.link_to_id(dlink)
            if gid and gid not in exclude:
                additionals.append(gid)
    print(f"Fetching {len(additionals)} addition Google Files from the webiste...")
    additionals = gdrive.gcache.get_items(additionals)
    ret = []
    for f in additionals:
        if f['mimeType'] not in TRAINABLE_MIMETYPES:
            continue
        f['size'] = int(f['size'])
        f['parent'] = '1Hb3_iSK9ISvY9BbSM-gkjWgKF3eVkiLi'
        ret.append(f)
    return ret

def extract_all_youtube_ids(all_the_google_drive_files:list[dict]=None, tag_for_folder:dict=None) -> dict[str, list[tuple[str,float|int]]]:
    """The eponomous ids are the keys of the returned dict, the values are the tag tuples as needed by the YouTubeDataSource"""
    ret = dict() # mapping id to tags
    website.load()
    for content in website.content:
        if not (content.external_url and 'youtu' in content.external_url):
            continue
        if 'list' in content.external_url:
            continue # TODO handle playlistst?
        ytid = gdrive.yt_url_to_id_re.search(content.external_url)
        if not ytid:
            continue
        ytid = ytid.groups()[0]
        tags = []
        if content.course:
            tags.append((content.course, COURSE_TAG_WEIGHT))
        if content.tags:
            tags.extend(((t,1) for t in content.tags))
        if ytid in ret:
            raise RuntimeError("Duplicate YTID Found in website: " + ytid)
        ret[ytid] = tags
    if all_the_google_drive_files and tag_for_folder:
        for file in all_the_google_drive_files:
            props = file.get('properties')
            if not props:
                continue
            url = props.get('url')
            if not url:
                continue
            ytid = gdrive.yt_url_to_id_re.search(url)
            if not ytid:
                continue
            ytid = ytid.groups()[0]
            if ytid in ret:
                continue
            tag = tag_for_folder.get(file['parent'])
            ret[ytid] = [(tag, 1)]
    elif all_the_google_drive_files or tag_for_folder:
        raise ValueError("Please supply both files and tagmap to extract YTIDs")
    return ret

PDF_TEXT_FOLDER = DATA_DIRECTORY.joinpath('rawpdftext')
if not PDF_TEXT_FOLDER.exists():
    PDF_TEXT_FOLDER.mkdir()
EPUB_TEXT_FOLDER = DATA_DIRECTORY.joinpath('rawepubtext')
if not EPUB_TEXT_FOLDER.exists():
    EPUB_TEXT_FOLDER.mkdir()

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
    incompleterawtextfile = text_folder.joinpath(f"{name}.incomplete")
    completerawtextfile = text_folder.joinpath(name)
    normalizedtextfile = NORMALIZED_TEXT_FOLDER.joinpath(f"{drivefile['id']}.pkl")
    if (not overwrite) and normalizedtextfile.exists():
        return
    try:
        if not completerawtextfile.exists():
            orig_file = text_folder.joinpath(f"{drivefile['id']}.{extension}")
            pdffile = None
            if not orig_file.exists():
                if int(drivefile['size']) < in_memory_filesize_limit:
                    pdffile = gdrive_base.get_file_contents(drivefile['id'], verbose=False)
                else:
                    gdrive_base.download_file(drivefile['id'], orig_file, verbose=False)
            if not pdffile:
                pdffile = orig_file
            incompleterawtextfile.write_text(reader_func(pdffile))
            incompleterawtextfile.rename(completerawtextfile)
        text = normalize_text(completerawtextfile.read_text())
        save_normalized_text(drivefile['id'], text)
    except Exception as e:
        print(f"Warning! There was an error downloading and parsing {drivefile['id']}:")
        print(e)
        normalizedtextfile.write_bytes(b'\x80\x04N.') # mark as no data

def save_all_drive_texts(parallelism=6, sample_size=None, min_size=0, max_size=150000000, all_files=None):
    """If sample_size is None, goes from smaller to larger files,
    otherwise a random sample is chosen
    
    If this task is interupted, please `rm *.incomplete`
    """
    if not all_files:
        all_files = get_all_trainable_files_in_folders()
        all_files += get_trainable_gfiles_from_site()
    # restore the cache from Google Drive first
    gdrive.download_folder_contents_to(NORMALIZED_DRIVE_FOLDER, NORMALIZED_TEXT_FOLDER, parallelism=parallelism)
    all_files = [
        file for file in all_files if
        file['mimeType'] in ['application/pdf', 'application/epub+zip'] and
        file['size'] <= max_size and
        file['size'] >= min_size and
        (not NORMALIZED_TEXT_FOLDER.joinpath(f"{file['id']}.pkl").exists())
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
            chunksize=4,
        )
    if len(epub_files) > 0:
        print(f"Downloading {len(epub_files)} epubs and extracting their text...")
        tqdm_process_map(
            save_epub_text_for_drive_file,
            epub_files,
            max_workers=parallelism,
            chunksize=4,
        )


class DataPoint():
    def __init__(
        self,
        title=None,
        content=None,
        tag=None,
        confidence=1.0,
        title_weight=4,
    ) -> None:
        self.title = title or ''
        self.content = content or ''
        self.tag = tag
        self.confidence = confidence
        self.title_weight = int(title_weight)
    def get_normalized_title(self):
        return self.title
    def get_normalized_content(self):
        if not self.content:
            return ''
        return self.content + self.title_weight * (' ' + self.title)
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
            tags = [(wc.course, COURSE_TAG_WEIGHT)]
        else:
            tags = []
        for t in wc.get('tags',[]):
            if wc.category == "canon" and t in CANON_TAGS:
                continue
            if t in self.folders:
                tags.append((t, 1))
        return tags

    def add_datapoints(self, title: str, content: str, tags: list[tuple], confidence=1.0, normalize=True, title_weight=4):
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
                    title_weight=title_weight,
                )
            )

class WebsiteDataSource(DataSource):
    def __init__(
        self,
    ) -> None:
        super().__init__()

    def load_data(self):
        print("Loading website tags...")
        website.load()
        for tag in tqdm(website.tags):
            self.add_datapoints(
                title=md_stripper(tag.content) + (" " + tag.title) * 4,
                content='',
                tags=[(tag.slug, 1)],
                confidence=10,
            )
        print("Loading website content...")
        for wc in tqdm(website.content):
            content = md_stripper(wc.content)
            if wc.category == 'canon':
                self.add_datapoints(
                    title=wc.title + ' ' + content,
                    content='',
                    tags=self.tags_for_wc(wc),
                )
            else:
                self.add_datapoints(
                    title=wc.title,
                    content=content,
                    tags=self.tags_for_wc(wc),
                )

class YouTubeDataSource(DataSource):
    def __init__(self) -> None:
        super().__init__()
    
    def load_data(self):
        ytids = extract_all_youtube_ids(
            get_all_trainable_files_in_folders(),
            self.folders
        )
        ytvideos = get_ytdata_for_ids(ytids)
        print("Loading YouTube DataPoints...")
        for vid in tqdm(ytvideos):
            self.add_datapoints(
                title=flatten_youtube_metadata(vid),
                content=flatten_youtube_transcript(vid['transcript']) if isinstance(vid['transcript'], list) else '',
                tags=ytids[vid['id']],
                title_weight=1,
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
        website.load()
        tag_for_folder = get_folder_to_tag_mapping()
        all_files = get_all_trainable_files_in_folders()
        content_for_gdid = {}
        if self.use_site_tags:
            all_files += get_trainable_gfiles_from_site()
            content_for_gdid = {
                gdrive_base.link_to_id(link): content
                for content in website.content
                for link in content.get('drive_links',[])
            }
        save_all_drive_texts(
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
            fp = NORMALIZED_TEXT_FOLDER.joinpath(f"{file['id']}.pkl")
            if fp.exists():
                content = joblib.load(fp)
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

class TqdmCountVectorizer(CountVectorizer):
    def _count_vocab(self, raw_documents, fixed_vocab):
        return super()._count_vocab(
            tqdm(raw_documents),
            fixed_vocab,
        )

def build_vectorizer(X_raw: list[str], stop_words: list[str], min_df: int) -> tuple[CountVectorizer, ArrayLike]:
    print("  Hashing the input data...")
    hasher = hashlib.md5(usedforsecurity=False)
    for s in tqdm(X_raw + stop_words):
        hasher.update(s.encode())
    hasher.update(str(min_df).encode())
    hashval = hasher.hexdigest()
    vocabfile = DATA_DIRECTORY.joinpath('vocab_cache')
    vocabfile.mkdir(exist_ok=True)
    X_file = vocabfile.joinpath(hashval+'.X_raw.pkl')
    vocabfile = vocabfile.joinpath(hashval+'.vocab.pkl')
    if vocabfile.exists():
        print("  CountVectorizer cache hit")
        vocab = joblib.load(vocabfile)
        ret = CountVectorizer(
            lowercase=False,
            vocabulary=vocab,
        )
        ret.transform([]) # prime the pump
        if X_file.exists():
            return (ret, joblib.load(X_file))
        print("  But transform miss :/ (Loading...)")
        procer = TqdmCountVectorizer(
            lowercase=False,
            vocabulary=vocab,
        )
        X_raw = procer.transform(X_raw)
        joblib.dump(X_raw, X_file, compress=4)
        return (ret, X_raw)
    print("  CountVectorizer cache miss (loading)...")
    if not RUN_RECENTLY:
        for fp in DATA_DIRECTORY.joinpath('vocab_cache').glob("*.pkl"):
            fp.unlink()
    ret = TqdmCountVectorizer(
        lowercase=False, # already lowered
        stop_words=stop_words,
        min_df=min_df,
    )
    X_raw = ret.fit_transform(X_raw)
    print("  Computed. Saving to disk...")
    joblib.dump(ret.vocabulary_, vocabfile, compress=2)
    joblib.dump(X_raw, X_file, compress=4)
    ret = CountVectorizer(lowercase=False, vocabulary=ret.vocabulary_)
    ret.transform([]) # prime the pump
    return (
        ret,
        X_raw,
    )

class OBUTopicClassifier:
    """
    Given a list of DataSources, learns a mapping from arbitrary strings to topic slugs.
    This is useful for automatically sorting unseen items into appropriate Unread folders.

    Usage
    -------
    classifier = OBUTopicClassifier(WebsiteDataSource())
    classifier.train()
    model_fp = MODELS_DIRECTORY.joinpath('small.pkl')
    classifier.save_as(model_fp)
    predictor = TagPredictor.load(model_fp)
    # Or can pass the data directly via:
    predictor = TagPredictor(classifier.vectorizer_.vocabulary_, classifier.classifiers_)
    predictions = predictor.predict(['Introduction to Buddhism', 'How to Meditate: A Guide to Peace'])
    # should return ^ ['buddhism', 'meditation']
    """
    def __init__(
        self,
        data_sources: list[DataSource] = None,
        min_df=15, # filter vocab rarer than this
        min_points: int = 50, # tags with less than this many data points will be filtered out
        max_depth: int = 10, # tags at this level will be considered leaf nodes
        base_classifier: BaseEstimator = None,
    ) -> None:
        self.data_sources = data_sources
        self.min_points = min_points
        self.min_df = min_df
        self.max_depth = max_depth
        # Two Main options for Classifier here: Logit or SVMs
        # for LogisticRegression, just set (max_iter=300) and keep the rest default
        # solver='saga' penalty='elasticnet' l1_ratio=0.5 performed slightly better in CV
        # but it proved too slow to train and impossible to parallelize :\
        # GradientBoosting significantly underperformed (as expected)
        # SVC Cross Validation suggested C=0.1 regularization but YT test data disagreed
        # see a couple hundred lines below for a performance summary against a holdout
        self.base_classifier = base_classifier if base_classifier is not None else LinearSVC(
            dual='auto', # suppress annoying warning hehe
        )
    
    def train(self):
        """The big main function"""
        # Honestly, if I were coding this again, I'd do this differently
        # and have a X_raw cache for a set of DataSources as it's fairly common
        # to train two different models on the same set of Sources, but oh well
        self._load_data()
        self._count_words() 
        to_train = [('root', 0)] # (slug, level)
        self.classifiers_ = dict()
        while len(to_train) > 0:
            slug, cur_level = to_train.pop()
            if slug in self.classifiers_:
                continue
            if cur_level < self.max_depth:
                classifier = self.train_node(slug)
            else:
                classifier = tag_predictor.ZeroLearningClassifier(label=slug)
            self.classifiers_[slug] = classifier
            to_train.extend([(child_slug, cur_level+1) for child_slug in classifier.classes_])
        return self

    def _load_data(self):
        self.drive_map = get_drive_folder_heirarchy()
        self.all_the_data_ = []
        for datasource in self.data_sources:
            self.all_the_data_.extend(datasource.get_all_datapoints())
        print("Sorting the datapoints...")
        self.all_the_data_.sort(key=lambda a: a.get_normalized_content())
    
    def _count_words(self):
        print("Counting all the words across the entire dataset...")
        X_raw = []
        for datapoint in self.all_the_data_:
            # Need to append even empty titles and content
            # so that the vectorizer below knows how to
            # stitch together the raw strings with their vectors
            # empty training points are filtered out below
            # in _training_data_from_datapoints by the
            # `if title.nnz > 0` condition :)
            X_raw.append(datapoint.get_normalized_title())
            X_raw.append(datapoint.get_normalized_content())
        shape = len(X_raw)
        self.vectorizer_, X_raw = build_vectorizer(
            X_raw,
            sorted([w for w in STOP_WORDS if w]),
            self.min_df,
        )
        if X_raw.shape[0] != shape:
            raise RuntimeError("build_vectorizer mangled the X_raw length?")
        for i in trange(0, int(X_raw.shape[0]), 2):
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
            # here is where we finally filter out empty values
            if title.nnz > 0:
                x.append(title)
                w.append(confidence * math.log(1+title.nnz))
            if content.nnz > 0:
                x.append(content)
                w.append(confidence * math.log(1+content.nnz))
        return (x, w)

    def train_node(self, tag:str) -> BaseEstimator:
        print(f"Building '{tag}' classifier job...")
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
            node_classifier = tag_predictor.OBUNodeClassifier(
                min_df=self.min_df,
                base_classifier=self.base_classifier,
            )
        else:
            print("  Nothing to learn")
            return tag_predictor.ZeroLearningClassifier(label=tag)
        X = sparse.vstack(X)
        print(f"  Actually training '{tag}' now...")
        return node_classifier.fit(X, y, sample_weight=w)

    def save_as(self, filepath: Path | str):
        """Save only the essential data to a pickle file (.pkl)"""
        if Path(filepath).exists():
            Path(filepath).replace(str(filepath)+'.prev')
        joblib.dump((self.vectorizer_.vocabulary_, self.classifiers_), filepath)


def report_model_score_against_youtube_data(model:TagPredictor, gdrive_also=True):
    if gdrive_also:
        yt_tags = extract_all_youtube_ids(
            get_all_trainable_files_in_folders(),
            get_folder_to_tag_mapping(),
        )
    else:
        yt_tags = extract_all_youtube_ids()
    for k in yt_tags:
        yt_tags[k] = [t[0] for t in yt_tags[k]]
    video_data = get_ytdata_for_ids([ytid for ytid in yt_tags.keys() if yt_tags[ytid]])
    print(f"Analyzing predictions for {len(video_data)} videos...")
    X_test = [get_normalized_text_for_youtube_vid(vid) for vid in video_data]
    y_pred = model.predict(X_test, normalized=True)
    #  Report on a tier:
    # S tier = first tag match
    # A tier = pred in tags
    # B tier = pred in first tag ancestors
    # C tier = pred in any tag ancestor
    # D tier = pred in any tag descendant
    # E tier = pred unrelated entirely
    vid_bins = {t: [] for t in 'sabcde'}
    drive_map = get_drive_folder_heirarchy()
    for i in range(len(video_data)):
        vid = video_data[i]
        pred = y_pred[i]
        tags = yt_tags[vid['id']]
        vid['prediction'] = pred
        vid['tags'] = tags
        if pred == tags[0]:
            vid_bins['s'].append(vid)
            continue
        if pred in tags:
            vid_bins['a'].append(vid)
            continue
        if pred in drive_map.get(tags[0],{'ancestors': []})['ancestors']:
            vid_bins['b'].append(vid)
            continue
        for tag in tags[1:]:
            if pred in drive_map.get(tag,{'ancestors':[]})['ancestors']:
                vid_bins['c'].append(vid)
                break
        if vid in vid_bins['c']:
            continue
        for tag in tags:
            if tag not in drive_map:
                continue
            if pred in drive_map[tag]['descendants']:
                vid_bins['d'].append(vid)
                break
            p = drive_map[tag]['ancestors'][-1]
            if pred in drive_map[p]['children']:
                vid_bins['d'].append(vid)
                break
        if vid not in vid_bins['d']:
            vid_bins['e'].append(vid)
    s = len(video_data)
    print(
        dedent(f"""\
               Analysis Complete!
               Of the {s} videos, their predicted tags break down as follows:
               S Tier (first tag match): {len(vid_bins['s'])/s:2.1%}
               A Tier (tag match):       {len(vid_bins['a'])/s:2.1%}
               B Tier (ancestor match):  {len(vid_bins['b'])/s:2.1%}
               C Tier (any tag ancestor):{len(vid_bins['c'])/s:2.1%}
               D Tier (direct relative): {len(vid_bins['d'])/s:2.1%}
               E Tier (no relation):     {len(vid_bins['e'])/s:2.1%}
               """
        )
    )
    return vid_bins

# As of Feb 3, 2024, the LinearSVC Classifier performed as follows on the YouTube Holdout:
# ----------
# Of the 167 videos, their predicted tags break down as follows:
# S Tier (first tag match): 22.2%
# A Tier (tag match):       26.3%
# B Tier (ancestor match):  3.6%
# C Tier (any tag ancestor):13.2%
# D Tier (direct relative): 15.0%
# E Tier (no relation):     19.8%
#
# As of Oct 30, 2025, the performance is now:
# ----------
# Of the 255 videos, their predicted tags break down as follows:
# S Tier (first tag match): 30.6%
# A Tier (tag match):       21.6%
# B Tier (ancestor match):  3.1%
# C Tier (any tag ancestor):14.1%
# D Tier (direct relative): 11.4%
# E Tier (no relation):     19.2%

if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        prog="python3 train_tag_predictor.py",
        description="Trains a mapping of doc strings to tag slugs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    argument_parser.add_argument(
        'modelname',
        default="default",
        nargs='?',
        help="The file name to use when saving the model"
    )
    argument_parser.add_argument(
        '--exclude-youtube-data',
        dest='no_yt_data',
        action='store_true',
        help="Will use the YT Data as a test set instead of as a training set.",
    )
    args = argument_parser.parse_args()
    data_sources = [WebsiteDataSource(), GoogleDriveFilesDataSource()]
    if not args.no_yt_data:
        data_sources.append(YouTubeDataSource())
    classifier = OBUTopicClassifier(
        data_sources=data_sources,
    )
    classifier.train()
    MODELS_DIRECTORY.mkdir(exist_ok=True)
    classifier.save_as(MODELS_DIRECTORY.joinpath(f"{args.modelname}.pkl"))
    print("Model file trained and saved!")
    if args.no_yt_data:
        predictor = TagPredictor(
            classifier.vectorizer_.vocabulary_,
            classifier.classifiers_,
        )
        report_model_score_against_youtube_data(predictor, gdrive_also=False)
