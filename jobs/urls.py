from django.urls import path

from .views import PostDetailView, PostListView, TriggerAsyncTask

urlpatterns = [
    path("", PostListView.as_view(), name="posts"),
    path("<uuid:pk>", PostDetailView.as_view(), name="post"),
    path("trigger-task/", TriggerAsyncTask.as_view(), name="trigger_task"),
]
