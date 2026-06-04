from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from jobs.choices import PostSource
from jobs.models import Company, Post


class JobsApiTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Acme")
        Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="HN role",
            source=PostSource.HACKER_NEWS,
        )
        Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="Remote OK role",
            source=PostSource.REMOTE_OK,
        )
        Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="WWR role",
            source=PostSource.WE_WORK_REMOTELY,
        )

    def test_jobs_endpoint_filters_by_source(self):
        response = self.client.get(reverse("api-1.0.0:get_jobs"), {"source": PostSource.REMOTE_OK})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert [job["source"] for job in data["jobs"]] == [PostSource.REMOTE_OK]

    def test_jobs_endpoint_rejects_invalid_source(self):
        response = self.client.get(reverse("api-1.0.0:get_jobs"), {"source": "LinkedIn"})

        assert response.status_code == 400
