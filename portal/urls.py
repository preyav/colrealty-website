from django.urls import path
from . import views

app_name = "portal"

urlpatterns = [
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
    "work-orders/<int:work_order_id>/invoice/add/",
    views.add_vendor_invoice,
    name="add_vendor_invoice",
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
    "invoices/<int:invoice_id>/approve/",
    views.approve_vendor_invoice,
    name="approve_vendor_invoice",
    ),
    path(
    "invoices/<int:invoice_id>/mark-paid/",
    views.mark_vendor_invoice_paid,
    name="mark_vendor_invoice_paid",
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
