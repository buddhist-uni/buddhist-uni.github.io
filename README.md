---
title: Behind the Scenes
---

> Alas! Asaṅga spent twelve years in the wilderness, practising meditation.  
> Without achieving any success in meditation,  
> He has instead compiled these treatises  
> As a burden for an elephant’s back.  
>  
> ~ [Vasubandhu](https://www.lotsawahouse.org/tibetan-masters/khenpo-shenga/life-of-vasubandhu)

### By Khemarato Bhikkhu

# Studying

There are two primary ways to use [this website](https://buddhistuniversity.net): taking [our self-paced courses](https://www.buddhistuniversity.net/courses/) or hanging out at [the library](https://www.buddhistuniversity.net/library/).

The library contains all the best content I've found on the internet, [organized primarily by topic](https://www.buddhistuniversity.net/tags/).  After reading a work, I contemplated what I learned and who I'd like to recommend it to. Only then do I file away the piece into a topic, based on my answers to those questions.

Once a given topic has accumulated sufficient material, I then take some time to organize it into an undergraduate-style syllabus: identifying the themes and connections across different works and putting them into dialogue with each-other. Of course, as I review the material to create the classes, I inevitably learn a lot---as anyone who tries to teach finds out.  Over time, works will be added, moved or even replaced.

Once published, these lesson plans may be studied online as-is or reworked for in-person use by a study group or class. There are already students and teachers around the world using our courses in a variety of ways and I couldn't be prouder!

While some Buddhist countries (i.e., Thailand) have official curricula for teaching Buddhism to e.g. new monks, no such comprehensive curriculum exists in the English language.  It was towards filling that gap that I decided to dedicate my studies and this website.

# History

This GitHub-hosted page started its life as [my personal library of Buddhist stuff on Google Drive](https://drive.google.com/open?id=1RJi6bEXa25zizGdsm5evCycYuY6a2D8r). 

Now, a personal library has two audiences and thus two priorities: 

1. First, a library is there to organize one's own media for their safe-keeping, retrieval and study. 
2. Second, a library is there for others (hi, friend!) to peruse and, hopefully, benefit from

These two practical aims find unity in the pride that any book-worm feels towards their library: 

**A library is a reflection of its creator**---who they are and what they'd like to be.

Given that I'm a Buddhist monk, naturally my personal library represents a course of study in Buddhism.

Reflecting on the structure of the internet, I opted to express myself in a giant [mind map](https://photos.app.goo.gl/Z8nvMf3Cbup6WA418). As a map of my mind, this website contains (editorially and structurally) my own biases. This is a feature not a bug. I named my elephants with a great deal of thought, care, and delight and I hope that, as you explore my library, you will feel some of that delight too. 😊 🐘

# About the Code

This is a static HTML website built with [Jekyll](https://jekyllrb.com/) and served by [GitHub Pages](https://pages.github.com/).

## Running the site locally

To run the site locally, clone the repo, then run "[`bundle`](https://bundler.io/) `install`" and "`bundle exec` [`jekyll`](https://jekyllrb.com/docs/installation/) `serve`" keeping in mind that the build may take up to 30 mins. 

To speed that up, you have two options:

1. You can add the `--config _config.yml,_quick_build.yml` build flag for a faster, but partial build.
2. You can serve the production build locally like so:

~~~
rm -rf _site
git pull
git checkout prod
cp -r . ~/obu-prod
git checkout master
mv ~/obu-prod _site
JEKYLL_ENV=production bundle exec jekyll serve --incremental --skip-initial-build
~~~

For more information on the build process, see [the Jekyll docs](https://jekyllrb.com/docs/usage/).

## The Source Code

You can think of each of the `_folders` in [the source code](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master) as representing individual object types. Each folder is a different "table" in the hardcoded "database."

- [_authors](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_authors) - Each author with their own page.
- [_content](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_content) - All of the individual works in the library, divided by `category` based on the type. Each content item has a number of [metadata fields](https://jekyllrb.com/docs/front-matter/) listing its bibliographic information (e.g. `pages`) in Bibtex format, or linking the entry out to its file (e.g. `external_url`) or linking it to its internal groups (e.g. `authors`). Conventionally, I put raw strings in `"Quotes"` and I represent links to other objects as `unquoted-slugs`. The templates then use these slugs to fetch the related objects at page render time.
- [_categories](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_categories) - This folder houses the `index.html` pages for the `/content/*` folders and contains a little metadata about the categories, such as their plain English titles.
- [_courses](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_courses) - The University's courses.
- [_data](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_data) - Site configuration [variables](https://jekyllrb.com/docs/datafiles/).
- [_drafts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_drafts) - Unpublished courses or blog posts.
- [_includes](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_includes) - A Jekyll folder which houses the site's [reusable UI components](https://jekyllrb.com/docs/includes/).
- [_journals](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_journals) - Periodicals which get their own page.
- [_layouts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_layouts) houses the [html page templates](https://jekyllrb.com/docs/layouts/).
- [_posts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_posts) are the [blog posts](https://jekyllrb.com/docs/posts/) which make up the newsletter.
- [_publishers](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_publishers) are the publishers which I have granted their own hub.
- [_sass](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_sass) contains [the site's css](https://jekyllrb.com/docs/assets/).
- [_series](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_series) - Are collections of `_content` items that were published as part of a `number`ed `series` (specified by fields on the content item)
- [_tags](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_tags) - The bibliographic topics, arranged in a directed, ontological graph via the `parents` field.
- [_tests](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_tests) - A couple of pages with Integration Tests I have used during development in the past, and decided to keep around in case the code is useful in the future.

For questions about the source code, feel free to [email me](mailto:khemarato.bhikkhu@gmail.com) or [post an issue or comment on GitHub](https://github.com/buddhist-uni/buddhist-uni.github.io/).

## Contributions

The beauty of Jekyll is that it outputs plain HTML, which you can find in [the repo's "prod" branch](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/prod). This raw html can be reworked in a variety of ways. Feel free to reuse it in any (ethical) way you like. If you would like to contribute anything back, please message me or fork the repository and open a pull request!  

# Future Directions

Over the next few years, I would like to expand the University's offerings further and further: into various regional forms of Buddhism, subtler points of Buddhist philosophy, the grand arcs of history, and much, much more. I'd also like to continue to improve the site's design and marketing, so it can be as accessible as possible to as many people as possible.

I have also tried to select content with "staying power" to avoid, as much as possible, anything that will become outdated in a few years.  This site, while technically a "blog," is **not** yet another newsfeed of digital ephemera. It is an experiment in a somewhat slower technology. It is my hope that this curriculum will provide a solid basis for Buddhist Studies for decades to come.

# Disclaimers

- This repository, like all other things in life, is imperfect and subject to change.
- While I have taken some pains to ensure that everything here is accurate and legal, please know that you use the University at your own risk.
- The various views expressed in each work are the opinions of the respective author(s) and may or may not reflect my own.

# Acknowledgements

A big thank you to [the content sources](https://www.buddhistuniversity.net/sources/), to Google (for hosting [the Drive library](https://drive.google.com/drive/folders/1RJi6bEXa25zizGdsm5evCycYuY6a2D8r)), to GitHub for hosting the site, and to all the various content creators and publishers who generously put their work out there for free. It's a testament to Buddhist generosity that such an expansive and outstanding collection can be compiled (almost entirely) from free material.

# Dedication

To all my teachers---past, present and future. Especially you.

[![DOI](https://zenodo.org/badge/244081930.svg)](https://zenodo.org/badge/latestdoi/244081930)

