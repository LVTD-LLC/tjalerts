from django.contrib import sitemaps

# from django.contrib.sitemaps import GenericSitemap
from django.db.models import Count, Exists, Max, OuterRef
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost
from jobs.constants import EXCLUDED_TECHNOLOGIES
from jobs.models import Company, Post, Technology, Title
from utils.constants import HIRABLE_TECH_LIST_SLUGS


class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.9
    protocol = "https"

    def items(self):
        return [
            "home",
            "companies",
            "technologies",
            "titles",
            "blog-posts",
            "posts",
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
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("company")

        companies_with_recent_posts = (
            Company.objects.annotate(has_recent_posts=Exists(recent_posts.filter(company=OuterRef("pk"))))
            .filter(has_recent_posts=True)
            .exclude(name="")
            .distinct()
        )
        return companies_with_recent_posts

    def lastmod(self, obj):
        return Post.objects.filter(company=obj).aggregate(latest_date=Max("submitted_datetime"))["latest_date"]

    def location(self, obj):
        return reverse("company-jobs", kwargs={"slug": obj.slug})


class TechnologiesJobsListicleSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("technologies")

        technologies_with_recent_posts = (
            Technology.objects.exclude(name__in=EXCLUDED_TECHNOLOGIES)
            .annotate(
                post_count=Count("posttechnology"),
                has_recent_posts=Exists(recent_posts.filter(technologies=OuterRef("pk"))),
            )
            .filter(has_recent_posts=True, post_count__gt=0)
            .distinct()
        )
        return technologies_with_recent_posts

    def lastmod(self, obj):
        return Post.objects.filter(technologies=obj).aggregate(latest_date=Max("submitted_datetime"))["latest_date"]

    def location(self, obj):
        return reverse("technology-jobs", kwargs={"slug": obj.slug})


class TitlesJobsListicleSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        two_months_ago = timezone.now() - timezone.timedelta(days=60)
        recent_posts = Post.objects.filter(submitted_datetime__gte=two_months_ago).values("titles")

        titles_with_recent_posts = (
            Title.objects.annotate(
                post_count=Count("posttitle"),
                has_recent_posts=Exists(recent_posts.filter(titles=OuterRef("pk"))),
            )
            .filter(has_recent_posts=True, post_count__gt=0)
            .distinct()
        )
        return titles_with_recent_posts

    def lastmod(self, obj):
        return Post.objects.filter(titles=obj).aggregate(latest_date=Max("submitted_datetime"))["latest_date"]

    def location(self, obj):
        return reverse("title-jobs", kwargs={"slug": obj.slug})


class BlogPostSitemap(sitemaps.Sitemap):
    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def items(self):
        return BlogPost.objects.filter(status=BlogPost.PUBLISHED)

    def lastmod(self, obj):
        return obj.modified

    def location(self, obj):
        return reverse("blog-post-detail", kwargs={"slug": obj.slug})


sitemaps = {
    "sitemaps": {
        "static": StaticViewSitemap,
        "blog-posts": BlogPostSitemap,
        # "highest_paid_jobs_listicle": HighestPaidJobsListicleSitemap,
        # "company_jobs": CompaniesJobsListicleSitemap,
        # "technology_jobs": TechnologiesJobsListicleSitemap,
        # "title_jobs": TitlesJobsListicleSitemap,
        # "posts": GenericSitemap(
        #     {
        #         "queryset": Post.objects.filter(created__gte=timezone.now() - timezone.timedelta(days=60)),
        #         "date_field": "modified",
        #     },
        #     priority=0.7,
        #     protocol="https",
        # ),
    }
}
