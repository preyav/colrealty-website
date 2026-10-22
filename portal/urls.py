from . import tenant_work
from . import reimbursement_views
from . import property_financial_views
from . import property_registers
from accounting import workspace_views, chart_actions, journal_views, financials, book_views, bank_actions
from django.urls import path
from . import views, settings_views
from properties import document_uploads

app_name = "portal"

urlpatterns = [
    path('work-orders/<int:work_order_id>/tenant-work/',tenant_work.save_tenant_work,name='save_tenant_work'),
    path('finance/reimbursements/<int:settlement_id>/', reimbursement_views.bill_reimbursement, name='bill_reimbursement'),
    path('finance/reimbursements/entries/<int:reimbursement_id>/void/', reimbursement_views.bill_reimbursement_void, name='bill_reimbursement_void'),
    path("properties/<int:property_id>/financials/",property_financial_views.property_financials,name="property_financials"),
    path("rentals/outstanding-balances/",property_registers.outstanding_balances,name="outstanding_balances"),
    path("maintenance/registers/<str:kind>/",property_registers.property_register,name="property_register"),
    path("maintenance/registers/<str:kind>/<int:record_id>/",property_registers.property_register,name="property_register_edit"),
    path("finance/accounts/financial/<int:account_id>/actions/<str:action>/",bank_actions.bank_account_action,name="finance_bank_account_action"),
    path("settings/",settings_views.portal_settings,name="portal_settings"),
    path("finance/operations/",book_views.accounting_operations,name="accounting_operations"),
    path('finance/general-ledger/',journal_views.general_ledger,name='general_ledger'),
    path('finance/journals/new/',journal_views.journal_create,name='journal_create'),
    path('finance/journals/<int:journal_id>/',journal_views.journal_detail,name='journal_detail'),
    path("properties/documents/upload/", document_uploads.upload_property_document, name="property_document_upload"),
    path("properties/documents/<uuid:upload_id>/", document_uploads.download_property_document, name="property_document_download"),
    path("", views.dashboard, name="dashboard"),
    path("leads/", views.leads_list, name="leads"),
    path("leads/retry-all/", views.leads_retry_all, name="leads_retry_all"),
    path("leads/<int:lead_id>/retry/", views.lead_retry_hubspot, name="lead_retry"),
    path("listings/", views.listings_list, name="listings"),
    path("listings/<int:listing_id>/featured/", views.toggle_featured, name="toggle_featured"),
    path("rentals/", views.rentals_list, name="rentals"),
    path("properties/", views.properties_list, name="properties"),
    path("owners/", views.owners_list, name="owners"),
    path("tenants/", views.tenants_list, name="tenants"),
    path("leases/", views.leases_list, name="leases"),
    path("maintenance/", views.maintenance_list, name="maintenance"),
    path("work-orders/", views.work_orders_list, name="work_orders"),
    path("finance/", financials.finance_dashboard, name="finance_dashboard"),
    path("finance/accounts/", workspace_views.accounts, name="finance_accounts"),
    path("finance/quickbooks/", views.finance_quickbooks, name="finance_quickbooks"),
    path("finance/quickbooks/connect/", views.finance_quickbooks_connect, name="finance_quickbooks_connect"),
    path("finance/quickbooks/callback/", views.finance_quickbooks_callback, name="finance_quickbooks_callback"),
    path("finance/quickbooks/disconnect/", views.finance_quickbooks_disconnect, name="finance_quickbooks_disconnect"),
    path("finance/quickbooks/test/", views.finance_quickbooks_test, name="finance_quickbooks_test"),
    path("finance/quickbooks/vendors/<int:vendor_id>/sync/", views.finance_quickbooks_vendor_sync, name="finance_quickbooks_vendor_sync"),
    path("finance/accounts/chart/add/", views.finance_chart_account_form, name="finance_chart_account_add"),
    path("finance/accounts/chart/<int:account_id>/edit/", views.finance_chart_account_form, name="finance_chart_account_edit"),
    path("finance/accounts/chart/<int:account_id>/actions/<str:action>/", chart_actions.chart_account_action, name="finance_chart_account_action"),
    path("finance/accounts/financial/add/", views.finance_financial_account_form, name="finance_financial_account_add"),
    path("finance/accounts/financial/<int:account_id>/edit/", views.finance_financial_account_form, name="finance_financial_account_edit"),
    path("finance/vendor-bills/", views.finance_vendor_invoices, name="finance_vendor_invoices"),
    path("finance/vendor-bills/<int:invoice_id>/", views.finance_vendor_invoice_detail, name="finance_vendor_invoice_detail"),
    path("finance/vendor-bills/<int:invoice_id>/quickbooks/", views.finance_vendor_invoice_quickbooks_sync, name="finance_vendor_invoice_quickbooks_sync"),
    path(
    "maintenance/property-options/",
    views.maintenance_property_options,
    name="maintenance_property_options",
    ),
    path(
    "maintenance/unit-options/",
    views.maintenance_unit_options,
    name="maintenance_unit_options",
    ),
    path(
    "maintenance/lease-options/",
    views.maintenance_lease_options,
    name="maintenance_lease_options",
    ),
    path(
    "maintenance/<int:request_id>/",
    views.maintenance_detail,
    name="maintenance_detail",
    ),
    path("vendors/", views.vendors_list, name="vendors"),
    path(
    "properties/<int:property_id>/",
    views.property_detail,
    name="property_detail",
    ),
    path(
    "work-orders/<int:work_order_id>/",
    views.work_order_detail,
    name="work_order_detail",
    ),
    path(
    "work-orders/<int:work_order_id>/edit/",
    views.edit_work_order,
    name="edit_work_order",
    ),
    path(
    "work-orders/<int:work_order_id>/assign-vendor/",
    views.assign_vendor,
    name="assign_vendor",
    ),
    path(
    "work-orders/<int:work_order_id>/change-vendor/",
    views.change_vendor,
    name="change_vendor",
    ),
    path(
    "work-orders/<int:work_order_id>/awards/<int:award_id>/confirm/",
    views.confirm_vendor,
    name="confirm_vendor",
    ),
    path(
    "work-orders/<int:work_order_id>/awards/<int:award_id>/assign/",
    views.assign_awarded_vendor,
    name="assign_awarded_vendor",
    ),
    path(
    "work-orders/<int:work_order_id>/assignments/<int:assignment_id>/cancel/",
    views.cancel_vendor_assignment,
    name="cancel_vendor_assignment",
    ),
    path(
    "maintenance/<int:request_id>/create-work-order/",
    views.create_work_order,
    name="create_work_order",
    ),
    path(
    "work-orders/<int:work_order_id>/assign-vendor/",
    views.assign_vendor,
    name="assign_vendor",
    ),
    path(
    "work-orders/<int:work_order_id>/assignments/<int:assignment_id>/schedule/",
    views.schedule_vendor,
    name="schedule_vendor",
    ),
    path(
    "work-orders/<int:work_order_id>/start/",
    views.start_work_order,
    name="start_work_order",
    ),
    path(
    "work-orders/<int:work_order_id>/complete/",
    views.complete_work_order,
    name="complete_work_order",
    ),
    path(
    "work-orders/<int:work_order_id>/cancel/",
    views.cancel_work_order,
    name="cancel_work_order",
    ),
    path(
    "finance/vendor-bills/work-orders/<int:work_order_id>/add/",
    views.add_vendor_invoice,
    name="add_vendor_invoice",
    ),
    path(
    "finance/vendor-bills/<int:invoice_id>/edit/",
    views.edit_vendor_invoice,
    name="edit_vendor_invoice",
    ),
    path(
    "maintenance/new/",
    views.create_maintenance_request,
    name="create_maintenance_request",
    ),
    path(
    "maintenance/<int:request_id>/edit/",
    views.edit_maintenance_request,
    name="edit_maintenance_request",
    ),
    path(
    "maintenance/<int:request_id>/triage/",
    views.triage_maintenance_request,
    name="triage_maintenance_request",
    ),
    path(
    "maintenance/<int:request_id>/approve/",
    views.approve_maintenance_request,
    name="approve_maintenance_request",
    ),
    path(
    "maintenance/<int:request_id>/photo/add/",
    views.add_maintenance_photo,
    name="add_maintenance_photo",
    ),
    path(
    "finance/vendor-bills/<int:invoice_id>/approve/",
    views.approve_vendor_invoice,
    name="approve_vendor_invoice",
    ),
    path(
    "finance/vendor-bills/<int:invoice_id>/payments/record/",
    views.record_vendor_payment,
    name="record_vendor_payment",
    ),
    path(
    "finance/payments/<int:payment_id>/void/",
    views.void_vendor_payment,
    name="void_vendor_payment",
    ),
    path(
    "finance/payments/<int:payment_id>/quickbooks/sync/",
    views.finance_vendor_payment_quickbooks_sync,
    name="finance_vendor_payment_quickbooks_sync",
    ),
    path(
    "estimates/<int:estimate_id>/approve/",
    views.approve_vendor_estimate,
    name="approve_vendor_estimate",
    ),
    path(
    "estimates/<int:estimate_id>/reject/",
    views.reject_vendor_estimate,
    name="reject_vendor_estimate",
    ),
    path(
    "work-orders/<int:work_order_id>/quotes/request/",
    views.request_vendor_quotes,
    name="request_vendor_quotes",
    ),
    path(
    "work-orders/<int:work_order_id>/estimate/add/",
    views.add_vendor_estimate,
    name="add_vendor_estimate",
    ),
    path(
    "vendors/new/",
    views.create_vendor,
    name="create_vendor",
    ),

    path(
        "vendors/<int:vendor_id>/",
        views.vendor_detail,
        name="vendor_detail",
    ),

    path(
        "vendors/<int:vendor_id>/edit/",
        views.edit_vendor,
        name="edit_vendor",
    ),
    path(
    "properties/new/",
    views.create_property,
    name="create_property",
    ),

    path(
        "properties/<int:property_id>/edit/",
        views.edit_property,
        name="edit_property",
    ),

    path(
        "properties/<int:property_id>/units/new/",
        views.create_property_unit,
        name="create_property_unit",
    ),

    path(
        "properties/<int:property_id>/units/<int:unit_id>/edit/",
        views.edit_property_unit,
        name="edit_property_unit",
    ),
    path(
    "owners/new/",
    views.create_owner,
    name="create_owner",
    ),

    path(
        "owners/<int:owner_id>/",
        views.owner_detail,
        name="owner_detail",
    ),

    path(
        "owners/<int:owner_id>/edit/",
        views.edit_owner,
        name="edit_owner",
    ),

    path(
        "properties/<int:property_id>/ownership/new/",
        views.create_property_ownership,
        name="create_property_ownership",
    ),

    path(
        "properties/<int:property_id>/ownership/<int:ownership_id>/edit/",
        views.edit_property_ownership,
        name="edit_property_ownership",
    ),

    path(
        "properties/<int:property_id>/ownership/<int:ownership_id>/remove/",
        views.remove_property_ownership,
        name="remove_property_ownership",
    ),
    path(
        "properties/geocode/",
        views.geocode_property_address,
        name="geocode_property_address",
    ),
    path(
    "tenants/new/",
    views.create_tenant,
    name="create_tenant",
    ),

    path(
        "tenants/<int:tenant_id>/",
        views.tenant_detail,
        name="tenant_detail",
    ),

    path(
        "tenants/<int:tenant_id>/edit/",
        views.edit_tenant,
        name="edit_tenant",
    ),

    path(
    "leases/new/",
    views.create_lease,
    name="create_lease",
    ),

    path("leases/<int:lease_id>/pending/", views.mark_lease_pending, name="mark_lease_pending"),
    path("leases/<int:lease_id>/activate/", views.activate_pending_lease, name="activate_pending_lease"),
    path("leases/<int:lease_id>/cancel/", views.cancel_pending_lease, name="cancel_pending_lease"),
    path("leases/<int:lease_id>/delete-draft/", views.delete_draft_lease, name="delete_draft_lease"),
    path("leases/<int:lease_id>/intent/renew/", views.record_renewal_intent, name="record_renewal_intent"),
    path("leases/<int:lease_id>/intent/vacate/", views.record_vacate_intent, name="record_vacate_intent"),
    path("leases/<int:lease_id>/notice/withdraw/", views.withdraw_move_out_notice, name="withdraw_move_out_notice"),
    path("leases/<int:lease_id>/renewal/new/", views.create_lease_renewal, name="create_lease_renewal"),

    path(
        "leases/<int:lease_id>/",
        views.lease_detail,
        name="lease_detail",
    ),

    path(
        "leases/<int:lease_id>/edit/",
        views.edit_lease,
        name="edit_lease",
    ),

    path(
        "leases/<int:lease_id>/tenants/new/",
        views.add_lease_tenant,
        name="add_lease_tenant",
    ),

    path(
        "leases/<int:lease_id>/tenants/<int:membership_id>/edit/",
        views.edit_lease_tenant,
        name="edit_lease_tenant",
    ),

    path(
        "properties/<int:property_id>/units/<int:unit_id>/lease/new/",
        views.create_unit_lease,
        name="create_unit_lease",
    ),

    path(
    "leases/<int:lease_id>/tenants/<int:membership_id>/remove/",
    views.remove_lease_tenant,
    name="remove_lease_tenant",
    ),
]


from leasing import document_views as lease_document_views
urlpatterns += [
    path('leases/<int:lease_id>/documents/add/', lease_document_views.add_document, name='lease_document_add'),
    path('leases/<int:lease_id>/documents/<int:document_id>/', lease_document_views.download_document, name='lease_document_download'),
]

from leasing import agreement_views
urlpatterns += [path('leases/<int:lease_id>/agreements/add/',agreement_views.add_agreement,name='lease_agreement_add')]

from leasing.agreement_pages import agreement_detail
urlpatterns += [path('leases/<int:lease_id>/agreements/<int:agreement_id>/', agreement_detail, name='lease_agreement_detail')]

from leasing.document_actions import delete_document
urlpatterns += [path('leases/<int:lease_id>/documents/<int:document_id>/delete/',delete_document,name='lease_document_delete')]

from accounting import rent_views
urlpatterns += [
    path('leases/<int:lease_id>/rent/',rent_views.rent_ledger,name='rent_ledger'),
    path('leases/<int:lease_id>/rent/<str:kind>/new/',rent_views.rent_entry,name='rent_entry'),
    path('leases/<int:lease_id>/rent/<str:kind>/<int:entry_id>/edit/',rent_views.rent_edit,name='rent_edit'),
    path('leases/<int:lease_id>/rent/<str:kind>/<int:entry_id>/void/',rent_views.rent_void,name='rent_void'),
    path('leases/<int:lease_id>/rent/receipts/<int:receipt_id>/apply/',rent_views.rent_apply_credit,name='rent_apply_credit'),
]
urlpatterns += [path('finance/rent/',rent_views.rent_overview,name='rent_overview')]

from accounting.allocation_editor import rent_allocations
urlpatterns += [path('leases/<int:lease_id>/rent/allocations/', rent_allocations, name='rent_allocations')]

from portal.historical_work import record_work_completion
urlpatterns += [path('work-orders/<int:work_order_id>/record-completion/', record_work_completion, name='record_work_completion')]
