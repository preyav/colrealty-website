from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .models import NewsletterIssue, Subscriber
from .services.mls_stats import get_market_stats
from django.utils import timezone
from django.http import JsonResponse

# reuse existing hubspot service
from leads.services.hubspot import upsert_contact, create_note

def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"

def newsletter_archive(request):
    issues = NewsletterIssue.objects.filter(status="published").order_by("-published_date")
    latest = issues.first()
    return render(request, "newsletter/archive.html", {"issues": issues, "latest": latest})

def newsletter_detail(request, slug):
    issue = get_object_or_404(NewsletterIssue, slug=slug, status="published")
    # Example: show metro-wide stats + a few local submarkets you care about
    stats_all = get_market_stats()
    stats_pflugerville = get_market_stats("Pflugerville")
    stats_roundrock = get_market_stats("Round Rock")

    return render(request, "newsletter/detail.html", {
        "issue": issue,
        "stats_all": stats_all,
        "stats_pflugerville": stats_pflugerville,
        "stats_roundrock": stats_roundrock,
    })

@require_http_methods(["POST"])
def subscribe(request):
    email = (request.POST.get("email") or "").strip().lower()
    first_name = (request.POST.get("first_name") or "").strip()
    last_name = (request.POST.get("last_name") or "").strip()
    zip_code = (request.POST.get("zip_code") or "").strip()

    if not email or "@" not in email:
        messages.error(request, "Please enter a valid email.")
        return render(request, "newsletter/subscribe_result.html", {"ok": False})

    subscriber, _ = Subscriber.objects.get_or_create(email=email)
    subscriber.first_name = first_name
    subscriber.last_name = last_name
    subscriber.zip_code = zip_code
    subscriber.is_active = True
    subscriber.save()

    # ---- HubSpot Sync (Option 1: set workflow properties) ----
    try:
        props = {
            "lead_source": "Newsletter",
            "newsletter_opt_in": True,  # boolean property in HubSpot
            "newsletter_zip": zip_code,
            "newsletter_subscribed_at": timezone.now().isoformat(),
        }

        contact_id = upsert_contact(
            email=email,
            firstname=first_name,
            lastname=last_name,
            props=props,
        )

        note_body = (
            f"<b>Newsletter Subscription</b><br>"
            f"Source: Website Newsletter<br>"
            f"ZIP: {zip_code or 'Not provided'}<br>"
            f"Subscribed at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}<br>"
        )
        create_note(contact_id, note_body)

        subscriber.hubspot_submitted = True
        subscriber.hubspot_response = f"HubSpot contact_id={contact_id}"
        subscriber.save(update_fields=["hubspot_submitted", "hubspot_response"])

        messages.success(request, "You're subscribed! Welcome to Col Realty Market Insider.")
        return render(request, "newsletter/subscribe_result.html", {"ok": True})

    except Exception as e:
        subscriber.hubspot_submitted = False
        subscriber.hubspot_response = str(e)[:5000]
        subscriber.save(update_fields=["hubspot_submitted", "hubspot_response"])

        # For popup/AJAX: still return ok=True because the user IS subscribed locally
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"ok": True, "hubspot_ok": False})

        # Non-AJAX fallback (no template required)
        return redirect("newsletter:newsletter_archive")
    
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    
    return redirect("newsletter:newsletter_archive")