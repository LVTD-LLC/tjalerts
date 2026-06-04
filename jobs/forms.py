from django import forms
from django.forms import ModelForm

from .models import Alert


class GenericForm(forms.Form):
    who_is_hiring_post_id = forms.CharField()


class CreateAlertForm(ModelForm):
    technology_selected = forms.CharField(max_length=100)

    class Meta:
        model = Alert
        fields = [
            "email",
        ]


class CreateCustomAlertForm(ModelForm):
    class Meta:
        model = Alert
        fields = [
            "name",
            "email",
            "filter",
        ]


class CreateIntentAlertForm(forms.Form):
    intent = forms.CharField(
        min_length=20,
        max_length=1500,
        widget=forms.Textarea,
        error_messages={
            "min_length": "Describe the kind of role you want in a little more detail.",
            "required": "Describe the kind of role you want.",
        },
    )


class ConfirmAlertForm(ModelForm):
    class Meta:
        model = Alert
        fields = ["confirmed"]
