from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from jobs.choices import PostSource
from jobs.models import Post
from jobs.tasks import (
    MAX_COMPANY_EMAILS_LENGTH,
    apply_remote_ok_structured_defaults,
    build_remote_ok_extraction_text,
    clean_remote_ok_string,
    create_remote_ok_post,
    merge_company_emails,
)
from jobs.utils import clean_job_json_object


class CompanyEmailMergeTests(SimpleTestCase):
    def test_merge_company_emails_deduplicates_and_adds_separator(self):
        assert merge_company_emails("a@example.com", "b@example.com, a@example.com") == ("a@example.com, b@example.com")

    def test_merge_company_emails_is_bounded(self):
        long_email_blob = "a" * (MAX_COMPANY_EMAILS_LENGTH + 100)

        assert len(merge_company_emails("", long_email_blob)) == MAX_COMPANY_EMAILS_LENGTH


class RemoteOkParsingTests(SimpleTestCase):
    def test_clean_remote_ok_string_repairs_mojibake(self):
        assert clean_remote_ok_string("We\u00e2\u0080\u0099re hiring in M\u00c3\u00a9xico") == (
            "We\u2019re hiring in M\u00e9xico"
        )

    def test_build_remote_ok_extraction_text_strips_html_and_preserves_source(self):
        job = {
            "company": "Acme",
            "position": "Senior Python Engineer",
            "location": "Worldwide",
            "tags": ["python", "django"],
            "description": "<p>Build APIs &amp; backend systems.</p>",
            "salary_min": 120000,
            "salary_max": 160000,
        }

        text = build_remote_ok_extraction_text(job)

        assert "Source: Remote OK" in text
        assert "Job title: Senior Python Engineer" in text
        assert "Build APIs & backend systems." in text
        assert "<p>" not in text

    def test_apply_remote_ok_defaults_keeps_structured_identity_fields(self):
        job = {
            "company": "Acme",
            "position": "Python Engineer",
            "location": "Remote",
            "apply_url": "https://remoteOK.com/remote-jobs/example-123",
            "url": "https://remoteOK.com/remote-jobs/example-123",
            "salary_min": 100000,
            "salary_max": 140000,
        }

        data = apply_remote_ok_structured_defaults(job, {})

        assert data["company_name"] == "Acme"
        assert data["job_titles"] == "Python Engineer"
        assert data["locations"] == "Remote"
        assert data["is_remote"] is True
        assert data["company_job_application_link"] == "https://remoteOK.com/remote-jobs/example-123"
        assert data["min_salary"] == 100000
        assert data["max_salary"] == 140000

    def test_clean_job_json_object_normalizes_boolean_strings(self):
        data = clean_job_json_object(
            {"text": "Remote Python role"},
            {
                "company_name": "Acme",
                "job_titles": "Python Engineer",
                "is_remote": "Yes",
                "is_onsite": "No",
                "compensation_summary": "",
            },
        )

        assert data["is_remote"] is True
        assert data["is_onsite"] is False


class RemoteOkImportTests(TestCase):
    @patch("jobs.tasks.get_embedding", return_value=[0.0] * 1536)
    @patch("jobs.tasks.extract_job_data_from_text")
    def test_create_remote_ok_post_persists_source_identity_and_attribution(self, mock_extract, _mock_embedding):
        mock_extract.return_value = {
            "company_name": "",
            "job_titles": "",
            "locations": "",
            "cities": "",
            "countries": "",
            "compensation_summary": "",
            "min_salary": 0,
            "max_salary": 0,
            "currency": "",
            "is_remote": True,
            "remote_timezones": "",
            "is_onsite": False,
            "capacity": "Full-time Employee",
            "description": "Build production Django APIs.",
            "technologies_used": "Python, Django",
            "company_homepage_link": "",
            "emails": "",
            "company_job_application_link": "",
            "names_of_the_contact_person": "",
            "years_of_experience": "",
            "levels_of_experience": "Senior",
        }
        remote_ok_job = {
            "id": "123",
            "epoch": 1780120540,
            "company": "Acme",
            "position": "Senior Python Engineer",
            "tags": ["python", "django"],
            "description": "<p>Build production Django APIs.</p>",
            "location": "Worldwide",
            "apply_url": "https://remoteOK.com/remote-jobs/example-123",
            "url": "https://remoteOK.com/remote-jobs/example-123",
            "salary_min": 120000,
            "salary_max": 160000,
        }

        post = create_remote_ok_post(remote_ok_job)

        assert post.source == PostSource.REMOTE_OK
        assert post.source_external_id == "123"
        assert post.source_url == "https://remoteOK.com/remote-jobs/example-123"
        assert post.who_is_hiring_comment_id is None
        assert post.company.name == "Acme"
        assert post.company_job_application_link == "https://remoteOK.com/remote-jobs/example-123"
        assert post.min_salary == 120000
        assert post.max_salary == 160000
        assert list(post.titles.values_list("name", flat=True)) == ["Senior Python Engineer"]
        assert set(post.technologies.values_list("name", flat=True)) == {"Python", "Django"}
        assert Post.objects.filter(source=PostSource.REMOTE_OK, source_external_id="123").exists()

        same_post = create_remote_ok_post(remote_ok_job)

        assert same_post.id == post.id
        assert Post.objects.filter(source=PostSource.REMOTE_OK, source_external_id="123").count() == 1
        assert mock_extract.call_count == 1
