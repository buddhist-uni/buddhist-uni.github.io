source "https://rubygems.org"

# Hello! This is where you manage which Jekyll version is used to run.
# When you want to use a different version, change it below, save the
# file and run `bundle install`. Run Jekyll with `bundle exec`, like so:
#
#     bundle exec jekyll serve
#
# This will help ensure the proper Jekyll version is running.
# Happy Jekylling!
gem "jekyll", "~> 4.3"
# our sass code is currently written for converter v3
gem "jekyll-sass-converter", ">= 3.0", "< 4.0"

# If you want to use GitHub Pages, remove the "gem "jekyll"" above and
# uncomment the line below. To upgrade, run `bundle update github-pages`.
# gem "github-pages", group: :jekyll_plugins

# If you have any plugins, put them here!
group :jekyll_plugins do
  gem "jekyll-feed", github: 'buddhist-uni/jekyll-feed', branch: 'collection-tags'
  gem "jekyll-sitemap", "~> 1.4.0"
  gem "jekyll-seo-tag", github: "buddhist-uni/jekyll-seo-tag", ref: '9d3cf62'
  gem "jekyll-last-modified-at", github: "buddhist-uni/jekyll-last-modified-at", branch: 'post-date'
  gem 'jekyll-include-cache'
end

# For my own ruby code
gem "priority_queue_cxx", "~> 0.3.4"

# Windows does not include zoneinfo files, so bundle the tzinfo-data gem
gem "tzinfo-data", platforms: [:mingw, :mswin, :x64_mingw, :jruby]

# Performance-booster for watching directories on Windows
gem "wdm", "~> 0.1.0" if Gem.win_platform?

gem "pry"

gem "webrick", "~> 1.7"
