from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from jobs.models import Company, Post, Technology, Title


class HomePageRenderTests(TestCase):
    @patch("pages.views.get_latest_submissions")
    def test_home_has_search_focused_copy_and_requests_six_jobs(self, get_latest_submissions):
        get_latest_submissions.return_value = []

        response = self.client.get(reverse("home"))

        assert response.status_code == 200
        self.assertContains(
            response, "<title>Developer Jobs Database | Search Tech &amp; Startup Jobs</title>", html=True
        )
        self.assertContains(response, "Find the right tech job faster")
        self.assertContains(response, "Search current developer and startup jobs gathered from across the web.")
        self.assertContains(response, "Browse database", count=1)
        self.assertContains(response, "Latest jobs")
        self.assertNotContains(response, "Six recent jobs")
        self.assertNotContains(response, "Hacker News")
        self.assertNotContains(response, "Remote OK")
        self.assertNotContains(response, "data-uidotsh-pick")
        self.assertNotContains(response, "https://ui.sh/ui-picker.js")
        self.assertNotContains(response, 'aria-label="Global"')
        get_latest_submissions.assert_called_once_with(6, for_homepage=True)

    @patch("pages.views.get_latest_submissions")
    def test_home_has_ai_agent_mcp_prompt_cta(self, get_latest_submissions):
        get_latest_submissions.return_value = []

        response = self.client.get(reverse("home"))

        assert response.status_code == 200
        self.assertContains(response, "Copy Prompt for AI")
        self.assertContains(response, 'data-controller="copy-prompt"')
        self.assertContains(response, 'data-action="copy-prompt#copy"')
        self.assertContains(response, "https://jobs.lvtd.dev/mcp/")
        self.assertContains(response, "https://jobs.lvtd.dev/users/settings/")
        self.assertContains(response, "Authorization: Bearer")
        self.assertContains(response, "search_jobs")
        self.assertContains(response, "get_job")
        self.assertContains(response, "Treat the key as a secret")
        self.assertContains(response, "this MCP server is read-only")

    def test_home_job_cards_link_to_job_role_and_technology_results(self):
        company = Company.objects.create(name="Northstar Labs")
        title = Title.objects.create(name="Backend Engineer")
        technology = Technology.objects.create(name="Django")
        post = Post.objects.create(
            company=company,
            submitted_datetime=timezone.now(),
            description="Build reliable data services.",
        )
        post.titles.add(title)
        post.technologies.add(technology)

        response = self.client.get(reverse("home"))

        assert response.status_code == 200
        self.assertContains(response, f'href="{reverse("post", args=[post.id])}"', count=1)
        self.assertContains(response, f'href="{reverse("title-jobs", args=[title.slug])}"', count=1)
        self.assertContains(response, f'href="{reverse("technology-jobs", args=[technology.slug])}"', count=1)

    def test_non_home_pages_keep_global_navigation(self):
        response = self.client.get(reverse("posts"))

        assert response.status_code == 200
        self.assertContains(response, 'aria-label="Global"')
        self.assertContains(response, "Create account")

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
