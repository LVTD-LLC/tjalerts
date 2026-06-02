from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from hn_jobs.posthog_events import capture_request_event, capture_user_event
from hn_jobs.utils import add_users_context, get_tjalerts_logger
from jobs.models import Alert

from .models import CustomUser

logger = get_tjalerts_logger(__name__)


def get_or_create_user_email_address(user):
    has_primary_email = EmailAddress.objects.filter(user=user, primary=True).exists()
    emailaddress, created = EmailAddress.objects.get_or_create(
        user=user,
        email=user.email,
        defaults={"primary": not has_primary_email, "verified": False},
    )

    if created:
        logger.warning("Email address record created for confirmation resend", user_id=user.id, email=user.email)

    return emailaddress


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

    def form_valid(self, form):
        response = super().form_valid(form)
        capture_user_event(
            self.object,
            "user profile updated",
            properties={"updated_fields": sorted(form.changed_data)},
        )
        return response


def resend_email_confirmation_email(request):
    user = request.user

    adapter = get_adapter(request)
    emailaddress = get_or_create_user_email_address(user)

    adapter.send_confirmation_mail(request, emailaddress, signup=False)
    capture_request_event(request, "email confirmation resent", properties={"email_verified": emailaddress.verified})

    return redirect("settings")
