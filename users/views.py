import logging

from allauth.account.utils import send_email_confirmation
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, UpdateView
from django_q.tasks import async_task

from hn_jobs.utils import add_users_context
from jobs.models import Technology

from .forms import CreateAlertForm, UpdateAlertForm
from .models import CustomUser, Subscriber
from .tasks import find_subs_to_alert, send_confirmation_email

logger = logging.getLogger(__file__)


def validate_technology_selected(value):
    technologies = Technology.objects.values_list("name", flat=True)
    if value not in technologies:
        raise ValidationError(f"{value} is not a valid technology name.")


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

        return context


def resend_email_confirmation_email(request):
    user = request.user
    send_email_confirmation(request, user, user.email)

    return redirect("settings")


class AlertCreateView(SuccessMessageMixin, CreateView):
    template_name = "account/create-alert.html"
    model = Subscriber
    form_class = CreateAlertForm
    success_url = reverse_lazy("home")
    success_message = "Thanks for subscribing :) Check your emails to confirm!"

    def form_valid(self, form):
        try:
            validate_technology_selected(form.cleaned_data["technology_selected"])
        except ValidationError:
            messages.add_message(self.request, messages.WARNING, "Please use a Technology from the dropdown list.")
            return redirect("home")

        if Subscriber.objects.filter(email=form.instance.email).exists():
            messages.add_message(self.request, messages.WARNING, "An alert already exists for this email.")
            return redirect("home")

        confirmation_url = self.request.build_absolute_uri(reverse("confirm_subscription", args=[form.instance.id]))
        async_task(send_confirmation_email, form.cleaned_data, confirmation_url)
        return super(AlertCreateView, self).form_valid(form)


class AlertUpdateView(SuccessMessageMixin, UpdateView):
    model = Subscriber
    form_class = UpdateAlertForm
    template_name = "account/subscription-confirmation.html"
    success_url = reverse_lazy("home")
    success_message = "Thanks for confirming :) You will receive your alerts soon!"

    def form_valid(self, form):
        response = super(AlertUpdateView, self).form_valid(form)
        async_task(find_subs_to_alert)

        return response
