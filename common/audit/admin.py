from django.contrib import admin

from .models import AuditEvent, AuditLedgerState


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "action",
        "entity_type",
        "entity_id",
        "actor_display",
    )
    list_filter = ("action", "entity_type", "source")
    search_fields = (
        "entity_id",
        "entity_display",
        "actor_display",
        "reason",
        "event_hash",
    )
    readonly_fields = [field.name for field in AuditEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLedgerState)
class AuditLedgerStateAdmin(admin.ModelAdmin):
    readonly_fields = ("id", "last_event_id", "last_hash", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
