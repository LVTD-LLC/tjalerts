from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
