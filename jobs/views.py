import logging

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView
from django_filters.views import FilterView
from django_q.tasks import async_task

from hn_jobs.utils import add_users_context
from users.forms import CreateAlertForm

from .constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from .filters import PostFilter
from .models import Post, Technology, Title
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        if user.is_authenticated:
            add_users_context(context, user)

        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "jobs/post_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        if user.is_authenticated:
            add_users_context(context, user)

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
