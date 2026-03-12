from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Lead
from django.utils.safestring import mark_safe


def retry_hubspot_sync(modeladmin, request, queryset):
    """Admin action — re-queue HubSpot sync for selected leads."""
    from leads.tasks import sync_lead_to_hubspot
    queued = 0
    for lead in queryset.filter(hubspot_sent=False):
        sync_lead_to_hubspot.apply_async(args=[lead.id], queue="hubspot")
        queued += 1
    messages.success(request, f"{queued} lead(s) queued for HubSpot sync.")


retry_hubspot_sync.short_description = "🔄 Retry HubSpot sync for selected leads"


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "name", "email", "phone",
        "source_type", "source_id",
        "email_sent_badge", "hubspot_badge", "error_badge",
    )
    list_filter = ("source_type", "email_sent", "hubspot_sent", "created_at")
    search_fields = ("name", "email", "phone", "message", "page_url")
    readonly_fields = (
        "created_at", "email_sent", "hubspot_sent",
        "hubspot_contact_id", "error", "page_url",
    )
    ordering = ("-created_at",)
    actions = [retry_hubspot_sync]

    fieldsets = (
        ("Contact Info", {
            "fields": ("name", "email", "phone")
        }),
        ("Inquiry", {
            "fields": ("source_type", "source_id", "message", "page_url")
        }),
        ("Delivery Status", {
            "fields": ("created_at", "email_sent", "hubspot_sent", "hubspot_contact_id", "error")
        }),
    )

    @admin.display(description="Email", boolean=True)
    def email_sent_badge(self, obj):
        return obj.email_sent

    @admin.display(description="HubSpot")
    def hubspot_badge(self, obj):
        if obj.hubspot_sent:
            return format_html(
                '<a href="https://app-na2.hubspot.com/contacts/242914945/record/0-1/{}" '
                'target="_blank" style="color:green;">✅ {}</a>',
                obj.hubspot_contact_id, obj.hubspot_contact_id
            )
        return mark_safe('<span style="color:red;">❌ Not synced</span>')

    @admin.display(description="Error")
    def error_badge(self, obj):
        if obj.error:
            return format_html('<span style="color:red;" title="{}">⚠️ Error</span>', obj.error)
        return "—"
