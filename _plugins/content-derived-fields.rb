module Jekyll
  module ContentDerivedFields
    def self.get_featured_post_for_item(item)
        slug = item.data['slug']
        for p in item.site.posts.docs
          if p.content.include?(slug)
            return p
          end
        end
        return nil
    end

    def self.base_stars_for_item(item)
        if item.data['status'].to_s == 'rejected'
          return 1
        end
        if not item.data['course']
          return 2
        end
        if item.data['status'].to_s != 'featured'
          return 3
        end
        return 4
     end

    Jekyll::Hooks.register :content, :pre_render do |item|
        # content_path
        item.data['content_path'] = item.relative_path[9...-3]

        # stars and featuring post
        item.data['stars'] = base_stars_for_item(item)
        item.data['featured_post'] = nil
        if item.data['stars'] == 4 and (item.data['external_url'] or item.data['file_links'] or item.data['drive_links'])
            item.data['featured_post'] = get_featured_post_for_item(item)
            if item.data['featured_post']
                item.data['stars'] = 5
            end
        end

        # page_count (won't be set if no "pages" field present)
        item.data['page_count'] = item.data['pages'].to_i if item.data['pages']
        if item.data['pages'].to_s.include?('--')
          a, b = item.data['pages'].to_s.split('--').map(&:to_i)
          item.data['page_count'] = b - a + 1
        end
    end
  end
end

