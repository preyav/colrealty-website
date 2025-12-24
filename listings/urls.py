from django.urls import path
from .views import ListingListView, ListingDetailView

app_name = "listings"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("pages.urls", namespace="pages")),
    path("listings/", include("listings.urls", namespace="listings")),
    path("listings/", ListingListView.as_view(), name="listing_list"),
    path("listings/<int:pk>/", ListingDetailView.as_view(), name="listing_detail"),
]
