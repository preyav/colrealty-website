import re
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from listings.models import Listing


def to_decimal(val: str):
    try:
        cleaned = (val or "").replace(",", "").replace("$", "").strip()
        return Decimal(cleaned) if cleaned else None
    except (InvalidOperation, AttributeError):
        return None


def get_listing_property_types(active_only: bool = True, listing_category: str = "sale") -> list[str]:
    qs = Listing.objects.filter(listing_category=listing_category)

    if active_only:
        qs = qs.filter(status="active")

    property_types = (
        qs.exclude(property_type__isnull=True)
        .exclude(property_type__exact="")
        .values_list("property_type", flat=True)
        .distinct()
    )
    return sorted({p.strip() for p in property_types if p}, key=str.lower)


def get_listing_cities(active_only: bool = True, listing_category: str = "sale") -> list[str]:
    qs = Listing.objects.filter(listing_category=listing_category)

    if active_only:
        qs = qs.filter(status="active")

    cities = (
        qs.exclude(city__isnull=True)
        .exclude(city__exact="")
        .values_list("city", flat=True)
        .distinct()
    )
    return sorted({c.strip() for c in cities if c}, key=str.lower)


def apply_listing_filters(qs, params: dict):
    q = (params.get("q") or "").strip()
    price_min = (params.get("price_min") or "").strip()
    price_max = (params.get("price_max") or "").strip()
    beds_min = (params.get("beds_min") or "").strip()
    baths_min = (params.get("baths_min") or "").strip()
    property_type = (params.get("property_type") or "").strip()

    if q:
        q_zip = re.sub(r"\D", "", q)
        normalized_q = q.strip().lower()

        known_cities = {city.lower(): city for city in get_listing_cities(active_only=True, listing_category="sale")}

        if normalized_q in known_cities:
            qs = qs.filter(city__iexact=known_cities[normalized_q])
        elif q_zip and len(q_zip) == 5:
            qs = qs.filter(zip_code__icontains=q_zip)
        else:
            qs = qs.filter(
                Q(city__icontains=q)
                | Q(zip_code__icontains=q_zip if q_zip else q)
                | Q(street_address__icontains=q)
                | Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(subdivision__icontains=q)
                | Q(school_district__icontains=q)
                | Q(elementary_school__icontains=q)
                | Q(middle_school__icontains=q)
                | Q(high_school__icontains=q)
                | Q(listing_agent_name__icontains=q)
                | Q(listing_agent_email__icontains=q)
                | Q(listing_office_name__icontains=q)
            )

    min_v = to_decimal(price_min)
    max_v = to_decimal(price_max)

    if min_v is not None:
        qs = qs.filter(price__gte=min_v)

    if max_v is not None:
        qs = qs.filter(price__lte=max_v)

    beds_v = to_decimal(beds_min)
    if beds_v is not None:
        qs = qs.filter(beds__gte=beds_v)

    baths_v = to_decimal(baths_min)
    if baths_v is not None:
        qs = qs.filter(baths__gte=baths_v)

    allowed_property_types = set(get_listing_property_types(active_only=True, listing_category="sale"))
    if property_type and property_type in allowed_property_types:
        qs = qs.filter(property_type=property_type)

    return qs