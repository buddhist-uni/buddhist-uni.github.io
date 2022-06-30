module Jekyll
  module MaxFilter
    def max(input)
        return input.inject(0) do |a,b|
            a.to_liquid.to_i>=b.to_liquid.to_i ? a : b
        end
    end
  end
end

Liquid::Template.register_filter(Jekyll::MaxFilter)

