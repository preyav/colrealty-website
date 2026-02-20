from django.db import models


class Lead(models.Model):
    SOURCE_CHOICES = [
        ("listing", "Listing"),
        ("rental", "Rental"),
    ]

    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id = models.PositiveIntegerField()  # listing.id or rental.id

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    message = models.TextField(blank=True)

    page_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # delivery tracking
    email_sent = models.BooleanField(default=False)
    hubspot_sent = models.BooleanField(default=False)
    hubspot_contact_id = models.CharField(max_length=64, blank=True)
    error = models.TextField(blank=True)

    def __str__(self):
        return f"{self.source_type}:{self.source_id} - {self.email}"
