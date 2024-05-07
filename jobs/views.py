from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Exists, Max, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from django_q.tasks import async_task

from hn_jobs.utils import add_users_context, get_tjalerts_logger, validate_technology_selected
from jobs.utils import default_alert_name
from utils.constants import HIRABLE_TECH_LIST_SLUGS

from .constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from .filters import PostFilter
from .forms import ConfirmAlertForm, CreateAlertForm
from .models import Alert, AlertEmailSend, Company, Post, Technology, TechnologyMapping, Title
from .queries import get_most_popular_technologies, get_most_popular_titles
from .tasks import (
    create_backfill_vector_data_jobs,
    create_update_min_and_max_salary_jobs,
    find_bad_submitted_dates,
    find_users_to_alert,
    get_hn_pages_to_analyze,
    send_confirmation_email,
)

logger = get_tjalerts_logger(__name__)

excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)


class PostListView(FilterView):
    model = Post
    template_name = "jobs/all_jobs.html"
    filterset_class = PostFilter
    paginate_by = 6

    def get(self, request, *args, **kwargs):
        params = request.GET.copy()

        try:
            del params["page"]
            del params["o"]
        except KeyError:
            pass

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        if user.is_authenticated:
            add_users_context(context, user, self)

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
        context["popular_titles"] = get_most_popular_titles()
        context["popular_technologies"] = get_most_popular_technologies(min_count=2)

        return context


class GenericForm(forms.Form):
    who_is_hiring_post_id = forms.CharField()


class TriggerAsyncTask(LoginRequiredMixin, UserPassesTestMixin, FormView):
    login_url = "account_login"
    success_url = reverse_lazy("home")
    template_name = "jobs/trigger_task.html"
    form_class = GenericForm

    def test_func(self):
        return self.request.user.is_staff

    def form_valid(self, form):
        who_is_hiring_post_id = form.cleaned_data.get("who_is_hiring_post_id")  # noqa: F841
        async_task(get_hn_pages_to_analyze, who_is_hiring_post_id, hook="hooks.print_result")
        return super(TriggerAsyncTask, self).form_valid(form)


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
        latest_date = max(dates)

        context["tech_name"] = tech.name
        context["tech_id"] = tech.id
        context["canonical_url"] = self.request.build_absolute_uri(self.request.path)
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
def find_bad_submitted_dates_view(request):
    async_task(find_bad_submitted_dates, hook="jobs.hooks.print_result", group="Find Bad Datetimes to Fix")

    return redirect("trigger_task")


def update_min_and_max_salary_view(request):
    async_task(
        create_update_min_and_max_salary_jobs, hook="jobs.hooks.print_result", group="Populate min and max salary"
    )

    return redirect("trigger_task")


def create_backfill_vector_data_jobs_view(request):
    async_task(
        create_backfill_vector_data_jobs, hook="jobs.hooks.print_result", group="Create Jobs to Update Vector Data."
    )

    return redirect("trigger_task")


class AlertCreateView(SuccessMessageMixin, CreateView):
    template_name = "jobs/create-alert.html"
    model = Alert
    form_class = CreateAlertForm
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        user = self.request.user
        existing_alerts = Alert.objects.filter(email=form.instance.email)

        if user.is_authenticated:
            form.instance.user = user

        technology_id = str(Technology.objects.get(name=form.cleaned_data["technology_selected"]).id)

        form.instance.filter = {"technologies": [technology_id]}

        try:
            validate_technology_selected(form.cleaned_data["technology_selected"])
        except ValidationError:
            messages.add_message(self.request, messages.WARNING, "Please use a Technology from the dropdown list.")
            return redirect("home")

        # if user.is_authenticated and existing_alerts.count() >= 3:
        #     messages.add_message(self.request, messages.WARNING, "Free users can only have 3 alerts.")
        #     return redirect("home")

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
            confirmation_url = self.request.build_absolute_uri(reverse("confirm_subscription", args=[form.instance.id]))
            async_task(send_confirmation_email, form.cleaned_data, confirmation_url, group="Send Confirmation Email")
            messages.add_message(
                self.request, messages.SUCCESS, "Thank for creating an alert! Check your emails to confirm!"
            )

        async_task(find_users_to_alert, group="Find Users to Alert")

        return super(AlertCreateView, self).form_valid(form)


class ConfirmAlertView(SuccessMessageMixin, UpdateView):
    model = Alert
    form_class = ConfirmAlertForm
    template_name = "jobs/subscription-confirmation.html"
    success_url = reverse_lazy("home")
    success_message = "Thanks for confirming :) You will receive your alerts soon!"

    def form_valid(self, form):
        response = super(ConfirmAlertView, self).form_valid(form)
        async_task(find_users_to_alert, group="Find Users to Alert")

        return response


def unauthed_weekly_digest_view(request, alert_email_send_id):
    template_name = "jobs/unauthed_weekly_digest.html"

    alert_email_send = get_object_or_404(AlertEmailSend, id=alert_email_send_id)
    alert = Alert.objects.get(email=alert_email_send.email, user__isnull=True)

    post_filter = PostFilter(alert.filter)
    queryset = post_filter.qs.filter(submitted_datetime__gte=alert_email_send.created - timedelta(days=7))
    name = f"{Technology.objects.get(id=alert.filter['technologies'][0]).name} Alert"

    context = {"alert": alert, "queryset": queryset, "name": name}
    return render(request, template_name, context)


def unsubscribe_from_unauthed_alert(request, alert_email_send_id):
    alert_email_send = get_object_or_404(AlertEmailSend, id=alert_email_send_id)
    alert = Alert.objects.get(email=alert_email_send.email, user__isnull=True)

    if request.method == "POST":
        alert.unsubscribed = True
        alert.save()
        messages.success(request, "You have been unsubscribed from the alert successfully.")
        return redirect(reverse("home"))

    return render(request, "jobs/unsubscribe_from_unauthed_alert.html", {"alert_email_send": alert_email_send})


@login_required(login_url="account_login")
def toggle_subscription_from_authed_alert(request, alert_id):
    alert = get_object_or_404(Alert, id=alert_id)

    if request.method == "POST":
        alert.unsubscribed = not alert.unsubscribed
        alert.save()

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
    alerts = Alert.objects.filter(email=user.email)

    context = {"alerts": []}

    for idx, alert in enumerate(alerts):
        post_filter = PostFilter(alert.filter)
        queryset = post_filter.qs.filter(submitted_datetime__gte=email_send.created - timedelta(days=7))

        name = default_alert_name(alert, idx)

        context["alerts"].append(
            {
                "name": name,
                "queryset": queryset,
            }
        )

    return render(request, template_name, context)


class CompanyJobsView(ListView):
    template_name = "jobs/company-jobs.html"
    model = Post

    def get_queryset(self):
        queryset = super().get_queryset()

        return queryset.filter(company__slug=self.kwargs.get("slug"))


class CompaniesJobsView(ListView):
    template_name = "jobs/companies-with-jobs.html"
    model = Company

    def get_queryset(self):
        three_months_ago = timezone.now() - timezone.timedelta(days=90)
        recent_posts = Post.objects.filter(created__gte=three_months_ago).values("company")

        queryset = (
            super()
            .get_queryset()
            .annotate(has_recent_posts=Exists(recent_posts.filter(company=OuterRef("pk"))))
            .filter(has_recent_posts=True)
        )

        return queryset
