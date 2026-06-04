import time
from typing import List, Optional

from django.http import HttpRequest
from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Q
from django_q.tasks import async_task
from ninja import NinjaAPI, Query
from ninja.errors import HttpError

from blog.models import BlogPost
from hn_jobs.posthog_events import capture_request_event
from hn_jobs.utils import get_tjalerts_logger
from jobs.choices import PostSource
from jobs.models import Company, Email, Post, Technology, TechnologyMapping, Title
from jobs.queries import get_similar_posts_from_db
from jobs.tasks import create_valid_emails
from users.models import CustomUser

from .schemas import (
    BlogPostCreateSchema,
    JobsResponse,
    ReadCompany,
    ReadEmails,
    SimilarPostsResponse,
    TechnologySchema,
    TitleSchema,
)

logger = get_tjalerts_logger(__name__)


api = NinjaAPI()


@api.get("/companies", response=List[ReadCompany])
def companies(request):
    return Company.objects.all()


@api.get("/create-emails")
def create_emails(request):
    async_task(create_valid_emails)  # noqa: F821
    capture_request_event(request, "admin task queued", properties={"task": "create_valid_emails"})
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


@api.get("/jobs", response=JobsResponse)
def get_jobs(
    request,
    technologies=Query(None),
    source: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    posts = Post.objects.prefetch_related("company", "technologies", "titles", "email")

    # Filter by technologies at the database level
    if technologies:
        user_submitted_technologies = [item.strip() for item in technologies.split(",")]

        # Get technology objects matching the names
        tech_objects = Technology.objects.filter(name__in=user_submitted_technologies)

        if tech_objects.exists():
            # Filter posts that have ALL the requested technologies
            for tech in tech_objects:
                posts = posts.filter(technologies=tech)

    if source:
        if source not in PostSource.values:
            raise HttpError(400, "Invalid job source")

        posts = posts.filter(source=source)

    # Sort by most recent submissions first
    posts = posts.order_by("-submitted_datetime")

    # Apply pagination at database level BEFORE materializing the queryset
    total = posts.count()
    total_pages = (total + page_size - 1) // page_size

    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    paginated_posts = posts[start_index:end_index]

    # Build the response
    posts_list = []
    for post in paginated_posts:
        post_technologies = [technology.name for technology in post.technologies.all()]
        post_titles = [title.name for title in post.titles.all()]
        post_emails = [
            {
                "email": email.email,
                "name": email.name,
            }
            for email in post.email.all()
        ]

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
            "source": post.source,
            "source_url": post.source_url,
            "source_external_id": post.source_external_id,
            "who_is_hiring_comment_id": post.who_is_hiring_comment_id,
            "submitted_datetime": post.submitted_datetime,
            "emails": post_emails,
        }

        posts_list.append(entry)

    return {
        "count": total,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
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

    logger.info("get_technologies_details", duration=round(time.time() - start_time, 2))

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

    logger.info("get_title_details", duration=round(time.time() - start_time, 2))

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


@api.post("/blog/create", response={201: dict, 403: dict, 404: dict, 500: dict})
def create_blog_post(request: HttpRequest, payload: BlogPostCreateSchema):
    if payload.admin_key != settings.ADMIN_KEY:
        logger.warning(
            "Non-superuser attempted to create a blog post.",
            user_id=request.user.id if request.user.is_authenticated else None,
        )
        raise HttpError(403, "Forbidden: You do not have permission to perform this action.")

    try:
        author = CustomUser.objects.get(username="rasulkireev")
    except CustomUser.DoesNotExist:
        logger.error("Author user 'rasulkireev' not found.")
        raise HttpError(404, "Author user 'rasulkireev' not found.")

    try:

        # Check for existing slug
        if BlogPost.objects.filter(slug=payload.slug).exists():
            raise HttpError(400, "Blog post with this slug already exists")

        blog_post = BlogPost.objects.create(
            title=payload.title,
            slug=payload.slug,
            content=payload.content,
            author=author,  # Assign the author
            description=payload.description if payload.description else "",
            tags=payload.tags if payload.tags else "",
            status=payload.status if payload.status else BlogPost.DRAFT,
        )
        logger.info(
            "Blog post created successfully.",
            post_id=blog_post.id,
            title=blog_post.title,
            author_id=author.id,  # Log the actual author's ID
        )
        return 201, {"status": "Success", "message": "Blog post created successfully."}
    except HttpError as e:
        raise e
    except Exception as e:
        logger.error("Error creating blog post.", error=str(e), payload=payload.dict())
        raise HttpError(500, f"Internal Server Error: {str(e)}")
