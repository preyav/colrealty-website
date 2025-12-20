from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Listing

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "city", "state", "price", "status", "is_featured")
    list_filter = ("status", "city", "state", "is_featured")
    search_fields = ("title", "street_address", "city", "zip_code", "mls_id")

