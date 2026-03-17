import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import AILeadProfile
from .services.orchestrator import run_concierge_turn
from .services.profile import get_or_create_profile


def _ensure_session(request) -> str:
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


@require_GET
def concierge_widget_page(request):
    return render(request, "ai_concierge/widget_demo.html")


@require_GET
def get_profile(request):
    session_id = _ensure_session(request)
    profile = get_or_create_profile(
        session_id=session_id,
        user=request.user if request.user.is_authenticated else None,
    )

    return JsonResponse(
        {
            "session_id": session_id,
            "profile": {
                "full_name": profile.full_name,
                "email": profile.email,
                "phone": profile.phone,
                "intent": profile.intent,
                "homeownership_status": profile.homeownership_status,
                "budget_min": profile.budget_min,
                "budget_max": profile.budget_max,
                "desired_locations": profile.desired_locations,
                "property_type": profile.property_type,
                "beds_min": profile.beds_min,
                "baths_min": float(profile.baths_min) if profile.baths_min is not None else None,
                "timeline": profile.timeline,
                "financing_status": profile.financing_status,
            },
        }
    )


@csrf_exempt
@require_POST
def ai_chat(request):
    session_id = _ensure_session(request)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    message = (payload.get("message") or "").strip()
    page_context = payload.get("page_context") or {}

    if not message:
        return JsonResponse({"error": "Message is required."}, status=400)

    result = run_concierge_turn(
        session_id=session_id,
        user=request.user if request.user.is_authenticated else None,
        message=message,
        page_context=page_context,
    )
    return JsonResponse(result)
