import structlog
from django.conf import settings
from django.core.mail import send_mail

logger = structlog.get_logger(__name__)


def email_support_request(instance):
    message = f"""
      User: {instance['current_user'].username}
      User Email: {instance['current_user'].email}
      Message: {instance['message']}.
    """
    send_mail(
        f"Support Request from {instance['current_user'].username}",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.DEFAULT_FROM_EMAIL],
        fail_silently=False,
    )
