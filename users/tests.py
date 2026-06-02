from unittest.mock import Mock, patch

from allauth.account.models import EmailAddress
from django.test import RequestFactory, TestCase

from users.models import CustomUser
from users.views import get_or_create_user_email_address, resend_email_confirmation_email


class EmailConfirmationResendTests(TestCase):
    def test_resend_confirmation_creates_missing_email_address_record(self):
        user = CustomUser.objects.create_user(username="missing-email", email="missing@example.com")
        request = RequestFactory().get("/users/send-confirmation")
        request.user = user
        adapter = Mock()

        with (
            patch("users.views.get_adapter", return_value=adapter),
            patch("users.views.capture_request_event") as capture_event_mock,
            patch("users.views.logger.warning") as warning_mock,
        ):
            response = resend_email_confirmation_email(request)

        emailaddress = EmailAddress.objects.get(user=user, email=user.email)
        assert emailaddress.primary is True
        assert emailaddress.verified is False
        adapter.send_confirmation_mail.assert_called_once_with(request, emailaddress, signup=False)
        capture_event_mock.assert_called_once_with(
            request,
            "email confirmation resent",
            properties={"email_verified": False},
        )
        warning_mock.assert_called_once_with(
            "Email address record created for confirmation resend",
            user_id=user.id,
            email="missing@example.com",
        )
        assert response.status_code == 302

    def test_missing_email_address_record_is_not_primary_when_user_already_has_primary_email(self):
        user = CustomUser.objects.create_user(username="changed-email", email="new@example.com")
        EmailAddress.objects.create(user=user, email="old@example.com", primary=True, verified=True)

        emailaddress = get_or_create_user_email_address(user)

        assert emailaddress.email == "new@example.com"
        assert emailaddress.primary is False
        assert emailaddress.verified is False
