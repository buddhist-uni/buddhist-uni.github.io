---
title: Behind the Scenes
---

### With Khemarato Bhikkhu

> Alas! Asaṅga spent twelve years in the wilderness, practising meditation.  
> Without achieving any success in meditation,  
> He has instead compiled these treatises  
> As a burden for an elephant’s back.  
>  
> ~ [Vasubandhu](https://www.lotsawahouse.org/tibetan-masters/khenpo-shenga/life-of-vasubandhu)

# Background

Most schools of Buddhism in Asia have a standardized curriculum for monastics and those of faith.
The Gelukpa has the "Geshe" degree, Thailand has the "Nak Tham" exams, but the "Modern" Buddhism focused on the earliest Buddhist texts which is emerging in the English-speaking world still has no such academic standard.
Perhaps that makes sense as we're still figuring it out!
But while our field is new, it is also large enough now that students of Buddhist Studies need guidance through the vast corpus.

When I ordained as a monk, I personally felt that need and looked around for a curriculum to help me.
Rejecting both sectarian and secular structures, however, I found myself assembling my own study-plan from what I could find online.

Fortunately, [there is quite a lot](https://buddhistuniversity.net/sources/)!

[Having organized that in Google Drive for my own studies](https://drive.google.com/open?id=1RJi6bEXa25zizGdsm5evCycYuY6a2D8r), I started to share what I had compiled with my friends, who later encouraged me to turn it into [this website](https://buddhistuniversity.net).

# This Website

There are two primary ways to use the site: taking [the self-paced courses](https://www.buddhistuniversity.net/courses/) or hanging out at [the library](https://www.buddhistuniversity.net/content/).

The library contains all the best content I've found organized [by topic](https://buddhistuniversity.net/tags/) (as well as [a few other ways](https://buddhistuniversity.net/library/)).

These topical bibliographies are then organized into course syllabi which can be studied online or used in your study group or class. There are already students and teachers around the world using the material here in a variety of ways and I couldn't be prouder!

# Methodology

After reading/listening to something good online (or [elsewhere](https://buddhistuniversity.net/exclusive/)), I  consider what I learned from the piece and who I’d recommend it to.
After answering those questions affirmatively, I squirrel away the e.g. PDF into an appropriate [subfolder on Google Drive](https://docs.google.com/document/u/2/d/1rGLm9Xh5de0e3hsMY2yyt97MWBuZJ1V1_q0jhGe7vpw/pub#h.c2mgbtxijho) corresponding to the topic at hand.

When a given subfolder has accumulated a fairly broad range of material, I then add its contents to [this website](https://buddhistuniversity.net/content/), and add the folder as a new "tag" on [the topics page](https://buddhistuniversity.net/tags/).

As a [map of my mind](https://photos.app.goo.gl/Z8nvMf3Cbup6WA418), that ontology (editorially and structurally) contains all my personal biases.
**This is a feature not a bug.** I named my elephants with thought, care, and delight and I hope that, as you explore my library, you will find some of that delight too. 😊 🐘

# About the Code

This is a static HTML website built with [Jekyll](https://jekyllrb.com/) and served by [GitHub Pages](https://pages.github.com/).

(Feel free to skip this section if you're not interested in the technical details.)

## Running the site locally

To run the site locally, clone [the repo](https://github.com/buddhist-uni/buddhist-uni.github.io), then run "[`bundle`](https://bundler.io/) `install`" and "`bundle exec` [`jekyll`](https://jekyllrb.com/docs/installation/) `serve`" keeping in mind that the build may take up to 30 mins. 

To speed that up, you have two options:

1. You can add the `--config _config.yml,_quick_build.yml` build flag for a faster, but partial build.
2. You can serve the production build locally like so:

~~~
rm -rf _site
git branch -D prod
git pull
git checkout prod
cp -r . _site
git checkout master
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
- [_plugins](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_plugins) is not a collection but rather contains native Ruby extensions for quickly running complex algorithms or for dynamically generating content. Currently my only custom plugin is the [similar content engine](https://github.com/buddhist-uni/buddhist-uni.github.io/blob/master/_plugins/similar_content.rb) which you can [read about here](https://talk.jekyllrb.com/t/replacing-a-slow-include-with-a-custom-ruby-tag/6064?u=khbh)
- [_posts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_posts) are the [blog posts](https://jekyllrb.com/docs/posts/) which make up the newsletter.
- [_publishers](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_publishers) are the publishers which I have granted their own hub.
- [_sass](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_sass) contains [the site's css](https://jekyllrb.com/docs/assets/).
- [_series](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_series) - Are collections of `_content` items that were published as part of a `number`ed `series` (specified by fields on the content item)
- [_tags](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_tags) - The bibliographic topics, arranged in a directed, ontological graph via the `parents` field.
- [_tests](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_tests) - A couple of pages with [Integration Tests](https://buddhistuniversity.net/tests/content) I have used during development in the past, and decided to keep around in case the code is useful in the future.

Lastly,
- [.github/workflows](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/.github/workflows) contains my [GitHub Actions](https://docs.github.com/en/actions) [Workflow files](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions) which build the site and check for certain errors.

For questions about the source code, feel free to [email me](mailto:khemarato.bhikkhu@gmail.com) or post an issue or comment on GitHub.

# Reuse

The beauty of Jekyll is that it outputs plain HTML, which you can find in [the repo's "prod" branch](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/prod). This raw html can be reworked in a variety of ways or you can fork the repo to use the source code.
[The entire database can also be found in Bibtex format here](https://buddhistuniversity.net/content.bib), in case that's helpful, for example for importing into an academic reference manager.

**Feel free to reuse this website in any (ethical) way you like** consistent with [the attached MIT License](https://mit-license.org/).

# Future Directions

Over the next few years, I'd like to expand the University's offerings further: into various regional forms of Buddhism, subtler points of Buddhist philosophy, the grand arcs of history, and much, much more. I'd also like to continue to improve the site's design and marketing, so it can be as accessible as possible.

If you'd like to contribute, comment on [an open issue on GitHub](https://github.com/buddhist-uni/buddhist-uni.github.io/issues) or [email me](mailto:khemarato.bhikkhu@gmail.com) with your own idea for a project and we'll take it from there!

It is my hope that this curriculum will provide a basis for Buddhist Studies for decades to come.

# Disclaimers

- This repository, like all things, is imperfect and subject to change.
- While I have taken some pains to ensure that everything here is accurate and legal, please know that you use the University at your own risk.
- The various views expressed in each work are the opinions of the respective author(s) and may or may not reflect my own.

# Acknowledgements

A big thank you to [the content sources](https://www.buddhistuniversity.net/sources/), to [Google](https://about.google/) (for hosting [the Drive library](https://drive.google.com/drive/folders/1RJi6bEXa25zizGdsm5evCycYuY6a2D8r)), to [GitHub](https://github.com/about/) for hosting the site, and to all the various [content creators](https://buddhistuniversity.net/authors/) and [publishers](https://buddhistuniversity.net/publishers/) who generously put their work out there for free. It's a testament to Buddhist generosity that such an expansive and outstanding collection can be compiled (almost entirely) from free material.

# Dedication

This curriculum is humbly dedicated to all of my teachers---past, present and future. Especially you.

[![DOI](https://zenodo.org/badge/244081930.svg)](https://zenodo.org/badge/latestdoi/244081930)

