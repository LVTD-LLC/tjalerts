from django.urls import path

from .views import (
    AlertCreateView,
    ConfirmAlertView,
    HighestPaidJobsView,
    PostDetailView,
    PostListView,
    TriggerAsyncTask,
    authed_weekly_digest_view,
    create_backfill_vector_data_jobs_view,
    find_bad_submitted_dates_view,
    toggle_subscription_from_authed_alert,
    unauthed_weekly_digest_view,
    unsubscribe_from_unauthed_alert,
    update_min_and_max_salary_view,
)

urlpatterns = [
    path("", PostListView.as_view(), name="posts"),
    path("<uuid:pk>", PostDetailView.as_view(), name="post"),
    path("trigger-task/", TriggerAsyncTask.as_view(), name="trigger_task"),
    path("find_bad_submitted_dates/", find_bad_submitted_dates_view, name="find-bad-submitted-dates"),
    path("update_min_and_max_salary/", update_min_and_max_salary_view, name="update_min_and_max_salary"),
    path(
        "create_backfill_vector_data_jobs/<int:rebuild>/",
        create_backfill_vector_data_jobs_view,
        name="create_backfill_vector_data_jobs",
    ),
    # path("highest-paid-list", HighestPaidBlogPostListView.as_view(), name="highest-paid-blog-posts"),
    path("create-alert", AlertCreateView.as_view(), name="create-alert"),
    path("confirm/<uuid:pk>/", ConfirmAlertView.as_view(), name="confirm_subscription"),
    path("<slug:slug>/highest-paid/", HighestPaidJobsView.as_view(), name="highest-paid-job-blog-post"),
    path("digest/<uuid:alert_email_send_id>/", unauthed_weekly_digest_view, name="unauthed_weekly_digest"),
    path("digest/", authed_weekly_digest_view, name="authed_weekly_digest"),
    path(
        "unsubscribe/u/<uuid:alert_email_send_id>/", unsubscribe_from_unauthed_alert, name="unauthed_alert_unsubscribe"
    ),
    path(
        "unsubscribe/<uuid:alert_id>/",
        toggle_subscription_from_authed_alert,
        name="toggle_subscription_from_authed_alert",
    ),
]
