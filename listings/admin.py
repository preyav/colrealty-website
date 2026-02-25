from django.contrib import admin
from django.utils.html import format_html
from .models import Listing


def mark_featured(modeladmin, request, queryset):
    updated = queryset.update(is_featured=True)
    modeladmin.message_user(request, f"{updated} listing(s) marked as featured.")
mark_featured.short_description = "⭐ Mark selected listings as featured"


def unmark_featured(modeladmin, request, queryset):
    updated = queryset.update(is_featured=False)
    modeladmin.message_user(request, f"{updated} listing(s) removed from featured.")
unmark_featured.short_description = "Remove featured from selected listings"


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        "title", "city", "state", "price_display",
        "beds", "baths", "property_type",
        "status_badge", "is_featured", "updated_at",
    )
    list_filter   = ("status", "is_featured", "state", "city", "property_type")
    search_fields = ("title", "street_address", "city", "zip_code", "mls_id")
    readonly_fields = ("mls_id", "created_at", "updated_at", "mls_modification_timestamp")
    ordering = ("-updated_at",)
    actions  = [mark_featured, unmark_featured]

    fieldsets = (
        ("Property Info", {
            "fields": ("title", "property_type", "status", "is_featured", "description")
        }),
        ("Address", {
            "fields": ("street_address", "city", "state", "zip_code")
        }),
        ("Pricing & Details", {
            "fields": ("price", "beds", "baths", "sqft", "lot_size", "year_built")
        }),
        ("Media", {
            "fields": ("main_image_url",)
        }),
        ("Location", {
            "fields": ("latitude", "longitude")
        }),
        ("MLS Metadata", {
            "classes": ("collapse",),
            "fields": ("mls_id", "mls_modification_timestamp", "created_at", "updated_at")
        }),
    )

    @admin.display(description="Price", ordering="price")
    def price_display(self, obj):
        return f"${obj.price:,.0f}"

    @admin.display(description="Status")
    def status_badge(self, obj):
        colours = {"active": "green", "pending": "orange", "sold": "red"}
        colour  = colours.get(obj.status, "gray")
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            colour, obj.status.title()
        )
