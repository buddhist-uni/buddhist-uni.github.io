module Jekyll
  module GroupByFirstTag

    def items_for_group(groups, name)
      group = groups.find { |g| g['name'] == name }
      if group
        return group['items']
      end
      return []
    end

    def group_by_first_tag(posts, pivot_tag = nil)
      tags = @context['site.tags']
      ret = []
      for rawtag in tags
        items = []
        new_posts = []
        tag = rawtag['slug']
        if tag == pivot_tag
          next
        end
        for post in posts
          if post['tags'].include?(tag)
            items << post
          else
            new_posts << post
          end
        end
        posts = new_posts
        if items.size > 0
          ret << { 'name' => tag, 'items' => items, 'size' => items.size }
        end
      end
      if posts.size > 0
        return [{ 'name' => (pivot_tag or 'misc'), 'items' => posts, 'size' => posts.size }].concat(ret)
      else
        return ret
      end
    end
  end
end

Liquid::Template.register_filter(Jekyll::GroupByFirstTag)
