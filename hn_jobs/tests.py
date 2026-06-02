from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.test import SimpleTestCase, TestCase

from hn_jobs.sitemaps import HighestPaidJobsListicleSitemap
from hn_jobs.utils import add_users_context
from users.models import CustomUser


class UserContextTests(TestCase):
    def test_add_users_context_defaults_unverified_when_email_address_is_missing(self):
        user = CustomUser.objects.create_user(username="missing-email", email="missing@example.com")
        context = {}

        with patch("hn_jobs.utils.logger.warning") as warning_mock:
            add_users_context(context, user)

        assert context["email_verified"] is False
        warning_mock.assert_called_once_with(
            "Email address record missing",
            user_id=user.id,
            email="missing@example.com",
        )

    def test_add_users_context_uses_email_address_verification_state(self):
        user = CustomUser.objects.create_user(username="verified-email", email="verified@example.com")
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
        context = {}

        add_users_context(context, user)

        assert context["email_verified"] is True


class SitemapTests(SimpleTestCase):
    def test_highest_paid_jobs_lastmod_returns_none_without_posts(self):
        technology = object()

        with patch("hn_jobs.sitemaps.Post.objects.filter") as filter_mock:
            filter_mock.return_value.aggregate.return_value = {"latest_date": None}

            assert HighestPaidJobsListicleSitemap().lastmod(technology) is None

        filter_mock.assert_called_once_with(technologies=technology)
