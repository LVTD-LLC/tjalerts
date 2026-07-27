from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from allauth.account.models import EmailAddress
from django.contrib.admin.views.decorators import staff_member_required
from django.db import models
from django.db.models import Count, Exists, Max, OuterRef, Subquery
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView, TemplateView
from django_filters.views import FilterView
from django_q.tasks import async_task

from hn_jobs.posthog_events import alias_request_user, capture_request_event
from hn_jobs.utils import build_absolute_site_url, get_tjalerts_logger
from jobs.choices import PostSource
from jobs.constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from jobs.filters import POSTED_WITHIN_CHOICES, WORK_MODE_CHOICES, PostFilter
from jobs.models import Company, Post, Technology, Title
from jobs.tasks import (
    create_backfill_vector_data_jobs,
    create_update_min_and_max_salary_jobs,
    find_bad_submitted_dates,
    import_remote_ok_jobs,
    import_we_work_remotely_jobs,
)
from jobs.technology_normalization import get_related_technology_ids
from jobs.utils import (
    MAX_ADDED_WITHIN_DAYS,
    day_count_label,
    generate_job_search_keywords,
    generate_job_search_title,
    parse_positive_day_count,
)
from utils.constants import HIRABLE_TECH_LIST_SLUGS

logger = get_tjalerts_logger(__name__)

excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)

YES_NO_LABELS = {"true": "Yes", "false": "No"}
HAS_FIELD_LABELS = {"yes": "Listed", "no": "Missing"}
POSTED_WITHIN_LABELS = dict(POSTED_WITHIN_CHOICES)
SOURCE_LABELS = dict(PostSource.choices)
WORK_MODE_LABELS = dict(WORK_MODE_CHOICES)

JOB_ACCESS_ALLOWED = "allowed"
JOB_ACCESS_ANONYMOUS = "anonymous"
JOB_ACCESS_EMAIL_MISSING = "email_missing"
JOB_ACCESS_EMAIL_UNVERIFIED = "email_unverified"


def job_access_status(user):
    if not user.is_authenticated:
        return JOB_ACCESS_ANONYMOUS

    if not user.email:
        return JOB_ACCESS_EMAIL_MISSING

    try:
        email_address = EmailAddress.objects.get_for_user(user, user.email)
    except EmailAddress.DoesNotExist:
        return JOB_ACCESS_EMAIL_MISSING

    return JOB_ACCESS_ALLOWED if email_address.verified else JOB_ACCESS_EMAIL_UNVERIFIED


def valid_uuid_values(values):
    valid_values = []

    for value in values:
        try:
            UUID(str(value))
        except (TypeError, ValueError):
            continue
        valid_values.append(value)

    return valid_values


def parse_positive_salary_floor(value):
    try:
        salary_floor = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None

    return salary_floor if salary_floor > 0 else None


def salary_label(value):
    salary_floor = parse_positive_salary_floor(value)
    if salary_floor is None:
        return value

    return f"${int(salary_floor):,}+"


def active_filter_summary(query_params):
    filters = []

    simple_filters = {
        "q": ("Search", None),
        "vector": ("Intent", None),
        "locations": ("Location", None),
        "source": ("Source", SOURCE_LABELS),
        "posted_within": ("Posted", POSTED_WITHIN_LABELS),
        "work_mode": ("Work", WORK_MODE_LABELS),
        "remove_duplicate_employers": ("Employers", {"true": "Unique only"}),
        "has_compensation": ("Comp", HAS_FIELD_LABELS),
        "has_contact": ("Contact", HAS_FIELD_LABELS),
        "is_remote": ("Remote", YES_NO_LABELS),
        "is_onsite": ("Onsite", YES_NO_LABELS),
        "compensation_summary__isempty": ("Comp", {"true": "Listed", "false": "Missing"}),
        "emails__isempty": ("Contact", {"true": "Listed", "false": "Missing"}),
    }

    for param, (label, value_labels) in simple_filters.items():
        value = query_params.get(param)
        if not value or value == "unknown":
            continue
        filters.append(
            {
                "label": label,
                "param": param,
                "value": value,
                "display": value_labels.get(value, value) if value_labels else value,
            }
        )

    salary_floor = parse_positive_salary_floor(query_params.get("salary_floor"))
    if salary_floor is not None:
        filters.append(
            {
                "label": "Salary",
                "param": "salary_floor",
                "value": query_params.get("salary_floor"),
                "display": salary_label(salary_floor),
            }
        )

    added_within_days = parse_positive_day_count(query_params.get("added_within_days"))
    if added_within_days is not None:
        filters.append(
            {
                "label": "Added",
                "param": "added_within_days",
                "value": query_params.get("added_within_days"),
                "display": f"Last {day_count_label(added_within_days)}",
            }
        )

    technology_ids = valid_uuid_values(query_params.getlist("technologies"))
    if technology_ids:
        technologies_by_id = {
            str(technology.id): technology.name for technology in Technology.objects.filter(id__in=technology_ids)
        }
        for technology_id in technology_ids:
            filters.append(
                {
                    "label": "Tech",
                    "param": "technologies",
                    "value": technology_id,
                    "display": technologies_by_id.get(str(technology_id), technology_id),
                }
            )

    title_ids = valid_uuid_values(query_params.getlist("titles"))
    if title_ids:
        titles_by_id = {str(title.id): title.name for title in Title.objects.filter(id__in=title_ids)}
        for title_id in title_ids:
            filters.append(
                {
                    "label": "Role",
                    "param": "titles",
                    "value": title_id,
                    "display": titles_by_id.get(str(title_id), title_id),
                }
            )

    return filters


class PostListView(FilterView):
    model = Post
    template_name = "jobs/all_jobs.html"
    filterset_class = PostFilter
    paginate_by = 6

    def get_queryset(self):
        return super().get_queryset().select_related("company").prefetch_related("titles", "technologies")

    def get(self, request, *args, **kwargs):
        query_params = request.GET.copy()
        needs_redirect = False

        for key in list(query_params.keys()):
            if query_params[key] == "unknown" or query_params[key] == "":
                del query_params[key]
                needs_redirect = True

        if "salary_floor" in query_params and parse_positive_salary_floor(query_params.get("salary_floor")) is None:
            del query_params["salary_floor"]
            needs_redirect = True

        if (
            "added_within_days" in query_params
            and parse_positive_day_count(query_params.get("added_within_days")) is None
        ):
            del query_params["added_within_days"]
            needs_redirect = True

        if query_params.get("page") not in (None, "1"):
            if job_access_status(request.user) != JOB_ACCESS_ALLOWED:
                del query_params["page"]
                query_params["access"] = "restricted"
                needs_redirect = True

        if needs_redirect:
            clean_url = f"{reverse('posts')}?{query_params.urlencode()}"
            return HttpResponseRedirect(clean_url)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date = timezone.now().strftime("%B %Y")
        page = context["page_obj"]
        page_items = list(page.object_list)
        page.object_list = page_items

        first_item_datetime = timezone.now()
        if page_items:
            first_item = page_items[0]
            first_item_datetime = first_item.submitted_datetime

        title = generate_job_search_title(self.request.GET, first_item_datetime)
        keywords = generate_job_search_keywords(self.request.GET)

        user = self.request.user
        if user.is_authenticated:
            alias_request_user(self.request)

        active_filters = active_filter_summary(self.request.GET)

        context["active_filters"] = active_filters
        context["active_filter_count"] = len(active_filters)
        context["result_count"] = page.paginator.count
        context["source_choices"] = PostSource.choices
        context["max_added_within_days"] = MAX_ADDED_WITHIN_DAYS
        context["title"] = title
        context["date"] = date
        context["keywords"] = ", ".join(map(str, keywords))
        context["canonical_url"] = build_absolute_site_url(self.request.path)
        if self.request.GET.get("access") == "restricted":
            context["job_access_status"] = job_access_status(self.request.user)
            context["show_access_modal"] = context["job_access_status"] != JOB_ACCESS_ALLOWED

        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "jobs/post_detail.html"

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        access_status = job_access_status(request.user)
        if access_status != JOB_ACCESS_ALLOWED:
            return render(
                request,
                "jobs/post_access_required.html",
                {
                    "access_action": "view job details",
                    "job_access_status": access_status,
                },
            )

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_queryset(self):
        return super().get_queryset().select_related("company").prefetch_related("titles", "technologies")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        if user.is_authenticated:
            alias_request_user(self.request)

        context["is_old"] = self.object.created < timezone.now() - timedelta(days=60)

        return context


class HighestPaidBlogPostListView(TemplateView):
    template_name = "jobs/highest-paid-blog-post-list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["hirable_tech_list"] = HIRABLE_TECH_LIST_SLUGS

        return context


class HighestPaidJobsView(ListView):
    template_name = "jobs/highest-paid-job.html"
    model = Post

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tech = (
            Technology.objects.filter(slug__icontains=self.kwargs.get("slug"))
            .annotate(post_count=Count("post"))
            .order_by("-post_count")
            .first()
        )

        data = self.get_queryset()
        dates = data.values_list("created", flat=True)
        latest_date = max(dates) if dates else None

        context["tech_name"] = tech.name
        context["tech_id"] = tech.id
        context["canonical_url"] = build_absolute_site_url(self.request.path)
        context["latest_date"] = latest_date

        return context

    def get_queryset(self):
        queryset = super().get_queryset().select_related("company").prefetch_related("titles", "technologies")

        tech = (
            Technology.objects.filter(slug__icontains=self.kwargs.get("slug"))
            .annotate(post_count=Count("post"))
            .order_by("-post_count")
            .first()
        )

        all_related_ids = get_related_technology_ids(tech)

        logger.info("Got all related tech ids", tech_id=tech.id if tech else None, count=len(all_related_ids))

        # This is to avoid multiple posting by a single company
        subquery = Post.objects.values("company").annotate(latest_post=Max("submitted_datetime")).values("latest_post")

        return (
            queryset.filter(technologies__id__in=all_related_ids)
            .exclude(max_salary=0)
            .order_by("-max_salary")
            .filter(submitted_datetime__in=subquery)
            .distinct()[:10]
        )


# One time views
@staff_member_required(login_url="account_login")
@require_POST
def find_bad_submitted_dates_view(request):
    async_task(find_bad_submitted_dates, hook="jobs.hooks.print_result", group="Find Bad Datetimes to Fix")
    capture_request_event(request, "admin task queued", properties={"task": "find_bad_submitted_dates"})

    return redirect("admin-panel")


@staff_member_required(login_url="account_login")
@require_POST
def update_min_and_max_salary_view(request):
    async_task(
        create_update_min_and_max_salary_jobs, hook="jobs.hooks.print_result", group="Populate min and max salary"
    )
    capture_request_event(request, "admin task queued", properties={"task": "create_update_min_and_max_salary_jobs"})

    return redirect("admin-panel")


@staff_member_required(login_url="account_login")
@require_POST
def create_backfill_vector_data_jobs_view(request, rebuild=False):
    async_task(
        create_backfill_vector_data_jobs,
        rebuild,
        hook="jobs.hooks.print_result",
        group="Create Jobs to Update Vector Data.",
    )
    capture_request_event(
        request,
        "admin task queued",
        properties={"task": "create_backfill_vector_data_jobs", "rebuild": bool(rebuild)},
    )

    return redirect("admin-panel")


@staff_member_required(login_url="account_login")
@require_POST
def import_remote_ok_jobs_view(request):
    async_task(import_remote_ok_jobs, hook="jobs.hooks.print_result", group="Import Remote OK Jobs")
    capture_request_event(request, "admin task queued", properties={"task": "import_remote_ok_jobs"})

    return redirect("admin-panel")


@staff_member_required(login_url="account_login")
@require_POST
def import_we_work_remotely_jobs_view(request):
    async_task(import_we_work_remotely_jobs, hook="jobs.hooks.print_result", group="Import We Work Remotely Jobs")
    capture_request_event(request, "admin task queued", properties={"task": "import_we_work_remotely_jobs"})

    return redirect("admin-panel")


class CompanyJobsView(ListView):
    template_name = "jobs/company-jobs.html"
    model = Post

    def get_queryset(self):
        queryset = super().get_queryset().select_related("company").prefetch_related("titles", "technologies")
        two_months_ago = timezone.now() - timezone.timedelta(days=60)

        return queryset.filter(company__slug=self.kwargs.get("slug"), submitted_datetime__gte=two_months_ago)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        companies = Company.objects.filter(slug=self.kwargs.get("slug"))
        if companies.exists():
            context["company"] = companies.first()
        else:
            # Handle the case where no company is found
            context["company"] = None
        return context


class TechnologyJobsView(ListView):
    template_name = "jobs/technology-jobs.html"
    model = Post

    def get_queryset(self):
        queryset = super().get_queryset().select_related("company").prefetch_related("titles", "technologies")
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        technology = Technology.objects.filter(slug=self.kwargs.get("slug")).first()

        return queryset.filter(
            technologies__id__in=get_related_technology_ids(technology),
            submitted_datetime__gte=two_months_ago,
        ).distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        tech = (
            Technology.objects.filter(slug=self.kwargs.get("slug"))
            .annotate(post_count=Count("posttechnology"))
            .order_by("-post_count")
            .first()
        )

        data = self.get_queryset()
        dates = data.values_list("created", flat=True)

        latest_date = max(dates) if dates else None

        context["tech_name"] = tech.name if tech else ""
        context["tech_id"] = tech.id if tech else None
        context["tech_slug"] = tech.slug if tech else ""
        context["canonical_url"] = build_absolute_site_url(self.request.path)
        context["latest_date"] = latest_date

        return context


class CompaniesJobsView(ListView):
    template_name = "jobs/companies-with-jobs.html"
    model = Company

    def get_queryset(self):
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("company")

        queryset = (
            super()
            .get_queryset()
            .annotate(has_recent_posts=Exists(recent_posts.filter(company=OuterRef("pk"))))
            .filter(has_recent_posts=True)
            .exclude(name="")
            .order_by("name")
        )

        return queryset


class TechnologiesJobsView(ListView):
    template_name = "jobs/technologies-with-jobs.html"
    model = Technology

    def get_queryset(self):
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago, technologies=OuterRef("pk"))

        recent_posts_count = Subquery(
            recent_posts.values("technologies").annotate(count=Count("pk")).values("count"),
            output_field=models.IntegerField(),
        )

        queryset = (
            super()
            .get_queryset()
            .exclude(name__in=EXCLUDED_TECHNOLOGIES)
            .annotate(
                post_count=Count("posttechnology"),
                has_recent_posts=Exists(recent_posts.filter(technologies=OuterRef("pk"))),
                recent_posts_count=recent_posts_count,
            )
            .filter(has_recent_posts=True, post_count__gt=5)
            .order_by("name")
        )

        return queryset


class TitlesJobsView(ListView):
    template_name = "jobs/titles-with-jobs.html"
    model = Title

    def get_queryset(self):
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago, titles=OuterRef("pk"))

        recent_posts_count = Subquery(
            recent_posts.values("titles").annotate(count=Count("pk")).values("count"),
            output_field=models.IntegerField(),
        )

        queryset = (
            super()
            .get_queryset()
            .annotate(
                post_count=Count("posttitle"),
                has_recent_posts=Exists(recent_posts.filter(titles=OuterRef("pk"))),
                recent_posts_count=recent_posts_count,
            )
            .filter(has_recent_posts=True, post_count__gt=5)
            .order_by("name")
        )

        return queryset


class TitleJobsView(ListView):
    template_name = "jobs/title-jobs.html"
    model = Post

    def get_queryset(self):
        queryset = super().get_queryset().select_related("company").prefetch_related("titles", "technologies")
        two_months_ago = timezone.now() - timezone.timedelta(days=60)

        queryset = queryset.filter(titles__slug=self.kwargs.get("slug"), submitted_datetime__gte=two_months_ago)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        title = (
            Title.objects.filter(slug=self.kwargs.get("slug"))
            .annotate(post_count=Count("posttitle"))
            .order_by("-post_count")
            .first()
        )

        data = self.get_queryset()
        dates = data.values_list("created", flat=True)
        latest_date = max(dates) if dates else None

        context["title_name"] = title.name
        context["title_id"] = title.id
        context["title_slug"] = title.slug
        context["canonical_url"] = build_absolute_site_url(self.request.path)
        context["latest_date"] = latest_date

        return context
