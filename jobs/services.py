from math import ceil
from typing import Literal, TypedDict
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet

from jobs.choices import PostSource
from jobs.models import Post

DEFAULT_JOB_PAGE_SIZE = 20
MAX_JOB_PAGE_SIZE = 100
MAX_JOB_PAGE = 10_000
MAX_JOB_QUERY_LENGTH = 500
MAX_TECHNOLOGY_FILTERS = 10
MAX_TECHNOLOGY_NAME_LENGTH = 100

JobSource = Literal["Hacker News", "Remote OK", "We Work Remotely"]


class JobSummary(TypedDict):
    id: str
    company_name: str
    compensation_summary: str | None
    min_salary: int | None
    max_salary: int | None
    currency: str
    is_remote: bool
    is_onsite: bool
    locations: str
    technologies: list[str]
    titles: list[str]
    source: str
    source_url: str
    submitted_datetime: str


class JobDetail(JobSummary):
    company_url: str
    description: str
    job_details: dict
    source_external_id: str
    application_url: str


class JobSearchResult(TypedDict):
    count: int
    total: int
    page: int
    page_size: int
    total_pages: int
    jobs: list[JobSummary]


class JobQueryError(ValueError):
    """Raised when a job query contains unsupported input."""


class JobNotFoundError(LookupError):
    """Raised when a requested job does not exist."""


def _job_queryset() -> QuerySet[Post]:
    return Post.objects.select_related("company").prefetch_related("technologies", "titles")


def _serialize_job_summary(post: Post) -> JobSummary:
    return {
        "id": str(post.id),
        "company_name": post.company.name,
        "compensation_summary": post.compensation_summary,
        "min_salary": post.min_salary,
        "max_salary": post.max_salary,
        "currency": post.currency,
        "is_remote": post.is_remote,
        "is_onsite": post.is_onsite,
        "locations": post.locations,
        "technologies": sorted(technology.name for technology in post.technologies.all()),
        "titles": sorted(title.name for title in post.titles.all()),
        "source": post.source,
        "source_url": post.source_url,
        "submitted_datetime": post.submitted_datetime.isoformat(),
    }


def _serialize_job(post: Post) -> JobDetail:
    return {
        **_serialize_job_summary(post),
        "company_url": post.company.company_homepage_link,
        "description": post.description,
        "job_details": post.job_details,
        "source_external_id": post.source_external_id,
        "application_url": post.company_job_application_link,
    }


def search_jobs(
    *,
    query: str | None = None,
    technologies: list[str] | None = None,
    source: JobSource | None = None,
    remote: bool | None = None,
    minimum_salary: int | None = None,
    page: int = 1,
    page_size: int = DEFAULT_JOB_PAGE_SIZE,
) -> JobSearchResult:
    """Return a bounded, serialized page of public jobs."""
    if not 1 <= page <= MAX_JOB_PAGE:
        raise JobQueryError(f"page must be between 1 and {MAX_JOB_PAGE}")
    if not 1 <= page_size <= MAX_JOB_PAGE_SIZE:
        raise JobQueryError(f"page_size must be between 1 and {MAX_JOB_PAGE_SIZE}")
    if source and source not in PostSource.values:
        raise JobQueryError(f"Unsupported job source: {source}")
    if minimum_salary is not None and minimum_salary < 0:
        raise JobQueryError("minimum_salary cannot be negative")
    if technologies and len(technologies) > MAX_TECHNOLOGY_FILTERS:
        raise JobQueryError(f"Use at most {MAX_TECHNOLOGY_FILTERS} technology filters")

    posts = _job_queryset()

    if query and (query := query.strip()):
        if len(query) > MAX_JOB_QUERY_LENGTH:
            raise JobQueryError(f"query cannot exceed {MAX_JOB_QUERY_LENGTH} characters")
        posts = posts.filter(
            Q(company__name__icontains=query)
            | Q(description__icontains=query)
            | Q(titles__name__icontains=query)
            | Q(technologies__name__icontains=query)
            | Q(locations__icontains=query)
            | Q(cities__icontains=query)
            | Q(countries__icontains=query)
            | Q(remote_timezones__icontains=query)
            | Q(compensation_summary__icontains=query)
        )

    normalized_technologies = []
    seen_technologies = set()
    for technology in technologies or []:
        if technology := technology.strip():
            if len(technology) > MAX_TECHNOLOGY_NAME_LENGTH:
                raise JobQueryError(f"technology names cannot exceed {MAX_TECHNOLOGY_NAME_LENGTH} characters")
            normalized_name = technology.casefold()
            if normalized_name not in seen_technologies:
                normalized_technologies.append(technology)
                seen_technologies.add(normalized_name)

    for technology in normalized_technologies:
        posts = posts.filter(technologies__name__iexact=technology)

    if source:
        posts = posts.filter(source=source)
    if remote is not None:
        posts = posts.filter(is_remote=remote)
    if minimum_salary is not None:
        posts = posts.filter(max_salary__gte=minimum_salary)

    posts = posts.distinct().order_by("-submitted_datetime", "id")
    count = posts.count()
    start = (page - 1) * page_size
    jobs = []
    if start < count:
        jobs = [_serialize_job_summary(post) for post in posts[start : start + page_size]]

    return {
        "count": count,
        "total": count,
        "page": page,
        "page_size": page_size,
        "total_pages": ceil(count / page_size),
        "jobs": jobs,
    }


def get_job(job_id: str | UUID) -> JobDetail:
    """Return one serialized public job."""
    try:
        post = _job_queryset().get(id=job_id)
    except (Post.DoesNotExist, ValidationError, ValueError) as exc:
        raise JobNotFoundError(f"Job not found: {job_id}") from exc

    return _serialize_job(post)
