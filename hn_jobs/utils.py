import json
import math
from urllib.parse import unquote

import posthog
from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList

from jobs.models import Technology


def get_tjalerts_logger(name):
    """This will add a `tjalerts` prefix to logger for easy configuration."""
    import structlog

    return structlog.getLogger(f"tjalerts.{name}")


logger = get_tjalerts_logger(__name__)


def add_users_context(context, user, self=None):
    try:
        context["email_verified"] = EmailAddress.objects.get_for_user(user, user.email).verified
    except EmailAddress.DoesNotExist as e:
        logger.error("Email Error", error=e)

    if self:
        posthog_cookie = self.request.COOKIES.get(f"ph_{posthog.project_api_key}_posthog")
        if posthog_cookie:
            cookie_dict = json.loads(unquote(posthog_cookie))
            if cookie_dict["distinct_id"] and self.request.user.is_authenticated:
                posthog.alias(cookie_dict["distinct_id"], self.request.user.email)

    return context


def floor_to_thousands(x):
    return int(math.floor(x / 1000.0)) * 1000


def floor_to_tens(x):
    return int(math.floor(x / 10.0)) * 10


class DivErrorList(ErrorList):
    def __str__(self):
        return self.as_divs()

    def as_divs(self):
        if not self:
            return ""
        return f"""
            <div class="p-4 my-4 border border-red-600 border-solid rounded-md bg-red-50">
              <div class="flex">
                <div class="flex-shrink-0">
                  <!-- Heroicon name: solid/x-circle -->
                  <svg class="w-5 h-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
                  </svg>
                </div>
                <div class="ml-3 text-sm text-red-700">
                      {''.join(['<p>%s</p>' % e for e in self])}
                </div>
              </div>
            </div>
         """  # noqa: E501


def validate_technology_selected(value):
    technologies = Technology.objects.values_list("name", flat=True)
    if value not in technologies:
        raise ValidationError(f"{value} is not a valid technology name.")
