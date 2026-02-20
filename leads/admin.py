from django.contrib import admin
from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("created_at", "source_type", "source_id", "name", "email", "phone", "email_sent", "hubspot_sent")
    list_filter = ("source_type", "email_sent", "hubspot_sent")
    search_fields = ("name", "email", "phone", "message", "page_url")
