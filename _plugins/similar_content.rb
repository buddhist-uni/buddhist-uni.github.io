require 'fc'
require 'set'

module Jekyll
  class SimilarContentFooterTag < Liquid::Tag
    @@config = nil
    @@parents_for_tag = nil
    @@similar_cats = nil
    @@content = nil
    @@content_for_tag = nil
    @@canon_tags = nil

    def dataInit(v)
      puts "Prefetching data for similar_content footer..."
      @@config = v["site.data.content"]
      @@parents_for_tag = {}
      @@similar_cats = {}
      @@content = []
      @@canon_tags = Set.new
      @@content_for_tag = Hash.new { |h, k| h[k] = Set.new }
      for cofefe in v["site.categories"]
        cat = cofefe.to_liquid.to_h
        @@similar_cats[cat['slug']] = cat['similars']
      end
      for cofefe in v["site.tags"]
        tag = cofefe.to_liquid.to_h
        @@parents_for_tag[tag["slug"]] = tag["parents"]
        if tag["is_canon"]
            @@canon_tags << tag["slug"]
        end
      end
      for cofefe in v["site.content"]
        c = cofefe.to_liquid.to_h
        if c["status"] == "rejected" then
            next
        end
        @@content << c
        for tag in c['tags']
          @@content_for_tag[tag] << c
        end
        @@content_for_tag[c['course']] << c if c['course']
        for tag in getBookTags(v, c)
            @@content_for_tag[tag] << c
        end
      end
      puts "Done prefetching"
    end

    def getCandidates(v, include_content, include_content_book_tags)
      candidates = Set[]
      course = include_content['course']
      tags = include_content['tags']
      if course then
        candidates.merge(@@content_for_tag[course])
      end
      for tag in tags
        candidates.merge(@@content_for_tag[tag])
      end
      for tag in include_content_book_tags
        candidates.merge(@@content_for_tag[tag])
      end
      if candidates.size <= @@config['candidate_min'] then
        puts "similar_content warning: only found %d likely candidates for %s" % [[candidates.size-1,0].max, include_content['url']]
        return @@content
      else
        return candidates
      end
    end

    def getBookTags(v, c)
        if c['from_book']
            b = v['site.content'].find { |x| x['slug'] == c['from_book'] && ['monographs', 'booklets'].include?(x['category']) }
            raise "book %s not found" % c['from_book'] if b.nil?
            b = b.to_liquid.to_h
            return b['tags']
        else
            return []
        end
    end

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
        if @@config.nil? then
            dataInit(v)
        end
        for i in 1..@@config["similar_count"]
            @similars.push({}, 0)
        end
        include_content = v["include_content"].to_liquid.to_h
        include_content_book_tags = getBookTags(v, include_content)
        for candidate in getCandidates(v, include_content, include_content_book_tags)
            if candidate['path'] == include_content['path'] then
                next
            end
            score = rand + rand
            score *= @@config["s_i"]
            denom = @@config["d_i"]
            if candidate["subcat"] and include_content["subcat"] == candidate["subcat"] then
                score += @@config["scms"]
            end
            candidate_book_tags = getBookTags(v, candidate)
            if include_content["course"] then
                if include_content["course"] == candidate["course"] then
                    score += @@config["ccms"]
                else
                    if candidate["tags"].include? include_content["course"] then
                        score += @@config["ctms"]
                    else
                        if candidate_book_tags.include? include_content["course"] then
                            score += @@config["ctms"] * @@config["btmm"]
                        else
                            ps = @@parents_for_tag[include_content["course"]]
                            if ps then
                                if ps.include? candidate["course"] then
                                    score += @@config["tpms"]
                                else
                                    for p in ps
                                        if candidate["tags"]&.include? p then
                                            score += @@config["tpms"]
                                            break
                                        end
                                    end
                                end
                            end
                        end
                    end
                end
            end
            if candidate["course"] then
                denom += @@config["cdms"]
                if include_content["tags"]&.include? candidate["course"] then
                    score += @@config["ctms"]
                elsif include_content_book_tags.include? candidate["course"] then
                    score += @@config["ctms"] * @@config["btmm"]
                end
            end
            if candidate["tags"]&.size&.nonzero? then
                denom += candidate["tags"].size * @@config["tdms"]
                denom += candidate_book_tags.size * @@config["tdms"] * @@config["btmm"]
                candidate_tags = candidate["tags"].map { |t| [t, false]} + candidate_book_tags.map { |t| [t, true] }
                candidate_tags.each do |t, is_book_tag|
                    ttms = @@config["ttms"]
                    if @@canon_tags.include? t and candidate["category"] == "canon"
                        ttms *= @@config["ctmm"]
                        denom -= @@config["tdms"] * (1.0 - @@config["ctmm"])
                    elsif is_book_tag
                        ttms *= @@config["btmm"]
                    end
                    if include_content["tags"].include? t then
                        score += ttms
                    else
                        if include_content_book_tags.include? t then
                          score += ttms * @@config["btmm"]
                        elsif @@parents_for_tag[t] then
                            for p in @@parents_for_tag[t]
                                if include_content["tags"].include? p then
                                    score += @@config["tpms"]
                                    break
                                elsif include_content["course"] == p then
                                    score += @@config["tpms"]
                                    break
                                elsif include_content_book_tags.include? p then
                                    score += @@config["tpms"] * @@config["btmm"]
                                    break
                                end
                            end
                        end
                    end
                end
            end
            if candidate["authors"]&.size&.nonzero? and v["include_content.authors.size"]&.nonzero? then
                denom += candidate["authors"].size * @@config["adms"]
                for a in include_content["authors"]
                    if candidate["authors"].include? a then
                        score += @@config["aams"]
                    end
                end
            end
            if include_content["category"] == candidate["category"] then
                score *= @@config["ccmm"]
            elsif @@similar_cats[include_content["category"]].include? candidate["category"] then
                score *= @@config["scmm"]
            end
            if candidate["status"] == "featured" then
                score *= @@config["fcmm"]
            elsif not candidate.key? "course" then
                score *= @@config["tsmm"]
            end
            score *= score / denom
            # It's a Heap, not a Stack
            @similars.push(candidate, score)
            # This pop (the min) ensures we keep the highest scoring candidates
            @similars.pop
        end
        ret = StringIO.new
        ret << '<div class="similar_content_footer"><p>You may also be interested in:</p><ul>'
        final_list = Array.new(@@config["similar_count"])
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

