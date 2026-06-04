import time

from django.core.cache import cache
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, When
from django.utils import timezone
from pgvector.django import L2Distance

from jobs.constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from jobs.models import Post, Technology, TechnologyMapping, Title
from jobs.utils import get_tjalerts_logger
from users.models import Subscriber

logger = get_tjalerts_logger(__name__)

CACHE_TTL_SECONDS = 60 * 5
LATEST_SUBMISSIONS_CACHE_TTL_SECONDS = 60


def _cache_key(name: str, *parts) -> str:
    normalized_parts = ":".join(str(part) for part in parts)
    return f"jobs:queries:{name}:{normalized_parts}"


def _ordered_queryset_for_ids(model, ids):
    if not ids:
        return model.objects.none()

    preserved_order = Case(
        *[When(pk=pk, then=position) for position, pk in enumerate(ids)],
        output_field=IntegerField(),
    )
    return model.objects.filter(pk__in=ids).order_by(preserved_order)


def _get_cached_ids(cache_key, queryset):
    ids = cache.get(cache_key)
    if ids is None:
        ids = list(queryset.values_list("id", flat=True))
        cache.set(cache_key, ids, CACHE_TTL_SECONDS)
    return ids


def get_latest_submissions(number_of: int, for_homepage: bool = False):
    start_time = time.time()
    cache_key = _cache_key("latest_submissions", number_of, for_homepage)
    should_cache = number_of > 0
    cached_post_ids = cache.get(cache_key) if should_cache else None
    if should_cache and cached_post_ids is not None:
        posts = (
            _ordered_queryset_for_ids(Post, cached_post_ids)
            .select_related("company")
            .prefetch_related("titles", "technologies")
        )
        logger.info(
            "Got latest submissions from cache",
            count=len(cached_post_ids),
            duration=round(time.time() - start_time, 2),
        )
        return posts

    posts = Post.objects.order_by("-submitted_datetime")

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

    if should_cache:
        post_ids = list(posts.values_list("id", flat=True)[:number_of])
        cache.set(cache_key, post_ids, LATEST_SUBMISSIONS_CACHE_TTL_SECONDS)
        posts = (
            _ordered_queryset_for_ids(Post, post_ids)
            .select_related("company")
            .prefetch_related("titles", "technologies")
        )
        count = len(post_ids)
    else:
        posts = posts.select_related("company").prefetch_related("titles", "technologies")
        count = None

    logger.info(
        "Got latest submissions",
        count=count,
        cached=False,
        duration=round(time.time() - start_time, 2),
    )

    return posts


def get_most_popular_titles(number_of: int = 0, min_count: int = 0):
    start_time = time.time()
    cache_key = _cache_key("popular_titles", number_of, min_count)
    should_cache = number_of > 0

    title_objects = Title.objects.exclude(name__in=EXCLUDED_TITLES)

    if number_of > 0 or min_count > 0:
        title_objects = title_objects.annotate(post_count=Count("posttitle")).order_by("-post_count")

    if min_count > 0:
        title_objects = title_objects.filter(post_count__gt=min_count)

    if should_cache:
        title_objects = title_objects[:number_of]
        ids = _get_cached_ids(cache_key, title_objects)
        title_objects = _ordered_queryset_for_ids(Title, ids)
        count = len(ids)
    else:
        count = None

    logger.info(
        "Got most popular titles", count=count, cached=should_cache, duration=round(time.time() - start_time, 2)
    )

    return title_objects


def get_most_popular_technologies(number_of: int = 0, min_count: int = 0, order_by_post_count: bool = True):
    start_time = time.time()
    cache_key = _cache_key("popular_technologies", number_of, min_count, order_by_post_count)
    should_cache = number_of > 0

    technology_objects = (
        Technology.objects.exclude(name__in=EXCLUDED_TECHNOLOGIES)
        .annotate(is_child=Exists(TechnologyMapping.objects.filter(child=OuterRef("pk"))))
        .filter(is_child=False)
    )

    if number_of > 0 or min_count > 0 or order_by_post_count:
        technology_objects = technology_objects.annotate(post_count=Count("posttechnology")).order_by("-post_count")

    if min_count > 0:
        technology_objects = technology_objects.filter(post_count__gt=min_count)

    if should_cache:
        technology_objects = technology_objects[:number_of]
        ids = _get_cached_ids(cache_key, technology_objects)
        technology_objects = _ordered_queryset_for_ids(Technology, ids)
        count = len(ids)
    else:
        count = None

    logger.info(
        "Got most popular technologies",
        count=count,
        cached=should_cache,
        duration=round(time.time() - start_time, 2),
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
