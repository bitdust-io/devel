from django.db import models
from django.utils.translation import ugettext_lazy as _

from cms.models import CMSPlugin, Page
try:
    from cms.models import get_plugin_media_path
except ImportError:
    def get_plugin_media_path(instance, filename):
        """
        See cms.models.pluginmodel.get_plugin_media_path on django CMS 3.0.4+ for information
        """
        return instance.get_media_path(filename)
from cms.utils.compat.dj import python_2_unicode_compatible


@python_2_unicode_compatible
class Teaser(CMSPlugin):
    """
    A Teaser
    """
    title = models.CharField(_("title"), max_length=255)

    image = models.ImageField(
        _("image"), upload_to=get_plugin_media_path, blank=True, null=True)

    page_link = models.ForeignKey(
        Page, verbose_name=_("page"),
        help_text=_("If present image will be clickable"), blank=True,
        null=True, limit_choices_to={'publisher_is_draft': True})

    url = models.CharField(
        _("link"), max_length=255, blank=True, null=True,
        help_text=_("If present image will be clickable."))

    description = models.TextField(_("description"), blank=True, null=True)
    
    def __str__(self):
        return self.title
    
    search_fields = ('description',)
