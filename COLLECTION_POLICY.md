---
title: "Collection Development Policy"
---

This document outlines the method and criteria used for adding new content to the library.

This document is primarily for onboarding new contributors, but it may also be of interest to patrons of the library.

## Table of Contents
- [Overview](#overview)
- [Inclusion Criteria](#inclusion-criteria)
- [Acceptance Levels](#acceptance-levels)
- [The Structure of the Collection](#ontology)
- [Conclusion](#conclusion)

## Overview

The OBU Library serves **English speakers** with at least a **basic education** and an **interest in Buddhism**.
It takes, to the extent possible, **the pan-sectarian, historical perspective** championed by such contemporary practitioner/scholars as [Bhante Analayo](https://buddhistuniversity.net/authors/analayo).

The Open Buddhist University collections are **entirely digital** and are a combination of self-hosted files (on [GitHub](https://github.com/buddhist-uni?tab=repositories&q=&type=source&language=html) and [Google Drive](https://drive.google.com/open?id=1NRjvD6E997jdaRpN5zAqxnaZv0SM-SOv)) and links to [resources accessible on the broader internet](https://buddhistuniversity.net/sources/).
Each file in the library is ideally hosted in multiple locations (e.g. at Archive.org and on Google Drive) for redundancy and accessibility.

The collection does not strive to host a copy or link to every work ever published about Buddhism.
That would undesirable even if it were possible.
The collection instead strives to offer a high-quality, representative selection in keeping with the University's mission **to provide a free, undergraduate-style curriculum in Buddhist Studies with a focus on [Early Buddhism](https://web.archive.org/web/20231130212016if_/https://www.buddhistinquiry.org/wp-content/uploads/2023/11/Early-Buddhism.pdf) to the English-speaking world.**

To that end, works found on the internet are accepted into the library on a five-point scale and are sorted into subtopics (aka "folders" or "tags") for easy access. The rest of this document will outline how that is done.

### The Pipeline

The usual procedure for ingesting new content is as follows:

1. Free content is [found online](https://buddhistuniversity.net/sources/) and added to [the ingestion queue on Google Drive](https://drive.google.com/drive/folders/1PXmhvbReaRdcuMdSTuiHuWqoxx-CqRa2).
2. That content is then sorted by subject area.
3. A reviewer then evaluates the pieces in their subject area.
4. Accepted pieces are moved to the appropriate folders in [the public Google Drive library](https://drive.google.com/drive/folders/1NRjvD6E997jdaRpN5zAqxnaZv0SM-SOv) based on what subject they teach and rejected items are archived.
5. When a topical folder on Drive has reached a state of maturity, its contents are added one-by-one to [the site's `_content` library](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_content) and the (Drive) folder is added as a new "[tag](https://buddhistuniversity.net/tags/)" on the website.
6. When a tag has a diverse set of works, its contents are reviewed again and organized into a course syllabus. (See [the open issues on GitHub](https://github.com/buddhist-uni/buddhist-uni.github.io/labels/writing) for courses currently awaiting a volunteer if you're interested in writing one!)

## Inclusion Criteria (ICs)

For inclusion in the OBU library, a given work should be:

1. Truthful and accurate
2. In beautiful and charismatic English
3. Espousing the Dharma and wholesome values
4. Adding a unique perspective
5. On an important topic of wide interest to Buddhists
6. Available for free
7. From a reputable source
8. Difficult to find elsewhere online

The above factors are to be taken "on balance" such that a deficiency in one area may be compensated for by strength in another.
For example, there are a few [works of fiction](https://buddhistuniversity.net/search/?q=%2Bis%3Afiction) in the library which fail IC1 (truthfulness), but whose craft (IC2) and wholesome messages (IC3) make up for their lack of literal truth.
On the other hand, the teachings of Chögyam Trungpa, for example, are so disreputable (IC7) and widely publicized elsewhere (IC8) as to be inadmissible to our library, regardless of his works' potential other merits.

Note that works are subject to reevaluation.
If a better (more up-to-date, etc) work is found covering the same topic as an older work, for example, then the older work should be archived in favor of the newer one.
[*In the Hope of Nibbana*](https://buddhistuniversity.net/content/monographs/in-the-hope-of-nibbana_king-winston) is a good example of such a work which was downranked after [better work](https://buddhistuniversity.net/content/booklets/nourishing-the-roots_bodhi) was found.

Works that would otherwise not be added to the site for their low score on IC2 and/or IC4 should still be added as rank2 works (see below) if they score highly on IC8 to ensure that they remain available online.

## Acceptance Levels

Rather than a binary "accepted or rejected" status, items in the OBU library are given a 1–5 star rating based on their score on the Inclusion Criteria above.

- Five-star pieces must fail none of the IC categories and must receive strong marks across the board. These are quite rare. They are not identified immediately, but are selected from the pool of recent four-star additions when it comes time to write the next blog post (usually every couple months). Five-star pieces are featured in the newsletter and are recommended for everyone.
- Four-star pieces fail at most one IC category and receive strong marks in multiple areas. A four-star review means that this piece is highly recommended to anyone interested in the topic and should be added to the website right away unless its IC5 score is particularly low.
- Three-star pieces fail at most one IC category and receive strong marks in one or two areas. This is the most common designation for accepted works. They are accepted into the appropriate subfolder on the public-facing Google Drive library and must be added to the site if that folder has already been added as a tag. Three-star pieces are recommended for those seriously studying the given topic.
- Two-star pieces fail at most one IC category but receive only lackluster scores on the rest. This is the most common score for the items we review. Such pieces are typically not added to the website, though occasionally a borderline rank3 work can be added to the site (especially if it scores well on IC8). Such works are placed in [this Google Drive folder](https://drive.google.com/drive/folders/1Hb3_iSK9ISvY9BbSM-gkjWgKF3eVkiLi) and are labeled "📦 Archived" on the site (see the table below).
- One-star pieces fail multiple IC categories and are never proactively added to the site. Their files are kept in a private archive on Google Drive of rejected works.

The following table summarizes the five levels and how they work on the website:

| Ranking | Label | Code | Effect | Example |
|---|---|---|---|---|
| rank1 | 📦 Deprecated | `status: rejected` and `reason: [explanation]` | The work will be delisted everywhere on the website except for search, where it will be downranked. | [The "Tipitaka" website](https://buddhistuniversity.net/content/reference/tipitaka) ([code](https://github.com/buddhist-uni/buddhist-uni.github.io/blob/main/_content/reference/tipitaka.md)) was delisted after [the new DPR website](https://buddhistuniversity.net/content/reference/dpr) was launched. |
| rank2 | 📦 Archived | `course: nil` | Archived works are downranked in search and content recommendations. | [One Teacher, Many Traditions](https://buddhistuniversity.net/content/monographs/buddhism-one-teacher-many-traditions_dalai-lama-thunten-chodron) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/main/_content/monographs/buddhism-one-teacher-many-traditions_dalai-lama-thunten-chodron.md)) Failed IC6, but scored well enough on the rest to deserve an "honorable mention" as a rank2 piece |
| rank3 | [none] | `course: [value]` | An accepted work will be featured on the `/tags/[value]` page. | [The Buddha's Remains](https://buddhistuniversity.net/content/articles/buddhas-remains_wallis-glenn) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/main/_content/articles/buddhas-remains_wallis-glenn.md)) Somewhat dry (IC2), niche (IC5) and Googlable (IC8), this otherwise-solid piece was accepted as a standard entry |
| rank4 | ⭐ Recommended | `status: featured` | These works are upranked in search and content recommendations and they get highlighted in content lists. | [The Buddha's Genitals](https://buddhistuniversity.net/content/essays/politics-of-the-buddhas-genitals_sujato) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/main/_content/essays/politics-of-the-buddhas-genitals_sujato.md)) This piece, in contrast, hits solid marks across the board, being a unique and interesting take buried in an online forum. |
| rank5 | 🏅 Best of | both of the above and a link to the work in a blog post | Same as `rank4` but are also highlighted in the newsletter. | [Arhat Invitation during the Song](https://buddhistuniversity.net/content/articles/arhat-invitation-in-the-song_joo-ryan) ([code](https://raw.githubusercontent.com/buddhist-uni/buddhist-uni.github.io/main/_content/articles/arhat-invitation-in-the-song_joo-ryan.md)) ([blog post](https://buddhistuniversity.net/blog/2021/11/19/wandering)) This piece was very interesting and more important than its unassuming title might suggest. It was therefore deemed worthy of featuring in the newsletter. |

Note: to view a piece's ranking directly on the website, click the "Bibtex Data" button and look for the `ranking` field.

## Ontology

As a valued contributor to / keen user of this library, it's worth familiarizing yourself with [the library's folder/tag structure](https://buddhistuniversity.net/tag-ontology/).
This will allow you to answer basic questions about the collection such as:

1. Where are the Jātaka tales?[^jataka]
2. Where is Tibetan Buddhism?[^tibetan]
3. What are the subcategories under Buddhist Philosophy?[^philosophy]

Having this structure in your head will help you navigate the collection efficiently and direct works to their correct folders/tags.

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
For example, a work about heaven and hell realms should be placed in "Cosmology" rather than (the more general) "Philosophy" folder.

### Adding to the site

When a work is added into the website, its `course` field is set to the slug of the folder it was accepted into on Google Drive.
The work may also be tagged with additional `tags` which mark other topics the work is about.

See [the "Adding items" wiki page](https://github.com/buddhist-uni/buddhist-uni.github.io/wiki/Adding-items-to-the-library) for more information.

## Conclusion

If you have any additional questions about the library not answered in this document, please feel free to [email me](mailto:khemarato.bhikkhu@gmail.com) at any time.

Thank you for your interest in the library and may you be blessed by the blessings of the Triple Gem. 🙏

💎💎💎

### Answers to the Ontology Quiz

[^jataka]: Buddhism->Forms->Indian->Rebirth Stories->Jataka

[^tibetan]: Buddhism->Forms->Mahayana->Vajrayana

[^philosophy]: Right View and Right Thought
