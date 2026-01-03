# pages/views.py
from datetime import timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone

from listings.models import Listing


def home(request):
    # Base filters (align with your listing list page)
    base = Listing.objects.filter(
        status="active",
        property_type__icontains="Residential"
    )

    new_listings = base.order_by("-created_at")[:3]

    recently_sold = Listing.objects.filter(status="sold").order_by("-updated_at")[:1]
    sold_one = recently_sold[0] if recently_sold else None

    last_30 = timezone.now() - timedelta(days=30)
    homes_sold_30_days = Listing.objects.filter(status="sold", updated_at__gte=last_30).count()

    context = {
        "new_listings": new_listings,
        "recently_sold": sold_one,
        "homes_sold_30_days": homes_sold_30_days,
        # CTA labels (optional)
        "cta_primary": "Book a Discovery Call",
        "cta_buyer": "Find My Lifestyle Match",
        "cta_seller": "Get Your Precision Equity Report",
        "cta_newsletter": "Join The Neighborhood Edit",
    }
    return render(request, "pages/home.html", context)


def contact(request):
    return render(request, "pages/contact.html")


# BUY pages
def buy_map(request):
    return render(request, "pages/buy/map.html")


def buy_neighborhoods(request):
    return render(request, "pages/buy/neighborhoods.html")


def buy_off_market(request):
    return render(request, "pages/buy/off_market.html")


# SELL pages
def sell_valuation(request):
    return render(request, "pages/sell/valuation.html")


def sell_marketing(request):
    return render(request, "pages/sell/marketing.html")


def sell_concierge(request):
    return render(request, "pages/sell/concierge.html")


# LIFESTYLE
def lifestyle(request):
    return render(request, "pages/lifestyle.html")


# PORTAL placeholders
def portal_login(request):
    return render(request, "pages/portal/login.html")


def portal_dashboard(request):
    return render(request, "pages/portal/dashboard.html")


def health(request):
    return JsonResponse({"status": "ok"})
