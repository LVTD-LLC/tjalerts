from django.urls import path

from .views import UserSettingsView, generate_api_key, resend_email_confirmation_email

urlpatterns = [
    path("settings/", UserSettingsView.as_view(), name="settings"),
    path("settings/api-key/", generate_api_key, name="generate_api_key"),
    path(
        "send-confirmation",
        resend_email_confirmation_email,
        name="resend_email_confirmation_email",
    ),
]
