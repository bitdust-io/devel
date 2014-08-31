# -*- coding: utf-8 -*-
from cms.models import CMSPlugin
import urllib
import urlparse
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from micawber.exceptions import ProviderNotFoundException, ProviderException
from pyquery import PyQuery
from .oembed_providers import bootstrap


providers = bootstrap()


class OembedVideoPlugin(CMSPlugin):
    oembed_url = models.URLField(verbose_name=_('url'))
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    autoplay = models.BooleanField(default=False)
    show_related = models.BooleanField(default=False, help_text=_('hiding related videos is not supported by Vimeo (you need vimeo plus)'))
    loop = models.BooleanField(default=False, help_text=_('looping is not supported by YouTube'))

    # cached oembed data
    type = models.CharField(max_length=255, blank=True, default='')
    provider = models.CharField(max_length=255, blank=True, default='')
    data = models.TextField(blank=True, default='')
    html = models.TextField(blank=True, default='')

    def __unicode__(self):
        return u"%s" % self.provider

    def clean(self):
        extra = {}
        if self.width:
            extra['maxwidth'] = self.width
        if self.height:
            extra['maxheight'] = self.height
        extra['autoplay'] = self.autoplay
        extra['rel'] = self.show_related
        extra['loop'] = self.loop
        extra['title'] = False  # Vimeo
        extra['byline'] = False  # Vimeo
        extra['portrait'] = False  # Vimeo
        try:
            data = providers.request(self.oembed_url, **extra)
        except ProviderNotFoundException, e:
            raise ValidationError(e.message)
        except ProviderException, e:
            raise ValidationError(e.message)
        if not data['type'] == 'video':
            raise ValidationError('This must be an url for a video. The "%(type)s" type is not supported.' % {'type': data['type']},)
        self.type = data.get('type', '')
        self.provider = data.get('provider_name', '')
        html = data.get('html', '')
        if 'provider_name' in data and self.provider in ['YouTube', 'Vimeo']:
            # dirty special handling of youtube and vimeo.
            # they ignore these parameters over oembed... so we use our own template to render them.
            iframe_html = PyQuery(html)
            url = iframe_html.attr('src')
            params = {
                'autoplay': int(self.autoplay),
                'loop': int(self.loop),
                'rel': int(self.show_related),
                'showinfo': 0,  # YouTube
                'hd': 1,  # YouTube
            }
            url_parts = list(urlparse.urlparse(url))
            query = dict(urlparse.parse_qsl(url_parts[4]))
            query.update(params)
            url_parts[4] = urllib.urlencode(query)
            new_url = mark_safe(urlparse.urlunparse(url_parts))
            aspect_ratio = float(data.get('width')) / float(data.get('height'))
            if self.width and not self.height:
                width = self.width
                height = int(float(self.width) / aspect_ratio)
            elif self.height and not self.width:
                height = self.height
                width = int(float(self.height) * aspect_ratio)
            elif self.width and self.height:
                width = self.width
                height = self.height
            else:
                width = data.get('width')
                height = data.get('height')
            context = {
                'url': new_url,
                'width': width,
                'height': height,
            }
            from django.template.loader import render_to_string
            html = render_to_string('djangocms_oembed/plugins/video_iframe.html', context)
        self.html = html
        self.data = data


