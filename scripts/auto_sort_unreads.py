#!/bin/python3

from pathlib import Path
import json
import regex
import random

from functools import cache
import numpy as np
import gensim.downloader
from sklearn.multiclass import OneVsRestClassifier
from sklearn.svm import SVC
from tqdm import tqdm

from strutils import (
    git_root_folder,
    prompt,
)
import website
import joblib
import gdrive
from pdfutils import readpdf

DATA_DIRECTORY = Path('/media/khbh/Data/autosort/')

disk_memorizor = joblib.Memory(DATA_DIRECTORY.joinpath('.cache'))
website.load()
DRIVE_FOLDERS = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
PUBLIC_FOLDER_FOR_PRIVATE = {
    gdrive.folderlink_to_id(pair['private']): gdrive.folderlink_to_id(pair['public'])
    for pair in DRIVE_FOLDERS.values() if pair['private'] and pair['public']
}

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

def get_all_trainable_drive_folders():
    """Returns a dict mapping tag-like slug to the gdrive folder IDs to use for it.
    
    In the normal case, this will map, e.g.
        "buddha" => [<Buddha>, <Unread (Buddha)>, <Archive (Buddha)>]
    There will be ambiguous cases.
    These will be prompted for and the answers cached."""
    folders_map = json.loads(gdrive.FOLDERS_DATA_FILE.read_text())
    buddhism_folder = gdrive.folderlink_to_id(folders_map['buddhism']['private'])
    world_folder = gdrive.folderlink_to_id(folders_map['world']['private'])
    folders_map = {
        gdrive.folderlink_to_id(folders_map[slug]['private']): slug
        for slug in folders_map if folders_map[slug]['private']
    }
    ret = _get_trainable_drive_folders(buddhism_folder, folders_map, {})
    return _get_trainable_drive_folders(world_folder, folders_map, ret)

ORGANIZATIONAL_SUBFOLDERS_FILE = DATA_DIRECTORY.joinpath('organizational_subfolders.json')
ORGANIZATIONAL_SUBFOLDERS = []
if ORGANIZATIONAL_SUBFOLDERS_FILE.exists():
    ORGANIZATIONAL_SUBFOLDERS = json.loads(ORGANIZATIONAL_SUBFOLDERS_FILE.read_text())
SUBFOLDERS_IGNORE_FILE = DATA_DIRECTORY.joinpath('ignored_subfolders.json')
IGNORE_SUBFOLDERS = []
if SUBFOLDERS_IGNORE_FILE.exists():
    IGNORE_SUBFOLDERS = json.loads(SUBFOLDERS_IGNORE_FILE.read_text())

def _get_trainable_drive_folders(this_folder, folders_map, ret):
    slug = folders_map[this_folder]
    ret[slug] = [this_folder]
    subfolders = gdrive.get_subfolders(this_folder)
    for subfolder in subfolders:
        if subfolder['id'] in IGNORE_SUBFOLDERS:
            continue
        name = subfolder['name']
        if 'unread' in name.lower() or 'archive' in name.lower() or subfolder['id'] in ORGANIZATIONAL_SUBFOLDERS:
            ret[slug].append(subfolder['id'])
            continue
        if subfolder['id'] not in folders_map:
            print(f"Folder {slug}/\"{subfolder['name']}\" isn't in the hierarchy.")
            new_slug = input("Add it as slug (blank for no): ")
            if new_slug:
                public_folder = input("Public folder link: ").split('?')[0]
                gdrive.add_tracked_folder(new_slug, public_folder, gdrive.FOLDER_LINK_PREFIX+subfolder['id'])
                folders_map[subfolder['id']] = new_slug
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
        ret = _get_trainable_drive_folders(subfolder['id'], folders_map, ret)
    return ret

FILE_FIELDS = 'id,name,shortcutDetails,size,mimeType,properties'
TRAINABLE_MIMETYPES = set([
    'application/pdf',
    'application/epub+zip',
    'application/vnd.google-apps.document',
])

def get_all_trainable_files_in_folders(trainable_folders, verbose=False):
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
    if not verbose:
        wrapper = tqdm
    for folderid in wrapper(trainable_folders):
        ret.extend(_get_trainable_files_in_folder(folderid, verbose))
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

PDF_TEXT_FOLDER = DATA_DIRECTORY.joinpath('pdftext')
if not PDF_TEXT_FOLDER.exists():
    PDF_TEXT_FOLDER.mkdir()

def save_pdf_text_for_drive_file(drivefile: dict, overwrite=False):
    name = f"{drivefile['id']}.txt"
    incompletetextfile = PDF_TEXT_FOLDER.joinpath(f"{name}.incomplete")
    completetextfile = PDF_TEXT_FOLDER.joinpath(name)
    if (not overwrite) and completetextfile.exists():
        print(f"Skipping {drivefile['id']} (text already extracted)")
        return
    try:
        if int(drivefile['size']) < 50000000: # 50 MB limit for doing this in-memory
            incompletetextfile.write_text(
                readpdf(gdrive.get_file_contents(drivefile['id']))
            )
        else:
            pdffile = PDF_TEXT_FOLDER.joinpath(f"{drivefile['id']}.pdf.incomplete")
            if not pdffile.exists():
                gdrive.download_file(drivefile['id'], pdffile)
            pdffile = pdffile.rename(pdffile.parent.joinpath(f"{drivefile['id']}.pdf"))
            incompletetextfile.write_text(readpdf(pdffile))
        incompletetextfile.rename(completetextfile)
    except Exception as e:
        print(f"Warning! There was an error downloading and parsing {drivefile['id']}:")
        print(e)

def save_all_pdf_texts(parallelism=16, sample_size=None, min_size=0, max_size=150000000):
    """If sample_size is None, goes from smaller to larger files,
    otherwise a random sample is chosen
    
    If this task is interupted, simply `rm *.incomplete`
    """
    print("Getting all pdf file ids...")
    folders = get_all_trainable_drive_folders()
    all_files = [
        file for file in 
        get_all_trainable_files_in_folders(folders)
        if file['mimeType'] == 'application/pdf' and
        int(file['size']) <= max_size and
        int(file['size']) >= min_size
    ]
    if sample_size:
        all_files = random.sample(all_files, sample_size)
    else:
        all_files.sort(key=lambda f: f['size'])
    print(f"Downloading {len(all_files)} pdfs and extracting their text...")
    joblib.Parallel(n_jobs=parallelism, verbose=10)(joblib.delayed(
        save_pdf_text_for_drive_file)(file) for file in all_files
    )
