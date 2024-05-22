#!/bin/python
from strutils import (
  whitespace,
)
import subprocess
from pathlib import Path

try:
  import pypdf
except:
  print("pip install pypdf")
  exit(1)

def get_page_count(pdf_path) -> int | None:
    try:
        result = subprocess.run(['exiftool', '-n', '-p', '$PageCount', str(pdf_path)], capture_output=True, text=True)
        page_count = int(result.stdout.strip())
        return page_count
    except:
        return None

def readpdf(pdf_file: str | Path, max_len=None, normalize=1) -> str:
  """Returns a pdf's text.
  
  normalize:
    0 -> the raw text
    1 -> normalize whitespace only (default)
    2 -> [reserved]
    3 -> filter out all non-alpha words
  
  max_len:
    stops extracting text after max_len is reached
    Note: returned text may be larger than max_len
  """
  reader = pypdf.PdfReader(pdf_file)
  ret = ''
  for page in reader.pages:
      # insert a page break (\f) between pages when normalize==0
      text = page.extract_text() + '\f'
      if normalize > 0:
        text = whitespace.split(text)
        if normalize > 2:
          text = [word for word in text if word.isalpha()]
        text = ' '.join(text)
      ret += text
      if max_len and len(ret) > max_len:
         break
  return ret
