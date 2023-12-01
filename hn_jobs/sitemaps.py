from django.contrib import sitemaps
from django.contrib.sitemaps import GenericSitemap
from django.urls import reverse

from jobs.models import Post, Technology
from utils.constants import HIRABLE_TECH_LIST_SLUGS


class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.5

    def items(self):
        return [
            "home",
            "posts",
        ]

    def location(self, item):
        return reverse(item)


class HighestPaidJobsListicleSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.5

    def items(self):
        return Technology.objects.filter(slug__in=HIRABLE_TECH_LIST_SLUGS)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("highest-paid-job-blog-post", kwargs={"slug": obj.slug})


sitemaps = {
    "sitemaps": {
        "static": StaticViewSitemap,
        "highest_paid_jobs_listicle": HighestPaidJobsListicleSitemap,
        "posts": GenericSitemap(
            {
                "queryset": Post.objects.all(),
                "date_field": "modified",
            }
        ),
    }
}
