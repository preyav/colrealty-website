from django.conf import settings
from django.db import models


class TenantProfile(models.Model):
    """
    Permanent tenant/contact record.

    A tenant may have multiple leases over time.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tenant_profile",
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )

    emergency_contact_name = models.CharField(
        max_length=200,
        blank=True,
    )

    emergency_contact_phone = models.CharField(
        max_length=30,
        blank=True,
    )

    notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email or f"Tenant #{self.pk}"