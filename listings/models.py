from django.db import models

# Create your models here.
from django.db import models

class Listing(models.Model):
    MLS_STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("sold", "Sold"),
    ]

    mls_id = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=255)

    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    zip_code = models.CharField(max_length=10)

    price = models.DecimalField(max_digits=12, decimal_places=2)
    beds = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    baths = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    sqft = models.IntegerField(null=True, blank=True)
    lot_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    property_type = models.CharField(max_length=100, blank=True)
    year_built = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=MLS_STATUS_CHOICES, default="active")

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    main_image_url = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} – {self.city}, {self.state}"
