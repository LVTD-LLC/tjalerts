from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django_q.tasks import async_task

from .models import Alert, Subscriber
from .utils import create_alert_message


def send_alert(subscriber: Subscriber):
    current_date = datetime.now()
    week_number = (current_date.day - 1) // 7 + 1
    formatted_date = current_date.strftime("%B %Y, Week {}".format(week_number))

    send_mail(
        f"Your Job Alerts for {subscriber.technology_selected} - {formatted_date}",
        create_alert_message(subscriber),
        settings.DEFAULT_FROM_EMAIL,
        [subscriber.email],
        fail_silently=False,
    )

    Alert.objects.create(subscriber=subscriber)

    return f"Email was sent to {subscriber.email}"


def find_subs_to_alert():
    seven_days_ago = datetime.now() - timedelta(days=7)

    waiting_subscribers = (
        Subscriber.objects.filter(confirmed=True).exclude(alert__created__gte=seven_days_ago).distinct()
    )

    count = 0
    for subscriber in waiting_subscribers:
        async_task(
            send_alert,
            subscriber,
            hook="jobs.hooks.print_result",
            group="send_alert",
        )
        count += 1

    return f"{count} alerts have been sent."


def send_confirmation_email(instance, confirmation_url):
    message = f"""
      Hey there,

      Thanks a ton for the alert subscription for {instance["technology_selected"]} jobs.

      To make sure you start receving weekly alerts,
      please confirm your subscription by clicking the link below:

      {confirmation_url}
    """
    send_mail(
        "Confirm Your Job Alert Subscription",
        message,
        settings.DEFAULT_FROM_EMAIL,
        [instance["email"]],
        fail_silently=False,
    )
