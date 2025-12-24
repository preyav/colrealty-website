# listings/urls.py
from django.urls import path
from .views import ListingListView, ListingDetailView

app_name = "listings"

urlpatterns = [
    # This will end up at /listings/ because config/urls.py prefixes it
    path("", ListingListView.as_view(), name="listing_list"),
    # This will be /listings/123/
    path("<int:pk>/", ListingDetailView.as_view(), name="listing_detail"),
]
