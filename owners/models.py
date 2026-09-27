from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from properties.models import Property


class OwnerProfile(models.Model):
    """
    Represents a property owner, either an individual or a legal entity.
    """

    OWNER_TYPE_CHOICES = [
        ("individual", "Individual"),
        ("entity", "Entity / Company"),
    ]

    owner_type = models.CharField(
        max_length=20,
        choices=OWNER_TYPE_CHOICES,
        default="individual",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owner_profile",
    )

    # Individual owner fields
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    # Company / entity owner field
    entity_name = models.CharField(max_length=255, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    mailing_address = models.CharField(max_length=255, blank=True)
    mailing_city = models.CharField(max_length=100, blank=True)
    mailing_state = models.CharField(max_length=50, blank=True)
    mailing_zip_code = models.CharField(max_length=20, blank=True)

    notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "entity_name"]

    def __str__(self):
        if self.owner_type == "entity" and self.entity_name:
            return self.entity_name

        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email or f"Owner #{self.pk}"


class PropertyOwnership(models.Model):
    """
    Connects an OwnerProfile to a Property.

    Supports multiple owners per property and fractional ownership.
    """

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="ownerships",
    )

    owner = models.ForeignKey(
        OwnerProfile,
        on_delete=models.CASCADE,
        related_name="property_ownerships",
    )

    ownership_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("100.00"),
        validators=[
            MinValueValidator(Decimal("0.01")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    is_primary_contact = models.BooleanField(default=False)

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    end_date = models.DateField(
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["property", "-is_primary_contact", "owner"]

        constraints = [
            models.UniqueConstraint(
                fields=["property", "owner"],
                name="unique_property_owner",
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(end_date__isnull=True)
                    | models.Q(end_date__gte=models.F("start_date"))
                    | models.Q(start_date__isnull=True)
                ),
                name="ownership_end_after_start",
            ),
        ]

    def __str__(self):
        return (
            f"{self.owner} → {self.property} "
            f"({self.ownership_percentage}%)"
        )