from django.db import models


class Rental(models.Model):

    mls_id = models.CharField(max_length=100, blank=True, null=True)

    title = models.CharField(max_length=200)

    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=50)
    zip_code = models.CharField(max_length=20)

    rent = models.DecimalField(max_digits=10, decimal_places=2)

    beds = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    baths = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    sqft = models.IntegerField(null=True, blank=True)

    property_type = models.CharField(max_length=100)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    main_image_url = models.URLField(blank=True, null=True)

    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=50,
        default="active",
        choices=[
            ("active", "Active"),
            ("leased", "Leased"),
            ("inactive", "Inactive"),
        ]
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return f"{self.title} - {self.city}"


    def full_address(self):
        return f"{self.street_address}, {self.city}, {self.state} {self.zip_code}"
