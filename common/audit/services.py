import hashlib
import json
import uuid
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.forms.models import model_to_dict

from .models import AuditEvent, AuditLedgerState


def audit_enabled():
    return getattr(settings, "AUDIT_ENABLED", True)


def _json_safe(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if hasattr(value, "pk"):
        return str(value.pk)
    return value


def normalize_dict(values):
    return {
        str(key): _json_safe(value)
        for key, value in (values or {}).items()
    }


def snapshot(instance, fields):
    data = model_to_dict(instance, fields=fields)
    return normalize_dict(data)


def changed_values(before, after):
    before = normalize_dict(before)
    after = normalize_dict(after)

    old_values = {}
    new_values = {}

    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            old_values[key] = before.get(key)
            new_values[key] = after.get(key)

    return old_values, new_values


def _actor_display(actor):
    if not actor:
        return "System"

    full_name = ""
    if hasattr(actor, "get_full_name"):
        full_name = (actor.get_full_name() or "").strip()

    return full_name or getattr(actor, "email", "") or getattr(actor, "username", "") or str(actor)


def _request_context(request):
    if request is None:
        return None, None

    request_id = getattr(request, "audit_request_id", None)
    if not request_id:
        request_id = uuid.uuid4()
        request.audit_request_id = request_id

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        ip_address = forwarded_for.split(",")[0].strip()
    else:
        ip_address = request.META.get("REMOTE_ADDR") or None

    return request_id, ip_address


def _hash_payload(payload):
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_event(
    *,
    action,
    instance,
    actor=None,
    request=None,
    old_values=None,
    new_values=None,
    reason="",
    metadata=None,
    property_id="",
    source="COL360 Web Portal",
):
    """
    Append one immutable, hash-chained business event.

    If AUDIT_ENABLED=False, no new event is written. Existing history is
    never changed or deleted.
    """
    if not audit_enabled():
        return None

    event_id = uuid.uuid4()
    from django.utils import timezone
    occurred_at = timezone.now()

    entity_type = instance.__class__.__name__
    entity_id = str(instance.pk)
    entity_display = str(instance)

    request_id, ip_address = _request_context(request)

    old_values = normalize_dict(old_values)
    new_values = normalize_dict(new_values)
    metadata = normalize_dict(metadata)

    with transaction.atomic():
        state, _ = AuditLedgerState.objects.select_for_update().get_or_create(pk=1)
        previous_hash = state.last_hash or ""

        payload = {
            "event_id": str(event_id),
            "occurred_at": occurred_at.isoformat(),
            "actor_id": str(actor.pk) if actor and getattr(actor, "pk", None) else "",
            "actor_display": _actor_display(actor),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_display": entity_display,
            "property_id": str(property_id or ""),
            "old_values": old_values,
            "new_values": new_values,
            "reason": reason or "",
            "metadata": metadata,
            "source": source,
            "request_id": str(request_id or ""),
            "ip_address": ip_address or "",
            "previous_hash": previous_hash,
        }
        event_hash = _hash_payload(payload)

        event = AuditEvent.objects.create(
            event_id=event_id,
            occurred_at=occurred_at,
            actor=actor if actor and getattr(actor, "pk", None) else None,
            actor_display=_actor_display(actor),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_display=entity_display,
            property_id=str(property_id or ""),
            old_values=old_values,
            new_values=new_values,
            reason=reason or "",
            metadata=metadata,
            source=source,
            request_id=request_id,
            ip_address=ip_address,
            previous_hash=previous_hash,
            event_hash=event_hash,
        )

        state.last_event_id = event.event_id
        state.last_hash = event.event_hash
        state.save(update_fields=["last_event_id", "last_hash", "updated_at"])

    return event
