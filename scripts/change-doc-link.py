#!/bin/python3

from refresh_link_docs import *

doc = input("Doc Link: ")
doc = gdrive.link_to_id(doc)
link = gdrive.input_with_prefill("New URL: ", "")
name = gdrive.session().files().update(fileId=doc,body={'properties':{'url':link}},fields="name").execute()['name']
regen_link_doc(doc, title=name, link=link)
