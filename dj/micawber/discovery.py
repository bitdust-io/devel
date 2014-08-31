try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from micawber.exceptions import ProviderException
from micawber.providers import Provider


class Finder(Provider):
    def __init__(self, endpoint=None, open_graph=False, search_attrs=None, **kwargs):
        super(Finder, self).__init__(endpoint, **kwargs)
        self.open_graph = open_graph
        self.search_attrs = search_attrs or dict(
            rel='alternate', type='application/json+oembed',
        )

    def request(self, url, **extra_params):
        response = self.fetch(url)
        if not response:
            raise ProviderException('Unable to fetch %s' % url)

        soup = BeautifulSoup(response)
        head = soup.find('head')
        if not head:
            return

        link_tag = head.find('link', self.search_attrs)
        if link_tag:
            href = link_tag.get('href')
            encoded_params = self.encode_params(url, **extra_params)
            if '?' in href:
                href = '%s&%s' % (href.rstrip('&'), encoded_params)
            else:
                href = '%s?%s' % (href, encoded_params)
            response = self.fetch(href)
            if response:
                return self.handle_response(response, url)
            else:
                raise ProviderException('Unabled to fetch %s' % url)
        elif not self.open_graph:
            raise ProviderException('No oembed <link> tag found for %s' % url)

        return self.search_og(url, head)

    def search_og(self, url, head):
        tag_or_gtfo = lambda t: head.find('meta', {'property': 'og:%s' % t})

        img_meta = tag_or_gtfo('image')
        title_meta = tag_or_gtfo('title')
        if img_meta:
            title = title_meta and title_meta.get('content') or url
            return dict(type='photo', url=img_meta.get('content'), title=title)
        raise ProviderException('No open graph tags found on %s' % url)
