import re

from .location_service import get_active_cities
from .property_search import get_listing_property_types


def parse_search_query(message: str) -> dict:
    text = (message or "").lower()
    filters: dict[str, str] = {}

    cities = sorted(get_active_cities(), key=len, reverse=True)
    for city in cities:
        if city.lower() in text:
            filters["q"] = city
            break

    property_types = sorted(get_listing_property_types(), key=len, reverse=True)
    for property_type in property_types:
        if property_type.lower() in text:
            filters["property_type"] = property_type
            break

    bed_match = re.search(r"(\d+(?:\.\d+)?)\s*[- ]?(?:bed|beds|bedroom|bedrooms)\b", text)
    if bed_match:
        filters["beds_min"] = bed_match.group(1)

    bath_match = re.search(r"(\d+(?:\.\d+)?)\s*[- ]?(?:bath|baths|bathroom|bathrooms)\b", text)
    if bath_match:
        filters["baths_min"] = bath_match.group(1)

    under_k_match = re.search(r"(?:under|below|max(?:imum)?|up to)\s*\$?\s*(\d{2,4})\s*k\b", text)
    if under_k_match:
        filters["price_max"] = str(int(under_k_match.group(1)) * 1000)
    else:
        under_match = re.search(r"(?:under|below|max(?:imum)?|up to)\s*\$?\s*(\d{5,7})\b", text)
        if under_match:
            filters["price_max"] = under_match.group(1)

    min_price_k_match = re.search(r"(?:over|above|min(?:imum)?|starting at)\s*\$?\s*(\d{2,4})\s*k\b", text)
    if min_price_k_match:
        filters["price_min"] = str(int(min_price_k_match.group(1)) * 1000)
    else:
        min_price_match = re.search(r"(?:over|above|min(?:imum)?|starting at)\s*\$?\s*(\d{5,7})\b", text)
        if min_price_match:
            filters["price_min"] = min_price_match.group(1)

    return filters


def looks_like_listing_search(message: str) -> bool:
    text = (message or "").lower()

    search_signals = [
        "show me",
        "find me",
        "looking for",
        "search for",
        "homes in",
        "houses in",
        "properties in",
        "condos in",
        "townhomes in",
    ]

    if any(signal in text for signal in search_signals):
        return True

    parsed = parse_search_query(message)
    return bool(parsed)
