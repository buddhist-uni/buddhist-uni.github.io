module Jekyll
  module UnaccentFilter
    def unaccent(input)
      input.to_s.unicode_normalize(:nfd).gsub(/\p{Mn}/, '')
    end
  end
end

Liquid::Template.register_filter(Jekyll::UnaccentFilter)
