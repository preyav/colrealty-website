from django.conf import settings
from django.db import models


class AILeadProfile(models.Model):
    HOMEOWNERSHIP_CHOICES = [
        ("unknown", "Unknown"),
        ("renting", "Renting"),
        ("owning", "Owning"),
    ]

    INTENT_CHOICES = [
        ("", "Unknown"),
        ("buy", "Buy"),
        ("rent", "Rent"),
        ("sell", "Sell"),
        ("invest", "Invest"),
        ("explore", "Explore"),
    ]

    FINANCING_CHOICES = [
        ("", "Unknown"),
        ("preapproved", "Preapproved"),
        ("exploring", "Exploring"),
        ("cash", "Cash"),
    ]

    session_id = models.CharField(max_length=120, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ai_lead_profiles",
    )

    full_name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    intent = models.CharField(max_length=50, choices=INTENT_CHOICES, blank=True, default="")
    homeownership_status = models.CharField(
        max_length=50,
        choices=HOMEOWNERSHIP_CHOICES,
        default="unknown",
    )
    first_time_buyer = models.BooleanField(null=True, blank=True)
    has_home_to_sell = models.BooleanField(null=True, blank=True)

    budget_min = models.IntegerField(null=True, blank=True)
    budget_max = models.IntegerField(null=True, blank=True)
    desired_locations = models.JSONField(default=list, blank=True)
    property_type = models.CharField(max_length=50, blank=True)
    beds_min = models.IntegerField(null=True, blank=True)
    baths_min = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)

    timeline = models.CharField(max_length=100, blank=True)
    financing_status = models.CharField(max_length=100, choices=FINANCING_CHOICES, blank=True, default="")
    investment_intent = models.BooleanField(null=True, blank=True)

    must_haves = models.JSONField(default=list, blank=True)
    deal_breakers = models.JSONField(default=list, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        label = self.full_name or self.email or self.session_id
        return f"AILeadProfile({label})"


class AIConversationMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("tool", "Tool"),
        ("system", "System"),
    ]

    session_id = models.CharField(max_length=120, db_index=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.message[:50]}"


class TourRequest(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("booked", "Booked"),
        ("closed", "Closed"),
    ]

    session_id = models.CharField(max_length=120, db_index=True)
    listing_id = models.CharField(max_length=100)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    preferred_dates = models.JSONField(default=list, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default="new")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"TourRequest({self.listing_id} - {self.full_name})"
