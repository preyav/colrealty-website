from django.contrib import admin
from django.utils.html import format_html
from .models import Rental


def mark_active(modeladmin, request, queryset):
    updated = queryset.update(status="active")
    modeladmin.message_user(request, f"{updated} rental(s) set to active.")
mark_active.short_description = "✅ Set selected rentals to Active"


def mark_leased(modeladmin, request, queryset):
    updated = queryset.update(status="leased")
    modeladmin.message_user(request, f"{updated} rental(s) marked as leased.")
mark_leased.short_description = "Mark selected rentals as Leased"


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):
    list_display = (
        "title", "city", "state", "rent_display",
        "beds", "baths", "property_type",
        "status_badge", "updated_at",
    )
    list_filter   = ("status", "city", "state", "property_type")
    search_fields = ("title", "street_address", "city", "zip_code", "mls_id")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-updated_at",)
    actions  = [mark_active, mark_leased]

    fieldsets = (
        ("Property Info", {
            "fields": ("title", "property_type", "status", "description")
        }),
        ("Address", {
            "fields": ("street_address", "city", "state", "zip_code")
        }),
        ("Pricing & Details", {
            "fields": ("rent", "beds", "baths", "sqft")
        }),
        ("Media", {
            "fields": ("main_image_url",)
        }),
        ("Location", {
            "fields": ("latitude", "longitude")
        }),
        ("MLS Metadata", {
            "classes": ("collapse",),
            "fields": ("mls_id", "created_at", "updated_at")
        }),
    )

    @admin.display(description="Rent/mo", ordering="rent")
    def rent_display(self, obj):
        return f"${obj.rent:,.0f}/mo"

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {"active": "green", "leased": "orange", "inactive": "red"}
        colour  = colours.get(obj.status, "gray")
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            colour, obj.status.title()
        )
