import time
from datetime import timedelta

from django.db.models import Case, Count, Exists, OuterRef, Q, When
from django.utils import timezone
from pgvector.django import L2Distance

from jobs.constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from jobs.models import Post, Technology, TechnologyMapping, Title
from jobs.utils import get_tjalerts_logger
from users.models import Subscriber

logger = get_tjalerts_logger(__name__)


def get_latest_submissions(number_of: int, for_homepage: bool = False):
    start_time = time.time()

    one_month_ago = timezone.now() - timedelta(days=30)

    posts = (
        Post.objects.all()
        .annotate(
            is_recently_sponsored=Case(When(sponsored=True, sponsored_at__gte=one_month_ago, then=True), default=False)
        )
        .order_by("-is_recently_sponsored", "-submitted_datetime")
    )

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

    logger.info("Got latest submissions", count=len(posts), duration=round(time.time() - start_time, 2))

    return posts


def get_most_popular_titles(number_of: int = 0, min_count: int = 0):
    start_time = time.time()

    title_objects = Title.objects.exclude(name__in=EXCLUDED_TITLES)

    if number_of > 0 or min_count > 0:
        title_objects = title_objects.annotate(post_count=Count("posttitle")).order_by("-post_count")

    if number_of > 0:
        title_objects = title_objects[:number_of]

    if min_count > 0:
        title_objects = title_objects.filter(post_count__gt=min_count)

    logger.info("Got most popular titles", count=len(title_objects), duration=round(time.time() - start_time, 2))

    return title_objects


def get_most_popular_technologies(number_of: int = 0, min_count: int = 0, order_by_post_count: bool = True):
    start_time = time.time()

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

    logger.info(
        "Got most popular technologies", count=len(technology_objects), duration=round(time.time() - start_time, 2)
    )

    return technology_objects


def get_weekly_jobs_for_a_subscriber(subscriber: Subscriber) -> str:
    seven_days_ago = timezone.now() - timezone.timedelta(days=7)
    return Post.objects.filter(
        created__gte=seven_days_ago, technologies__name=subscriber.technology_selected
    ).distinct()


def get_similar_posts_from_db(post, limit=5):
    start_time = time.time()

    excluded_posts = Q(id=post.id) | Q(company=post.company)
    similar_posts = (
        Post.objects.select_related("company")
        .exclude(excluded_posts)
        .annotate(distance=L2Distance("vector", post.vector))
        .order_by("distance")
    )

    result = []
    seen_companies = set()

    for similar_post in similar_posts[: limit * 2]:
        if similar_post.company.id not in seen_companies:
            result.append(similar_post)
            seen_companies.add(similar_post.company.id)

        if len(result) == limit:
            break

    logger.info("Got similar posts", count=len(result), duration=round(time.time() - start_time, 2))

    return result
