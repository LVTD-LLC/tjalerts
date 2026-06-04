from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomePageRenderTests(TestCase):
    def test_anonymous_home_keeps_database_browsing_visible(self):
        response = self.client.get(reverse("home"))

        assert response.status_code == 200
        self.assertContains(response, "Browse database")
        self.assertContains(response, reverse("posts"))

    def test_verified_user_home_renders_intent_alert_form(self):
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
        self.assertContains(response, reverse("create-intent-alerts"))
        self.assertContains(response, 'name="intent"')
