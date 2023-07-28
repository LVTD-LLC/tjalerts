from django.urls import path

from .views import PostDetailView, PostListView, TriggerAsyncTask, find_bad_submitted_dates_view

urlpatterns = [
    path("", PostListView.as_view(), name="posts"),
    path("<uuid:pk>", PostDetailView.as_view(), name="post"),
    path("trigger-task/", TriggerAsyncTask.as_view(), name="trigger_task"),
    path("find_bad_submitted_dates/", find_bad_submitted_dates_view, name="find-bad-submitted-dates"),
]
