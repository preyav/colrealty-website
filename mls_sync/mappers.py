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
    # leave room for ellipsis
    return value[: max_len - 3] + "..."


def map_property_to_listing_data(record: Dict[str, Any]) -> Dict[str, Any]:
    price = record.get("ListPrice")
    beds = record.get("BedroomsTotal")
    baths = record.get("BathroomsTotalDecimal")
    lat = record.get("Latitude")
    lon = record.get("Longitude")

    street_number = record.get("StreetNumber") or ""
    street_name = record.get("StreetName") or ""
    street_address = f"{street_number} {street_name}".strip()

    # Short, UI-friendly title
    raw_title = record.get("PropertySubType") or street_address or "MLS Listing"
    title = truncate(raw_title, 512)  # matches CharField(max_length=512)

    # Long remarks go to description (TextField)
    description = record.get("PublicRemarks") or ""

    media_items = record.get("Media") or []
    main_image_url = ""
    if media_items:
        first = media_items[0]
        main_image_url = (
            first.get("MediaURL")
            or first.get("MediaURLLarge")
            or first.get("MediaURLMedium")
            or ""
        )

    modification_ts = record.get("ModificationTimestamp")

    return {
        "mls_id": str(record.get("ListingKey") or ""),
        "title": title,
        "description": description,

        "street_address": street_address,
        "city": record.get("City") or "",
        "state": record.get("StateOrProvince") or "",
        "zip_code": record.get("PostalCode") or "",

        "price": Decimal(str(price or 0)),
        "beds": beds,
        "baths": baths,
        "sqft": record.get("BuildingAreaTotal") or None,
        "lot_size": record.get("LotSizeAcres") or None,
        "property_type": record.get("PropertyType") or "",
        "year_built": record.get("YearBuilt") or None,
        "status": "active",  # or map_mls_status(record.get("StandardStatus")),

        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,

        "main_image_url": main_image_url,
        "is_featured": bool(price and price > 750000),
        "mls_modification_timestamp": modification_ts,
    }
