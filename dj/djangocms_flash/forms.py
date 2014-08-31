from django import forms

from .models import Flash


class FlashForm(forms.ModelForm):
    class Meta:
        model = Flash
        exclude = ('page', 'position', 'placeholder', 'language',
                   'plugin_type')