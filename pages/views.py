# pages/views.py
import os
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse

from listings.models import Listing
from rentals.models import Rental


BUY_TYPES = {
    "Commercial Sale", "Condo", "Duplex", "Farm", "Land", "Multi-Family",
    "Residential", "Residential Income", "Single Family", "Townhome",
}


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

class ColRealtyLoginView(LoginView):
    template_name = "pages/login.html"
    next_page     = "index"


def login(request):
    return render(request, "pages/login.html")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _build_listing_markers(qs):
    markers = []
    for l in qs:
        if l.latitude is None or l.longitude is None:
            continue
        markers.append({
            "id":            l.id,
            "title":         l.title,
            "price":         str(l.price),
            "address":       f"{l.street_address}, {l.city}, {l.state} {l.zip_code}",
            "lat":           float(l.latitude),
            "lng":           float(l.longitude),
            "image":         l.main_image_url,
            "status":        l.status,
            "property_type": l.property_type,
            "url":           reverse("listings:listing_detail", kwargs={"pk": l.pk}),
        })
    return markers


def _build_rental_markers(qs):
    markers = []
    for r in qs:
        if r.latitude is None or r.longitude is None:
            continue
        markers.append({
            "id":      r.id,
            "title":   r.title,
            "price":   str(r.rent),         # Rental uses `rent`, not `price`
            "address": r.full_address(),
            "lat":     float(r.latitude),
            "lng":     float(r.longitude),
            "image":   r.main_image_url or "",
            "url":     reverse("rentals:detail", kwargs={"pk": r.pk}),
        })
    return markers


# ─────────────────────────────────────────────
# Core pages
# ─────────────────────────────────────────────

def home(request):
    qs = Listing.objects.filter(status="active").order_by("-id")
    paginator  = Paginator(qs, 12)
    page_obj   = paginator.get_page(request.GET.get("page"))
    return render(request, "pages/home.html", {
        "listings":    page_obj,
        "page_obj":    page_obj,
        "paginator":   paginator,
        "is_paginated": page_obj.has_other_pages(),
    })


def contact(request):
    return render(request, "pages/contact.html")


def health(request):
    return JsonResponse({"status": "ok"})


# ─────────────────────────────────────────────
# Buy pages
# ─────────────────────────────────────────────

def buy(request):
    qs         = Listing.objects.filter(status="active", property_type__in=BUY_TYPES).order_by("-id")
    paginator  = Paginator(qs, 12)
    page_obj   = paginator.get_page(request.GET.get("page"))
    return render(request, "listings/list.html", {
        "listings":    page_obj,
        "page_obj":    page_obj,
        "paginator":   paginator,
        "is_paginated": page_obj.has_other_pages(),
        "markers":     _build_listing_markers(qs),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


def buy_map(request):
    return render(request, "pages/buy/map.html")


def buy_neighborhoods(request):
    return render(request, "pages/buy/neighborhoods.html")


def buy_off_market(request):
    return render(request, "pages/buy/off_market.html")


# ─────────────────────────────────────────────
# Sell pages
# ─────────────────────────────────────────────

def sell(request):
    return render(request, "pages/sell.html")


def sell_valuation(request):
    return render(request, "pages/sell/valuation.html")


def sell_marketing(request):
    return render(request, "pages/sell/marketing.html")


def sell_concierge(request):
    return render(request, "pages/sell/concierge.html")


# ─────────────────────────────────────────────
# Rent pages  ← FIXED: now uses Rental model
# ─────────────────────────────────────────────

def rent(request):
    qs        = Rental.objects.filter(status="active").order_by("-id")
    paginator = Paginator(qs, 12)
    page_obj  = paginator.get_page(request.GET.get("page"))
    return render(request, "rentals/list.html", {
        "rentals":     page_obj,
        "page_obj":    page_obj,
        "paginator":   paginator,
        "is_paginated": page_obj.has_other_pages(),
        "markers":     _build_rental_markers(qs),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


def rent_marketing(request):
    return render(request, "pages/rent/marketing.html")


# ─────────────────────────────────────────────
# Property management
# ─────────────────────────────────────────────

def propman(request):
    return render(request, "pages/propman.html")


# ─────────────────────────────────────────────
# Company pages
# ─────────────────────────────────────────────

def company_aboutus(request):
    return render(request, "pages/company/aboutus.html")


def company_joinus(request):
    return render(request, "pages/company/joinus.html")


def company_contactus(request):
    return render(request, "pages/company/contactus.html")


# ─────────────────────────────────────────────
# ColCircle pages
# ─────────────────────────────────────────────

def colcircle(request):
    return render(request, "pages/colcircle.html")


def colcircle_blog(request):
    return render(request, "pages/colcircle/blog.html")


def colcircle_newsletter(request):
    return render(request, "pages/colcircle/newsletter.html")


def colcircle_colcircle(request):
    return render(request, "pages/colcircle/colcircle.html")


# ─────────────────────────────────────────────
# Explore pages
# ─────────────────────────────────────────────

def explore_neighborhoods(request):
    return render(request, "pages/explore/neighborhoods.html")


def explore_newhomes(request):
    return render(request, "pages/explore/newhomes.html")


def explore_commercial(request):
    return render(request, "pages/explore/commercial.html")
