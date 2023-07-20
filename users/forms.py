from allauth.account.forms import LoginForm, SignupForm
from django.forms import ModelForm

from hn_jobs.utils import DivErrorList

from .models import Subscriber


class CustomSignUpForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super(CustomSignUpForm, self).__init__(*args, **kwargs)
        self.error_class = DivErrorList


class CustomLoginForm(LoginForm):
    def __init__(self, *args, **kwargs):
        super(CustomLoginForm, self).__init__(*args, **kwargs)
        self.error_class = DivErrorList


class CreateAlertForm(ModelForm):
    class Meta:
        model = Subscriber
        fields = [
            "email",
            "technology_selected",
        ]


class UpdateAlertForm(ModelForm):
    class Meta:
        model = Subscriber
        fields = ["confirmed"]
