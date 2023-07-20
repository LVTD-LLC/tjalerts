from django.urls import path

from .views import HomeView, ProductHuntView, SupportView  # , PricingView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    # path("pricing", PricingView.as_view(), name="pricing"),
    path("product-hunt", ProductHuntView.as_view(), name="product-hunt"),
    path("support", SupportView.as_view(), name="support"),
]
