from django.contrib import admin
from .models import AILeadProfile, AIConversationMessage, TourRequest


@admin.register(AILeadProfile)
class AILeadProfileAdmin(admin.ModelAdmin):
    list_display = (
        "session_id",
        "full_name",
        "email",
        "intent",
        "homeownership_status",
        "timeline",
        "updated_at",
    )
    search_fields = ("session_id", "full_name", "email", "phone")
    list_filter = ("intent", "homeownership_status", "financing_status", "created_at")


@admin.register(AIConversationMessage)
class AIConversationMessageAdmin(admin.ModelAdmin):
    list_display = ("session_id", "role", "short_message", "created_at")
    search_fields = ("session_id", "message")
    list_filter = ("role", "created_at")

    def short_message(self, obj):
        return obj.message[:80]


@admin.register(TourRequest)
class TourRequestAdmin(admin.ModelAdmin):
    list_display = ("listing_id", "full_name", "email", "status", "created_at")
    search_fields = ("listing_id", "full_name", "email", "phone")
    list_filter = ("status", "created_at")
