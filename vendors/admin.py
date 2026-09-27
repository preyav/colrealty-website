from django.contrib import admin

from .models import Vendor, VendorTrade


class VendorTradeInline(admin.TabularInline):
    model = VendorTrade
    extra = 0


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "email",
        "phone",
        "status",
        "updated_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "name",
        "company_name",
        "email",
        "phone",
    )

    inlines = [
        VendorTradeInline,
    ]


@admin.register(VendorTrade)
class VendorTradeAdmin(admin.ModelAdmin):
    list_display = (
        "vendor",
        "trade",
    )

    list_filter = (
        "trade",
    )