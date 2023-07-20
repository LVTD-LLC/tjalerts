import logging

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView
from django_filters.views import FilterView
from django_q.tasks import async_task

from hn_jobs.utils import add_users_context, floor_to_tens

from .constants import EXCLUDED_TECHNOLOGIES, EXCLUDED_TITLES
from .filters import PostFilter
from .models import Post, Technology, Title
from .tasks import analyze_hn_page

logger = logging.getLogger(__file__)

excluded_tech = Technology.objects.filter(name__in=EXCLUDED_TECHNOLOGIES)
excluded_titles = Title.objects.filter(name__in=EXCLUDED_TITLES)


class PostListView(FilterView):
    model = Post
    template_name = "jobs/all_jobs.html"
    queryset = (
        Post.objects.all()
        .annotate(num_technologies=Count("technologies"), num_jobs=Count("jobs"))
        .order_by("-submitted_datetime")
    )
    filterset_class = PostFilter
    paginate_by = 6

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["num_of_jobs"] = floor_to_tens(len(Post.objects.all()))

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
        async_task(analyze_hn_page, who_is_hiring_post_id, hook="hooks.print_result")
        return super(TriggerAsyncTask, self).form_valid(form)
