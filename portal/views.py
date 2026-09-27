"""
portal/views.py
───────────────
Custom staff-only admin portal for Col Realty.
Accessible at /portal/ — requires staff login.

Sections:properties_list
  - Dashboard  → live stats overview
  - Leads      → all leads with HubSpot status + retry
  - Listings   → buy listings management
  - Rentals    → rental listings management
"""
import requests
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.core.mail import send_mail, send_mass_mail
from datetime import timedelta

from leads.models import Lead
from listings.models import Listing
from rentals.models import Rental

from properties.models import Property, PropertyUnit
from owners.models import OwnerProfile, PropertyOwnership
from tenants.models import TenantProfile
from leasing.models import Lease, LeaseTenant, LeaseIntentRecord
from common.audit.models import AuditEvent
from common.audit.services import changed_values, record_event, snapshot
from maintenance.models import (
    MaintenancePhoto,
    MaintenanceRequest,
    VendorAssignment,
    VendorAward,
    VendorEstimate,
    VendorQuoteRequest,
    WorkOrder,
    WorkOrderStatusHistory,
)

from .forms import (
    MaintenancePhotoForm,
    MaintenanceRequestCreateForm,
    MaintenanceRequestReviewForm,
    VendorForm,
    VendorTradeForm,
    VendorAssignmentForm,
    ChangeVendorForm,
    CancelVendorAssignmentForm,
    VendorScheduleForm,
    VendorEstimateForm,
    VendorQuoteRequestForm,
    WorkOrderCompleteForm,
    WorkOrderCreateForm,
    WorkOrderCancelForm,
    PropertyForm,
    PropertyUnitForm,
    OwnerProfileForm,
    PropertyOwnershipForm,
    TenantProfileForm,
    LeaseForm,
    ActiveLeaseOperationalForm,
    LeaseTenantForm,
    LeaseRenewalIntentForm,
    LeaseVacateIntentForm,
)
from vendors.models import Vendor, VendorTrade
from financial.services import get_financial_provider, get_work_order_financials
from financial.providers.base import FinancialProviderError, FinancialProviderDisabled



AUDIT_FIELD_LABELS = {
    "status": "Status",
    "move_in_date": "Move-In Date",
    "move_out_date": "Move-Out Date",
    "notes": "Notes",
    "response_date": "Response Date",
    "notice_received_date": "Notice Received Date",
    "planned_move_out_date": "Planned Move-Out Date",
    "notice_method": "Notice Method",
    "monthly_rent": "Monthly Rent",
    "security_deposit": "Security Deposit",
    "start_date": "Start Date",
    "end_date": "End Date",
    "renewal_lease_id": "Renewal Lease",
    "role": "Role",
    "tenant": "Tenant",
    "is_financially_responsible": "Financially Responsible",
    "street_address": "Street Address",
    "unit_number": "Unit",
    "city": "City",
    "state": "State",
    "zip_code": "ZIP Code",
    "county": "County",
    "subdivision": "Subdivision",
    "property_type": "Property Type",
    "property_type_other": "Other Property Type",
    "year_built": "Year Built",
    "bedrooms": "Bedrooms",
    "bathrooms_full": "Full Baths",
    "bathrooms_half": "Half Baths",
    "sqft": "Square Feet",
    "lot_size_sqft": "Lot Size",
    "management_status": "Management Status",
    "is_multi_unit": "Multi-Unit",
    "beds": "Bedrooms",
    "market_rent": "Market Rent",
    "owner": "Owner",
    "ownership_percentage": "Ownership",
    "is_primary_contact": "Primary Contact",
    "title": "Title",
    "description": "Description",
    "priority": "Priority",
    "scheduled_for": "Scheduled For",
    "estimated_cost": "Estimated Cost",
    "actual_cost": "Actual Cost",
    "completed_at": "Completed At",
    "vendor": "Vendor",
    "vendor_notes": "Vendor Notes",
}

AUDIT_ACTION_LABELS = {
    "ACTIVE_LEASE_OPERATIONAL_UPDATED": "Lease information updated",
    "LEASE_MARKED_PENDING_SIGNATURE": "Lease marked Pending Signature",
    "LEASE_ACTIVATED": "Lease activated",
    "LEASE_CANCELLED": "Lease cancelled",
    "MOVE_OUT_NOTICE_RECORDED": "Move-out notice recorded",
    "MOVE_OUT_NOTICE_WITHDRAWN": "Move-out notice withdrawn",
    "RENEWAL_INTENT_RECORDED": "Renewal intent recorded",
    "LEASE_RENEWAL_DRAFT_CREATED": "Renewal draft created",
    "LEASE_TENANT_ADDED": "Tenant added",
    "LEASE_TENANT_UPDATED": "Tenant updated",
    "LEASE_TENANT_REMOVED": "Tenant removed",
    "PROPERTY_CREATED": "Property created",
    "PROPERTY_UPDATED": "Property updated",
    "PROPERTY_UNIT_ADDED": "Unit added",
    "PROPERTY_UNIT_UPDATED": "Unit updated",
    "PROPERTY_OWNERSHIP_ADDED": "Owner added to property",
    "PROPERTY_OWNERSHIP_UPDATED": "Ownership updated",
    "PROPERTY_OWNERSHIP_REMOVED": "Owner removed from property",
    "MAINTENANCE_REQUEST_CREATED": "Maintenance request created",
    "MAINTENANCE_REQUEST_UPDATED": "Maintenance request updated",
    "MAINTENANCE_REQUEST_TRIAGED": "Maintenance request triaged",
    "MAINTENANCE_REQUEST_APPROVED": "Maintenance request approved",
    "WORK_ORDER_CREATED": "Work order created",
    "WORK_ORDER_UPDATED": "Work order updated",
    "VENDOR_ASSIGNED": "Vendor assigned",
    "VENDOR_SCHEDULED": "Vendor scheduled",
    "WORK_ORDER_STARTED": "Work order started",
    "WORK_ORDER_COMPLETED": "Work order completed",
    "WORK_ORDER_CANCELLED": "Work order cancelled",
    "VENDOR_ESTIMATE_ADDED": "Vendor estimate added",
    "VENDOR_ESTIMATE_APPROVED": "Vendor estimate approved",
    "VENDOR_ESTIMATE_REJECTED": "Vendor estimate rejected",
}

AUDIT_VALUE_LABELS = {
    "active": "Active",
    "cancelled": "Cancelled",
    "co_tenant": "Co-Tenant",
    "draft": "Draft",
    "email": "Email",
    "expired": "Expired",
    "notice": "Notice Given",
    "occupant": "Occupant",
    "pending": "Pending Signature",
    "phone": "Phone",
    "primary": "Primary Tenant",
    "terminated": "Terminated",
    "text": "Text",
    "prospect": "Prospect",
    "onboarding": "Onboarding",
    "inactive": "Inactive",
    "single_family_residential": "Single Family Residential",
    "condominium": "Condominium",
    "manufactured_home": "Manufactured Home",
    "mobile_home": "Mobile Home",
    "modular": "Modular",
    "townhouse": "Townhouse",
    "other": "Other",
    "vacant": "Vacant",
    "occupied": "Occupied",
    "maintenance": "Maintenance",
    "new": "New",
    "triaged": "Triaged",
    "approved": "Approved",
    "converted": "Converted to Work Order",
    "assigned": "Assigned",
    "scheduled": "Scheduled",
    "in_progress": "In Progress",
    "completed": "Completed",
    "cancelled": "Cancelled",
    "low": "Low",
    "normal": "Normal",
    "high": "High",
    "urgent": "Urgent",
}

AUDIT_HIDDEN_FIELDS = {"tenant_id"}

# These reasons are useful to the immutable ledger, but add little value to the
# day-to-day business timeline. They remain stored on AuditEvent.
AUDIT_ROUTINE_REASONS = {
    "Work order details updated in COL360.",
    "Work order completed in COL360.",
    "Work order started in COL360.",
    "Vendor visit scheduled in COL360.",
    "Vendor assigned to work order in COL360.",
    "Work order created from approved maintenance request.",
    "Maintenance request approved in COL360.",
    "Maintenance request triaged in COL360.",
    "Maintenance request created in COL360.",
    "Tenant membership added from Lease 360.",
    "Tenant membership updated from Lease 360.",
    "Tenant membership removed from Lease 360.",
    "Tenant renewal intent recorded by staff.",
    "Tenant move-out notice recorded by staff.",
    "Tenant move-out notice withdrawn by staff.",
    "Executed Pending Signature lease activated by staff.",
}


def _audit_display_value(value):
    if value is None or value == "":
        return "—"
    if value is True:
        return "Yes"
    if value is False:
        return "No"

    text = str(value)

    # Human-friendly enum / workflow values.
    if text in AUDIT_VALUE_LABELS:
        return AUDIT_VALUE_LABELS[text]

    # Human-friendly ISO dates without changing the underlying audit data.
    try:
        if len(text) == 10 and text[4] == "-" and text[7] == "-":
            parsed = timezone.datetime.strptime(text, "%Y-%m-%d").date()
            return parsed.strftime("%b %d, %Y")
    except (TypeError, ValueError):
        pass

    return text


def _format_audit_display_value(field_name, value):
    """Presentation-only formatting; AuditEvent JSON/hash remain unchanged."""
    if value in (None, ""):
        return "—"
    if field_name in {"estimated_cost", "actual_cost", "amount"}:
        try:
            return f"${float(value):,.2f}"
        except (TypeError, ValueError):
            return value
    if field_name in {"scheduled_for", "completed_at"} and isinstance(value, str):
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timezone.is_aware(dt):
                dt = timezone.localtime(dt)
            # Portable 12-hour format without platform-specific %-I.
            hour = dt.strftime("%I").lstrip("0") or "12"
            return f"{dt.strftime('%b %d, %Y')} · {hour}:{dt.strftime('%M %p')}"
        except (TypeError, ValueError):
            return value
    return value


def _prepare_audit_events(events):
    prepared = []

    for event in events:
        old_values = event.old_values or {}
        new_values = event.new_values or {}
        keys = sorted(set(old_values.keys()) | set(new_values.keys()))

        event.display_action = AUDIT_ACTION_LABELS.get(
            event.action,
            event.action.replace("_", " ").title(),
        )

        # Renewal uses a response method; move-out uses a notice method.
        field_labels = dict(AUDIT_FIELD_LABELS)
        if event.action == "RENEWAL_INTENT_RECORDED":
            field_labels["notice_method"] = "Response Method"

        display_changes = []
        for key in keys:
            if key in AUDIT_HIDDEN_FIELDS:
                continue

            previous_raw = old_values.get(key)
            new_raw = new_values.get(key)

            # Business-friendly ownership display. AuditEvent JSON remains
            # untouched; only the Property 360 presentation is enriched.
            if key == "owner" and event.entity_type == "PropertyOwnership":
                owner_ids = {
                    value for value in (previous_raw, new_raw)
                    if value not in (None, "")
                }
                owner_names = {
                    str(owner.pk): str(owner)
                    for owner in OwnerProfile.objects.filter(pk__in=owner_ids)
                }
                previous = (
                    owner_names.get(str(previous_raw), str(previous_raw))
                    if previous_raw not in (None, "") else "—"
                )
                new = (
                    owner_names.get(str(new_raw), str(new_raw))
                    if new_raw not in (None, "") else "—"
                )
            elif key == "ownership_percentage":
                def _ownership_percent(value):
                    if value in (None, ""):
                        return "—"
                    try:
                        number = float(value)
                        formatted = (
                            str(int(number))
                            if number.is_integer()
                            else f"{number:.2f}".rstrip("0").rstrip(".")
                        )
                        return f"{formatted}%"
                    except (TypeError, ValueError):
                        return f"{value}%"

                previous = _ownership_percent(previous_raw)
                new = _ownership_percent(new_raw)
            else:
                previous = _format_audit_display_value(
                    key,
                    _audit_display_value(previous_raw),
                )
                new = _format_audit_display_value(
                    key,
                    _audit_display_value(new_raw),
                )

            # The audit service should already avoid no-op fields, but keeping
            # this guard makes the presentation layer intentionally quiet.
            if previous == new:
                continue

            if previous == "—":
                summary = new
                change_kind = "added"
            elif new == "—":
                summary = previous
                change_kind = "removed"
            else:
                summary = f"{previous} → {new}"
                change_kind = "changed"

            display_changes.append({
                "label": field_labels.get(
                    key, key.replace("_", " ").title()
                ),
                "previous": previous,
                "new": new,
                "summary": summary,
                "change_kind": change_kind,
            })

        event.display_changes = display_changes
        event.display_reason = (
            event.reason
            if event.reason and event.reason not in AUDIT_ROUTINE_REASONS
            else ""
        )
        prepared.append(event)

    return prepared


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

@staff_member_required(login_url="/admin/login/")
def dashboard(request):
    now   = timezone.now()
    today = now.date()
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Listing stats ──────────────────────────────────────────────────────
    listing_stats = {
        "total_active":  Listing.objects.filter(status="active").count(),
        "total_pending": Listing.objects.filter(status="pending").count(),
        "total_sold":    Listing.objects.filter(status="sold").count(),
        "featured":      Listing.objects.filter(is_featured=True).count(),
    }

    # ── Rental stats ───────────────────────────────────────────────────────
    rental_stats = {
        "total_active": Rental.objects.filter(status="active").count(),
        "total_leased": Rental.objects.filter(status="leased").count(),
    }

        # ── Property Management stats ────────────────────────────────────────
    property_stats = {
        "total": Property.objects.count(),
        "active": Property.objects.filter(
            management_status="active"
        ).count(),
        "onboarding": Property.objects.filter(
            management_status="onboarding"
        ).count(),
    }

    unit_stats = {
        "total": PropertyUnit.objects.count(),
        "occupied": PropertyUnit.objects.filter(
            status="occupied"
        ).count(),
        "vacant": PropertyUnit.objects.filter(
            status="vacant"
        ).count(),
    }

    if unit_stats["total"]:
        unit_stats["occupancy_rate"] = round(
            (unit_stats["occupied"] / unit_stats["total"]) * 100,
            1,
        )
    else:
        unit_stats["occupancy_rate"] = 0

    lease_stats = {
        "active": Lease.objects.filter(
            status="active"
        ).count(),
        "notice": Lease.objects.filter(
            status="notice"
        ).count(),
        "expiring_90_days": Lease.objects.filter(
            status="active",
            end_date__gte=today,
            end_date__lte=today + timedelta(days=90),
        ).count(),
    }

    maintenance_stats = {
        "open": MaintenanceRequest.objects.exclude(
            status__in=["completed", "cancelled"]
        ).count(),

        "new": MaintenanceRequest.objects.filter(
            status="new"
        ).count(),

        "high_priority": MaintenanceRequest.objects.filter(
            priority="high"
        ).exclude(
            status__in=["completed", "cancelled"]
        ).count(),

        "emergency": MaintenanceRequest.objects.filter(
            priority="emergency"
        ).exclude(
            status__in=["completed", "cancelled"]
        ).count(),
    }

    work_order_stats = {
        "open": WorkOrder.objects.exclude(
            status__in=["completed", "cancelled"]
        ).count(),

        "scheduled": WorkOrder.objects.filter(
            status="scheduled"
        ).count(),

        "in_progress": WorkOrder.objects.filter(
            status="in_progress"
        ).count(),
    }

    people_stats = {
        "owners": OwnerProfile.objects.filter(
            is_active=True
        ).count(),

        "tenants": TenantProfile.objects.filter(
            is_active=True
        ).count(),

        "vendors": Vendor.objects.filter(
            status="active"
        ).count(),
    }

    active_monthly_rent = (
        Lease.objects.filter(status="active")
        .aggregate(total=Sum("monthly_rent"))
        .get("total")
        or 0
    )

    recent_maintenance = (
        MaintenanceRequest.objects
        .select_related(
            "unit__property",
            "reported_by_tenant",
        )
        .order_by("-submitted_at")[:8]
    )

    # ── Lead stats ─────────────────────────────────────────────────────────
    lead_stats = {
        "total":           Lead.objects.count(),
        "today":           Lead.objects.filter(created_at__date=today).count(),
        "this_week":       Lead.objects.filter(created_at__gte=week_ago).count(),
        "this_month":      Lead.objects.filter(created_at__gte=month_ago).count(),
        "hubspot_synced":  Lead.objects.filter(hubspot_sent=True).count(),
        "hubspot_pending": Lead.objects.filter(hubspot_sent=False).count(),
        "has_errors":      Lead.objects.exclude(error="").count(),
    }

    # ── Recent leads ───────────────────────────────────────────────────────
    recent_leads = Lead.objects.order_by("-created_at")[:10]

    # ── Failed leads (need attention) ─────────────────────────────────────
    failed_leads = Lead.objects.filter(
        hubspot_sent=False
    ).exclude(error="").order_by("-created_at")[:5]

    return render(request, "portal/dashboard.html", {
        "listing_stats": listing_stats,
        "rental_stats":  rental_stats,
        "lead_stats":    lead_stats,
        "recent_leads":  recent_leads,
        "failed_leads":  failed_leads,

        "property_stats": property_stats,
        "unit_stats": unit_stats,
        "lease_stats": lease_stats,
        "maintenance_stats": maintenance_stats,
        "work_order_stats": work_order_stats,
        "people_stats": people_stats,
        "active_monthly_rent": active_monthly_rent,
        "recent_maintenance": recent_maintenance,

        "section": "dashboard",
    })


# ─────────────────────────────────────────────
# Leads
# ─────────────────────────────────────────────

@staff_member_required(login_url="/admin/login/")
def leads_list(request):
    qs = Lead.objects.order_by("-created_at")

    # Filters
    source_filter   = request.GET.get("source", "")
    synced_filter   = request.GET.get("synced", "")
    search          = request.GET.get("q", "").strip()

    if source_filter in {"listing", "rental"}:
        qs = qs.filter(source_type=source_filter)
    if synced_filter == "yes":
        qs = qs.filter(hubspot_sent=True)
    elif synced_filter == "no":
        qs = qs.filter(hubspot_sent=False)
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    return render(request, "portal/leads.html", {
        "leads":          qs,
        "source_filter":  source_filter,
        "synced_filter":  synced_filter,
        "search":         search,
        "total":          qs.count(),
        "section":        "leads",
    })


@staff_member_required(login_url="/admin/login/")
def lead_retry_hubspot(request, lead_id):
    """Retry HubSpot sync for a single lead."""
    lead = get_object_or_404(Lead, pk=lead_id)
    if lead.hubspot_sent:
        messages.info(request, f"Lead #{lead_id} already synced to HubSpot.")
    else:
        from leads.tasks import sync_lead_to_hubspot
        sync_lead_to_hubspot.apply_async(args=[lead.id], queue="hubspot")
        messages.success(request, f"Lead #{lead_id} queued for HubSpot sync.")
    return redirect("portal:leads")


@staff_member_required(login_url="/admin/login/")
def leads_retry_all(request):
    """Retry HubSpot sync for ALL unsynced leads."""
    from leads.tasks import sync_lead_to_hubspot
    unsynced = Lead.objects.filter(hubspot_sent=False)
    count = unsynced.count()
    for lead in unsynced:
        sync_lead_to_hubspot.apply_async(args=[lead.id], queue="hubspot")
    messages.success(request, f"{count} lead(s) queued for HubSpot sync.")
    return redirect("portal:leads")


# ─────────────────────────────────────────────
# Listings
# ─────────────────────────────────────────────

@staff_member_required(login_url="/admin/login/")
def listings_list(request):
    qs = Listing.objects.order_by("-updated_at")

    status_filter = request.GET.get("status", "")
    search        = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(city__icontains=search) |
            Q(street_address__icontains=search) |
            Q(mls_id__icontains=search)
        )

    return render(request, "portal/listings.html", {
        "listings":      qs[:100],
        "status_filter": status_filter,
        "search":        search,
        "total":         qs.count(),
        "section":       "listings",
    })


@staff_member_required(login_url="/admin/login/")
def toggle_featured(request, listing_id):
    """Toggle featured status for a listing."""
    listing = get_object_or_404(Listing, pk=listing_id)
    listing.is_featured = not listing.is_featured
    listing.save(update_fields=["is_featured"])
    status = "featured" if listing.is_featured else "unfeatured"
    messages.success(request, f"'{listing.title}' is now {status}.")
    return redirect("portal:listings")


# ─────────────────────────────────────────────
# Rentals
# ─────────────────────────────────────────────

@staff_member_required(login_url="/admin/login/")
def rentals_list(request):
    qs = Rental.objects.order_by("-updated_at")

    status_filter = request.GET.get("status", "")
    search        = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(city__icontains=search) |
            Q(street_address__icontains=search)
        )

    return render(request, "portal/rentals.html", {
        "rentals":       qs[:100],
        "status_filter": status_filter,
        "search":        search,
        "total":         qs.count(),
        "section":       "rentals",
    })

# ─────────────────────────────────────────────────────────────────────────────
# Property Management
# ─────────────────────────────────────────────────────────────────────────────

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET"])
def geocode_property_address(request):
    street_address = request.GET.get("street_address", "").strip()
    city = request.GET.get("city", "").strip()
    state = request.GET.get("state", "").strip()
    zip_code = request.GET.get("zip_code", "").strip()

    if not street_address or not city or not state or not zip_code:
        return JsonResponse(
            {
                "success": False,
                "error": "Street address, city, state, and ZIP code are required.",
            },
            status=400,
        )

    full_address = ", ".join(
        [street_address, city, state, zip_code]
    )

    api_key = settings.GOOGLE_MAPS_API_KEY

    if not api_key:
        return JsonResponse(
            {
                "success": False,
                "error": "Google Maps API key is not configured.",
            },
            status=500,
        )

    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params={
                "address": full_address,
                "key": api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

    except requests.RequestException:
        return JsonResponse(
            {
                "success": False,
                "error": "Unable to contact the geocoding service.",
            },
            status=502,
        )

    if data.get("status") != "OK" or not data.get("results"):
        return JsonResponse(
            {
                "success": False,
                "error": "Google geocoding failed.",
                "google_status": data.get("status"),
                "google_error": data.get("error_message", ""),
            },
            status=400,
        )

    result = data["results"][0]
    location = result["geometry"]["location"]

    return JsonResponse(
        {
            "success": True,
            "latitude": location["lat"],
            "longitude": location["lng"],
            "formatted_address": result["formatted_address"],
        }
    )


@staff_member_required(login_url="/admin/login/")
def properties_list(request):
    qs = Property.objects.prefetch_related(
        "units", "ownerships__owner"
    ).order_by("street_address")

    status_filter = request.GET.get("status", "")
    search = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(management_status=status_filter)

    if search:
        qs = qs.filter(
            Q(street_address__icontains=search) |
            Q(city__icontains=search) |
            Q(zip_code__icontains=search) |
            Q(county__icontains=search)
        )

    return render(request, "portal/properties.html", {
        "properties": qs[:100],
        "status_filter": status_filter,
        "search": search,
        "total": qs.count(),
        "section": "properties",
    })

@staff_member_required(login_url="/admin/login/")
def property_detail(request, property_id):
    property_obj = get_object_or_404(
        Property.objects.prefetch_related(
            "units__leases__lease_tenants__tenant",
            "ownerships__owner",
            "units__maintenance_requests__reported_by_tenant",
            "units__work_orders__vendor_assignments__vendor",
            "units__work_orders__vendor_estimates__vendor",
            "units__work_orders__vendor_invoices__vendor",
        ),
        pk=property_id,
    )

    units = property_obj.units.all()

    today = timezone.localdate()

    # Current occupancy is derived only from an Active lease whose
    # lease period includes today. Historical primary tenants therefore
    # cannot be mistaken for the property's current tenant.
    current_leases = (
        Lease.objects
        .filter(
            unit__property=property_obj,
            status="active",
            start_date__lte=today,
            end_date__gte=today,
        )
        .select_related("unit")
        .prefetch_related("lease_tenants__tenant")
        .order_by("start_date")
    )

    # Future Draft/Pending leases are planning records, not current
    # occupancy. Keep them visually separate on Property 360.
    upcoming_leases = (
        Lease.objects
        .filter(
            unit__property=property_obj,
            status__in=["draft", "pending"],
            start_date__gt=today,
        )
        .select_related("unit")
        .prefetch_related("lease_tenants__tenant")
        .order_by("start_date")
    )

    # Property 360 exposes real rentable units only for properties that
    # staff has explicitly marked as Multi-Unit. Occupancy is derived from
    # leases rather than PropertyUnit.status so Lease remains the source of truth.
    current_by_unit = {lease.unit_id: lease for lease in current_leases}
    upcoming_by_unit = {lease.unit_id: lease for lease in upcoming_leases}

    unit_rows = []
    if property_obj.is_multi_unit:
        for unit in units:
            unit_rows.append({
                "unit": unit,
                "current_lease": current_by_unit.get(unit.id),
                "upcoming_lease": upcoming_by_unit.get(unit.id),
            })

    maintenance_requests = (
        MaintenanceRequest.objects
        .filter(unit__property=property_obj)
        .select_related(
            "unit",
            "reported_by_tenant",
        )
        .order_by("-submitted_at")
    )

    work_orders = (
        WorkOrder.objects
        .filter(unit__property=property_obj)
        .select_related(
            "unit",
            "maintenance_request",
        )
        .prefetch_related(
            "vendor_assignments__vendor",
            "vendor_estimates__vendor",
            "vendor_invoices__vendor",
        )
        .order_by("-created_at")
    )

    open_maintenance_count = maintenance_requests.exclude(
        status__in=["completed", "cancelled"]
    ).count()

    open_work_order_count = work_orders.exclude(
        status__in=["completed", "cancelled"]
    ).count()

    # Property 360 shows only Property / PropertyUnit business events.
    # Lease events remain on Lease 360 even though they share property_id.
    audit_events = _prepare_audit_events(
        AuditEvent.objects.filter(
            property_id=property_obj.id,
            entity_type__in=[
                "Property", "PropertyUnit", "PropertyOwnership",
                "MaintenanceRequest", "WorkOrder", "VendorAssignment",
            ],
        ).select_related("actor")[:25]
    )

    return render(
        request,
        "portal/property_detail.html",
        {
            "property": property_obj,
            "units": units,
            "unit_rows": unit_rows,
            "current_leases": current_leases,
            "upcoming_leases": upcoming_leases,
            "maintenance_requests": maintenance_requests[:20],
            "work_orders": work_orders[:20],
            "open_maintenance_count": open_maintenance_count,
            "open_work_order_count": open_work_order_count,
            "audit_events": audit_events,
            "section": "properties",
        },
    )

@staff_member_required(login_url="/admin/login/")
def owners_list(request):
    qs = OwnerProfile.objects.prefetch_related(
        "property_ownerships__property"
    ).order_by("last_name", "first_name", "entity_name")

    search = request.GET.get("q", "").strip()

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(entity_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    return render(request, "portal/owners.html", {
        "owners": qs[:100],
        "search": search,
        "total": qs.count(),
        "section": "owners",
    })


@staff_member_required(login_url="/admin/login/")
def tenants_list(request):
    qs = TenantProfile.objects.prefetch_related(
        "lease_memberships__lease__unit__property"
    ).order_by("last_name", "first_name")

    search = request.GET.get("q", "").strip()

    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    return render(request, "portal/tenants.html", {
        "tenants": qs[:100],
        "search": search,
        "total": qs.count(),
        "section": "tenants",
    })


@staff_member_required(login_url="/admin/login/")
def leases_list(request):
    qs = Lease.objects.select_related(
        "unit__property"
    ).prefetch_related(
        "lease_tenants__tenant"
    ).order_by("-start_date")

    status_filter = request.GET.get("status", "")
    search = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if search:
        qs = qs.filter(
            Q(unit__property__street_address__icontains=search) |
            Q(unit__property__city__icontains=search) |
            Q(lease_tenants__tenant__first_name__icontains=search) |
            Q(lease_tenants__tenant__last_name__icontains=search)
        ).distinct()

    return render(request, "portal/leases.html", {
        "leases": qs[:100],
        "status_filter": status_filter,
        "search": search,
        "total": qs.count(),
        "section": "leases",
    })


@staff_member_required(login_url="/admin/login/")
def maintenance_list(request):
    qs = MaintenanceRequest.objects.select_related(
        "unit__property",
        "reported_by_tenant",
    ).order_by("-submitted_at")

    status_filter = request.GET.get("status", "")
    priority_filter = request.GET.get("priority", "")
    search = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(unit__property__street_address__icontains=search)
        )

    return render(request, "portal/maintenance.html", {
        "requests": qs[:100],
        "status_filter": status_filter,
        "priority_filter": priority_filter,
        "search": search,
        "total": qs.count(),
        "section": "maintenance",
    })


@staff_member_required(login_url="/admin/login/")
def work_orders_list(request):
    active_assignments = VendorAssignment.objects.exclude(
        status__in=["declined", "cancelled"],
    ).select_related("vendor").order_by("-assigned_at")

    qs = WorkOrder.objects.select_related(
        "unit__property",
    ).prefetch_related(
        Prefetch(
            "vendor_assignments",
            queryset=active_assignments,
            to_attr="current_vendor_assignments",
        ),
    ).order_by("-created_at", "-id")

    status_filter = request.GET.get("status", "")
    property_filter = request.GET.get("property", "")
    queue_filter = request.GET.get("queue", "")
    search = request.GET.get("q", "").strip()

    valid_statuses = {value for value, _label in WorkOrder.STATUS_CHOICES}
    if status_filter in valid_statuses:
        qs = qs.filter(status=status_filter)
    else:
        status_filter = ""

    if property_filter.isdigit():
        qs = qs.filter(unit__property_id=property_filter)
    else:
        property_filter = ""

    if queue_filter == "open":
        qs = qs.exclude(status__in=["completed", "cancelled"])
    elif queue_filter == "unassigned":
        qs = qs.exclude(status__in=["completed", "cancelled"]).exclude(
            vendor_assignments__status__in=[
                "assigned", "accepted", "scheduled", "completed",
            ],
        )
    elif queue_filter == "scheduled":
        qs = qs.filter(status="scheduled")
    elif queue_filter == "in_progress":
        qs = qs.filter(status="in_progress")
    elif queue_filter == "completed":
        qs = qs.filter(status="completed")
    else:
        queue_filter = ""

    if search:
        search_filter = (
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(unit__property__street_address__icontains=search)
            | Q(unit__unit_number__icontains=search)
            | Q(vendor_assignments__vendor__name__icontains=search)
            | Q(vendor_assignments__vendor__company_name__icontains=search)
        )
        if search.isdigit():
            search_filter |= Q(pk=int(search))
        qs = qs.filter(search_filter)

    qs = qs.distinct()
    total = qs.count()
    properties = Property.objects.filter(
        units__work_orders__isnull=False,
    ).distinct().order_by("street_address")

    return render(request, "portal/work_orders.html", {
        "work_orders": qs[:100],
        "properties": properties,
        "queue_choices": [
            ("open", "Open"),
            ("unassigned", "Unassigned"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
        ],
        "status_choices": WorkOrder.STATUS_CHOICES,
        "status_filter": status_filter,
        "property_filter": property_filter,
        "queue_filter": queue_filter,
        "search": search,
        "total": total,
        "section": "maintenance",
        "maintenance_subsection": "work_orders",
    })

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_maintenance_request(request):

    # -----------------------------------------------------
    # Optional context supplied by Lease 360 / Tenant 360
    # -----------------------------------------------------

    unit_id = request.GET.get("unit_id")
    lease_id = request.GET.get("lease_id")
    tenant_id = request.GET.get("tenant_id")

    context_unit = None
    context_lease = None
    context_tenant = None

    # -----------------------------------------------------
    # Resolve Lease context first.
    #
    # A lease already tells us its unit.
    # -----------------------------------------------------

    if lease_id:
        context_lease = get_object_or_404(
            Lease.objects.select_related(
                "unit__property"
            ),
            pk=lease_id,
            status__in=["active", "notice"],
        )

        context_unit = context_lease.unit

    # -----------------------------------------------------
    # Resolve explicit Unit context.
    #
    # If both lease and unit were supplied,
    # they must match.
    # -----------------------------------------------------

    if unit_id:
        requested_unit = get_object_or_404(
            PropertyUnit.objects.select_related(
                "property"
            ),
            pk=unit_id,
        )

        if (
            context_unit
            and requested_unit.id != context_unit.id
        ):
            messages.error(
                request,
                (
                    "The selected lease does not "
                    "belong to the requested unit."
                ),
            )

            return redirect(
                "portal:maintenance"
            )

        context_unit = requested_unit

    # -----------------------------------------------------
    # Resolve Tenant context.
    # -----------------------------------------------------

    if tenant_id:
        context_tenant = get_object_or_404(
            TenantProfile,
            pk=tenant_id,
            is_active=True,
        )

        # If a lease is already known, tenant must
        # actually belong to that lease.
        if context_lease:
            tenant_on_lease = (
                LeaseTenant.objects
                .filter(
                    lease=context_lease,
                    tenant=context_tenant,
                )
                .exists()
            )

            if not tenant_on_lease:
                messages.error(
                    request,
                    (
                        "This tenant is not associated "
                        "with the selected lease."
                    ),
                )

                return redirect(
                    "portal:tenant_detail",
                    tenant_id=context_tenant.id,
                )

        # If only the tenant was supplied, determine
        # their current lease automatically.
        else:
            current_memberships = (
                LeaseTenant.objects
                .filter(
                    tenant=context_tenant,
                    lease__status__in=["active", "notice"],
                )
                .select_related(
                    "lease__unit__property"
                )
            )

            membership_count = (
                current_memberships.count()
            )

            if membership_count == 1:
                membership = (
                    current_memberships.first()
                )

                context_lease = membership.lease
                context_unit = (
                    membership.lease.unit
                )

            elif membership_count == 0:
                messages.error(
                    request,
                    (
                        "This tenant does not currently "
                        "have an active lease."
                    ),
                )

                return redirect(
                    "portal:tenant_detail",
                    tenant_id=context_tenant.id,
                )

            else:
                messages.error(
                    request,
                    (
                        "This tenant is associated with "
                        "more than one active lease. "
                        "Please resolve the lease records "
                        "before creating maintenance."
                    ),
                )

                return redirect(
                    "portal:tenant_detail",
                    tenant_id=context_tenant.id,
                )

    # -----------------------------------------------------
    # Build the form
    # -----------------------------------------------------

    form = MaintenanceRequestCreateForm(
        request.POST or None,
        context_unit=context_unit,
        context_lease=context_lease,
        context_tenant=context_tenant,
    )

    # -----------------------------------------------------
    # Save
    # -----------------------------------------------------

    if form.is_valid():
        maintenance_request = form.save(
            commit=False
        )

        # Never trust manipulated POST values when
        # this page was launched with known context.

        if context_unit:
            maintenance_request.unit = (
                context_unit
            )

        if context_lease:
            maintenance_request.lease = (
                context_lease
            )

        if context_tenant:
            maintenance_request.reported_by_tenant = (
                context_tenant
            )

        maintenance_request.status = "new"

        maintenance_request.reported_by_user = (
            request.user
        )

        with transaction.atomic():
            maintenance_request.save()
            record_event(
                action="MAINTENANCE_REQUEST_CREATED",
                instance=maintenance_request,
                actor=request.user,
                request=request,
                old_values={},
                new_values=snapshot(
                    maintenance_request,
                    ["title", "description", "priority", "status"],
                ),
                reason="Maintenance request created in COL360.",
                property_id=maintenance_request.unit.property_id,
            )

        messages.success(
            request,
            (
                f"Maintenance Request "
                f"#{maintenance_request.id} "
                "was created."
            ),
        )

        return redirect(
            "portal:maintenance_detail",
            request_id=maintenance_request.id,
        )

    # -----------------------------------------------------
    # Render
    # -----------------------------------------------------

    return render(
        request,
        "portal/create_maintenance_request.html",
        {
            "form": form,
            "context_unit": context_unit,
            "context_lease": context_lease,
            "context_tenant": context_tenant,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
def vendors_list(request):
    qs = Vendor.objects.prefetch_related(
        "trades"
    ).order_by("company_name", "name")

    status_filter = request.GET.get("status", "")
    search = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)

    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(company_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )

    return render(request, "portal/vendors.html", {
        "vendors": qs[:100],
        "status_filter": status_filter,
        "search": search,
        "total": qs.count(),
        "section": "vendors",
    })

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_maintenance_request(request, request_id):
    maintenance_request = get_object_or_404(
        MaintenanceRequest.objects.select_related(
            "unit__property",
            "lease",
            "reported_by_tenant",
        ),
        pk=request_id,
    )

    # Workflow status is deliberately not editable here. Status changes must
    # go through Review & Approve / Work Order actions so the audit trail
    # cannot be bypassed by a generic edit form.
    tracked_fields = [
        "title",
        "description",
        "category",
        "priority",
        "permission_to_enter",
        "availability_date",
        "availability_start_time",
        "availability_end_time",
    ]
    before = snapshot(maintenance_request, tracked_fields)

    form = MaintenanceRequestCreateForm(
        request.POST or None,
        instance=maintenance_request,
        context_unit=maintenance_request.unit,
        context_lease=maintenance_request.lease,
        context_tenant=maintenance_request.reported_by_tenant,
    )
    form.fields.pop("status", None)

    if request.method == "POST" and form.is_valid():
        candidate = form.save(commit=False)

        # Preserve workflow/context fields. They are controlled elsewhere.
        candidate.unit = maintenance_request.unit
        candidate.lease = maintenance_request.lease
        candidate.reported_by_tenant = maintenance_request.reported_by_tenant
        candidate.reported_by_user = maintenance_request.reported_by_user
        candidate.status = maintenance_request.status

        after = snapshot(candidate, tracked_fields)
        old_values, new_values = changed_values(before, after)

        if not new_values:
            messages.info(request, "No maintenance information changed.")
            return redirect(
                "portal:maintenance_detail",
                request_id=maintenance_request.id,
            )

        with transaction.atomic():
            candidate.save()
            record_event(
                action="MAINTENANCE_REQUEST_UPDATED",
                instance=candidate,
                actor=request.user,
                request=request,
                old_values=old_values,
                new_values=new_values,
                reason="Maintenance request details updated in COL360.",
                property_id=candidate.unit.property_id,
            )

        messages.success(
            request,
            f"Maintenance Request #{candidate.id} was updated.",
        )
        return redirect(
            "portal:maintenance_detail",
            request_id=candidate.id,
        )

    return render(
        request,
        "portal/edit_maintenance_request.html",
        {
            "form": form,
            "maintenance_request": maintenance_request,
            "section": "maintenance",
        },
    )


@staff_member_required(login_url="/admin/login/")
def maintenance_detail(request, request_id):
    maintenance_request = get_object_or_404(
        MaintenanceRequest.objects.select_related(
            "unit__property",
            "lease",
            "reported_by_tenant",
            "reported_by_user",
        ).prefetch_related(
            "photos",
        ),
        pk=request_id,
    )

    # Keep cancelled work orders as history while exposing only the current
    # non-cancelled work order as the active operational record.
    work_orders = (
        WorkOrder.objects
        .filter(maintenance_request=maintenance_request)
        .select_related(
            "unit__property",
            "approved_by",
        )
        .prefetch_related(
            "vendor_assignments__vendor",
            "vendor_estimates__vendor",
            "vendor_invoices__vendor",
            "status_history__changed_by",
        )
        .order_by("-created_at")
    )
    work_order = work_orders.exclude(status="cancelled").first()
    work_order_history = list(work_orders)

    property_history = (
        MaintenanceRequest.objects
        .filter(unit__property_id=maintenance_request.unit.property_id)
        .exclude(pk=maintenance_request.pk)
        .select_related("unit")
        .prefetch_related("work_orders")
        .order_by("-submitted_at")[:10]
    )

    review_form = None
    reviewable_statuses = {
        "new", "triaged", "under_review", "pending_information",
    }
    if not work_order and maintenance_request.status in reviewable_statuses:
        due_offsets = {
            "emergency": timedelta(hours=1),
            "high": timedelta(hours=8),
            "normal": timedelta(days=2),
            "low": timedelta(days=5),
        }
        initial = {"decision": "approved"}
        if not maintenance_request.review_due_at:
            initial["review_due_at"] = (
                timezone.now() + due_offsets[maintenance_request.priority]
            )
        review_form = MaintenanceRequestReviewForm(
            instance=maintenance_request,
            initial=initial,
        )

    return render(
        request,
        "portal/maintenance_detail.html",
        {
            "maintenance_request": maintenance_request,
            "work_order": work_order,
            "work_order_history": work_order_history,
            "review_form": review_form,
            "property_history": property_history,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_POST
def triage_maintenance_request(request, request_id):
    maintenance_request = get_object_or_404(
        MaintenanceRequest,
        pk=request_id,
    )

    if maintenance_request.status != "new":
        messages.error(
            request,
            "Only a new maintenance request can be marked as triaged."
        )
        return redirect(
            "portal:maintenance_detail",
            request_id=maintenance_request.id,
        )

    with transaction.atomic():
        previous_status = maintenance_request.status
        maintenance_request.status = "triaged"
        maintenance_request.save(
            update_fields=["status", "updated_at"]
        )
        record_event(
            action="MAINTENANCE_REQUEST_TRIAGED",
            instance=maintenance_request,
            actor=request.user,
            request=request,
            old_values={"status": previous_status},
            new_values={"status": "triaged"},
            reason="Maintenance request triaged in COL360.",
            property_id=maintenance_request.unit.property_id,
        )

    messages.success(
        request,
        f"Maintenance Request #{maintenance_request.id} was marked as triaged."
    )

    return redirect(
        "portal:maintenance_detail",
        request_id=maintenance_request.id,
    )

@staff_member_required(login_url="/admin/login/")
@require_POST
def approve_maintenance_request(request, request_id):
    maintenance_request = get_object_or_404(
        MaintenanceRequest,
        pk=request_id,
    )

    reviewable_statuses = {
        "new", "triaged", "under_review", "pending_information",
    }
    if maintenance_request.status not in reviewable_statuses:
        messages.error(
            request,
            "This maintenance request is no longer awaiting a review decision.",
        )
        return redirect(
            "portal:maintenance_detail",
            request_id=maintenance_request.id,
        )

    form = MaintenanceRequestReviewForm(
        request.POST,
        instance=maintenance_request,
    )
    if not form.is_valid():
        work_order = (
            WorkOrder.objects
            .filter(maintenance_request=maintenance_request)
            .first()
        )
        property_history = (
            MaintenanceRequest.objects
            .filter(unit__property_id=maintenance_request.unit.property_id)
            .exclude(pk=maintenance_request.pk)
            .select_related("unit")
            .prefetch_related("work_orders")
            .order_by("-submitted_at")[:10]
        )
        return render(
            request,
            "portal/maintenance_detail.html",
            {
                "maintenance_request": maintenance_request,
                "work_order": work_order,
                "review_form": form,
                "property_history": property_history,
                "section": "maintenance",
            },
            status=400,
        )

    decision = form.cleaned_data["decision"]
    tracked_fields = [
        "category", "priority", "status", "review_notes",
        "pending_reason", "assigned_reviewer_id", "review_due_at",
    ]
    before = snapshot(
        maintenance_request,
        tracked_fields,
    )

    with transaction.atomic():
        maintenance_request = form.save(commit=False)
        previous_status = maintenance_request.status
        maintenance_request.status = decision
        if decision in {"approved", "declined"}:
            maintenance_request.reviewed_by = request.user
            maintenance_request.reviewed_at = timezone.now()
            maintenance_request.review_due_at = None
            maintenance_request.pending_reason = ""
        else:
            maintenance_request.reviewed_by = None
            maintenance_request.reviewed_at = None
            if decision == "under_review":
                maintenance_request.pending_reason = ""
        maintenance_request.save(
            update_fields=[
                "category",
                "priority",
                "review_notes",
                "pending_reason",
                "assigned_reviewer",
                "review_due_at",
                "status",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )
        after = snapshot(
            maintenance_request,
            tracked_fields,
        )
        old_values, new_values = changed_values(before, after)
        record_event(
            action={
                "approved": "MAINTENANCE_REQUEST_APPROVED",
                "declined": "MAINTENANCE_REQUEST_DECLINED",
                "pending_information": "MAINTENANCE_REQUEST_PENDING_INFORMATION",
                "under_review": "MAINTENANCE_REQUEST_UNDER_REVIEW",
            }[decision],
            instance=maintenance_request,
            actor=request.user,
            request=request,
            old_values=old_values,
            new_values=new_values,
            reason={
                "approved": "Maintenance request reviewed and approved in COL360.",
                "declined": "Maintenance request reviewed and declined in COL360.",
                "pending_information": "Maintenance request placed pending additional information in COL360.",
                "under_review": "Maintenance request assigned for further review in COL360.",
            }[decision],
            metadata={
                "decision_by_user_id": request.user.pk,
                "previous_status": previous_status,
                "assigned_reviewer_id": maintenance_request.assigned_reviewer_id,
            },
            property_id=maintenance_request.unit.property_id,
        )

    messages.success(request, {
        "approved": (
            f"Maintenance Request #{maintenance_request.id} was approved. "
            "Complete the Work Order details."
        ),
        "declined": f"Maintenance Request #{maintenance_request.id} was declined.",
        "pending_information": (
            f"Maintenance Request #{maintenance_request.id} is pending additional information."
        ),
        "under_review": f"Maintenance Request #{maintenance_request.id} is under review.",
    }[decision])

    if decision == "approved":
        return redirect(
            "portal:create_work_order",
            request_id=maintenance_request.id,
        )

    return redirect(
        "portal:maintenance_detail",
        request_id=maintenance_request.id,
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_work_order(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related("maintenance_request", "unit__property"),
        pk=work_order_id,
    )
    if work_order.status in ["completed", "cancelled"]:
        messages.error(request, "Completed or cancelled work orders are read-only.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    tracked_fields = ["title", "description", "estimated_cost", "notes"]
    before = snapshot(work_order, tracked_fields)
    form = WorkOrderCreateForm(request.POST or None, instance=work_order)
    form.fields.pop("scheduled_for", None)

    if request.method == "POST" and form.is_valid():
        candidate = form.save(commit=False)
        candidate.maintenance_request = work_order.maintenance_request
        candidate.unit = work_order.unit
        candidate.status = work_order.status
        candidate.approved_by = work_order.approved_by
        candidate.approved_at = work_order.approved_at
        candidate.scheduled_for = work_order.scheduled_for
        candidate.completed_at = work_order.completed_at
        candidate.actual_cost = work_order.actual_cost
        after = snapshot(candidate, tracked_fields)
        old_values, new_values = changed_values(before, after)

        if not new_values:
            messages.info(request, "No work order information changed.")
            return redirect("portal:work_order_detail", work_order_id=work_order.id)

        with transaction.atomic():
            candidate.save()
            record_event(
                action="WORK_ORDER_UPDATED",
                instance=candidate,
                actor=request.user,
                request=request,
                old_values=old_values,
                new_values=new_values,
                reason="Work order details updated in COL360.",
                property_id=candidate.unit.property_id,
            )
        messages.success(request, f"Work Order #{candidate.id} was updated.")
        return redirect("portal:work_order_detail", work_order_id=candidate.id)

    return render(request, "portal/edit_work_order.html", {
        "form": form, "work_order": work_order, "section": "maintenance",
    })


@staff_member_required(login_url="/admin/login/")
def work_order_detail(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related(
            "unit__property",
            "maintenance_request",
            "approved_by",
            "supersedes",
        ).prefetch_related(
            "vendor_assignments__vendor",
            "vendor_awards__vendor",
            "vendor_awards__estimate",
            "vendor_estimates__vendor",
            "quote_requests__vendor",
            "status_history__changed_by",
        ),
        pk=work_order_id,
    )

    estimates = list(
        work_order.vendor_estimates.all()
    )

    active_award = next(
        (
            award for award in work_order.vendor_awards.all()
            if award.status in ["pending_confirmation", "active"]
        ),
        None,
    )
    approved_estimate = active_award.estimate if active_award else None

    pending_estimate_count = sum(
        1
        for estimate in estimates
        if estimate.status == "pending"
    )

    estimate_amounts = [
        estimate.amount
        for estimate in estimates
    ]

    lowest_estimate = (
        min(estimate_amounts)
        if estimate_amounts
        else None
    )

    highest_estimate = (
        max(estimate_amounts)
        if estimate_amounts
        else None
    )

    # V1.5A: accounting data is resolved through the configured provider.
    # Core work-order/estimate behavior remains independent of accounting.
    financial = get_work_order_financials(work_order)

    has_variance = (
        work_order.estimated_cost is not None
        and work_order.actual_cost is not None
    )
    variance = (
        work_order.actual_cost - work_order.estimated_cost
        if has_variance
        else None
    )

    maintenance_request = work_order.maintenance_request
    active_sibling_exists = bool(
        maintenance_request
        and maintenance_request.work_orders.exclude(status="cancelled")
        .exclude(pk=work_order.pk)
        .exists()
    )
    can_create_replacement = bool(
        maintenance_request
        and work_order.status == "cancelled"
        and maintenance_request.status == "approved"
        and not active_sibling_exists
    )
    try:
        replacement_work_order = work_order.replacement_work_order
    except WorkOrder.DoesNotExist:
        replacement_work_order = None

    assignments = list(work_order.vendor_assignments.all())
    quote_requests = list(work_order.quote_requests.all())
    assigned_vendor_ids = {assignment.vendor_id for assignment in assignments}
    selected_vendor_assigned = bool(
        active_award and active_award.vendor_id in assigned_vendor_ids
    )
    active_assignment = next(
        (
            assignment
            for assignment in assignments
            if assignment.status not in ["cancelled", "declined"]
            and (
                active_award is None
                or assignment.vendor_id == active_award.vendor_id
            )
        ),
        None,
    )

    # V1.5A.2: one operational row per vendor. VendorEstimate and
    # VendorAssignment remain separate domain records; this is presentation only.
    vendor_rows_by_id = {}

    for quote_request in quote_requests:
        vendor_rows_by_id.setdefault(
            quote_request.vendor_id,
            {
                "vendor": quote_request.vendor,
                "quote_request": quote_request,
                "estimate": None,
                "assignment": None,
            },
        )

    for estimate in estimates:
        row = vendor_rows_by_id.setdefault(
            estimate.vendor_id,
            {
                "vendor": estimate.vendor,
                "quote_request": None,
                "estimate": None,
                "assignment": None,
            },
        )
        current = row["estimate"]
        # Prefer the awarded estimate, otherwise the newest estimate.
        if (
            current is None
            or (active_award and active_award.estimate_id == estimate.pk)
            or (
                (not active_award or active_award.estimate_id != current.pk)
                and estimate.pk > current.pk
            )
        ):
            row["estimate"] = estimate

    for assignment in assignments:
        row = vendor_rows_by_id.setdefault(
            assignment.vendor_id,
            {
                "vendor": assignment.vendor,
                "quote_request": None,
                "estimate": None,
                "assignment": None,
            },
        )
        row["assignment"] = assignment

    for row in vendor_rows_by_id.values():
        row["is_alternative"] = bool(
            active_award and row["vendor"].pk != active_award.vendor_id
        )
        row["is_active_award"] = bool(
            active_award and row["vendor"].pk == active_award.vendor_id
        )

    vendor_rows = sorted(
        vendor_rows_by_id.values(),
        key=lambda row: (
            0
            if row["is_active_award"]
            else 1,
            str(row["vendor"]).lower(),
        ),
    )

    status_history = list(work_order.status_history.all())
    has_invoices = bool(financial["invoices"])

    return render(
        request,
        "portal/work_order_detail.html",
        {
            "work_order": work_order,
            "maintenance_request": maintenance_request,
            "can_create_replacement": can_create_replacement,
            "replacement_work_order": replacement_work_order,
            "quote_requests": quote_requests,

            "financial": financial,
            # Temporary compatibility aliases for existing presentation code.
            "total_invoiced": financial["total_invoiced"],
            "total_paid": financial["total_paid"],
            "outstanding": financial["outstanding"],
            "variance": variance,
            "has_estimated_cost": work_order.estimated_cost is not None,
            "has_variance": has_variance,

            "estimates": estimates,
            "approved_estimate": approved_estimate,
            "active_award": active_award,
            "pending_estimate_count": pending_estimate_count,
            "lowest_estimate": lowest_estimate,
            "highest_estimate": highest_estimate,
            "selected_vendor_assigned": selected_vendor_assigned,
            "active_assignment": active_assignment,
            "vendor_rows": vendor_rows,
            "status_history": status_history,
            "has_invoices": has_invoices,

            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def assign_vendor(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related(
            "unit__property"
        ).prefetch_related("vendor_assignments", "vendor_awards"),
        pk=work_order_id,
    )

    if work_order.status in ["completed", "cancelled"]:
        messages.error(
            request,
            "A vendor cannot be assigned to a completed or cancelled work order."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    active_award = work_order.vendor_awards.filter(
        status__in=["pending_confirmation", "active"]
    ).first()
    if active_award:
        messages.info(
            request,
            "This work order already has a current vendor selection.",
        )
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    estimate_id = request.GET.get("estimate_id")
    selected_estimate = None
    selected_vendor = None

    if estimate_id:
        selected_estimate = get_object_or_404(
            VendorEstimate.objects.select_related("vendor"),
            pk=estimate_id,
            work_order=work_order,
        )
        selected_vendor = selected_estimate.vendor

    if request.method == "POST":
        posted_vendor_id = selected_vendor.pk if selected_vendor else request.POST.get("vendor")
        existing_assignment = work_order.vendor_assignments.filter(
            vendor_id=posted_vendor_id
        ).first()
        form = VendorAssignmentForm(
            request.POST,
            work_order=work_order,
            quote_selected=bool(selected_estimate),
            selected_estimate=selected_estimate,
            initial={"vendor": selected_vendor} if selected_vendor else None,
            instance=existing_assignment,
        )
        if selected_vendor:
            form.fields["vendor"].disabled = True

        if form.is_valid():
            if selected_estimate:
                with transaction.atomic():
                    award = VendorAward.objects.create(
                        work_order=work_order,
                        vendor=selected_vendor,
                        estimate=selected_estimate,
                        method="quote",
                        status="pending_confirmation",
                        decision_reason=(
                            form.cleaned_data.get("award_rationale")
                            or "lowest_qualified_quote"
                        ),
                        decision_notes=form.cleaned_data.get(
                            "award_rationale_notes", ""
                        ),
                        awarded_by=request.user,
                    )
                    work_order.estimated_cost = selected_estimate.amount
                    work_order.save(update_fields=["estimated_cost", "updated_at"])
                    record_event(
                        action="VENDOR_QUOTE_SELECTED",
                        instance=award,
                        actor=request.user,
                        request=request,
                        old_values={},
                        new_values={
                            "vendor": str(selected_vendor),
                            "estimate_id": selected_estimate.pk,
                            "status": "pending_confirmation",
                        },
                        reason="Quote selected pending vendor confirmation.",
                        property_id=work_order.unit.property_id,
                    )
                send_mail(
                    subject=f"Quote selected for Work Order #{work_order.id}",
                    message=(
                        f"Hello {selected_vendor},\n\n"
                        f"Your quote for Work Order #{work_order.id} — "
                        f"{work_order.title} — has been selected, pending confirmation "
                        "of your availability and final work-order assignment.\n\n"
                        f"Selected quote: ${selected_estimate.amount:,.2f}\n\n"
                        "Please contact the property manager to confirm that you can "
                        "perform the work under the quoted scope, price, and terms."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[selected_vendor.email],
                    fail_silently=False,
                )
                messages.success(
                    request,
                    f"{selected_vendor}'s quote was selected and a confirmation request was emailed.",
                )
            else:
                with transaction.atomic():
                    assignment = form.save(commit=False)
                    assignment.work_order = work_order
                    assignment.status = "assigned"
                    assignment.save()
                    award = VendorAward.objects.create(
                        work_order=work_order,
                        vendor=assignment.vendor,
                        method="direct",
                        status="active",
                        decision_reason=form.cleaned_data["direct_assignment_reason"],
                        decision_notes=assignment.vendor_notes,
                        awarded_by=request.user,
                        confirmed_by=request.user,
                        confirmed_at=timezone.now(),
                    )
                    previous_status = work_order.status
                    work_order.status = "assigned"
                    work_order.save(update_fields=["status", "updated_at"])
                    WorkOrderStatusHistory.objects.create(
                        work_order=work_order,
                        from_status=previous_status,
                        to_status="assigned",
                        changed_by=request.user,
                        notes=f"Vendor directly assigned: {assignment.vendor}",
                    )
                    record_event(
                        action="VENDOR_ASSIGNED",
                        instance=assignment,
                        actor=request.user,
                        request=request,
                        old_values={},
                        new_values={"vendor": str(assignment.vendor), "award_id": award.pk},
                        reason="Vendor assigned without quote.",
                        property_id=work_order.unit.property_id,
                    )
                messages.success(
                    request,
                    f"{assignment.vendor} was assigned to Work Order #{work_order.id}.",
                )

            return redirect(
                "portal:work_order_detail",
                work_order_id=work_order.id,
            )

    else:
        existing_assignment = (
            work_order.vendor_assignments.filter(vendor=selected_vendor).first()
            if selected_vendor else None
        )
        form = VendorAssignmentForm(
            work_order=work_order,
            quote_selected=bool(selected_estimate),
            selected_estimate=selected_estimate,
            initial={"vendor": selected_vendor} if selected_vendor else None,
            instance=existing_assignment,
        )
        if selected_vendor:
            form.fields["vendor"].disabled = True

    return render(
        request,
        "portal/assign_vendor.html",
        {
            "form": form,
            "work_order": work_order,
            "selected_estimate": selected_estimate,
            "section": "maintenance",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_POST
def confirm_vendor(request, work_order_id, award_id):
    work_order = get_object_or_404(WorkOrder, pk=work_order_id)
    with transaction.atomic():
        award = get_object_or_404(
            VendorAward.objects.select_for_update(),
            pk=award_id,
            work_order=work_order,
            status="pending_confirmation",
        )
        award.status = "active"
        award.confirmed_by = request.user
        award.confirmed_at = timezone.now()
        award.save(update_fields=["status", "confirmed_by", "confirmed_at"])
        record_event(
            action="VENDOR_CONFIRMED",
            instance=award,
            actor=request.user,
            request=request,
            old_values={"status": "pending_confirmation"},
            new_values={"status": "active"},
            reason="Vendor availability and quoted terms confirmed.",
            property_id=work_order.unit.property_id,
        )
    messages.success(request, f"{award.vendor} was confirmed. The work order is ready to assign.")
    return redirect("portal:work_order_detail", work_order_id=work_order.id)


@staff_member_required(login_url="/admin/login/")
@require_POST
def assign_awarded_vendor(request, work_order_id, award_id):
    work_order = get_object_or_404(WorkOrder.objects.select_related("unit__property"), pk=work_order_id)
    if work_order.status in ["completed", "cancelled"]:
        messages.error(request, "This work order cannot be assigned in its current status.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    with transaction.atomic():
        award = get_object_or_404(
            VendorAward.objects.select_for_update().select_related("vendor"),
            pk=award_id,
            work_order=work_order,
            status="active",
        )
        if work_order.vendor_assignments.filter(
            status__in=["assigned", "accepted", "scheduled"]
        ).exists():
            messages.error(request, "Cancel the current assignment before assigning another vendor.")
            return redirect("portal:work_order_detail", work_order_id=work_order.id)
        assignment, _ = VendorAssignment.objects.get_or_create(
            work_order=work_order,
            vendor=award.vendor,
            defaults={"status": "assigned"},
        )
        assignment.status = "assigned"
        assignment.scheduled_for = None
        assignment.completed_at = None
        assignment.save(update_fields=["status", "scheduled_for", "completed_at", "updated_at"])
        previous_status = work_order.status
        work_order.status = "assigned"
        work_order.scheduled_for = None
        work_order.save(update_fields=["status", "scheduled_for", "updated_at"])
        WorkOrderStatusHistory.objects.create(
            work_order=work_order,
            from_status=previous_status,
            to_status="assigned",
            changed_by=request.user,
            notes=f"Work order assigned to {award.vendor}.",
        )
        record_event(
            action="VENDOR_ASSIGNED",
            instance=assignment,
            actor=request.user,
            request=request,
            old_values={},
            new_values={"vendor": str(award.vendor), "award_id": award.pk},
            reason="Confirmed vendor explicitly assigned to work order.",
            property_id=work_order.unit.property_id,
        )
    send_mail(
        subject=f"Work Order #{work_order.id} assigned to you",
        message=(
            f"Hello {award.vendor},\n\nWork Order #{work_order.id} — "
            f"{work_order.title} — has been assigned to you. The property manager "
            "will coordinate scheduling and access details with you."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[award.vendor.email],
        fail_silently=False,
    )
    messages.success(request, f"Work Order #{work_order.id} was assigned to {award.vendor}.")
    return redirect("portal:work_order_detail", work_order_id=work_order.id)


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def cancel_vendor_assignment(request, work_order_id, assignment_id):
    work_order = get_object_or_404(WorkOrder.objects.select_related("unit__property"), pk=work_order_id)
    assignment = get_object_or_404(
        VendorAssignment.objects.select_related("vendor"),
        pk=assignment_id,
        work_order=work_order,
        status__in=["assigned", "accepted", "scheduled"],
    )
    form = CancelVendorAssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        previous_status = work_order.status
        previous_assignment_status = assignment.status
        reason_label = dict(VendorAward.CHANGE_REASON_CHOICES)[
            form.cleaned_data["reason"]
        ]
        with transaction.atomic():
            assignment.status = "cancelled"
            assignment.scheduled_for = None
            assignment.save(update_fields=["status", "scheduled_for", "updated_at"])
            work_order.status = "new"
            work_order.scheduled_for = None
            work_order.save(update_fields=["status", "scheduled_for", "updated_at"])
            WorkOrderStatusHistory.objects.create(
                work_order=work_order,
                from_status=previous_status,
                to_status="new",
                changed_by=request.user,
                notes=(
                    f"Assignment to {assignment.vendor} cancelled ({reason_label}): "
                    f"{form.cleaned_data['notes']}"
                ),
            )
            record_event(
                action="VENDOR_ASSIGNMENT_CANCELLED",
                instance=assignment,
                actor=request.user,
                request=request,
                old_values={"status": previous_assignment_status},
                new_values={"status": "cancelled"},
                reason=f"{reason_label}: {form.cleaned_data['notes']}",
                property_id=work_order.unit.property_id,
            )
        messages.success(request, "The assignment was cancelled. The vendor award remains in place.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)
    return render(request, "portal/cancel_vendor_assignment.html", {
        "form": form,
        "work_order": work_order,
        "assignment": assignment,
        "section": "maintenance",
    })


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def change_vendor(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related("unit__property"), pk=work_order_id
    )
    active_award = get_object_or_404(
        VendorAward.objects.select_related("vendor", "estimate"),
        work_order=work_order,
        status__in=["pending_confirmation", "active"],
    )
    if work_order.vendor_assignments.filter(
        status__in=["assigned", "accepted", "scheduled"]
    ).exists():
        messages.error(
            request,
            "Cancel the active assignment before changing the vendor award.",
        )
        return redirect("portal:work_order_detail", work_order_id=work_order.id)
    if work_order.status in ["in_progress", "completed", "cancelled"]:
        messages.error(
            request,
            "Stop or reopen the work order before changing its active vendor.",
        )
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    form = ChangeVendorForm(
        request.POST or None, work_order=work_order, active_award=active_award
    )
    if request.method == "POST" and form.is_valid():
        replacement = form.cleaned_data["replacement_estimate"]
        reason_label = dict(VendorAward.CHANGE_REASON_CHOICES)[form.cleaned_data["reason"]]
        now = timezone.now()
        with transaction.atomic():
            locked_award = VendorAward.objects.select_for_update().get(
                pk=active_award.pk,
                status__in=["pending_confirmation", "active"],
            )
            locked_award.status = "revoked"
            locked_award.revoked_by = request.user
            locked_award.revoked_at = now
            locked_award.revocation_reason = form.cleaned_data["reason"]
            locked_award.revocation_notes = form.cleaned_data["notes"]
            locked_award.save(update_fields=[
                "status", "revoked_by", "revoked_at", "revocation_reason",
                "revocation_notes",
            ])
            VendorAssignment.objects.filter(
                work_order=work_order,
                vendor=locked_award.vendor,
                status__in=["assigned", "accepted", "scheduled"],
            ).update(status="cancelled")

            previous_status = work_order.status
            work_order.scheduled_for = None
            if replacement:
                new_award = VendorAward.objects.create(
                    work_order=work_order,
                    vendor=replacement.vendor,
                    estimate=replacement,
                    method="quote",
                    status="pending_confirmation",
                    decision_reason="replacement_after_vendor_change",
                    decision_notes=form.cleaned_data["notes"],
                    awarded_by=request.user,
                )
                work_order.status = "new"
                work_order.estimated_cost = replacement.amount
                note = f"{replacement.vendor}'s quote selected pending confirmation."
            else:
                new_award = None
                work_order.status = "new"
                work_order.estimated_cost = None
                note = "Active vendor removed; work order returned to vendor sourcing."
            work_order.save(update_fields=[
                "status", "scheduled_for", "estimated_cost", "updated_at"
            ])
            WorkOrderStatusHistory.objects.create(
                work_order=work_order,
                from_status=previous_status,
                to_status=work_order.status,
                changed_by=request.user,
                notes=f"{note} Reason: {reason_label}",
            )
            record_event(
                action="WORK_ORDER_VENDOR_CHANGED",
                instance=work_order,
                actor=request.user,
                request=request,
                old_values={"vendor": str(active_award.vendor), "award_id": active_award.pk},
                new_values={
                    "vendor": str(replacement.vendor) if replacement else None,
                    "award_id": new_award.pk if new_award else None,
                },
                reason=form.cleaned_data["notes"] or reason_label,
                property_id=work_order.unit.property_id,
            )
        if replacement:
            send_mail(
                subject=f"Quote selected for Work Order #{work_order.id}",
                message=(
                    f"Hello {replacement.vendor},\n\nYour quote for Work Order "
                    f"#{work_order.id} — {work_order.title} — has been selected, "
                    "pending confirmation of availability and final assignment."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[replacement.vendor.email],
                fail_silently=False,
            )
        messages.success(request, note)
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    return render(request, "portal/change_vendor.html", {
        "form": form,
        "work_order": work_order,
        "active_award": active_award,
        "section": "maintenance",
    })

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def schedule_vendor(request, work_order_id, assignment_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related(
            "unit__property"
        ),
        pk=work_order_id,
    )

    assignment = get_object_or_404(
        VendorAssignment.objects.select_related(
            "vendor",
            "work_order",
        ),
        pk=assignment_id,
        work_order=work_order,
    )

    if work_order.status in ["completed", "cancelled"]:
        messages.error(
            request,
            "A completed or cancelled work order cannot be scheduled."
        )

        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if assignment.status in ["completed", "cancelled", "declined"]:
        messages.error(
            request,
            "This vendor assignment cannot be scheduled."
        )

        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if request.method == "POST":
        form = VendorScheduleForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                scheduled_for = form.cleaned_data["scheduled_for"]
                vendor_notes = form.cleaned_data["vendor_notes"]

                previous_status = work_order.status

                assignment.scheduled_for = scheduled_for
                assignment.status = "scheduled"

                if vendor_notes:
                    assignment.vendor_notes = vendor_notes

                assignment.save(
                    update_fields=[
                        "scheduled_for",
                        "status",
                        "vendor_notes",
                        "updated_at",
                    ]
                )

                # Scheduling an additional vendor must never move an
                # in-progress work order backward to "scheduled".
                if work_order.status != "in_progress":
                    work_order.scheduled_for = scheduled_for
                    work_order.status = "scheduled"

                    work_order.save(
                        update_fields=[
                            "scheduled_for",
                            "status",
                            "updated_at",
                        ]
                    )

                WorkOrderStatusHistory.objects.create(
                    work_order=work_order,
                    from_status=previous_status,
                    to_status=work_order.status,
                    changed_by=request.user,
                    notes=(
                        f"{assignment.vendor} scheduled for "
                        f"{scheduled_for:%b %d, %Y %I:%M %p}"
                    ),
                )
                record_event(
                    action="VENDOR_SCHEDULED",
                    instance=assignment,
                    actor=request.user,
                    request=request,
                    old_values={},
                    new_values={
                        "vendor": str(assignment.vendor),
                        "scheduled_for": scheduled_for,
                        "status": assignment.status,
                    },
                    reason="Vendor visit scheduled in COL360.",
                    property_id=work_order.unit.property_id,
                )

            messages.success(
                request,
                f"{assignment.vendor} was scheduled successfully."
            )

            return redirect(
                "portal:work_order_detail",
                work_order_id=work_order.id,
            )

    else:
        form = VendorScheduleForm(
            initial={
                "scheduled_for": assignment.scheduled_for,
                "vendor_notes": assignment.vendor_notes,
            }
        )

    return render(
        request,
        "portal/schedule_vendor.html",
        {
            "form": form,
            "work_order": work_order,
            "assignment": assignment,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["POST"])
def start_work_order(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder,
        pk=work_order_id,
    )

    if work_order.status == "in_progress":
        messages.info(
            request,
            f"Work Order #{work_order.id} is already in progress."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if work_order.status in ["completed", "cancelled"]:
        messages.error(
            request,
            "A completed or cancelled work order cannot be started."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if work_order.status != "scheduled":
        messages.error(
            request,
            "Only a scheduled work order can be started."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    with transaction.atomic():
        previous_status = work_order.status

        work_order.status = "in_progress"
        work_order.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        WorkOrderStatusHistory.objects.create(
            work_order=work_order,
            from_status=previous_status,
            to_status="in_progress",
            changed_by=request.user,
            notes="Work started.",
        )
        record_event(
            action="WORK_ORDER_STARTED",
            instance=work_order,
            actor=request.user,
            request=request,
            old_values={"status": previous_status},
            new_values={"status": "in_progress"},
            reason="Work order started in COL360.",
            property_id=work_order.unit.property_id,
        )

    messages.success(
        request,
        f"Work Order #{work_order.id} is now in progress."
    )

    return redirect(
        "portal:work_order_detail",
        work_order_id=work_order.id,
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def complete_work_order(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related(
            "maintenance_request",
            "unit__property",
        ).prefetch_related(
            "vendor_assignments__vendor",
        ),
        pk=work_order_id,
    )

    if work_order.status == "completed":
        messages.info(
            request,
            f"Work Order #{work_order.id} is already completed."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if work_order.status == "cancelled":
        messages.error(
            request,
            "A cancelled work order cannot be completed."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if work_order.status != "in_progress":
        messages.error(
            request,
            "Only a work order that is in progress can be completed."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if request.method == "POST":
        form = WorkOrderCompleteForm(request.POST)

        if form.is_valid():
            completed_at = (
                form.cleaned_data["completed_at"]
                or timezone.now()
            )

            actual_cost = form.cleaned_data["actual_cost"]
            completion_notes = form.cleaned_data["completion_notes"]

            with transaction.atomic():
                previous_status = work_order.status

                work_order.status = "completed"
                work_order.actual_cost = actual_cost
                work_order.completed_at = completed_at

                if completion_notes:
                    if work_order.notes:
                        work_order.notes += (
                            "\n\nCompletion Notes:\n"
                            + completion_notes
                        )
                    else:
                        work_order.notes = completion_notes

                work_order.save(
                    update_fields=[
                        "status",
                        "actual_cost",
                        "completed_at",
                        "notes",
                        "updated_at",
                    ]
                )

                for assignment in work_order.vendor_assignments.all():
                    if assignment.status not in [
                        "cancelled",
                        "declined",
                    ]:
                        assignment.status = "completed"
                        assignment.completed_at = completed_at
                        assignment.save(
                            update_fields=[
                                "status",
                                "completed_at",
                                "updated_at",
                            ]
                        )

                maintenance_request = work_order.maintenance_request

                if maintenance_request:
                    maintenance_request.status = "completed"
                    maintenance_request.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )

                WorkOrderStatusHistory.objects.create(
                    work_order=work_order,
                    from_status=previous_status,
                    to_status="completed",
                    changed_by=request.user,
                    notes=completion_notes or "Work completed.",
                )
                record_event(
                    action="WORK_ORDER_COMPLETED",
                    instance=work_order,
                    actor=request.user,
                    request=request,
                    old_values={"status": previous_status},
                    new_values={
                        "status": "completed",
                        "actual_cost": actual_cost,
                        "completed_at": completed_at,
                    },
                    reason=completion_notes or "Work order completed in COL360.",
                    property_id=work_order.unit.property_id,
                )

            messages.success(
                request,
                f"Work Order #{work_order.id} was completed successfully."
            )

            return redirect(
                "portal:work_order_detail",
                work_order_id=work_order.id,
            )

    else:
        form = WorkOrderCompleteForm(
            initial={
                "actual_cost": work_order.actual_cost,
            }
        )

    return render(
        request,
        "portal/complete_work_order.html",
        {
            "form": form,
            "work_order": work_order,
            "section": "maintenance",
        },
    )

def cancel_work_order(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related(
            "maintenance_request",
            "unit__property",
        ).prefetch_related(
            "vendor_assignments__vendor",
        ),
        pk=work_order_id,
    )

    if work_order.status == "completed":
        messages.error(
            request,
            "A completed work order cannot be cancelled."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if work_order.status == "cancelled":
        messages.info(
            request,
            f"Work Order #{work_order.id} is already cancelled."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=work_order.id,
        )

    if request.method == "POST":
        form = WorkOrderCancelForm(request.POST)

        if form.is_valid():
            cancellation_reason = (
                form.cleaned_data["cancellation_reason"]
            )

            with transaction.atomic():
                previous_status = work_order.status

                work_order.status = "cancelled"

                if work_order.notes:
                    work_order.notes += (
                        "\n\nCancellation Reason:\n"
                        + cancellation_reason
                    )
                else:
                    work_order.notes = (
                        "Cancellation Reason:\n"
                        + cancellation_reason
                    )

                work_order.save(
                    update_fields=[
                        "status",
                        "notes",
                        "updated_at",
                    ]
                )

                for assignment in work_order.vendor_assignments.all():
                    if assignment.status not in [
                        "completed",
                        "cancelled",
                        "declined",
                    ]:
                        assignment.status = "cancelled"
                        assignment.save(
                            update_fields=[
                                "status",
                                "updated_at",
                            ]
                        )

                maintenance_request = (
                    work_order.maintenance_request
                )

                if maintenance_request:
                    previous_request_status = maintenance_request.status
                    maintenance_request.status = "approved"
                    maintenance_request.save(
                        update_fields=[
                            "status",
                            "updated_at",
                        ]
                    )
                    record_event(
                        action="MAINTENANCE_REQUEST_REOPENED",
                        instance=maintenance_request,
                        actor=request.user,
                        request=request,
                        old_values={"status": previous_request_status},
                        new_values={"status": "approved"},
                        reason=(
                            "Linked work order was cancelled; a replacement "
                            "work order may now be created."
                        ),
                        property_id=work_order.unit.property_id,
                    )

                WorkOrderStatusHistory.objects.create(
                    work_order=work_order,
                    from_status=previous_status,
                    to_status="cancelled",
                    changed_by=request.user,
                    notes=cancellation_reason,
                )
                record_event(
                    action="WORK_ORDER_CANCELLED",
                    instance=work_order,
                    actor=request.user,
                    request=request,
                    old_values={"status": previous_status},
                    new_values={"status": "cancelled"},
                    reason=cancellation_reason,
                    property_id=work_order.unit.property_id,
                )

            messages.success(
                request,
                (
                    f"Work Order #{work_order.id} was cancelled. "
                    "The maintenance request is approved for a replacement "
                    "work order."
                )
            )

            return redirect(
                "portal:work_order_detail",
                work_order_id=work_order.id,
            )

    else:
        form = WorkOrderCancelForm()

    return render(
        request,
        "portal/cancel_work_order.html",
        {
            "form": form,
            "work_order": work_order,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_work_order(request, request_id):
    maintenance_request = get_object_or_404(
        MaintenanceRequest.objects.select_related(
            "unit__property"
        ),
        pk=request_id,
    )

    # A request may retain cancelled work orders as history, but it can have
    # only one non-cancelled work order at a time.
    existing_work_order = WorkOrder.objects.filter(
        maintenance_request=maintenance_request
    ).exclude(status="cancelled").first()

    if existing_work_order:
        messages.info(
            request,
            "A work order already exists for this maintenance request."
        )
        return redirect(
            "portal:work_order_detail",
            work_order_id=existing_work_order.id,
        )

    replacement_candidate = WorkOrder.objects.filter(
        maintenance_request=maintenance_request,
        status="cancelled",
        replacement_work_order__isnull=True,
    ).order_by("-created_at").first()

    # A Work Order may only be created after the
    # Maintenance Request has been approved.
    if maintenance_request.status != "approved":
        messages.error(
            request,
            (
                f"This maintenance request is currently "
                f"{maintenance_request.get_status_display()}. "
                "Approve the request before creating a Work Order."
            ),
        )
        return redirect(
            "portal:maintenance_detail",
            request_id=maintenance_request.id,
        )
    if request.method == "POST":
        form = WorkOrderCreateForm(request.POST)

        if form.is_valid():

            with transaction.atomic():

                locked_request = MaintenanceRequest.objects.select_for_update().get(
                    pk=maintenance_request.pk
                )
                if locked_request.status != "approved":
                    messages.error(
                        request,
                        "This request is no longer approved for work-order creation.",
                    )
                    return redirect(
                        "portal:maintenance_detail",
                        request_id=locked_request.id,
                    )
                concurrent_work_order = WorkOrder.objects.filter(
                    maintenance_request=locked_request
                ).exclude(status="cancelled").first()
                if concurrent_work_order:
                    messages.info(
                        request,
                        "A current work order already exists for this request.",
                    )
                    return redirect(
                        "portal:work_order_detail",
                        work_order_id=concurrent_work_order.id,
                    )

                superseded_work_order = WorkOrder.objects.filter(
                    maintenance_request=locked_request,
                    status="cancelled",
                    replacement_work_order__isnull=True,
                ).order_by("-created_at").first()

                work_order = form.save(commit=False)

                work_order.maintenance_request = (
                    locked_request
                )

                work_order.supersedes = superseded_work_order

                work_order.unit = (
                    locked_request.unit
                )

                # Explicit starting state.
                work_order.status = "new"

                work_order.save()

                # Move the maintenance request forward
                # only after the work order is created.
                locked_request.status = "converted"

                locked_request.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                record_event(
                    action="WORK_ORDER_CREATED",
                    instance=work_order,
                    actor=request.user,
                    request=request,
                    old_values={},
                    new_values=snapshot(
                        work_order,
                        ["title", "description", "status", "estimated_cost"],
                    ),
                    reason=(
                        f"Replacement for Work Order #{superseded_work_order.id}."
                        if superseded_work_order
                        else "Work order created from approved maintenance request."
                    ),
                    property_id=work_order.unit.property_id,
                )

            messages.success(
                request,
                f"Work Order #{work_order.id} was created successfully."
            )

            return redirect(
                "portal:work_order_detail",
                work_order_id=work_order.id,
            )

    else:
        form = WorkOrderCreateForm(
            initial={
                "title": maintenance_request.title,
                "description": maintenance_request.description,
            }
        )

    return render(
        request,
        "portal/create_work_order.html",
        {
            "form": form,
            "maintenance_request": maintenance_request,
            "replacement_candidate": replacement_candidate,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def add_vendor_invoice(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.prefetch_related("vendor_assignments__vendor"),
        pk=work_order_id,
    )
    provider = get_financial_provider()

    if not provider.capabilities()["can_add_invoice"]:
        messages.info(request, f"Invoice entry is unavailable with {provider.label}.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    assigned_vendor_ids = work_order.vendor_assignments.values_list("vendor_id", flat=True)
    vendor_queryset = Vendor.objects.filter(id__in=assigned_vendor_ids).order_by(
        "company_name", "name"
    )
    form = provider.get_invoice_form(
        request.POST or None,
        vendor_queryset=vendor_queryset,
    )

    if request.method == "POST" and form.is_valid():
        try:
            invoice = provider.create_invoice(form, work_order=work_order)
        except FinancialProviderError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Invoice {invoice.invoice_number or invoice.id} was added.",
            )
            return redirect("portal:work_order_detail", work_order_id=work_order.id)

    return render(
        request,
        "portal/add_vendor_invoice.html",
        {"form": form, "work_order": work_order, "section": "maintenance"},
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def add_maintenance_photo(request, request_id):
    maintenance_request = get_object_or_404(
        MaintenanceRequest,
        pk=request_id,
    )

    if request.method == "POST":
        form = MaintenancePhotoForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            photo = form.save(commit=False)
            photo.maintenance_request = maintenance_request
            photo.uploaded_by = request.user
            photo.save()

            messages.success(
                request,
                "Maintenance photo uploaded successfully."
            )

            return redirect(
                "portal:maintenance_detail",
                request_id=maintenance_request.id,
            )

    else:
        form = MaintenancePhotoForm()

    return render(
        request,
        "portal/add_maintenance_photo.html",
        {
            "form": form,
            "maintenance_request": maintenance_request,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["POST"])
def approve_vendor_invoice(request, invoice_id):
    provider = get_financial_provider()
    try:
        invoice = provider.get_invoice(invoice_id)
        invoice, result = provider.approve_invoice(invoice, actor=request.user)
        if result == "already_approved":
            messages.info(request, f"Invoice {invoice.invoice_number or invoice.id} is already approved.")
        elif result == "already_paid":
            messages.info(request, f"Invoice {invoice.invoice_number or invoice.id} is already paid.")
        else:
            messages.success(request, f"Invoice {invoice.invoice_number or invoice.id} was approved.")
        work_order_id = invoice.work_order_id
    except (FinancialProviderError, FinancialProviderDisabled) as exc:
        messages.error(request, str(exc))
        return redirect("portal:maintenance")
    return redirect("portal:work_order_detail", work_order_id=work_order_id)


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["POST"])
def mark_vendor_invoice_paid(request, invoice_id):
    provider = get_financial_provider()
    try:
        invoice = provider.get_invoice(invoice_id)
        invoice, result = provider.mark_invoice_paid(invoice, actor=request.user)
        if result == "already_paid":
            messages.info(request, f"Invoice {invoice.invoice_number or invoice.id} is already marked paid.")
        else:
            messages.success(request, f"Invoice {invoice.invoice_number or invoice.id} was marked paid.")
        work_order_id = invoice.work_order_id
    except (FinancialProviderError, FinancialProviderDisabled) as exc:
        messages.error(request, str(exc))
        return redirect("portal:maintenance")
    return redirect("portal:work_order_detail", work_order_id=work_order_id)

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["POST"])
def approve_vendor_estimate(request, estimate_id):
    estimate = get_object_or_404(
        VendorEstimate.objects.select_related("work_order__unit__property", "vendor"),
        pk=estimate_id,
    )
    work_order = estimate.work_order

    messages.info(
        request,
        "Quotes are no longer approved separately. Use Award & Assign to select this vendor.",
    )
    return redirect("portal:work_order_detail", work_order_id=work_order.id)

    # Legacy implementation retained below temporarily for migration context.
    if work_order.status in ["completed", "cancelled"]:
        messages.error(request, "Estimates cannot be approved for a completed or cancelled work order.")
    elif estimate.status == "approved":
        messages.info(request, f"Estimate from {estimate.vendor} is already approved.")
    elif estimate.status == "rejected":
        messages.error(request, "A rejected estimate cannot be approved.")
    elif estimate.status != "pending":
        messages.error(request, "Only a pending estimate can be approved.")
    else:
        with transaction.atomic():
            estimates = VendorEstimate.objects.select_for_update().filter(work_order=work_order)
            existing_approved = estimates.filter(status="approved").exclude(pk=estimate.pk).first()
            if existing_approved:
                messages.error(
                    request,
                    f"This work order already has an approved estimate from {existing_approved.vendor}.",
                )
                return redirect("portal:work_order_detail", work_order_id=work_order.id)

            rejected_ids = list(
                estimates.filter(status="pending").exclude(pk=estimate.pk).values_list("id", flat=True)
            )
            estimate.status = "approved"
            estimate.approved_by = request.user
            estimate.approved_at = timezone.now()
            estimate.save(update_fields=["status", "approved_by", "approved_at"])
            estimates.filter(pk__in=rejected_ids).update(status="rejected")
            old_estimated_cost = work_order.estimated_cost
            work_order.estimated_cost = estimate.amount
            work_order.save(update_fields=["estimated_cost", "updated_at"])

            record_event(
                action="VENDOR_ESTIMATE_APPROVED",
                instance=estimate,
                actor=request.user,
                request=request,
                old_values={"status": "pending", "estimated_cost": old_estimated_cost},
                new_values={
                    "vendor": str(estimate.vendor),
                    "amount": estimate.amount,
                    "status": "approved",
                    "estimated_cost": estimate.amount,
                },
                metadata={"automatically_rejected_estimate_ids": rejected_ids},
                reason="Vendor estimate selected for the work order.",
                property_id=work_order.unit.property_id,
            )

        messages.success(
            request,
            f"Estimate from {estimate.vendor} was selected and approved. The work order estimated cost is now ${estimate.amount:,.2f}.",
        )

    return redirect("portal:work_order_detail", work_order_id=work_order.id)


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["POST"])
def reject_vendor_estimate(request, estimate_id):
    estimate = get_object_or_404(
        VendorEstimate.objects.select_related("work_order__unit__property", "vendor"),
        pk=estimate_id,
    )
    work_order = estimate.work_order

    messages.info(
        request,
        "Received quotes remain available as alternatives and are not rejected during selection.",
    )
    return redirect("portal:work_order_detail", work_order_id=work_order.id)

    # Legacy implementation retained below temporarily for migration context.
    if work_order.status in ["completed", "cancelled"]:
        messages.error(request, "Estimates cannot be changed for a completed or cancelled work order.")
    elif estimate.status == "approved":
        messages.error(request, "An approved estimate cannot be rejected.")
    elif estimate.status == "rejected":
        messages.info(request, f"Estimate from {estimate.vendor} is already rejected.")
    elif estimate.status != "pending":
        messages.error(request, "Only a pending estimate can be rejected.")
    else:
        with transaction.atomic():
            estimate.status = "rejected"
            estimate.save(update_fields=["status"])
            record_event(
                action="VENDOR_ESTIMATE_REJECTED",
                instance=estimate,
                actor=request.user,
                request=request,
                old_values={"status": "pending"},
                new_values={"vendor": str(estimate.vendor), "amount": estimate.amount, "status": "rejected"},
                reason="Vendor estimate rejected in COL360.",
                property_id=work_order.unit.property_id,
            )
        messages.success(request, f"Estimate from {estimate.vendor} was rejected.")

    return redirect("portal:work_order_detail", work_order_id=work_order.id)


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def request_vendor_quotes(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related("unit__property"),
        pk=work_order_id,
    )

    if work_order.status in ["completed", "cancelled"]:
        messages.error(request, "Quotes cannot be requested for a completed or cancelled work order.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    requested_vendor_ids = work_order.quote_requests.exclude(
        status__in=["declined", "expired", "cancelled"],
    ).values_list("vendor_id", flat=True)
    vendor_queryset = Vendor.objects.filter(status="active").exclude(
        id__in=requested_vendor_ids,
    ).order_by("company_name", "name")

    form = VendorQuoteRequestForm(
        request.POST or None,
        vendor_queryset=vendor_queryset,
        initial={
            "scope": work_order.description,
            "response_due": timezone.localdate() + timedelta(days=3),
        },
    )

    if request.method == "POST" and form.is_valid():
        vendors = list(form.cleaned_data["vendors"])
        response_due = form.cleaned_data["response_due"]
        scope = form.cleaned_data["scope"]
        instructions = form.cleaned_data["instructions"]
        subject = f"Quote requested for Work Order #{work_order.id}: {work_order.title}"
        due_text = response_due.strftime("%b %d, %Y") if response_due else "as soon as practical"

        messages_to_send = []
        for vendor in vendors:
            body = (
                f"Hello {vendor.name or vendor.company_name},\n\n"
                f"Please provide a quote for the following work at "
                f"{work_order.unit.property.street_address}:\n\n{scope}\n\n"
                f"Requested response: {due_text}.\n"
            )
            if instructions:
                body += f"\nAdditional instructions:\n{instructions}\n"
            messages_to_send.append(
                (subject, body, settings.DEFAULT_FROM_EMAIL, [vendor.email])
            )

        try:
            send_mass_mail(tuple(messages_to_send), fail_silently=False)
        except Exception:
            messages.error(
                request,
                "The quote requests could not be emailed. No requests were recorded; verify the email configuration and try again.",
            )
        else:
            sent_at = timezone.now()
            with transaction.atomic():
                for vendor in vendors:
                    quote_request = VendorQuoteRequest.objects.create(
                        work_order=work_order,
                        vendor=vendor,
                        status="sent",
                        scope=scope,
                        instructions=instructions,
                        response_due=response_due,
                        delivery_channel="email",
                        requested_by=request.user,
                        sent_at=sent_at,
                    )
                    record_event(
                        action="VENDOR_QUOTE_REQUEST_SENT",
                        instance=quote_request,
                        actor=request.user,
                        request=request,
                        old_values={},
                        new_values={
                            "vendor": str(vendor),
                            "status": "sent",
                            "response_due": response_due,
                        },
                        reason="Vendor quote requested through COL360.",
                        property_id=work_order.unit.property_id,
                    )
            messages.success(
                request,
                f"Quote request sent to {len(vendors)} vendor{'s' if len(vendors) != 1 else ''}.",
            )
            return redirect("portal:work_order_detail", work_order_id=work_order.id)

    return render(request, "portal/request_vendor_quotes.html", {
        "form": form,
        "work_order": work_order,
        "section": "maintenance",
    })


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def add_vendor_estimate(request, work_order_id):
    work_order = get_object_or_404(
        WorkOrder.objects.select_related("unit__property").prefetch_related("vendor_estimates"),
        pk=work_order_id,
    )

    if work_order.status in ["completed", "cancelled"]:
        messages.error(request, "An estimate cannot be added to a completed or cancelled work order.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    quote_request = None
    request_id = request.GET.get("request_id") or request.POST.get("quote_request_id")
    if request_id:
        quote_request = get_object_or_404(
            VendorQuoteRequest.objects.select_related("vendor"),
            pk=request_id,
            work_order=work_order,
        )

    estimated_vendor_ids = work_order.vendor_estimates.values_list("vendor_id", flat=True)
    vendor_queryset = (
        Vendor.objects.filter(status="active")
        .exclude(id__in=estimated_vendor_ids)
        .order_by("company_name", "name")
    )

    if quote_request:
        vendor_queryset = Vendor.objects.filter(pk=quote_request.vendor_id)

    if not vendor_queryset.exists():
        messages.info(request, "There are no additional active vendors available for an estimate.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    form_data = request.POST.copy() if request.method == "POST" else None
    if form_data is not None and quote_request:
        form_data["vendor"] = str(quote_request.vendor_id)
        form_data["source"] = "col360"
    form = VendorEstimateForm(form_data, request.FILES or None)
    form.fields["vendor"].queryset = vendor_queryset
    form.fields["vendor"].empty_label = "Select vendor"
    if quote_request:
        form.fields["vendor"].initial = quote_request.vendor_id
        form.fields["source"].initial = "col360"

    if form.is_valid():
        with transaction.atomic():
            estimate = form.save(commit=False)
            estimate.work_order = work_order
            estimate.quote_request = quote_request
            estimate.status = "pending"
            estimate.save()
            if quote_request:
                quote_request.status = "quote_received"
                quote_request.save(update_fields=["status", "updated_at"])
            record_event(
                action="VENDOR_ESTIMATE_ADDED",
                instance=estimate,
                actor=request.user,
                request=request,
                old_values={},
                new_values={
                    "vendor": str(estimate.vendor),
                    "amount": estimate.amount,
                    "entry_method": estimate.entry_method,
                    "source": estimate.source,
                    "description": estimate.description,
                    "status": estimate.status,
                },
                reason="Vendor estimate added to work order in COL360.",
                property_id=work_order.unit.property_id,
            )
        messages.success(request, f"Estimate from {estimate.vendor} was added for ${estimate.amount:,.2f}.")
        return redirect("portal:work_order_detail", work_order_id=work_order.id)

    return render(
        request,
        "portal/add_vendor_estimate.html",
        {
            "form": form,
            "work_order": work_order,
            "quote_request": quote_request,
            "section": "maintenance",
        },
    )

@staff_member_required(login_url="/admin/login/")
def maintenance_property_options(request):
    property_id = request.GET.get("property_id")

    if not property_id:
        return JsonResponse({
            "is_multi_unit": False,
            "units": [],
        })

    property_obj = get_object_or_404(
        Property,
        pk=property_id,
    )

    units = (
        property_obj.units
        .exclude(status="inactive")
        .order_by("unit_number")
    )

    unit_data = [
        {
            "id": unit.id,
            "label": (
                f"Unit {unit.unit_number}"
                if unit.unit_number
                else "Main Unit"
            ),
        }
        for unit in units
    ]

    return JsonResponse({
        "is_multi_unit": property_obj.is_multi_unit,
        "units": unit_data,
    })


@staff_member_required(login_url="/admin/login/")
def maintenance_unit_options(request):
    unit_id = request.GET.get("unit_id")

    if not unit_id:
        return JsonResponse({
            "leases": [],
            "tenants": [],
        })

    leases = (
        Lease.objects
        .filter(
            unit_id=unit_id,
            status="active",
        )
        .order_by("-start_date")
    )

    lease_data = [
        {
            "id": lease.id,
            "label": (
                f"{lease.start_date:%b %d, %Y} - "
                f"{lease.end_date:%b %d, %Y}"
            ),
        }
        for lease in leases
    ]

    tenants = (
        TenantProfile.objects
        .filter(
            lease_memberships__lease__in=leases,
            is_active=True,
        )
        .distinct()
        .order_by("last_name", "first_name")
    )

    tenant_data = [
        {
            "id": tenant.id,
            "label": str(tenant),
        }
        for tenant in tenants
    ]

    return JsonResponse({
        "leases": lease_data,
        "tenants": tenant_data,
    })

@staff_member_required(login_url="/admin/login/")
def maintenance_lease_options(request):
    lease_id = request.GET.get("lease_id")

    if not lease_id:
        return JsonResponse({
            "tenants": [],
        })

    tenants = (
        TenantProfile.objects
        .filter(
            lease_memberships__lease_id=lease_id,
            is_active=True,
        )
        .distinct()
        .order_by(
            "last_name",
            "first_name",
        )
    )

    tenant_data = [
        {
            "id": tenant.id,
            "label": str(tenant),
        }
        for tenant in tenants
    ]

    return JsonResponse({
        "tenants": tenant_data,
    })

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_vendor(request):
    vendor_form = VendorForm(
        request.POST or None
    )

    trade_form = VendorTradeForm(
        request.POST or None
    )

    if vendor_form.is_valid() and trade_form.is_valid():
        with transaction.atomic():
            vendor = vendor_form.save()

            for trade in trade_form.cleaned_data["trades"]:
                VendorTrade.objects.create(
                    vendor=vendor,
                    trade=trade,
                )

        messages.success(
            request,
            f"{vendor} was created successfully."
        )

        return redirect(
            "portal:vendor_detail",
            vendor_id=vendor.id,
        )

    return render(
        request,
        "portal/vendor_form.html",
        {
            "vendor_form": vendor_form,
            "trade_form": trade_form,
            "page_heading": "Add Vendor",
            "submit_label": "Create Vendor",
            "section": "vendors",
        },
    )


@staff_member_required(login_url="/admin/login/")
def vendor_detail(request, vendor_id):
    vendor = get_object_or_404(
        Vendor.objects.prefetch_related(
            "trades",
            "work_order_assignments__work_order__unit__property",
            "estimates__work_order",
            "invoices__work_order",
        ),
        pk=vendor_id,
    )

    return render(
        request,
        "portal/vendor_detail.html",
        {
            "vendor": vendor,
            "section": "vendors",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_vendor(request, vendor_id):
    vendor = get_object_or_404(
        Vendor.objects.prefetch_related(
            "trades"
        ),
        pk=vendor_id,
    )

    current_trades = list(
        vendor.trades.values_list(
            "trade",
            flat=True,
        )
    )

    vendor_form = VendorForm(
        request.POST or None,
        instance=vendor,
    )

    trade_form = VendorTradeForm(
        request.POST or None,
        initial={
            "trades": current_trades,
        },
    )

    if vendor_form.is_valid() and trade_form.is_valid():
        with transaction.atomic():
            vendor = vendor_form.save()

            selected_trades = set(
                trade_form.cleaned_data["trades"]
            )

            existing_trades = set(
                vendor.trades.values_list(
                    "trade",
                    flat=True,
                )
            )

            for trade in selected_trades - existing_trades:
                VendorTrade.objects.create(
                    vendor=vendor,
                    trade=trade,
                )

            vendor.trades.filter(
                trade__in=existing_trades - selected_trades
            ).delete()

        messages.success(
            request,
            f"{vendor} was updated successfully."
        )

        return redirect(
            "portal:vendor_detail",
            vendor_id=vendor.id,
        )

    return render(
        request,
        "portal/vendor_form.html",
        {
            "vendor_form": vendor_form,
            "trade_form": trade_form,
            "vendor": vendor,
            "page_heading": "Edit Vendor",
            "submit_label": "Save Changes",
            "section": "vendors",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_property(request):
    form = PropertyForm(request.POST or None)

    if form.is_valid():
        with transaction.atomic():
            property_obj = form.save(commit=False)
            property_obj.created_by = request.user
            property_obj.save()

            PropertyUnit.objects.create(
                property=property_obj,
                unit_number=property_obj.unit_number,
                beds=property_obj.bedrooms,
                baths=(
                    (property_obj.bathrooms_full or 0)
                    + ((property_obj.bathrooms_half or 0) * 0.5)
                ),
                sqft=property_obj.sqft,
            )

            tracked_fields = [
                "street_address", "unit_number", "city", "state", "zip_code",
                "county", "subdivision", "property_type", "property_type_other",
                "year_built", "bedrooms", "bathrooms_full", "bathrooms_half",
                "sqft", "lot_size_sqft", "management_status", "is_multi_unit",
                "notes",
            ]
            record_event(
                action="PROPERTY_CREATED",
                instance=property_obj,
                actor=request.user,
                request=request,
                old_values={},
                new_values=snapshot(property_obj, tracked_fields),
                reason="Property created in COL360.",
                property_id=property_obj.id,
            )

        messages.success(
            request,
            f"{property_obj.full_address} was created successfully."
        )
        return redirect("portal:property_detail", property_id=property_obj.id)

    return render(
        request,
        "portal/property_form.html",
        {
            "form": form,
            "page_heading": "Add Property",
            "submit_label": "Create Property",
            "section": "properties",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_property(request, property_id):
    property_obj = get_object_or_404(Property, pk=property_id)

    tracked_fields = [
        "street_address", "unit_number", "city", "state", "zip_code",
        "county", "subdivision", "property_type", "property_type_other",
        "year_built", "bedrooms", "bathrooms_full", "bathrooms_half",
        "sqft", "lot_size_sqft", "management_status", "is_multi_unit",
        "notes",
    ]
    before = snapshot(property_obj, tracked_fields)

    form = PropertyForm(request.POST or None, instance=property_obj)

    if form.is_valid():
        candidate = form.save(commit=False)
        after = snapshot(candidate, tracked_fields)
        old_values, new_values = changed_values(before, after)

        if not old_values:
            messages.info(request, "No property information changed.")
            return redirect("portal:property_detail", property_id=property_obj.id)

        with transaction.atomic():
            property_obj = form.save()

            primary_unit = PropertyUnit.objects.filter(
                property=property_obj
            ).order_by("id").first()

            if primary_unit:
                primary_unit.unit_number = property_obj.unit_number
                primary_unit.beds = property_obj.bedrooms
                primary_unit.baths = (
                    (property_obj.bathrooms_full or 0)
                    + ((property_obj.bathrooms_half or 0) * 0.5)
                )
                primary_unit.sqft = property_obj.sqft
                primary_unit.save(
                    update_fields=[
                        "unit_number", "beds", "baths", "sqft", "updated_at",
                    ]
                )

            record_event(
                action="PROPERTY_UPDATED",
                instance=property_obj,
                actor=request.user,
                request=request,
                old_values=old_values,
                new_values=new_values,
                reason="Property information updated in COL360.",
                property_id=property_obj.id,
            )

        messages.success(
            request,
            f"{property_obj.full_address} was updated successfully."
        )
        return redirect("portal:property_detail", property_id=property_obj.id)

    return render(
        request,
        "portal/property_form.html",
        {
            "form": form,
            "property_obj": property_obj,
            "page_heading": "Edit Property",
            "submit_label": "Save Changes",
            "section": "properties",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_property_unit(request, property_id):
    property_obj = get_object_or_404(Property, pk=property_id)

    if (
        property_obj.property_type == "single_family_residential"
        or not property_obj.is_multi_unit
    ):
        messages.error(
            request,
            "Units can only be added to an eligible property marked as Multi-Unit."
        )
        return redirect("portal:property_detail", property_id=property_obj.id)

    form = PropertyUnitForm(request.POST or None, property_obj=property_obj)

    if form.is_valid():
        with transaction.atomic():
            unit = form.save(commit=False)
            unit.property = property_obj
            unit.save()

            tracked_fields = [
                "unit_number", "beds", "bathrooms_full", "bathrooms_half",
                "sqft", "market_rent", "status",
            ]
            record_event(
                action="PROPERTY_UNIT_ADDED",
                instance=unit,
                actor=request.user,
                request=request,
                old_values={},
                new_values=snapshot(unit, tracked_fields),
                reason="Rentable unit added in Property 360.",
                property_id=property_obj.id,
            )

        messages.success(
            request,
            f"Unit {unit.unit_number or 'Main Unit'} was added."
        )
        return redirect("portal:property_detail", property_id=property_obj.id)

    return render(
        request,
        "portal/property_unit_form.html",
        {
            "form": form,
            "property_obj": property_obj,
            "page_heading": "Add Unit",
            "submit_label": "Create Unit",
            "section": "properties",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_property_unit(request, property_id, unit_id):
    property_obj = get_object_or_404(Property, pk=property_id)

    if (
        property_obj.property_type == "single_family_residential"
        or not property_obj.is_multi_unit
    ):
        messages.error(
            request,
            "Unit management is only available for an eligible property marked as Multi-Unit."
        )
        return redirect("portal:property_detail", property_id=property_obj.id)

    unit = get_object_or_404(
        PropertyUnit,
        pk=unit_id,
        property=property_obj,
    )

    tracked_fields = [
        "unit_number", "beds", "bathrooms_full", "bathrooms_half",
        "sqft", "market_rent", "status",
    ]
    before = snapshot(unit, tracked_fields)

    form = PropertyUnitForm(
        request.POST or None,
        instance=unit,
        property_obj=property_obj,
    )

    if form.is_valid():
        candidate = form.save(commit=False)
        after = snapshot(candidate, tracked_fields)
        old_values, new_values = changed_values(before, after)

        if not old_values:
            messages.info(request, "No unit information changed.")
            return redirect("portal:property_detail", property_id=property_obj.id)

        with transaction.atomic():
            unit = form.save()
            record_event(
                action="PROPERTY_UNIT_UPDATED",
                instance=unit,
                actor=request.user,
                request=request,
                old_values=old_values,
                new_values=new_values,
                reason="Rentable unit updated in Property 360.",
                property_id=property_obj.id,
            )

        messages.success(
            request,
            f"Unit {unit.unit_number or 'Main Unit'} was updated."
        )
        return redirect("portal:property_detail", property_id=property_obj.id)

    return render(
        request,
        "portal/property_unit_form.html",
        {
            "form": form,
            "property_obj": property_obj,
            "unit": unit,
            "page_heading": "Edit Unit",
            "submit_label": "Save Changes",
            "section": "properties",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_owner(request):
    form = OwnerProfileForm(
        request.POST or None
    )

    if form.is_valid():
        owner = form.save()

        messages.success(
            request,
            f"{owner} was created successfully."
        )

        return redirect(
            "portal:owner_detail",
            owner_id=owner.id,
        )

    return render(
        request,
        "portal/owner_form.html",
        {
            "form": form,
            "page_heading": "Add Owner",
            "submit_label": "Create Owner",
            "section": "owners",
        },
    )


@staff_member_required(login_url="/admin/login/")
def owner_detail(request, owner_id):
    owner = get_object_or_404(
        OwnerProfile.objects.prefetch_related(
            "property_ownerships__property"
        ),
        pk=owner_id,
    )

    return render(
        request,
        "portal/owner_detail.html",
        {
            "owner": owner,
            "section": "owners",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_owner(request, owner_id):
    owner = get_object_or_404(
        OwnerProfile,
        pk=owner_id,
    )

    form = OwnerProfileForm(
        request.POST or None,
        instance=owner,
    )

    if form.is_valid():
        owner = form.save()

        messages.success(
            request,
            f"{owner} was updated successfully."
        )

        return redirect(
            "portal:owner_detail",
            owner_id=owner.id,
        )

    return render(
        request,
        "portal/owner_form.html",
        {
            "form": form,
            "owner": owner,
            "page_heading": "Edit Owner",
            "submit_label": "Save Changes",
            "section": "owners",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_property_ownership(request, property_id):
    property_obj = get_object_or_404(
        Property,
        pk=property_id,
    )

    form = PropertyOwnershipForm(
        request.POST or None,
        property_obj=property_obj,
    )

    if form.is_valid():
        with transaction.atomic():
            ownership = form.save(commit=False)
            ownership.property = property_obj
            ownership.save()

            tracked_fields = [
                "owner",
                "ownership_percentage",
                "is_primary_contact",
                "start_date",
                "end_date",
            ]
            record_event(
                action="PROPERTY_OWNERSHIP_ADDED",
                instance=ownership,
                actor=request.user,
                request=request,
                old_values={},
                new_values=snapshot(ownership, tracked_fields),
                reason="Owner added to property in Property 360.",
                property_id=property_obj.id,
            )

        messages.success(
            request,
            f"{ownership.owner} was added to this property."
        )

        return redirect(
            "portal:property_detail",
            property_id=property_obj.id,
        )

    return render(
        request,
        "portal/property_ownership_form.html",
        {
            "form": form,
            "property_obj": property_obj,
            "page_heading": "Add Owner to Property",
            "submit_label": "Save Ownership",
            "section": "properties",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_property_ownership(
    request,
    property_id,
    ownership_id,
):
    property_obj = get_object_or_404(
        Property,
        pk=property_id,
    )

    ownership = get_object_or_404(
        PropertyOwnership,
        pk=ownership_id,
        property=property_obj,
    )

    tracked_fields = [
        "owner",
        "ownership_percentage",
        "is_primary_contact",
        "start_date",
        "end_date",
    ]
    before = snapshot(ownership, tracked_fields)

    form = PropertyOwnershipForm(
        request.POST or None,
        instance=ownership,
        property_obj=property_obj,
    )

    if form.is_valid():
        candidate = form.save(commit=False)
        after = snapshot(candidate, tracked_fields)
        old_values, new_values = changed_values(before, after)

        if not old_values:
            messages.info(request, "No ownership information changed.")
            return redirect(
                "portal:property_detail",
                property_id=property_obj.id,
            )

        with transaction.atomic():
            ownership = form.save()
            record_event(
                action="PROPERTY_OWNERSHIP_UPDATED",
                instance=ownership,
                actor=request.user,
                request=request,
                old_values=old_values,
                new_values=new_values,
                reason="Ownership information updated in Property 360.",
                property_id=property_obj.id,
            )

        messages.success(
            request,
            "Ownership record was updated successfully."
        )

        return redirect(
            "portal:property_detail",
            property_id=property_obj.id,
        )

    return render(
        request,
        "portal/property_ownership_form.html",
        {
            "form": form,
            "property_obj": property_obj,
            "ownership": ownership,
            "page_heading": "Edit Ownership",
            "submit_label": "Save Changes",
            "section": "properties",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_POST
def remove_property_ownership(request, property_id, ownership_id):
    property_obj = get_object_or_404(
        Property,
        pk=property_id,
    )

    ownership = get_object_or_404(
        PropertyOwnership.objects.select_related("owner"),
        pk=ownership_id,
        property=property_obj,
    )

    owner = ownership.owner
    property_address = property_obj.full_address
    tracked_fields = [
        "owner",
        "ownership_percentage",
        "is_primary_contact",
        "start_date",
        "end_date",
    ]
    removed_values = snapshot(ownership, tracked_fields)

    with transaction.atomic():
        record_event(
            action="PROPERTY_OWNERSHIP_REMOVED",
            instance=ownership,
            actor=request.user,
            request=request,
            old_values=removed_values,
            new_values={},
            reason="Owner removed from property in COL360.",
            property_id=property_obj.id,
        )
        ownership.delete()

    messages.success(
        request,
        (
            f"{property_address} was removed from "
            f"{owner}'s ownership records. "
            "The property and owner were not deleted."
        ),
    )

    return redirect(
        "portal:owner_detail",
        owner_id=owner.id,
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_tenant(request):
    next_url = request.GET.get("next") or request.POST.get("next")

    form = TenantProfileForm(
        request.POST or None
    )

    if form.is_valid():
        tenant = form.save()

        messages.success(
            request,
            f"{tenant} was created successfully."
        )

        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            separator = "&" if "?" in next_url else "?"

            return redirect(
                f"{next_url}{separator}tenant_id={tenant.id}"
            )

        return redirect(
            "portal:tenant_detail",
            tenant_id=tenant.id,
        )

    return render(
        request,
        "portal/tenant_form.html",
        {
            "form": form,
            "next_url": next_url,
            "page_heading": "Add Tenant",
            "submit_label": "Create Tenant",
            "section": "tenants",
        },
    )


@staff_member_required(login_url="/admin/login/")
def tenant_detail(request, tenant_id):
    tenant = get_object_or_404(
        TenantProfile.objects.prefetch_related(
            "lease_memberships__lease__unit__property",
            "maintenance_requests__unit__property",
        ),
        pk=tenant_id,
    )

    return render(
        request,
        "portal/tenant_detail.html",
        {
            "tenant": tenant,
            "section": "tenants",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_tenant(request, tenant_id):
    tenant = get_object_or_404(
        TenantProfile,
        pk=tenant_id,
    )

    form = TenantProfileForm(
        request.POST or None,
        instance=tenant,
    )

    if form.is_valid():
        tenant = form.save()

        messages.success(
            request,
            f"{tenant} was updated successfully."
        )

        return redirect(
            "portal:tenant_detail",
            tenant_id=tenant.id,
        )

    return render(
        request,
        "portal/tenant_form.html",
        {
            "form": form,
            "tenant": tenant,
            "page_heading": "Edit Tenant",
            "submit_label": "Save Changes",
            "section": "tenants",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_lease(request):
    form = LeaseForm(
        request.POST or None,
        include_tenants=True,
        require_active_property=True,
        generic_property_select=True,
    )

    if form.is_valid():
        with transaction.atomic():
            lease = form.save()

            LeaseTenant.objects.create(
                lease=lease,
                tenant=form.cleaned_data["primary_tenant"],
                role="primary",
                is_financially_responsible=True,
            )

            for tenant in form.cleaned_data["co_tenants"]:
                LeaseTenant.objects.create(
                    lease=lease,
                    tenant=tenant,
                    role="co_tenant",
                    is_financially_responsible=True,
                )

            if lease.status == "active" and lease.unit.status != "occupied":
                lease.unit.status = "occupied"
                lease.unit.save(update_fields=["status"])

        messages.success(
            request,
            "Lease and tenant membership were created successfully."
        )

        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    return render(
        request,
        "portal/lease_form.html",
        {
            "form": form,
            "page_heading": "Create Lease",
            "submit_label": "Create Lease",
            "section": "leases",
            "generic_property_select": True,
            "multi_unit_property_ids": list(
                Property.objects
                .filter(
                    management_status="active",
                    is_multi_unit=True,
                    units__isnull=False,
                )
                .distinct()
                .values_list("id", flat=True)
            ),
            "unit_property_map": {
                str(unit.id): unit.property_id
                for unit in PropertyUnit.objects
                .filter(
                    property__management_status="active",
                    property__is_multi_unit=True,
                )
                .exclude(unit_number="")
                .only("id", "property_id")
            },
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_unit_lease(
    request,
    property_id,
    unit_id,
):
    property_obj = get_object_or_404(
        Property,
        pk=property_id,
    )

    unit = get_object_or_404(
        PropertyUnit,
        pk=unit_id,
        property=property_obj,
    )

    # Foundation authorization rule: an executed Property Management
    # Agreement is represented by Active management status. Do not allow
    # lease creation until staff has explicitly made the property Active.
    if property_obj.management_status != "active":
        messages.error(
            request,
            (
                "Lease creation unavailable. This property must have Active "
                "management status before a lease can be created. Confirm "
                "that an executed Property Management Agreement is in place "
                "and change the property status to Active."
            ),
        )
        return redirect(
            "portal:property_detail",
            property_id=property_obj.id,
        )

    form = LeaseForm(
        request.POST or None,
        locked_unit=unit,
        include_tenants=True,
        require_active_property=True,
    )

    if form.is_valid():
        with transaction.atomic():
            lease = form.save(commit=False)

            # Never trust the submitted unit value.
            lease.unit = unit
            lease.save()

            LeaseTenant.objects.create(
                lease=lease,
                tenant=form.cleaned_data["primary_tenant"],
                role="primary",
                is_financially_responsible=True,
            )

            for tenant in form.cleaned_data["co_tenants"]:
                LeaseTenant.objects.create(
                    lease=lease,
                    tenant=tenant,
                    role="co_tenant",
                    is_financially_responsible=True,
                )

            # Keep internal occupancy synchronized with lease status.
            if lease.status == "active" and unit.status != "occupied":
                unit.status = "occupied"
                unit.save(update_fields=["status"])

        messages.success(
            request,
            "Lease and tenant membership were created successfully."
        )

        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    return render(
        request,
        "portal/lease_form.html",
        {
            "form": form,
            "property_obj": property_obj,
            "unit": unit,
            "page_heading": "Create Lease",
            "submit_label": "Create Lease",
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
def lease_detail(request, lease_id):
    lease = get_object_or_404(
        Lease.objects.select_related(
            "unit__property",
        ).prefetch_related(
            "lease_tenants__tenant",
            "maintenance_requests",
            "intent_records__recorded_by",
        ),
        pk=lease_id,
    )

    today = timezone.localdate()

    current_intent = (
        lease.intent_records
        .filter(is_active=True)
        .select_related("recorded_by")
        .order_by("-created_at")
        .first()
    )

    upcoming_lease_exists = (
        Lease.objects
        .filter(
            unit=lease.unit,
            status__in=["draft", "pending"],
            start_date__gt=lease.end_date,
        )
        .exclude(pk=lease.pk)
        .exists()
    )

    show_renewal_reminder = False
    can_record_lease_intent = False
    can_create_renewal_draft = False
    lease_days_remaining = None
    intent_deadline = None
    intent_days_remaining = None

    if lease.status == "active":
        lease_days_remaining = (lease.end_date - today).days

        # Renewal workflow timing:
        # - At 70 days: staff may record renew/vacate intent.
        # - At 60 days: a recorded renewal intent may become a Draft renewal.
        can_record_lease_intent = (
            0 <= lease_days_remaining <= 70
            and not upcoming_lease_exists
        )
        can_create_renewal_draft = (
            0 <= lease_days_remaining <= 60
            and not upcoming_lease_exists
            and current_intent is not None
            and current_intent.intent == "renew"
        )

        if can_record_lease_intent and current_intent is None:
            show_renewal_reminder = True
            intent_deadline = lease.end_date - timedelta(days=60)
            intent_days_remaining = (intent_deadline - today).days

    audit_events = _prepare_audit_events(
        AuditEvent.objects.filter(
            entity_type="Lease",
            entity_id=str(lease.id),
        ).select_related("actor")[:25]
    )

    return render(
        request,
        "portal/lease_detail.html",
        {
            "lease": lease,
            "current_intent": current_intent,
            "upcoming_lease_exists": upcoming_lease_exists,
            "show_renewal_reminder": show_renewal_reminder,
            "can_record_lease_intent": can_record_lease_intent,
            "can_create_renewal_draft": can_create_renewal_draft,
            "lease_days_remaining": lease_days_remaining,
            "intent_deadline": intent_deadline,
            "intent_days_remaining": intent_days_remaining,
            "audit_events": audit_events,
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def record_renewal_intent(request, lease_id):
    lease = get_object_or_404(
        Lease.objects.select_related("unit__property"),
        pk=lease_id,
    )

    if lease.status != "active":
        messages.error(
            request,
            "Renewal intent can only be recorded for an Active lease.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    days_remaining = (lease.end_date - timezone.localdate()).days
    if not 0 <= days_remaining <= 70:
        messages.error(
            request,
            "Renewal intent becomes available 70 days before lease expiration.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    if request.method == "POST":
        form = LeaseRenewalIntentForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                # Preserve any prior intent in the audit trail.
                prior_intents = lease.intent_records.filter(
                    is_active=True
                )

                for intent in prior_intents:
                    intent.is_active = False
                    intent.withdrawn_at = timezone.now()
                    intent.withdrawn_by = request.user
                    intent.save(
                        update_fields=[
                            "is_active",
                            "withdrawn_at",
                            "withdrawn_by",
                        ]
                    )

                LeaseIntentRecord.objects.create(
                    lease=lease,
                    intent="renew",
                    response_date=form.cleaned_data[
                        "response_date"
                    ],
                    notice_method=form.cleaned_data[
                        "notice_method"
                    ],
                    notes=form.cleaned_data["notes"],
                    recorded_by=request.user,
                )

                record_event(
                    action="RENEWAL_INTENT_RECORDED",
                    instance=lease,
                    actor=request.user,
                    request=request,
                    old_values={},
                    new_values={
                        "response_date": form.cleaned_data["response_date"],
                        "notice_method": form.cleaned_data["notice_method"],
                        "notes": form.cleaned_data["notes"],
                    },
                    reason="Tenant renewal intent recorded by staff.",
                    property_id=lease.unit.property_id,
                )

            messages.success(
                request,
                "Tenant renewal intent was recorded. "
                "No renewal lease was created automatically.",
            )
            return redirect(
                "portal:lease_detail",
                lease_id=lease.id,
            )
    else:
        form = LeaseRenewalIntentForm(
            initial={
                "response_date": timezone.localdate(),
            }
        )

    return render(
        request,
        "portal/lease_intent_form.html",
        {
            "form": form,
            "lease": lease,
            "page_heading": "Record Renewal Intent",
            "intro_text": (
                "Record the tenant's stated intent to renew. "
                "This does not create a renewal lease."
            ),
            "submit_label": "Record Renewal Intent",
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def record_vacate_intent(request, lease_id):
    lease = get_object_or_404(
        Lease.objects.select_related("unit__property"),
        pk=lease_id,
    )

    if lease.status != "active":
        messages.error(
            request,
            "Move-out intent can only be recorded for an Active lease.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    days_remaining = (lease.end_date - timezone.localdate()).days
    if not 0 <= days_remaining <= 70:
        messages.error(
            request,
            "Renewal or move-out intent becomes available 70 days before lease expiration.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    if request.method == "POST":
        form = LeaseVacateIntentForm(
            request.POST,
            lease=lease,
        )

        if form.is_valid():
            with transaction.atomic():
                # If the tenant previously indicated renewal, retain that
                # record historically and make the move-out intent current.
                prior_intents = lease.intent_records.filter(
                    is_active=True
                )

                for intent in prior_intents:
                    intent.is_active = False
                    intent.withdrawn_at = timezone.now()
                    intent.withdrawn_by = request.user
                    intent.save(
                        update_fields=[
                            "is_active",
                            "withdrawn_at",
                            "withdrawn_by",
                        ]
                    )

                LeaseIntentRecord.objects.create(
                    lease=lease,
                    intent="vacate",
                    response_date=form.cleaned_data[
                        "notice_received_date"
                    ],
                    planned_move_out_date=form.cleaned_data[
                        "planned_move_out_date"
                    ],
                    notice_method=form.cleaned_data[
                        "notice_method"
                    ],
                    notes=form.cleaned_data["notes"],
                    recorded_by=request.user,
                )

                # Notice means tenancy is still operational, but staff
                # now knows the tenant plans to leave.
                lease.status = "notice"
                lease.save(
                    update_fields=[
                        "status",
                        "updated_at",
                    ]
                )

                record_event(
                    action="MOVE_OUT_NOTICE_RECORDED",
                    instance=lease,
                    actor=request.user,
                    request=request,
                    old_values={"status": "active"},
                    new_values={
                        "status": "notice",
                        "notice_received_date": form.cleaned_data["notice_received_date"],
                        "planned_move_out_date": form.cleaned_data["planned_move_out_date"],
                        "notice_method": form.cleaned_data["notice_method"],
                        "notes": form.cleaned_data["notes"],
                    },
                    reason="Tenant move-out notice recorded by staff.",
                    property_id=lease.unit.property_id,
                )

            messages.success(
                request,
                "Tenant move-out notice was recorded. "
                "The lease is now on Notice.",
            )
            return redirect(
                "portal:lease_detail",
                lease_id=lease.id,
            )
    else:
        form = LeaseVacateIntentForm(
            lease=lease,
            initial={
                "notice_received_date": timezone.localdate(),
                "planned_move_out_date": lease.end_date,
            },
        )

    return render(
        request,
        "portal/lease_intent_form.html",
        {
            "form": form,
            "lease": lease,
            "page_heading": "Record Move-Out Intent",
            "intro_text": (
                "Record the tenant's notice and planned move-out date. "
                "The lease will remain operational and will move to Notice status."
            ),
            "submit_label": "Record Move-Out Notice",
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_POST
def withdraw_move_out_notice(request, lease_id):
    lease = get_object_or_404(
        Lease.objects.select_related("unit__property"),
        pk=lease_id,
    )

    current_intent = (
        lease.intent_records
        .filter(
            is_active=True,
            intent="vacate",
        )
        .first()
    )

    if lease.status != "notice" or current_intent is None:
        messages.error(
            request,
            "There is no active move-out notice to withdraw.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    conflicting_lease = (
        Lease.objects
        .filter(
            unit=lease.unit,
            status__in=[
                "draft",
                "pending",
                "active",
                "notice",
            ],
            start_date__lte=lease.end_date,
            end_date__gte=lease.start_date,
        )
        .exclude(pk=lease.pk)
        .exists()
    )

    if conflicting_lease:
        messages.error(
            request,
            "The move-out notice cannot be withdrawn because "
            "another lease conflicts with this lease period.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    with transaction.atomic():
        current_intent.is_active = False
        current_intent.withdrawn_at = timezone.now()
        current_intent.withdrawn_by = request.user
        current_intent.save(
            update_fields=[
                "is_active",
                "withdrawn_at",
                "withdrawn_by",
            ]
        )

        lease.status = "active"
        lease.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        record_event(
            action="MOVE_OUT_NOTICE_WITHDRAWN",
            instance=lease,
            actor=request.user,
            request=request,
            old_values={"status": "notice"},
            new_values={"status": "active"},
            reason="Tenant move-out notice withdrawn by staff.",
            property_id=lease.unit.property_id,
            metadata={"intent_record_id": current_intent.id},
        )

    messages.success(
        request,
        "Move-out notice was withdrawn. "
        "The lease is Active again.",
    )

    return redirect(
        "portal:lease_detail",
        lease_id=lease.id,
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def create_lease_renewal(request, lease_id):
    """Create a new Draft lease that renews an existing lease."""
    source_lease = get_object_or_404(
        Lease.objects
        .select_related("unit__property")
        .prefetch_related("lease_tenants__tenant"),
        pk=lease_id,
    )

    if source_lease.status not in ["active", "notice"]:
        messages.error(
            request,
            "Only an Active lease or a lease on Notice can be renewed.",
        )
        return redirect("portal:lease_detail", lease_id=source_lease.id)

    days_remaining = (source_lease.end_date - timezone.localdate()).days
    if not 0 <= days_remaining <= 60:
        messages.error(
            request,
            "Create Renewal Draft becomes available 60 days before lease expiration.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=source_lease.id,
        )

    renewal_intent_exists = (
        source_lease.intent_records
        .filter(
            is_active=True,
            intent="renew",
        )
        .exists()
    )

    if not renewal_intent_exists:
        messages.error(
            request,
            "Record the tenant's renewal intent before creating a renewal Draft.",
        )
        return redirect(
            "portal:lease_detail",
            lease_id=source_lease.id,
        )

    primary_membership = (
        source_lease.lease_tenants
        .filter(role="primary")
        .select_related("tenant")
        .first()
    )

    if not primary_membership:
        messages.error(
            request,
            "This lease does not have a Primary Tenant. "
            "Add a Primary Tenant before creating a renewal.",
        )
        return redirect("portal:lease_detail", lease_id=source_lease.id)

    renewal_start = source_lease.end_date + timedelta(days=1)

    initial = {
        "start_date": renewal_start,
        "monthly_rent": source_lease.monthly_rent,
        "security_deposit": source_lease.security_deposit,
        "status": "draft",
        "primary_tenant": primary_membership.tenant,
    }

    if request.method == "POST":
        form = LeaseForm(
            request.POST,
            locked_unit=source_lease.unit,
            include_tenants=True,
        )
    else:
        form = LeaseForm(
            locked_unit=source_lease.unit,
            include_tenants=True,
            initial=initial,
        )

    # LeaseForm normally hides tenants who are already attached to
    # an Active/Pending/Notice lease. For a renewal, however, the
    # existing lease tenants must remain selectable because the new
    # lease begins after the current lease ends.
    source_tenant_ids = source_lease.lease_tenants.values_list(
        "tenant_id",
        flat=True,
    )

    normally_available_ids = (
        form.fields["primary_tenant"]
        .queryset
        .values_list("id", flat=True)
    )

    renewal_available_tenants = (
        TenantProfile.objects
        .filter(
            is_active=True,
        )
        .filter(
            Q(id__in=normally_available_ids)
            | Q(id__in=source_tenant_ids)
        )
        .order_by("last_name", "first_name")
    )

    form.fields["primary_tenant"].queryset = renewal_available_tenants
    form.fields["co_tenants"].queryset = renewal_available_tenants

    if form.is_valid():
        with transaction.atomic():
            renewal = form.save(commit=False)
            renewal.unit = source_lease.unit
            renewal.status = "draft"
            renewal.save()

            LeaseTenant.objects.create(
                lease=renewal,
                tenant=form.cleaned_data["primary_tenant"],
                role="primary",
                is_financially_responsible=True,
            )

            for tenant in form.cleaned_data["co_tenants"]:
                LeaseTenant.objects.create(
                    lease=renewal,
                    tenant=tenant,
                    role="co_tenant",
                    is_financially_responsible=True,
                )

            record_event(
                action="RENEWAL_DRAFT_CREATED",
                instance=renewal,
                actor=request.user,
                request=request,
                old_values={},
                new_values={
                    "status": "draft",
                    "start_date": renewal.start_date,
                    "end_date": renewal.end_date,
                    "monthly_rent": renewal.monthly_rent,
                    "security_deposit": renewal.security_deposit,
                },
                reason="Renewal Draft created from existing lease.",
                property_id=renewal.unit.property_id,
                metadata={"source_lease_id": source_lease.id},
            )

            record_event(
                action="RENEWAL_DRAFT_LINKED",
                instance=source_lease,
                actor=request.user,
                request=request,
                old_values={},
                new_values={"renewal_lease_id": renewal.id},
                reason="Renewal Draft created from this lease.",
                property_id=source_lease.unit.property_id,
            )

        messages.success(
            request,
            "Renewal Draft created successfully. "
            "The original lease was not changed.",
        )
        return redirect("portal:lease_detail", lease_id=renewal.id)

    return render(
        request,
        "portal/lease_form.html",
        {
            "form": form,
            "property_obj": source_lease.unit.property,
            "locked_unit": source_lease.unit,
            "is_renewal": True,
            "source_lease": source_lease,
            "page_heading": "Create Lease Renewal",
            "submit_label": "Create Renewal",
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_POST
def mark_lease_pending(request, lease_id):
    """Move a valid Draft lease to Pending Signature."""
    lease = get_object_or_404(
        Lease.objects.select_related("unit__property"),
        pk=lease_id,
    )

    if lease.status != "draft":
        messages.error(
            request,
            "Only Draft leases can be marked Pending Signature.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    primary_tenant_count = lease.lease_tenants.filter(
        role="primary"
    ).count()

    if primary_tenant_count != 1:
        messages.error(
            request,
            "The lease must have exactly one Primary Tenant "
            "before it can be marked Pending Signature.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    if not lease.start_date or not lease.end_date:
        messages.error(
            request,
            "The lease must have both a Start Date and End Date.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    if lease.end_date <= lease.start_date:
        messages.error(
            request,
            "The End Date must be later than the Start Date.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    if lease.monthly_rent is None or lease.monthly_rent <= 0:
        messages.error(
            request,
            "Monthly Rent must be greater than $0.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    conflicting_lease = (
        Lease.objects
        .filter(
            unit=lease.unit,
            status__in=[
                "draft",
                "pending",
                "active",
                "notice",
            ],
            start_date__lt=lease.end_date,
            end_date__gt=lease.start_date,
        )
        .exclude(pk=lease.pk)
        .order_by("start_date")
        .first()
    )

    if conflicting_lease:
        messages.error(
            request,
            "This lease overlaps another Draft, Pending, Active, "
            "or Notice lease for the property. Review the existing "
            "lease before marking this one Pending Signature.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    with transaction.atomic():
        lease.status = "pending"
        lease.save(update_fields=["status", "updated_at"])

        record_event(
            action="LEASE_MARKED_PENDING_SIGNATURE",
            instance=lease,
            actor=request.user,
            request=request,
            old_values={"status": "draft"},
            new_values={"status": "pending"},
            reason="Lease moved from Draft to Pending Signature.",
            property_id=lease.unit.property_id,
        )

    messages.success(
        request,
        "Lease was marked Pending Signature.",
    )
    return redirect("portal:lease_detail", lease_id=lease.id)


@staff_member_required(login_url="/admin/login/")
@require_POST
def activate_pending_lease(request, lease_id):
    """Deliberately activate a fully executed Pending Signature lease."""
    lease = get_object_or_404(Lease.objects.select_related("unit__property"), pk=lease_id)

    if lease.status != "pending":
        messages.error(request, "Only a Pending Signature lease can be activated.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    if not lease.signed_date:
        messages.error(request, "A Signed Date is required before this lease can be activated.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    if lease.lease_tenants.filter(role="primary").count() != 1:
        messages.error(request, "The lease must have exactly one Primary Tenant before activation.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    if not lease.start_date or not lease.end_date or lease.end_date <= lease.start_date:
        messages.error(request, "The lease must have valid Start and End Dates before activation.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    if lease.monthly_rent is None or lease.monthly_rent <= 0:
        messages.error(request, "Monthly Rent must be greater than $0 before activation.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    today = timezone.localdate()
    if lease.start_date > today:
        messages.error(request, "This lease cannot be activated before its Start Date.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    if lease.end_date < today:
        messages.error(request, "This lease has already ended and cannot be activated.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    conflict = Lease.objects.filter(
        unit=lease.unit,
        status__in=["active", "notice"],
        start_date__lt=lease.end_date,
        end_date__gt=lease.start_date,
    ).exclude(pk=lease.pk).exists()

    if conflict:
        messages.error(request, "This lease overlaps an existing Active or Notice lease for the property and cannot be activated.")
        return redirect("portal:lease_detail", lease_id=lease.id)

    with transaction.atomic():
        lease.status = "active"
        lease.save(update_fields=["status", "updated_at"])
        if lease.unit.status != "occupied":
            lease.unit.status = "occupied"
            lease.unit.save(update_fields=["status", "updated_at"])

        record_event(
            action="LEASE_ACTIVATED",
            instance=lease,
            actor=request.user,
            request=request,
            old_values={"status": "pending"},
            new_values={"status": "active"},
            reason="Executed Pending Signature lease activated by staff.",
            property_id=lease.unit.property_id,
            metadata={"signed_date": lease.signed_date},
        )

    messages.success(request, "Lease was activated successfully.")
    return redirect("portal:lease_detail", lease_id=lease.id)


@staff_member_required(login_url="/admin/login/")
@require_POST
def cancel_pending_lease(request, lease_id):
    """Cancel a Pending Signature lease without deleting its history."""
    lease = get_object_or_404(
        Lease.objects.select_related("unit__property"),
        pk=lease_id,
    )

    if lease.status != "pending":
        messages.error(
            request,
            "Only a Pending Signature lease can be cancelled.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    with transaction.atomic():
        lease.status = "cancelled"
        lease.save(update_fields=["status", "updated_at"])

        record_event(
            action="LEASE_CANCELLED",
            instance=lease,
            actor=request.user,
            request=request,
            old_values={"status": "pending"},
            new_values={"status": "cancelled"},
            reason="Pending Signature lease cancelled by staff.",
            property_id=lease.unit.property_id,
        )

    messages.success(
        request,
        "Pending lease was cancelled. The lease record was preserved for history.",
    )
    return redirect("portal:lease_detail", lease_id=lease.id)


@staff_member_required(login_url="/admin/login/")
@require_POST
def delete_draft_lease(request, lease_id):
    """Permanently delete a Draft lease only."""
    lease = get_object_or_404(
        Lease.objects.select_related("unit__property"),
        pk=lease_id,
    )

    if lease.status != "draft":
        messages.error(
            request,
            "Only Draft leases can be deleted.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    property_id = lease.unit.property_id

    with transaction.atomic():
        # LeaseTenant rows are removed by the model's CASCADE relationship.
        lease.delete()

    messages.success(
        request,
        "Draft lease was deleted successfully.",
    )
    return redirect("portal:property_detail", property_id=property_id)


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_lease(request, lease_id):
    lease = get_object_or_404(
        Lease.objects.select_related(
            "unit__property"
        ),
        pk=lease_id,
    )

    if lease.status == "cancelled":
        messages.error(
            request,
            "Cancelled leases are read-only and cannot be edited.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    # Active leases are executed records. Ordinary Edit Lease may update only
    # operational fields. Contract terms require a future Lease Amendment
    # workflow and must never be silently rewritten here.
    if lease.status == "active":
        tracked_fields = [
            "move_in_date",
            "move_out_date",
            "notes",
        ]
        before = snapshot(lease, tracked_fields)

        form = ActiveLeaseOperationalForm(
            request.POST or None,
            instance=lease,
        )

        if form.is_valid():
            candidate = form.save(commit=False)
            after = snapshot(candidate, tracked_fields)
            old_values, new_values = changed_values(before, after)

            if not old_values:
                messages.info(
                    request,
                    "No lease information changed.",
                )
                return redirect(
                    "portal:lease_detail",
                    lease_id=lease.id,
                )

            with transaction.atomic():
                lease = form.save()

                record_event(
                    action="ACTIVE_LEASE_OPERATIONAL_UPDATED",
                    instance=lease,
                    actor=request.user,
                    request=request,
                    old_values=old_values,
                    new_values=new_values,
                    reason=form.cleaned_data["change_reason"],
                    property_id=lease.unit.property_id,
                    metadata={
                        "lease_status": lease.status,
                        "protected_contract_terms": [
                            "unit",
                            "start_date",
                            "end_date",
                            "monthly_rent",
                            "security_deposit",
                            "status",
                            "signed_date",
                        ],
                    },
                )

            messages.success(
                request,
                "Active lease operational information was updated and recorded in the Audit Ledger.",
            )

            return redirect(
                "portal:lease_detail",
                lease_id=lease.id,
            )

        return render(
            request,
            "portal/lease_form.html",
            {
                "form": form,
                "lease": lease,
                "property_obj": lease.unit.property,
                "unit": lease.unit,
                "page_heading": "Update Active Lease",
                "submit_label": "Save & Record Change",
                "active_controlled_edit": True,
                "section": "leases",
            },
        )

    # Draft/Pending/Notice/etc. retain the existing edit workflow.
    form = LeaseForm(
        request.POST or None,
        instance=lease,
        locked_unit=lease.unit,
    )

    if form.is_valid():
        lease = form.save()

        unit = lease.unit

        if lease.status == "active":
            if unit.status != "occupied":
                unit.status = "occupied"
                unit.save(update_fields=["status"])
        else:
            has_active_lease = Lease.objects.filter(
                unit=unit,
                status="active",
            ).exclude(
                pk=lease.pk,
            ).exists()

            if not has_active_lease and unit.status == "occupied":
                unit.status = "vacant"
                unit.save(update_fields=["status"])

        messages.success(
            request,
            "Lease was updated successfully."
        )

        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    return render(
        request,
        "portal/lease_form.html",
        {
            "form": form,
            "lease": lease,
            "property_obj": lease.unit.property,
            "unit": lease.unit,
            "page_heading": "Edit Lease",
            "submit_label": "Save Changes",
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def add_lease_tenant(request, lease_id):
    lease = get_object_or_404(
        Lease.objects.select_related(
            "unit__property"
        ),
        pk=lease_id,
    )

    if lease.status == "cancelled":
        messages.error(
            request,
            "Cancelled leases are read-only. Tenant memberships cannot be changed.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    if request.method == "POST":
        form = LeaseTenantForm(
            request.POST,
            lease=lease,
        )
    else:
        initial = {}

        tenant_id = request.GET.get("tenant_id")

        if tenant_id:
            initial["tenant"] = tenant_id

        form = LeaseTenantForm(
            lease=lease,
            initial=initial,
        )

    if form.is_valid():
        with transaction.atomic():
            membership = form.save(commit=False)
            membership.lease = lease
            membership.save()

            record_event(
                action="LEASE_TENANT_ADDED",
                instance=lease,
                actor=request.user,
                request=request,
                old_values={},
                new_values={
                    "tenant_id": membership.tenant_id,
                    "tenant": str(membership.tenant),
                    "role": membership.role,
                    "is_financially_responsible": membership.is_financially_responsible,
                },
                reason="Tenant membership added from Lease 360.",
                property_id=lease.unit.property_id,
                metadata={"membership_id": membership.id},
            )

        messages.success(
            request,
            f"{membership.tenant} was added to the lease and recorded in the Audit Ledger."
        )

        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    return render(
        request,
        "portal/lease_tenant_form.html",
        {
            "form": form,
            "lease": lease,
            "page_heading": "Add Tenant to Lease",
            "submit_label": "Add Tenant",
            "section": "leases",
        },
    )


@staff_member_required(login_url="/admin/login/")
@require_http_methods(["GET", "POST"])
def edit_lease_tenant(
    request,
    lease_id,
    membership_id,
):
    lease = get_object_or_404(
        Lease.objects.select_related(
            "unit__property"
        ),
        pk=lease_id,
    )

    if lease.status == "cancelled":
        messages.error(
            request,
            "Cancelled leases are read-only. Tenant memberships cannot be changed.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    membership = get_object_or_404(
        LeaseTenant,
        pk=membership_id,
        lease=lease,
    )

    tenant_before = {
        "tenant_id": membership.tenant_id,
        "tenant": str(membership.tenant),
        "role": membership.role,
        "is_financially_responsible": membership.is_financially_responsible,
    }

    form = LeaseTenantForm(
        request.POST or None,
        instance=membership,
        lease=lease,
    )

    if form.is_valid():
        with transaction.atomic():
            membership = form.save()

            tenant_after = {
                "tenant_id": membership.tenant_id,
                "tenant": str(membership.tenant),
                "role": membership.role,
                "is_financially_responsible": membership.is_financially_responsible,
            }
            old_values, new_values = changed_values(
                tenant_before,
                tenant_after,
            )

            if old_values:
                record_event(
                    action="LEASE_TENANT_UPDATED",
                    instance=lease,
                    actor=request.user,
                    request=request,
                    old_values=old_values,
                    new_values=new_values,
                    reason="Tenant membership updated from Lease 360.",
                    property_id=lease.unit.property_id,
                    metadata={"membership_id": membership.id},
                )

        messages.success(
            request,
            "Tenant membership was updated successfully and recorded in the Audit Ledger."
        )

        return redirect(
            "portal:lease_detail",
            lease_id=lease.id,
        )

    return render(
        request,
        "portal/lease_tenant_form.html",
        {
            "form": form,
            "lease": lease,
            "membership": membership,
            "page_heading": "Edit Lease Tenant",
            "submit_label": "Save Changes",
            "section": "leases",
        },
    )

@staff_member_required(login_url="/admin/login/")
@require_POST
def remove_lease_tenant(request, lease_id, membership_id):
    lease = get_object_or_404(
        Lease,
        pk=lease_id,
    )

    if lease.status == "cancelled":
        messages.error(
            request,
            "Cancelled leases are read-only. Tenant memberships cannot be changed.",
        )
        return redirect("portal:lease_detail", lease_id=lease.id)

    membership = get_object_or_404(
        LeaseTenant.objects.select_related("tenant"),
        pk=membership_id,
        lease=lease,
    )

    tenant_name = str(membership.tenant)
    removed_values = {
        "tenant_id": membership.tenant_id,
        "tenant": tenant_name,
        "role": membership.role,
        "is_financially_responsible": membership.is_financially_responsible,
    }
    membership_id_value = membership.id

    with transaction.atomic():
        membership.delete()

        record_event(
            action="LEASE_TENANT_REMOVED",
            instance=lease,
            actor=request.user,
            request=request,
            old_values=removed_values,
            new_values={},
            reason="Tenant membership removed from Lease 360.",
            property_id=lease.unit.property_id,
            metadata={"membership_id": membership_id_value},
        )

    messages.success(
        request,
        f"{tenant_name} was removed from the lease and recorded in the Audit Ledger."
    )

    return redirect(
        "portal:lease_detail",
        lease_id=lease.id,
    )
