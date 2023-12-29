from django import forms
from django.forms import ModelForm

from .models import Alert


class CreateAlertForm(ModelForm):
    technology_selected = forms.CharField(max_length=100)

    class Meta:
        model = Alert
        fields = [
            "email",
        ]


class UpdateAlertForm(ModelForm):
    class Meta:
        model = Alert
        fields = ["confirmed"]
