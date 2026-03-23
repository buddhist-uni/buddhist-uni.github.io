# Sass Migration Guide for Volunteers

This document explains why we still use Sass `@import` in this project, what will break in the future, and how to migrate safely before Dart Sass 3.0.0.

## Why this matters

Sass has deprecated `@import` and old global built-in behavior. The Sass team has said these will be removed in Dart Sass 3.0.0.

That means this project eventually needs to move to the module system (`@use` and `@forward`) to stay compatible.

## Current project status

This repo uses Jekyll + `jekyll-sass-converter` (v3.x), which supports modern Sass.

However, our stylesheets are currently written in a **global-scope pattern** that depends on `@import` behavior:

- entry files in `assets/css/` import shared files (for example `support`, `minima`, `nimitta`)
- many partials in `_sass/` use variables and mixins without namespacing
- those variables/mixins are expected to be globally available via import order

When we switch to `@use`, those globals are no longer implicit, so compilation errors appear (undefined variable/mixin/function, namespace issues).

## Why migration tools failed in this repo

Running the Sass migrator directly on Jekyll entry files can fail because those files include Jekyll front matter (`---`), which the migrator does not parse as valid Sass.

So even with correct intent, the migrator can fail before applying changes.

## What volunteers should do (recommended approach)
## BTW this is Dylan here - I had AI write this based on contextual investigation. I'm not ordering anyone around
## But this is good context from AI for our knowledge - but don't feel pressured, I just need this here.


### 1) Keep `@import` for now in production branches

Do not force a half-migration that breaks Jekyll builds.

### 2) Migrate in small, reviewable phases

Perform migration in small PRs so each step can be verified:

1. **Normalize partial dependencies**
   - make each partial explicitly load what it needs
   - reduce hidden global coupling

2. **Introduce module boundaries**
   - create one or more module entry files in `_sass/`
   - export shared tokens/mixins using `@forward`

3. **Convert consumers**
   - replace `@import` with `@use`
   - update references to namespaced form (for example `tokens.$banner-color`, `mixins.media-query(...)`)

4. **Update Jekyll entry files last**
   - once internal partials are module-ready, switch top-level stylesheet imports

### 3) Keep behavior stable while migrating

- avoid changing visual design and spacing during module conversion
- avoid unrelated refactors in migration PRs
- keep PRs focused on one group of files at a time

## Common pitfalls to avoid

- Converting only one file to `@use` while its dependencies still rely on globals
- Mixing old and new patterns without clear module boundaries
- Running migrator on front-matter entry files in `assets/css/` and expecting clean output

## Suggested migration checklist for each PR

- [ ] No new undefined variable/mixin/function errors
- [ ] No namespace collisions
- [ ] CSS output remains visually unchanged on key pages
- [ ] Scope of changes is limited and documented
- [ ] Follow-up files are listed for the next PR

## Practical note on timeline

Dart Sass 3.0.0 is the milestone where deprecated `@import` behavior is expected to be removed. Exact release timing may change, so we should treat this as a pending compatibility requirement and migrate incrementally now.

## Short version

- We are not blocked by Jekyll version.
- We are blocked by legacy global Sass structure.
- Migration is still necessary.
- The safe path is incremental module refactoring, not one-shot conversion.
