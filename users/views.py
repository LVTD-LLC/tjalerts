from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.views.generic import UpdateView

from hn_jobs.posthog_events import capture_request_event, capture_user_event
from hn_jobs.utils import add_users_context, get_tjalerts_logger

from .api_keys import rotate_user_api_key
from .forms import UserSettingsForm
from .models import CustomUser

logger = get_tjalerts_logger(__name__)


class UserSettingsView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    login_url = "account_login"
    model = CustomUser
    form_class = UserSettingsForm
    success_message = "User Profile Updated"
    success_url = reverse_lazy("settings")
    template_name = "account/settings.html"

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        add_users_context(context, self.request.user, self)
        context["api_key_record"] = getattr(self.request.user, "api_key", None)

        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        capture_user_event(
            self.object,
            "user profile updated",
            properties={"updated_fields": sorted(form.changed_data)},
        )
        return response


@never_cache
@require_POST
@login_required(login_url="account_login")
def generate_api_key(request):
    with transaction.atomic():
        key_record, api_key = rotate_user_api_key(request.user)
        transaction.on_commit(lambda: capture_user_event(request.user, "api key rotated"))

        context = {
            "form": UserSettingsForm(instance=request.user),
            "api_key_record": key_record,
            "generated_api_key": api_key,
        }
        add_users_context(context, request.user)
        return render(request, "account/settings.html", context)


def resend_email_confirmation_email(request):
    user = request.user

    adapter = get_adapter(request)
    emailaddress = EmailAddress.objects.get_for_user(user, user.email)

    adapter.send_confirmation_mail(request, emailaddress, signup=False)
    capture_request_event(request, "email confirmation resent", properties={"email_verified": emailaddress.verified})

    return redirect("settings")
