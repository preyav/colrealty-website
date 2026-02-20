# listings/urls.py
from django.urls import path
from .views import ListingListView, ListingDetailView, listing_markers

app_name = "listings"

urlpatterns = [
    path("", ListingListView.as_view(), name="listing_list"),
    path("markers/", listing_markers, name="markers"),  # ✅ add
    path("<int:pk>/", ListingDetailView.as_view(), name="listing_detail"),
]