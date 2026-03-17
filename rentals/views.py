from decimal import Decimal

from django.conf import settings
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import Rental
from .services.search import apply_rental_filters, get_rental_property_types


def rental_list(request):
    qs = Rental.objects.filter(status="active")
    qs = apply_rental_filters(qs, request.GET).order_by("-id")

    paginator = Paginator(qs, 42)
    page_obj = paginator.get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    search_q = request.GET.get("q", "")
    search_price_min = request.GET.get("price_min", "")
    search_price_max = request.GET.get("price_max", "")
    search_beds_min = request.GET.get("beds_min", "")
    search_baths_min = request.GET.get("baths_min", "")
    search_property_type = request.GET.get("property_type", "")

    return render(request, "rentals/list.html", {
        "rentals": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": paginator.num_pages > 1,
        "query_string": params.urlencode(),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
        "PROPERTY_TYPE_CHOICES": get_rental_property_types(active_only=True),

        "search_q": search_q,
        "search_price_min": search_price_min,
        "search_price_max": search_price_max,
        "search_beds_min": search_beds_min,
        "search_baths_min": search_baths_min,
        "search_property_type": search_property_type,

        "has_active_filters": any([
            search_q,
            search_price_min,
            search_price_max,
            search_beds_min,
            search_baths_min,
            search_property_type,
        ]),
    })


def rental_detail(request, pk):
    listing = get_object_or_404(Rental, pk=pk, status="active")

    is_favorite = False

    if listing.price:
        price_lo = listing.price * Decimal("0.75")
        price_hi = listing.price * Decimal("1.25")
        similar_listings = (
            Rental.objects
            .filter(status="active", city=listing.city, price__gte=price_lo, price__lte=price_hi)
            .exclude(pk=listing.pk)
            .order_by("-id")[:8]
        )
    else:
        similar_listings = []

    return render(request, "rentals/detail.html", {
        "listing": listing,
        "is_favorite": is_favorite,
        "similar_listings": similar_listings,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


@require_GET
def rental_markers(request):
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
            "id": r.id,
            "title": r.title,
            "price": str(r.price),
            "address": f"{r.street_address}, {r.city}, {r.state} {r.zip_code}",
            "lat": lat,
            "lng": lng,
            "image": r.main_image_url or "",
            "url": reverse("rentals:detail", kwargs={"pk": r.pk}),
        })

    return JsonResponse(markers, safe=False)