from django.contrib import admin
from .models import UserProfile, SavedSearch, FavoriteListing, RecentlyViewed

admin.site.register(UserProfile)
admin.site.register(SavedSearch)
admin.site.register(FavoriteListing)
admin.site.register(RecentlyViewed)
