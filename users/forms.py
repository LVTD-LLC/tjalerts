from allauth.account.forms import LoginForm, SignupForm
from django import forms

from hn_jobs.utils import DivErrorList

from .models import CustomUser


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["name", "email"]


class CustomSignUpForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super(CustomSignUpForm, self).__init__(*args, **kwargs)
        self.error_class = DivErrorList


class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.error_class = DivErrorList
