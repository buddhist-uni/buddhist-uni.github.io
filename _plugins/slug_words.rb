module Jekyll
  module SlugWordsFilter
    # "The Pāli Suttas" => "-the-pali-sutta-", for whole-word matching that ignores accents and plurals
    def slug_words(input)
      "-#{Utils.slugify(input.to_s.unicode_normalize(:nfd).gsub(/\p{Mn}/, ''))}-".gsub('s-', '-')
    end
  end
end

Liquid::Template.register_filter(Jekyll::SlugWordsFilter)
