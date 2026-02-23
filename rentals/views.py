from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Rental

RENT_TYPES = {"Residential Lease", "Commercial Lease"}

@require_GET
def rental_markers(request):

    qs = Rental.objects.filter(
        status="active",
        property_type__in=RENT_TYPES,
        latitude__isnull=False,
        longitude__isnull=False
    )

    markers = [{
        "id": r.id,
        "title": r.title,
        "price": str(r.rent),
        "address": r.full_address(),
        "lat": float(r.latitude),
        "lng": float(r.longitude),
        "image": r.main_image_url,
        "url": f"/rentals/{r.id}/",
    } for r in qs[:3000]]  # safety cap

    return JsonResponse(markers, safe=False)

def _build_markers(qs):

    markers = []

    for r in qs:
        if not r.latitude or not r.longitude:
            continue

        markers.append({
            "id": r.id,
            "title": r.title,
            "price": str(r.rent),
            "address": r.full_address(),
            "lat": float(r.latitude),
            "lng": float(r.longitude),
            "image": r.main_image_url,
            "url": reverse("rentals:detail", kwargs={"pk": r.pk}),
        })

    return markers

def rental_list(request):
    qs = Rental.objects.filter(status="active", property_type__in=RENT_TYPES).order_by("-id")

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "rentals/list.html", {
        "rentals": page_obj,                 # template loops over this
        "page_obj": page_obj,                # pagination controls
        "paginator": paginator,              # page count
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })

def rental_detail(request, pk):
    rental = get_object_or_404(Rental, pk=pk)
    return render(request, "rentals/detail.html", {
        "rental": rental,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })

