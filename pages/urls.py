from django.urls import path
from .views import HomePageView, BuyPageView, ContactPageView

app_name = "pages"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("buy/", BuyPageView.as_view(), name="buy"),
    path("contact/", ContactPageView.as_view(), name="contact"),
]
