from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from jobs.choices import PostSource
from jobs.models import Company, Post, Technology, Title
from jobs.semantic_search import SemanticSearchUnavailableError
from jobs.services import JobNotFoundError, JobQueryError, get_job, search_jobs


class JobQueryServiceTests(TestCase):
    def setUp(self):
        company = Company.objects.create(
            name="Acme",
            company_homepage_link="https://acme.example",
        )
        python = Technology.objects.create(name="Python")
        django = Technology.objects.create(name="Django")
        backend = Title.objects.create(name="Backend Engineer")

        self.remote_post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="Build APIs with Python and Django.",
            source=PostSource.REMOTE_OK,
            source_external_id="remote-1",
            source_url="https://remote.example/jobs/1",
            company_job_application_link="https://acme.example/apply",
            is_remote=True,
            min_salary=120_000,
            max_salary=160_000,
            locations="Worldwide",
        )
        self.remote_post.technologies.add(python, django)
        self.remote_post.titles.add(backend)

        self.onsite_post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="Onsite Go role.",
            source=PostSource.HACKER_NEWS,
            who_is_hiring_comment_id=123,
            is_onsite=True,
            max_salary=100_000,
            locations="Berlin",
        )

    def test_search_jobs_filters_and_serializes_a_bounded_page(self):
        result = search_jobs(
            query="python",
            technologies=["Django"],
            source=PostSource.REMOTE_OK,
            remote=True,
            minimum_salary=150_000,
            page=1,
            page_size=10,
        )

        self.assertEqual(result["count"], 1)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 10)
        self.assertEqual(result["total_pages"], 1)
        self.assertEqual(
            result["jobs"],
            [
                {
                    "id": str(self.remote_post.id),
                    "company_name": "Acme",
                    "compensation_summary": None,
                    "min_salary": 120_000,
                    "max_salary": 160_000,
                    "currency": "",
                    "is_remote": True,
                    "is_onsite": False,
                    "locations": "Worldwide",
                    "technologies": ["Django", "Python"],
                    "titles": ["Backend Engineer"],
                    "source": PostSource.REMOTE_OK,
                    "source_url": "https://remote.example/jobs/1",
                    "submitted_datetime": self.remote_post.submitted_datetime.isoformat(),
                }
            ],
        )

    def test_search_jobs_excludes_incomplete_posts(self):
        incomplete_post = Post.objects.create(
            company=self.remote_post.company,
            submitted_datetime=timezone.now(),
            description="",
            source=PostSource.REMOTE_OK,
        )

        result = search_jobs()

        self.assertEqual(result["count"], 2)
        self.assertNotIn(str(incomplete_post.id), [job["id"] for job in result["jobs"]])

    @patch("jobs.semantic_search.get_embedding", return_value=[0.0] * 1536)
    def test_search_jobs_semantic_query_orders_jobs_by_vector_distance(self, get_embedding):
        self.remote_post.vector = [0.0] * 1536
        self.remote_post.submitted_datetime = timezone.now() - timedelta(days=1)
        self.remote_post.save(update_fields=["vector", "submitted_datetime"])
        self.onsite_post.vector = [0.01] * 1536
        self.onsite_post.submitted_datetime = timezone.now()
        self.onsite_post.save(update_fields=["vector", "submitted_datetime"])

        result = search_jobs(semantic_query="distributed systems")

        get_embedding.assert_called_once_with("distributed systems")
        self.assertEqual(
            [job["id"] for job in result["jobs"]],
            [str(self.remote_post.id), str(self.onsite_post.id)],
        )

    @patch("jobs.semantic_search.get_embedding", side_effect=TimeoutError("provider timeout"))
    def test_search_jobs_translates_embedding_provider_failure(self, _get_embedding):
        with self.assertRaisesMessage(
            SemanticSearchUnavailableError,
            "Semantic search is temporarily unavailable",
        ):
            search_jobs(semantic_query="distributed systems")

    def test_get_job_returns_one_serialized_job(self):
        result = get_job(self.remote_post.id)

        self.assertEqual(result["id"], str(self.remote_post.id))
        self.assertEqual(result["technologies"], ["Django", "Python"])
        self.assertEqual(result["titles"], ["Backend Engineer"])

    def test_get_job_rejects_an_incomplete_post(self):
        incomplete_post = Post.objects.create(
            company=self.remote_post.company,
            submitted_datetime=timezone.now(),
            description="",
            source=PostSource.REMOTE_OK,
        )

        with self.assertRaisesMessage(JobNotFoundError, f"Job not found: {incomplete_post.id}"):
            get_job(incomplete_post.id)

    def test_search_jobs_rejects_invalid_source(self):
        with self.assertRaisesMessage(JobQueryError, "Unsupported job source"):
            search_jobs(source="LinkedIn")

    def test_search_jobs_rejects_unbounded_page_size(self):
        with self.assertRaisesMessage(JobQueryError, "page_size must be between 1 and 100"):
            search_jobs(page_size=101)

    def test_search_jobs_rejects_too_many_technology_filters(self):
        with self.assertRaisesMessage(JobQueryError, "at most 10 technology filters"):
            search_jobs(technologies=[f"technology-{index}" for index in range(11)])

    def test_search_jobs_rejects_oversized_text_inputs(self):
        with self.assertRaisesMessage(JobQueryError, "query cannot exceed 500 characters"):
            search_jobs(query="x" * 501)

        with self.assertRaisesMessage(JobQueryError, "technology names cannot exceed 100 characters"):
            search_jobs(technologies=["x" * 101])

    @patch("jobs.semantic_search.get_embedding")
    def test_search_jobs_validates_filters_before_generating_embedding(self, get_embedding):
        with self.assertRaisesMessage(JobQueryError, "technology names cannot exceed 100 characters"):
            search_jobs(
                semantic_query="distributed systems",
                technologies=["x" * 101],
            )

        get_embedding.assert_not_called()

    def test_search_jobs_rejects_an_excessive_page(self):
        with self.assertRaisesMessage(JobQueryError, "page must be between 1 and 10000"):
            search_jobs(page=10_001)
