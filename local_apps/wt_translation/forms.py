from django import forms
from django.db.models import Q

from wt_translation.models import MachineTranslator, LanguagePair, \
     TranslationRequest


class TranslationRequestForm(forms.ModelForm):
    def __init__(self, translation_project=None, *args, **kwargs):
        super(TranslationRequestForm, self).__init__(*args, **kwargs)

        if translation_project != None:
            self.translation_project = translation_project

            self.fields['translator'].queryset = MachineTranslator. \
                                                 objects.filter(
                supported_languages__in=LanguagePair.objects.filter(
                Q(source_language=
                  translation_project.project.source_language),
                Q(target_language=translation_project.language)))

    class Meta:
        model = TranslationRequest
        exclude = ('status', 'external_id', 'timestamp',)
