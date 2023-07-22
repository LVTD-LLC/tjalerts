from django.contrib import sitemaps
from django.contrib.sitemaps import GenericSitemap
from django.urls import reverse

from jobs.models import Post


class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.5

    def items(self):
        return [
            "home",
            "posts",
        ]

    def location(self, item):
        return reverse(item)


sitemaps = {
    "sitemaps": {
        "static": StaticViewSitemap,
        "posts": GenericSitemap(
            {
                "queryset": Post.objects.all(),
                "date_field": "modified",
            }
        ),
    }
}
