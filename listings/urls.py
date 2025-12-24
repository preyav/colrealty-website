# listings/urls.py
from django.urls import path
from .views import ListingListView, ListingDetailView

app_name = "listings"

urlpatterns = [
    path("", ListingListView.as_view(), name="listing_list"),      # /listings/
    path("<int:pk>/", ListingDetailView.as_view(), name="listing_detail"),  # /listings/123/
]
