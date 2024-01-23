#!/bin/python
from strutils import (
  whitespace,
)

try:
  import pypdf
except:
  print("pip install pypdf")
  exit(1)

def readpdf(pdf_file, max_len=None, normalize=1):
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
