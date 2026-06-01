from allauth.account.signals import email_confirmed, user_logged_in, user_signed_up
from django.dispatch import receiver

from hn_jobs.posthog_events import capture_request_event, capture_user_event


@receiver(user_signed_up)
def capture_user_signed_up(request, user, **kwargs):
    capture_user_event(user, "user signed up", properties={"provider": _provider_from_kwargs(kwargs)})


@receiver(user_logged_in)
def capture_user_logged_in(request, user, **kwargs):
    capture_request_event(request, "user logged in", properties={"provider": _provider_from_kwargs(kwargs)})


@receiver(email_confirmed)
def capture_email_confirmed(request, email_address, **kwargs):
    capture_request_event(
        request,
        "email confirmed",
        properties={
            "user_id": str(email_address.user_id),
        },
    )


def _provider_from_kwargs(kwargs):
    sociallogin = kwargs.get("sociallogin")
    if not sociallogin:
        return "email"

    return getattr(getattr(sociallogin, "account", None), "provider", "") or "social"
