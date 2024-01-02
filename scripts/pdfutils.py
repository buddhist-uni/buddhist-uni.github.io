from io import StringIO

from strutils import (
  iolen,
  whitespace,
)

try:
  from pdfminer.converter import TextConverter
  from pdfminer.layout import LAParams
  from pdfminer.pdfdocument import PDFDocument
  from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
  from pdfminer.pdfpage import PDFPage
  from pdfminer.pdfparser import PDFParser
except:
  print("pip install pdfminer.six")
  quit(1)

rsrcmgr = PDFResourceManager()

def get_searchable_contents(pdf_file):
    output_string = StringIO()
    device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    with open(pdf_file, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)
            if iolen(output_string) > 1500:
              break
    words = whitespace.sub(" ",
      output_string.getvalue()
    ).strip().split(" ")
    return " ".join([word for word in words if word.isalpha()])
