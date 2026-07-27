from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.api_keys import authenticate_api_key, rotate_user_api_key
from users.models import UserAPIKey


class UserSettingsTests(TestCase):
    def test_unverified_email_banner_does_not_promise_alert_delivery(self):
        user = get_user_model().objects.create_user(
            username="reader",
            email="reader@example.com",
            password="password",
        )
        EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
        self.client.force_login(user)

        response = self.client.get(reverse("settings"))

        assert response.status_code == 200
        self.assertContains(response, "Confirm your account email")
        self.assertNotContains(response, "keep alerts active")

    def test_settings_includes_api_key_management(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("settings"))

        assert response.status_code == 200
        self.assertContains(response, "API key")
        self.assertContains(response, "Generate API key")

    def test_api_key_generation_requires_login(self):
        response = self.client.post(reverse("generate_api_key"))

        assert response.status_code == 302
        assert response.url.startswith(reverse("account_login"))

    def test_generating_api_key_shows_it_once_without_storing_raw_value(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("generate_api_key"))

        assert response.status_code == 200
        api_key = response.context["generated_api_key"]
        assert api_key.startswith("tja_")
        self.assertContains(response, api_key)
        self.assertEqual(response.headers["Cache-Control"], "max-age=0, no-cache, no-store, must-revalidate, private")
        key_record = UserAPIKey.objects.get(user=user)
        assert api_key not in key_record.key_hash
        assert authenticate_api_key(api_key) == user

        settings_response = self.client.get(reverse("settings"))
        self.assertNotContains(settings_response, api_key)
        self.assertContains(settings_response, f"{key_record.key_prefix}…")

    def test_rotating_api_key_invalidates_the_previous_key(self):
        user = get_user_model().objects.create_user(
            username="agent-user",
            email="agent@example.com",
            password="password",
        )
        self.client.force_login(user)

        first_response = self.client.post(reverse("generate_api_key"))
        second_response = self.client.post(reverse("generate_api_key"))

        first_api_key = first_response.context["generated_api_key"]
        second_api_key = second_response.context["generated_api_key"]
        assert first_api_key != second_api_key
        assert authenticate_api_key(first_api_key) is None
        assert authenticate_api_key(second_api_key) == user
        assert UserAPIKey.objects.filter(user=user).count() == 1


class APIKeyTests(TestCase):
    def test_inactive_user_cannot_authenticate(self):
        user = get_user_model().objects.create_user(username="inactive", is_active=False)
        _, api_key = rotate_user_api_key(user)

        assert authenticate_api_key(api_key) is None
