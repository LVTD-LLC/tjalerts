import math

import structlog
from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList

from hn_jobs.posthog_events import alias_request_user, distinct_id_for_user
from jobs.models import Technology


def get_tjalerts_logger(name):
    """This will add a `tjalerts` prefix to logger for easy configuration."""

    return structlog.get_logger(f"tjalerts.{name}")


logger = get_tjalerts_logger(__name__)


def build_absolute_site_url(path="/"):
    if not path.startswith("/"):
        path = f"/{path}"

    return f"{settings.SITE_URL}{path}"


def site_metadata(request):
    user = getattr(request, "user", None)
    return {
        "SITE_URL": settings.SITE_URL,
        "SENTRY_BROWSER_CONFIG": {
            "dsn": settings.SENTRY_BROWSER_DSN if settings.SENTRY_ENABLE_BROWSER else "",
            "environment": settings.ENVIRONMENT,
            "release": settings.SENTRY_RELEASE,
            "siteUrl": settings.SITE_URL,
            "tracesSampleRate": settings.SENTRY_BROWSER_TRACES_SAMPLE_RATE,
            "replaysSessionSampleRate": settings.SENTRY_BROWSER_REPLAYS_SESSION_SAMPLE_RATE,
            "replaysOnErrorSampleRate": settings.SENTRY_BROWSER_REPLAYS_ON_ERROR_SAMPLE_RATE,
            "enableLogs": settings.SENTRY_ENABLE_LOGS,
        },
        "ENVIRONMENT": settings.ENVIRONMENT,
        "POSTHOG_API_KEY": settings.POSTHOG_API_KEY,
        "POSTHOG_HOST": settings.POSTHOG_HOST,
        "POSTHOG_ENABLED": settings.POSTHOG_ENABLED,
        "POSTHOG_DISTINCT_ID": distinct_id_for_user(user),
    }


def add_users_context(context, user, self=None):
    try:
        context["email_verified"] = EmailAddress.objects.get_for_user(user, user.email).verified
    except EmailAddress.DoesNotExist as e:
        logger.warning("Email Error", error=e)

    if self:
        alias_request_user(self.request)

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
