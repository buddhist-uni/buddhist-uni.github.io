---
title: "Collection Development Policy"
---

This document outlines the method and criteria used for adding new content to the library.

This document is primarily for onboarding new contributors, but it may also be of interest to users and patrons of the library.

## Table of Contents
- [Overview](#overview)
- [Inclusion Criteria](#inclusion-criteria)
- [Acceptance Levels](#acceptance-levels)
- [The Structure of the Collection](#ontology)
- [Conclusion](#conclusion)

## Overview

The OBU Library serves **English speakers** with a basic education and an **interest in Buddhism**.

Its collections are **entirely digital** and are a combination of self-hosted files (on GitHub and Google Drive) and links to resources accessible on the broader internet.
Each entry in the library is ideally hosted in two different locations (e.g. at Archive.org and on Google Drive) for redundancy and accessibility.

The collection does not strive to host a copy or link to every work ever published about Buddhism.
That would be undesirable, even if it were possible.
The collection instead strives to offer a high-quality, representative selection in keeping with the University's mission to provide a free, undergraduate-style curriculum in Buddhist Studies.

### The Pipeline

The usual procedure for ingesting new content is as follows:

1. Content freely available on the internet or directly given to OBU gets uploaded to [the ingestion folder on Google Drive](https://drive.google.com/drive/folders/16-z8CRbEfo3L8DTUpR76Sq1uCs4Am5b_).
2. That content is then deduped and sorted into "unreviewed" buckets on G-Drive by subject (if you'd like to become a reviewer for a particular subject, send a message and I can invite you to the appropriate subfolder).
3. A reviewer then reviews a piece for acceptance or rejection. (See details below).
4. Accepted pieces (rank3+) are moved to the appropriate folder in [the public Google Drive library](https://drive.google.com/drive/folders/1RJi6bEXa25zizGdsm5evCycYuY6a2D8r) based on what subject that piece teaches (rejected items are archived in Google Drive).
5. When a topical folder on Drive has reached a state of maturity, its contents are added one-by-one to [the site's `_content` library](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_content) and the (Drive) folder is added as a new [`_tag`](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_tags)
6. When that tag has reached a level of maturity (with a diverse set of works providing good coverage), its content is reviewed, moved around if necessary, and organized into a syllabus on Google Docs. When ready, this draft syllabus is added as a new [`_course`](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/master/_courses) of the same name. (See [the open issues on GitHub](https://github.com/buddhist-uni/buddhist-uni.github.io/labels/writing) for courses awaiting a volunteer if you're interested in writing one!)

## Inclusion Criteria

For inclusion in the OBU library, a given work should be:

1. Truthful and accurate
2. In beautiful and charismatic English
3. Espousing the Dharma and wholesome values
4. Adding a unique perspective
5. On an important topic of wide interest to Buddhists
6. Available for free
7. From a reputable source
8. Difficult to find online

The above factors are to be taken "on balance" such that a deficiency in one area may be compensated for by strength in another.
For example, there are a few [works of fiction](https://buddhistuniversity.net/search/?q=%2Bis%3Afiction) in the library which fail IC1, but whose craft (IC2) and wholesome messages (IC3) make up for their lack of literal truth.
The teachings of Chögyam Trungpa, however, fail IC7 and IC8 so thoroughly as to be inadmissible regardless of the works' other merits.

Note that IC4 (uniqueness) can be applied retroactively.
If a better (more up-to-date, etc) work is found covering the same topic as an older work, than that older work should be archived in favor of the better one.
[*In the Hope of Nibbana*](https://buddhistuniversity.net/content/monographs/in-the-hope-of-nibbana_king-winston) is an example of such a downranked work.

Works that would otherwise not be added to the site for their low score on IC2 and/or IC4 should still be added as rank2 works (see below) if they score highly on IC8 to ensure they remain available online.

## Acceptance Levels

Rather than a binary "accepted or rejected" status, items in the OBU library are given a 1–5 star rating based on their score on the Inclusion Criteria above.

- One-star pieces fail multiple IC categories and are never proactively added to the site. Their files are kept in a private archive on Google Drive of rejected works.
- Two-star pieces fail at most one IC category but receive only lackluster scores on the rest. This is the most common score for items we review. Such pieces are typically not added to the website, though occasionally a borderline rank3 work can be added (especially if it scores well on IC8). Such works are placed in [this Google Drive folder](https://drive.google.com/drive/folders/1Ih3PRUKLHaWzVvoVVkCRuaCzbsjreQXa) and are labeled "📦 Archived" on the site (see the table below).
- Three-star pieces fail at most one IC category and receive strong marks in one or two areas. This is the most common designation for accepted works. They are accepted into the appropriate subfolder on the public-facing Google Drive library and must be added to the site if that folder has already been added.
- Four-star pieces fail at most one IC category but receive very strong marks in multiple other areas. A four-star review means that this piece is highly recommended and should be added to the website right away (unless its IC5 score is particularly low).
- Five-star pieces must fail none of the IC categories and must receive strong marks across the board. These are quite rare. They are not identified immediately, but are selected from the pool of recent four-star additions when it comes time to write the next blog post (usually every couple months).

The following table summarizes the five levels and how they work on the website:

| Ranking | Label | Code | Effect | Example |
|---|---|---|---|---|
| rank1 | 📦 Deprecated | `status: rejected` and `reason: [explanation]` | The work will be delisted everywhere on the website except for search, where it will be downranked. | [The Ancient Path to Enlightenment](https://buddhistuniversity.net/content/av/ancient-path-to-enlightenment_dabei) ([code](https://github.com/buddhist-uni/buddhist-uni.github.io/blob/master/_content/av/ancient-path-to-enlightenment_dabei.md)) was delisted after the video was taken down. |
| rank2 | 📦 Archived | `course: nil` | Archived works are downranked in search and content recommendations. | [One Teacher, Many Traditions](https://buddhistuniversity.net/content/monographs/buddhism-one-teacher-many-traditions_dalai-lama-thunten-chodron) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/master/_content/monographs/buddhism-one-teacher-many-traditions_dalai-lama-thunten-chodron.md)) Failed IC6 and IC4, but scored highly enough on the rest to deserve an "honorable mention" as a rank2 piece |
| rank3 | [none] | `course: [value]` | An accepted work will be featured on the `/tags/[value]` page. | [The Buddha's Remains](https://buddhistuniversity.net/content/articles/buddhas-remains_wallis-glenn) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/master/_content/articles/buddhas-remains_wallis-glenn.md)) Somewhat dry (IC2), niche (IC5) and Googlable (IC8), this otherwise-solid piece was accepted as a standard entry |
| rank4 | ⭐ Recommended | `status: featured` | These works are upranked in search and content recommendations and they get highlighted in content lists. | [The Buddha's Genitals](https://buddhistuniversity.net/content/essays/politics-of-the-buddhas-genitals_sujato) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/master/_content/essays/politics-of-the-buddhas-genitals_sujato.md)) This piece, in contrast, hits solid marks across the board, being a unique and interesting take buried in an online forum. |
| rank5 | 🏅 Featured | both of the above and a link to the work in a blog post | Same as `rank4` but are also highlighted in the newsletter. | [Arhat Invitation during the Song](https://buddhistuniversity.net/content/articles/arhat-invitation-in-the-song_joo-ryan) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/master/_content/articles/arhat-invitation-in-the-song_joo-ryan.md)) ([blog post](https://buddhistuniversity.net/blog/2021/11/19/wandering)) This piece was very interesting and more important than its unassuming title might suggest. It was therefore deemed worthy of featuring in the newsletter. |

Note: to view a piece's ranking directly on the website, click the "Bibtex Data" button and look for the `ranking` field.

## Ontology

As a keen user of this library, it's worth taking some time to familiarize yourself with [the folder structure on Drive](https://drive.google.com/drive/folders/1-zOQ53Le2uYZp6lCjuLZUA38H6zvlrzf).
Contributors to the library should be able to answer basic questions about the collection such as:

1. Where can I find a copy of the Jātaka tales?[^jataka]
2. Where is "The Human World" folder?[^world]
3. What are the subcategories under Buddhist Philosophy?[^philosophy]

Having this structure in your head will help you navigate the collection efficiently and helps reviewers direct works to the correct folders.

### Choosing a Folder

Once a work has been accepted for inclusion, the reviewer must select the folder (and, if it's being added to the website, `tags`) to which this work belongs.

This selection is more art than science, but a few questions are helpful to ask when making the decision:

- What _discourse_ is this work contributing to?
- What does the piece _claim_ to be about (e.g. in its title)?
- Is it actually about something else?
- What did _I personally_ learn from it?
- I would enthusiastically recommend this to someone interested in what?
- Could I imagine this being assigned reading in an undergrad course about ______?

The collection is already quite large, so it's best to be conservative and place works in the smallest conceivable category.
For example, a work about Buddhist Cosmology should be placed in "Cosmology" not in "Philosophy".

### Adding to the site

When a work is added into the website, its `course` field is set to the slug of the folder it was accepted into on Google Drive.
The work may also be tagged with additional `tags` which mark other topics the work is about.

Tags should, but don't have to, correspond to folders on Drive.
If they do, however, a work should not be tagged with both a folder **and** that folder's parent. Obviously a work about `thai` Buddhism is also about `theravada` and a work about `philosophy` is also about right `view`. Tags should mark wildly different places a work may have been added: for example `sutta` and `lay` for a work about Pāḷi discourses to lay people.

## Conclusion

If you have any additional questions about the library not answered in this document, please feel free to [email me](mailto:khemarato.bhikkhu@gmail.com) at any time.

Thank you for your interest in the library and may you be blessed by the blessings of the Triple Gem. 🙏

💎💎💎

### Answers to the Ontology Quiz

[^jataka]: Forms->Indian->Stories->Jataka

[^world]: Inside the "[Cosmology](https://drive.google.com/drive/folders/1-3P5u65MsX2gjuN46xqNV2dJxoAxrQDQ)" folder

[^philosophy]: Right View and Right Thought
