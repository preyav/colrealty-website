from .ownership_choices import OWNERSHIP_CHOICES, LEGACY_OWNERSHIP_CHOICES
import uuid

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


class Property(models.Model):
    """
    Permanent physical real-estate asset.

    This is the actual property being managed by Col Realty.
    It is separate from MLS Listing and Rental marketing records.
    """

    PROPERTY_TYPE_CHOICES = [
        ("single_family_residential", "Single Family Residential"),
        ("condominium", "Condominium"),
        ("manufactured_home", "Manufactured Home"),
        ("mobile_home", "Mobile Home"),
        ("modular", "Modular"),
        ("townhouse", "Townhouse"),
        ('apartments', 'Apartments'),
        ('duplex', 'Duplex'),
        ('triplex', 'Triplex'),
        ('quadruplex', 'Quadruplex'),
        ("other", "Other"),
    ]

    MANAGEMENT_STATUS_CHOICES = [
        ("prospect", "Prospect"),
        ("onboarding", "Onboarding"),
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    property_code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # Address
    street_address = models.CharField(max_length=255)
    unit_number = models.CharField(
    max_length=50,
    blank=True,
    default="",
    )
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50, default="TX")
    zip_code = models.CharField(max_length=20)

    county = models.CharField(max_length=100)
    subdivision = models.CharField(max_length=255)

    street_number = models.CharField(max_length=40, blank=True, default='')
    street_dir_prefix = models.CharField(max_length=2, blank=True, default='')
    street_name = models.CharField(max_length=180, blank=True, default='')
    street_suffix = models.CharField(max_length=40, blank=True, default='')
    street_dir_suffix = models.CharField(max_length=2, blank=True, default='')
    out_of_state_county = models.CharField(max_length=100, blank=True, default='')
    out_of_state_city = models.CharField(max_length=100, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='United States of America')
    zip_plus_four = models.CharField(max_length=4, blank=True, default='')
    tax_block = models.CharField(max_length=100, blank=True, default='')
    tax_lot = models.CharField(max_length=100, blank=True, default='')
    parcel_number = models.CharField(max_length=255, blank=True, default='')
    mls_area = models.CharField(max_length=100, blank=True, default='')

    # Physical property details
    property_type = models.CharField(
        max_length=50,
        choices=PROPERTY_TYPE_CHOICES,
        verbose_name='Property Sub Type',
    )
    property_type_other = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )

    year_built = models.IntegerField(
        null=True,
        blank=True,
    )

    main_level_bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    other_level_beds = models.PositiveSmallIntegerField(null=True, blank=True)

    bedrooms = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    bathrooms_full = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    bathrooms_half = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    sqft = models.IntegerField(
        null=True,
        blank=True,
    )

    lot_size_sqft = models.IntegerField(
        null=True,
        blank=True,
    )

    latitude = models.FloatField(
        null=True,
        blank=True,
    )

    longitude = models.FloatField(
        null=True,
        blank=True,
    )

    # Property management state
    management_status = models.CharField(
        max_length=20,
        choices=MANAGEMENT_STATUS_CHOICES,
        default="prospect",
        db_index=True,
    )

    is_multi_unit = models.BooleanField(default=False)

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_properties",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["street_address", "city"]
        verbose_name_plural = "properties"

    def __str__(self):
        return self.full_address

    @property
    def full_address(self):
        street = self.street_address

        if self.unit_number:
            street = f"{street} #{self.unit_number}"

        return (
            f"{street}, "
            f"{self.city}, {self.state} {self.zip_code}"
        )


class PropertyUnit(models.Model):
    """
    Rentable or occupiable unit belonging to a Property.

    Single-family homes normally have one unit.
    Multifamily properties can have multiple units.
    """

    STATUS_CHOICES = [
        ("vacant", "Vacant"),
        ("occupied", "Occupied"),
        ("notice", "Notice Given"),
        ("maintenance", "Maintenance"),
        ("inactive", "Inactive"),
    ]

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="units",
    )

    unit_number = models.CharField(
        max_length=50,
        blank=True,
        default="",
    )

    beds = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )

    # Legacy combined bathroom value retained for compatibility with
    # existing code/data. New unit entry uses full/half bathroom fields.
    baths = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
    )

    bathrooms_full = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    bathrooms_half = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    sqft = models.IntegerField(
        null=True,
        blank=True,
    )

    market_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="vacant",
        db_index=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["property", "unit_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["property", "unit_number"],
                name="unique_property_unit",
            )
        ]

    def save(self, *args, **kwargs):
        if self.bathrooms_full is not None or self.bathrooms_half is not None:
            self.baths = (
                (self.bathrooms_full or 0)
                + ((self.bathrooms_half or 0) * 0.5)
            )
        super().save(*args, **kwargs)

    def __str__(self):
        if self.unit_number:
            return f"{self.property.full_address} - Unit {self.unit_number}"

        return self.property.full_address
# Optional property reference information; financial transactions stay in Finance.

class PropertyProfile(models.Model):
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name="profile"
    )
    tax_legal_description = models.CharField(max_length=255, blank=True, default="")
    fema_flood_plain_types = models.JSONField(default=list, blank=True)
    fema_flood_plain = models.CharField(max_length=255, blank=True, default="")
    housing_vouchers = models.CharField(
        max_length=3, blank=True, default="",
        choices=[("yes", "Yes"), ("no", "No")],
    )
    etj = models.CharField(max_length=255, blank=True, default="")
    occupancy_status = models.CharField(
        max_length=30, blank=True, default="",
        choices=[("vacant", "Vacant"), ("owner_occupied", "Owner Occupied"),
                 ("tenant_occupied", "Tenant Occupied"), ("other", "Other")],
    )
    ownership_type = models.CharField(
        max_length=30,
        blank=True,
        default="",
        choices=OWNERSHIP_CHOICES + LEGACY_OWNERSHIP_CHOICES,
    )
    school_district = models.CharField(max_length=255, blank=True, default="")
    out_of_state_school_district = models.CharField(max_length=255, blank=True, default="")
    elementary_school = models.CharField(max_length=255, blank=True, default="")
    middle_school = models.CharField(max_length=255, blank=True, default="")
    high_school = models.CharField(max_length=255, blank=True, default="")
    elementary_school_other = models.CharField(max_length=255, blank=True, default="")
    middle_school_other = models.CharField(max_length=255, blank=True, default="")
    high_school_other = models.CharField(max_length=255, blank=True, default="")
    school_information_source = models.CharField(max_length=255, blank=True, default="")
    levels = models.PositiveSmallIntegerField(null=True, blank=True)
    level_types = models.JSONField(default=list, blank=True)
    living_areas = models.PositiveSmallIntegerField(null=True, blank=True)
    dining_areas = models.PositiveSmallIntegerField(null=True, blank=True)
    year_built_source = models.CharField(max_length=255, blank=True, default="")
    living_area_source = models.CharField(max_length=255, blank=True, default="")
    garage_spaces = models.PositiveSmallIntegerField(null=True, blank=True)
    parking_total = models.PositiveSmallIntegerField(null=True, blank=True)
    direction_faces = models.CharField(max_length=255, blank=True, default="")
    move_in_special_yn = models.CharField(max_length=3, blank=True, default="", choices=[("yes", "Yes"), ("no", "No")])
    move_in_special_description = models.TextField(max_length=1000, blank=True, default="")
    lot_features_types = models.JSONField(default=list, blank=True)
    accessibility_features_types = models.JSONField(default=list, blank=True)
    pool_features_types = models.JSONField(default=list, blank=True)
    spa_features_types = models.JSONField(default=list, blank=True)
    security_features_types = models.JSONField(default=list, blank=True)
    fireplace_features_types = models.JSONField(default=list, blank=True)
    property_condition = models.CharField(max_length=255, blank=True, default="")
    builder_name = models.CharField(max_length=255, blank=True, default="")
    lot_dimensions = models.CharField(max_length=255, blank=True, default="")
    interior_feature_types = models.JSONField(default=list, blank=True)
    interior_features = models.TextField(blank=True, default="", max_length=4000)
    exterior_feature_types = models.JSONField(default=list, blank=True)
    exterior_features = models.TextField(blank=True, default="", max_length=4000)
    flooring_types = models.JSONField(default=list, blank=True)
    flooring = models.TextField(blank=True, default="", max_length=4000)
    construction_material_types = models.JSONField(default=list, blank=True)
    construction_materials = models.TextField(blank=True, default="", max_length=4000)
    foundation_types = models.JSONField(default=list, blank=True)
    foundation = models.TextField(blank=True, default="", max_length=4000)
    roof_types = models.JSONField(default=list, blank=True)
    roof = models.TextField(blank=True, default="", max_length=4000)
    parking_features = models.TextField(blank=True, default="", max_length=4000)
    lot_features = models.TextField(blank=True, default="", max_length=4000)
    restrictions = models.TextField(blank=True, default="", max_length=4000)
    heating_types = models.JSONField(default=list, blank=True)
    cooling_types = models.JSONField(default=list, blank=True)
    utility_services_types = models.JSONField(default=list, blank=True)
    appliances_types = models.JSONField(default=list, blank=True)
    appliances = models.TextField(blank=True, default="", max_length=4000)
    accessibility_features = models.TextField(blank=True, default="", max_length=4000)
    patio_porch_features = models.TextField(blank=True, default="", max_length=4000)
    window_features_types = models.JSONField(default=list, blank=True)
    window_features = models.TextField(blank=True, default="", max_length=4000)
    security_features = models.TextField(blank=True, default="", max_length=4000)
    laundry_location = models.TextField(blank=True, default="", max_length=4000)
    fencing = models.TextField(blank=True, default="", max_length=4000)
    community_features = models.TextField(blank=True, default="", max_length=4000)
    other_structures = models.TextField(blank=True, default="", max_length=4000)
    fireplaces = models.PositiveSmallIntegerField(null=True, blank=True)
    fireplace_features = models.TextField(blank=True, default="", max_length=4000)
    has_pool = models.BooleanField(null=True, blank=True, default=None)
    pool_features = models.TextField(blank=True, default="", max_length=4000)
    spa = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    spa_features = models.TextField(blank=True, default="", max_length=4000)
    waterfront = models.BooleanField(null=True, blank=True, default=None)
    ownership_management_remarks = models.TextField(blank=True, default='', max_length=4000)
    property_overview_remarks = models.TextField(blank=True, default='', max_length=4000)
    physical_features_remarks = models.TextField(blank=True, default='', max_length=4000)
    utilities_services_remarks = models.TextField(blank=True, default='', max_length=4000)
    rules_compliance_remarks = models.TextField(blank=True, default='', max_length=4000)
    green_energy_remarks = models.TextField(blank=True, default='', max_length=4000)
    application_association_yn = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_fee_per_person = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_fee_payable_to = models.CharField(max_length=255, blank=True, default='')
    application_managed_by = models.CharField(max_length=255, blank=True, default='')
    application_security_deposit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_security_deposit_payable_to = models.CharField(max_length=255, blank=True, default='')
    application_required = models.TextField(max_length=4000, blank=True, default='')
    application_administration_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_administration_fee_payable_to = models.CharField(max_length=255, blank=True, default='')
    application_first_month_rent_payable_to = models.CharField(max_length=255, blank=True, default='')
    application_renters_insurance_required = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_short_term_premium = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_short_term_premium_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_on_site_compliance = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_certified_funds = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_minimum_lease_months = models.PositiveSmallIntegerField(null=True, blank=True)
    application_maximum_lease_months = models.PositiveSmallIntegerField(null=True, blank=True)
    application_available_date = models.DateField(null=True, blank=True)
    application_lease_term = models.CharField(max_length=255, blank=True, default='')
    application_lease_guarantor_yn = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_policy = models.TextField(max_length=4000, blank=True, default='')
    application_max_number_of_pets = models.PositiveSmallIntegerField(null=True, blank=True)
    application_pet_deposit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_pet_deposit_per_pet = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_monthly_pet_rent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_monthly_pet_rent_per_pet = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_additional_pet_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    application_additional_pet_fee_description = models.TextField(max_length=4000, blank=True, default='')
    application_pets_allowed = models.TextField(max_length=4000, blank=True, default='')
    application_one_time_expenses = models.TextField(max_length=4000, blank=True, default='')
    application_recurring_expenses = models.TextField(max_length=4000, blank=True, default='')
    application_deliver_address = models.CharField(max_length=100, blank=True, default='')
    application_public_link = models.URLField(max_length=255, blank=True, default='')
    application_agent_link = models.URLField(max_length=255, blank=True, default='')
    application_rentspree_online_yn = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_owner_contributions_yn = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    application_intermediary_yn = models.CharField(max_length=3, blank=True, default='', choices=[('yes', 'Yes'), ('no', 'No')])
    waterfront_features = models.TextField(blank=True, default="", max_length=4000)
    water_body_name = models.CharField(max_length=255, blank=True, default="")
    community_website = models.URLField(max_length=1000, blank=True, default="")
    disclosures = models.TextField(blank=True, default="", max_length=4000)
    heating = models.TextField(blank=True, default="", max_length=4000)
    cooling = models.TextField(blank=True, default="", max_length=4000)
    water_source = models.TextField(max_length=4000, blank=True, default="")
    sewer = models.TextField(max_length=4000, blank=True, default="")
    utility_services = models.TextField(blank=True, default="", max_length=4000)
    utility_providers = models.TextField(blank=True, default="", max_length=4000)
    utility_responsibilities = models.TextField(blank=True, default="", max_length=4000)
    energy_features = models.TextField(blank=True, default="", max_length=4000)
    sustainability_features = models.TextField(blank=True, default="", max_length=4000)
    solar = models.BooleanField(null=True, blank=True, default=None)
    solar_ownership = models.CharField(
        max_length=30,
        blank=True,
        default="",
        choices=[("owned", "Owned"), ("leased", "Leased"), ("other", "Other")],
    )
    has_hoa = models.BooleanField(null=True, blank=True, default=None)
    association_name = models.CharField(max_length=255, blank=True, default="")
    hoa_management_company = models.TextField(blank=True, default="")
    association_fee = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    association_fee_frequency = models.CharField(
        max_length=30,
        blank=True,
        default="",
        choices=[
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semiannual", "Semiannual"),
            ("annual", "Annual"),
            ("other", "Other"),
        ],
    )
    association_requirements = models.TextField(blank=True, default="", max_length=4000)
    association_fees_include = models.TextField(blank=True, default="", max_length=4000)
    special_assessment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    annual_tax_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    tax_year = models.PositiveSmallIntegerField(null=True, blank=True)
    tax_assessed_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    tax_rate = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    tax_exemptions = models.TextField(blank=True, default="", max_length=4000)
    updated_at = models.DateTimeField(auto_now=True)


class PropertyMarketingDefaults(models.Model):
    property = models.OneToOneField(
        Property, on_delete=models.CASCADE, related_name="marketing_defaults"
    )
    showing_requirements = models.TextField(blank=True, default="", max_length=4000)
    showing_contact_name = models.CharField(max_length=255, blank=True, default="")
    showing_contact_phone = models.CharField(max_length=255, blank=True, default="")
    showing_contact_email = models.EmailField(blank=True, default="")
    lockbox_type = models.TextField(max_length=4000, blank=True, default="")
    lockbox_serial_number = models.CharField(max_length=255, blank=True, default="")
    lockbox_location = models.TextField(blank=True, default="", max_length=4000)
    access_code = models.CharField(max_length=255, blank=True, default="")
    showing_instructions = models.TextField(blank=True, default="", max_length=4000)
    assigned_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_assigned_manager_defaults",
    )
    listing_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_listing_agent_defaults",
    )
    co_listing_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="property_co_listing_agent_defaults",
    )
    # Display names may include external agents; existing account links remain intact.
    assigned_manager_name = models.CharField(max_length=255, blank=True, default="")
    listing_agent_name = models.CharField(max_length=255, blank=True, default="")
    co_listing_agent_name = models.CharField(max_length=255, blank=True, default="")
    office_notes = models.TextField(blank=True, default="", max_length=4000)
    public_remarks = models.TextField(blank=True, default="", max_length=4000)
    private_remarks = models.TextField(blank=True, default="", max_length=4000)
    directions = models.TextField(blank=True, default="", max_length=4000)
    branded_tour_url = models.URLField(max_length=1000, blank=True, default="")
    unbranded_tour_url = models.URLField(max_length=1000, blank=True, default="")
    branded_video_url = models.URLField(max_length=1000, blank=True, default="")
    unbranded_video_url = models.URLField(max_length=1000, blank=True, default="")
    listing_detail_url = models.URLField(max_length=1000, blank=True, default="")
    allow_public_display = models.BooleanField(default=False)
    allow_address_display = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


class PropertyDocumentLink(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="document_links"
    )
    title = models.CharField(max_length=255)
    category = models.CharField(
        max_length=30,
        choices=[
            ("agreement", "Agreement"),
            ("disclosure", "Disclosure"),
            ("inspection", "Inspection"),
            ("warranty", "Warranty / Manual"),
            ("other", "Other"),
        ],
        default="other",
    )
    url = models.URLField(max_length=1000)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ["title", "id"]


class PropertyEnergyCertification(models.Model):
    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="energy_certifications"
    )
    verification_type = models.CharField(max_length=255)
    metric = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=30,
        choices=[
            ("pending", "Pending"),
            ("verified", "Verified"),
            ("expired", "Expired"),
        ],
    )
    rating = models.CharField(max_length=100, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-year", "id"]


class FlooringOption(models.Model):
    """Administrator-maintained flooring vocabulary; codes remain stable."""
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "label", "pk")

    def __str__(self):
        return self.label


class InteriorFeatureOption(models.Model):
    """Administrator-maintained interior feature vocabulary."""
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "label", "pk")

    def __str__(self):
        return self.label


class ExteriorFeatureOption(models.Model):
    """Administrator-maintained exterior feature vocabulary."""
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "label", "pk")

    def __str__(self):
        return self.label


class ConstructionMaterialOption(models.Model):
    """Administrator-maintained construction material vocabulary."""
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "label", "pk")

    def __str__(self):
        return self.label


class FoundationOption(models.Model):
    """Administrator-maintained foundation vocabulary."""
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "label", "pk")

    def __str__(self):
        return self.label


class RoofOption(models.Model):
    """Administrator-maintained roof vocabulary."""
    code = models.SlugField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "label", "pk")

    def __str__(self):
        return self.label


class PropertyEditorDraft(models.Model):
    """Staff-owned partial editor input; never a published or active property."""
    property = models.ForeignKey(Property, null=True, blank=True, on_delete=models.CASCADE, related_name='editor_drafts')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_editor_drafts')
    payload = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']


class PropertyDocumentUpload(models.Model):
    """Private file metadata, staged until its property reference is saved."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    property = models.ForeignKey(Property, null=True, blank=True, on_delete=models.CASCADE, related_name='document_uploads')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    storage_key = models.CharField(max_length=1000, unique=True)
    original_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
