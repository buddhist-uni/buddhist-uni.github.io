---
title: Welcome to the Open Buddhist University
---

# Epigraphs

> On the third day of the year 47 BC, the most renowned library of antiquity burned to the ground.  
>  
> Throughout the history of humanity, only one refuge kept books safe from war and conflagration: the walking library, an idea that occurred to the grand vizier of Persia, Abdul Kassem Ismael, at the end of the tenth century.  
>  
> This prudent and tireless traveler kept his library with him. One hundred and seventeen thousand books aboard four hundred camels formed a caravan a mile long. The camels were also the catalogue  
>  
> ~ "January 3rd" from *Children of the Days* by Eduardo Galeano

> Alas! Asaṅga spent twelve years in the wilderness, practising meditation.  
> Without achieving any success in meditation,  
> He has instead compiled these treatises  
> As a burden for an elephant’s back.  
>  
> ~ [Vasubandhu](https://www.lotsawahouse.org/tibetan-masters/khenpo-shenga/life-of-vasubandhu)

# Introduction

This GitHub Page is my personal library of Buddhist media.

As a resource, a library has two audiences (and thus two priorities): 

1. First, a library is there to organize one's media for their safe-keeping, retrieval and study. 
2. Second, a library is there for others (hello, friend!) to peruse and, at best, benefit from

These two practical aims find unity in the pride that any book-worm feels towards their library: 

**A library is a reflection of its creator**---who they are and what they'd like to be.

Given that I'm a Buddhist monk, naturally my personal library represents a course of study in Buddhism.

In translating this proud, ancient tradition to the digital age, different constraints and possibilities emerged. Reflecting on the structure of the internet, I opted to express myself in a giant [mind map](https://photos.app.goo.gl/Z8nvMf3Cbup6WA418). 

As a map of my mind, this library contains (editorially and structurally) my own biases. This is a feature not a bug. I named my camels with a great deal of thought, care, and delight and I hope that, as you explore my library, you will feel some of that delight too. 😊 🐪

# Using the Site

There are two primary ways to study here: taking [the courses](https://buddhist-uni.github.io/courses/) or hanging out at [the library](https://buddhist-uni.github.io/library/).

The library contains all the best content I've found on the internet, [organized primarily by topic](https://buddhist-uni.github.io/tags/).

The courses provide contextualized and sequential walk-throughs of the same content, organized into progressive undergraduate-style syllabi. These lesson plans may be studied as-is or reworked for use by your study group or class. There are already teachers around the world using these syllabi as a starting point for their courses, and I couldn't be prouder!

# Structure of the Source Code

You can think of each of the `_folders` in the main folder as individual database tables. Each represents a different kind of object in the (hardcoded) "database."

- [_authors](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_authors) - Each author with their own page.
- [_content](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_content) - All of the individual works in the library, divided by `category` based on the type. Each content item has a number of [metadata fields](https://jekyllrb.com/docs/front-matter/) listing its bibliographic information (e.g. `pages`) in Bibtex format, or linking the entry out to its file (e.g. `external_url`) or linking it to its internal groups (e.g. `authors`). Conventionally, I put raw strings in `"Quotes"` and I represent links to other objects as `unquoted-slugs`. The templates then use these slugs to fetch the related objects at page render time.
- [content](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/content) - This (un-underscored) folder merely houses `index.html` pages for `/content/*` and doesn't represent any actual content.
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

For more information, see [the Jekyll docs](https://jekyllrb.com/docs/).

# Disclaimers

- This repository, like all other things, is subject to change.
- While I have taken some pains to ensure that everything here is trustworthy and legal, please know that you use the University facilities at your own risk.
- The views expressed in each work are the opinions of the author(s) and may not reflect my own.

# Contributions

If you have any feedback or would like to volunteer, please feel free to email me at any time with your thoughts and we can take it from there. I'm especially looking for design help at the moment, so if you're a web designer interested in volunteering, please contact me!

# Acknowledgements

A big thank you to [our sources](https://buddhist-uni.github.io/sources/), to Google (for hosting [the Drive library](https://drive.google.com/drive/folders/1RJi6bEXa25zizGdsm5evCycYuY6a2D8r)), to GitHub for hosting the site, and to all the various content creators and publishers who generously put their work out for free. It's a testament to Buddhist generosity that such an expansive and outstanding collection can be compiled (almost entirely) from free material.

# Dedication

To all my teachers---past, present and future. Especially you.

***

To start exploring, [pick a topic](https://buddhist-uni.github.io/tags/) that interests you.

To run the site locally, clone the repo, then run "[`bundle`](https://bundler.io/) ` install`" and "`bundle run ` [`jekyll`](https://jekyllrb.com/) ` serve`"

Be aware that it takes about ten minutes to build the site.
