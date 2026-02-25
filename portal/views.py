"""
portal/views.py
───────────────
Custom staff-only admin portal for Col Realty.
Accessible at /portal/ — requires staff login.

Sections:
  - Dashboard  → live stats overview
  - Leads      → all leads with HubSpot status + retry
  - Listings   → buy listings management
  - Rentals    → rental listings management
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta

from leads.models import Lead
from listings.models import Listing
from rentals.models import Rental


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
        "section":       "dashboard",
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
