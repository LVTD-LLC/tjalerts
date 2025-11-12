from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail

from hn_jobs.utils import get_tjalerts_logger
from jobs.models import Email

logger = get_tjalerts_logger(__name__)


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


def send_test_sponsorship_email(email_obj_id):
    from jobs.utils import create_stripe_checkout_session_for_post

    try:
        email_obj = Email.objects.select_related("company", "post").get(id=email_obj_id)
    except Email.DoesNotExist:
        logger.error("Email object not found", email_obj_id=email_obj_id)
        return "Email object not found"

    site_domain = Site.objects.get_current().domain
    post_url = f"https://{site_domain}{email_obj.post.get_absolute_url()}"
    company_name = email_obj.company.name
    greeting = f"Hi {email_obj.name}," if email_obj.name else "Hi there,"

    try:
        checkout_url = create_stripe_checkout_session_for_post(email_obj.post, post_url, post_url)
    except Exception as e:
        logger.error(
            "Failed to create Stripe checkout session for test email",
            error=str(e),
            post_id=email_obj.post.id,
        )
        return f"Failed to create checkout session: {str(e)}"

    company_mention = f" at {company_name}" if company_name else ""
    subject_company = f" - {company_name}" if company_name else ""
    subject = f"[TEST] Your Job Post is Now on TJAlerts{subject_company}"

    message = f"""[THIS IS A TEST EMAIL - Original recipient: {email_obj.email}]

{greeting}

Your job post{company_mention} just got indexed on TJ Alerts—a searchable database of tech jobs that attracts 1,300+ unique visitors monthly.

Here's your listing:
{post_url}

Want to stand out? For $500/month, you can sponsor your post and get:
• Featured placement at the top of all search results
• Highlighted styling with a "Sponsored" badge
• Maximum visibility to active job seekers

Here's what sponsored listings look like:
- Homepage: https://{site_domain}/static/vendors/images/sponsored-home-page.png
- Search results: https://{site_domain}/static/vendors/images/sponsored-jobs-search.png

Ready to boost your visibility?
👉 Sponsor your post now: {checkout_url}

Best,
TJAlerts Team
"""

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            ["rasul@lvtd.dev"],
            fail_silently=False,
        )

        logger.info(
            "Test sponsorship email sent",
            original_email=email_obj.email,
            post_id=email_obj.post.id,
            company=company_name,
            sent_to="rasul@lvtd.dev",
        )
        return f"Test sponsorship email sent to rasul@lvtd.dev (original: {email_obj.email})"

    except Exception as e:
        logger.error(
            "Failed to send test sponsorship email",
            error=str(e),
            email=email_obj.email,
            post_id=email_obj.post.id,
        )
        return f"Failed to send test email: {str(e)}"
