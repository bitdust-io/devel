from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from cms.models import CMSPlugin


GRID_CONFIG = {'COLUMNS': 24, 'TOTAL_WIDTH': 960, 'GUTTER': 20}
GRID_CONFIG.update(getattr(settings, 'DJANGOCMS_GRID_CONFIG', {}))

DJANGOCMS_GRID_CHOICES = [
    ('%s' % i, 'grid-%s' % i) for i in range(1, GRID_CONFIG['COLUMNS']+1)
]


class Grid(CMSPlugin):
    inner = models.BooleanField(_('inner'), default=True, help_text=_('Defines whether the plugin is already inside a grid container or another Multi-column plugin.'))
    custom_classes = models.CharField(_('custom classes'), max_length=200, blank=True)
    translatable_content_excluded_fields = ['custom_classes']

    def __unicode__(self):
        return _(u"%s columns") % self.cmsplugin_set.all().count()


class GridColumn(CMSPlugin):
    size = models.CharField(_('size'), choices=DJANGOCMS_GRID_CHOICES, default='1', max_length=50)
    custom_classes = models.CharField(_('custom classes'), max_length=200, blank=True)
    translatable_content_excluded_fields = ['custom_classes']

    def __unicode__(self):
        return u"%s" % self.get_size_display()
