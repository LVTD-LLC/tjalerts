from django.urls import path

from .views import AlertCreateView, AlertUpdateView, HomeView, SupportView  # , PricingView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    # path("pricing", PricingView.as_view(), name="pricing"),
    path("support", SupportView.as_view(), name="support"),
    path("create-alert", AlertCreateView.as_view(), name="create-alert"),
    path("confirm/<uuid:pk>/", AlertUpdateView.as_view(), name="confirm_subscription"),
]
