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

# History

While studying in London, there was a room at the Queen Mary library I liked to hang out in.
A large, dimly lit room, it was only accessible to us undergrads and the librarians.
Tables and chairs lined the tinted glass walls and in the center were rows and rows of books.
Called "The Undergraduate Reading Room," it contained a copy of every book for every class that semester.

It was built to ensure that even the poorest students at the university had access to their assigned reading, but the result was even cooler:
The room offered an up-to-date, physical snapshot of the entire university.

I'd walk around and run my hand down the shelves: Econ 101, Intro to Macroeconomics, Intro to Microeconomics... Education... Electrical Engineering... Film Studies... Whatever subject interested me, I'd pull the recommended text off the shelf, and read.

I spent many hours happily chipping away at my ignorance.
I finished none of the books (even for my own classes!) but just skimming the collection gave me an appreciation for the breadth of the academy and for the richness of its disciplines.

---

In Asia, most sects of Buddhism have a standardized curriculum for monastics and those of faith.
The Gelukpa has the "Geshe" degree, Thailand has the "Nak Tham" exams, but the "Protestant" Buddhism emerging in the English-speaking world still has no academic standards.
Perhaps that makes sense since we're still in the process of understanding the darn thing!
Our field is still new, I admit, but it is also large enough now that its students need guidance to get up to speed.

When I ordained, I felt that need myself and looked around for syllabi to help me.
I'm not afraid of studying history or questioning orthodoxy, but I'm also not okay with the materialistic reduction of religion.
So, rejecting both Eastern/sectarian and Western/academic structures, I found myself assembling a curriculum for myself out of what I could find online.

Fortunately, [there is quite a lot](https://buddhistuniversity.net/sources/)!

[Having organized that material for my own studies](https://drive.google.com/open?id=1RJi6bEXa25zizGdsm5evCycYuY6a2D8r) in a way that reminded me fondly of the QMUL library, I started to share that folder with my friends, who in turn encouraged me to build [this website](https://buddhistuniversity.net).

# Studying

There are two primary ways to use the website: taking [our self-paced courses](https://www.buddhistuniversity.net/courses/) or hanging out at [the library](https://www.buddhistuniversity.net/library/).

The library contains all the best content I've found organized [by topic](https://buddhistuniversity.net/tags/). These topical bibliographies are then compiled into [course syllabi](https://buddhistuniversity.net/courses/) which can be studied online or used in your study group or class. There are already students and teachers around the world using the free material here in a variety of ways and I couldn't be prouder!

# Methodology

After reading stuff I find online, I  contemplate what I learned from it and who I’d recommend it to. Only after answering these questions affirmatively do I then squirrel away the e.g. PDF into an appropriate folder on Google Drive.

In this way, my library (like all personal libraries) slowly grew to serve two purposes: 

1. to organize the media for my own safe-keeping, retrieval and revision, and  
2. for others (hello!) to peruse and, hopefully, benefit from.

These two aims find unity in the pride that any book-worm inevitably feels towards their library. As a [map of my mind](https://photos.app.goo.gl/Z8nvMf3Cbup6WA418), this website contains (editorially and structurally) all of my personal biases. **This is a feature not a bug.** I named the elephants which carry my assembled treatises with thought, care, and delight and I hope that, as you explore my library, you will find some of that delight too. 😊 🐘

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

## Reuse

The beauty of Jekyll is that it outputs plain HTML, which you can find in [the repo's "prod" branch](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/prod). This raw html can be reworked in a variety of ways. Feel free to reuse it in any (ethical) way you like or fork the repository.

You can also find [the entire database in Bibtex format on the website](https://buddhistuniversity.net/content.bib), in case that's useful.

# Future Directions

Over the next few years, I would like to expand the University's offerings further and further: into various regional forms of Buddhism, subtler points of Buddhist philosophy, the grand arcs of history, and much, much more. I'd also like to continue to improve the site's design and marketing, so it can be as accessible as possible.

If you'd like to contribute, take a look at [our issues page on GitHub](https://github.com/buddhist-uni/buddhist-uni.github.io/issues) for some open tasks in need of help, or feel free to [email me](mailto:khemarato.bhikkhu@gmail.com) with your idea!

I have tried to select content with "staying power" to avoid, as much as possible, anything that will become outdated in a few years.  This site, while technically a "blog," is **not** another newsfeed of digital ephemera. It is an experiment in slow technology. It is my hope that this curriculum will provide a basis for Buddhist Studies for decades to come.

# Disclaimers

- This repository, like all things, is imperfect and subject to change.
- While I have taken some pains to ensure that everything here is accurate and legal, please know that you use the University at your own risk.
- The various views expressed in each work are the opinions of the respective author(s) and may or may not reflect my own.

# Acknowledgements

A big thank you to [the content sources](https://www.buddhistuniversity.net/sources/), to [Google](https://about.google/) (for hosting [the Drive library](https://drive.google.com/drive/folders/1RJi6bEXa25zizGdsm5evCycYuY6a2D8r)), to [GitHub](https://github.com/about/) for hosting the site, and to all the various [content creators](https://buddhistuniversity.net/authors/) and [publishers](https://buddhistuniversity.net/publishers/) who generously put their work out there for free. It's a testament to Buddhist generosity that such an expansive and outstanding collection can be compiled (almost entirely) from free material.

# Dedication

This curriculum is humbly dedicated to all of my teachers---past, present and future. Especially you.

[![DOI](https://zenodo.org/badge/244081930.svg)](https://zenodo.org/badge/latestdoi/244081930)

