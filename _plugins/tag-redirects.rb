module Jekyll
  # Topic pages moved from /tags/ to /topics/, so each old URL gets a page that redirects
  class TagRedirects < Generator
    def generate(site)
      (site.collections['tags'].docs.map(&:url) << '/topics/').each do |to|
        page = PageWithoutAFile.new(site, site.source, '', 'tag-redirect.html')
        page.data.merge!('layout' => 'none', 'sitemap' => false, 'permalink' => to.sub('/topics', '/tags'))
        page.content = <<~HTML
          <!DOCTYPE html>
          <html lang="en">
          <meta charset="utf-8">
          <title>Redirecting…</title>
          <link rel="canonical" href="#{site.config['url']}#{to}">
          <meta http-equiv="refresh" content="0; url=#{to}">
          <meta name="robots" content="noindex">
          <script>location.replace("#{to}" + location.search + location.hash)</script>
          <a href="#{to}">This page has moved</a>
          </html>
        HTML
        site.pages << page
      end
    end
  end
end
