from django.contrib import admin

from .models import Property, PropertyUnit


class PropertyUnitInline(admin.TabularInline):
    model = PropertyUnit
    extra = 0


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        "street_address",
        "city",
        "state",
        "zip_code",
        "property_type",
        "management_status",
        "is_multi_unit",
        "updated_at",
    )

    list_filter = (
        "management_status",
        "property_type",
        "state",
        "is_multi_unit",
    )

    search_fields = (
        "street_address",
        "city",
        "zip_code",
        "county",
        "subdivision",
    )

    readonly_fields = (
        "property_code",
        "created_at",
        "updated_at",
    )

    inlines = [
        PropertyUnitInline,
    ]


@admin.register(PropertyUnit)
class PropertyUnitAdmin(admin.ModelAdmin):
    list_display = (
        "property",
        "unit_number",
        "beds",
        "baths",
        "sqft",
        "market_rent",
        "status",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "property__street_address",
        "property__city",
        "property__zip_code",
        "unit_number",
    )