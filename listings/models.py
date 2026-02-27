from django.db import models
from django.urls import reverse


class Listing(models.Model):
    MLS_STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("sold", "Sold"),
    ]

    # ── Core MLS fields ───────────────────────────────────────────────────
    mls_id = models.CharField(max_length=128, unique=True, db_index=True)
    mls_modification_timestamp = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=512)

    # ── Address ───────────────────────────────────────────────────────────
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)
    county = models.CharField(max_length=100, blank=True)
    subdivision = models.CharField(max_length=255, blank=True)

    # ── Pricing ───────────────────────────────────────────────────────────
    price = models.DecimalField(max_digits=12, decimal_places=2)
    original_list_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_year = models.IntegerField(null=True, blank=True)
    hoa_fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hoa_frequency = models.CharField(max_length=50, blank=True)  # monthly, quarterly, annually
    buyer_agent_compensation = models.CharField(max_length=50, blank=True)

    # ── Core specs ────────────────────────────────────────────────────────
    beds = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    baths = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    baths_full = models.IntegerField(null=True, blank=True)
    baths_half = models.IntegerField(null=True, blank=True)
    sqft = models.IntegerField(null=True, blank=True)
    lot_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)   # acres
    lot_size_sqft = models.IntegerField(null=True, blank=True)

    # ── Building info ─────────────────────────────────────────────────────
    property_type = models.CharField(max_length=100, blank=True)
    year_built = models.IntegerField(null=True, blank=True)
    stories = models.IntegerField(null=True, blank=True)
    garage_spaces = models.IntegerField(null=True, blank=True)
    parking_total = models.IntegerField(null=True, blank=True)

    # ── Features (stored as comma-separated strings from MLS) ─────────────
    interior_features = models.TextField(blank=True)    # e.g. "Double Vanity, Kitchen Island, Pantry"
    exterior_features = models.TextField(blank=True)    # e.g. "Private Yard, Covered Patio"
    community_features = models.TextField(blank=True)   # e.g. "Pool, Tennis Courts, Golf"
    parking_features = models.TextField(blank=True)     # e.g. "Attached, Driveway, Garage"
    appliances = models.TextField(blank=True)           # e.g. "Dishwasher, Gas Range, Microwave"
    flooring = models.TextField(blank=True)             # e.g. "Carpet, Tile, Vinyl"
    laundry_features = models.TextField(blank=True)
    window_features = models.TextField(blank=True)
    patio_porch_features = models.TextField(blank=True)

    # ── Property attributes (booleans) ───────────────────────────────────
    has_fireplace = models.BooleanField(null=True, blank=True)
    has_pool = models.BooleanField(null=True, blank=True)
    has_garage = models.BooleanField(null=True, blank=True)
    is_waterfront = models.BooleanField(null=True, blank=True)
    is_new_construction = models.BooleanField(null=True, blank=True)

    # ── Construction ─────────────────────────────────────────────────────
    construction_materials = models.CharField(max_length=255, blank=True)
    foundation = models.CharField(max_length=100, blank=True)
    roof = models.CharField(max_length=100, blank=True)
    fencing = models.CharField(max_length=255, blank=True)
    direction_faces = models.CharField(max_length=50, blank=True)

    # ── Utilities ─────────────────────────────────────────────────────────
    heating = models.CharField(max_length=255, blank=True)
    cooling = models.CharField(max_length=255, blank=True)
    sewer = models.CharField(max_length=100, blank=True)
    water_source = models.CharField(max_length=100, blank=True)

    # ── Schools ───────────────────────────────────────────────────────────
    school_district = models.CharField(max_length=255, blank=True)
    elementary_school = models.CharField(max_length=255, blank=True)
    middle_school = models.CharField(max_length=255, blank=True)
    high_school = models.CharField(max_length=255, blank=True)

    # ── Open house ────────────────────────────────────────────────────────
    open_house_date = models.DateField(null=True, blank=True)
    open_house_start_time = models.TimeField(null=True, blank=True)
    open_house_end_time = models.TimeField(null=True, blank=True)

    # ── Listing Agent ─────────────────────────────────────────────────────
    listing_agent_name = models.CharField(max_length=255, blank=True)
    listing_agent_email = models.EmailField(max_length=255, blank=True)
    listing_agent_phone = models.CharField(max_length=50, blank=True)
    listing_office_name = models.CharField(max_length=255, blank=True)

    # ── Media ─────────────────────────────────────────────────────────────
    main_image_url = models.URLField(max_length=1000, blank=True)
    image_urls = models.JSONField(default=list, blank=True)   # all MLS photos
    virtual_tour_url = models.URLField(max_length=1000, blank=True)

    # ── Listing metadata ──────────────────────────────────────────────────
    status = models.CharField(max_length=20, choices=MLS_STATUS_CHOICES, default="active")
    days_on_market = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    directions = models.TextField(blank=True)

    # ── Location ──────────────────────────────────────────────────────────
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    # ── Admin ─────────────────────────────────────────────────────────────
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} – {self.city}, {self.state}"

    def get_absolute_url(self):
        return reverse("listings:listing_detail", args=[self.pk])

    @property
    def price_per_sqft(self):
        if self.price and self.sqft and self.sqft > 0:
            return round(self.price / self.sqft)
        return None

    @property
    def full_address(self):
        return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}"

    def interior_features_list(self):
        return [f.strip() for f in self.interior_features.split(",") if f.strip()]

    def exterior_features_list(self):
        return [f.strip() for f in self.exterior_features.split(",") if f.strip()]

    def community_features_list(self):
        return [f.strip() for f in self.community_features.split(",") if f.strip()]

    def parking_features_list(self):
        return [f.strip() for f in self.parking_features.split(",") if f.strip()]

    def appliances_list(self):
        return [f.strip() for f in self.appliances.split(",") if f.strip()]
