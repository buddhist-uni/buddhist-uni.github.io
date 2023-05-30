module Jekyll
  module ContentDerivedFields
    # Constants for the Expected Timespent Model
    # y: expected time
    # x: total time
    # s: horizontal asymptote (max expected time)
    # m: vertical asymptote (inv growth rate)
    # c: x-axis intercept
    # f = c/m
    # Full equation is:
    #   y = s[f+(x*(1-f)/(x-m))]
    # Values were chosen by a combination of intuition
    # and validation against video watch data in GA4
    # Numbers are therefore highly approximate
    @@etm = {
        max_expected_mins: 70.0,
        max_expected_mins_featured: 105.0,
        x_inter: -0.2,
        y_asymt: -165.0,
        mins_per_page: 2.0
    }
    @@etm[:offset] = @@etm[:x_inter] / @@etm[:y_asymt]
    def self.expected_mins(item)
        mins = item.data['minutes'].to_f
        if item.data['page_count'] and mins == 0
            mins = item.data['page_count'].to_f * @@etm[:mins_per_page]
        end
        if mins == 0
            return nil
        end
        ratio = (1.0 - @@etm[:offset]) / (mins - @@etm[:y_asymt])
        ratio *= mins
        ratio += @@etm[:offset]
        if item.data['status'].to_s == 'featured'
            return @@etm[:max_expected_mins_featured] * ratio
        else
            return @@etm[:max_expected_mins] * ratio
        end
    end

    def self.get_featured_post_for_item(item)
        slug = item.data['slug'].to_s
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
        item.data['free'] = !!(item.data['external_url'] or item.data['file_links'] or item.data['drive_links'])
        if item.data['stars'].to_i == 4 and item.data['free']
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

        # set the expected value of downloading this item
        item.data['expected_mins'] = expected_mins(item)
        if item.data['expected_mins']
            stars = item.data['stars'].to_f
            if item.data['category'].to_s == 'canon'
                stars += 1.0
            end
            item.data['expected_value'] = 0.02 * stars * item.data['expected_mins'].to_f
        else
            item.data['expected_value'] = item.data['base_value'].to_f
            if item.data['status'].to_s == 'featured'
                item.data['expected_value'] *= 2.0
            end
        end
        if not item.data['free']
            if item.data['excerpt_url']
                item.data['expected_value'] /= 2.0
            else
                item.data['expected_value'] /= 100.0 # chance someone actually seeks this out
            end
        end
        item.data['expected_value'] = item.data['expected_value'].to_f.round(3)
    end
  end
end

