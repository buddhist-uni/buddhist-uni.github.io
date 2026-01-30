#!/bin/python3

from train_tag_predictor import get_trainable_gfiles_from_site, save_all_drive_texts
from tag_predictor import TagPredictor
from yaspin import yaspin


print("Grabbing latest text pickles...")
save_all_drive_texts(all_files=get_trainable_gfiles_from_site())
print("Latest pickles grabbed")

with yaspin(text="Loading tag predictor..."):
  TagPredictor.load()
print("Tag Predictor loaded")
