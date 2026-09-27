from django.db import models


class Vendor(models.Model):
    """
    Service provider used for property maintenance.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("pending", "Pending Verification"),
    ]

    name = models.CharField(max_length=255)

    company_name = models.CharField(
        max_length=255,
        blank=True,
    )

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name", "name"]

    def __str__(self):
        return self.company_name or self.name


class VendorTrade(models.Model):
    """
    Trade/category supported by a vendor.
    """

    TRADE_CHOICES = [
        ("plumbing", "Plumbing"),
        ("electrical", "Electrical"),
        ("hvac", "HVAC"),
        ("appliance", "Appliance"),
        ("general", "General Maintenance"),
        ("landscaping", "Landscaping"),
        ("roofing", "Roofing"),
        ("painting", "Painting"),
        ("flooring", "Flooring"),
        ("pest", "Pest Control"),
        ("locksmith", "Locksmith"),
        ("other", "Other"),
    ]

    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.CASCADE,
        related_name="trades",
    )

    trade = models.CharField(
        max_length=50,
        choices=TRADE_CHOICES,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["vendor", "trade"]
        constraints = [
            models.UniqueConstraint(
                fields=["vendor", "trade"],
                name="unique_vendor_trade",
            )
        ]

    def __str__(self):
        return f"{self.vendor} - {self.get_trade_display()}"