import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, models
from django.db.models import Count, Exists, Max, OuterRef, Subquery
from django.http import HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from django_q.tasks import async_task

from hn_jobs.posthog_events import capture_event, capture_request_event, distinct_id_for_email
from hn_jobs.utils import add_users_context, build_absolute_site_url, get_tjalerts_logger, validate_technology_selected
from jobs.constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from jobs.filters import PostFilter
from jobs.forms import ConfirmAlertForm, CreateAlertForm, CreateCustomAlertForm
from jobs.models import Alert, AlertEmailSend, Company, Post, Technology, TechnologyMapping, Title
from jobs.tasks import (
    add_email_to_buttondown,
    create_backfill_vector_data_jobs,
    create_update_min_and_max_salary_jobs,
    find_bad_submitted_dates,
    find_users_to_alert,
    import_remote_ok_jobs,
    send_confirmation_email,
)
from jobs.utils import (
    default_alert_name,
    generate_job_search_keywords,
    generate_job_search_title,
    is_email_confirmed,
    remove_params_for_filters,
)
from utils.constants import HIRABLE_TECH_LIST_SLUGS

logger = get_tjalerts_logger(__name__)

excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)


class PostListView(FilterView):
    model = Post
    template_name = "jobs/all_jobs.html"
    filterset_class = PostFilter
    paginate_by = 6

    def get(self, request, *args, **kwargs):
        query_params = request.GET.copy()
        needs_redirect = False

        for key in list(query_params.keys()):
            if query_params[key] == "unknown" or query_params[key] == "":
                del query_params[key]
                needs_redirect = True

        if needs_redirect:
            clean_url = f"{reverse('posts')}?{query_params.urlencode()}"
            return HttpResponseRedirect(clean_url)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filtered_qs = self.filterset.qs
        date = timezone.now().strftime("%B %Y")

        paginator = Paginator(filtered_qs, self.paginate_by)
        page_number = self.request.GET.get("page", 1)
        page = paginator.get_page(page_number)

        first_item_datetime = timezone.now()
        if page.object_list:
            first_item = page.object_list[0]
            first_item_datetime = first_item.submitted_datetime

        title = generate_job_search_title(self.request.GET, first_item_datetime)
        keywords = generate_job_search_keywords(self.request.GET)

        user = self.request.user
        if user.is_authenticated:
            add_users_context(context, user, self)

        params = remove_params_for_filters(self.request.GET.copy().dict())
        params["technologies"] = self.request.GET.getlist("technologies")

        context["CustomAlertForm"] = CreateCustomAlertForm
        context["custom_alert_filters"] = json.dumps(params)
        context["title"] = title
        context["date"] = date
        context["keywords"] = ", ".join(map(str, keywords))
        context["canonical_url"] = build_absolute_site_url(self.request.path)

        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "jobs/post_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        if user.is_authenticated:
            add_users_context(context, user, self)

        context["create_alert_form"] = CreateAlertForm
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
        context["create_alert_form"] = CreateAlertForm

        return context

    def get_queryset(self):
        queryset = super().get_queryset()

        tech_id = (
            Technology.objects.filter(slug__icontains=self.kwargs.get("slug"))
            .annotate(post_count=Count("post"))
            .order_by("-post_count")
            .values_list("id", flat=True)
            .first()
        )

        child_ids = list(TechnologyMapping.objects.filter(parent_id=tech_id).values_list("child__id", flat=True))
        all_related_ids = [tech_id] + child_ids

        logger.info("Got all related tech ids", tech_id=tech_id, number_of_child_ids=len(child_ids))

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


class CreateCustomAlertView(SuccessMessageMixin, CreateView):
    template_name = "jobs/create-custom-alert.html"
    model = Alert
    form_class = CreateCustomAlertForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        user = self.request.user
        if user.is_authenticated:
            form.instance.user = user

        # if user.is_authenticated and existing_alerts.count() >= 3:
        #     messages.add_message(self.request, messages.WARNING, "Free users can only have 3 alerts.")
        #     return redirect("home")
        existing_alerts = Alert.objects.filter(email=form.instance.email)
        if not user.is_authenticated and existing_alerts.exists():
            messages.add_message(self.request, messages.WARNING, "Sign up to create multiple alerts.")
            return redirect("home")

        if user.is_authenticated and existing_alerts.exists():
            if existing_alerts.latest("modified").confirmed is True or is_email_confirmed(user):
                form.instance.confirmed = True
                messages.add_message(
                    self.request, messages.SUCCESS, "Alert has been added, you will start getting jobs soon!"
                )
        else:
            confirmation_url = self.request.build_absolute_uri(reverse("confirm_subscription", args=[form.instance.id]))
            async_task(send_confirmation_email, form.cleaned_data, confirmation_url, group="Send Confirmation Email")
            messages.add_message(
                self.request, messages.SUCCESS, "Thank for creating an alert! Check your emails to confirm!"
            )

        async_task(find_users_to_alert, group="Find Users to Alert")

        response = super(CreateCustomAlertView, self).form_valid(form)
        capture_request_event(
            self.request,
            "alert created",
            properties={
                "alert_id": str(self.object.id),
                "alert_type": "custom",
                "confirmed": self.object.confirmed,
                "authenticated": user.is_authenticated,
                "existing_alert_count": existing_alerts.count(),
                "filter_keys": sorted(self.object.filter.keys()),
            },
        )

        return response


class AlertCreateView(SuccessMessageMixin, CreateView):
    template_name = "jobs/create-alert.html"
    model = Alert
    form_class = CreateAlertForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        try:
            user = self.request.user
            existing_alerts = Alert.objects.filter(email=form.instance.email)

            if user.is_authenticated:
                form.instance.user = user

            technology = Technology.objects.filter(name=form.cleaned_data["technology_selected"]).first()
            if not technology:
                messages.add_message(self.request, messages.WARNING, "Invalid technology selected.")
                return redirect("home")

            form.instance.filter = {"technologies": [str(technology.id)]}

            try:
                validate_technology_selected(form.cleaned_data["technology_selected"])
            except ValidationError:
                messages.add_message(self.request, messages.WARNING, "Please use a Technology from the dropdown list.")
                return redirect("home")

            if not user.is_authenticated and existing_alerts.exists():
                messages.add_message(self.request, messages.WARNING, "Sign up to create multiple alerts.")
                return redirect("home")

            if user.is_authenticated and existing_alerts.exists():
                if existing_alerts.latest("modified").confirmed is True:
                    form.instance.confirmed = True
                    messages.add_message(
                        self.request, messages.SUCCESS, "Alert has been added, you will start getting jobs soon!"
                    )
            else:
                confirmation_url = self.request.build_absolute_uri(
                    reverse("confirm_subscription", args=[form.instance.id])
                )
                async_task(
                    send_confirmation_email, form.cleaned_data, confirmation_url, group="Send Confirmation Email"
                )
                messages.add_message(
                    self.request, messages.SUCCESS, "Thank for creating an alert! Check your emails to confirm!"
                )

            async_task(find_users_to_alert, group="Find Users to Alert")

            response = super(AlertCreateView, self).form_valid(form)
            capture_request_event(
                self.request,
                "alert created",
                properties={
                    "alert_id": str(self.object.id),
                    "alert_type": "technology",
                    "confirmed": self.object.confirmed,
                    "authenticated": user.is_authenticated,
                    "existing_alert_count": existing_alerts.count(),
                    "technology_id": str(technology.id),
                    "technology_name": technology.name,
                },
            )

            return response

        except IntegrityError as e:
            logger.error("IntegrityError in AlertCreateView", error={str(e)})
            capture_request_event(
                self.request,
                "alert creation failed",
                properties={"error_type": type(e).__name__},
            )
            messages.add_message(self.request, messages.ERROR, f"An error occurred: {str(e)}")
            return redirect("home")
        except Exception as e:
            messages.add_message(self.request, messages.ERROR, "An unexpected error occurred. Please try again.")
            logger.error("Exception in AlertCreateView", error={str(e)})
            capture_request_event(
                self.request,
                "alert creation failed",
                properties={"error_type": type(e).__name__},
            )
            return redirect("home")


class ConfirmAlertView(SuccessMessageMixin, UpdateView):
    model = Alert
    form_class = ConfirmAlertForm
    template_name = "jobs/subscription-confirmation.html"
    success_url = reverse_lazy("home")
    success_message = "Thanks for confirming :) You will receive your alerts soon!"

    def form_valid(self, form):
        response = super(ConfirmAlertView, self).form_valid(form)
        async_task(add_email_to_buttondown, self.object.email, tag="user", group="Add Email to Buttondown")
        async_task(find_users_to_alert, group="Find Users to Alert")
        capture_event(
            "alert confirmed",
            distinct_id=distinct_id_for_email(self.object.email),
            properties={
                "alert_id": str(self.object.id),
                "alert_type": "custom" if self.object.name else "technology",
                "authenticated": bool(self.object.user_id),
            },
        )

        return response


def unauthed_weekly_digest_view(request, alert_email_send_id):
    template_name = "jobs/unauthed_weekly_digest.html"

    alert_email_send = get_object_or_404(AlertEmailSend, id=alert_email_send_id)
    alert = Alert.objects.get(email=alert_email_send.email, user__isnull=True)

    post_filter = PostFilter(alert.filter)
    queryset = post_filter.qs.filter(submitted_datetime__gte=alert_email_send.created - timedelta(days=7))
    name = f"{Technology.objects.get(id=alert.filter['technologies'][0]).name} Alert"

    context = {"alert": alert, "queryset": queryset, "name": name}
    capture_event(
        "alert digest viewed",
        distinct_id=distinct_id_for_email(alert.email),
        properties={
            "alert_email_send_id": str(alert_email_send.id),
            "alert_id": str(alert.id),
            "authenticated": False,
            "job_count": queryset.count(),
        },
    )
    return render(request, template_name, context)


def unsubscribe_from_unauthed_alert(request, alert_email_send_id):
    alert_email_send = get_object_or_404(AlertEmailSend, id=alert_email_send_id)
    alert = Alert.objects.get(email=alert_email_send.email, user__isnull=True)

    if request.method == "POST":
        alert.unsubscribed = True
        alert.save()
        capture_event(
            "alert unsubscribed",
            distinct_id=distinct_id_for_email(alert.email),
            properties={
                "alert_id": str(alert.id),
                "alert_email_send_id": str(alert_email_send.id),
                "authenticated": False,
            },
        )
        messages.success(request, "You have been unsubscribed from the alert successfully.")
        return redirect(reverse("home"))

    return render(request, "jobs/unsubscribe_from_unauthed_alert.html", {"alert_email_send": alert_email_send})


@login_required(login_url="account_login")
def toggle_subscription_from_authed_alert(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id)

    if request.method == "POST":
        alert.unsubscribed = not alert.unsubscribed
        alert.save()
        capture_request_event(
            request,
            "alert subscription toggled",
            properties={
                "alert_id": str(alert.id),
                "unsubscribed": alert.unsubscribed,
                "authenticated": True,
            },
        )

        custom_message = (
            "You have been unsubscribed from the alert successfully."
            if alert.unsubscribed
            else "You have been subscribed to the alert successfully."
        )
        messages.success(request, custom_message)
        return redirect(reverse("settings"))

    return render(request, "jobs/toggle_subscription_from_authed_alert.html", {"alert": alert})


@login_required(login_url="account_login")
def authed_weekly_digest_view(request):
    template_name = "jobs/authed_weekly_digest.html"

    user = request.user

    email_send = AlertEmailSend.objects.filter(user=user).latest("created")
    alerts = Alert.objects.filter(email=user.email, unsubscribed=False)

    context = {
        "alerts": [],
    }

    for idx, alert in enumerate(alerts):

        # passing a plain dict won't work. It has to be a QueryDict
        query_dict = QueryDict("", mutable=True)
        for key, value in alert.filter.items():
            if isinstance(value, list):
                query_dict.setlist(key, value)
            else:
                query_dict[key] = value

        post_filter = PostFilter(query_dict)
        queryset = post_filter.qs.filter(submitted_datetime__gte=email_send.created - timedelta(days=7))

        name = default_alert_name(alert, idx)

        if queryset.count() > 0:
            context["alerts"].append(
                {
                    "name": name,
                    "queryset": queryset,
                }
            )

    capture_request_event(
        request,
        "alert digest viewed",
        properties={
            "authenticated": True,
            "alert_count": len(context["alerts"]),
            "alert_email_send_id": str(email_send.id),
        },
    )

    return render(request, template_name, context)


class CompanyJobsView(ListView):
    template_name = "jobs/company-jobs.html"
    model = Post

    def get_queryset(self):
        queryset = super().get_queryset()
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
        queryset = super().get_queryset()
        two_months_ago = timezone.now() - timezone.timedelta(days=60)

        return queryset.filter(technologies__slug=self.kwargs.get("slug"), submitted_datetime__gte=two_months_ago)

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
        context["create_alert_form"] = CreateAlertForm

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
        queryset = super().get_queryset()
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
        context["create_alert_form"] = CreateAlertForm

        return context
