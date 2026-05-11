from django.db import models
from django.contrib.auth.models import User
from listings.models import Listing


class UserProfile(models.Model):
    USER_TYPES = [("agent", "Agent"), ("buyer_seller",
                                       "Buyer/Seller"), ("other", "Other")]
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile")
    user_type = models.CharField(max_length=20, choices=USER_TYPES, blank=True)
    avatar_url = models.URLField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.user.email} ({self.user_type})"


class SavedSearch(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="saved_searches"
    )

    # Display name (e.g. "78717, $500K-$650K")
    name = models.CharField(max_length=150)

    # Raw filters used to rebuild the search
    filters = models.JSONField(default=dict, blank=True)

    # Optional UI fields (Compass-style display)
    location_label = models.CharField(max_length=255, blank=True)
    search_type = models.CharField(max_length=50, blank=True, default="Sales")
    summary_line = models.CharField(max_length=500, blank=True)

    # Thumbnail image (first matching listing)
    cover_image = models.URLField(blank=True)

    # Full query string URL
    query_url = models.TextField()

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.name}"


class FavoriteListing(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="favorites")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "listing")


class RecentlyViewed(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="recently_viewed")
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "listing")
        ordering = ["-viewed_at"]
