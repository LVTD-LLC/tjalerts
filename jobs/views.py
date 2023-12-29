import logging

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db.models import Max
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, FormView, ListView, TemplateView, UpdateView
from django_filters.views import FilterView
from django_q.tasks import async_task

from hn_jobs.utils import add_users_context, validate_technology_selected
from users.tasks import find_subs_to_alert, send_confirmation_email
from utils.constants import HIRABLE_TECH_LIST_SLUGS

from .constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from .filters import PostFilter
from .forms import CreateAlertForm, UpdateAlertForm
from .models import Alert, Post, Technology, Title
from .queries import get_most_popular_technologies, get_most_popular_titles
from .tasks import (
    create_backfill_vector_data_jobs,
    create_update_min_and_max_salary_jobs,
    find_bad_submitted_dates,
    get_hn_pages_to_analyze,
)

logger = logging.getLogger(__file__)

excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)


class PostListView(FilterView):
    model = Post
    template_name = "jobs/all_jobs.html"
    filterset_class = PostFilter
    paginate_by = 6

    def get(self, request, *args, **kwargs):
        params = request.GET.copy()

        del params["page"]
        del params["o"]

        logger.info(f"params: {params}")

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

    def get_queryset(self):
        queryset = super().get_queryset()

        tech_id = Technology.objects.filter(slug=self.kwargs.get("slug")).first().id
        subquery = Post.objects.values("company").annotate(latest_post=Max("submitted_datetime")).values("latest_post")

        return (
            queryset.filter(technologies__id=tech_id)
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

        if user.is_authenticated and existing_alerts.count() >= 3:
            messages.add_message(self.request, messages.WARNING, "Free users can only have 3 alerts.")
            return redirect("home")
        elif not user.is_authenticated and existing_alerts.exists():
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
            async_task(send_confirmation_email, form.cleaned_data, confirmation_url)
            messages.add_message(
                self.request, messages.SUCCESS, "Thank for creating an alert! Check your emails to confirm!"
            )

        return super(AlertCreateView, self).form_valid(form)


class AlertUpdateView(SuccessMessageMixin, UpdateView):
    model = Alert
    form_class = UpdateAlertForm
    template_name = "jobs/subscription-confirmation.html"
    success_url = reverse_lazy("home")
    success_message = "Thanks for confirming :) You will receive your alerts soon!"

    def form_valid(self, form):
        response = super(AlertUpdateView, self).form_valid(form)
        async_task(find_subs_to_alert)

        return response
