# pages/urls.py
from django.urls import path
from . import views

app_name = "pages"

urlpatterns = [
    path("", views.home, name="home"),
    path("contact/", views.contact, name="contact"),

    # BUY
    path("buy/", views.buy, name="buy"),
    path("buy/map/", views.buy_map, name="buy_map"),
    path("buy/neighborhoods/", views.buy_neighborhoods, name="buy_neighborhoods"),
    path("buy/off-market/", views.buy_off_market, name="buy_off_market"),

    # SELL
    path("sell/", views.sell, name="sell"),
    path("sell/valuation/", views.sell_valuation, name="sell_valuation"),
    path("sell/marketing/", views.sell_marketing, name="sell_marketing"),
    path("sell/concierge/", views.sell_concierge, name="sell_concierge"),

    # RENT
    path("rent/", views.rent, name="rent"),
    path("rent/marketing/", views.rent_marketing, name="rent_marketing"),

    # PROPERTY MANAGEMENT
    path("propman/", views.propman, name="propman"),

    # CONTACT
    path("contact/", views.contact, name="contact"),

    # portal
    path("portal/", views.login, name="login"),

    # ABOUT US
    path("company/aboutus/", views.company_aboutus, name="aboutus"),

    # JOIN US
    path("company/joinus/", views.company_joinus, name="joinus"),

    # CONTACT US
    path("company/contactus/", views.company_contactus, name="contactus"),

    # BLOG
    path("colcircle/blog/", views.colcircle_blog, name="blog"),

    # NEWSLETTER
    path("colcircle/newsletter/", views.colcircle_newsletter, name="newsletter"),

    # COL CIRCLE
    path("colcircle/colcircle/", views.colcircle_colcircle, name="colcircle"),

    # NEIGHBORHOODS
    path("explore/neighborhoods/", views.explore_neighborhoods, name="neighborhoods"),

    # NEW HOMES
    path("explore/newhomes/", views.explore_newhomes, name="newhomes"),

    # COMMERCIAL
    path("explore/commercial/", views.explore_commercial, name="commercial"),

    # HEALTHCHECK
    path("health/", views.health, name="health"),
]
