import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import ListView, DetailView

from .models import Listing


BUY_TYPES = {
    "Commercial Sale", "Condo", "Duplex", "Farm", "Land", "Multi-Family",
    "Residential", "Residential Income", "Single Family", "Single Family Residence", "Townhome",
}


def to_decimal(val: str):
    try:
        cleaned = (val or "").replace(",", "").replace("$", "").strip()
        return Decimal(cleaned) if cleaned else None
    except (InvalidOperation, AttributeError):
        return None


class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 12

    def get_queryset(self):
        qs = Listing.objects.filter(status="active", property_type__in=BUY_TYPES)

        q = (self.request.GET.get("q") or "").strip()
        price_min = (self.request.GET.get("price_min") or "").strip()
        price_max = (self.request.GET.get("price_max") or "").strip()

        if q:
            q_zip = re.sub(r"\D", "", q)
            qs = qs.filter(
                Q(city__icontains=q)
                | Q(zip_code__icontains=q_zip if q_zip else q)
                | Q(street_address__icontains=q)
                | Q(title__icontains=q)
                | Q(description__icontains=q)
            )

        min_v = to_decimal(price_min)
        max_v = to_decimal(price_max)

        if min_v is not None:
            qs = qs.filter(price__gte=min_v)
        if max_v is not None:
            qs = qs.filter(price__lte=max_v)

        return qs.order_by("-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY
        return ctx
    
    def force_public_mlsgrid_s3(url: str) -> str:
        if not url:
            return ""
        if "s3.amazonaws.com/mlsgrid" in url or "mlsgrid.s3.amazonaws.com" in url:
            return url
        if "/images/" in url:
            return "https://s3.amazonaws.com/mlsgrid" + url[url.find("/images/"):]
        return url
        listing.main_image_url = force_public_mlsgrid_s3(raw_photo_url)


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY
        return ctx

@require_GET
def listing_markers(request):
    qs = Listing.objects.filter(
        status="active",
        property_type__in=BUY_TYPES,
        latitude__isnull=False,
        longitude__isnull=False,
    ).only(
        "id", "title", "description", "price", "street_address", "city", "state", "zip_code",
        "latitude", "longitude", "main_image_url"
    )

    q = (request.GET.get("q") or "").strip()
    price_min = (request.GET.get("price_min") or "").strip()
    price_max = (request.GET.get("price_max") or "").strip()

    if q:
        q_zip = re.sub(r"\D", "", q)
        qs = qs.filter(
            Q(city__icontains=q)
            | Q(zip_code__icontains=q_zip if q_zip else q)
            | Q(street_address__icontains=q)
            | Q(title__icontains=q)
            | Q(description__icontains=q)
        )

    min_v = to_decimal(price_min)
    max_v = to_decimal(price_max)

    if min_v is not None:
        qs = qs.filter(price__gte=min_v)
    if max_v is not None:
        qs = qs.filter(price__lte=max_v)

    qs = qs.order_by("-id")[:3000]

    markers = []

    for l in qs:
        try:
            lat = float(l.latitude)
            lng = float(l.longitude)
        except (TypeError, ValueError):
            continue  # skip bad coordinates

        markers.append({
            "id": l.id,
            "title": l.title,
            "price": str(l.price),
            "address": f"{l.street_address}, {l.city}, {l.state} {l.zip_code}",
            "lat": lat,
            "lng": lng,
            "image": l.main_image_url,
            "url": f"/listings/{l.id}/",
        })

    return JsonResponse(markers, safe=False)
