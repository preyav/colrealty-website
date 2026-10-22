from django.contrib import admin

from .models import (
    ChartAccount,
    FinancialAccount,
    QuickBooksBillMapping,
    QuickBooksConnection,
    QuickBooksPaymentMapping,
    QuickBooksVendorMapping,
)


@admin.register(ChartAccount)
class ChartAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account_type", "is_active")
    list_filter = ("account_type", "is_active")
    search_fields = ("code", "name")


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "ledger_account", "institution_name", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "institution_name", "ledger_account__code")


@admin.register(QuickBooksConnection)
class QuickBooksConnectionAdmin(admin.ModelAdmin):
    list_display = ("company_name", "realm_id", "environment", "is_active", "connected_at")
    list_filter = ("environment", "is_active")
    search_fields = ("company_name", "realm_id")
    readonly_fields = (
        "realm_id", "company_name", "environment", "connected_by", "connected_at",
        "last_synced_at", "last_error", "updated_at",
    )
    exclude = ("access_token_encrypted", "refresh_token_encrypted")


@admin.register(QuickBooksVendorMapping)
class QuickBooksVendorMappingAdmin(admin.ModelAdmin):
    list_display = ("vendor", "connection", "quickbooks_vendor_id", "last_synced_at")
    search_fields = ("vendor__name", "vendor__company_name", "quickbooks_vendor_id")
    readonly_fields = ("created_at", "updated_at", "last_synced_at")


@admin.register(QuickBooksBillMapping)
class QuickBooksBillMappingAdmin(admin.ModelAdmin):
    list_display = (
        "invoice", "connection", "quickbooks_bill_id", "document_number",
        "expense_account_name", "last_synced_at",
    )
    search_fields = (
        "invoice__invoice_number", "invoice__vendor__name",
        "invoice__vendor__company_name", "quickbooks_bill_id", "document_number",
    )
    readonly_fields = (
        "connection", "invoice", "quickbooks_bill_id", "sync_token",
        "document_number", "expense_account_id", "expense_account_name",
        "last_synced_at", "last_error", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(QuickBooksPaymentMapping)
class QuickBooksPaymentMappingAdmin(admin.ModelAdmin):
    list_display = (
        "payment", "connection", "quickbooks_payment_id", "status",
        "payment_account_name", "last_synced_at",
    )
    list_filter = ("status", "payment_account_type")
    search_fields = (
        "payment__invoice__invoice_number", "quickbooks_payment_id",
        "document_number", "payment_account_name",
    )
    readonly_fields = (
        "connection", "payment", "bill_mapping", "quickbooks_payment_id",
        "sync_token", "document_number", "payment_account_id",
        "payment_account_name", "payment_account_type", "status",
        "last_synced_at", "last_error", "created_at", "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# Setup is explicit; these screens never create opening balances or historical payments.
from .book_models import AccountingEntity,PropertyBooks,EntityBank,BookPosting,BillAccounting,FundsEvent,BankReconciliation,BankClearance

@admin.register(AccountingEntity)
class AccountingEntityAdmin(admin.ModelAdmin):
    list_display=['name','default_basis','is_active']

@admin.register(PropertyBooks)
class PropertyBooksAdmin(admin.ModelAdmin):
    def has_delete_permission(self,request,obj=None):return False
    list_display=['property','entity','enabled','reserve']
    list_filter=['entity','enabled']

@admin.register(EntityBank)
class EntityBankAdmin(admin.ModelAdmin):
    def has_delete_permission(self,request,obj=None):return False
    list_display=['entity','bank']

@admin.register(BillAccounting)
class BillAccountingAdmin(admin.ModelAdmin):
    def has_delete_permission(self,request,obj=None):return False
    def get_readonly_fields(self,request,obj=None):
        if obj and BookPosting.objects.filter(source_key='bill:'+str(obj.invoice_id)).exists():return ['invoice','expense_account','service_start','service_end','recognition_date']
        return []
    list_display=['invoice','expense_account','service_start','service_end','recognition_date']

class ReadOnlyBookAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False

admin.site.register(BookPosting,ReadOnlyBookAdmin)
admin.site.register(FundsEvent,ReadOnlyBookAdmin)
admin.site.register(BankReconciliation,ReadOnlyBookAdmin)
admin.site.register(BankClearance,ReadOnlyBookAdmin)
