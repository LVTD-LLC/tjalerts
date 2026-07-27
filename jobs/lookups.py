from django.db.models import Count, Exists, OuterRef, Q

from jobs.models import Technology, TechnologyAlias, TechnologyMapping, Title
from jobs.queries import get_similar_posts_from_db
from jobs.technology_names import DEFAULT_TECHNOLOGY_ALIAS_MAP, normalize_technology_key


def search_technology_options(query):
    if not query:
        return []

    normalized_query = normalize_technology_key(query)
    builtin_canonical_name = DEFAULT_TECHNOLOGY_ALIAS_MAP.get(normalized_query)
    alias_technology_ids = TechnologyAlias.objects.filter(
        Q(alias__icontains=query) | Q(normalized_alias__icontains=normalized_query)
    ).values("technology_id")
    builtin_alias_query = Q()
    if builtin_canonical_name:
        builtin_alias_query = Q(name__iexact=builtin_canonical_name)

    technologies = (
        Technology.objects.filter(
            Q(name__icontains=query) | Q(slug__icontains=query) | Q(id__in=alias_technology_ids) | builtin_alias_query
        )
        .annotate(
            post_count=Count("posttechnology"),
            is_child=Exists(TechnologyMapping.objects.filter(child=OuterRef("pk"))),
        )
        .filter(is_child=False)
        .distinct()
        .order_by("-post_count")[:10]
    )

    return [
        {
            "id": str(technology.id),
            "name": technology.name,
            "slug": technology.slug,
            "post_count": technology.post_count,
        }
        for technology in technologies
    ]


def get_technology_option(technology_id):
    technology = (
        Technology.objects.filter(id=technology_id)
        .annotate(post_count=Count("posttechnology"))
        .values("id", "name", "slug", "post_count")
        .first()
    )
    if technology:
        technology["id"] = str(technology["id"])
    return technology


def search_title_options(query):
    if not query:
        return []

    titles = (
        Title.objects.filter(Q(name__icontains=query) | Q(slug__icontains=query))
        .annotate(post_count=Count("posttitle"))
        .order_by("-post_count")[:10]
    )
    return [
        {
            "id": str(title.id),
            "name": title.name,
            "slug": title.slug,
            "post_count": title.post_count,
        }
        for title in titles
    ]


def get_title_option(title_id):
    title = (
        Title.objects.filter(id=title_id)
        .annotate(post_count=Count("posttitle"))
        .values("id", "name", "slug", "post_count")
        .first()
    )
    if title:
        title["id"] = str(title["id"])
    return title


def get_similar_post_options(post):
    similar_posts = get_similar_posts_from_db(post, limit=5)
    return [
        {
            "id": str(similar_post.id),
            "description": similar_post.description,
            "created_at": similar_post.created,
            "company": {
                "id": str(similar_post.company.id),
                "name": similar_post.company.name,
            },
        }
        for similar_post in similar_posts
    ]
