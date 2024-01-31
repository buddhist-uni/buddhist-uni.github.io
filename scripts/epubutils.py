#!/bin/python3

from bs4 import BeautifulSoup
import ebooklib
import ebooklib.epub
from pathlib import Path

def read_epub(file_name: str | Path):
    book = ebooklib.epub.read_epub(file_name, options={'ignore_ncx': True})
    ret = []
    for section in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(section.get_content(), features="xml")
        ret.append(soup.get_text())
    return '\f'.join(ret)
