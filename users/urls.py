from django.urls import path

from .views import UserSettingsView, resend_email_confirmation_email

urlpatterns = [
    path("settings/", UserSettingsView.as_view(), name="settings"),
    path(
        "send-confirmation",
        resend_email_confirmation_email,
        name="resend_email_confirmation_email",
    ),
]
