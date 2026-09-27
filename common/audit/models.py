import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLedgerState(models.Model):
    """
    Singleton row used to serialize writes to the hash chain.

    This row is mutable by design. AuditEvent rows are not.
    """
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    last_event_id = models.UUIDField(null=True, blank=True)
    last_hash = models.CharField(max_length=64, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "audit ledger state"
        verbose_name_plural = "audit ledger state"

    def __str__(self):
        return "COL Audit Ledger State"


class AuditEvent(models.Model):
    """
    Append-only record of a meaningful business event.

    Application code must never update or delete an AuditEvent. Corrections
    are represented by a new event.
    """
    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    actor_display = models.CharField(max_length=255, blank=True, default="")

    action = models.CharField(max_length=100, db_index=True)
    entity_type = models.CharField(max_length=100, db_index=True)
    entity_id = models.CharField(max_length=100, db_index=True)
    entity_display = models.CharField(max_length=500, blank=True, default="")

    property_id = models.CharField(max_length=100, blank=True, default="", db_index=True)

    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    reason = models.TextField(blank=True, default="")
    source = models.CharField(max_length=100, blank=True, default="COL360 Web Portal")
    request_id = models.UUIDField(null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    previous_hash = models.CharField(max_length=64, blank=True, default="")
    event_hash = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "-occurred_at"]),
            models.Index(fields=["property_id", "-occurred_at"]),
            models.Index(fields=["action", "-occurred_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError(
                "AuditEvent is append-only. Existing audit events cannot be modified."
            )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError(
            "AuditEvent is append-only. Audit events cannot be deleted."
        )

    def __str__(self):
        return f"{self.action} · {self.entity_type} {self.entity_id}"
