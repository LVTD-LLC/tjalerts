from django import forms
from django.forms import Form


class SupportForm(Form):
    # user = forms.CharField()
    message = forms.CharField(widget=forms.Textarea)

    def __init__(self, current_user=None, *args, **kwargs):
        self.current_user = current_user
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["current_user"] = self.current_user
        return cleaned_data
