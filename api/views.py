from typing import List

from django.conf import settings
from django_q.tasks import async_task
from ninja import NinjaAPI, Query
from ninja.security import HttpBearer

from hn_jobs.utils import get_tjalerts_logger
from jobs.models import Company, Email, Post
from jobs.tasks import create_valid_emails

from .schemas import ReadCompany, ReadEmails

logger = get_tjalerts_logger(__name__)


class GlobalAuth(HttpBearer):
    def authenticate(self, request, token):
        if token == settings.API_TOKEN:
            return token


api = NinjaAPI(auth=GlobalAuth())


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
    posts = Post.objects.prefetch_related("company", "technologies", "jobs")

    user_submitted_technologies = technologies.split(",")
    user_submitted_technologies = [item.strip() for item in user_submitted_technologies]

    posts_list = []
    for post in posts:
        post_technologies = [technology.name for technology in post.technologies.all()]

        if not set(user_submitted_technologies).issubset(post_technologies):
            continue

        post_titles = [title.name for title in post.jobs.all()]

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
