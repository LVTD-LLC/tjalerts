from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from api.views import search_technologies
from jobs.choices import PostSource
from jobs.models import Company, Post, Technology
from users.api_keys import rotate_user_api_key


class JobsApiTests(TestCase):
    def setUp(self):
        company = Company.objects.create(name="Acme")
        self.hacker_news_post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="HN role",
            source=PostSource.HACKER_NEWS,
        )
        self.remote_ok_post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="Remote OK role",
            source=PostSource.REMOTE_OK,
        )
        self.we_work_remotely_post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="WWR role",
            source=PostSource.WE_WORK_REMOTELY,
        )
        user = get_user_model().objects.create_user(username="api-user")
        _, api_key = rotate_user_api_key(user)
        self.api_headers = {"HTTP_AUTHORIZATION": f"Bearer {api_key}"}

    def test_jobs_endpoint_requires_api_key(self):
        response = self.client.get(reverse("api-1.0.0:get_jobs"))

        assert response.status_code == 401

    def test_jobs_endpoint_returns_all_sources_without_source_filter(self):
        response = self.client.get(reverse("api-1.0.0:get_jobs"), **self.api_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert {job["source"] for job in data["jobs"]} == set(PostSource.values)

    def test_jobs_endpoint_filters_by_source(self):
        expected_post_ids = {
            PostSource.HACKER_NEWS: str(self.hacker_news_post.id),
            PostSource.REMOTE_OK: str(self.remote_ok_post.id),
            PostSource.WE_WORK_REMOTELY: str(self.we_work_remotely_post.id),
        }

        for source, expected_post_id in expected_post_ids.items():
            with self.subTest(source=source):
                response = self.client.get(reverse("api-1.0.0:get_jobs"), {"source": source}, **self.api_headers)

                assert response.status_code == 200
                data = response.json()
                assert data["count"] == 1
                assert [job["id"] for job in data["jobs"]] == [expected_post_id]
                assert [job["source"] for job in data["jobs"]] == [source]

    def test_jobs_endpoint_rejects_invalid_source(self):
        response = self.client.get(reverse("api-1.0.0:get_jobs"), {"source": "LinkedIn"}, **self.api_headers)

        assert response.status_code == 400

    def test_jobs_endpoint_rejects_invalid_api_key(self):
        response = self.client.get(
            reverse("api-1.0.0:get_jobs"),
            HTTP_AUTHORIZATION="Bearer tja_invalid",
        )

        assert response.status_code == 401

    def test_api_documentation_requires_api_key(self):
        for path in ("/api/docs", "/api/openapi.json"):
            with self.subTest(path=path):
                response = self.client.get(path)

                assert response.status_code == 401
                assert response.headers["WWW-Authenticate"] == "Bearer"

    def test_api_documentation_accepts_api_key(self):
        for path in ("/api/docs", "/api/openapi.json"):
            with self.subTest(path=path):
                response = self.client.get(path, **self.api_headers)

                assert response.status_code == 200


class TechnologySearchTests(TestCase):
    def test_search_technologies_matches_builtin_alias_without_alias_row(self):
        Technology.objects.create(name="Django REST Framework")

        results = search_technologies(None, query="drf")

        assert len(results) == 1
        assert results[0]["name"] == "Django REST Framework"
