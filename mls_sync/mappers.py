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


def safe_decimal(value, max_digits=10):
    """Convert to Decimal, return None if value is too large or invalid."""
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        limit = Decimal(10 ** (max_digits - 2))
        if abs(d) >= limit:
            return None
        return d
    except Exception:
        return None


def safe_int(value, max_val=2147483647):
    """Convert to int, return None if value is too large or invalid."""
    if value is None:
        return None
    try:
        i = int(float(str(value)))
        if abs(i) > max_val:
            return None
        return i
    except Exception:
        return None



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
        "original_list_price": safe_decimal(record.get("OriginalListPrice"), 12),
        "tax_amount": safe_decimal(record.get("TaxAnnualAmount")),
        "tax_year": safe_int(record.get("TaxYear")),
        "hoa_fee": safe_decimal(record.get("AssociationFee")),
        "hoa_frequency": record.get("AssociationFeeFrequency") or "",
        "buyer_agent_compensation": record.get("BuyerAgencyCompensation") or "",

        # Specs
        "beds": beds,
        "baths": baths,
        "baths_full": safe_int(record.get("BathroomsFull")),
        "baths_half": safe_int(record.get("BathroomsHalf")),
        "sqft": safe_int(record.get("BuildingAreaTotal")),
        "lot_size": record.get("LotSizeAcres") or None,
        "lot_size_sqft": safe_int(record.get("LotSizeSquareFeet")),

        # Building
        "property_type": record.get("PropertyType") or "",
        "year_built": safe_int(record.get("YearBuilt")),
        "stories": safe_int(record.get("StoriesTotal")),
        "garage_spaces": safe_int(record.get("GarageSpaces")),
        "parking_total": safe_int(record.get("ParkingTotal")),

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

        # Listing Agent
        "listing_agent_name":  record.get("ListAgentFullName") or record.get("ListAgentFirstName", "") + " " + record.get("ListAgentLastName", "") or "",
        "listing_agent_email": record.get("ListAgentEmail") or "",
        "listing_agent_phone": record.get("ListAgentDirectPhone") or record.get("ListAgentOfficePhone") or "",
        "listing_office_name": record.get("ListOfficeName") or "",

        # Metadata
        "days_on_market": safe_int(record.get("DaysOnMarket")),
        "is_featured": bool(price and price > 750000),
    }
