from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView

from .models import Listing
from .services.search import apply_listing_filters, get_listing_property_types


class ListingListView(ListView):
    model = Listing
    template_name = "listings/list.html"
    context_object_name = "listings"
    paginate_by = 42

    def get_queryset(self):
        active_property_types = get_listing_property_types(active_only=True, listing_category="sale")

        qs = Listing.objects.filter(
            status="active",
            listing_category="sale",
            property_type__in=active_property_types,
        )
        return apply_listing_filters(qs, self.request.GET).order_by("-id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY
        ctx["PROPERTY_TYPE_CHOICES"] = get_listing_property_types(active_only=True, listing_category="sale")

        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["query_string"] = params.urlencode()

        ctx["search_q"] = self.request.GET.get("q", "")
        ctx["search_price_min"] = self.request.GET.get("price_min", "")
        ctx["search_price_max"] = self.request.GET.get("price_max", "")
        ctx["search_beds_min"] = self.request.GET.get("beds_min", "")
        ctx["search_baths_min"] = self.request.GET.get("baths_min", "")
        ctx["search_property_type"] = self.request.GET.get("property_type", "")
        ctx["has_active_filters"] = any([
            ctx["search_q"],
            ctx["search_price_min"],
            ctx["search_price_max"],
            ctx["search_beds_min"],
            ctx["search_baths_min"],
            ctx["search_property_type"],
        ])

        return ctx


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY

        listing = self.object
        active_property_types = get_listing_property_types(active_only=True, listing_category="sale")

        ctx["is_favorite"] = (
            self.request.user.is_authenticated
            and self.request.user.favorites.filter(listing=listing).exists()
        )

        if listing.price:
            price_lo = listing.price * Decimal("0.75")
            price_hi = listing.price * Decimal("1.25")
            ctx["similar_listings"] = (
                Listing.objects.filter(
                    status="active",
                    listing_category="sale",
                    property_type__in=active_property_types,
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
    active_property_types = get_listing_property_types(active_only=True, listing_category="sale")

    qs = Listing.objects.filter(
        status="active",
        listing_category="sale",
        property_type__in=active_property_types,
        latitude__isnull=False,
        longitude__isnull=False,
    ).only(
        "id",
        "title",
        "price",
        "street_address",
        "city",
        "state",
        "zip_code",
        "latitude",
        "longitude",
        "main_image_url",
    )

    qs = apply_listing_filters(qs, request.GET).order_by("-id")[:3000]

    markers = []
    for listing in qs:
        try:
            lat = float(listing.latitude)
            lng = float(listing.longitude)
        except (TypeError, ValueError):
            continue

        markers.append(
            {
                "id": listing.id,
                "title": listing.title,
                "price": str(listing.price),
                "address": f"{listing.street_address}, {listing.city}, {listing.state} {listing.zip_code}",
                "lat": lat,
                "lng": lng,
                "image": listing.main_image_url,
                "url": f"/listings/{listing.id}/",
            }
        )

    return JsonResponse(markers, safe=False)

    ctx["has_active_filters"] = any([
    ctx["search_q"],
    ctx["search_price_min"],
    ctx["search_price_max"],
    ctx["search_beds_min"],
    ctx["search_baths_min"],
    ctx["search_property_type"],
])

