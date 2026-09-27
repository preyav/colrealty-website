from django.contrib import admin

from .models import (
    MaintenancePhoto,
    MaintenanceRequest,
    VendorAssignment,
    VendorAward,
    VendorEstimate,
    VendorInvoice,
    VendorQuoteRequest,
    WorkOrder,
    WorkOrderStatusHistory,
)

class VendorAssignmentInline(admin.TabularInline):
    model = VendorAssignment
    extra = 0


class VendorAwardInline(admin.TabularInline):
    model = VendorAward
    extra = 0
    readonly_fields = ("awarded_at", "confirmed_at", "revoked_at")

class MaintenancePhotoInline(admin.TabularInline):
    model = MaintenancePhoto
    extra = 0


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "unit",
        "category",
        "priority",
        "status",
        "assigned_reviewer",
        "review_due_at",
        "reported_by_tenant",
        "submitted_at",
    )

    list_filter = (
        "status",
        "priority",
        "category",
    )

    search_fields = (
        "title",
        "description",
        "unit__property__street_address",
        "reported_by_tenant__first_name",
        "reported_by_tenant__last_name",
    )

    inlines = [MaintenancePhotoInline]

class WorkOrderStatusHistoryInline(admin.TabularInline):
    model = WorkOrderStatusHistory
    extra = 0
    readonly_fields = ("changed_at",)


class VendorEstimateInline(admin.TabularInline):
    model = VendorEstimate
    extra = 0


class VendorInvoiceInline(admin.TabularInline):
    model = VendorInvoice
    extra = 0

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "unit",
        "status",
        "scheduled_for",
        "estimated_cost",
        "actual_cost",
        "updated_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "title",
        "description",
        "unit__property__street_address",
    )

    inlines = [
        VendorAwardInline,
        VendorAssignmentInline,
        VendorEstimateInline,
        VendorInvoiceInline,
        WorkOrderStatusHistoryInline,
    ]


@admin.register(VendorAssignment)
class VendorAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "work_order",
        "vendor",
        "status",
        "assigned_at",
        "scheduled_for",
        "completed_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "vendor__name",
        "vendor__company_name",
        "work_order__title",
        "work_order__unit__property__street_address",
    )


@admin.register(MaintenancePhoto)
class MaintenancePhotoAdmin(admin.ModelAdmin):
    list_display = (
        "maintenance_request",
        "photo_type",
        "caption",
        "uploaded_by",
        "created_at",
    )

    list_filter = (
        "photo_type",
    )

    search_fields = (
        "maintenance_request__title",
        "maintenance_request__unit__property__street_address",
        "caption",
    )


@admin.register(WorkOrderStatusHistory)
class WorkOrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "work_order",
        "from_status",
        "to_status",
        "changed_by",
        "changed_at",
    )

    list_filter = (
        "to_status",
    )

    search_fields = (
        "work_order__title",
        "work_order__unit__property__street_address",
        "notes",
    )


@admin.register(VendorEstimate)
class VendorEstimateAdmin(admin.ModelAdmin):
    list_display = (
        "work_order",
        "vendor",
        "amount",
        "status",
        "submitted_at",
        "approved_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "vendor__name",
        "vendor__company_name",
        "work_order__title",
        "work_order__unit__property__street_address",
    )


@admin.register(VendorAward)
class VendorAwardAdmin(admin.ModelAdmin):
    list_display = (
        "work_order", "vendor", "method", "status", "awarded_at",
        "confirmed_at", "revoked_at",
    )
    list_filter = ("status", "method", "revocation_reason")
    search_fields = ("vendor__name", "vendor__company_name", "work_order__title")


@admin.register(VendorQuoteRequest)
class VendorQuoteRequestAdmin(admin.ModelAdmin):
    list_display = (
        "work_order",
        "vendor",
        "status",
        "response_due",
        "sent_at",
    )
    list_filter = ("status", "delivery_channel")
    search_fields = (
        "vendor__name",
        "vendor__company_name",
        "work_order__title",
        "work_order__unit__property__street_address",
    )


@admin.register(VendorInvoice)
class VendorInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "vendor",
        "work_order",
        "amount",
        "status",
        "invoice_date",
        "due_date",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "invoice_number",
        "vendor__name",
        "vendor__company_name",
        "work_order__title",
        "work_order__unit__property__street_address",
    )
