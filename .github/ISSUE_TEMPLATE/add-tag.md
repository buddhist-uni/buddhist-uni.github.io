---
name: Add Tag
about: Tracking the steps required to add new tags to the site.
title: "Add '{{ name }}' content to the site"
labels: ''
assignees: buddhist-uni
milestone: 2
body:
  - type: input
    id: tag
    attributes:
      label: Tag Slug
      description: The slug ID of the tag we're adding.
      placeholder: e.g. pali-canon
    validations:
      required: true
  - type: input
    id: name
    attributes:
      label: Tag Name
      description: The full name of the tag
      placeholder: e.g. The Pāli Canon
    validations:
      required: true
  - type: input
    id: drivelink
    attributes:
      label: Drive Folder
      description: A link to the folder on Google Drive.
      placeholder: https://drive.google.com/drive/folders/1NRjvD6E997jdaRpN5zAqxnaZv0SM-SOv
    validations:
      required: true
---

This is a task to publish the [{{ name }}]({{ drivelink }}) folder on Google Drive as [a new bibliography/tag](https://github.com/buddhist-uni/buddhist-uni.github.io/wiki/Adding-new-tags) on the site.

This includes adding all the `course: {{ tag }}` content.
 For more information on how to add content from Drive to the website, see [the content data entry guide](https://github.com/buddhist-uni/buddhist-uni.github.io/wiki/Adding-items-to-the-library).

Steps needed to accomplish this:
  - [x] Add the tag as a draft to [_tags/](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_tags)
    - Done! See **the draft tag [here](https://buddhistuniversity.net/tags/{{ tag }})**
  - [x] Add suttas from the folder to the site
  - [x] Add OpenAlex academic articles in the folder to the site
  - [ ] Add all other content from the public drive folder
  - [ ] Add any copyrighted content (e.g. YouTube links, books, or podcasts) not shared directly in the public folder
  - [ ] Add a draft set of images
  - [ ] Add a description
  - [ ] Add an image caption
  - [ ] Audit tag content for:
    - [ ] Meeting the diversity quotas
    - [ ] Weeding content that shouldn't be included
    - [ ] Harmony of description, images, and content
  - [ ] Productionize images
  - [ ] Publish the tag
  - [ ] Announce the tag on the blog/newsletter
