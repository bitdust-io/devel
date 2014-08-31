from django.utils.translation import ugettext_lazy as _

from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool

from .forms import FlashForm
from .models import Flash


class FlashPlugin(CMSPluginBase):
    model = Flash
    name = _("Flash")
    form = FlashForm
    render_template = "cms/plugins/flash.html"

    def render(self, context, instance, placeholder):
        context.update({
            'object': instance,
            'placeholder': placeholder,
        })
        return context

plugin_pool.register_plugin(FlashPlugin)
