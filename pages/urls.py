# pages/urls.py
from django.urls import path
from . import views
from .views import health

app_name = "pages"

urlpatterns = [
    path("", views.home, name="home"),

    # Core pages
    path("contact/", views.contact, name="contact"),

    # BUY
    path("buy/map/", views.buy_map, name="buy_map"),
    path("buy/neighborhoods/", views.buy_neighborhoods, name="buy_neighborhoods"),
    path("buy/off-market/", views.buy_off_market, name="buy_off_market"),

    # SELL
    path("sell/valuation/", views.sell_valuation, name="sell_valuation"),
    path("sell/marketing/", views.sell_marketing, name="sell_marketing"),
    path("sell/concierge/", views.sell_concierge, name="sell_concierge"),

    # Lifestyle
    path("lifestyle/", views.lifestyle, name="lifestyle"),

    # Portal placeholders (later you can wire to auth)
    path("portal/login/", views.portal_login, name="portal_login"),
    path("portal/", views.portal_dashboard, name="portal_dashboard"),

    # Healthcheck
    path("health/", views.health, name="health"),
]