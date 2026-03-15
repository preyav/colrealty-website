# pages/views.py
import logging
import os

from django.conf import settings
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from listings.models import Listing
from rentals.models import Rental
from .models import Agent, LegalDocument
from django.http import Http404


BUY_TYPES = {
    "Commercial Sale", "Condo", "Duplex", "Farm", "Land", "Multi-Family",
    "Residential", "Residential Income", "Single Family", "Townhome",
}

LEASE_TYPES = ["Residential Lease", "Commercial Lease"]

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

class ColRealtyLoginView(LoginView):
    template_name = "pages/login.html"
    next_page = "index"


def login(request):
    return render(request, "pages/login.html")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _build_listing_markers(qs):
    markers = []
    for l in qs:
        if l.latitude is None or l.longitude is None:
            continue
        markers.append({
            "id":            l.id,
            "title":         l.title,
            "price":         str(l.price),
            "address":       f"{l.street_address}, {l.city}, {l.state} {l.zip_code}",
            "lat":           float(l.latitude),
            "lng":           float(l.longitude),
            "image":         l.main_image_url,
            "status":        l.status,
            "property_type": l.property_type,
            "url":           reverse("listings:listing_detail", kwargs={"pk": l.pk}),
        })
    return markers


def _build_rental_markers(qs):
    markers = []
    for r in qs:
        if r.latitude is None or r.longitude is None:
            continue
        markers.append({
            "id":      r.id,
            "title":   r.title,
            "price":   str(r.rent),
            "address": r.full_address(),
            "lat":     float(r.latitude),
            "lng":     float(r.longitude),
            "image":   r.main_image_url or "",
            "url":     reverse("rentals:detail", kwargs={"pk": r.pk}),
        })
    return markers


# ─────────────────────────────────────────────
# Core pages
# ─────────────────────────────────────────────

def home(request):
    new_listings = Listing.objects.filter(
        status="active"
    ).exclude(
        property_type__in=LEASE_TYPES
    ).order_by("-id")[:8]

    recent_rentals = Rental.objects.filter(
        status="active"
    ).order_by("-id")[:8]

    land_listings = Listing.objects.filter(
        status="active",
        property_type__in=["Land", "Farm"]
    ).order_by("-id")[:8]

    return render(request, "pages/home.html", {
        "new_listings":   new_listings,
        "recent_rentals": recent_rentals,
        "land_listings":  land_listings,
    })


def contact(request):
    return render(request, "pages/contact.html")


def contact_submit(request):
    if request.method != "POST":
        return redirect("pages:contact")

    name = (request.POST.get("name") or "").strip()
    email = (request.POST.get("email") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    subject = (request.POST.get("subject") or "").strip()
    description = (request.POST.get("description") or "").strip()
    issue = (request.POST.get("issue") or "General Inquiry").strip()

    if not name or not email or not subject or not description:
        return redirect("pages:contact")

    # Email Col Realty
    try:
        notify_email = getattr(settings, "LEAD_NOTIFY_EMAIL", "").strip()
        if notify_email:
            body = (
                f"New Contact Form Submission\n"
                f"{'='*40}\n"
                f"Issue:       {issue}\n"
                f"Name:        {name}\n"
                f"Email:       {email}\n"
                f"Phone:       {phone or 'Not provided'}\n"
                f"Subject:     {subject}\n\n"
                f"Description:\n{description}\n"
            )
            send_mail(
                f"[Col Realty Contact] {subject}",
                body,
                settings.DEFAULT_FROM_EMAIL,
                [notify_email],
                fail_silently=False,
            )
            logger.info("Contact form email sent to %s", notify_email)
    except Exception as exc:
        logger.exception("Contact form email failed: %s", exc)

    # Sync to HubSpot
    try:
        if getattr(settings, "HUBSPOT_PRIVATE_APP_TOKEN", "").strip():
            from leads.services.hubspot import upsert_contact, create_note
            parts = name.strip().split(" ", 1)
            firstname = parts[0]
            lastname = parts[1] if len(parts) > 1 else ""
            contact_id = upsert_contact(
                email=email, firstname=firstname, lastname=lastname, phone=phone,
            )
            create_note(
                contact_id, f"Contact Form Inquiry\nIssue: {issue}\nSubject: {subject}\n\n{description}")
            logger.info(
                "Contact form synced to HubSpot contact %s", contact_id)
    except Exception as exc:
        logger.exception("Contact form HubSpot sync failed: %s", exc)

    return redirect("/contact/?sent=1")


def health(request):
    return JsonResponse({"status": "ok"})


# ─────────────────────────────────────────────
# Buy pages
# ─────────────────────────────────────────────

def buy(request):
    qs = Listing.objects.filter(
        status="active", property_type__in=BUY_TYPES).order_by("-id")
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "listings/list.html", {
        "listings":       page_obj,
        "page_obj":       page_obj,
        "paginator":      paginator,
        "is_paginated":   page_obj.has_other_pages(),
        "markers":        _build_listing_markers(qs),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


def buy_map(request):
    return render(request, "pages/buy/map.html")


def buy_neighborhoods(request):
    return render(request, "pages/buy/neighborhoods.html")


def buy_off_market(request):
    return render(request, "pages/buy/off_market.html")


# ─────────────────────────────────────────────
# Sell pages
# ─────────────────────────────────────────────

def sell(request):
    return render(request, "pages/sell.html")


def sell_valuation(request):
    return render(request, "pages/sell/valuation.html")


def sell_marketing(request):
    return render(request, "pages/sell/marketing.html")


def sell_concierge(request):
    return render(request, "pages/sell/concierge.html")


# ─────────────────────────────────────────────
# Rent pages
# ─────────────────────────────────────────────

def rent(request):
    qs = Rental.objects.filter(status="active").order_by("-id")
    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "rentals/list.html", {
        "rentals":        page_obj,
        "page_obj":       page_obj,
        "paginator":      paginator,
        "is_paginated":   page_obj.has_other_pages(),
        "markers":        _build_rental_markers(qs),
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API_KEY,
    })


def rent_marketing(request):
    return render(request, "pages/rent/marketing.html")


# ─────────────────────────────────────────────
# Property management
# ─────────────────────────────────────────────

def propman(request):
    return render(request, "pages/propman.html")


# ─────────────────────────────────────────────
# Agents
# ─────────────────────────────────────────────

def agents(request):
    """Team page — lists all active agents."""
    agents_qs = (
        Agent.objects.filter(is_active=True)
        .prefetch_related("specialties")
        .order_by("order", "name")
    )
    return render(request, "pages/agents/team.html", {"agents": agents_qs})


def agent_detail(request, slug):
    """Individual agent profile page."""
    agent = get_object_or_404(
        Agent.objects.prefetch_related("specialties", "testimonials"),
        slug=slug,
        is_active=True,
    )
    listings = Listing.objects.filter(
        listing_agent_email__iexact=agent.email,
        status="active"
    ).order_by("-created_at")

    return render(request, "pages/agents/detail.html", {
        "agent": agent,
        "listings": listings,
    })


def agent_contact(request, slug):
    """Handles the contact form submission from the agent detail page."""
    agent = get_object_or_404(Agent, slug=slug, is_active=True)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        interest = request.POST.get('interest', '')
        message = request.POST.get('message', '').strip()

        send_mail(
            subject=f'New enquiry for {agent.name} from {name} via Col Realty',
            message=(
                f"Name:     {name}\n"
                f"Email:    {email}\n"
                f"Phone:    {phone}\n"
                f"Interest: {interest}\n\n"
                f"Message:\n{message}"
            ),
            from_email='noreply@colrealty.com',
            recipient_list=[agent.email],
            fail_silently=True,
        )

    return redirect('pages:agent_detail', slug=slug)


def agents_joincol(request):
    return render(request, "pages/agents/joincol.html")

# ─────────────────────────────────────────────
# Company pages
# ─────────────────────────────────────────────
def company_aboutus(request):
    return render(request, "pages/company/aboutus.html")


def company_joinus(request):
    return render(request, "pages/company/joinus.html")


def company_contactus(request):
    return render(request, "pages/company/contactus.html")


# ─────────────────────────────────────────────
# ColCircle pages
# ─────────────────────────────────────────────

def colcircle(request):
    return render(request, "pages/colcircle.html")


def colcircle_blog(request):
    return render(request, "pages/colcircle/blog.html")


def newsletter(request):
    return redirect("newsletter:newsletter_archive")


def colcircle_colcircle(request):
    return render(request, "pages/colcircle/colcircle.html")

# ─────────────────────────────────────────────
# Explore pages
# ─────────────────────────────────────────────


def explore_neighborhoods(request):
    return render(request, "pages/explore/neighborhoods.html")


def explore_newhomes(request):
    return render(request, "pages/explore/newhomes.html")


def explore_commercial(request):
    return render(request, "pages/explore/commercial.html")

# ______________________________________________________________
#   LEGAL DOCUMENTS
# ______________________________________________________________


def legal_documents(request):
    docs = LegalDocument.objects.filter(is_active=True)
    return render(request, 'pages/legal_documents.html', {'docs': docs})


def legal_trec(request):
    doc = LegalDocument.objects.filter(doc_type='trec', is_active=True).first()
    if doc:
        return redirect(doc.file.url)
    return redirect('pages:legal_documents')


def legal_iabs(request):
    doc = LegalDocument.objects.filter(doc_type='iabs', is_active=True).first()
    if doc:
        return redirect(doc.file.url)
    return redirect('pages:legal_documents')
