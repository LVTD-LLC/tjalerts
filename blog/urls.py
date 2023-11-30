from django.urls import path

from .views import BlogPostListView

urlpatterns = [
    path("", BlogPostListView.as_view(), name="blog-posts"),
    # path("<slug:slug>", BlogPostDetailView.as_view(), name="blog-post"),
]
