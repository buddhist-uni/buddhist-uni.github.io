#!/bin/python3

import argparse
import math
from pathlib import Path
import json
import regex
import random
import hashlib
from functools import cache
from textwrap import dedent

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
from sklearn.svm import LinearSVC
from sklearn.base import (
    BaseEstimator,
    ClassifierMixin,
    TransformerMixin,
)
from sklearn.base import clone as sklearn_clone
from sklearn.utils.validation import (
    check_X_y,
    check_is_fitted,
    check_array,
)
from sklearn.utils.multiclass import unique_labels
import joblib
from tqdm import tqdm, trange
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
disk_memorizor = joblib.Memory(DATA_DIRECTORY.joinpath('.cache'))

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

COURSE_TAG_WEIGHT = 2.5

def normalize_text(text: str) -> str:
    text = unidecode(text).lower()
    text = (
        stemmer.stem(word)
        for word in regex.split(r"[^a-z]+", text)
        if len(word) >= 4 and word not in STOP_WORDS
    )
    return ' '.join(text)

@cache
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

@cache
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

YOUTUBE_DATA_FOLDER = DATA_DIRECTORY.joinpath('youtube_metadata')
if not YOUTUBE_DATA_FOLDER.exists():
    YOUTUBE_DATA_FOLDER.mkdir()

def get_ytdata_for_ids(youtube_ids: dict | list) -> list[dict]:
    ids_to_fetch = []
    ret = []
    for ytid in youtube_ids:
        cachefile = YOUTUBE_DATA_FOLDER.joinpath(f"{ytid}.json")
        if cachefile.exists():
            ret.append(json.loads(cachefile.read_text()))
        else:
            ids_to_fetch.append(ytid)
    if ids_to_fetch:
        print(f"Fetching YouTube Data for {len(ids_to_fetch)} urls...")
        snippets = gdrive.get_ytvideo_snippets(ids_to_fetch)
        transcripts, _ = gdrive.YouTubeTranscriptApi.get_transcripts(
            ids_to_fetch, continue_after_error=True)
        if len(snippets) != len(ids_to_fetch):
            raise ValueError("Didn't get all the snippets?")
        for vid in snippets:
            if transcripts.get(vid['id']):
                vid['transcript'] = transcripts[vid['id']]
            else:
                vid['transcript'] = {}
            cachefile = YOUTUBE_DATA_FOLDER.joinpath(f"{vid['id']}.json")
            cachefile.write_text(json.dumps(vid))
            ret.append(vid)
    return ret

YT_STOP_LINES = set([
    '',
    'foreign',
    'cheers',
    '[Music]',
])
def flatten_youtube_transcript(transcript:list[dict]):
    """Note: does not normalize!"""
    ret = ' '.join([line['text'] for line in transcript if line['text'] not in YT_STOP_LINES])
    return regex.sub(r'\[.{0,35}\]', '', ret)

def md_stripper(markdown):
    """Very dumb. Just rm links because other
    features are rare in my content"""
    markdown = regex.sub(r'\]\([h/].{5,100}\)', '', markdown)
    return regex.sub(r'\{.{5,60}\}', '', markdown)

def flatten_youtube_metadata(video_data: dict) -> str:
    ret = (video_data['title'] + ' ') * 3
    if video_data.get('description'):
        ret += video_data['description'] + ' '
    if video_data.get('tags'):
        ret += ' '.join(video_data['tags']*5) + ' '
    return ret

def get_normalized_text_for_youtube_vid(video_data: dict) -> str:
    ret = flatten_youtube_metadata(video_data)
    if video_data.get('transcript'):
        ret += flatten_youtube_transcript(video_data['transcript'])
    return normalize_text(ret)

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

def save_all_drive_texts(parallelism=6, sample_size=None, min_size=0, max_size=150000000, all_files=None):
    """If sample_size is None, goes from smaller to larger files,
    otherwise a random sample is chosen
    
    If this task is interupted, simply `rm *.incomplete`
    """
    if not all_files:
        all_files = get_all_trainable_files_in_folders()
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
                tags=[(tag.slug, 1)],
                confidence=10,
            )
        print("Loading website DataPoints...")
        for wc in tqdm(website.content):
            content = md_stripper(wc.content)
            if wc.category == 'canon':
                self.add_datapoints(
                    title=wc.title + ' ' + content,
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
                content=flatten_youtube_transcript(vid['transcript']),
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
                gdrive.link_to_id(link): content
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
    
def explain_logit(c: LogisticRegression, vocabulary: ArrayLike):
    ret = ''
    for i in range(len(c.classes_) if len(c.classes_) > 2 else 1):
        ret += f" {c.classes_[i]}:\n"
        coefs = c.coef_[i]
        indexes = np.argsort(coefs)[::-1][:5]
        coefs = coefs[indexes]
        terms = vocabulary[indexes]
        ret += f"   The most indicative terms within this folder are:\n"
        for j in range(5):
            ret += f"     {terms[j]} - {coefs[j]}\n"
        ret += f"   And the most anti-indicative terms for this folder were:\n"
        indexes = np.argsort(c.coef_[i])[:5]
        coefs = c.coef_[i][indexes]
        terms = vocabulary[indexes]
        for j in range(5):
            ret += f"     {terms[j]} - {coefs[j]}\n"
    return ret

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
            self.base_classifier = LogisticRegression(max_iter=300)

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
    def explain_yourself(self, vocabulary: ArrayLike):
        ret = f"I'm a NodeClassifier trained on {self.N_} points\n"
        word_mask = self.pipeline_.steps[0][1]
        ret += f"I filter the features from {word_mask.num_features_in} words to {word_mask.num_features_out}\n"
        word_mask = word_mask.sparse_mask
        vocabulary = vocabulary[word_mask]
        classifier = self.pipeline_.steps[2][1]
        ret += f"I then predict one of {self.classes_} using {classifier}\n"
        if isinstance(classifier, LogisticRegression):
            ret += explain_logit(classifier, vocabulary)
        return ret

    def predict(self, X):
        check_is_fitted(self)
        X = check_array(X, accept_sparse=True)
        return self.pipeline_.predict(X)        

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
    ret = TqdmCountVectorizer(
        lowercase=False, # already lowered
        stop_words=stop_words,
        min_df=min_df,
    )
    X_raw = ret.fit_transform(X_raw)
    print("  Computed. Saving to disk...")
    joblib.dump(ret.vocabulary_, vocabfile, compress=2)
    joblib.dump(X_raw, X_file, compress=4)
    return (
        CountVectorizer(lowercase=False, vocabulary=ret.vocabulary_),
        X_raw,
    )

class OBUTopicClassifier:
    """
    Given a list of DataSources, learns a mapping from arbitrary strings to topic slugs.
    This is useful for automatically sorting unseen items into appropriate Unread folders.

    Example
    -------
    big_classifier = OBUTopicClassifier(WebsiteDataSource())
    big_classifier.train()
    big_classifier.predict(['Introduction to Buddhism', 'How to Meditate: A Guide to Peace'])
    # should return ^ ['buddhism', 'meditation']
    """
    def __init__(
        self,
        data_sources: list[DataSource] = None,
        min_df=15, # filter vocab rarer than this
        min_points: int = 50, # tags with less than this many data points will be filtered out
        max_depth: int = 10, # tags at this level will be considered leaf nodes
        base_classifier: BaseEstimator = None,
        # fill both these to skip training
        classifiers: dict[str, OBUNodeClassifier | ZeroLearningClassifier] = None,
        vocabulary = None,
    ) -> None:
        self.data_sources = data_sources
        self.min_points = min_points
        self.min_df = min_df
        self.max_depth = max_depth
        if (not vocabulary) != (not classifiers):
            raise ValueError("To short-circuit training, load both vocabulary and the classifiers")
        self.classifiers_ = classifiers
        if vocabulary:
            self.vectorizer_ = CountVectorizer(lowercase=False, vocabulary=vocabulary)
        elif not data_sources:
            raise ValueError("You need to supply a DataSource to train the model")
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
        if self.classifiers_:
            raise RuntimeError("Attempting to train a trained OBUTopicClassifier")
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
                classifier = ZeroLearningClassifier(label=slug)
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
            content = datapoint.get_normalized_title()
            if content:
                X_raw.append(content)
            content = datapoint.get_normalized_content()
            if content:
                X_raw.append(content)
        self.vectorizer_, X_raw = build_vectorizer(
            X_raw,
            sorted([w for w in STOP_WORDS if w]),
            self.min_df,
        )
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
            node_classifier = OBUNodeClassifier(
                min_df=self.min_df,
                base_classifier=self.base_classifier,
            )
        else:
            print("  Nothing to learn")
            return ZeroLearningClassifier(label=tag)
        X = sparse.vstack(X)
        print(f"Actually training '{tag}' now...")
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

    def save_as(self, filepath: Path | str):
        """Save only the essential data to a pickle file (.pkl)"""
        self.vectorizer_.transform([]) # prime the vectorizer in case it hasn't been used yet
        joblib.dump((self.vectorizer_.vocabulary_, self.classifiers_), filepath, compress=3)

    @classmethod
    def load(cls, filepath: Path | str):
        """Loads a new instance of OBUTopicClassifier from the given save_as'ed .pkl file"""
        vocabulary, classifiers = joblib.load(filepath)
        return cls(vocabulary=vocabulary, classifiers=classifiers)

def report_model_score_against_youtube_data(model:OBUTopicClassifier, gdrive_also=True):
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
                
               (This Function will return the vid data in bins for you to analyze)
               """
        )
    )
    return vid_bins

# As of Feb 1, 2024, the LinearSVC Classifier performed as follows on the YouTube Holdout:
# ----------
# Of the 166 videos on the website, their predicted tags break down as follows:
# S Tier (first tag match): 21.7%
# A Tier (tag match):       24.7%
# B Tier (ancestor match):  3.0%
# C Tier (any tag ancestor):13.9%
# D Tier (direct relative): 16.3%
# E Tier (no relation):     20.5%

def import_links(command_args):
    print("Here is where my code will go for importing links")

if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        prog="python3 auto_sort_unreads.py",
        description="A set of tools for bulk importing unread items into the appropriate subfolders.",
    )
    command_group = argument_parser.add_subparsers(required=True, dest='command')

    links_subparser = command_group.add_parser('import_links')
    links_subparser.set_defaults(func=import_links)

    command_args = argument_parser.parse_args()
    command_args.func(command_args)
