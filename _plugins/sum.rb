module Jekyll
  module SumFilter
    def sum(input)
        return input.inject(0) do |a,b|
            a.to_i + b.to_i
        end
    end
  end
end

Liquid::Template.register_filter(Jekyll::SumFilter)

