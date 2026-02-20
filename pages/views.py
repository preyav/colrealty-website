# pages/views.py
import os
from datetime import timedelta
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.views import LoginView
from listings.models import Listing
from django.urls import reverse


class ColRealtyLoginView(LoginView):
    template_name = 'pages/login.html'
    # Redirect to homepage or a specific dashboard after login
    next_page = 'index'

def home(request):
    qs = Listing.objects.all().order_by("-id")

    paginator = Paginator(qs, 12)  # 12 listings per page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "listings": page_obj,              # important: template loops over listings
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
    }
    return render(request, "pages/home.html", context)

# BUY pages
def contact(request):
    return render(request, "pages/contact.html")

RENT_TYPES = {"Residential Lease", "Commercial Lease"}
BUY_TYPES = {
    "Commercial Sale", "Condo", "Duplex", "Farm", "Land", "Multi-Family",
    "Residential", "Residential Income", "Single Family", "Townhome",
}


def _build_markers(qs):
    markers = []
    for l in qs:
        if l.latitude is None or l.longitude is None:
            continue

        markers.append({
            "id": l.id,
            "title": l.title,
            "price": str(l.price),
            "address": f"{l.street_address}, {l.city}, {l.state} {l.zip_code}",
            "lat": float(l.latitude),
            "lng": float(l.longitude),
            "image": l.main_image_url,
            "status": l.status,
            "property_type": l.property_type,
            "url": reverse("listings:listing_detail", kwargs={"pk": l.pk}),
        })
    return markers

# BUY pages
def buy(request):
    qs = Listing.objects.filter(status="active", property_type__in=BUY_TYPES).order_by("-id")
    listings = Listing.objects.exclude(latitude__isnull=True)[:100]

    # Prepare the list for the map
    marker_list = []
    for l in listings:
        marker_list.append({
            'lat': float(l.latitude),
            'lng': float(l.longitude),
            'title': l.title,
            'price': f"{l.price:,.0f}",
            'url': l.get_absolute_url(),
            'image': l.main_image_url if l.main_image_url else ""
        })

    context = {
        'markers': marker_list, # This name must match the json_script tag
        'GOOGLE_MAPS_API_KEY': os.environ.get('GOOGLE_MAPS_API_KEY'),
    }
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))


    markers = _build_markers(qs)
    print("BUY markers type:", type(markers), "len:", len(markers))

    return render(request, "listings/list.html", {
        "listings": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "markers": markers,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })

def buy_map(request):
    return render(request, "pages/buy/map.html")


def buy_neighborhoods(request):
    return render(request, "pages/buy/neighborhoods.html")


def buy_off_market(request):
    return render(request, "pages/buy/off_market.html")


# SELL pages
def sell(request):
    return render(request, "pages/sell.html")  

def sell_valuation(request):
    return render(request, "pages/sell/valuation.html")


def sell_marketing(request):
    return render(request, "pages/sell/marketing.html")


def sell_concierge(request):
    return render(request, "pages/sell/concierge.html")


# RENT

def rent(request):
    qs = Listing.objects.filter(status="active", property_type__in=RENT_TYPES).order_by("-id")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "pages/rent.html", {
        "listings": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "markers": _build_markers(qs),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })

def rent_marketing(request):
    return render(request, "pages/rent/marketing.html")

# PROPERTY MANAGEMENT
def propman(request):
    return render(request, "pages/propman.html")

# CONTACT
def contact(request):
    return render(request, "pages/contact.html")


# CUSTOM LOGIN placeholders
def login(request):
    return render(request, "pages/login.html")


def health(request):
    return JsonResponse({"status": "ok"})
