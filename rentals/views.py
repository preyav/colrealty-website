import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import Rental


RENTAL_PROPERTY_TYPE_CHOICES = [
    "Commercial Lease",
    "Condo",
    "Multi-Family",
    "Residential",
    "Residential Lease",
    "Single Family",
    "Townhome",
]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _to_decimal(val: str):
    try:
        cleaned = (val or "").replace(",", "").replace("$", "").strip()
        return Decimal(cleaned) if cleaned else None
    except (InvalidOperation, AttributeError):
        return None


def apply_rental_filters(qs, params: dict):
    """
    Apply all search/filter params to a Rental queryset.
    Mirrors apply_listing_filters() in listings/views.py for consistency.
    """
    q             = (params.get("q")             or "").strip()
    rent_min      = (params.get("rent_min")      or "").strip()
    rent_max      = (params.get("rent_max")      or "").strip()
    beds_min      = (params.get("beds_min")      or "").strip()
    baths_min     = (params.get("baths_min")     or "").strip()
    property_type = (params.get("property_type") or "").strip()

    # ── Keyword / location search ──────────────────────────────────────────
    if q:
        q_zip = re.sub(r"\D", "", q)
        qs = qs.filter(
            Q(city__icontains=q)
            | Q(zip_code__icontains=q_zip if q_zip else q)
            | Q(street_address__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
        )

    # ── Rent range ─────────────────────────────────────────────────────────
    min_v = _to_decimal(rent_min)
    max_v = _to_decimal(rent_max)
    if min_v is not None:
        qs = qs.filter(rent__gte=min_v)
    if max_v is not None:
        qs = qs.filter(rent__lte=max_v)

    # ── Beds / Baths (minimum) ─────────────────────────────────────────────
    beds_v = _to_decimal(beds_min)
    if beds_v is not None:
        qs = qs.filter(beds__gte=beds_v)

    baths_v = _to_decimal(baths_min)
    if baths_v is not None:
        qs = qs.filter(baths__gte=baths_v)

    # ── Property type ──────────────────────────────────────────────────────
    if property_type and property_type in RENTAL_PROPERTY_TYPE_CHOICES:
        qs = qs.filter(property_type=property_type)

    return qs


# ─────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────

def rental_list(request):
    qs = Rental.objects.filter(status="active").order_by("-id")
    qs = apply_rental_filters(qs, request.GET)

    paginator = Paginator(qs, 12)
    page_obj  = paginator.get_page(request.GET.get("page"))

    # Preserve filters across pagination
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "rentals/list.html", {
        "rentals":              page_obj,
        "page_obj":             page_obj,
        "paginator":            paginator,
        "is_paginated":         paginator.num_pages > 1,
        "query_string":         params.urlencode(),
        "GOOGLE_MAPS_API_KEY":  settings.GOOGLE_MAPS_API_KEY,
        "PROPERTY_TYPE_CHOICES": RENTAL_PROPERTY_TYPE_CHOICES,

        # Repopulate form fields
        "search_q":             request.GET.get("q", ""),
        "search_rent_min":      request.GET.get("rent_min", ""),
        "search_rent_max":      request.GET.get("rent_max", ""),
        "search_beds_min":      request.GET.get("beds_min", ""),
        "search_baths_min":     request.GET.get("baths_min", ""),
        "search_property_type": request.GET.get("property_type", ""),
    })


def rental_detail(request, pk):
    rental = get_object_or_404(Rental, pk=pk, status="active")
    return render(request, "rentals/detail.html", {
        "rental":              rental,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


@require_GET
def rental_markers(request):
    """Return marker data for the rentals map — respects all active filters."""
    qs = Rental.objects.filter(
        status="active",
        latitude__isnull=False,
        longitude__isnull=False,
    )
    qs = apply_rental_filters(qs, request.GET).order_by("-id")[:3000]

    markers = []
    for r in qs:
        try:
            lat = float(r.latitude)
            lng = float(r.longitude)
        except (TypeError, ValueError):
            continue

        markers.append({
            "id":      r.id,
            "title":   r.title,
            "price":   str(r.rent),         # Rental model uses `rent`, not `price`
            "address": r.full_address(),
            "lat":     lat,
            "lng":     lng,
            "image":   r.main_image_url or "",
            "url":     reverse("rentals:detail", kwargs={"pk": r.pk}),
        })

    return JsonResponse(markers, safe=False)
