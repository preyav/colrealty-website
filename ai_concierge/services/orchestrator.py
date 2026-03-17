import re
from typing import Optional

from .profile import get_or_create_profile, update_profile
from .memory import save_message, get_recent_messages


BUY_WORDS = {"buy", "purchase", "home", "house", "condo"}
RENT_WORDS = {"rent", "rental", "lease", "apartment"}
INVEST_WORDS = {"invest", "investment"}
SELL_WORDS = {"sell", "listing my home", "list my home"}


def _detect_intent(message: str) -> Optional[str]:
    text = message.lower()

    if any(word in text for word in SELL_WORDS):
        return "sell"
    if any(word in text for word in INVEST_WORDS):
        return "invest"
    if any(word in text for word in RENT_WORDS):
        return "rent"
    if any(word in text for word in BUY_WORDS):
        return "buy"
    return None


def _detect_homeownership_status(message: str) -> Optional[str]:
    text = message.lower()

    renting_patterns = [
        "i rent",
        "i'm renting",
        "i am renting",
        "currently renting",
        "we rent",
        "renting now",
    ]
    owning_patterns = [
        "i own",
        "i'm a homeowner",
        "i am a homeowner",
        "currently own",
        "we own",
        "homeowner",
        "own my home",
    ]

    if any(p in text for p in renting_patterns):
        return "renting"
    if any(p in text for p in owning_patterns):
        return "owning"
    return None


def _detect_budget_max(message: str) -> Optional[int]:
    text = message.lower().replace(",", "")
    match = re.search(r"\$?(\d{2,7})\s?k\b", text)
    if match:
        return int(match.group(1)) * 1000

    match = re.search(r"\$?(\d{5,7})\b", text)
    if match:
        return int(match.group(1))

    return None


def _detect_beds_min(message: str) -> Optional[int]:
    text = message.lower()
    match = re.search(r"(\d+)\s*[- ]?bed", text)
    if match:
        return int(match.group(1))
    return None


def _detect_location(message: str) -> list[str]:
    known_locations = [
        "austin",
        "cedar park",
        "round rock",
        "pflugerville",
        "leander",
        "georgetown",
    ]
    text = message.lower()
    found = [loc.title() for loc in known_locations if loc in text]
    return found


def run_concierge_turn(session_id: str, user, message: str, page_context: dict | None = None) -> dict:
    page_context = page_context or {}
    profile = get_or_create_profile(session_id=session_id, user=user)

    save_message(session_id=session_id, role="user", message=message, metadata={"page_context": page_context})

    updates = {}

    detected_intent = _detect_intent(message)
    if detected_intent and not profile.intent:
        updates["intent"] = detected_intent

    detected_homeownership = _detect_homeownership_status(message)
    if detected_homeownership:
        updates["homeownership_status"] = detected_homeownership

    detected_budget_max = _detect_budget_max(message)
    if detected_budget_max and not profile.budget_max:
        updates["budget_max"] = detected_budget_max

    detected_beds = _detect_beds_min(message)
    if detected_beds and not profile.beds_min:
        updates["beds_min"] = detected_beds

    detected_locations = _detect_location(message)
    if detected_locations and not profile.desired_locations:
        updates["desired_locations"] = detected_locations

    if updates:
        profile = update_profile(profile, updates)

    reply = _build_reply(profile, message, page_context)
    save_message(session_id=session_id, role="assistant", message=reply, metadata={"profile_updates": updates})

    return {
        "reply": reply,
        "profile": {
            "intent": profile.intent,
            "homeownership_status": profile.homeownership_status,
            "budget_max": profile.budget_max,
            "beds_min": profile.beds_min,
            "desired_locations": profile.desired_locations,
        },
        "profile_updates": updates,
        "suggested_actions": _suggested_actions(profile),
    }


def _build_reply(profile, message: str, page_context: dict) -> str:
    if not profile.intent:
        return (
            "Happy to help with that. Are you looking to buy, rent, sell, invest, "
            "or just explore options right now?"
        )

    if profile.homeownership_status == "unknown" and profile.intent in {"buy", "rent", "invest"}:
        return (
            "Got it. Before I narrow things down, are you currently renting, "
            "or do you own your home today?"
        )

    if profile.intent == "buy":
        missing = []
        if not profile.desired_locations:
            missing.append("location")
        if not profile.budget_max:
            missing.append("budget")
        if not profile.beds_min:
            missing.append("bedrooms")

        if missing:
            if "location" in missing:
                return "Which areas are you most interested in around Austin?"
            if "budget" in missing:
                return "Do you already have a target budget range in mind?"
            if "bedrooms" in missing:
                return "How many bedrooms would you ideally like?"

        return (
            f"Great — I have a good starting profile for your home search"
            f"{' in ' + ', '.join(profile.desired_locations) if profile.desired_locations else ''}. "
            "Next, I can help surface matching homes, compare options, or start narrowing by style, "
            "school areas, or commute preferences."
        )

    if profile.intent == "rent":
        return (
            "Thanks — I can help narrow rental options by area, budget, and move-in timing. "
            "What neighborhoods or suburbs are you considering?"
        )

    if profile.intent == "sell":
        return (
            "I can help with seller guidance too. Are you looking for a rough pricing range, "
            "market timing insight, or to connect directly with an agent?"
        )

    if profile.intent == "invest":
        return (
            "I can help with investment-focused searches and market guidance. "
            "Are you looking for long-term rental potential, appreciation, or both?"
        )

    return "Tell me a little more about what you're looking for, and I’ll help narrow it down."


def _suggested_actions(profile) -> list[str]:
    actions = []

    if profile.intent in {"buy", "rent"}:
        actions.extend(["Start search", "Refine preferences"])

    if profile.intent == "sell":
        actions.extend(["Get pricing guidance", "Talk to an agent"])

    if profile.homeownership_status == "owning":
        actions.append("Discuss sell-before-buy strategy")

    return actions[:3]
