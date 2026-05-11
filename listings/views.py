from decimal import Decimal
from django.db.models import Q
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
        qs = Listing.objects.filter(
            status="active",
            listing_category="sale",
        ).exclude(
            property_type__in=["Residential Lease", "Commercial Lease"]
        )
        return apply_listing_filters(qs, self.request.GET).order_by("-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY
        context["PROPERTY_TYPE_CHOICES"] = get_listing_property_types(active_only=True, listing_category="sale")

        params = self.request.GET.copy()
        params.pop("page", None)
        context["query_string"] = params.urlencode()

        context["search_q"] = self.request.GET.get("q", "")
        context["search_price_min"] = self.request.GET.get("price_min", "")
        context["search_price_max"] = self.request.GET.get("price_max", "")
        context["search_beds_min"] = self.request.GET.get("beds_min", "")
        context["search_baths_min"] = self.request.GET.get("baths_min", "")
        context["search_property_type"] = self.request.GET.get("property_type", "")
        context["search_beds_max"] = params.get("beds_max", "")
        context["search_baths_max"] = params.get("baths_max", "")
        context["search_status"] = params.get("status", "")
        context["search_sqft_min"] = params.get("sqft_min", "")
        context["search_sqft_max"] = params.get("sqft_max", "")
        context["search_lot_min"] = params.get("lot_min", "")
        context["search_lot_max"] = params.get("lot_max", "")
        context["search_year_min"] = params.get("year_min", "")
        context["search_year_max"] = params.get("year_max", "")
        context["search_stories_min"] = params.get("stories_min", "")
        context["search_stories_max"] = params.get("stories_max", "")
        context["search_parking_min"] = params.get("parking_min", "")
        context["search_hoa_max"] = params.get("hoa_max", "")
        context["search_keywords"] = params.get("keywords", "")
        context["search_has_pool"] = bool(params.get("has_pool"))
        context["search_has_garage"] = bool(params.get("has_garage"))
        context["search_is_waterfront"] = bool(params.get("is_waterfront"))
        context["search_is_new_construction"] = bool(params.get("is_new_construction"))
        context["search_has_fireplace"] = bool(params.get("has_fireplace"))
        context["search_has_ac"] = bool(params.get("has_ac"))
        context["search_open_house"] = bool(params.get("open_house"))
        context["has_active_filters"] = any([
            context["search_q"],
            context["search_price_min"],
            context["search_price_max"],
            context["search_beds_min"],
            context["search_baths_min"],
            context["search_property_type"],
            context["search_beds_max"],
            context["search_baths_max"],
            context["search_status"],
            context["search_sqft_min"],
            context["search_sqft_max"],
            context["search_lot_min"],
            context["search_lot_max"],
            context["search_year_min"],
            context["search_year_max"],
            context["search_stories_min"],
            context["search_stories_max"],
            context["search_parking_min"],
            context["search_hoa_max"],
            context["search_keywords"],
            context["search_has_pool"],
            context["search_has_garage"],
            context["search_is_waterfront"],
            context["search_is_new_construction"],
            context["search_has_fireplace"],
            context["search_has_ac"],
            context["search_open_house"]
        ])

        return context


class ListingDetailView(DetailView):
    model = Listing
    template_name = "listings/detail.html"
    context_object_name = "listing"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["GOOGLE_MAPS_API_KEY"] = settings.GOOGLE_MAPS_API_KEY

        listing = self.object

        context["is_favorite"] = (
            self.request.user.is_authenticated
            and self.request.user.favorites.filter(listing=listing).exists()
        )

        if listing.price:
            price_lo = listing.price * Decimal("0.75")
            price_hi = listing.price * Decimal("1.25")
            context["similar_listings"] = (
                Listing.objects.filter(
                    status="active",
                    city=listing.city,
                    price__gte=price_lo,
                    price__lte=price_hi,
                )
                .exclude(property_type__in=["Residential Lease", "Commercial Lease"])
                .exclude(pk=listing.pk)
                .order_by("-id")[:8]
            )
        else:
            context["similar_listings"] = []

        return context


@require_GET
def listing_markers(request):
    qs = Listing.objects.filter(
        status="active",
        latitude__isnull=False,
        longitude__isnull=False,
    ).exclude(
        property_type__in=["Residential Lease", "Commercial Lease"]
    ).only(
        "id", "title", "price", "street_address", "city", "state",
        "zip_code", "latitude", "longitude", "main_image_url",
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
            "id": listing.id,
            "title": listing.title,
            "price": str(listing.price),
            "address": f"{listing.street_address}, {listing.city}, {listing.state} {listing.zip_code}",
            "lat": lat,
            "lng": lng,
            "image": listing.main_image_url,
            "url": f"/listings/{listing.id}/",
        })

    return JsonResponse(markers, safe=False)


