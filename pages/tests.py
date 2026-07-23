from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomePageRenderTests(TestCase):
    @patch("pages.views.get_latest_submissions")
    def test_home_has_one_database_cta_and_requests_six_jobs(self, get_latest_submissions):
        get_latest_submissions.return_value = []

        response = self.client.get(reverse("home"))

        assert response.status_code == 200
        self.assertContains(response, "Find the right tech job faster")
        self.assertContains(response, "Browse database", count=1)
        self.assertContains(response, f'href="{reverse("posts")}"', count=1)
        self.assertNotContains(response, 'aria-label="Global"')
        get_latest_submissions.assert_called_once_with(6, for_homepage=True)

    def test_verified_user_home_stays_focused_on_database_browsing(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="home-user",
            email="home@example.com",
            password="password",
        )
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        assert response.status_code == 200
        self.assertContains(response, "Browse database", count=1)
        self.assertNotContains(response, "Weekly digest")
        self.assertNotContains(response, "Create alerts")
        self.assertNotContains(response, 'name="intent"')
