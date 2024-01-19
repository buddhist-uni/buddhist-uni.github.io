#!/bin/python3

try:
  import trafilatura
except:
   print("  pip install trafilatura")
   exit(1)

def extract_simplified_html_for_url(url):
    downloaded_webpage = trafilatura.fetch_url(url)
    parsed_document = trafilatura.extract(
       downloaded_webpage,
       output_format='xml',
       include_images=True,
       include_links=True,
       include_comments=False,
       favor_recall=True,
    ) or ''
    # convert trafilatura's silly xml back to html
    html_doc = parsed_document\
      .replace(" target=\"", " href=\"")\
      .replace("<ref ", "<a ")\
      .replace("</ref>", "</a>")\
      .replace("<section", "<div")\
      .replace("</section>","</div>")\
      .replace("<graphic","<img")\
      .replace("</graphic>","</img>")\
      .replace('<list rend="ul">',"<ul>")\
      .replace('<list rend="ol">',"<ul>")\
      .replace("</list>","</ul>")\
      .replace("<item","<li")\
      .replace("</item>","</li>")\
      .replace("<head","<h3")\
      .replace("</head>","</h3>")
    return html_doc
