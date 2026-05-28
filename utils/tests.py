from django.test import SimpleTestCase, override_settings

from hn_jobs.utils import build_absolute_site_url, site_metadata


class SiteMetadataTests(SimpleTestCase):
    @override_settings(SITE_URL="https://example.com")
    def test_build_absolute_site_url_uses_configured_host(self):
        assert build_absolute_site_url("/jobs/") == "https://example.com/jobs/"

    @override_settings(SITE_URL="https://example.com")
    def test_build_absolute_site_url_normalizes_relative_paths(self):
        assert build_absolute_site_url("jobs/") == "https://example.com/jobs/"

    @override_settings(SITE_URL="https://example.com")
    def test_site_metadata_exposes_site_url_to_templates(self):
        assert site_metadata(None)["SITE_URL"] == "https://example.com"
