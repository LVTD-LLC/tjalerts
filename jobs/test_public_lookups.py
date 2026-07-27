from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from jobs.models import Company, Post, Technology, Title


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

    def test_anonymous_user_can_search_title_filter_options(self):
        title = Title.objects.create(name="Backend Engineer")

        response = self.client.get(reverse("job-title-search"), {"query": "backend"})

        assert response.status_code == 200
        assert response.json() == [
            {
                "id": str(title.id),
                "name": "Backend Engineer",
                "slug": title.slug,
                "post_count": 0,
            }
        ]

    def test_anonymous_user_can_restore_filter_options(self):
        technology = Technology.objects.create(name="Django")
        title = Title.objects.create(name="Backend Engineer")

        technology_response = self.client.get(
            reverse("job-technology-detail", kwargs={"pk": technology.id}),
        )
        title_response = self.client.get(
            reverse("job-title-detail", kwargs={"pk": title.id}),
        )

        assert technology_response.status_code == 200
        assert technology_response.json() == {
            "id": str(technology.id),
            "name": "Django",
            "slug": technology.slug,
            "post_count": 0,
        }
        assert title_response.status_code == 200
        assert title_response.json() == {
            "id": str(title.id),
            "name": "Backend Engineer",
            "slug": title.slug,
            "post_count": 0,
        }

    def test_filter_option_details_return_not_found_for_unknown_ids(self):
        technology = Technology.objects.create(name="Django")
        technology_id = technology.id
        technology.delete()
        title = Title.objects.create(name="Backend Engineer")
        title_id = title.id
        title.delete()

        technology_response = self.client.get(
            reverse("job-technology-detail", kwargs={"pk": technology_id}),
        )
        title_response = self.client.get(
            reverse("job-title-detail", kwargs={"pk": title_id}),
        )

        assert technology_response.status_code == 404
        assert technology_response.json() == {"error": "Not found"}
        assert title_response.status_code == 404
        assert title_response.json() == {"error": "Not found"}
