from cms.models import CMSPlugin
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

if hasattr(settings, "COLUMN_WIDTH_CHOICES"):
    WIDTH_CHOICES = settings.COLUMN_WIDTH_CHOICES
else:
    WIDTH_CHOICES = (
        ('10%', _("10%")),
        ('25%', _("25%")),
        ('33.33%', _('33%')),
        ('50%', _("50%")),
        ('66.66%', _('66%')),
        ('75%', _("75%")),
        ('100%', _('100%')),
    )

class MultiColumns(CMSPlugin):
    """
    A plugin that has sub Column classes
    """
    def __unicode__(self):
        return _(u"%s columns") % self.cmsplugin_set.all().count()


class Column(CMSPlugin):
    """
    A Column for the MultiColumns Plugin
    """

    width = models.CharField(_("width"), choices=WIDTH_CHOICES, default=WIDTH_CHOICES[0][0], max_length=50)

    def __unicode__(self):
        return u"%s" % self.get_width_display()

