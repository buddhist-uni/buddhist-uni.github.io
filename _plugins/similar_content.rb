require 'fc'

module Jekyll
  class SimilarContentFooterTag < Liquid::Tag

    def initialize(tag_name, text, tokens)
      super
      @similars = FastContainers::PriorityQueue.new(:min)
    end
    
    # Straight copy-paste from Jekyll::Tags::IncludeTag
    # This really should have been a public, static method there
    # so I could call it directly, but oh well, it's open source, so... #YOLO
    def load_cached_partial(path, context)
        context.registers[:cached_partials] ||= {}
        cached_partial = context.registers[:cached_partials]

        if cached_partial.key?(path)
          cached_partial[path]
        else
          unparsed_file = context.registers[:site]
            .liquid_renderer
            .file(path)
          begin
            cached_partial[path] = unparsed_file.parse(File.read(path, **context.registers[:site].file_read_opts))
          rescue Liquid::Error => e
            e.template_name = path
            e.markup_context = "included " if e.markup_context.nil?
            raise e
          end
        end
    end

    def render(v)
        config = v["site.data.content"]
        for i in 1..config["similar_count"]
            @similars.push({}, 0)
        end
        category = v["category"]
        if category.nil? or category.is_a? String then
            category = v["include_content.category"]
            category = v["site.categories"].find{|c| c.data["slug"] == category}
        end
        category = category.to_liquid.to_h
        for cofefe in v["site.content"]
            candidate = cofefe.to_liquid.to_h
            if candidate["status"] == "rejected" or candidate["path"] == v["include_content.path"] then
                next
            end
            score = rand + rand
            score *= config["s_i"]
            denom = config["d_i"]
            if candidate["subcat"] and v["include_content.subcat"] == candidate["subcat"] then
                score += config["scms"]
            end
            if v["include_content.course"] then
                if v["include_content.course"] == candidate["course"] then
                    score += config["ccms"]
                end
                if candidate["tags"]&.size&.nonzero? then
                    if candidate["tags"].include? v["include_content.course"] then
                        score += config["ctms"]
                    end
                end
            end
            if candidate["course"] then
                denom += config["cdms"]
                if v["include_content.tags"]&.include? candidate["course"] then
                    score += config["ctms"]
                end
            end
            if candidate["tags"]&.size&.nonzero? then
                denom += candidate["tags"].size * config["tdms"]
                if v["include_content.tags.size"] then
                    for t in v["include_content.tags"]
                        if candidate["tags"].include? t then
                            score += config["ttms"]
                        end
                    end
                end
            end
            if candidate["authors"]&.size&.nonzero? and v["include_content.authors.size"]&.nonzero? then
                denom += candidate["authors"].size * config["adms"]
                for a in v["include_content.authors"]
                    if candidate["authors"].include? a then
                        score += config["aams"]
                    end
                end
            end
            if v["include_content.category"] == candidate["category"] then
                score *= config["ccmm"]
            elsif category["similars"].to_a.include? candidate["category"] then
                score *= config["scmm"]
            end
            if candidate["status"] == "featured" then
                score *= config["fcmm"]
            elsif not candidate.key? "course" then
                score *= config["tsmm"]
            end
            score *= score / denom
            # It's a Heap, not a Stack
            @similars.push(candidate, score)
            # This pop (the min) ensures we keep the highest scoring candidates
            @similars.pop
        end
        ret = StringIO.new
        ret << '<div class="similar_content_footer"><p>You may also be interested in:</p><ul>'
        final_list = Array.new(config["similar_count"])
        # Manually load and render the simple_content_title include
        simple_content_title = load_cached_partial("_includes/simple_content_title.html", v)
        @similars.pop_each { |obj, score|
            v.stack do
                v["include"] = {"content" => obj}
                sct = simple_content_title.render!(v)
                final_list.push("<li>#{sct}</li>")
            end
        }
        # The Heap pops off the smallest first, so we use an Array to reverse the order
        final_list.reverse_each {|s| ret << s }
        ret << '<li><a href="/content/random">Or A Random Item from the Library...</a></li></ul></div>'
        return ret.string
    end
  end
end

Liquid::Template.register_tag('similar_content', Jekyll::SimilarContentFooterTag)

