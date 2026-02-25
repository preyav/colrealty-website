"""
leads/services/hubspot.py
──────────────────────────
All HubSpot CRM API logic for Col Realty.

Three public functions:
  - upsert_contact()          → create or update a Contact by email
  - create_note()             → attach an inquiry note to a Contact
  - send_agent_notification() → trigger a HubSpot notification email to the agent

Never import and call these at module level.
Always call from inside a function or Celery task.
"""
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

HUBSPOT_BASE = "https://api.hubapi.com"


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _headers() -> dict:
    token = getattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "HUBSPOT_PRIVATE_APP_TOKEN is not set. "
            "Add it to your .env file or AWS Parameter Store."
        )
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }


def _request(method: str, path: str, json: dict = None, timeout: int = 15) -> dict:
    """
    Authenticated HubSpot API request.
    Raises RuntimeError on 4xx/5xx so Celery can catch and retry.
    """
    url = f"{HUBSPOT_BASE}{path}"
    logger.debug("HubSpot %s %s", method, path)
    response = requests.request(method, url, headers=_headers(), json=json, timeout=timeout)

    if response.status_code >= 400:
        raise RuntimeError(
            f"HubSpot API error {response.status_code} on {method} {path}: {response.text}"
        )

    # 204 No Content (PATCH responses) — return empty dict
    if response.status_code == 204:
        return {}

    return response.json()


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def upsert_contact(
    email:     str,
    firstname: str = "",
    lastname:  str = "",
    phone:     str = "",
    props:     dict = None,
) -> str:
    """
    Create or update a HubSpot Contact by email.
    Returns the HubSpot contact ID (string).
    """
    # Search for existing contact
    search_payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator":     "EQ",
                "value":        email,
            }]
        }],
        "properties": ["email", "firstname", "lastname"],
        "limit": 1,
    }
    search  = _request("POST", "/crm/v3/objects/contacts/search", json=search_payload)
    results = (search or {}).get("results", [])

    contact_props = {"email": email, "firstname": firstname, "lastname": lastname}
    if phone:
        contact_props["phone"] = phone
    if props:
        contact_props.update(props)

    if results:
        contact_id = results[0]["id"]
        _request("PATCH", f"/crm/v3/objects/contacts/{contact_id}",
                 json={"properties": contact_props})
        logger.info("HubSpot: updated contact %s (%s)", contact_id, email)
        return contact_id

    created    = _request("POST", "/crm/v3/objects/contacts", json={"properties": contact_props})
    contact_id = created["id"]
    logger.info("HubSpot: created contact %s (%s)", contact_id, email)
    return contact_id


def create_note(contact_id: str, body: str) -> str:
    """
    Create a Note in HubSpot and associate it with a Contact.
    Returns the note ID (string).
    """
    timestamp_ms = str(int(time.time() * 1000))

    note    = _request("POST", "/crm/v3/objects/notes", json={
        "properties": {
            "hs_note_body": body,
            "hs_timestamp": timestamp_ms,
        }
    })
    note_id = note["id"]

    # Associate note → contact (association type 202 = note_to_contact)
    _request("PUT",
             f"/crm/v3/objects/notes/{note_id}/associations/contacts/{contact_id}/202")
    logger.info("HubSpot: created note %s on contact %s", note_id, contact_id)
    return note_id


def send_agent_notification(
    agent_email:  str,
    lead_name:    str,
    lead_email:   str,
    lead_phone:   str,
    source_type:  str,
    source_id:    int,
    page_url:     str,
    message:      str,
) -> None:
    """
    Send a transactional notification email to the agent via HubSpot.

    Prerequisites in HubSpot:
      1. Create a Transactional Email template in HubSpot Marketing > Email > Transactional.
      2. Note its numeric Email ID.
      3. Set HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID=<id> in your .env

    Custom token names used (add these to your HubSpot template):
      {{ lead_name }}, {{ lead_email }}, {{ lead_phone }},
      {{ source_type }}, {{ source_id }}, {{ page_url }}, {{ message }}

    If the email ID is not configured, logs a warning and skips silently
    so it never blocks lead capture.
    """
    email_id = getattr(settings, "HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID", "").strip()
    if not email_id:
        logger.warning(
            "HUBSPOT_AGENT_NOTIFICATION_EMAIL_ID not configured — "
            "skipping HubSpot agent notification. "
            "Set this in .env to enable it."
        )
        return

    payload = {
        "emailId": int(email_id),
        "message": {"to": agent_email},
        "customProperties": [
            {"name": "lead_name",   "value": lead_name},
            {"name": "lead_email",  "value": lead_email},
            {"name": "lead_phone",  "value": lead_phone or "Not provided"},
            {"name": "source_type", "value": source_type.title()},
            {"name": "source_id",   "value": str(source_id)},
            {"name": "page_url",    "value": page_url},
            {"name": "message",     "value": message or "No message provided"},
        ],
    }

    _request("POST", "/marketing/v3/transactional/single-email/send", json=payload)
    logger.info("HubSpot: agent notification sent to %s for lead %s", agent_email, lead_email)
