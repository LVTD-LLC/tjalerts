from datetime import timedelta

from django.contrib import sitemaps
from django.contrib.sitemaps import GenericSitemap
from django.db.models import Count, Max
from django.urls import reverse
from django.utils import timezone

from jobs.models import Company, Post, Technology
from utils.constants import HIRABLE_TECH_LIST_SLUGS


class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.9
    protocol = "https"

    def items(self):
        return [
            "home",
            "companies",
        ]

    def location(self, item):
        return reverse(item)


class HighestPaidJobsListicleSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return (
            Technology.objects.filter(slug__in=HIRABLE_TECH_LIST_SLUGS)
            .annotate(num_posts=Count("post"))
            .filter(num_posts__gt=0)
        )

    def lastmod(self, obj):
        print(obj)
        return obj.post.order_by("-submitted_datetime").first().submitted_datetime

    def location(self, obj):
        return reverse("highest-paid-job-blog-post", kwargs={"slug": obj.slug})


class CompaniesJobsListicleSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        companies_with_recent_posts = (
            Company.objects.filter(post__created__gte=timezone.now() - timedelta(days=60))
            .annotate(num_posts=Count("post"))
            .filter(num_posts__gt=0)
            .distinct()
        )
        return companies_with_recent_posts

    def lastmod(self, obj):
        return Post.objects.filter(company=obj).aggregate(latest_date=Max("submitted_datetime"))["latest_date"]

    def location(self, obj):
        return reverse("company-jobs", kwargs={"slug": obj.slug})


sitemaps = {
    "sitemaps": {
        "static": StaticViewSitemap,
        "highest_paid_jobs_listicle": HighestPaidJobsListicleSitemap,
        "company_jobs": CompaniesJobsListicleSitemap,
        "posts": GenericSitemap(
            {
                "queryset": Post.objects.all(),
                "date_field": "modified",
            },
            priority=0.7,
            protocol="https",
        ),
    }
}
