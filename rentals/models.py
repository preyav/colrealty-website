from django.db import models
from django.urls import reverse


class Rental(models.Model):

    # ── Core MLS fields ───────────────────────────────────────────────────
    mls_id = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=200)

    # ── Address ───────────────────────────────────────────────────────────
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    county = models.CharField(max_length=100, blank=True)
    subdivision = models.CharField(max_length=255, blank=True)

    # ── Pricing ───────────────────────────────────────────────────────────
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    lease_term = models.CharField(max_length=100, blank=True)   # e.g. "12 months"
    pets_allowed = models.BooleanField(null=True, blank=True)
    utilities_included = models.TextField(blank=True)            # e.g. "Water, Trash"

    # ── Core specs ────────────────────────────────────────────────────────
    beds = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    baths = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    baths_full = models.IntegerField(null=True, blank=True)
    baths_half = models.IntegerField(null=True, blank=True)
    sqft = models.IntegerField(null=True, blank=True)
    lot_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # ── Building info ─────────────────────────────────────────────────────
    property_type = models.CharField(max_length=100)
    year_built = models.IntegerField(null=True, blank=True)
    stories = models.IntegerField(null=True, blank=True)
    garage_spaces = models.IntegerField(null=True, blank=True)

    # ── Features ─────────────────────────────────────────────────────────
    interior_features = models.TextField(blank=True)
    exterior_features = models.TextField(blank=True)
    community_features = models.TextField(blank=True)
    appliances = models.TextField(blank=True)
    flooring = models.TextField(blank=True)
    laundry_features = models.TextField(blank=True)

    # ── Property attributes ───────────────────────────────────────────────
    has_fireplace = models.BooleanField(null=True, blank=True)
    has_pool = models.BooleanField(null=True, blank=True)
    has_garage = models.BooleanField(null=True, blank=True)

    # ── Utilities ─────────────────────────────────────────────────────────
    heating = models.CharField(max_length=255, blank=True)
    cooling = models.CharField(max_length=255, blank=True)

    # ── Schools ───────────────────────────────────────────────────────────
    school_district = models.CharField(max_length=255, blank=True)
    elementary_school = models.CharField(max_length=255, blank=True)
    middle_school = models.CharField(max_length=255, blank=True)
    high_school = models.CharField(max_length=255, blank=True)

    # ── Availability ──────────────────────────────────────────────────────
    available_date = models.DateField(null=True, blank=True)
    open_house_date = models.DateField(null=True, blank=True)
    open_house_start_time = models.TimeField(null=True, blank=True)
    open_house_end_time = models.TimeField(null=True, blank=True)

    # ── Media ─────────────────────────────────────────────────────────────
    main_image_url = models.URLField(blank=True, null=True)
    virtual_tour_url = models.URLField(max_length=1000, blank=True)

    # ── Listing metadata ──────────────────────────────────────────────────
    status = models.CharField(
        max_length=50,
        default="active",
        choices=[
            ("active", "Active"),
            ("leased", "Leased"),
            ("inactive", "Inactive"),
        ]
    )
    days_on_market = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    directions = models.TextField(blank=True)

    # ── Location ──────────────────────────────────────────────────────────
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} - {self.city}"

    def get_absolute_url(self):
        return reverse("rentals:rental_detail", args=[self.pk])

    def full_address(self):
        return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}"

    @property
    def price_per_sqft(self):
        if self.rent and self.sqft and self.sqft > 0:
            return round(self.rent / self.sqft, 2)
        return None

    def interior_features_list(self):
        return [f.strip() for f in self.interior_features.split(",") if f.strip()]

    def exterior_features_list(self):
        return [f.strip() for f in self.exterior_features.split(",") if f.strip()]

    def community_features_list(self):
        return [f.strip() for f in self.community_features.split(",") if f.strip()]

    def appliances_list(self):
        return [f.strip() for f in self.appliances.split(",") if f.strip()]
