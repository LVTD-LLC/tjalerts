from django.contrib.sites.models import Site
from django.utils import timezone

from jobs.models import Post

from .models import Subscriber


def create_alert_message(subscriber: Subscriber) -> str:
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    posts = Post.objects.filter(
        created__gte=seven_days_ago, technologies__name=subscriber.technology_selected
    ).distinct()

    if posts.count() == 0:
        return f"There are no new companies that are looking for people who know {subscriber.technology_selected}."

    message = f"Here are the companies that are looking for people that know {subscriber.technology_selected}:\n"

    for post in posts:
        full_url = "https://%s" % (Site.objects.get_current().domain)
        link = post.get_absolute_url()
        message += f"• {post.company.name} - {full_url + link}\n"

    return message
