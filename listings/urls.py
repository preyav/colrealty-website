from django.urls import path
from .views import ListingListView, ListingDetailView

app_name = "listings"

urlpatterns = [
    path("", ListingListView.as_view(), name="list"),
    path("<int:pk>/", ListingDetailView.as_view(), name="detail"),
]

