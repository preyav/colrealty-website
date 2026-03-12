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

PROPERTY_TYPE_CHOICES = sorted(BUY_TYPES)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def to_decimal(val: str):
    try:
        cleaned = (val or "").replace(",", "").replace("$", "").strip()
        return Decimal(cleaned) if cleaned else None
    except (InvalidOperation, AttributeError):
        return None


def apply_listing_filters(qs, params: dict):
    """
    Apply all search/filter params to a Listing queryset.
    Centralised here so ListingListView and listing_markers stay in sync.
    """
    q = (params.get("q") or "").strip()
    price_min = (params.get("price_min") or "").strip()
    price_max = (params.get("price_max") or "").strip()
    beds_min = (params.get("beds_min") or "").strip()
    baths_min = (params.get("baths_min") or "").strip()
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

    # ── Price range ────────────────────────────────────────────────────────
    min_v = to_decimal(price_min)
    max_v = to_decimal(price_max)
    if min_v is not None:
        qs = qs.filter(price__gte=min_v)
    if max_v is not None:
        qs = qs.filter(price__lte=max_v)

    # ── Beds / Baths (minimum) ─────────────────────────────────────────────
    beds_v = to_decimal(beds_min)
    if beds_v is not None:
        qs = qs.filter(beds__gte=beds_v)

    baths_v = to_decimal(baths_min)
    if baths_v is not None:
        qs = qs.filter(baths__gte=baths_v)

    # ── Property type ──────────────────────────────────────────────────────
    if property_type and property_type in BUY_TYPES:
        qs = qs.filter(property_type=property_type)

    return qs


# ─────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────

class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 42

    def get_queryset(self):
        qs = Listing.objects.filter(
            status="active", property_type__in=BUY_TYPES)
        return apply_listing_filters(qs, self.request.GET).order_by("-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY
        ctx["PROPERTY_TYPE_CHOICES"] = PROPERTY_TYPE_CHOICES

        # ── Preserve query string for pagination links ──────────────────────
        # e.g. ?q=Austin&price_max=500000&page=2  →  page link keeps filters
        params = self.request.GET.copy()
        params.pop("page", None)
        # used in template pagination
        ctx["query_string"] = params.urlencode()

        # ── Repopulate form fields after submit ────────────────────────────
        ctx["search_q"] = self.request.GET.get("q", "")
        ctx["search_price_min"] = self.request.GET.get("price_min", "")
        ctx["search_price_max"] = self.request.GET.get("price_max", "")
        ctx["search_beds_min"] = self.request.GET.get("beds_min", "")
        ctx["search_baths_min"] = self.request.GET.get("baths_min", "")
        ctx["search_property_type"] = self.request.GET.get("property_type", "")

        return ctx


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY

        listing = self.object

        # ── Is favorite ────────────────────────────────────────────────────
        ctx["is_favorite"] = (
            self.request.user.is_authenticated
            and self.request.user.favorites.filter(listing=listing).exists()
        )

        # ── Similar listings: same city, similar price, exclude self ───────
        if listing.price:
            price_lo = listing.price * Decimal("0.75")
            price_hi = listing.price * Decimal("1.25")
            ctx["similar_listings"] = (
                Listing.objects
                .filter(
                    status="active",
                    property_type__in=BUY_TYPES,
                    city=listing.city,
                    price__gte=price_lo,
                    price__lte=price_hi,
                )
                .exclude(pk=listing.pk)
                .order_by("-id")[:8]
            )
        else:
            ctx["similar_listings"] = []

        return ctx


@require_GET
def listing_markers(request):
    """Return GeoJSON-style marker data for the map — respects all active filters."""
    qs = Listing.objects.filter(
        status="active",
        property_type__in=BUY_TYPES,
        latitude__isnull=False,
        longitude__isnull=False,
    ).only(
        "id", "title", "price", "street_address", "city", "state", "zip_code",
        "latitude", "longitude", "main_image_url",
    )

    qs = apply_listing_filters(qs, request.GET).order_by("-id")[:3000]

    markers = []
    for listing in qs:
        try:
            lat = float(listing.latitude)
            lng = float(listing.longitude)
        except (TypeError, ValueError):
            continue

        markers.append({
            "id":      listing.id,
            "title":   listing.title,
            "price":   str(listing.price),
            "address": f"{listing.street_address}, {listing.city}, {listing.state} {listing.zip_code}",
            "lat":     lat,
            "lng":     lng,
            "image":   listing.main_image_url,
            "url":     f"/listings/{listing.id}/",
        })

    return JsonResponse(markers, safe=False)





