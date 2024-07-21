import time
from typing import List, Optional

from django.db.models import Count, Exists, OuterRef, Q
from django_q.tasks import async_task
from ninja import NinjaAPI, Query

from hn_jobs.utils import get_tjalerts_logger
from jobs.models import Company, Email, Post, Technology, TechnologyMapping, Title
from jobs.queries import get_similar_posts_from_db
from jobs.tasks import create_valid_emails

from .schemas import ReadCompany, ReadEmails, SimilarPostsResponse, TechnologySchema, TitleSchema

logger = get_tjalerts_logger(__name__)


api = NinjaAPI()


@api.get("/companies", response=List[ReadCompany])
def companies(request):
    return Company.objects.all()


@api.get("/create-emails")
def create_emails(request):
    async_task(create_valid_emails)  # noqa: F821
    return "Task Started"


@api.get("/emails", response=ReadEmails)
def get_emails(
    request,
    is_valid: bool = True,
    with_names_only: bool = Query(False, alias="names"),
    exclude_generic_email: bool = Query(True, alias="exclude-generic"),
    only_approved: bool = Query(False, alias="only-approved"),
):
    emails = (
        Email.objects.select_related("company")
        .filter(email_is_valid=is_valid)
        .values("email", "name", "company__name", "company__compliment")
    )

    if with_names_only:
        emails = emails.exclude(name="")

    if exclude_generic_email:
        emails = emails.exclude(email_is_generic=True)

    if only_approved:
        emails = emails.filter(is_approved=True)

    unique_emails = emails.values("email").distinct()
    unique_emails_queryset = emails.filter(email__in=unique_emails)

    return {
        "count": len(unique_emails_queryset),
        "emails": list(unique_emails_queryset),
    }


@api.get("/jobs")
def get_jobs(request, technologies=Query(None)):
    posts = Post.objects.prefetch_related("company", "technologies", "titles")

    user_submitted_technologies = technologies.split(",")
    user_submitted_technologies = [item.strip() for item in user_submitted_technologies]

    posts_list = []
    for post in posts:
        post_technologies = [technology.name for technology in post.technologies.all()]

        if not set(user_submitted_technologies).issubset(post_technologies):
            continue

        post_titles = [title.name for title in post.titles.all()]

        entry = {
            "company_name": post.company.name,
            "company_url": post.company.company_homepage_link,
            "description": post.description,
            "compensation_summary": post.compensation_summary,
            "min_salary": post.min_salary,
            "max_salary": post.max_salary,
            "is_remote": post.is_remote,
            "locations": post.locations,
            "technologies": post_technologies,
            "title": post_titles,
            "id": str(post.id),
            "who_is_hiring_comment_id": post.who_is_hiring_comment_id,
            "submitted_datetime": post.submitted_datetime,
        }

        posts_list.append(entry)

    return {
        "count": len(posts_list),
        "jobs": posts_list,
    }


@api.get("/technologies/search", response=List[TechnologySchema])
def search_technologies(request, query: Optional[str] = Query(None, min_length=2)):
    if query:
        technologies = (
            Technology.objects.filter(Q(name__icontains=query) | Q(slug__icontains=query))
            .annotate(
                post_count=Count("posttechnology"),
                is_child=Exists(TechnologyMapping.objects.filter(child=OuterRef("pk"))),
            )
            .filter(is_child=False)
            .order_by("-post_count")[:10]
        )
    else:
        technologies = Technology.objects.none()

    return [
        TechnologySchema(id=str(tech.id), name=tech.name, slug=tech.slug, post_count=tech.post_count)
        for tech in technologies
    ]


@api.get("/technology/{id}", response=TechnologySchema)
def get_technologies_details(request, id: str):
    start_time = time.time()

    technology = (
        Technology.objects.filter(id=id)
        .annotate(post_count=Count("posttechnology"))
        .values("id", "name", "slug", "post_count")
        .first()
    )

    if technology:
        technology["id"] = str(technology["id"])

    logger.info("get_technologies_details", duration={round(time.time() - start_time, 2)})

    return technology


@api.get("/title/search", response=List[TitleSchema])
def search_title(request, query: Optional[str] = Query(None, min_length=2)):
    if query:
        titles = (
            Title.objects.filter(Q(name__icontains=query) | Q(slug__icontains=query))
            .annotate(
                post_count=Count("posttitle"),
            )
            .order_by("-post_count")[:10]
        )
    else:
        titles = Title.objects.none()

    return [
        TitleSchema(id=str(title.id), name=title.name, slug=title.slug, post_count=title.post_count) for title in titles
    ]


@api.get("/title/{id}", response=TitleSchema)
def get_title_details(request, id: str):
    start_time = time.time()

    title = (
        Title.objects.filter(id=id)
        .annotate(post_count=Count("posttitle"))
        .values("id", "name", "slug", "post_count")
        .first()
    )

    if title:
        title["id"] = str(title["id"])

    logger.info("get_technologies_details", duration={round(time.time() - start_time, 2)})

    return title


@api.get("/posts/similar/{id}", response=SimilarPostsResponse)
def get_similar_posts(request, id: str):
    post = Post.objects.get(id=id)
    similar_posts = get_similar_posts_from_db(post, limit=5)

    similar_posts_data = [
        {
            "id": str(post.id),
            "description": post.description,
            "created_at": post.created,
            "company": {"id": str(post.company.id), "name": post.company.name},
        }
        for post in similar_posts
    ]

    return {"similar_posts": similar_posts_data}
