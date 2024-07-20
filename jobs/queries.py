from django.db.models import Count, Exists, OuterRef
from django.utils import timezone

from users.models import Subscriber

from .constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from .models import Post, Technology, TechnologyMapping, Title


def get_latest_submissions(number_of: int, for_homepage: bool = False):
    posts = Post.objects.all().order_by("-submitted_datetime")

    if for_homepage:
        excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
        excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)

        posts = (
            posts.annotate(num_technologies=Count("technologies"), num_titles=Count("titles"))
            .exclude(
                technologies__in=excluded_tech,
                titles__in=excluded_titles,
                company__name="",
            )
            .filter(num_technologies__gt=0, num_titles__gt=0)
        )

    if number_of > 0:
        posts = posts[:number_of]

    return posts


def get_most_popular_titles(number_of: int = 0, min_count: int = 0):
    title_objects = Title.objects.exclude(name__in=EXCLUDED_TITLES)

    if number_of > 0 or min_count > 0:
        title_objects = title_objects.annotate(post_count=Count("posttitle")).order_by("-post_count")

    if number_of > 0:
        title_objects = title_objects[:number_of]

    if min_count > 0:
        title_objects = title_objects.filter(post_count__gt=min_count)

    return title_objects


def get_most_popular_technologies(number_of: int = 0, min_count: int = 0, order_by_post_count: bool = True):
    technology_objects = (
        Technology.objects.exclude(name__in=EXCLUDED_TECHNOLOGIES)
        .annotate(is_child=Exists(TechnologyMapping.objects.filter(child=OuterRef("pk"))))
        .filter(is_child=False)
    )

    if number_of > 0 or min_count > 0 or order_by_post_count:
        technology_objects = technology_objects.annotate(post_count=Count("posttechnology")).order_by("-post_count")

    if number_of > 0:
        technology_objects = technology_objects[:number_of]

    if min_count > 0:
        technology_objects = technology_objects.filter(post_count__gt=min_count)

    return technology_objects


def get_weekly_jobs_for_a_subscriber(subscriber: Subscriber) -> str:
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    return Post.objects.filter(
        created__gte=seven_days_ago, technologies__name=subscriber.technology_selected
    ).distinct()
