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

    contract_details = models.JSONField(default=dict, blank=True)

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

class LeaseDocument(models.Model):
    CATEGORY_CHOICES = [('lease', 'Lease'), ('amendment', 'Amendment'),
                        ('extension', 'Lease Extension'), ('animal', 'Animal Agreement'),
                        ('other', 'Other')]
    lease = models.ForeignKey(Lease, on_delete=models.PROTECT, related_name='documents')
    agreement = models.ForeignKey('LeaseAgreement', null=True, blank=True, on_delete=models.PROTECT, related_name='documents')
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    url = models.URLField(max_length=2000, blank=True)
    storage_key = models.CharField(max_length=1000, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.CheckConstraint(
            condition=(models.Q(storage_key='', url__gt='') | models.Q(url='', storage_key__gt='')),
            name='lease_document_file_or_link')]

    def __str__(self):
        return self.title


class LeaseAgreement(models.Model):
    KIND_CHOICES = [('extension','Lease Extension'),('amendment','Amendment'),
                    ('animal','Animal Agreement'),('addendum','Addendum'),('other','Other')]
    STATUS_CHOICES = [('draft','Draft'),('executed','Executed'),('void','Voided')]
    lease = models.ForeignKey(Lease, on_delete=models.PROTECT, related_name='agreements')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='extension')
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    effective_date = models.DateField()
    signed_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    rent_action = models.CharField(max_length=20, choices=[('unchanged','Remains the same'),('changed','Changed'),('unspecified','Not specified')], default='unspecified')
    monthly_rent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0'))])
    contact_action = models.CharField(max_length=20, choices=[('unchanged','Remains the same'),('changed','Changed'),('unspecified','Not specified')], default='unspecified')
    named_landlords = models.TextField(blank=True)
    named_tenants = models.TextField(blank=True)
    contact_details = models.TextField(blank=True)
    paragraph_references = models.CharField(max_length=500, blank=True)
    amendment_text = models.TextField(blank=True)
    return_deadline = models.DateField(null=True, blank=True)
    unsigned_outcome = models.CharField(max_length=20, choices=[('month_to_month','Month-to-month'),('terminate','Terminate'),('unspecified','Not specified')], default='unspecified')
    unsigned_rent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0'))])
    unsigned_effective_date = models.DateField(null=True, blank=True)
    signature_details = models.TextField(blank=True)
    review_notes = models.TextField(blank=True)
    source_key = models.CharField(max_length=255, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['effective_date','signed_date','pk']
        constraints = [models.UniqueConstraint(fields=['lease','source_key'], condition=~models.Q(source_key=''), name='unique_lease_agreement_source'),
            models.CheckConstraint(condition=(~models.Q(rent_action='changed') | models.Q(monthly_rent__isnull=False)), name='agreement_changed_rent_present')]

    def __str__(self):
        return self.title
