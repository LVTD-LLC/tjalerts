from datetime import timedelta

from django import template
from django.utils import timezone

from jobs.models import TechnologyMapping

register = template.Library()


@register.filter()
def replace_child_with_parent_technology(technology):
    child = TechnologyMapping.objects.filter(child=technology)

    if child.exists():
        technology = child.first().parent

    return technology


@register.filter()
def is_recently_sponsored(post):
    if not post.sponsored or not post.sponsored_at:
        return False

    one_month_ago = timezone.now() - timedelta(days=30)
    return post.sponsored_at >= one_month_ago
