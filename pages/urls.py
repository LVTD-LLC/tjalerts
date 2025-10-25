from django.urls import path

from .views import AdminPanelView, HomeView, PrivacyView, SupportView, TosView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    # path("pricing", PricingView.as_view(), name="pricing"),
    # path("product-hunt", ProductHuntView.as_view(), name="product-hunt"),
    path("support", SupportView.as_view(), name="support"),
    path("privacy", PrivacyView.as_view(), name="privacy"),
    path("tos", TosView.as_view(), name="tos"),
    path("admin-panel/", AdminPanelView.as_view(), name="admin-panel"),
]
