from django import forms


class GenericForm(forms.Form):
    who_is_hiring_post_id = forms.CharField()
