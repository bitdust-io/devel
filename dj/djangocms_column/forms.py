from django import forms
from djangocms_column.models import MultiColumns, WIDTH_CHOICES
from django.utils.translation import ugettext_lazy as _

class MultiColumnForm(forms.ModelForm):
    NUM_COLUMNS = (
        (0, "0"),
        (1, "1"),
        (2, "2"),
        (3, "3"),
        (4, "4"),
        (5, "5"),
        (6, "6"),
        (7, "7"),
        (8, "8"),
        (9, "9"),
        (10, "10"),
    )


    create = forms.ChoiceField(choices=NUM_COLUMNS, label=_("Create Columns"), help_text=_("Create this number of columns"))
    create_width = forms.ChoiceField(choices=WIDTH_CHOICES, label=_("Column width"), help_text=("Width of created columns. You can still change the width of the column afterwards."))


    class Meta:
        model = MultiColumns
        exclude = ('page', 'position', 'placeholder', 'language', 'plugin_type')
