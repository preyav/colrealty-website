import requests
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.contrib import messages

from .models import Lead

HUBSPOT_BASE = "https://api.hubapi.com"


def _hubspot_headers():
    if not settings.HUBSPOT_PRIVATE_APP_TOKEN:
        raise RuntimeError("HUBSPOT_PRIVATE_APP_TOKEN is not set")
    return {
        "Authorization": f"Bearer {settings.HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json",
    }


def _hubspot_request(method, path, json=None, timeout=12):
    url = f"{HUBSPOT_BASE}{path}"
    r = requests.request(method, url, headers=_hubspot_headers(), json=json, timeout=timeout)
    if r.status_code >= 400:
        raise RuntimeError(f"HubSpot {r.status_code}: {r.text}")
    return r.json()


def _split_name(full_name: str):
    parts = (full_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def hubspot_upsert_contact(email: str, name: str, phone: str = "") -> str:
    search_payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": email,
            }]
        }],
        "properties": ["email"],
        "limit": 1,
    }
    search = _hubspot_request("POST", "/crm/v3/objects/contacts/search", json=search_payload)
    results = (search or {}).get("results", [])

    firstname, lastname = _split_name(name)
    props = {"email": email, "firstname": firstname, "lastname": lastname}
    if phone:
        props["phone"] = phone

    if results:
        contact_id = results[0]["id"]
        _hubspot_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", json={"properties": props})
        return contact_id

    created = _hubspot_request("POST", "/crm/v3/objects/contacts", json={"properties": props})
    return created["id"]


@require_POST
@csrf_protect
def create_lead(request):
    if request.method != "POST":
        return redirect("pages:home")


    source_type = (request.POST.get("source_type") or "").strip()
    source_id = (request.POST.get("source_id") or "").strip()
    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    message = (request.POST.get("message") or "").strip()
    page_url = (request.POST.get("page_url") or "").strip()

    if source_type not in {"listing", "rental"}:
        return HttpResponseBadRequest("Invalid source_type")
    if not source_id.isdigit():
        return HttpResponseBadRequest("Invalid source_id")
    if not name or not email:
        return HttpResponseBadRequest("Name and email required")

    lead = Lead.objects.create(
        source_type=source_type,
        source_id=int(source_id),
        name=name,
        email=email,
        phone=phone,
        message=message,
        page_url=page_url,
    )

    # 1) Email you
    try:
        if getattr(settings, "LEAD_NOTIFY_EMAIL", ""):
            subject = f"New Col Realty lead: {source_type} #{source_id}"
            body = (
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Phone: {phone}\n"
                f"Page: {page_url}\n\n"
                f"Message:\n{message}\n"
            )
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [settings.LEAD_NOTIFY_EMAIL],
                fail_silently=False,
            )
            lead.email_sent = True
            lead.save(update_fields=["email_sent"])
    except Exception as e:
        lead.error = f"Email failed: {e}"
        lead.save(update_fields=["error"])

    # 2) HubSpot
    try:
        if getattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", ""):
            contact_id = hubspot_upsert_contact(email=email, name=name, phone=phone)
            lead.hubspot_sent = True
            lead.hubspot_contact_id = contact_id
            lead.save(update_fields=["hubspot_sent", "hubspot_contact_id"])
    except Exception as e:
        lead.error = (lead.error + "\n" if lead.error else "") + f"HubSpot failed: {e}"
        lead.save(update_fields=["error"])

  # ✅ Redirect instead of returning JSON
    if page_url:
        # add querystring so the page can show a success banner
        joiner = "&" if "?" in page_url else "?"
        messages.success(request, "Thanks! We got your request — we’ll reach out shortly.")
        return redirect(page_url + f"{joiner}sent=1")

    # fallback if page_url missing
    messages.success(request, "Thanks! We got your request — we’ll reach out shortly.")
    if source_type == "rental":
        return redirect("rentals:detail", pk=source_id)
    return redirect("listings:listing_detail", pk=source_id)
