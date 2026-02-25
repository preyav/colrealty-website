"""
leads/views.py
──────────────
Handles lead form submissions from listing and rental detail pages.

Flow:
  1. Validate form fields
  2. Save Lead to DB immediately (fast — user never waits for this)
  3. Send Django email notification to agent (fast SMTP)
  4. Queue Celery task for HubSpot sync (async — runs in background)
  5. Redirect user back with success message
"""
import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .models import Lead

logger = logging.getLogger(__name__)


@require_POST
@csrf_protect
def create_lead(request):
    # ── 1. Parse & validate ────────────────────────────────────────────────
    source_type = (request.POST.get("source_type") or "").strip()
    source_id   = (request.POST.get("source_id")   or "").strip()
    name        = (request.POST.get("name")         or "").strip()
    email       = (request.POST.get("email")        or "").strip()
    phone       = (request.POST.get("phone")        or "").strip()
    message     = (request.POST.get("message")      or "").strip()
    page_url    = (request.POST.get("page_url")     or "").strip()

    if source_type not in {"listing", "rental"}:
        return HttpResponseBadRequest("Invalid source_type")
    if not source_id.isdigit():
        return HttpResponseBadRequest("Invalid source_id")
    if not name or not email:
        return HttpResponseBadRequest("Name and email are required")

    # ── 2. Save lead to DB immediately ────────────────────────────────────
    lead = Lead.objects.create(
        source_type = source_type,
        source_id   = int(source_id),
        name        = name,
        email       = email,
        phone       = phone,
        message     = message,
        page_url    = page_url,
    )
    logger.info("Lead #%s created (%s / %s)", lead.id, source_type, source_id)

    # ── 3. Django email notification (direct SMTP — fast) ─────────────────
    try:
        notify_email = getattr(settings, "LEAD_NOTIFY_EMAIL", "").strip()
        if notify_email:
            subject = f"New Col Realty lead: {source_type} #{source_id}"
            body = (
                f"Name:    {name}\n"
                f"Email:   {email}\n"
                f"Phone:   {phone or 'Not provided'}\n"
                f"Page:    {page_url or 'N/A'}\n\n"
                f"Message:\n{message or 'No message provided'}\n"
            )
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [notify_email],
                fail_silently=False,
            )
            lead.email_sent = True
            lead.save(update_fields=["email_sent"])
            logger.info("Lead #%s — Django email notification sent to %s", lead.id, notify_email)

    except Exception as exc:
        logger.exception("Lead #%s — Django email failed: %s", lead.id, exc)
        lead.error = f"Email failed: {exc}"
        lead.save(update_fields=["error"])

    # ── 4. Queue HubSpot sync as async Celery task ────────────────────────
    # The user is never blocked by this. If HubSpot is down, Celery retries
    # automatically up to 3 times with exponential backoff.
    try:
        if getattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "").strip():
            from leads.tasks import sync_lead_to_hubspot
            sync_lead_to_hubspot.apply_async(
                args=[lead.id],
                countdown=2,        # 2 second delay so DB write is committed first
                queue="hubspot",
            )
            logger.info("Lead #%s — HubSpot sync task queued", lead.id)
        else:
            logger.warning("Lead #%s — HUBSPOT_PRIVATE_APP_TOKEN not set, skipping CRM sync", lead.id)

    except Exception as exc:
        # Celery broker down? Log it but don't break the user experience.
        logger.exception("Lead #%s — failed to queue HubSpot task: %s", lead.id, exc)
        existing = lead.error + "\n" if lead.error else ""
        lead.error = existing + f"HubSpot queue failed: {exc}"
        lead.save(update_fields=["error"])

    # ── 5. Redirect with success message ──────────────────────────────────
    messages.success(request, "Thanks! We got your request — we'll reach out shortly.")

    if page_url:
        joiner = "&" if "?" in page_url else "?"
        return redirect(page_url + f"{joiner}sent=1")

    # Fallback if page_url missing
    if source_type == "rental":
        return redirect("rentals:detail", pk=int(source_id))
    return redirect("listings:listing_detail", pk=int(source_id))
