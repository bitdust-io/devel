from django import forms
from djangocms_grid.models import Grid, GRID_CONFIG, DJANGOCMS_GRID_CHOICES
from django.utils.translation import ugettext_lazy as _

NUM_COLUMNS = [
    (i, '%s' % i) for i in range(0, GRID_CONFIG['COLUMNS'])
]


class GridPluginForm(forms.ModelForm):
    create = forms.ChoiceField(choices=NUM_COLUMNS, label=_('Create Columns'), help_text=_('Create this number of columns inside'))
    create_size = forms.ChoiceField(choices=DJANGOCMS_GRID_CHOICES, label=_('Column size'), help_text=('Width of created columns. You can still change the width of the column afterwards.'))

    class Meta:
        model = Grid
        exclude = ('page', 'position', 'placeholder', 'language', 'plugin_type')
