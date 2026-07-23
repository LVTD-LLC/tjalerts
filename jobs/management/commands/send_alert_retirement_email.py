from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand
from django.db.models.functions import Lower
from django.utils import timezone

from jobs.models import Alert, AlertEmailSend

SUBJECT = "A change to Tech Job Alerts"
BODY = """Hi,

I’m sorry to say that I’m winding down the email alert and digest feature.

Tech Job Alerts will be pivoting a little. Instead of sending job emails, I plan to make the underlying job data available through an API, MCP, and CLI.

Your existing alerts will no longer send emails, and you don’t need to do anything. This message is a one-time service notice about the change.

Thank you for using Tech Job Alerts and for trusting me with your inbox.

Rasul
"""


def recipient_emails():
    cutoff = timezone.now() - timedelta(days=30)
    active_alert_emails = (
        Alert.objects.filter(confirmed=True, unsubscribed=False)
        .exclude(email="")
        .annotate(recipient=Lower("email"))
        .values_list("recipient", flat=True)
    )
    recent_recipient_emails = (
        AlertEmailSend.objects.filter(created__gte=cutoff)
        .exclude(email="")
        .annotate(recipient=Lower("email"))
        .values_list("recipient", flat=True)
    )
    return active_alert_emails.union(recent_recipient_emails).order_by("recipient")


class Command(BaseCommand):
    help = "Send a one-time service notice to active or recent alert recipients"

    def add_arguments(self, parser):
        parser.add_argument(
            "--send",
            action="store_true",
            help="Send the messages. Without this flag, only report the recipient count.",
        )

    def handle(self, *args, **options):
        recipients = recipient_emails()
        recipient_count = recipients.count()

        if not options["send"]:
            self.stdout.write(
                f"Dry run: found {recipient_count} unique recipients. "
                "No email was sent. Re-run with --send to deliver the notice."
            )
            return

        sent_count = 0
        connection = get_connection(fail_silently=False)
        with connection:
            for email in recipients.iterator(chunk_size=500):
                message = EmailMessage(
                    subject=SUBJECT,
                    body=BODY,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                    connection=connection,
                )
                sent_count += message.send(fail_silently=False)

        self.stdout.write(self.style.SUCCESS(f"Sent {sent_count} emails."))
