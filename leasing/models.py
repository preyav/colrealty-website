from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings

from properties.models import PropertyUnit
from tenants.models import TenantProfile


class Lease(models.Model):
    """
    Lease agreement for one PropertyUnit.

    A unit may have multiple leases over time, but normally only
    one active lease at a time.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending Signature"),
        ("active", "Active"),
        ("notice", "Notice Given"),
        ("expired", "Expired"),
        ("terminated", "Terminated"),
        ("cancelled", "Cancelled"),
    ]

    unit = models.ForeignKey(
        PropertyUnit,
        on_delete=models.PROTECT,
        related_name="leases",
    )

    start_date = models.DateField()
    end_date = models.DateField()

    monthly_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    security_deposit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    signed_date = models.DateField(
        null=True,
        blank=True,
    )

    move_in_date = models.DateField(
        null=True,
        blank=True,
    )

    move_out_date = models.DateField(
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="lease_end_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(move_out_date__isnull=True)
                    | models.Q(move_in_date__isnull=True)
                    | models.Q(move_out_date__gte=models.F("move_in_date"))
                ),
                name="lease_moveout_after_movein",
            ),
        ]

    def __str__(self):
        return (
            f"{self.unit} | "
            f"{self.start_date} - {self.end_date}"
        )


class LeaseIntentRecord(models.Model):
    """
    Audit record of a tenant's stated renewal or move-out intent.

    Only one record should normally be active at a time for a lease.
    Historical records remain available when an intent is withdrawn
    or replaced.
    """

    INTENT_CHOICES = [
        ("renew", "Plans to Renew"),
        ("vacate", "Plans to Vacate"),
    ]

    METHOD_CHOICES = [
        ("email", "Email"),
        ("written", "Written Notice"),
        ("portal", "Portal"),
        ("other", "Other"),
    ]

    lease = models.ForeignKey(
        Lease,
        on_delete=models.CASCADE,
        related_name="intent_records",
    )

    intent = models.CharField(
        max_length=20,
        choices=INTENT_CHOICES,
    )

    response_date = models.DateField()

    notice_method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
    )

    planned_move_out_date = models.DateField(
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_lease_intents",
    )

    withdrawn_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="withdrawn_lease_intents",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.lease} | "
            f"{self.get_intent_display()} | "
            f"{self.response_date}"
        )


class LeaseTenant(models.Model):
    """
    Connects tenants to leases.

    Supports multiple tenants on one lease.
    """

    ROLE_CHOICES = [
        ("primary", "Primary Tenant"),
        ("co_tenant", "Co-Tenant"),
        ("occupant", "Occupant"),
    ]

    lease = models.ForeignKey(
        Lease,
        on_delete=models.CASCADE,
        related_name="lease_tenants",
    )

    tenant = models.ForeignKey(
        TenantProfile,
        on_delete=models.PROTECT,
        related_name="lease_memberships",
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="co_tenant",
    )

    is_financially_responsible = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lease", "role", "tenant"]
        constraints = [
            models.UniqueConstraint(
                fields=["lease", "tenant"],
                name="unique_lease_tenant",
            )
        ]

    def __str__(self):
        return f"{self.tenant} → {self.lease}"