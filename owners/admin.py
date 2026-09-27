from django.contrib import admin

from .models import OwnerProfile, PropertyOwnership


class PropertyOwnershipInline(admin.TabularInline):
    model = PropertyOwnership
    extra = 0


@admin.register(OwnerProfile)
class OwnerProfileAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "owner_type",
        "email",
        "phone",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "owner_type",
        "is_active",
    )

    search_fields = (
        "first_name",
        "last_name",
        "entity_name",
        "email",
        "phone",
    )

    inlines = [
        PropertyOwnershipInline,
    ]


@admin.register(PropertyOwnership)
class PropertyOwnershipAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "owner",
        "ownership_percentage",
        "is_primary_contact",
        "start_date",
        "end_date",
    )

    list_filter = (
        "is_primary_contact",
    )

    search_fields = (
        "property__street_address",
        "property__city",
        "owner__first_name",
        "owner__last_name",
        "owner__entity_name",
        "owner__email",
    )