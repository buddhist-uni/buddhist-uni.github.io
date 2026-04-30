#!/bin/python
from strutils import (
  whitespace,
  thumbnail_path_for_file,
  THUMBNAIL_SIZES,
)
import subprocess
from pathlib import Path
import os.path

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

def render_pdf_thumbnail(path, min_d_size=256, max_d_size=512, type='png') -> bytes:
  try:
    import fitz
  except:
    print("pip install pymupdf")
    exit(1)
  doc = fitz.open(path)
  page = doc[0]
  maxzoom = max_d_size / max(page.rect.width, page.rect.height, max_d_size)
  minzoom = min_d_size / min(page.rect.width, page.rect.height)
  zoom = minzoom if minzoom < maxzoom else maxzoom
  pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
  return pix.tobytes(type)

def get_shared_cached_pdf_thumbnail(pdf_path: Path, size='large') -> bytes:
  thumbnail_path = thumbnail_path_for_file(pdf_path, shared=True, size=size)
  if thumbnail_path.is_file():
    return thumbnail_path.read_bytes()
  tsize = THUMBNAIL_SIZES[size]
  thebytes = render_pdf_thumbnail(
    pdf_path,
    min_d_size=tsize,
    max_d_size=2*tsize,
    type='png',
  )
  thumbnail_path.parent.mkdir(exist_ok=True, parents=True)
  thumbnail_path.write_bytes(thebytes)
  return thebytes

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
  reader = pypdf.PdfReader(pdf_file, strict=False)
  ret = ''
  for i, page in enumerate(reader.pages):
      # insert a page break (\f) between pages when normalize==0
      text = ""
      try:
        text = page.extract_text() + '\f'
      except UnboundLocalError:
        print(f"WARNING: Unable to extract text from page {i} of \"{os.path.basename(pdf_file)}\" due to a bug in pypdf.")
      if normalize > 0 and text:
        text = whitespace.split(text)
        if normalize > 2:
          text = [word for word in text if word.isalpha()]
        text = ' '.join(text)
      ret += text
      if max_len and len(ret) > max_len:
         break
  return ret
