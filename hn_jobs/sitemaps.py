from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlsplit

from django.contrib import sitemaps
from django.conf import settings

# from django.contrib.sitemaps import GenericSitemap
from django.db.models import Count, Exists, Max, OuterRef
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost
from jobs.constants import EXCLUDED_TECHNOLOGIES
from jobs.models import Company, Post, Technology, Title
from utils.constants import HIRABLE_TECH_LIST_SLUGS


class CanonicalHostSitemap(sitemaps.Sitemap):
    def get_urls(self, page=1, site=None, protocol=None):
        canonical_site = SimpleNamespace(domain=urlsplit(settings.SITE_URL).netloc)
        return super().get_urls(page=page, site=canonical_site, protocol=protocol)


class StaticViewSitemap(CanonicalHostSitemap):
    priority = 0.9
    protocol = "https"

    def items(self):
        return [
            "home",
            "support",
            "privacy",
            "tos",
            "uses",
            "companies",
            "technologies",
            "titles",
            "blog-posts",
            "posts",
        ]

    def location(self, item):
        return reverse(item)


class HighestPaidJobsListicleSitemap(CanonicalHostSitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return (
            Technology.objects.filter(slug__in=HIRABLE_TECH_LIST_SLUGS, post__isnull=False)
            .order_by("slug")
            .values_list("slug", flat=True)
            .distinct()
        )

    def lastmod(self, slug):
        return Post.objects.filter(technologies__slug=slug).aggregate(latest_date=Max("submitted_datetime"))[
            "latest_date"
        ]

    def location(self, slug):
        return reverse("highest-paid-job-blog-post", kwargs={"slug": slug})


class CompaniesJobsListicleSitemap(CanonicalHostSitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        two_months_ago = timezone.now() - timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("company")

        return (
            Company.objects.annotate(has_recent_posts=Exists(recent_posts.filter(company=OuterRef("pk"))))
            .filter(has_recent_posts=True)
            .exclude(name="", slug="")
            .order_by("slug")
            .values_list("slug", flat=True)
            .distinct()
        )

    def lastmod(self, slug):
        return Post.objects.filter(company__slug=slug).aggregate(latest_date=Max("submitted_datetime"))["latest_date"]

    def location(self, slug):
        return reverse("company-jobs", kwargs={"slug": slug})


class TechnologiesJobsListicleSitemap(CanonicalHostSitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        two_months_ago = timezone.now() - timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("technologies")

        return (
            Technology.objects.exclude(name__in=EXCLUDED_TECHNOLOGIES)
            .annotate(
                post_count=Count("posttechnology"),
                has_recent_posts=Exists(recent_posts.filter(technologies=OuterRef("pk"))),
            )
            .filter(has_recent_posts=True, post_count__gt=0)
            .exclude(slug="")
            .order_by("slug")
            .values_list("slug", flat=True)
            .distinct()
        )

    def lastmod(self, slug):
        return Post.objects.filter(technologies__slug=slug).aggregate(latest_date=Max("submitted_datetime"))[
            "latest_date"
        ]

    def location(self, slug):
        return reverse("technology-jobs", kwargs={"slug": slug})


class TitlesJobsListicleSitemap(CanonicalHostSitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        two_months_ago = timezone.now() - timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("titles")

        return (
            Title.objects.annotate(
                post_count=Count("posttitle"),
                has_recent_posts=Exists(recent_posts.filter(titles=OuterRef("pk"))),
            )
            .filter(has_recent_posts=True, post_count__gt=0)
            .exclude(slug="")
            .order_by("slug")
            .values_list("slug", flat=True)
            .distinct()
        )

    def lastmod(self, slug):
        return Post.objects.filter(titles__slug=slug).aggregate(latest_date=Max("submitted_datetime"))["latest_date"]

    def location(self, slug):
        return reverse("title-jobs", kwargs={"slug": slug})


class BlogPostSitemap(CanonicalHostSitemap):
    changefreq = "weekly"
    priority = 0.91
    protocol = "https"

    def items(self):
        return BlogPost.objects.filter(status=BlogPost.PUBLISHED)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("blog-post", kwargs={"slug": obj.slug})


class RecentPostSitemap(CanonicalHostSitemap):
    changefreq = "daily"
    priority = 0.7
    protocol = "https"

    def items(self):
        two_months_ago = timezone.now() - timedelta(days=60)
        return Post.objects.filter(created__gte=two_months_ago).exclude(description="")

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return obj.get_absolute_url()


sitemaps = {
    "sitemaps": {
        "static": StaticViewSitemap,
        "blog-posts": BlogPostSitemap,
        "highest_paid_jobs_listicle": HighestPaidJobsListicleSitemap,
        "company_jobs": CompaniesJobsListicleSitemap,
        "technology_jobs": TechnologiesJobsListicleSitemap,
        "title_jobs": TitlesJobsListicleSitemap,
        "posts": RecentPostSitemap,
    }
}
