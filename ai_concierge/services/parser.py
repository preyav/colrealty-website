import re

from listings.services.search import get_listing_cities
from rentals.services.search import get_rental_cities


def get_known_cities() -> list[str]:
    cities = set(get_listing_cities(active_only=True))
    cities.update(get_rental_cities(active_only=True))
    return sorted(cities, key=len, reverse=True)


def extract_intent(text: str, intent_hint: str | None = None) -> str:
    text = text.lower()

    rent_keywords = ["rent", "lease", "apartment", "for rent", "rental"]
    buy_keywords = ["buy", "purchase", "own", "for sale", "home", "house", "condo"]

    if any(k in text for k in rent_keywords):
        return "rent"
    if any(k in text for k in buy_keywords):
        return "buy"

    if intent_hint in {"rent", "buy"}:
        return intent_hint

    return "buy"


def extract_beds(text: str):
    match = re.search(r"(\d+)\s*(bed|bd|bedroom)", text.lower())
    return int(match.group(1)) if match else None


def extract_price(text: str):
    text = text.lower().replace(",", "")

    under_k = re.search(r"(under|below|max|up to)\s*\$?\s*(\d+)\s*k", text)
    if under_k:
        return {"price_max": int(under_k.group(2)) * 1000}

    under_plain = re.search(r"(under|below|max|up to)\s*\$?\s*(\d+)", text)
    if under_plain:
        return {"price_max": int(under_plain.group(2))}

    over_k = re.search(r"(over|above|min|starting at)\s*\$?\s*(\d+)\s*k", text)
    if over_k:
        return {"price_min": int(over_k.group(2)) * 1000}

    over_plain = re.search(r"(over|above|min|starting at)\s*\$?\s*(\d+)", text)
    if over_plain:
        return {"price_min": int(over_plain.group(2))}

    return {}


def extract_location(text: str):
    lowered = text.lower()

    for city in get_known_cities():
        if city.lower() in lowered:
            return city

    return None


def parse_query(text: str, intent_hint: str | None = None) -> dict:
    intent = extract_intent(text, intent_hint=intent_hint)
    beds = extract_beds(text)
    price = extract_price(text)
    location = extract_location(text)

    filters = {}

    if beds:
        filters["beds_min"] = beds

    filters.update(price)

    if location:
        filters["q"] = location
    elif text.strip():
        filters["q"] = text.strip()

    return {
        "intent": intent,
        "filters": filters
    }