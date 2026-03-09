from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.http import JsonResponse
from django.utils import timezone
from .models import UserProfile, FavoriteListing, SavedSearch, RecentlyViewed


def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


@login_required
def overview(request):
    profile = get_or_create_profile(request.user)
    favorites = FavoriteListing.objects.filter(
        user=request.user).select_related('listing')[:8]
    saved_searches = SavedSearch.objects.filter(
        user=request.user).order_by('-created_at')[:5]
    recently_viewed = RecentlyViewed.objects.filter(
        user=request.user).select_related('listing')[:8]
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
        user=request.user).select_related('listing')
    return render(request, 'accounts/favorites.html', {'favorites': items})


@login_required
def saved_searches(request):
    items = SavedSearch.objects.filter(
        user=request.user).order_by('-created_at')
    return render(request, 'accounts/saved_searches.html', {'saved_searches': items})


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
    from listings.models import Listing
    if request.method == 'POST':
        listing = Listing.objects.get(pk=listing_id)
        fav, created = FavoriteListing.objects.get_or_create(
            user=request.user, listing=listing)
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
    else:
        return redirect('accounts:overview')


def sign_out(request):
    logout(request)
    return redirect('/')
