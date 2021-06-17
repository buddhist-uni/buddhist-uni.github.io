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

# Studying

There are two primary ways to use [this website](https://buddhistuniversity.net): taking [our self-paced courses](https://www.buddhistuniversity.net/courses/) or hanging out at [the library](https://www.buddhistuniversity.net/library/).

The library contains all the best content I've found [on the internet](https://buddhistuniversity.net/sources/) organized [by topic](https://buddhistuniversity.net/tags/). These topical bibliographies are then compiled into [course syllabi](https://buddhistuniversity.net/courses/) which can be studied online or used more formally in your study group or class. There are already students and teachers around the world using the free material here in a variety of ways and I couldn't be prouder!

# History

This webpage started its life as [my personal library of Buddhist stuff on Google Drive](https://drive.google.com/open?id=1RJi6bEXa25zizGdsm5evCycYuY6a2D8r). 

After reading stuff I found online, I would contemplate what I learned from it and who I’d recommend it to. Only after answering these questions would I then squirrel away the e.g. PDF into an appropriate Google Drive folder.

In this way, my library (like all personal libraries) has slowly grown to serve two purposes: 

1. to organize my own media for their safe-keeping, retrieval and revision, and  
2. for others (hello!) to peruse and, hopefully, benefit from.

These two aims find unity in the pride that any book-worm feels towards their library. As a [map of my mind](https://photos.app.goo.gl/Z8nvMf3Cbup6WA418), this website contains (editorially and structurally) my own biases. **This is a feature not a bug.** I named my elephants with a great deal of thought, care, and delight and I hope that, as you explore my library, you will feel some of that delight too. 😊 🐘

# About the Code

This is a static HTML website built with [Jekyll](https://jekyllrb.com/) and served by [GitHub Pages](https://pages.github.com/).

## Running the site locally

To run the site locally, clone the repo, then run "[`bundle`](https://bundler.io/) `install`" and "`bundle exec` [`jekyll`](https://jekyllrb.com/docs/installation/) `serve`" keeping in mind that the build may take up to 30 mins. 

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
- [_tests](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_tests) - A couple of pages with Integration Tests I have used during development in the past, and decided to keep around in case the code is useful in the future.

Lastly,
- [.github/workflows](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/.github/workflows) contains my [GitHub Actions](https://docs.github.com/en/actions) [Workflow files](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions) which build the site and check for certain errors.

For questions about the source code, feel free to [email me](mailto:khemarato.bhikkhu@gmail.com) or post an issue or comment on GitHub.

## Contributions

The beauty of Jekyll is that it outputs plain HTML, which you can find in [the repo's "prod" branch](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/prod). This raw html can be reworked in a variety of ways. Feel free to reuse it in any (ethical) way you like. If you would like to contribute anything back, please message me, [open an issue](https://github.com/buddhist-uni/buddhist-uni.github.io/issues/new) or fork the repository and open a pull request!  

# Future Directions

Over the next few years, I would like to expand the University's offerings further and further: into various regional forms of Buddhism, subtler points of Buddhist philosophy, the grand arcs of history, and much, much more. I'd also like to continue to improve the site's design and marketing, so it can be as accessible as possible to as many people as possible.

I have also tried to select content with "staying power" to avoid, as much as possible, anything that will become outdated in a few years.  This site, while technically a "blog," is **not** yet another newsfeed of digital ephemera. It is an experiment in a somewhat slower technology. It is my hope that this curriculum will provide a solid basis for Buddhist Studies for decades to come.

# Disclaimers

- This repository, like all other things in life, is imperfect and subject to change.
- While I have taken some pains to ensure that everything here is accurate and legal, please know that you use the University at your own risk.
- The various views expressed in each work are the opinions of the respective author(s) and may or may not reflect my own.

# Acknowledgements

A big thank you to [the content sources](https://www.buddhistuniversity.net/sources/), to [Google](https://about.google/) (for hosting [the Drive library](https://drive.google.com/drive/folders/1RJi6bEXa25zizGdsm5evCycYuY6a2D8r)), to [GitHub](https://github.com/about/) for hosting the site, and to all the various [content creators](https://buddhistuniversity.net/authors/) and [publishers](https://buddhistuniversity.net/publishers/) who generously put their work out there for free. It's a testament to Buddhist generosity that such an expansive and outstanding collection can be compiled (almost entirely) from free material.

# Dedication

To all my teachers---past, present and future. Especially you.

[![DOI](https://zenodo.org/badge/244081930.svg)](https://zenodo.org/badge/latestdoi/244081930)

