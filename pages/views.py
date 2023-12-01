import logging

from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import FormView, TemplateView
from django_q.tasks import async_task

from hn_jobs.utils import add_users_context
from jobs.queries import get_latest_submissions, get_most_popular_technologies, get_most_popular_titles
from users.forms import CreateAlertForm

from .forms import SupportForm
from .tasks import email_support_request

logger = logging.getLogger(__file__)


class HomeView(TemplateView):
    template_name = "pages/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context["latest_job_submissions"] = get_latest_submissions(9, for_homepage=True)
        context["popular_titles"] = get_most_popular_titles()
        context["popular_technologies"] = get_most_popular_technologies(min_count=2)
        context["create_alert_form"] = CreateAlertForm

        if user.is_authenticated:
            add_users_context(context, user, self)

        return context


class PrivacyView(TemplateView):
    template_name = "pages/privacy_policy.html"


class TosView(TemplateView):
    template_name = "pages/tos.html"


class PricingView(TemplateView):
    template_name = "pages/pricing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_authenticated:
            add_users_context(context, user, self)

        return context


class SupportView(FormView):
    template_name = "pages/support.html"
    form_class = SupportForm

    def get_success_url(self):
        messages.add_message(
            self.request,
            messages.INFO,
            "Thanks for sending your feedback. I'll get back to you ASAP.",
        )
        return reverse_lazy("home")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user
        if user.is_authenticated:
            add_users_context(context, user, self)

        return context

    def form_valid(self, form):
        async_task(email_support_request, form.cleaned_data, hook="hooks.email_sent")
        return super(SupportView, self).form_valid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs


class ProductHuntView(TemplateView):
    template_name = "pages/product_hunt.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context["latest_job_submissions"] = get_latest_submissions(9, for_homepage=True)
        context["popular_titles"] = get_most_popular_titles()
        context["popular_technologies"] = get_most_popular_technologies(min_count=2)
        context["create_alert_form"] = CreateAlertForm

        if user.is_authenticated:
            add_users_context(context, user, self)

        return context
