from django.db.models import Count, Max

from jobs.constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from jobs.models import Post, Technology, Title


def get_latest_submissions(number_of: int, for_homepage: bool = False):
    posts = Post.objects.annotate(latest_datetime=Max("submitted_datetime")).order_by("-latest_datetime")

    if for_homepage:
        excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
        excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)

        posts = (
            posts.annotate(num_technologies=Count("technologies"), num_jobs=Count("jobs"))
            .exclude(technologies__in=excluded_tech)
            .exclude(jobs__in=excluded_titles)
            .filter(num_technologies__gt=0, num_jobs__gt=0)
        )

    if number_of > 0:
        posts = posts[:number_of]

    return posts


def get_most_popular_titles(number_of: int = 0):
    title_objects = (
        Title.objects.exclude(name__in=EXCLUDED_TITLES).annotate(post_count=Count("posttitle")).order_by("-post_count")
    )

    if number_of > 0:
        title_objects = title_objects[:number_of]

    return title_objects


def get_most_popular_technologies(number_of: int = 0, min_count: int = 0):
    technology_objects = (
        Technology.objects.exclude(name__in=EXCLUDED_TECHNOLOGIES)
        .annotate(post_count=Count("posttechnology"))
        .order_by("-post_count")
    )

    if number_of > 0:
        technology_objects = technology_objects[:number_of]

    if min_count > 0:
        technology_objects = technology_objects.filter(post_count__gt=min_count)

    return technology_objects
