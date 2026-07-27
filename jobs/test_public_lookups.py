from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from jobs.models import Company, Post, Technology


class PublicJobLookupTests(TestCase):
    def test_anonymous_user_can_search_technology_filter_options(self):
        technology = Technology.objects.create(name="Django")

        response = self.client.get(reverse("job-technology-search"), {"query": "dja"})

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": str(technology.id),
                "name": "Django",
                "slug": technology.slug,
                "post_count": 0,
            }
        ]

    def test_anonymous_user_can_load_similar_jobs(self):
        company = Company.objects.create(name="Acme")
        post = Post.objects.create(
            company=company,
            description="Python role",
            submitted_datetime=timezone.now(),
        )

        response = self.client.get(reverse("job-similar-posts", kwargs={"pk": post.id}))

        assert response.status_code == 200
        assert response.json() == {"similar_posts": []}
