import uuid

from django.conf import settings
from django.db import models


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

    # Physical property details
    property_type = models.CharField(
        max_length=50,
        choices=PROPERTY_TYPE_CHOICES,
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