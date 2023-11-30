from django.views.generic import ListView

from .models import BlogPost


class BlogPostListView(ListView):
    model = BlogPost
    queryset = BlogPost.objects.filter(status="PUBLISHED")
    template_name = "blog/blog-post-list.html"
