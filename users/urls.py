from django.urls import path

from .views import AlertCreateView, AlertUpdateView, UserSettingsView, resend_email_confirmation_email

urlpatterns = [
    path("settings/", UserSettingsView.as_view(), name="settings"),
    path(
        "send-confirmation",
        resend_email_confirmation_email,
        name="resend_email_confirmation_email",
    ),
    path("create-alert", AlertCreateView.as_view(), name="create-alert"),
    path("confirm/<uuid:pk>/", AlertUpdateView.as_view(), name="confirm_subscription"),
]
