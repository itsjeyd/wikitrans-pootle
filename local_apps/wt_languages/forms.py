from django import forms

from wt_languages.models import LanguageCompetancy

class LanguageCompetancyForm(forms.ModelForm):

    class Meta:
        model = LanguageCompetancy
        exclude = ('user','updated')

    def __init__(self, user=None, *args, **kwargs):
        self.user = user
        super(LanguageCompetancyForm, self).__init__(*args, **kwargs)
