"""
leads/tasks.py
──────────────
Celery tasks for the leads app.

The only task here is sync_lead_to_hubspot — called by leads/views.py
after saving a lead to the database.  It runs asynchronously in the
'hubspot' queue so the user's form redirect is never delayed by API calls.

Retry strategy:
  - Max 3 retries
  - Exponential backoff: 30s → 90s → 270s
  - On final failure, error is written to lead.error for admin visibility
"""
import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    queue="hubspot",
    max_retries=3,
    default_retry_delay=30,       # base delay in seconds; doubles each retry
    acks_late=True,               # re-queue task if worker crashes mid-execution
    reject_on_worker_lost=True,
)
def sync_lead_to_hubspot(self, lead_id: int) -> dict:
    """
    Async HubSpot CRM sync for a single lead.

    Steps:
      1. Load lead from DB
      2. Upsert HubSpot Contact (create or update by email)
      3. Attach a Note with inquiry details + property URL
      4. Send agent notification email via HubSpot transactional API
      5. Mark lead.hubspot_sent = True and save contact ID

    Called from leads/views.py:
        sync_lead_to_hubspot.apply_async(args=[lead.id], countdown=2)
    """
    from leads.models import Lead
    from leads.services.hubspot import (
        create_note,
        send_agent_notification,
        upsert_contact,
    )

    # ── Load lead ──────────────────────────────────────────────────────────
    try:
        lead = Lead.objects.get(pk=lead_id)
    except Lead.DoesNotExist:
        logger.error("sync_lead_to_hubspot: Lead #%s not found — aborting", lead_id)
        return {"status": "error", "reason": "lead_not_found"}

    if not getattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "").strip():
        logger.warning("HUBSPOT_PRIVATE_APP_TOKEN not set — skipping HubSpot sync for lead #%s", lead_id)
        return {"status": "skipped", "reason": "no_token"}

    # Split full name into first / last
    parts     = (lead.name or "").strip().split()
    firstname = parts[0] if parts else ""
    lastname  = " ".join(parts[1:]) if len(parts) > 1 else ""

    try:
        # ── Step 1: Upsert Contact ─────────────────────────────────────────
        contact_id = upsert_contact(
            email=lead.email,
            firstname=firstname,
            lastname=lastname,
            phone=lead.phone,
            props={
                "lifecyclestage": "lead",
                "hs_lead_status": "NEW",
                "website":        "https://www.colrealty.com",
            },
        )

        # ── Step 2: Attach Note ────────────────────────────────────────────
        note_body = (
            f"New inquiry from Col Realty website\n"
            f"{'─' * 40}\n"
            f"Source:  {lead.source_type.title()} #{lead.source_id}\n"
            f"Page:    {lead.page_url or 'N/A'}\n"
            f"Phone:   {lead.phone or 'Not provided'}\n"
            f"\nMessage:\n{lead.message or 'No message provided'}"
        )
        create_note(contact_id=contact_id, body=note_body)

        # ── Step 3: Agent notification email ──────────────────────────────
        agent_email = getattr(settings, "LEAD_NOTIFY_EMAIL", "").strip()
        if agent_email:
            send_agent_notification(
                agent_email=agent_email,
                lead_name=lead.name,
                lead_email=lead.email,
                lead_phone=lead.phone,
                source_type=lead.source_type,
                source_id=lead.source_id,
                page_url=lead.page_url,
                message=lead.message,
            )

        # ── Step 4: Mark lead as synced ────────────────────────────────────
        lead.hubspot_sent       = True
        lead.hubspot_contact_id = contact_id
        lead.error              = ""         # clear any previous error
        lead.save(update_fields=["hubspot_sent", "hubspot_contact_id", "error"])

        logger.info(
            "sync_lead_to_hubspot: lead #%s → HubSpot contact %s ✓",
            lead_id, contact_id,
        )
        return {"status": "ok", "contact_id": contact_id}

    except Exception as exc:
        logger.warning(
            "sync_lead_to_hubspot: lead #%s failed (attempt %s/%s): %s",
            lead_id, self.request.retries + 1, self.max_retries + 1, exc,
        )

        # Write error to lead immediately so admin can see it
        lead.error = f"Attempt {self.request.retries + 1}: {exc}"
        lead.save(update_fields=["error"])

        # Retry with exponential backoff: 30s, 90s, 270s
        raise self.retry(exc=exc, countdown=30 * (3 ** self.request.retries))
