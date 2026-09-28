module Jekyll
  class RaiseErrorTag < Liquid::Tag
    def initialize(tag_name, text, tokens)
      super
      @text = text.strip
    end

    def render(context)
      # Look up the variable name in the current Liquid context
      error_message = context[@text]
      
      # Fallback to the raw text if the variable isn't found
      error_message = @text if error_message.nil? || error_message.empty?

      raise Exception.new("Build aborted with error: #{error_message}")
    end
  end
end
Liquid::Template.register_tag('raise_error', Jekyll::RaiseErrorTag)
