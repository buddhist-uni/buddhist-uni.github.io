Contribution Guide
==================

Thank you for your interest in contributing to the Open Buddhist University!

If you're looking to report a problem or propose a change, feel free to simply [create an issue](https://github.com/buddhist-uni/buddhist-uni.github.io/issues/new) or [open a Pull Request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

If you'd like to get more involved, but aren't sure where to begin, some project ideas are listed on [the issues page](https://github.com/buddhist-uni/buddhist-uni.github.io/issues?q=is%3Aissue+label%3A%22good+first+issue%22+is%3Aopen).
Feel free to [email me](mailto:theopenbuddhistuniversity@gmail.com) if you have any questions!

For an introduction to the codebase, read on:

## Table of Contents

- [The Code](#the-code)
  - [Running the site locally](#running-the-site-locally)
  - [The Source](#the-source-code)
- [Reuse](#reuse)


## The Code

OBU is a static HTML website built with [Jekyll](https://jekyllrb.com/) and served by [GitHub Pages](https://pages.github.com/).

### Running the site locally

To run the site locally:

Install [Node](https://nodejs.org/en/download/package-manager/), [Ruby](https://www.ruby-lang.org/en/documentation/installation/), and [Bundler](https://bundler.io/).
Then run:

```bash
git clone https://github.com/buddhist-uni/buddhist-uni.github.io.git
cd buddhist-uni.github.io
npm ci
bash scripts/install-deps.bash
bundle install
bundle exec jekyll serve -tI
```

Note that you can add the `--config _config.yml,_quick_build.yml` build flag to `jekyll serve` for a faster, but partial build of the site.

For more information on the build options, see [the Jekyll docs](https://jekyllrb.com/docs/usage/) and for the production build script, see [build.yaml](https://github.com/buddhist-uni/buddhist-uni.github.io/blob/main/.github/workflows/build.yaml).

### The Source Code

For this section of the guide, we'll walk through OBU's [source tree](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main).

You can think of each of the `_folders` in the source code as representing individual object types.
Each folder is a different "table" in a hardcoded "database":

- [_authors](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_authors) - Each author with their own page.
- [_content](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_content) - All of the individual works in the library, divided by `category` based on the type. Each content item has a number of [metadata fields](https://jekyllrb.com/docs/front-matter/) listing its bibliographic information (e.g. `pages`). The site templates use this information to render the HTML pages of the website.
- [_categories](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_categories) - This folder houses the `index.html` pages for the `/content/*` folders and contains a little metadata about the categories, such as their English titles.
- [_courses](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_courses) - The University's courses.
- [_data](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_data) - Site configuration [variables](https://jekyllrb.com/docs/datafiles/).
- [_drafts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_drafts) - Unpublished courses or tags.
- [_includes](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_includes) - A Jekyll folder which houses the site's [reusable UI components](https://jekyllrb.com/docs/includes/).
- [_journals](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_journals) - Periodicals which get their own page.
- [_layouts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_layouts) houses the [html page templates](https://jekyllrb.com/docs/layouts/).
- [_plugins](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_plugins) is not a collection but rather contains native Ruby extensions for quickly running complex algorithms or for dynamically generating content.
- [_posts](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_posts) are the [blog posts](https://jekyllrb.com/docs/posts/) which make up the newsletter.
- [_publishers](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_publishers) are the publishers which I have granted their own hub page.
- [_sass](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_sass) contains [the site's css](https://jekyllrb.com/docs/assets/).
- [_series](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_series) - Are collections of `_content` items that were published as part of a `number`ed `series` (specified by fields on the content item)
- [_tags](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_tags) - The bibliographic topics, arranged in a directed, ontological graph via the `parents` field.
- [_tests](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/_tests) - A couple of pages with [Integration Tests](https://buddhistuniversity.net/tests/content). Currently, only the "content" tests are actively monitored.

Lastly,
- [.github/workflows](https://github.com/buddhist-uni/buddhist-uni.github.io/tree/main/.github/workflows) contains my [GitHub Actions](https://docs.github.com/en/actions) [Workflow files](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions) which build the site and check for broken links.

## Reuse

The beauty of Jekyll is that it outputs plain HTML, which you can reuse in a variety of ways.
[The entire database can also be found in Bibtex format here](https://buddhistuniversity.net/content.bib), in case that's helpful, for example for importing into an academic reference manager.

**Feel free to reuse this website in any (ethical) way you like** consistent with [the attached MIT License](https://obu.mit-license.org/).

A slightly out-of-date backup of the site's source code can be found at:

[![DOI](https://zenodo.org/badge/244081930.svg)](https://zenodo.org/badge/latestdoi/244081930)

