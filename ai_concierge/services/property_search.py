from listings.models import Listing
from listings.services.search import BUY_TYPES, PROPERTY_TYPE_CHOICES, apply_listing_filters


def get_listing_property_types() -> list[str]:
    return PROPERTY_TYPE_CHOICES


def serialize_listing_for_ai(listing: Listing) -> dict:
    return {
        "id": listing.id,
        "title": listing.title,
        "price": float(listing.price) if listing.price is not None else None,
        "beds": float(listing.beds) if listing.beds is not None else None,
        "baths": float(listing.baths) if listing.baths is not None else None,
        "sqft": listing.sqft,
        "city": listing.city,
        "address": listing.full_address,
        "image": listing.main_image_url,
        "url": listing.get_absolute_url(),
        "property_type": listing.property_type,
        "price_per_sqft": listing.price_per_sqft,
        "description": (listing.description or "")[:220],
    }


def search_buy_properties(filters: dict, limit: int = 6) -> list[dict]:
    queryset = Listing.objects.filter(
        status="active",
        property_type__in=BUY_TYPES,
    )

    queryset = apply_listing_filters(queryset, filters).order_by("-id")[:limit]
    return [serialize_listing_for_ai(listing) for listing in queryset]
