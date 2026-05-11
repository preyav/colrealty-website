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
    price_min = params.get("price_min")
    price_max = params.get("price_max")
    beds_min = params.get("beds_min")
    beds_max = params.get("beds_max")
    baths_min = params.get("baths_min")
    baths_max = params.get("baths_max")
    property_type = params.get("property_type")
    status = params.get("status")

    sqft_min = params.get("sqft_min")
    sqft_max = params.get("sqft_max")
    lot_min = params.get("lot_min")
    lot_max = params.get("lot_max")
    year_min = params.get("year_min")
    year_max = params.get("year_max")
    stories_min = params.get("stories_min")
    stories_max = params.get("stories_max")
    parking_min = params.get("parking_min")
    hoa_max = params.get("hoa_max")

    keywords = params.get("keywords")

    # --- Keyword search ---
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

    # --- Price ---
    if price_min:
        qs = qs.filter(price__gte=Decimal(price_min))
    if price_max:
        qs = qs.filter(price__lte=Decimal(price_max))

    # --- Beds / Baths ---
    if beds_min:
        qs = qs.filter(beds__gte=beds_min)
    if beds_max:
        qs = qs.filter(beds__lte=beds_max)

    if baths_min:
        qs = qs.filter(baths__gte=baths_min)
    if baths_max:
        qs = qs.filter(baths__lte=baths_max)

    # --- Type / Status ---
    if property_type:
        qs = qs.filter(property_type=property_type)

    if status:
        qs = qs.filter(status=status)

    # --- Property facts ---
    if sqft_min:
        qs = qs.filter(sqft__gte=sqft_min)
    if sqft_max:
        qs = qs.filter(sqft__lte=sqft_max)

    if lot_min:
        qs = qs.filter(lot_size__gte=lot_min)
    if lot_max:
        qs = qs.filter(lot_size__lte=lot_max)

    if year_min:
        qs = qs.filter(year_built__gte=year_min)
    if year_max:
        qs = qs.filter(year_built__lte=year_max)

    if stories_min:
        qs = qs.filter(stories__gte=stories_min)
    if stories_max:
        qs = qs.filter(stories__lte=stories_max)

    if parking_min:
        qs = qs.filter(parking_total__gte=parking_min)

    if hoa_max:
        qs = qs.filter(hoa_fee__lte=hoa_max)

    # --- Amenities ---
    if params.get("has_pool"):
        qs = qs.filter(has_pool=True)

    if params.get("has_garage"):
        qs = qs.filter(has_garage=True)

    if params.get("is_waterfront"):
        qs = qs.filter(is_waterfront=True)

    if params.get("is_new_construction"):
        qs = qs.filter(is_new_construction=True)

    if params.get("has_fireplace"):
        qs = qs.filter(has_fireplace=True)

    if params.get("has_ac"):
        qs = qs.exclude(cooling="")

    # --- Keywords (deep search) ---
    if keywords:
        qs = qs.filter(
            Q(description__icontains=keywords) |
            Q(interior_features__icontains=keywords) |
            Q(exterior_features__icontains=keywords) |
            Q(community_features__icontains=keywords)
        )

    # --- Open house ---
    if params.get("open_house"):
        qs = qs.filter(open_house_date__isnull=False)

    return qs.distinct()