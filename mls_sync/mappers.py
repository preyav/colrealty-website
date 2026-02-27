# mls_sync/mappers.py
from decimal import Decimal
from typing import Dict, Any, Optional
from listings.models import Listing


def truncate(value: Optional[str], max_len: int) -> str:
    if not value:
        return ""
    value = str(value)
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def join_list(items) -> str:
    """Convert a list or comma-string to a clean comma-separated string."""
    if not items:
        return ""
    if isinstance(items, list):
        return ", ".join(str(i).strip() for i in items if i)
    return str(items)


def map_property_to_listing_data(record: Dict[str, Any]) -> Dict[str, Any]:
    price = record.get("ListPrice")
    beds = record.get("BedroomsTotal")
    baths = record.get("BathroomsTotalDecimal")
    lat = record.get("Latitude")
    lon = record.get("Longitude")

    street_number = record.get("StreetNumber") or ""
    street_name = record.get("StreetName") or ""
    street_address = f"{street_number} {street_name}".strip()

    raw_title = record.get("PropertySubType") or street_address or "MLS Listing"
    title = truncate(raw_title, 512)

    description = record.get("PublicRemarks") or ""

    # ── Media: extract all photo URLs ────────────────────────────────────
    media_items = record.get("Media") or []
    main_image_url = ""
    image_urls = []

    for item in media_items:
        url = (
            item.get("MediaURL")
            or item.get("MediaURLLarge")
            or item.get("MediaURLMedium")
            or ""
        )
        if url:
            image_urls.append(url)

    if image_urls:
        main_image_url = image_urls[0]

    modification_ts = record.get("ModificationTimestamp")

    # ── Status ────────────────────────────────────────────────────────────
    raw_status = (record.get("StandardStatus") or "Active").lower()
    status = "active" if "active" in raw_status else ("pending" if "pending" in raw_status else ("sold" if "sold" in raw_status or "closed" in raw_status else "active"))

    return {
        # Core
        "mls_id": str(record.get("ListingKey") or ""),
        "title": title,
        "description": description,
        "status": status,
        "mls_modification_timestamp": modification_ts,

        # Address
        "street_address": street_address,
        "city": record.get("City") or "",
        "state": record.get("StateOrProvince") or "",
        "zip_code": record.get("PostalCode") or "",
        "county": record.get("CountyOrParish") or "",
        "subdivision": truncate(record.get("SubdivisionName") or "", 255),

        # Pricing
        "price": Decimal(str(price or 0)),
        "original_list_price": Decimal(str(record.get("OriginalListPrice") or 0)) if record.get("OriginalListPrice") else None,
        "tax_amount": record.get("TaxAnnualAmount") or None,
        "tax_year": record.get("TaxYear") or None,
        "hoa_fee": record.get("AssociationFee") or None,
        "hoa_frequency": record.get("AssociationFeeFrequency") or "",
        "buyer_agent_compensation": record.get("BuyerAgencyCompensation") or "",

        # Specs
        "beds": beds,
        "baths": baths,
        "baths_full": record.get("BathroomsFull") or None,
        "baths_half": record.get("BathroomsHalf") or None,
        "sqft": record.get("BuildingAreaTotal") or None,
        "lot_size": record.get("LotSizeAcres") or None,
        "lot_size_sqft": record.get("LotSizeSquareFeet") or None,

        # Building
        "property_type": record.get("PropertyType") or "",
        "year_built": record.get("YearBuilt") or None,
        "stories": record.get("StoriesTotal") or None,
        "garage_spaces": record.get("GarageSpaces") or None,
        "parking_total": record.get("ParkingTotal") or None,

        # Features
        "interior_features": join_list(record.get("InteriorFeatures")),
        "exterior_features": join_list(record.get("ExteriorFeatures")),
        "community_features": join_list(record.get("CommunityFeatures")),
        "parking_features": join_list(record.get("ParkingFeatures")),
        "appliances": join_list(record.get("Appliances")),
        "flooring": join_list(record.get("Flooring")),
        "laundry_features": join_list(record.get("LaundryFeatures")),
        "window_features": join_list(record.get("WindowFeatures")),
        "patio_porch_features": join_list(record.get("PatioAndPorchFeatures")),

        # Booleans
        "has_fireplace": bool(record.get("FireplaceYN")),
        "has_pool": bool(record.get("PoolPrivateYN") or record.get("PoolFeatures")),
        "has_garage": bool(record.get("GarageYN")),
        "is_waterfront": bool(record.get("WaterfrontYN")),
        "is_new_construction": bool(record.get("NewConstructionYN")),

        # Construction
        "construction_materials": join_list(record.get("ConstructionMaterials")),
        "foundation": join_list(record.get("FoundationDetails")),
        "roof": join_list(record.get("Roof")),
        "fencing": join_list(record.get("Fencing")),
        "direction_faces": record.get("DirectionFaces") or "",

        # Utilities
        "heating": join_list(record.get("Heating")),
        "cooling": join_list(record.get("Cooling")),
        "sewer": join_list(record.get("Sewer")),
        "water_source": join_list(record.get("WaterSource")),

        # Schools
        "school_district": record.get("ElementarySchoolDistrict") or record.get("SchoolDistrict") or "",
        "elementary_school": record.get("ElementarySchool") or "",
        "middle_school": record.get("MiddleOrJuniorSchool") or "",
        "high_school": record.get("HighSchool") or "",

        # Location
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,
        "directions": record.get("Directions") or "",

        # Media
        "main_image_url": main_image_url,
        "image_urls": image_urls,
        "virtual_tour_url": record.get("VirtualTourURLUnbranded") or record.get("VirtualTourURLBranded") or "",

        # Metadata
        "days_on_market": record.get("DaysOnMarket") or None,
        "is_featured": bool(price and price > 750000),
    }
