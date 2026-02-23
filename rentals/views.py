from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Rental

@require_GET
def rental_markers(request):

    qs = Rental.objects.filter(
        status="active",
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
    qs = Rental.objects.filter(status="active").order_by("-id")

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

def force_public_mlsgrid_s3(url: str) -> str:
    if not url:
        return ""
    if "s3.amazonaws.com/mlsgrid" in url or "mlsgrid.s3.amazonaws.com" in url:
        return url
    if "/images/" in url:
        return "https://s3.amazonaws.com/mlsgrid" + url[url.find("/images/"):]
    return url
    Rental.main_image_url = force_public_mlsgrid_s3(raw_photo_url)