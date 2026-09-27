from django.contrib import admin

from .models import Lease, LeaseTenant


class LeaseTenantInline(admin.TabularInline):
    model = LeaseTenant
    extra = 0


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = (
        "unit",
        "start_date",
        "end_date",
        "monthly_rent",
        "security_deposit",
        "status",
        "updated_at",
    )

    list_filter = (
        "status",
        "start_date",
        "end_date",
    )

    search_fields = (
        "unit__property__street_address",
        "unit__property__city",
        "unit__unit_number",
    )

    inlines = [
        LeaseTenantInline,
    ]


@admin.register(LeaseTenant)
class LeaseTenantAdmin(admin.ModelAdmin):
    list_display = (
        "lease",
        "tenant",
        "role",
        "is_financially_responsible",
    )

    list_filter = (
        "role",
        "is_financially_responsible",
    )

    search_fields = (
        "tenant__first_name",
        "tenant__last_name",
        "tenant__email",
        "lease__unit__property__street_address",
    )