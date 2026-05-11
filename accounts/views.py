from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from .models import UserProfile, FavoriteListing, SavedSearch, RecentlyViewed
from listings.models import Listing


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def to_int(value):
    try:
        return int(value) if value not in [None, ""] else None
    except (TypeError, ValueError):
        return None


def build_name(filters):
    parts = []

    if filters.get("q"):
        parts.append(filters["q"])
    elif filters.get("zip_code"):
        parts.append(filters["zip_code"])
    elif filters.get("city"):
        parts.append(filters["city"])

    if filters.get("property_type"):
        parts.append(filters["property_type"])

    min_price = to_int(filters.get("price_min"))
    max_price = to_int(filters.get("price_max"))

    if min_price and max_price:
        min_k = min_price // 1000
        max_k = max_price // 1000
        parts.append(f"${min_k}K-${max_k}K")
    elif min_price:
        min_k = min_price // 1000
        parts.append(f"${min_k}K+")
    elif max_price:
        max_k = max_price // 1000
        parts.append(f"Up to ${max_k}K")

    return ", ".join(parts) if parts else "Saved Search"


def build_summary(filters):
    parts = []

    if filters.get("zip_code"):
        parts.append(filters["zip_code"])
    elif filters.get("city"):
        parts.append(filters["city"])
    elif filters.get("q"):
        parts.append(filters["q"])

    parts.append("Sales")

    min_price = to_int(filters.get("price_min"))
    max_price = to_int(filters.get("price_max"))
    if min_price or max_price:
        low = f"${min_price:,}" if min_price else "0"
        high = f"${max_price:,}" if max_price else "+"
        parts.append(f"Price: {low} to {high}")

    if filters.get("status"):
        parts.append(filters["status"])

    if filters.get("property_type"):
        parts.append(filters["property_type"])

    return " | ".join(parts)


def get_cover_image(filters):
    qs = Listing.objects.all()

    if filters.get("city"):
        qs = qs.filter(city__iexact=filters["city"])

    if filters.get("zip_code"):
        qs = qs.filter(zip_code=filters["zip_code"])

    if filters.get("property_type"):
        qs = qs.filter(property_type__iexact=filters["property_type"])

    min_price = to_int(filters.get("price_min"))
    max_price = to_int(filters.get("price_max"))

    if min_price:
        qs = qs.filter(price__gte=min_price)

    if max_price:
        qs = qs.filter(price__lte=max_price)

    beds_min = to_int(filters.get("beds_min"))
    baths_min = to_int(filters.get("baths_min"))

    if beds_min:
        qs = qs.filter(bedrooms__gte=beds_min)

    if baths_min:
        qs = qs.filter(bathrooms__gte=baths_min)

    if filters.get("status"):
        status_values = [s.strip() for s in filters["status"].split(",") if s.strip()]
        if status_values:
            qs = qs.filter(standard_status__in=status_values)

    listing = qs.order_by("-mls_modification_timestamp").first()
    return listing.main_image_url if listing and listing.main_image_url else ""


@login_required
def overview(request):
    profile = get_or_create_profile(request.user)
    favorites = FavoriteListing.objects.filter(
        user=request.user
    ).select_related('listing')[:8]
    saved_searches = SavedSearch.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    recently_viewed = RecentlyViewed.objects.filter(
        user=request.user
    ).select_related('listing')[:8]

    hour = timezone.localtime().hour
    if hour < 12:
        greeting = 'Good morning'
    elif hour < 17:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'

    return render(request, 'accounts/overview.html', {
        'profile': profile,
        'favorites': favorites,
        'saved_searches': saved_searches,
        'recently_viewed': recently_viewed,
        'greeting': greeting,
    })


@login_required
def favorites(request):
    items = FavoriteListing.objects.filter(
        user=request.user
    ).select_related('listing')
    return render(request, 'accounts/favorites.html', {'favorites': items})


@login_required
@require_POST
def save_search(request):
    query_url = request.POST.get("query_url") or request.META.get("HTTP_REFERER", "/")

    filters = {
        "q": (request.POST.get("q") or "").strip(),
        "city": (request.POST.get("city") or "").strip(),
        "zip_code": (request.POST.get("zip_code") or "").strip(),
        "price_min": (request.POST.get("price_min") or "").strip(),
        "price_max": (request.POST.get("price_max") or "").strip(),
        "beds_min": (request.POST.get("beds_min") or "").strip(),
        "baths_min": (request.POST.get("baths_min") or "").strip(),
        "property_type": (request.POST.get("property_type") or "").strip(),
        "status": (request.POST.get("status") or "").strip(),
        "sort": (request.POST.get("sort") or "").strip(),
    }

    # remove empty values so filters JSON stays clean
    filters = {k: v for k, v in filters.items() if v not in [None, ""]}

    name = build_name(filters)
    summary_line = build_summary(filters)
    cover_image = get_cover_image(filters)

    saved_search = SavedSearch.objects.create(
        user=request.user,
        name=name,
        query_url=query_url,
        filters=filters,
        summary_line=summary_line,
        cover_image=cover_image,
    )

    return JsonResponse({
        "status": "saved",
        "id": saved_search.pk,
        "name": saved_search.name,
        "summary_line": summary_line,
        "cover_image": cover_image,
    })


@login_required
def saved_searches(request):
    items = SavedSearch.objects.filter(
        user=request.user
    ).order_by('-created_at')
    return render(request, 'accounts/saved_searches.html', {'saved_searches': items})


@login_required
def saved_search_detail(request, pk):
    saved_search = SavedSearch.objects.get(pk=pk, user=request.user)
    filters = saved_search.filters or {}

    listings = Listing.objects.all()

    if filters.get("city"):
        listings = listings.filter(city__iexact=filters["city"])

    if filters.get("zip_code"):
        listings = listings.filter(zip_code=filters["zip_code"])

    if filters.get("property_type"):
        listings = listings.filter(property_type__iexact=filters["property_type"])

    if filters.get("price_min"):
        listings = listings.filter(price__gte=filters["price_min"])

    if filters.get("price_max"):
        listings = listings.filter(price__lte=filters["price_max"])

    if filters.get("beds_min"):
        listings = listings.filter(bedrooms__gte=filters["beds_min"])

    if filters.get("baths_min"):
        listings = listings.filter(bathrooms__gte=filters["baths_min"])

    if filters.get("status"):
        listings = listings.filter(standard_status__in=filters["status"].split(","))

    listings = listings.order_by("-mls_modification_timestamp")[:48]

    return render(request, "accounts/saved_search_detail.html", {
        "saved_search": saved_search,
        "listings": listings,
    })


@login_required
def saved_search_listing_preview(request, pk):
    """
    AJAX endpoint — returns the rendered listing preview partial.
    Called by fetch() in saved_search_detail.html
    """
    listing = get_object_or_404(Listing, pk=pk)
    html = render_to_string(
        "accounts/partials/saved_search_listing_preview.html",
        {"listing": listing},
        request=request,
    )
    return HttpResponse(html)


@login_required
@require_POST
def delete_saved_search(request, pk):
    saved_search = get_object_or_404(SavedSearch, pk=pk, user=request.user)
    saved_search.delete()

    return JsonResponse({"status": "deleted"})

@login_required
def account_settings(request):
    profile = get_or_create_profile(request.user)
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.save()

        profile.phone = request.POST.get('phone', '')
        profile.save()

        messages.success(request, 'Your settings have been saved successfully.')
        return redirect('accounts:settings')

    return render(request, 'accounts/settings.html', {'profile': profile})


@login_required
def toggle_favorite(request, listing_id):
    if request.method == 'POST':
        listing = Listing.objects.get(pk=listing_id)
        fav, created = FavoriteListing.objects.get_or_create(
            user=request.user,
            listing=listing
        )
        if not created:
            fav.delete()
            return JsonResponse({'status': 'removed'})
        return JsonResponse({'status': 'added'})

    return JsonResponse({'error': 'POST required'}, status=405)


def select_user_type(request):
    role = request.GET.get('role') or request.POST.get('user_type', 'other')
    if request.user.is_authenticated:
        profile = get_or_create_profile(request.user)
        profile.user_type = role
        profile.save()

    if role == 'agent':
        return redirect('/portal/')
    return redirect('accounts:overview')


def sign_out(request):
    logout(request)
    return redirect('/')