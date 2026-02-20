from django.contrib import admin
from .models import Rental


@admin.register(Rental)
class RentalAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "city",
        "rent",
        "beds",
        "status",
    )

    list_filter = ("status", "city", "property_type")
    search_fields = ("title", "street_address", "city")
