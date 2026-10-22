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

from .models import FlooringOption


@admin.register(FlooringOption)
class FlooringOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "code")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


from .models import InteriorFeatureOption


@admin.register(InteriorFeatureOption)
class InteriorFeatureOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "code")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


from .models import ExteriorFeatureOption


@admin.register(ExteriorFeatureOption)
class ExteriorFeatureOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "code")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


from .models import ConstructionMaterialOption


@admin.register(ConstructionMaterialOption)
class ConstructionMaterialOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "code")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


from .models import FoundationOption


@admin.register(FoundationOption)
class FoundationOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "code")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()


from .models import RoofOption


@admin.register(RoofOption)
class RoofOptionAdmin(admin.ModelAdmin):
    list_display = ("label", "code", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("label", "code")

    def get_readonly_fields(self, request, obj=None):
        return ("code",) if obj else ()
