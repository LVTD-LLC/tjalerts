import logging

from django.core.mail import send_mail

logger = logging.getLogger(__file__)


def email_support_request(instance):
    message = f"""
      User: {instance['current_user'].username}
      User Email: {instance['current_user'].email}
      Message: {instance['message']}.
    """
    send_mail(
        f"Support Request from {instance['current_user'].username}",
        message,
        "rasul@builtwithdjango.com",
        ["rasul@builtwithdjango.com"],
        fail_silently=False,
    )
