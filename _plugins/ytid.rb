module Jekyll
  module YTIDFilter
    def ytid(input)
      regex = /(?:youtube(?:-nocookie)?\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})/
      match = regex.match(input)
      if match && match[1].is_a?(String)
        match[1]
      else
        nil
      end
    end
  end
end

Liquid::Template.register_filter(Jekyll::YTIDFilter)

