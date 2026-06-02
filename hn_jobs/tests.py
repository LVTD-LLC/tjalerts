from unittest.mock import patch

from django.test import SimpleTestCase

from hn_jobs.sitemaps import HighestPaidJobsListicleSitemap


class SitemapTests(SimpleTestCase):
    def test_highest_paid_jobs_lastmod_returns_none_without_posts(self):
        technology = object()

        with patch("hn_jobs.sitemaps.Post.objects.filter") as filter_mock:
            filter_mock.return_value.aggregate.return_value = {"latest_date": None}

            assert HighestPaidJobsListicleSitemap().lastmod(technology) is None

        filter_mock.assert_called_once_with(technologies=technology)
