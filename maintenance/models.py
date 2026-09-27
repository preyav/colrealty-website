from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from leasing.models import Lease
from properties.models import PropertyUnit
from tenants.models import TenantProfile
from vendors.models import Vendor


class MaintenanceRequest(models.Model):
    """
    Initial maintenance issue reported by a tenant, staff member,
    or property manager.
    """

    CATEGORY_CHOICES = [
        ("plumbing", "Plumbing"),
        ("electrical", "Electrical"),
        ("hvac", "HVAC"),
        ("appliance", "Appliance"),
        ("structural", "Structural"),
        ("roofing", "Roofing"),
        ("pest", "Pest Control"),
        ("landscaping", "Landscaping"),
        ("security", "Security / Locks"),
        ("other", "Other"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
        ("emergency", "Emergency"),
    ]

    STATUS_CHOICES = [
        ("new", "New"),
        ("triaged", "Triaged"),
        ("under_review", "Under Review"),
        ("pending_information", "Pending Information"),
        ("approved", "Approved"),
        ("declined", "Declined"),
        ("converted", "Converted to Work Order"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    unit = models.ForeignKey(
        PropertyUnit,
        on_delete=models.PROTECT,
        related_name="maintenance_requests",
    )

    lease = models.ForeignKey(
        Lease,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_requests",
    )

    reported_by_tenant = models.ForeignKey(
        TenantProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="maintenance_requests",
    )

    reported_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reported_maintenance_requests",
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="other",
        db_index=True,
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="normal",
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        db_index=True,
    )

    permission_to_enter = models.BooleanField(default=False)

    tenant_availability = models.TextField(blank=True)

    # Structured availability used by the COL360 maintenance intake flow.
    # The legacy text field above is retained so existing records are not
    # destroyed when this feature is introduced.
    availability_date = models.DateField(
        null=True,
        blank=True,
    )

    availability_start_time = models.TimeField(
        null=True,
        blank=True,
    )

    availability_end_time = models.TimeField(
        null=True,
        blank=True,
    )

    review_notes = models.TextField(
        blank=True,
        help_text="Internal notes recorded when the request is reviewed.",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_maintenance_requests",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    PENDING_REASON_CHOICES = [
        ("tenant_details", "Contact tenant / obtain more details"),
        ("owner_authorization", "Owner authorization"),
        ("budget_review", "Budget / accounting review"),
        ("warranty_check", "Warranty verification"),
        ("property_inspection", "Property inspection"),
        ("other", "Other"),
    ]

    pending_reason = models.CharField(
        max_length=30,
        choices=PENDING_REASON_CHOICES,
        blank=True,
    )

    assigned_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_maintenance_reviews",
    )

    review_due_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.unit} - {self.title}"

    @property
    def review_is_overdue(self):
        return (
            self.status in {"under_review", "pending_information"}
            and self.review_due_at is not None
            and self.review_due_at < timezone.now()
        )

    @property
    def work_order(self):
        """Return the current work order, or the latest cancelled one.

        This compatibility property preserves existing presentation code after
        the relationship changes from one-to-one to one-to-many.
        """
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get(
            "work_orders"
        )
        if prefetched is not None:
            orders = sorted(
                prefetched,
                key=lambda item: (item.created_at, item.pk),
                reverse=True,
            )
            return next(
                (item for item in orders if item.status != "cancelled"),
                orders[0] if orders else None,
            )

        current = self.work_orders.exclude(status="cancelled").first()
        return current or self.work_orders.first()


class WorkOrder(models.Model):
    """
    Operational work item created from a MaintenanceRequest.
    """

    STATUS_CHOICES = [
        ("new", "New"),
        ("approved", "Approved"),
        ("assigned", "Assigned"),
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    maintenance_request = models.ForeignKey(
        MaintenanceRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="work_orders",
    )

    supersedes = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replacement_work_order",
        help_text="Cancelled work order replaced by this work order.",
    )

    unit = models.ForeignKey(
        PropertyUnit,
        on_delete=models.PROTECT,
        related_name="work_orders",
    )

    title = models.CharField(max_length=255)
    description = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="new",
        db_index=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_work_orders",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    actual_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["maintenance_request"],
                condition=(
                    Q(maintenance_request__isnull=False)
                    & ~Q(status="cancelled")
                ),
                name="maintenance_one_open_work_order",
            ),
        ]

    def clean(self):
        super().clean()
        if self._state.adding and self.scheduled_for:
            current_minute = timezone.now().replace(second=0, microsecond=0)
            if self.scheduled_for < current_minute:
                raise ValidationError(
                    {
                        "scheduled_for": (
                            "The scheduled date and time cannot be in the past."
                        )
                    }
                )

    def __str__(self):
        return f"WO-{self.pk or 'NEW'} | {self.unit} | {self.title}"


class VendorAssignment(models.Model):
    """
    Assignment of a vendor to a WorkOrder.
    """

    STATUS_CHOICES = [
        ("assigned", "Assigned"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="vendor_assignments",
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="work_order_assignments",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="assigned",
        db_index=True,
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    scheduled_for = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    vendor_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assigned_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["work_order", "vendor"],
                name="unique_workorder_vendor",
            )
        ]

    def __str__(self):
        return f"{self.vendor} → {self.work_order}"


class MaintenancePhoto(models.Model):
    """
    Photo or image documentation associated with a maintenance request.

    Examples:
    - Tenant-submitted issue photo
    - Before-repair photo
    - After-repair photo
    """

    PHOTO_TYPE_CHOICES = [
        ("issue", "Issue"),
        ("before", "Before Repair"),
        ("after", "After Repair"),
        ("other", "Other"),
    ]

    maintenance_request = models.ForeignKey(
        MaintenanceRequest,
        on_delete=models.CASCADE,
        related_name="photos",
    )

    photo_type = models.CharField(
        max_length=20,
        choices=PHOTO_TYPE_CHOICES,
        default="issue",
    )

    image = models.ImageField(
        max_length=500,
        upload_to="maintenance/photos/%Y/%m/",
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
    )

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_maintenance_photos",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"{self.maintenance_request} "
            f"- {self.get_photo_type_display()}"
        )


class WorkOrderStatusHistory(models.Model):
    """
    Audit trail for WorkOrder status changes.
    """

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    from_status = models.CharField(
        max_length=20,
        blank=True,
    )

    to_status = models.CharField(
        max_length=20,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="work_order_status_changes",
    )

    notes = models.TextField(blank=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return (
            f"{self.work_order}: "
            f"{self.from_status or 'new'} → {self.to_status}"
        )


class VendorQuoteRequest(models.Model):
    """A tracked request asking one vendor to quote a work order."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("viewed", "Viewed"),
        ("quote_received", "Quote Received"),
        ("declined", "Declined"),
        ("expired", "Expired"),
        ("cancelled", "Cancelled"),
    ]

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="quote_requests",
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="quote_requests",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    scope = models.TextField()
    instructions = models.TextField(blank=True)
    response_due = models.DateField(null=True, blank=True)
    delivery_channel = models.CharField(max_length=20, default="email")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_vendor_quotes",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Quote request: {self.vendor} - {self.work_order}"


class VendorEstimate(models.Model):
    """
    Estimate or quote submitted by a vendor for a work order.
    """

    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("expired", "Expired"),
    ]

    ENTRY_METHOD_CHOICES = [
        ("total", "Total amount only"),
        ("itemized", "Itemized cost breakdown"),
    ]

    SOURCE_CHOICES = [
        ("col360", "COL360 Quote Request"),
        ("phone", "Phone"),
        ("email", "Email"),
        ("text", "Text Message"),
        ("in_person", "In Person"),
        ("vendor_portal", "Vendor Portal"),
        ("other", "Other"),
    ]

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.CASCADE,
        related_name="vendor_estimates",
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="estimates",
    )

    quote_request = models.ForeignKey(
        VendorQuoteRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="estimates",
    )

    entry_method = models.CharField(
        max_length=20,
        choices=ENTRY_METHOD_CHOICES,
        default="total",
    )

    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="other",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    labor_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.00"))])
    materials_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.00"))])
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.00"))])
    other_fees = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.00"))])
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0.00"))])
    received_date = models.DateField(default=timezone.localdate)
    valid_through = models.DateField(null=True, blank=True)
    attachment = models.FileField(
        upload_to="maintenance/vendor_quotes/%Y/%m/",
        null=True,
        blank=True,
    )

    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        db_index=True,
    )

    submitted_at = models.DateTimeField(auto_now_add=True)

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_vendor_estimates",
    )

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return (
            f"{self.vendor} - {self.work_order} "
            f"- ${self.amount}"
        )


class VendorAward(models.Model):
    """The vendor decision for a work order, separate from received quotes."""

    STATUS_CHOICES = [
        ("pending_confirmation", "Pending Vendor Confirmation"),
        ("active", "Active"),
        ("revoked", "Revoked"),
    ]
    METHOD_CHOICES = [
        ("quote", "Selected Quote"),
        ("direct", "Direct Assignment / Quote Waived"),
    ]
    AWARD_REASON_CHOICES = [
        ("lowest_qualified_quote", "Lowest qualified quote"),
        ("better_scope", "Better scope of work"),
        ("faster_availability", "Faster availability"),
        ("trusted_vendor", "Preferred / trusted vendor"),
        ("warranty_advantage", "Warranty advantage"),
        ("better_materials", "Better materials"),
        ("owner_preference", "Owner preference"),
        ("other", "Other"),
    ]
    CHANGE_REASON_CHOICES = [
        ("vendor_unavailable", "Vendor unavailable"),
        ("vendor_declined", "Vendor declined the work"),
        ("missed_schedule", "Vendor missed the schedule"),
        ("price_changed", "Price or terms changed"),
        ("scope_issue", "Scope or capability issue"),
        ("compliance_issue", "Insurance or compliance issue"),
        ("other", "Other"),
    ]

    work_order = models.ForeignKey(
        WorkOrder, on_delete=models.CASCADE, related_name="vendor_awards"
    )
    vendor = models.ForeignKey(
        Vendor, on_delete=models.PROTECT, related_name="work_order_awards"
    )
    estimate = models.ForeignKey(
        VendorEstimate,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="awards",
    )
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="active", db_index=True
    )
    decision_reason = models.CharField(max_length=50, blank=True)
    decision_notes = models.TextField(blank=True)
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vendor_awards_made",
    )
    awarded_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vendor_awards_confirmed",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="vendor_awards_revoked",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(
        max_length=30, choices=CHANGE_REASON_CHOICES, blank=True
    )
    revocation_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-awarded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["work_order"],
                condition=Q(status__in=["pending_confirmation", "active"]),
                name="maintenance_one_current_vendor_award",
            )
        ]

    def clean(self):
        super().clean()
        if self.method == "quote" and not self.estimate_id:
            raise ValidationError({"estimate": "A quote award requires an estimate."})
        if self.estimate_id:
            if self.estimate.work_order_id != self.work_order_id:
                raise ValidationError({"estimate": "The quote belongs to another work order."})
            if self.estimate.vendor_id != self.vendor_id:
                raise ValidationError({"estimate": "The quote belongs to another vendor."})

    def __str__(self):
        return f"{self.vendor} - {self.work_order} ({self.get_status_display()})"

    @property
    def decision_reason_display(self):
        return dict(self.AWARD_REASON_CHOICES).get(
            self.decision_reason, self.decision_reason.replace("_", " ").title()
        )


class VendorInvoice(models.Model):
    """
    Final vendor invoice associated with a completed work order.
    """

    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("approved", "Approved"),
        ("paid", "Paid"),
        ("disputed", "Disputed"),
        ("void", "Void"),
    ]

    work_order = models.ForeignKey(
        WorkOrder,
        on_delete=models.PROTECT,
        related_name="vendor_invoices",
    )

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.PROTECT,
        related_name="invoices",
    )

    invoice_number = models.CharField(
        max_length=100,
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal("0.00")),
        ],
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="submitted",
        db_index=True,
    )

    invoice_date = models.DateField(
        null=True,
        blank=True,
    )

    due_date = models.DateField(
        null=True,
        blank=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_vendor_invoices",
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "invoice_number"],
                condition=~models.Q(invoice_number=""),
                name="unique_vendor_invoice_number",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(due_date__isnull=True)
                    | models.Q(invoice_date__isnull=True)
                    | models.Q(due_date__gte=models.F("invoice_date"))
                ),
                name="invoice_due_after_invoice_date",
            ),
        ]

    def __str__(self):
        invoice_label = self.invoice_number or f"Invoice #{self.pk}"
        return f"{self.vendor} - {invoice_label} - ${self.amount}"
