from typing import Optional
from django.contrib.auth import get_user_model
from ai_concierge.models import AILeadProfile

User = get_user_model()


def get_or_create_profile(session_id: str, user: Optional[User] = None) -> AILeadProfile:
    profile, created = AILeadProfile.objects.get_or_create(
        session_id=session_id,
        defaults={"user": user if getattr(user, "is_authenticated", False) else None},
    )

    if getattr(user, "is_authenticated", False) and profile.user_id != user.id:
        profile.user = user
        profile.save(update_fields=["user", "updated_at"])

    return profile


def update_profile(profile: AILeadProfile, updates: dict) -> AILeadProfile:
    allowed_fields = {
        "full_name",
        "email",
        "phone",
        "intent",
        "homeownership_status",
        "first_time_buyer",
        "has_home_to_sell",
        "budget_min",
        "budget_max",
        "desired_locations",
        "property_type",
        "beds_min",
        "baths_min",
        "timeline",
        "financing_status",
        "investment_intent",
        "must_haves",
        "deal_breakers",
        "notes",
    }

    changed = False
    for key, value in updates.items():
        if key in allowed_fields and value is not None:
            setattr(profile, key, value)
            changed = True

    if changed:
        profile.save()

    return profile
