import logging

from allauth.account.utils import send_email_confirmation
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from hn_jobs.utils import add_users_context
from jobs.models import Alert

from .models import CustomUser

logger = logging.getLogger(__file__)


class UserSettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    login_url = "account_login"
    model = CustomUser
    fields = ["name", "email"]
    success_message = "User Profile Updated"
    success_url = reverse_lazy("settings")
    template_name = "account/settings.html"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        add_users_context(context, user, self)

        context["alerts"] = Alert.objects.filter(email=user.email)

        return context


def resend_email_confirmation_email(request):
    user = request.user
    send_email_confirmation(request, user, user.email)

    return redirect("settings")
